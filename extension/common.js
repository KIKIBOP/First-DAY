export async function native(type,data={}) {
  const response=await chrome.runtime.sendMessage({route:'native',type,data});
  if(!response?.ok) throw Error(response?.error || '本地程序未响应');
  return response.data;
}
export const $=id=>document.getElementById(id);
export function report(e){ $('status').textContent=e.message || String(e); }
