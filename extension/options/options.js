import {native,$,report} from '../common.js';
const bools={auto_bitcomet:'自动调用 BitComet',save_images:'自动保存图片',save_magnet:'保存磁力链接文本',skip_existing:'跳过完整的已有图片',open_after:'采集后打开目录'};
for(const [key,label] of Object.entries(bools)){
  const el=document.createElement('label'),input=document.createElement('input'); input.type='checkbox';input.id=key;el.append(input,document.createTextNode(label));$('checks').append(el);
}
$('save').onclick=async()=>{try{
  const cfg={root:$('root').value.trim(),bitcomet_path:$('bitcomet_path').value.trim(),retries:Number($('retries').value),log_level:$('log_level').value};
  for(const k of Object.keys(bools))cfg[k]=$(k).checked;
  await native('update_settings',cfg);$('status').textContent='设置已保存';
}catch(e){report(e);}};
$('detect').onclick=async()=>{try{$('status').textContent=JSON.stringify(await native('check_bitcomet'),null,2);}catch(e){report(e);}};
(async()=>{try{
  const cfg=await native('get_settings');$('connection').textContent='本地辅助程序已连接 · 扩展 ID：'+chrome.runtime.id;
  for(const [key,value] of Object.entries(cfg)){if(!$(key))continue;if(typeof value==='boolean')$(key).checked=value;else $(key).value=value;}
  const {history}=await native('get_status');
  for(const task of history){const p=document.createElement('p');p.textContent=task.title+' · '+task.state;
    if(task.folder){const b=document.createElement('button');b.textContent='打开目录';b.onclick=()=>native('open_folder',{folder:task.folder}).catch(report);p.append(b);}
    $('history').append(p);
  }
}catch(e){$('connection').textContent='未连接 · 扩展 ID：'+chrome.runtime.id;report(e);}})();
