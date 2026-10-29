"""Bounded original-image transfer from the extension; never accepts local paths."""
import base64
import hashlib
import os
import shutil
import time
from pathlib import Path

from config_manager import atomic_json, load_json, state_dir
from image_downloader import MAX_BYTES, image_extension

CHUNK_BYTES = 192 * 1024


def needed_slots(data, config):
    from folder_manager import existing_folder, contained
    result=list(range(len(data['images'])))
    if not config.get('skip_existing', True): return result
    folder=existing_folder(config['root'],data['title'],data['url'])
    if folder is None: return result
    metadata=load_json(folder/'metadata.json',{})
    for record in metadata.get('images',[]):
        try:
            slot=record['slot']
            if type(slot) is not int or slot not in result: continue
            target=contained(config['root'],folder/record['file'])
            if record['url']==data['images'][slot]['url'] and target.is_file() and not target.is_symlink() and hashlib.sha256(target.read_bytes()).hexdigest()==record['sha256']:
                result.remove(slot)
        except (ValueError,OSError,KeyError,TypeError): pass
    return result


def cleanup_stale():
    from task_manager import task_path
    root=state_dir()/'browser-images'
    if not root.is_dir(): return
    for path in root.iterdir():
        if path.is_dir() and not path.is_symlink() and time.time()-path.stat().st_mtime>86400:
            try:
                task_path(path.name)
                shutil.rmtree(path)
            except (ValueError,OSError): pass


def transfer_dir(task_id):
    from task_manager import task_path
    task_path(task_id)  # Validate before using it as a path component.
    root = state_dir() / 'browser-images'
    root.mkdir(exist_ok=True)
    target = root / task_id
    if target.is_symlink():
        raise ValueError('图片暂存目录无效')
    target.mkdir(exist_ok=True)
    return target


def transfer(data):
    from task_manager import task_path, task_status
    task_id = data.get('task_id')
    task = task_status(task_id)
    if task.get('state') == 'cancelled' or task_path(task_id).with_suffix('.cancel').exists():
        raise InterruptedError('用户取消')
    if not task.get('browser_preparing') or task['state'] != 'queued':
        raise ValueError('任务不在浏览器图片接收阶段')
    slot = data.get('slot')
    if type(slot) is not int or not 0 <= slot < len(task['data']['images']):
        raise ValueError('图片序号无效')
    if data.get('action') == 'heartbeat':
        task_path(task_id).with_suffix('.heartbeat').touch()
        return {'waiting': True}
    folder = transfer_dir(task_id)
    part, ready, info_path = (folder / f'{slot}{ext}' for ext in ('.part', '.ready', '.json'))
    if any(p.is_symlink() for p in (part, ready, info_path)):
        raise ValueError('图片暂存文件无效')
    action = data.get('action')
    if action == 'begin':
        mime = data.get('mime', '')
        if not isinstance(mime, str) or len(mime) > 200:
            raise ValueError('图片类型无效')
        if part.exists() or ready.exists() or info_path.exists():
            raise ValueError('图片接收已开始')
        part.touch(exist_ok=False)
        atomic_json(info_path, {'url': task['data']['images'][slot]['url'], 'mime': mime})
    elif action == 'chunk':
        encoded = data.get('content')
        offset = data.get('offset')
        if not isinstance(encoded, str) or len(encoded) > CHUNK_BYTES * 4 // 3:
            raise ValueError('图片分块大小无效')
        payload = base64.b64decode(encoded, validate=True)
        if not payload or type(offset) is not int or offset != part.stat().st_size:
            raise ValueError('图片分块顺序无效')
        if offset + len(payload) > MAX_BYTES:
            raise ValueError('图片超过 25 MiB')
        with part.open('ab') as out:
            out.write(payload)
    elif action == 'finish':
        info = load_json(info_path)
        if part.stat().st_size > MAX_BYTES:
            raise ValueError('图片超过 25 MiB')
        payload = part.read_bytes()
        ext = image_extension(payload, info['mime'])
        info.update(ext=ext, sha256=hashlib.sha256(payload).hexdigest())
        atomic_json(info_path, info)
        os.replace(part, ready)
    else:
        raise ValueError('图片传输操作无效')
    task_path(task_id).with_suffix('.heartbeat').touch()
    return {'received': ready.stat().st_size if ready.exists() else part.stat().st_size}


def read_image(task_id, slot, url):
    folder = transfer_dir(task_id)
    ready, info_path = folder / f'{slot}.ready', folder / f'{slot}.json'
    if not ready.exists():
        return None
    if ready.is_symlink() or info_path.is_symlink() or ready.stat().st_size > MAX_BYTES:
        raise ValueError('浏览器原图暂存文件无效')
    info = load_json(info_path)
    payload = ready.read_bytes()
    if info['url'] != url or hashlib.sha256(payload).hexdigest() != info['sha256']:
        raise ValueError('浏览器原图完整性校验失败')
    return payload, image_extension(payload, info['mime'])


def cleanup(task_id):
    from task_manager import task_path
    task_path(task_id)
    path = state_dir() / 'browser-images' / task_id
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
