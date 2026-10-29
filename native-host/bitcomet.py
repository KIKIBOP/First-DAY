import os, re
from pathlib import Path
from validation import magnet

def check_bitcomet(config):
    result=dict(platform=os.name, configured_path=config.get('bitcomet_path',''), candidates=[], protocol_command='', associated=False)
    if os.name!='nt': return result | {'note':'待 Windows 真机验证'}
    import winreg
    for key in (r'Software\Classes\magnet\shell\open\command',):
        for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_CLASSES_ROOT):
            try:
                actual=key if hive==winreg.HKEY_CURRENT_USER else r'magnet\shell\open\command'
                with winreg.OpenKey(hive,actual) as k: result['protocol_command']=winreg.QueryValueEx(k,None)[0]
                if result['protocol_command']: break
            except OSError: pass
    # UserChoice ProgId takes precedence when available.
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\Shell\Associations\UrlAssociations\magnet\UserChoice') as k:
            prog=winreg.QueryValueEx(k,'ProgId')[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,prog+r'\shell\open\command') as k:
            result['protocol_command']=winreg.QueryValueEx(k,None)[0]
    except OSError: pass
    match=re.match(r'^\s*(?:"([^"]+\.exe)"|(.+?\.exe))(?:\s|$)',result['protocol_command'],re.I)
    exe=(match.group(1) or match.group(2)) if match else ''
    exe=os.path.expandvars(exe)
    result['protocol_executable']=exe
    result['associated']=bool(exe and Path(exe).name.lower() in ('bitcomet.exe','bitcomet_x64.exe') and Path(exe).is_file())
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY):
            for exe in ('BitComet.exe','BitComet_x64.exe'):
                try:
                    with winreg.OpenKey(hive,r'Software\Microsoft\Windows\CurrentVersion\App Paths'+'\\'+exe,0,winreg.KEY_READ|view) as k:
                        path=winreg.QueryValueEx(k,None)[0]
                    if Path(path).is_file() and path not in result['candidates']: result['candidates'].append(path)
                except OSError: pass
    return result

def launch(uri, config):
    magnet(uri)
    if os.name!='nt': raise RuntimeError('磁力协议调用仅支持 Windows；待真机验证')
    detection=check_bitcomet(config)
    if not detection['associated']:
        raise RuntimeError('尚未确认 Magnet 已关联 BitComet。请在 Windows 默认应用中设置后重试；不会向未知处理程序提交。')
    os.startfile(uri)
    return '已发送至系统磁力链接处理程序，请在 BitComet 中确认。请将任务保存目录设为本影片文件夹。'
