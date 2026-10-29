/* UI tests use mocked chrome APIs. They do not claim real Native Messaging integration. */
const {chromium}=require('playwright');const path=require('node:path');const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--allow-file-access-from-files','--disable-background-networking']});
 try{
  const page=await browser.newPage({viewport:{width:800,height:600}});
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
   }},storage:{local:{get:async key=>key==='lastTask'?{lastTask:localStorage.lastTask||undefined}:{popupLayout:JSON.parse(localStorage.popupLayout||'null')}}},tabs:{query:async()=>[{id:1,url:sample.url}]},scripting:{executeScript:async req=>req.files?[]:[{result:{page:sample}}]}};
  });
  await page.goto('http://127.0.0.1/popup.html');
  await page.waitForFunction(()=>!document.getElementById('collect').disabled);
  const checks={};
  checks['中文标题显示']=(await page.locator('#title').textContent()).includes('中文と日本語');
  checks['单磁力自动选择']=!!(await page.locator('#magnets').inputValue());
  checks['无远程图片重取']=await page.locator('img[src^="http"]').count()===0;
  checks['固定宽高生效且采集按钮无需滚动']=await page.evaluate(()=>{
    const body=document.body.getBoundingClientRect(),button=document.getElementById('collect').getBoundingClientRect();
    return body.width===500&&body.height===580&&button.bottom<=body.bottom&&button.top>0;
  });
  await page.locator('#collect').click();await page.waitForFunction(()=>document.getElementById('status').textContent.includes('采集完成'));
  const payload=await page.evaluate(()=>calls.find(c=>c.type==='start_collection').data);
  checks['当前标签页数据提交']=payload.url==='https://example.com/thread-123.html'&&payload.images.length===2&&payload.magnets.length===1;
  checks['不默认重发磁力']=payload.options.resubmit===false;
  checks['仅请求当前图片站点']=await page.evaluate(()=>permissionRequests.length===1&&JSON.stringify(permissionRequests[0].origins)===JSON.stringify(['https://cdn.example.com/*']));
  await page.reload();await page.waitForFunction(()=>document.getElementById('status').textContent.includes('采集完成'));
  checks['重开弹窗恢复查询']=await page.evaluate(()=>calls.some(c=>c.type==='get_task_status'));
  checks['打开影片目录可用']=await page.locator('#open').isEnabled();
  await page.locator('#pageDetails').evaluate(el=>el.open=true);
  await page.locator('.popup-content').evaluate(el=>el.scrollTop=el.scrollHeight);
  checks['展开来源后操作区仍可见且原图地址保留']=await page.evaluate(()=>{
    const button=document.getElementById('collect').getBoundingClientRect();
    return button.bottom<=document.body.getBoundingClientRect().bottom&&document.querySelectorAll('#imageSources p').length===2&&document.getElementById('imageSources').textContent.includes('https://cdn.example.com/preview.webp');
  });
  await page.evaluate(()=>localStorage.popupLayout=JSON.stringify({width:780,height:420}));
  await page.reload();await page.waitForFunction(()=>!document.getElementById('collect').disabled);
  checks['旧版保存的尺寸不再影响弹窗']=await page.evaluate(()=>document.body.getBoundingClientRect().width===500&&document.body.getBoundingClientRect().height===580);
  // Simulate the initial tiny viewport before a popup host negotiates content size.
  // This is a layout regression check, not an actual Chrome extension host test.
  await page.setViewportSize({width:25,height:25});
  await page.reload();await page.waitForFunction(()=>!document.getElementById('collect').disabled);
  const intrinsic=await page.evaluate(()=>{
    const body=document.body.getBoundingClientRect();
    return {width:body.width,height:body.height,rootWidth:document.documentElement.scrollWidth,
      rootHeight:document.documentElement.scrollHeight,contentHeight:document.querySelector('.popup-content').clientHeight};
  });
  checks['初始25像素视口仍提供完整内容尺寸']=intrinsic.width===500&&intrinsic.height===580&&intrinsic.rootWidth>=500&&intrinsic.rootHeight>=580&&intrinsic.contentHeight>200;
  await page.setViewportSize({width:500,height:580});
  checks['按内容尺寸展开后无横向溢出且操作区可见']=await page.evaluate(()=>document.documentElement.scrollWidth===500&&document.getElementById('collect').getBoundingClientRect().bottom<=580);
  if(process.env.POPUP_SCREENSHOT)await page.locator('body').screenshot({path:process.env.POPUP_SCREENSHOT});
  await page.setViewportSize({width:25,height:25});
  await page.goto('http://127.0.0.1/popup-narrow.html');
  await page.waitForFunction(()=>!document.getElementById('collect').disabled);
  checks['半宽入口在初始极小视口仍提供固定尺寸']=await page.evaluate(()=>{
    const body=document.body.getBoundingClientRect();
    return body.width===250&&body.height===580&&document.documentElement.scrollWidth>=250&&document.querySelector('.popup-content').clientHeight>200;
  });
  await page.setViewportSize({width:250,height:580});
  await page.locator('#pageDetails').evaluate(el=>el.open=true);
  await page.locator('.popup-content').evaluate(el=>el.scrollTop=el.scrollHeight);
  checks['窄版展开内容无横向溢出且全部按钮可见']=await page.evaluate(()=>document.documentElement.scrollWidth===250&&
    [...document.querySelectorAll('.controls button')].every(el=>{const box=el.getBoundingClientRect();return box.left>=0&&box.right<=250&&box.bottom<=580;}));
  await page.locator('#collect').click();await page.waitForFunction(()=>document.getElementById('status').textContent.includes('采集完成'));
  checks['窄版保留原图及磁力采集流程']=await page.evaluate(()=>{
    const request=calls.find(x=>x.type==='start_collection');return request.data.images.length===2&&request.data.magnets.length===1&&request.data.options.resubmit===false;
  });
  await page.locator('#pageDetails').evaluate(el=>el.open=false);
  await page.locator('.popup-content').evaluate(el=>el.scrollTop=0);
  if(process.env.POPUP_NARROW_SCREENSHOT)await page.locator('body').screenshot({path:process.env.POPUP_NARROW_SCREENSHOT});
  const result={ok:Object.values(checks).every(Boolean),checks};console.log(JSON.stringify(result,null,2));if(!result.ok)process.exitCode=1;
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
