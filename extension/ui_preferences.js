export const DEFAULT_LAYOUT=Object.freeze({width:640,height:560});
const ranges={width:[480,780],height:[420,600]};

export async function readLayout() {
  const {popupLayout}=await chrome.storage.local.get('popupLayout');
  const layout={...DEFAULT_LAYOUT};
  for(const [key,[min,max]] of Object.entries(ranges)) {
    const value=popupLayout?.[key];
    if(Number.isInteger(value)&&value>=min&&value<=max) layout[key]=value;
  }
  return layout;
}

export async function saveLayout(layout) {
  for(const [key,[min,max]] of Object.entries(ranges)) {
    if(!Number.isInteger(layout[key])||layout[key]<min||layout[key]>max)
      throw Error(`${key==='width'?'宽度':'高度'}应为 ${min}–${max} 之间的整数`);
  }
  await chrome.storage.local.set({popupLayout:{width:layout.width,height:layout.height}});
}

export function applyLayout(layout) {
  document.documentElement.style.setProperty('--popup-width',layout.width+'px');
  document.documentElement.style.setProperty('--popup-height',layout.height+'px');
}
