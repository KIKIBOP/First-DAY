"""Build a portable ZIP from reviewed source and an existing Windows runtime.

No downloaded program is executed. The supplied EXE and runtime are checked
against their package's checksum list, then reused without recompilation.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import shutil
import struct
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def tracked_files():
    result=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,check=True)
    files=[ROOT/name for name in result.stdout.decode('utf-8').split('\0') if name]
    required={'AGENTS.md','README.md','.gitignore','.gitattributes','package.json','requirements.txt',
              'extension/manifest.json','extension/popup-narrow.html','extension/popup_modes.js','native-host/main.py','native-host/browser_images.py',
              'native-host/tls_config.py','native-host/certs/cacert.pem','native-host/certs/CERTIFI-LICENSE.txt','native-host/certs/provenance.json',
              'installer/build_exe.bat','tools/build_portable.py','register.ps1','extension-id.txt'}
    names={path.relative_to(ROOT).as_posix() for path in files}
    if required-names:
        raise ValueError('必要源码或配置尚未加入 Git 暂存区：'+', '.join(sorted(required-names)))
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise ValueError('源码清单包含不存在的文件或链接：'+str(path))
    return sorted(files)


def pe64(path):
    with path.open('rb') as stream:
        if stream.read(2)!=b'MZ': raise ValueError('不是 Windows PE：'+str(path))
        stream.seek(0x3c); offset=struct.unpack('<I',stream.read(4))[0]
        stream.seek(offset)
        if stream.read(4)!=b'PE\0\0' or struct.unpack('<H',stream.read(2))[0]!=0x8664:
            raise ValueError('不是 Windows x64 程序：'+str(path))


def verify_base(base):
    expected={}
    for line in (base/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest,name=line.split(maxsplit=1)
        name=name.lstrip('*').replace('\\','/')
        if name.startswith('runtime/') or name=='MediaCollectorHost.exe':
            path=base/name
            if not path.resolve().is_relative_to(base.resolve()) or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                raise ValueError('原包运行文件校验失败：'+name)
            expected[name]=digest
    for name in ['MediaCollectorHost.exe','runtime/python.exe','runtime/python313.dll','runtime/Lib/site-packages/PIL/__init__.py']:
        if name not in expected: raise ValueError('原包运行文件缺失校验：'+name)
    pe64(base/'MediaCollectorHost.exe'); pe64(base/'runtime/python.exe')
    key=json.loads((ROOT/'extension/manifest.json').read_text(encoding='utf-8-sig'))['key']
    identity=''.join(chr(ord('a')+int(ch,16)) for ch in hashlib.sha256(base64.b64decode(key,validate=True)).hexdigest()[:32])
    if identity!=(ROOT/'extension-id.txt').read_text(encoding='utf-8-sig').strip():
        raise ValueError('扩展公钥与固定 ID 不一致')
    certs=ROOT/'native-host/certs'
    provenance=json.loads((certs/'provenance.json').read_text(encoding='utf-8-sig'))
    if hashlib.sha256((certs/'cacert.pem').read_bytes()).hexdigest()!=provenance['sha256']:
        raise ValueError('应用 CA 列表与来源记录不一致')
    return len(expected)


def zip_files(files, prefix, stamp):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for relative,data in files:
            entry=zipfile.ZipInfo(prefix+relative,date_time=stamp)
            entry.compress_type=zipfile.ZIP_DEFLATED
            entry.external_attr=0o100644<<16
            archive.writestr(entry,data)
    return output.getvalue()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-package',required=True,type=Path,help='已解压且含 SHA256SUMS.txt 的旧便携包')
    parser.add_argument('--out-dir',required=True,type=Path,help='构建暂存目录')
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    checked=verify_base(args.base_package)
    files=tracked_files()
    version=json.loads((ROOT/'extension/manifest.json').read_text(encoding='utf-8-sig'))['version']
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    epoch=int(os.environ.get('SOURCE_DATE_EPOCH') or subprocess.run(['git','show','-s','--format=%ct','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip())
    stamp=tuple(datetime.fromtimestamp(max(epoch,315532800),timezone.utc).timetuple()[:6])
    if args.check_only:
        print(json.dumps({'version':version,'source_files':len(files),'verified_runtime_files':checked}))
        return
    out=args.out_dir.resolve(); out.mkdir(parents=True,exist_ok=True)
    folder=out/'MediaCollector-Portable-x64'
    if folder.exists(): raise ValueError('构建目录已存在，请选择新的空暂存目录：'+str(folder))
    folder.mkdir()
    shutil.copytree(args.base_package/'runtime',folder/'runtime',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copy2(args.base_package/'MediaCollectorHost.exe',folder/'MediaCollectorHost.exe')
    for directory in ['extension','native-host','docs']:
        shutil.copytree(ROOT/directory,folder/directory,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ['register.ps1','unregister.ps1','extension-id.txt','首次使用-注册.bat','取消注册.bat','运行自检.bat','先读我-使用说明.txt','THIRD-PARTY-NOTICES.txt']:
        shutil.copy2(ROOT/name,folder/name)
    source=zip_files([(str(path.relative_to(ROOT)).replace('\\','/'),path.read_bytes()) for path in files],'chrome-media-collector/',stamp)
    (folder/'source-code.zip').write_bytes(source)
    source_path=out/f'MediaCollector-source-v{version}.zip'
    source_path.write_bytes(source)
    info=json.loads((args.base_package/'build-info.json').read_text(encoding='utf-8-sig'))
    info.update(version=version,built_on=datetime.fromtimestamp(epoch,timezone(timedelta(hours=8))).date().isoformat(),
                windows_execution='NOT RUN: awaiting Windows 11 host',launcher_reused=True,source_commit=commit)
    (folder/'build-info.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    contents=sorted(path for path in folder.rglob('*') if path.is_file())
    (folder/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.relative_to(folder).as_posix()+'\n' for path in contents),encoding='utf-8')
    package=out/f'MediaCollector-Portable-x64-v{version}.zip'
    package.write_bytes(zip_files([(path.relative_to(folder).as_posix(),path.read_bytes()) for path in sorted(folder.rglob('*')) if path.is_file()],folder.name+'/',stamp))
    for artifact in [source_path,package]:
        with zipfile.ZipFile(artifact) as archive:
            if archive.testzip() is not None: raise ValueError('ZIP 完整性验证失败')
        digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
        artifact.with_suffix(artifact.suffix+'.sha256').write_text(digest+'  '+artifact.name+'\n',encoding='utf-8')
        print(json.dumps({'file':str(artifact),'bytes':artifact.stat().st_size,'sha256':digest},ensure_ascii=False))


if __name__=='__main__': main()
