import {publicImageURL,imageOrigins} from './image_access.js';

const CHUNK_BYTES=192*1024;
const MAX_BYTES=25*1024*1024;
let ruleId=100000;
let initialized;

function initializeRules() {
  if(!initialized) initialized=(async()=>{
    const old=await chrome.declarativeNetRequest.getSessionRules();
    const ids=old.filter(rule=>rule.id>100000&&rule.id<200000).map(rule=>rule.id);
    if(ids.length) await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds:ids});
  })();
  return initialized;
}

function base64(bytes) {
  let value='';
  for(let i=0;i<bytes.length;i+=8192) value+=String.fromCharCode(...bytes.subarray(i,i+8192));
  return btoa(value);
}

async function receiveImage(connection,taskId,slot,image,source) {
  await initializeRules();
  const url=publicImageURL(image.url);
  if(!await chrome.permissions.contains({origins:imageOrigins([image])})) throw Error('尚未获得图片站点访问权限');
  const id=++ruleId;
  const controller=new AbortController();
  let reader, installed=false, checking=false;
  const timeout=setTimeout(()=>controller.abort(Error('浏览器原图下载超过 90 秒')),90000);
  const pulse=setInterval(async()=>{
    if(checking) return;
    checking=true;
    try {
      await connection.request('image_transfer',{task_id:taskId,slot,action:'heartbeat'});
    } catch(e) { controller.abort(e); }
    finally { checking=false; }
  },2000);
  try {
    // Modify only this extension's request for the selected original image path.
    // Never read/export browser Cookie headers or include signed page queries.
    const path=(url.origin+url.pathname).replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
    if(path.length<1500) {
      await chrome.declarativeNetRequest.updateSessionRules({addRules:[{
        id, priority:1,
        action:{type:'modifyHeaders',requestHeaders:[{header:'referer',operation:'set',value:new URL(source).origin+'/'}]},
        condition:{regexFilter:'^'+path+'(?:\\?|$)',isUrlFilterCaseSensitive:true,
          initiatorDomains:[chrome.runtime.id],requestDomains:[url.hostname],resourceTypes:['xmlhttprequest'],tabIds:[-1]}
      }]});
      installed=true;
    }
    const response=await fetch(url.href,{credentials:'include',redirect:'error',signal:controller.signal});
    if(!response.ok) throw Error('图片 HTTP 状态 '+response.status);
    const length=Number(response.headers.get('Content-Length') || 0);
    if(length>MAX_BYTES) throw Error('图片超过 25 MiB');
    if(!response.body) throw Error('图片响应为空');
    await connection.request('image_transfer',{task_id:taskId,slot,action:'begin',mime:response.headers.get('Content-Type') || ''});
    reader=response.body.getReader();
    let offset=0;
    while(true) {
      const {done,value}=await reader.read();
      if(done) break;
      if(offset+value.length>MAX_BYTES) throw Error('图片超过 25 MiB');
      for(let start=0;start<value.length;start+=CHUNK_BYTES) {
        const chunk=value.subarray(start,start+CHUNK_BYTES);
        await connection.request('image_transfer',{task_id:taskId,slot,action:'chunk',offset,content:base64(chunk)});
        offset+=chunk.length;
      }
    }
    await connection.request('image_transfer',{task_id:taskId,slot,action:'finish'});
  } finally {
    clearTimeout(timeout); clearInterval(pulse);
    controller.abort();
    try { await reader?.cancel(); } catch {}
    if(installed) await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds:[id]});
  }
}

export async function downloadImages(connection,taskId,data,slots=data.images.map((_,i)=>i)) {
  const errors=[];
  try {
    for(const slot of slots) {
      try { await receiveImage(connection,taskId,slot,data.images[slot],data.url); }
      catch(e) {
        const task=await connection.request('get_task_status',{task_id:taskId});
        if(task.state==='cancelled') break;
        errors.push(`${slot===0?'封面':'预览'}原图浏览器获取失败，将尝试本地下载：${String(e.message).slice(0,180)}`);
      }
    }
    await connection.request('finish_preparation',{task_id:taskId,errors});
  } finally { connection.close(); }
}
