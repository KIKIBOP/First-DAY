export function publicImageURL(value) {
  const url=new URL(value);
  const host=url.hostname.toLowerCase();
  if(!['https:','http:'].includes(url.protocol) || url.username || url.password ||
     (url.port && !['80','443'].includes(url.port)) || value.length>8192 ||
     !host.includes('.') || /^[\d.]+$/.test(host) || host.includes(':') ||
     /(?:^|\.)(?:localhost|local|internal|test|invalid)$/.test(host)) {
    throw Error('图片地址必须是公开网站的 HTTP(S) 地址');
  }
  url.hash='';
  return url;
}

export function imageOrigins(images) {
  return [...new Set(images.map(image=>publicImageURL(image.url).origin+'/*'))];
}
