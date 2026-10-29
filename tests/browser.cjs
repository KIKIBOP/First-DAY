const {chromium}=require('playwright');
const fs=require('node:fs');const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-background-networking']});
 try{
  const page=await browser.newPage();
  await page.route('**/*',r=>r.abort());
  await page.setContent(fs.readFileSync(path.join(__dirname,'fixtures/thread.html'),'utf8'),{waitUntil:'domcontentloaded'});
  await page.addScriptTag({content:fs.readFileSync(path.join(__dirname,'../extension/adapters/forum.js'),'utf8')});
  const result=await page.evaluate(()=>{
   const p=MediaCollectorAdapter.extract(document,'https://example.com/thread-1.html');
   const checks={
    '主标题与实体解码':p.title==='[高清] 测试影片 ABC-123 & 日本語：完整主标题',
    '正文区域两张图':p.images.length===2,
    '优先外层原图链接':p.images[0].url==='https://cdn.example.com/cover.png',
    '懒加载原图':p.images[1].url==='https://cdn.example.com/preview.webp',
    '磁力提取及去重':p.magnets.length===2,
    'BTv2':p.magnets[1].includes('urn:btmh:1220'),
    '拒绝伪磁力':!MediaCollectorAdapter.validMagnet('magnet:?xt=bad'),
    '原图已确认':p.images.every(x=>x.confirmed)
   };
   const unsupported=new DOMParser().parseFromString('<h1>无适配</h1>','text/html');
   try{MediaCollectorAdapter.extract(unsupported,'https://example.com');checks['拒绝未知结构']=false;}catch{checks['拒绝未知结构']=true;}
   // Large ad outside preview does not enter results. Test fallback confidence and candidates separately.
   document.querySelector('[data-film-preview]').innerHTML='<img data-src="https://cdn.example.com/lazy.png"><img srcset="https://cdn.example.com/1.png 400w, https://cdn.example.com/2.png 1600w">';
   const fallback=MediaCollectorAdapter.extract(document,'https://example.com/thread-1.html');
   checks['懒加载回退']=fallback.images[0].url==='https://cdn.example.com/lazy.png';
   checks['srcset最高分辨率']=fallback.images[1].url==='https://cdn.example.com/2.png';
   checks['不猜测原图且警告']=fallback.images.every(x=>!x.confirmed)&&fallback.warnings.length>0;
   return {ok:Object.values(checks).every(Boolean),checks};
  });
  const expected=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/user-reference.json'),'utf8'));
  await page.setContent(fs.readFileSync(path.join(__dirname,'fixtures/user-reference.html'),'utf8'),{waitUntil:'domcontentloaded'});
  const reference=await page.evaluate(expected=>{
    const p=MediaCollectorAdapter.extract(document,expected.url);
    return {
      '用户范例完整标题含分类':p.title===expected.title,
      '用户范例磁力完整匹配与去重':p.magnets.length===1&&p.magnets[0]===expected.magnet,
      '用户范例两张图片文件名匹配':p.images.length===2&&expected.filenames.every((name,i)=>p.images[i].url.endsWith('/'+name)),
      'Discuz原图属性优先':p.images.every(x=>x.confirmed&&!x.url.includes('small')),
      '真实目标域名适配候选':p.adapterId==='sehuatang-discuz-candidate'
    };
  },expected);
  Object.assign(result.checks,reference);
  result.ok=Object.values(result.checks).every(Boolean);
  const actualHtml=fs.readFileSync(process.env.ORIGINAL_FIXTURE||path.join(__dirname,'fixtures/actual-thread-minimal.html'),'utf8');
  const actualChecks=await page.evaluate(({text,expected})=>{
    // Parse in an inert document: never execute uploaded page scripts or event handlers.
    const doc=new DOMParser().parseFromString(text,'text/html');
    const p=MediaCollectorAdapter.extract(doc,expected.url);
    return {
      '真实HTML完整标题含分类':p.title===expected.title,
      '真实HTML磁力精确匹配':p.magnets.length===1&&p.magnets[0]===expected.magnet,
      '真实HTML附件提示文件名配对':p.images.length===2,
      '真实HTML原图地址精确匹配':p.images.length===2&&p.images.every((image,i)=>image.url===expected.originalUrls[i]),
      '真实HTML不保存none.gif占位图':p.images.length===2&&p.images.every(image=>image.confirmed&&!image.url.endsWith('none.gif')),
      '真实HTML无识别歧义':p.warnings.length===0,
      '原始标题保留内部空格':p.originalTitle.includes('SORA-646  [')
    };
  },{text:actualHtml,expected});
  Object.assign(result.checks,actualChecks);result.ok=Object.values(result.checks).every(Boolean);
  console.log(JSON.stringify(result,null,2));if(!result.ok)process.exitCode=1;
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
