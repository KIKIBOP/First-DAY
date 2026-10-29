/* Extensible DOM adapters. Target-domain candidate is NOT live-HTML validated. */
(() => {
  const validMagnet = value => {
    try {
      if (typeof value !== 'string' || value.length > 16384 || /[\x00-\x20]/.test(value)) return false;
      const u = new URL(value);
      return u.protocol === 'magnet:' && !u.host && !u.pathname && !u.hash && u.searchParams.getAll('xt').some(x =>
        /^urn:btih:(?:[a-f\d]{40}|[a-z2-7]{32})$/i.test(x) || /^urn:btmh:1220[a-f\d]{64}$/i.test(x));
    } catch { return false; }
  };
  function magnetKeys(value){
    return new URL(value).searchParams.getAll('xt').flatMap(xt=>{
      if(/^urn:btmh:1220[a-f\d]{64}$/i.test(xt)) return ['btmh:'+xt.slice(9).toLowerCase()];
      if(!/^urn:btih:(?:[a-f\d]{40}|[a-z2-7]{32})$/i.test(xt))return [];
      let value=xt.slice(9);
      if(value.length===32){
        const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';let bits=0,buffer=0,hex='';
        for(const ch of value.toUpperCase()){
          buffer=(buffer<<5)|alphabet.indexOf(ch);bits+=5;
          if(bits>=8){bits-=8;hex+=((buffer>>bits)&255).toString(16).padStart(2,'0');}
        }
        value=hex;
      }
      return ['btih:'+value.toLowerCase()];
    });
  }
  const SiteAdapters = [
    {id:'sehuatang-discuz-candidate', match:(doc,url)=> /(^|\.)sehuatang\.net$/i.test(url.hostname) && !!doc.querySelector('#thread_subject'), label:'目标站 Discuz 适配（已验证所提供 HTML，在线待真机验证）'},
    {id:'fixture-discuz-v1', match:(doc)=>!!doc.querySelector('#thread_subject, h1[data-thread-title]'), label:'示例 / Discuz 结构适配'}
  ];
  function extract(doc = document, base = location.href) {
    const adapter=SiteAdapters.find(a=>a.match(doc,new URL(base)));
    if(!adapter) throw Error('未找到可用的网站适配器');
    const title = doc.querySelector('#thread_subject, h1[data-thread-title]');
    const body = doc.querySelector('[id^="postmessage_"], [data-post-body]');
    if (!title || !body) throw Error('未找到支持的帖子结构。首版为示例 / Discuz 类适配器，真实论坛待适配。');
    // Discuz category link often sits beside #thread_subject, outside the span.
    const rawTitle=title.textContent.replace(/\s+/g,' ').trim();
    const categories=Array.from(title.closest('h1')?.querySelectorAll('a[href*="typeid="]') || []).map(a=>a.textContent.trim()).filter(Boolean);
    const fullTitle=[...categories.filter(c=>!rawTitle.includes(c)),rawTitle].join(' ');
    const absolute = s => { try { const u = new URL(s, base); return /^https?:$/.test(u.protocol) ? u.href : null; } catch { return null; } };
    const images = [];
    // Never search the whole page for largest images. Require an explicit preview region.
    let region = body.querySelector('[data-film-preview], .film-preview, #film-preview');
    let nodes=region?Array.from(region.querySelectorAll('img')):[];
    // Fallback is a precise filename pair inside first post body, never global image size.
    // Derive the film code from each title; the example's code/URLs are never hardcoded.
    const code=fullTitle.match(/\b[A-Z]{2,12}-\d{2,8}\b/i)?.[0];
    let namedPair=false;
    if(!region && code){
      const escaped=code.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
      const names=[new RegExp('(?:^|[ /?=&])'+escaped+'\\.(?:jpe?g|png|webp)(?:$|[ ?&#])','i'),new RegExp('(?:^|[ /?=&])'+escaped+'[-.][a-z0-9.-]+\\.(?:jpe?g|png|webp)(?:$|[ ?&#])','i')];
      const candidates=Array.from(body.querySelectorAll('img')).filter(img=>!img.closest('.avatar,.advertisement,.ad,.smilie'));
      const fields=img=>{
        // Real Discuz attachment names live in the image tooltip, not img.alt/title or the hashed URL.
        const menu=img.id?doc.getElementById(img.id+'_menu'):null;
        const group=img.closest('ignore_js_op,.ignore_js_op');
        const label=(menu && body.contains(menu)?menu:group)?.querySelector('.xs0 p strong, p strong')?.textContent || '';
        return ['alt','title','file','zoomfile','data-original','data-src','src'].map(k=>{try{return decodeURIComponent(img.getAttribute(k)||'');}catch{return '';}}).join(' ')+' '+label;
      };
      const groups=names.map(pattern=>candidates.filter(img=>pattern.test(fields(img))));
      if(groups.every(group=>group.length===1)&&groups[0][0]!==groups[1][0]){nodes=groups.map(group=>group[0]);namedPair=true;}
    }
    if (nodes.length) for (const img of nodes) {
      if (img.closest('.avatar,.advertisement,.ad,.smilie') || /avatar|smilie|logo/i.test(img.className)) continue;
      const link = img.closest('a')?.getAttribute('href');
      const attachment=img.closest('ignore_js_op,.ignore_js_op')?.querySelector('.aimg_tip a[href]')?.getAttribute('href');
      const fields = [img.getAttribute('zoomfile'), img.getAttribute('file'), img.getAttribute('data-original'), img.getAttribute('data-full'), img.getAttribute('data-zoom'), attachment];
      if (link && /\.(?:jpe?g|png|webp|gif|bmp|avif)(?:[?#]|$)/i.test(link)) fields.unshift(link);
      const srcset = (img.getAttribute('srcset') || '').split(',').map(x => x.trim().split(/\s+/)).filter(x=>x[0]);
      srcset.sort((a,b) => parseFloat(b[1] || '0') - parseFloat(a[1] || '0'));
      const explicit = fields.find(Boolean);
      const fallback = img.getAttribute('data-src') || img.getAttribute('data-lazy-src') || srcset[0]?.[0] || img.currentSrc || img.getAttribute('src');
      const url = absolute(explicit || fallback);
      let preview=null;
      // Render a small preview only from pixels the page already permits us to read.
      // Never refetch an untrusted image URL in the privileged popup.
      if(img.complete && img.naturalWidth){
        try{
          const canvas=doc.createElement('canvas');const scale=Math.min(1,180/img.naturalWidth,120/img.naturalHeight);
          canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));
          canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);
          const value=canvas.toDataURL('image/png');if(value.length<90000)preview=value;
        }catch{/* Cross-origin canvas: display URL text without loading it again. */}
      }
      if (url && !images.some(x=>x.url===url)) images.push({url, preview, confirmed:!!explicit, source:explicit?'DOM 原图字段 / 图片链接':'显示图，原图尚未确认'});
    }
    const candidates = [];
    for (const el of body.querySelectorAll('a,input,textarea,.blockcode li,[id^="code_"] li,[data-clipboard-text],[data-magnet],[onclick]')) {
      candidates.push(el.textContent || '', el.getAttribute('href') || '', el.value || '', el.getAttribute('data-clipboard-text') || '', el.getAttribute('data-magnet') || '', el.getAttribute('onclick') || '');
    }
    candidates.push(body.textContent);
    const magnets = [], keys = new Set();
    for (const source of candidates) for (const match of source.matchAll(/magnet:\?[^\s<>"'`]+/gi)) {
      const value = match[0].replace(/&amp;/gi,'&');
      if (!validMagnet(value)) continue;
      const hashKeys=magnetKeys(value);
      if(!hashKeys.some(key=>keys.has(key))){hashKeys.forEach(key=>keys.add(key));magnets.push(value);}
    }
    return {adapter:adapter.label,adapterId:adapter.id,title:fullTitle,originalTitle:[...categories.filter(c=>!rawTitle.includes(c)),title.textContent.trim()].join(' '),url:base,
      images:images.slice(0,2),imageCandidateCount:images.length,magnets,
      warnings:[...(!region && !namedPair?['未找到明确的影片预览区域或唯一的影片文件名配对，需要补充真实网站 DOM 适配']:[]),
        ...(images.length!==2?['预览区域图片数量不是两张，请检查识别结果']:[]),
        ...(images.some(x=>!x.confirmed)?['存在未确认原图的显示图，采集前需确认']:[])]};
  }
  globalThis.MediaCollectorAdapter = {extract,validMagnet,magnetKeys,SiteAdapters};
})();
