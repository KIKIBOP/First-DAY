import hashlib, os, time, logging, threading, tempfile
from pathlib import Path
from contextlib import contextmanager
from config_manager import settings, state_dir, atomic_json, load_json
from folder_manager import movie_folder, contained
from image_downloader import fetch
from validation import magnet_keys
from bitcomet import launch
from task_manager import task_path
from browser_images import read_image, cleanup as cleanup_images
from tls_config import ImageCertificateError

@contextmanager
def lock(name, cancelled):
    p=state_dir()/('lock-'+name)
    for _ in range(600):
        try:
            p.mkdir(); break
        except FileExistsError:
            if cancelled(): raise InterruptedError('用户取消')
            time.sleep(.1)
    else: raise RuntimeError('同一帖子另有任务运行，或存在异常中止的锁；请确认历史任务后清理锁目录')
    try: yield
    finally: p.rmdir()

def run(task_id):
    path=task_path(task_id); task=load_json(path); cfg=settings(); data=task['data']
    cfg.update({k:v for k,v in data.get('options',{}).items() if k in cfg})
    cancel=lambda:path.with_suffix('.cancel').exists()
    stop=threading.Event()
    # Persist a heartbeat independently of long socket reads / lock waits.
    def heartbeat():
        while not stop.wait(15):
            path.with_suffix('.heartbeat').touch()
    pulse=threading.Thread(target=heartbeat,daemon=True); pulse.start()
    def event(text):
        task['events'].append(text); task['heartbeat']=time.time(); atomic_json(path,task)
        logging.info('%s %s',task_id,text)
    try:
        task['state']='running'; event('开始采集')
        identity=data['url'].split('#')[0]
        with lock(hashlib.sha256(identity.encode()).hexdigest(),cancel):
            if cancel(): raise InterruptedError('用户取消')
            folder=movie_folder(cfg['root'],data['title'],identity)
            task['folder']=str(folder); event('影片目录已就绪')
            meta_path=contained(cfg['root'],folder/'metadata.json')
            old=load_json(meta_path,{})
            # Preserve prior records and successful dispatch claims across partial retries.
            meta=old | dict(title=data['title'],original_title=data.get('raw_title',data['title']),source_url=data['url'],images=old.get('images',[]),magnets=data['magnets'],updated_at=time.time())
            errors=[]
            if cfg['save_images']:
                if len(data['images'])!=2: errors.append('需要明确识别两张原图，请检查适配器')
                for i,image in enumerate(data['images']):
                    if cancel(): raise InterruptedError('用户取消')
                    base=('封面原图','预览原图')[i]
                    record=next((r for r in meta['images'] if r.get('slot')==i),None)
                    if cfg['skip_existing'] and record and record['url']==image['url']:
                        target=contained(cfg['root'],folder/record['file'])
                        if target.is_file() and not target.is_symlink() and hashlib.sha256(target.read_bytes()).hexdigest()==record['sha256']:
                            event(base+'已完整存在，跳过'); continue
                    event(base+'下载中')
                    for attempt in range(cfg['retries']+1):
                        try:
                            staged=read_image(task_id,i,image['url'])
                            payload,ext=staged if staged is not None else fetch(image['url'],data['url'],cancel)
                            target=contained(cfg['root'],folder/(base+ext))
                            # Never clobber an existing unknown/user-created image.
                            if target.exists():
                                if target.read_bytes()!=payload:
                                    target=contained(cfg['root'],folder/(base+'-'+hashlib.sha256(payload).hexdigest()[:12]+ext))
                            if not target.exists():
                                fd,temp=tempfile.mkstemp(prefix='.image-',dir=folder)
                                try:
                                    with os.fdopen(fd,'wb') as f: f.write(payload); f.flush(); os.fsync(f.fileno())
                                    # Publish atomically without replacing existing files. Windows rename also works on FAT/exFAT.
                                    try:
                                        if os.name=='nt': os.rename(temp,target)
                                        else: os.link(temp,target)
                                    except FileExistsError:
                                        if target.read_bytes()!=payload: raise ValueError('图片目标文件发生并发冲突')
                                finally:
                                    if os.path.exists(temp): os.unlink(temp)
                            meta['images']=[r for r in meta['images'] if r.get('slot')!=i]+[dict(slot=i,url=image['url'],file=target.name,sha256=hashlib.sha256(payload).hexdigest())]
                            atomic_json(meta_path,meta); event(base+'保存成功'); break
                        except InterruptedError: raise
                        except ImageCertificateError as e:
                            errors.append(base+'失败：'+str(e)); event(errors[-1]); break
                        except Exception as e:
                            if attempt==cfg['retries']: errors.append(base+'失败：'+str(e)); event(errors[-1])
                            else:
                                for _ in range(10*(attempt+1)):
                                    if cancel(): raise InterruptedError('用户取消')
                                    time.sleep(.1)
            if cancel(): raise InterruptedError('用户取消')
            if cfg['save_magnet']:
                target=contained(cfg['root'],folder/'磁力链接.txt')
                existing=target.read_text(encoding='utf-8') if target.exists() else ''
                additions=[m for m in data['magnets'] if m not in existing.splitlines()]
                if additions:
                    with target.open('a',encoding='utf-8') as f: f.write(('\n' if existing and not existing.endswith('\n') else '')+'\n'.join(additions)+'\n')
                event('磁力链接已保存' if data['magnets'] else '未选择磁力链接')
            submitted=meta.get('submitted',{})
            if cfg['auto_bitcomet'] and data['magnets']:
                uri=data['magnets'][0]; keys=magnet_keys(uri)
                # One global durable journal also prevents the same magnet on different posts being sent twice.
                with lock('magnet-dispatch',cancel):
                    journal_path=state_dir()/'magnet-journal.json'
                    journal=load_json(journal_path,{})
                    if any(key in submitted or key in journal for key in keys) and not data.get('options',{}).get('resubmit'):
                        event('该磁力此前已请求提交，跳过重复调用（未验证 BitComet 是否添加成功）')
                    else:
                        intent={'state':'dispatch_intent','time':time.time()}
                        for key in keys: submitted[key]=intent; journal[key]=intent
                        meta['submitted']=submitted
                        atomic_json(meta_path,meta); atomic_json(journal_path,journal)
                        if cancel(): raise InterruptedError('用户取消；已记录提交意图，下次需主动勾选再次发送')
                        try:
                            status=launch(uri,cfg)
                            intent['state']='protocol_requested'; event(status)
                        except Exception as e:
                            intent['state']='dispatch_unconfirmed'; errors.append(str(e)); event(str(e))
                        atomic_json(journal_path,journal)
            meta['submitted']=submitted; atomic_json(meta_path,meta)
            task['state']='partial' if errors else 'completed'; task['errors']=errors
            event('部分完成，请检查错误' if errors else '采集完成；协议提交不代表下载完成')
            if cfg['open_after']:
                try: open_folder(str(folder))
                except Exception as e: event('自动打开目录失败：'+str(e))
    except InterruptedError as e:
        task['state']='cancelled'; event(str(e))
    except Exception as e:
        task['state']='failed'; task['error']=str(e); event('失败：'+str(e))
    finally:
        stop.set(); pulse.join(timeout=2)
        try: cleanup_images(task_id)
        except OSError: logging.warning('图片暂存目录清理失败')

def open_folder(folder):
    cfg=settings()
    if not cfg['root']: raise ValueError('请先设置保存根目录')
    p=contained(cfg['root'],Path(folder))
    if not p.is_dir(): raise ValueError('目录不存在')
    if os.name!='nt': raise RuntimeError('打开目录待 Windows 真机验证')
    os.startfile(str(p))
    return {'opened':True}
