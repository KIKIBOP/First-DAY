import re, base64
from urllib.parse import urlsplit, parse_qs

def magnet(uri):
    if not isinstance(uri,str) or len(uri)>16384 or re.search(r'[\x00-\x20]',uri): raise ValueError('磁力链接非法')
    p=urlsplit(uri)
    if p.scheme.lower()!='magnet' or p.netloc or p.path or p.fragment: raise ValueError('磁力 URI 非法')
    xt=parse_qs(p.query).get('xt',[])
    if not any(re.fullmatch(r'urn:btih:(?:[a-fA-F0-9]{40}|[a-zA-Z2-7]{32})',x) or re.fullmatch(r'urn:btmh:1220[a-fA-F0-9]{64}',x) for x in xt):
        raise ValueError('缺少合法 BT v1/v2 哈希')
    return uri

def magnet_keys(uri):
    magnet(uri)
    keys=set()
    for xt in parse_qs(urlsplit(uri).query)['xt']:
        if re.fullmatch(r'urn:btih:(?:[a-fA-F0-9]{40}|[a-zA-Z2-7]{32})',xt):
            value=xt[9:]
            if len(value)==32: value=base64.b32decode(value.upper()).hex()
            keys.add('btih:'+value.lower())
        elif re.fullmatch(r'urn:btmh:1220[a-fA-F0-9]{64}',xt):
            keys.add('btmh:'+xt[9:].lower())
    return sorted(keys)

def magnet_key(uri):
    return '|'.join(magnet_keys(uri))


def web_url(url):
    if not isinstance(url,str) or len(url)>8192 or re.search(r'[\x00-\x20]',url): raise ValueError('URL 非法')
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password: raise ValueError('仅允许 HTTP(S) URL')
    if p.port not in (None,80,443): raise ValueError('不允许非标准端口')
    return url

def collection(data):
    if not isinstance(data,dict): raise ValueError('采集数据类型错误')
    title=data.get('title')
    if not isinstance(title,str) or not title.strip() or len(title)>4000: raise ValueError('标题非法')
    original=data.get('raw_title',title)
    if not isinstance(original,str) or len(original)>8000: raise ValueError('原始标题非法')
    web_url(data.get('url'))
    images=data.get('images',[])
    if not isinstance(images,list) or len(images)>2: raise ValueError('最多两张图片')
    for image in images:
        if not isinstance(image,dict): raise ValueError('图片格式错误')
        web_url(image.get('url'))
    magnets=data.get('magnets',[])
    if not isinstance(magnets,list) or len(magnets)>1: raise ValueError('请选择一条磁力链接')
    for uri in magnets: magnet(uri)
    options=data.get('options',{})
    if not isinstance(options,dict) or set(options)-{'save_images','save_magnet','auto_bitcomet','resubmit'}: raise ValueError('操作选项非法')
    if any(type(v) is not bool for v in options.values()): raise ValueError('操作选项必须为布尔值')
    return dict(title=title.strip(),raw_title=original,url=data['url'],images=[{'url':image['url']} for image in images],magnets=magnets,options=options)
