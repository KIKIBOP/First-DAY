/* Real options/background modules and Python protocol; Chrome APIs and Windows detection are mocked. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');

(async()=>{
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'collector-options-'));
  const project=path.resolve(__dirname,'..');
  function native(request) {
    const payload=Buffer.from(JSON.stringify(request));
    const header=Buffer.alloc(4);header.writeUInt32LE(payload.length);
    const result=spawnSync(process.env.PYTHON||'python3',[path.join(project,'native-host/main.py')],{
      input:Buffer.concat([header,payload]),env:{...process.env,MEDIA_COLLECTOR_STATE:path.join(temp,'state')},timeout:10000});
    if(result.error) throw result.error;
    if(result.status!==0 || result.stdout.length<4) throw Error(result.stderr.toString()||'Native process failed');
    const size=result.stdout.readUInt32LE(0);
    if(result.stdout.length!==size+4) throw Error('Invalid Native frame');
    return JSON.parse(result.stdout.subarray(4).toString());
  }
  native({type:'update_settings',data:{root:path.join(temp,'原目录'),save_images:true,save_magnet:false,retries:3}});
  let browser;
  try {
    browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,
      args:['--no-sandbox','--disable-background-networking']});
    const page=await browser.newPage();
    const ext=path.join(project,'extension');
    await page.exposeFunction('callNative',native);
    await page.route('**/*',route=>{
      const url=new URL(route.request().url());const file=path.resolve(ext,'.'+url.pathname);
      if(url.hostname!=='127.0.0.1'||!file.startsWith(ext+path.sep)||!fs.existsSync(file)) return route.abort();
      let body=fs.readFileSync(file);
      // Register the actual background listener before the actual options page starts.
      if(url.pathname==='/options/options.js') body=Buffer.concat([Buffer.from("await import('../background.js');\n"),body]);
      return route.fulfill({contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html',body});
    });
    await page.addInitScript(()=>{
      const id='a'.repeat(32);
      window.nativeRequests=[];
      window.openedTabs=[];
      window.chrome={storage:{local:{get:async key=>({[key]:JSON.parse(localStorage.getItem('chrome_'+key)||'null')}),
        set:async data=>{for(const [key,value] of Object.entries(data)) localStorage.setItem('chrome_'+key,JSON.stringify(value));}}},
        commands:{getAll:async()=>[{name:'_execute_action',shortcut:sessionStorage.shortcut??'Alt+Shift+Y'}]},
        tabs:{create:async detail=>openedTabs.push(detail)},runtime:{id,onMessage:{addListener:fn=>window.backgroundListener=fn},
        sendNativeMessage:async(host,request)=>{
          nativeRequests.push(request);
          const mode=sessionStorage.nativeMode;
          if(mode==='offline') throw Error('Specified native messaging host not found.');
          if(mode==='historyFailure'&&request.type==='get_status') return {ok:false,error:'采集历史读取失败'};
          if(request.type==='check_bitcomet') return {ok:true,data:{platform:'nt',associated:mode!=='noAssociation',
            protocol_executable:'C:\\Program Files\\BitComet\\BitComet_x64.exe',candidates:['C:\\Program Files\\BitComet\\BitComet_x64.exe']}};
          return window.callNative(request);
        },sendMessage:message=>new Promise(resolve=>{
          let replied=false;
          const keepAlive=backgroundListener(message,{id,url:'chrome-extension://'+id+'/options/index.html',tab:{id:7}},value=>{replied=true;resolve(value);});
          if(keepAlive!==true&&!replied) resolve(undefined);
        })}};
    });
    await page.goto('http://127.0.0.1/options/index.html');
    await page.waitForFunction(()=>/已连接|未连接/.test(document.getElementById('connection').textContent));
    const checks={};
    checks['设置标签页通过后台读取本地配置']=(await page.locator('#root').inputValue())===path.join(temp,'原目录');
    if(checks['设置标签页通过后台读取本地配置']) {
      checks['已保存的勾选项及重试次数正确恢复']=await page.locator('#save_images').isChecked()&&!(await page.locator('#save_magnet').isChecked())&&(await page.locator('#retries').inputValue())==='3';
      await page.locator('#root').fill(path.join(temp,'新目录'));
      await page.locator('#save_magnet').check();await page.locator('#skip_existing').uncheck();await page.locator('#retries').fill('4');
      await page.locator('#save').click();await page.waitForFunction(()=>document.getElementById('status').textContent.includes('设置已保存'));
      await page.reload();await page.waitForFunction(()=>document.getElementById('connection').textContent.includes('已连接'));
      checks['重新打开后从新Native进程恢复设置']=(await page.locator('#root').inputValue())===path.join(temp,'新目录')&&await page.locator('#save_magnet').isChecked()&&!(await page.locator('#skip_existing').isChecked())&&(await page.locator('#retries').inputValue())==='4';
      await page.locator('#detect').click();await page.waitForFunction(()=>document.getElementById('status').textContent.includes('BitComet'));
      checks['设置标签页可以检测BitComet关联']=(await page.locator('#status').textContent()).includes('已确认磁力链接关联 BitComet');
      await page.evaluate(()=>sessionStorage.nativeMode='noAssociation');await page.locator('#detect').click();
      await page.waitForFunction(()=>document.getElementById('status').textContent.includes('默认应用'));
      checks['安装存在但未关联时给出明确说明']=(await page.locator('#status').textContent()).includes('检测到 BitComet 安装路径');
      const saved=JSON.stringify(native({type:'get_settings'}).data);
      await page.evaluate(()=>sessionStorage.nativeMode='offline');await page.reload();
      await page.waitForFunction(()=>document.getElementById('connection').textContent.includes('未连接'));
      checks['连接失败时禁止保存空表单']=await page.locator('#save').isDisabled()&&await page.locator('#detect').isDisabled();
      checks['连接错误保留Chrome具体原因']=(await page.locator('#status').textContent()).includes('Specified native messaging host not found.');
      checks['连接失败不会覆盖磁盘设置']=saved===JSON.stringify(native({type:'get_settings'}).data);
      await page.evaluate(()=>sessionStorage.removeItem('nativeMode'));await page.locator('#reconnect').click();
      await page.waitForFunction(()=>document.getElementById('connection').textContent.includes('已连接'));
      checks['重连后恢复已有设置且无需重新填写']=(await page.locator('#root').inputValue())===path.join(temp,'新目录')&&await page.locator('#save').isEnabled();
      await page.evaluate(()=>sessionStorage.nativeMode='historyFailure');await page.reload();
      await page.waitForFunction(()=>document.getElementById('status').textContent.includes('历史'));
      checks['历史读取失败不误报设置连接中断']=await page.locator('#save').isEnabled()&&(await page.locator('#connection').textContent()).includes('已连接');
      const denied=await page.evaluate(()=>{
        const before=nativeRequests.length;const id=chrome.runtime.id;
        const sources=[{id,url:'https://forum.example/options/index.html',tab:{id:8}},
          {id:'b'.repeat(32),url:'chrome-extension://'+id+'/options/index.html'},
          {id,url:'chrome-extension://'+id+'/unexpected.html',tab:{id:9}},
          {id,tab:{id:10}}];
        for(const sender of sources) backgroundListener({route:'native',type:'get_settings'},sender,()=>{});
        return before===nativeRequests.length;
      });
      checks['网页内容脚本及未知扩展页面不能读取本地配置']=denied;
      checks['显示当前实际分配的弹窗快捷键']=(await page.locator('#shortcutStatus').textContent()).includes('Alt+Shift+Y');
      await page.locator('#shortcuts').click();
      checks['快捷键按钮打开Chrome原生配置页']=await page.evaluate(()=>openedTabs.at(-1).url==='chrome://extensions/shortcuts');
      await page.evaluate(()=>{sessionStorage.nativeMode='offline';sessionStorage.shortcut='';});await page.reload();
      await page.waitForFunction(()=>document.getElementById('connection').textContent.includes('未连接'));
      checks['快捷键未分配时提示手动设置']=(await page.locator('#shortcutStatus').textContent()).includes('未读取到已分配');
      await page.locator('#popupWidth').fill('740');await page.locator('#popupHeight').fill('480');await page.locator('#saveLayout').click();
      await page.waitForFunction(()=>document.getElementById('layoutStatus').textContent.includes('已保存'));
      await page.reload();await page.waitForFunction(()=>document.getElementById('popupWidth').value==='740');
      checks['本地程序离线时仍可保存并恢复弹窗大小']=(await page.locator('#popupHeight').inputValue())==='480';
      await page.locator('#popupWidth').fill('2000');await page.locator('#saveLayout').click();
      await page.waitForFunction(()=>document.getElementById('layoutStatus').textContent.includes('宽度应为'));
      checks['尺寸超限不会覆盖已保存值']=await page.evaluate(()=>JSON.parse(localStorage.chrome_popupLayout).width===740);
      await page.locator('#resetLayout').click();await page.waitForFunction(()=>document.getElementById('popupWidth').value==='640');
      checks['恢复默认尺寸不修改采集配置']=JSON.stringify(native({type:'get_settings'}).data)===saved;
    }
    const result={ok:Object.values(checks).every(Boolean),checks};
    console.log(JSON.stringify(result,null,2));if(!result.ok) process.exitCode=1;
  }finally{await browser?.close();fs.rmSync(temp,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
