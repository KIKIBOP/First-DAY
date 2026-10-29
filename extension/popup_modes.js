export const POPUP_MODES=Object.freeze({standard:'popup.html',narrow:'popup-narrow.html'});

export async function readPopupMode() {
  const {popupMode}=await chrome.storage.local.get('popupMode');
  return popupMode==='narrow'?'narrow':'standard';
}

export async function restorePopupMode() {
  const mode=await readPopupMode();
  await chrome.action.setPopup({popup:POPUP_MODES[mode]});
  return mode;
}

export async function savePopupMode(mode) {
  if(mode!=='standard'&&mode!=='narrow') throw Error('请选择标准或窄版菜单');
  const previous=await readPopupMode();
  await chrome.action.setPopup({popup:POPUP_MODES[mode]});
  try { await chrome.storage.local.set({popupMode:mode}); }
  catch(e) {
    try { await chrome.action.setPopup({popup:POPUP_MODES[previous]}); } catch {}
    throw e;
  }
}
