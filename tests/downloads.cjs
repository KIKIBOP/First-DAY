/* Offline browser tests; Chrome permission/DNR/Native APIs are mocked explicitly. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');

(async()=>{
  const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,
    args:['--no-sandbox','--disable-background-networking']});
  try {
    const page=await browser.newPage();
    const root=path.resolve(__dirname,'../extension');
    await page.route('**/*',route=>{
      const url=new URL(route.request().url());
      if(url.hostname!=='127.0.0.1') return route.abort();
      const file=path.resolve(root,'.'+url.pathname);
      if(!file.startsWith(root+path.sep)) return route.abort();
      return route.fulfill({contentType:file.endsWith('.js')?'application/javascript':'text/html',
        body:fs.existsSync(file)?fs.readFileSync(file):'<html><body>offline tests</body></html>'});
    });
    await page.goto('http://127.0.0.1/test.html');
    const checks=await page.evaluate(async()=>{
      // Preserve module loading through the intercepted fixture server.
      const {downloadImages}=await import('/browser_images.js');
      const {imageOrigins}=await import('/image_access.js');
      const {NativeConnection}=await import('/native_bridge.js');
      const checks={};
      const data={url:'https://forum.example.com/thread-1.html?private=do-not-forward',
        images:[{url:'https://cdn.example.com/cover.jpg'},{url:'https://cdn.example.com/preview.jpg'}],
        options:{save_images:true}};
      const originalFetch=window.fetch;
      function environment({denied=false,httpError=false,cancelled=false}={}) {
        const calls=[],rules=[],requests=[];
        let closed=false;
        window.chrome={runtime:{id:'a'.repeat(32)},permissions:{contains:async()=>!denied},
          declarativeNetRequest:{getSessionRules:async()=>[],updateSessionRules:async rule=>rules.push(rule)}};
        const payload=new Uint8Array(1200001);
        for(let i=0;i<payload.length;i++) payload[i]=i%251;
        window.fetch=async(url,options)=>{
          requests.push({url,options});
          return new Response(new ReadableStream({start(controller){controller.enqueue(payload);controller.close();}}),
            {status:httpError?403:200,headers:{'Content-Type':'application/octet-stream'}});
        };
        const connection={request:async(type,detail)=>{
          calls.push({type,data:detail});
          if(cancelled && type==='image_transfer') throw Error('用户取消');
          if(type==='get_task_status') return {state:cancelled?'cancelled':'queued'};
          if(cancelled && type==='finish_preparation') throw Error('用户取消');
          return {};
        },close:()=>{closed=true;}};
        return {calls,rules,requests,payload,connection,closed:()=>closed};
      }
      let env=environment();
      await downloadImages(env.connection,'1'.repeat(32),data);
      const chunks=env.calls.filter(x=>x.type==='image_transfer'&&x.data.action==='chunk');
      checks['原图分块小于Native消息上限']=chunks.length>4&&chunks.every(x=>JSON.stringify(x).length<900000);
      const first=chunks.filter(x=>x.data.slot===0);
      let restored='',offset=0;
      let ordered=true;
      for(const item of first){ordered&&=item.data.offset===offset;const part=atob(item.data.content);restored+=part;offset+=part.length;}
      checks['分块顺序与原始字节完整保留']=ordered&&restored.length===env.payload.length&&Array.from(env.payload).every((v,i)=>restored.charCodeAt(i)===v);
      checks['浏览器请求使用当前会话']=env.requests.length===2&&env.requests.every(x=>x.options.credentials==='include');
      checks['不自动跟随未授权跳转']=env.requests.every(x=>x.options.redirect==='error');
      checks['两张原图均完成接收']=env.calls.filter(x=>x.type==='image_transfer'&&x.data.action==='finish').length===2;
      checks['图片准备结束后启动后台']=env.calls.at(-1).type==='finish_preparation'&&env.calls.at(-1).data.errors.length===0;
      const adds=env.rules.filter(x=>x.addRules).flatMap(x=>x.addRules);
      checks['来源规则仅作用于本扩展原图请求']=adds.length===2&&adds.every(x=>x.condition.initiatorDomains[0]===chrome.runtime.id&&x.condition.tabIds[0]===-1&&x.condition.requestDomains[0]==='cdn.example.com'&&x.condition.regexFilter.startsWith('^https://'));
      checks['来源不泄露帖子查询参数']=adds.every(x=>x.action.requestHeaders[0].value==='https://forum.example.com/');
      checks['请求结束清理临时来源规则']=env.rules.filter(x=>x.removeRuleIds).length===2&&env.closed();

      env=environment({httpError:true});
      await downloadImages(env.connection,'2'.repeat(32),data);
      checks['403保留原因并进入本地回退']=env.calls.at(-1).type==='finish_preparation'&&env.calls.at(-1).data.errors.length===2&&env.calls.at(-1).data.errors.every(x=>x.includes('403'));
      checks['403仍清理临时规则']=env.rules.filter(x=>x.removeRuleIds).length===2&&env.closed();

      env=environment({denied:true});
      await downloadImages(env.connection,'3'.repeat(32),data);
      checks['没有站点授权时不发网络请求']=env.requests.length===0&&env.calls.at(-1).data.errors.length===2;

      env=environment();
      await downloadImages(env.connection,'6'.repeat(32),data,[]);
      checks['完整图片存在时不重新下载']=env.requests.length===0&&env.calls.length===1&&env.calls[0].type==='finish_preparation';
      env=environment();
      await downloadImages(env.connection,'7'.repeat(32),data,[1]);
      checks['只下载指定缺失图片']=env.requests.length===1&&env.requests[0].url.endsWith('/preview.jpg');

      env=environment({cancelled:true});
      let cancelled=false;
      try { await downloadImages(env.connection,'4'.repeat(32),data); } catch(e) {cancelled=e.message.includes('取消');}
      checks['取消后停止其余图片并关闭连接']=cancelled&&env.requests.length===1&&env.closed();

      checks['相同图片站点只申请一个来源']=JSON.stringify(imageOrigins(data.images))===JSON.stringify(['https://cdn.example.com/*']);
      checks['拒绝本地地址及非HTTP图片']=['http://127.0.0.1/x','http://[::1]/x','http://localhost/x','file:///tmp/a','https://u:p@cdn.example.com/x'].every(url=>{
        try {imageOrigins([{url}]);return false;} catch {return true;}
      });

      // Exercise the real bridge queue with a mocked Chrome Native port.
      let reply,disconnect;
      const posted=[];
      const port={onMessage:{addListener:fn=>reply=fn},onDisconnect:{addListener:fn=>disconnect=fn},
        postMessage:msg=>{posted.push(msg.type);queueMicrotask(()=>reply({ok:true,data:msg.type}));},disconnect:()=>disconnect?.()};
      chrome.runtime.connectNative=()=>port;
      const bridge=new NativeConnection();
      const replies=await Promise.all([bridge.request('one'),bridge.request('two')]);
      bridge.close();
      checks['Native端口顺序请求不混淆响应']=JSON.stringify(posted)==='["one","two"]'&&JSON.stringify(replies)==='["one","two"]';

      // Run the actual background listener and ensure it responds before image work ends.
      env=environment();
      let listener, portReply, portDisconnect, portClosed=false;
      const order=[];
      chrome.runtime.onMessage={addListener:fn=>listener=fn};
      chrome.storage={local:{set:async()=>order.push('stored')}};
      chrome.runtime.connectNative=()=>({onMessage:{addListener:fn=>portReply=fn},onDisconnect:{addListener:fn=>portDisconnect=fn},
        postMessage:msg=>queueMicrotask(()=>{order.push(msg.type);portReply({ok:true,data:msg.type==='prepare_collection'?{task_id:'5'.repeat(32)}:{}});}),
        disconnect:()=>{portClosed=true;portDisconnect?.();}});
      window.fetch=originalFetch;
      await import('/background.js');
      window.fetch=async()=>new Response(new Uint8Array([1,2,3]),{headers:{'Content-Type':'image/png'}});
      let respond;
      const response=new Promise(resolve=>respond=value=>{order.push('responded');resolve(value);});
      const keepAlive=listener({route:'native',type:'start_collection',data},{id:chrome.runtime.id},respond);
      const result=await response;
      for(let i=0;i<200&&!portClosed;i++) await new Promise(resolve=>setTimeout(resolve,5));
      checks['弹窗关闭前已有可查询任务']=keepAlive===true&&result.ok&&result.data.task_id==='5'.repeat(32)&&order.indexOf('responded')<order.indexOf('finish_preparation');
      checks['后台完成后关闭Native长连接']=portClosed&&order.includes('finish_preparation');
      checks['页面内容脚本不能请求特权下载']=listener({route:'native',type:'start_collection',data},{id:chrome.runtime.id,tab:{id:9}},()=>{})===undefined;
      window.fetch=originalFetch;
      return checks;
    });
    const result={ok:Object.values(checks).every(Boolean),checks};
    console.log(JSON.stringify(result,null,2));
    if(!result.ok) process.exitCode=1;
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
