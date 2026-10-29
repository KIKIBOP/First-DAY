import os, re, sys, uuid, subprocess, json
from pathlib import Path
from config_manager import state_dir, atomic_json, load_json, settings
from validation import collection

def task_path(task_id):
    if not isinstance(task_id,str) or not re.fullmatch('[a-f0-9]{32}',task_id): raise ValueError('任务 ID 非法')
    d=state_dir()/'tasks'; d.mkdir(exist_ok=True)
    return d/(task_id+'.json')

def task_status(task_id):
    value=load_json(task_path(task_id))
    if value is None: raise ValueError('任务不存在')
    # Detect a worker lost to reboot/crash without claiming completion.
    if value['state'] in ('queued','running'):
        import time
        pulse=task_path(task_id).with_suffix('.heartbeat')
        latest=max(value.get('heartbeat',0),pulse.stat().st_mtime if pulse.exists() else 0)
        if time.time()-latest>180:
            value['state']='interrupted'; value['error']='后台任务未更新；可能已退出，请检查文件后重试'
    return value

def start(data, prepare=False):
    data=collection(data)
    cfg=settings()
    cfg.update({k:v for k,v in data.get('options',{}).items() if k in cfg})
    if not cfg['root']: raise ValueError('请先设置保存根目录')
    task_id=uuid.uuid4().hex; path=task_path(task_id)
    import time
    atomic_json(path,dict(id=task_id,state='queued',heartbeat=time.time(),data=data,
                          events=['正在通过浏览器获取原图'] if prepare else [],folder='',browser_preparing=prepare))
    if prepare:
        from browser_images import cleanup_stale, needed_slots
        cleanup_stale()
        return {'task_id':task_id,'image_slots':needed_slots(data,cfg)}
    _spawn(task_id)
    return {'task_id':task_id}

def _spawn(task_id):
    path=task_path(task_id)
    args=([sys.executable,'--worker',task_id] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).with_name('main.py')),'--worker',task_id])
    flags=(subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if os.name=='nt' else 0
    try:
        subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         creationflags=flags,start_new_session=os.name!='nt',close_fds=True)
    except Exception as e:
        task=load_json(path)
        task.update(state='failed',error='后台任务启动失败：'+str(e))
        atomic_json(path,task)
        from browser_images import cleanup
        cleanup(task_id)
        raise

def fail_preparation(data):
    task_id=data.get('task_id'); path=task_path(task_id); task=load_json(path)
    if task and task.get('browser_preparing'):
        task.update(state='failed',browser_preparing=False,error='浏览器原图传输中断，请重新采集或检查缺失文件')
        atomic_json(path,task)
    if not task or task['state'] not in ('queued','running'):
        from browser_images import cleanup
        cleanup(task_id)
    return {'recorded':True}

def finish_preparation(data):
    import time
    task_id=data.get('task_id'); path=task_path(task_id); task=task_status(task_id)
    if path.with_suffix('.cancel').exists() or task['state']=='cancelled':
        from browser_images import cleanup
        cleanup(task_id)
        raise InterruptedError('用户取消')
    if not task.get('browser_preparing') or task['state']!='queued':
        raise ValueError('任务已离开图片准备阶段')
    errors=data.get('errors',[])
    if not isinstance(errors,list) or len(errors)>2 or any(not isinstance(x,str) or len(x)>300 for x in errors):
        raise ValueError('图片获取结果无效')
    task['events'].extend(errors)
    task.update(browser_preparing=False,heartbeat=time.time())
    atomic_json(path,task)
    _spawn(task_id)
    return {'task_id':task_id}

def cancel(task_id):
    path=task_path(task_id)
    if not path.exists(): raise ValueError('任务不存在')
    path.with_suffix('.cancel').touch()
    task=load_json(path)
    if task.get('browser_preparing'):
        task.update(state='cancelled',browser_preparing=False)
        task['events'].append('用户取消')
        atomic_json(path,task)
    return {'requested':True}

def history():
    tasks=state_dir()/'tasks'
    if not tasks.exists(): return []
    paths=sorted(tasks.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]
    items=[]; size=0
    for p in paths:
        v=load_json(p)
        item=dict(id=v['id'],state=v['state'],title=v['data']['title'],url=v['data']['url'],folder=v.get('folder',''))
        size+=len(json.dumps(item,ensure_ascii=False).encode('utf-8'))
        if size>200_000: break
        items.append(item)
    return items
