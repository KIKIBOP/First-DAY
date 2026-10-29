"""Portable Windows check; never downloads images or submits a magnet."""
import sys, io, json, hashlib, base64, subprocess, struct, tempfile
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    if sys.platform!='win32': raise RuntimeError('此自检仅在 Windows 64 位系统运行')
    import ssl, ctypes, winreg, PIL
    from PIL import Image
    from protocol import read_message, write_message
    from tls_config import trust_status
    assert ctypes.sizeof(ctypes.c_void_p)==8, '需要 Windows x64 运行环境'
    manifest=json.loads((root/'extension/manifest.json').read_text(encoding='utf-8'))
    key=base64.b64decode(manifest['key'],validate=True)
    extension_id=''.join(chr(ord('a')+int(x,16)) for x in hashlib.sha256(key).hexdigest()[:32])
    assert extension_id==(root/'extension-id.txt').read_text().strip(), '扩展 ID 与公钥不匹配'
    image=io.BytesIO();Image.new('RGB',(3,3),'blue').save(image,'PNG')
    with Image.open(io.BytesIO(image.getvalue())) as im:im.load();assert im.format=='PNG'
    request=io.BytesIO()
    for kind in ('get_status','get_settings'):write_message(request,{'type':kind,'data':{}})
    result=subprocess.run([str(root/'MediaCollectorHost.exe')],input=request.getvalue(),capture_output=True,timeout=20)
    if result.returncode: raise RuntimeError('启动器退出失败：'+result.stderr.decode('utf-8',errors='replace'))
    stream=io.BytesIO(result.stdout);status=read_message(stream);settings=read_message(stream)
    assert status and status.get('ok') and settings and settings.get('ok'), 'Native 二进制协议自检失败'
    assert read_message(stream) is None,'Native stdout 出现额外数据'
    assert status['data']['version']==manifest['version'], '扩展与本地程序版本不一致，请完整更新 extension 和 native-host'
    print('本地程序版本：'+status['data']['version']+' / 扩展版本：'+manifest['version'])
    print(f'内置 Python {sys.version.split()[0]} / Pillow {PIL.__version__} / Windows x64')
    trust=trust_status()
    assert trust['certificate_verification'] and trust['hostname_verification']
    print(f"HTTPS 信任库已加载 {trust['trusted_ca_count']} 个 CA，证书与主机名校验已开启（未连接图片站点）。")
    print('原图解码、本地启动器和 Native 二进制协议自检通过。')
    print('扩展 ID：'+extension_id)
    if not status['data']['bitcomet'].get('associated'):
        print('尚未确认 BitComet 的磁力协议关联；请在插件设置中检测。')
    print('本次自检没有下载图片、添加磁力或操作任何 BitComet 任务。')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('自检失败：'+str(e),file=sys.stderr);raise SystemExit(1)
