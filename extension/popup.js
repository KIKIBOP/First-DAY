import {native,$,report} from './common.js';
import {imageOrigins} from './image_access.js';
let page, cfg, taskId, folder='', timer;
const terminal=['completed','partial','failed','cancelled','interrupted'];
const stateNames={queued:'排队中',running:'采集中',completed:'采集完成',partial:'部分完成',failed:'失败',cancelled:'已取消',interrupted:'已中断'};
async function poll(){
  if(!taskId) return;
  try {
    const task=await native('get_task_status',{task_id:taskId});
    folder=task.folder || folder;
    $('open').disabled=!folder; $('copyFolder').disabled=!folder;
    $('cancel').disabled=terminal.includes(task.state);
    $('status').textContent=`任务 ${task.id}\n状态：${stateNames[task.state] || task.state}\n`+task.events.join('\n')+(folder?'\n保存目录：'+folder:'')+(task.error?'\n'+task.error:'');
    if(terminal.includes(task.state)){clearInterval(timer); $('collect').disabled=!page || !cfg; $('repair').disabled=!page || !cfg;}
  } catch(e){clearInterval(timer);report(e);}
}
function watch(id){taskId=id;clearInterval(timer);poll();timer=setInterval(poll,1200);}
async function collect(repair=false){
  try{
    if(!page || !cfg) throw Error('页面或本地程序尚未准备好');
    const wantsImages=$('save_images').checked;
    if(wantsImages && page.images.length!==2) throw Error('需要识别两张预览图片；请补充站点适配');
    if(wantsImages && page.warnings.length && !$('confirmImages').checked) throw Error('请先检查并确认图片识别结果');
    const magnets=$('magnets').value?[$('magnets').value]:[];
    if($('auto_bitcomet').checked && !magnets.length && !repair) throw Error('请先选择一条磁力链接');
    $('collect').disabled=true; $('repair').disabled=true;
    if(wantsImages) {
      $('status').textContent='正在准备原图下载，请允许访问所识别的图片站点。';
      const granted=await chrome.permissions.request({origins:imageOrigins(page.images)});
      if(!granted) throw Error('未获得图片站点访问权限。请允许后重试，或取消勾选保存图片。');
    }
    const result=await native('start_collection',{title:page.title,raw_title:page.originalTitle || page.title,url:page.url,images:page.images.map(x=>({url:x.url})),magnets,
      options:{save_images:wantsImages,save_magnet:$('save_magnet').checked,auto_bitcomet:repair?false:$('auto_bitcomet').checked,resubmit:repair?false:$('resubmit').checked}});
    watch(result.task_id);
  }catch(e){report(e);$('collect').disabled=!page || !cfg;$('repair').disabled=!page || !cfg;}
}
$('collect').onclick=()=>collect();$('repair').onclick=()=>collect(true);
$('options').onclick=()=>chrome.runtime.openOptionsPage();
$('copyFolder').onclick=()=>navigator.clipboard.writeText(folder).then(()=>{$('status').textContent+='\n保存目录已复制';}).catch(report);
$('open').onclick=()=>native('open_folder',{folder}).catch(report);
$('cancel').onclick=()=>native('cancel_task',{task_id:taskId}).catch(report);
async function init(){
  const stored=await chrome.storage.local.get('lastTask');
  try {
    cfg=await native('get_settings');
    $('root').textContent=cfg.root || '尚未设置保存根目录，请打开设置';
    for(const key of ['save_images','save_magnet','auto_bitcomet']) $(key).checked=cfg[key];
  }catch(e){report(e);$('root').textContent='本地程序未连接，请安装辅助程序';}
  try{
    const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
    if(!tab?.id || !/^https?:/.test(tab.url || '')) throw Error('请在普通 HTTP(S) 论坛帖子中使用本扩展');
    await chrome.scripting.executeScript({target:{tabId:tab.id},files:['adapters/forum.js']});
    const [{result}]=await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>{try{return {page:globalThis.MediaCollectorAdapter.extract()};}catch(e){return {error:e.message};}}});
    if(result.error) throw Error(result.error);
    page=result.page;
    $('support').textContent='结构已识别';$('title').textContent=page.title;$('url').textContent=page.url;$('adapter').textContent=page.adapter;
    for (const [index,image] of page.images.entries()){
      const label=index===0?'封面原图':'预览原图';
      const tile=document.createElement('div');tile.className='preview-tile';
      if(image.preview && /^data:image\/png;base64,/.test(image.preview)){
        const img=document.createElement('img');img.src=image.preview;img.alt=label;tile.append(img);
      }else{const hint=document.createElement('div');hint.className='preview-placeholder';hint.textContent='原图已定位';hint.title='网页限制缩略图显示，原图下载结果请查看操作状态';tile.append(hint);}
      const caption=document.createElement('span');caption.className='preview-caption';caption.textContent=label;tile.append(caption);$('previews').append(tile);
      const p=document.createElement('p');p.className='muted';p.textContent=label+' · '+image.source+'：'+image.url;$('imageSources').append(p);
    }
    $('counts').textContent=`预览图片 ${page.images.length} 张 · 磁力链接 ${page.magnets.length} 条`;
    $('warnings').textContent=page.warnings.join('；');$('confirmWrap').hidden=!page.warnings.length;
    const placeholder=new Option(page.magnets.length>1?'请选择一条磁力链接':'未选择磁力链接','');$('magnets').add(placeholder);
    page.magnets.forEach((m,i)=>$('magnets').add(new Option(`${i+1}. ${m}`,m)));
    if(page.magnets.length===1) $('magnets').value=page.magnets[0];
    $('collect').disabled=!cfg || !cfg.root;$('repair').disabled=!cfg || !cfg.root;
    if(cfg){
      const {history}=await native('get_status');
      // Compare canonical source URL from persistent tasks, not a title guess.
      for(const old of history){
        if(old.url.split('#')[0]===page.url.split('#')[0]){
          $('duplicate').textContent='该影片此前已经采集过。可检查缺失文件、重新采集或打开原目录。';
          folder=old.folder; $('open').disabled=!folder; $('copyFolder').disabled=!folder; break;
        }
      }
    }
    if(!stored.lastTask || page) $('status').textContent='标题识别成功。请检查图片地址和磁力链接后开始采集。';
  }catch(e){$('support').textContent='暂不支持';$('title').textContent='未识别帖子';report(e);}
  if(stored.lastTask){const old=await native('get_task_status',{task_id:stored.lastTask});if(!page || old.data.url.split('#')[0]===page.url.split('#')[0])watch(stored.lastTask);}
}
init().catch(report);
