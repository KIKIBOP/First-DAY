const HOST='com.chrome_media_collector.host';
import {NativeConnection} from './native_bridge.js';
import {downloadImages} from './browser_images.js';
import {imageOrigins} from './image_access.js';
import {restorePopupMode} from './popup_modes.js';

// Select a pre-sized HTML entry, rather than resizing a popup after it opens.
const restoreMenu=()=>restorePopupMode().catch(e=>console.warn('恢复菜单样式失败：'+e.message));
chrome.runtime.onInstalled.addListener(restoreMenu);
chrome.runtime.onStartup.addListener(restoreMenu);

chrome.runtime.onMessage.addListener((message,sender,respond)=>{
  if(sender.id!==chrome.runtime.id || !message || message.route!=='native') return;
  // Options may open in a tab. Authorize the extension page URL, not tab presence.
  let ownPage=false;
  try {
    const url=new URL(sender.url);
    ownPage=url.protocol==='chrome-extension:'&&url.hostname===chrome.runtime.id&&
      ['/popup.html','/popup-narrow.html','/options/index.html'].includes(url.pathname);
  } catch {}
  if(!ownPage) { respond({ok:false,error:'仅允许插件弹窗和设置页访问本地程序'}); return; }
  if(message.type==='start_collection' && message.data?.options?.save_images) {
    (async()=>{
      const data=message.data;
      if(!await chrome.permissions.contains({origins:imageOrigins(data.images)})) throw Error('请先允许访问当前图片站点');
      const connection=new NativeConnection();
      let result;
      try { result=await connection.request('prepare_collection',data); }
      catch(e) { connection.close(); throw e; }
      try { await chrome.storage.local.set({lastTask:result.task_id}); }
      catch(e) { await connection.request('fail_preparation',{task_id:result.task_id}); connection.close(); throw e; }
      respond({ok:true,data:result});
      // Native port owns the job after the popup closes; no page scripts run here.
      downloadImages(connection,result.task_id,data,result.image_slots).catch(()=>{
        chrome.runtime.sendNativeMessage(HOST,{type:'fail_preparation',data:{task_id:result.task_id}}).catch(()=>{});
      });
    })().catch(e=>respond({ok:false,error:e.message}));
    return true;
  }
  chrome.runtime.sendNativeMessage(HOST,{type:message.type,data:message.data || {}})
    .then(async result=>{
      if(result.ok && message.type==='start_collection') await chrome.storage.local.set({lastTask:result.data.task_id});
      respond(result);
    }).catch(e=>respond({ok:false,error:'本地程序未连接：'+e.message+'。请运行“首次使用-注册.bat”，或按源码说明注册本地程序。'}));
  return true;
});
