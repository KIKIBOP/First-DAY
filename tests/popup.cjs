/* UI tests use mocked chrome APIs. They do not claim real Native Messaging integration. */
const {chromium}=require('playwright');const path=require('node:path');const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--allow-file-access-from-files','--disable-background-networking']});
 try{
  const page=await browser.newPage({viewport:{width:460,height:1000}});
  const ext=path.resolve(__dirname,'../extension');
  await page.route('**/*',async route=>{
    const url=new URL(route.request().url());
    const file=path.resolve(ext,'.'+url.pathname);
    if(url.hostname!=='127.0.0.1'||!file.startsWith(ext+path.sep)||!fs.existsSync(file))return route.abort();
    const mime=file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html';
    return route.fulfill({status:200,contentType:mime,body:fs.readFileSync(file)});
  });
  await page.addInitScript(()=>{
   const M='magnet:?xt=urn:btih:'+'a'.repeat(40);
   const sample={adapter:'UI 测试适配器',title:'[高清] 示例影片 ABC-123 · 中文と日本語',url:'https://example.com/thread-123.html',images:[{url:'https://cdn.example.com/cover.png',confirmed:true,source:'DOM 原图字段'},{url:'https://cdn.example.com/preview.webp',confirmed:true,source:'DOM 原图字段'}],magnets:[M],warnings:[]};
   const cfg={root:'D:\\影片收藏',bitcomet_path:'',auto_bitcomet:true,save_images:true,save_magnet:true,skip_existing:true,retries:2,open_after:false,log_level:'INFO'};
   window.calls=[];
   window.permissionRequests=[];
   window.chrome={permissions:{request:async request=>{permissionRequests.push(request);return true;}},runtime:{id:'a'.repeat(32),openOptionsPage:async()=>{},sendMessage:async msg=>{
    calls.push(msg);
    let data;
    switch(msg.type){
     case 'get_settings':data=cfg;break;
     case 'get_status':data={history:[]};break;
     case 'start_collection':localStorage.lastTask='a'.repeat(32);data={task_id:'a'.repeat(32)};break;
     case 'get_task_status':data={id:'a'.repeat(32),state:'completed',folder:'D:\\影片收藏\\示例',data:sample,events:['封面原图保存成功','预览原图保存成功','已发送至系统磁力链接处理程序，请在 BitComet 中确认。']};break;
     default:data={};
    }return {ok:true,data};
   }},storage:{local:{get:async()=>({lastTask:localStorage.lastTask||undefined})}},tabs:{query:async()=>[{id:1,url:sample.url}]},scripting:{executeScript:async req=>req.files?[]:[{result:{page:sample}}]}};
  });
  await page.goto('http://127.0.0.1/popup.html');
  await page.waitForFunction(()=>!document.getElementById('collect').disabled);
  const checks={};
  checks['中文标题显示']=(await page.locator('#title').textContent()).includes('中文と日本語');
  checks['单磁力自动选择']=!!(await page.locator('#magnets').inputValue());
  checks['无远程图片重取']=await page.locator('img[src^="http"]').count()===0;
  await page.locator('#collect').click();await page.waitForFunction(()=>document.getElementById('status').textContent.includes('采集完成'));
  const payload=await page.evaluate(()=>calls.find(c=>c.type==='start_collection').data);
  checks['当前标签页数据提交']=payload.url==='https://example.com/thread-123.html'&&payload.images.length===2&&payload.magnets.length===1;
  checks['不默认重发磁力']=payload.options.resubmit===false;
  checks['仅请求当前图片站点']=await page.evaluate(()=>permissionRequests.length===1&&JSON.stringify(permissionRequests[0].origins)===JSON.stringify(['https://cdn.example.com/*']));
  await page.reload();await page.waitForFunction(()=>document.getElementById('status').textContent.includes('采集完成'));
  checks['重开弹窗恢复查询']=await page.evaluate(()=>calls.some(c=>c.type==='get_task_status'));
  checks['打开影片目录可用']=await page.locator('#open').isEnabled();
  if(process.env.POPUP_SCREENSHOT)await page.screenshot({path:process.env.POPUP_SCREENSHOT,fullPage:true});
  const result={ok:Object.values(checks).every(Boolean),checks};console.log(JSON.stringify(result,null,2));if(!result.ok)process.exitCode=1;
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
