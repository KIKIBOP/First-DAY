"""Pinned public DNS address per connection, HTTPS SNI retained; no proxy/cookies."""
import http.client, socket, ssl, ipaddress, io, warnings, time
from urllib.parse import urlsplit, urljoin
from PIL import Image
from validation import web_url
from tls_config import create_context, certificate_error
MAX_BYTES=25*1024*1024
Image.MAX_IMAGE_PIXELS=60_000_000
FORMATS={'JPEG':('.jpg','image/jpeg'),'PNG':('.png','image/png'),'WEBP':('.webp','image/webp'),'GIF':('.gif','image/gif'),'BMP':('.bmp','image/bmp'),'AVIF':('.avif','image/avif')}

def public_addresses(host,port):
    values=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    addresses=[]
    for family,_,_,_,addr in values:
        ip=ipaddress.ip_address(addr[0])
        if not ip.is_global or getattr(ip,'ipv4_mapped',None) and not ip.ipv4_mapped.is_global:
            raise ValueError('图片地址指向本地或保留网络')
        addresses.append((family,addr))
    if not addresses: raise ValueError('DNS 未返回地址')
    return addresses

def image_extension(data,mime):
    with warnings.catch_warnings():
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as im:
            fmt=im.format
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            im.load()
        if fmt not in FORMATS: raise ValueError('不支持的图片格式')
        ext,expected=FORMATS[fmt]
        declared=mime.split(';')[0].strip().lower()
        # Attachment servers commonly return generic binary MIME. Decode the complete
        # original bytes first; an explicit, conflicting image type remains an error.
        if declared not in ('','application/octet-stream','binary/octet-stream',expected):
            raise ValueError('图片 MIME 与实际内容不符')
        return ext

def fetch(url,referer,cancel=lambda:False):
    web_url(referer)
    deadline=time.monotonic()+90
    for redirect in range(6):
        if time.monotonic()>deadline: raise TimeoutError('图片下载总时限 90 秒')
        if cancel(): raise InterruptedError('用户取消')
        web_url(url); p=urlsplit(url); port=p.port or (443 if p.scheme=='https' else 80)
        family,address=public_addresses(p.hostname,port)[0]
        conn=http.client.HTTPConnection(p.hostname,port,timeout=20)
        sock=socket.socket(family,socket.SOCK_STREAM); sock.settimeout(20)
        try:
            sock.connect(address)
            if p.scheme=='https':
                try: sock=create_context().wrap_socket(sock,server_hostname=p.hostname)
                except ssl.SSLCertVerificationError as error: raise certificate_error(error) from error
            conn.sock=sock
            headers={'User-Agent':'ChromeMediaCollector/0.1','Accept':'image/*'}
            # Do not leak signed URLs/full post query to another origin.
            r=urlsplit(referer)
            headers['Referer']=referer if (p.scheme,p.netloc)==(r.scheme,r.netloc) else r.scheme+'://'+r.netloc+'/'
            conn.request('GET',(p.path or '/')+('?' + p.query if p.query else ''),headers=headers)
            response=conn.getresponse()
            if response.status in (301,302,303,307,308):
                target=urljoin(url,response.getheader('Location',''))
                if p.scheme=='https' and urlsplit(target).scheme!='https': raise ValueError('拒绝 HTTPS 降级重定向')
                url=target; continue
            if response.status!=200: raise ValueError('图片 HTTP 状态 '+str(response.status)+'；受登录保护的图片请等待浏览器会话获取适配')
            size=response.getheader('Content-Length')
            if size and int(size)>MAX_BYTES: raise ValueError('图片超过 25 MiB')
            data=bytearray()
            while True:
                if cancel(): raise InterruptedError('用户取消')
                if time.monotonic()>deadline: raise TimeoutError('图片下载总时限 90 秒')
                chunk=response.read(64*1024)
                if not chunk: break
                data.extend(chunk)
                if len(data)>MAX_BYTES: raise ValueError('图片超过 25 MiB')
            data=bytes(data)
            return data,image_extension(data,response.getheader('Content-Type',''))
        finally:
            conn.close(); sock.close()
    raise ValueError('重定向次数过多')
