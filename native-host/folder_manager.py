import hashlib, re
from pathlib import Path
from config_manager import atomic_json, load_json

def safe_name(title):
    s=re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title).strip(' .')
    if not s: s='未命名影片'
    if re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)',s,re.I): s='_'+s
    # Limit UTF-16 code units, not Python code points.
    s=s.encode('utf-16-le')[:160].decode('utf-16-le',errors='ignore').rstrip(' .')
    return s

def contained(root, path):
    root=Path(root).resolve(); path=Path(path).resolve()
    if path == root or not path.is_relative_to(root): raise ValueError('路径超出影片根目录')
    return path

def existing_folder(root, title, identity):
    base=Path(root).resolve()
    if not base.is_dir(): return None
    name=safe_name(title); identity=identity.split('#')[0]
    legacy=name+' ['+hashlib.sha256(identity.encode()).hexdigest()[:10]+']'
    candidates=sorted(base.iterdir(),key=lambda p:p.name!=legacy)
    for path in candidates:
        if not (path.name.casefold()==name.casefold() or path.name==legacy or
                re.fullmatch(re.escape(name)+r' \(\d+\)',path.name,re.I)):
            continue
        if not path.is_dir() or path.is_symlink(): continue
        try:
            meta=load_json(contained(base,path/'metadata.json'),{})
            source=meta.get('source_url') if isinstance(meta,dict) else None
            if isinstance(source,str) and source.split('#')[0]==identity:
                return contained(base,path)
        except (ValueError,OSError): pass
    return None

def movie_folder(root, title, identity):
    if not root or not Path(root).is_absolute(): raise ValueError('请先设置保存根目录')
    base=Path(root).resolve(); base.mkdir(parents=True,exist_ok=True)
    identity=identity.split('#')[0]
    name=safe_name(title)
    owned=existing_folder(base,title,identity)
    if owned is not None: return owned

    def belongs(path):
        if not path.is_dir() or path.is_symlink(): return False
        try:
            meta=load_json(contained(base,path/'metadata.json'),{})
            source=meta.get('source_url') if isinstance(meta,dict) else None
            return isinstance(source,str) and source.split('#')[0]==identity
        except (ValueError,OSError):
            return False

    # Keep existing download destinations usable; never rename a BitComet path here.
    legacy=base/(name+' ['+hashlib.sha256(identity.encode()).hexdigest()[:10]+']')
    if belongs(legacy): return contained(base,legacy)
    for number in range(1,10001):
        candidate=name if number==1 else f'{name} ({number})'
        # Treat names case-insensitively on every development platform, as Windows does.
        existing=next((p for p in base.iterdir() if p.name.casefold()==candidate.casefold()),None)
        if existing is not None:
            if belongs(existing): return contained(base,existing)
            continue
        path=contained(base,base/candidate)
        try: path.mkdir()
        except FileExistsError:
            if belongs(path): return path
            continue
        try: atomic_json(path/'metadata.json',{'source_url':identity})
        except Exception:
            try: path.rmdir()
            except OSError: pass
            raise
        return path
    raise ValueError('同名目录过多，请调整帖子标题或保存根目录')
