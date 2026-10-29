import {native,$,report} from '../common.js';

const bools={auto_bitcomet:'自动调用 BitComet',save_images:'自动保存图片',save_magnet:'保存磁力链接文本',skip_existing:'跳过完整的已有图片',open_after:'采集后打开目录'};
for(const [key,label] of Object.entries(bools)) {
  const el=document.createElement('label'),input=document.createElement('input');
  input.type='checkbox';input.id=key;el.append(input,document.createTextNode(label));$('checks').append(el);
}

function fill(cfg) {
  for(const [key,value] of Object.entries(cfg)) {
    if(!$(key)) continue;
    if(typeof value==='boolean') $(key).checked=value;
    else $(key).value=value;
  }
}

$('save').onclick=async()=>{
  try {
    const cfg={root:$('root').value.trim(),bitcomet_path:$('bitcomet_path').value.trim(),retries:Number($('retries').value),log_level:$('log_level').value};
    for(const k of Object.keys(bools)) cfg[k]=$(k).checked;
    fill(await native('update_settings',cfg));
    $('status').textContent='设置已保存，重新打开会自动读取。';
  } catch(e) { report(e); }
};

$('detect').onclick=async()=>{
  try {
    const result=await native('check_bitcomet');
    if(result.associated) {
      $('status').textContent='已确认磁力链接关联 BitComet。'+(result.protocol_executable?'\n程序：'+result.protocol_executable:'');
    } else if(result.platform!=='nt') {
      $('status').textContent=result.note || 'BitComet 检测需要 Windows。';
    } else {
      const paths=result.candidates || [];
      $('status').textContent=(paths.length?'检测到 BitComet 安装路径：\n'+paths.join('\n')+'\n':'尚未检测到有效的 BitComet 磁力关联。\n')+
        '请在 Windows 默认应用中将磁力链接关联到 BitComet，然后重新检测。更改安装路径后请先保存设置。';
    }
  } catch(e) { report(e); }
};

async function connect() {
  $('settingsFields').disabled=true;$('reconnect').hidden=true;
  $('connection').textContent='正在读取已保存设置…';
  $('settingsHint').textContent='正在连接本地辅助程序。';
  try {
    fill(await native('get_settings'));
  } catch(e) {
    $('connection').textContent='未连接 · 扩展 ID：'+chrome.runtime.id;
    $('settingsHint').textContent='尚未读到本机设置，不代表设置已丢失。请先运行原便携包中的“运行自检.bat”；移动过程序目录时需重新注册。';
    $('reconnect').hidden=false;report(e);return;
  }
  $('connection').textContent='本地辅助程序已连接 · 扩展 ID：'+chrome.runtime.id;
  $('settingsHint').textContent='已读取本机设置，关闭窗口后会保留。日常使用直接打开插件，无需重复运行注册脚本。';
  $('settingsFields').disabled=false;$('status').textContent='已读取已保存设置。';
  $('history').replaceChildren();
  // A history/status failure must not turn a successful settings read into "disconnected".
  try {
    const {history}=await native('get_status');
    for(const task of history) {
      const p=document.createElement('p');p.textContent=task.title+' · '+task.state;
      if(task.folder) {
        const b=document.createElement('button');b.textContent='打开目录';
        b.onclick=()=>native('open_folder',{folder:task.folder}).catch(report);p.append(b);
      }
      $('history').append(p);
    }
  } catch(e) { $('status').textContent='设置已读取，采集历史暂不可用：'+e.message; }
}
$('reconnect').onclick=connect;
connect();
