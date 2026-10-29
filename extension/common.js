export async function native(type,data={}) {
  const response=await chrome.runtime.sendMessage({route:'native',type,data});
  if(!response?.ok) throw Error(response?.error || '扩展后台未返回响应，请在 chrome://extensions 中重新加载插件后重试');
  return response.data;
}
export const $=id=>document.getElementById(id);
export function report(e){ $('status').textContent=e.message || String(e); }
