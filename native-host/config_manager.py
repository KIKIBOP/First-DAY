import json, os, tempfile
from pathlib import Path

DEFAULTS = dict(root='', bitcomet_path='', auto_bitcomet=True, save_images=True,
                save_magnet=True, skip_existing=True, retries=2, open_after=False, log_level='INFO')

def state_dir():
    base = os.environ.get('MEDIA_COLLECTOR_STATE')
    p = Path(base) if base else Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'.local/share')))/'ChromeMediaCollector'
    p.mkdir(parents=True, exist_ok=True)
    return p

def atomic_json(path, value):
    path = Path(path)
    fd, temp = tempfile.mkstemp(prefix='.collector-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def load_json(path, default=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError: return default

def settings():
    return DEFAULTS | load_json(state_dir()/'settings.json', {})

def update_settings(changes):
    if not isinstance(changes, dict) or set(changes)-set(DEFAULTS):
        raise ValueError('未知设置')
    cfg = settings() | changes
    for k,v in DEFAULTS.items():
        if type(cfg[k]) is not type(v): raise ValueError('设置类型错误: '+k)
    if not 0 <= cfg['retries'] <= 5: raise ValueError('重试次数应为 0–5')
    if cfg['log_level'] not in ('DEBUG','INFO','WARNING','ERROR'): raise ValueError('日志级别无效')
    if cfg['root']:
        p=Path(cfg['root'])
        if not p.is_absolute(): raise ValueError('根目录必须为绝对路径')
        if os.name=='nt' and (str(p).startswith('\\\\') or len(str(p))>110):
            raise ValueError('首版仅支持长度不超过 110 字符的本地绝对根目录')
        p.mkdir(parents=True,exist_ok=True)
        cfg['root']=str(p.resolve())
    if cfg['bitcomet_path']:
        p=Path(cfg['bitcomet_path'])
        if p.name.lower() not in ('bitcomet.exe','bitcomet_x64.exe') or not p.is_file():
            raise ValueError('请选择存在的 BitComet.exe 或 BitComet_x64.exe')
    atomic_json(state_dir()/'settings.json',cfg)
    return cfg
