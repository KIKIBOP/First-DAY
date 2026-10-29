const HOST='com.chrome_media_collector.host';

// A connected Native port keeps the MV3 worker alive while original images transfer.
export class NativeConnection {
  constructor() {
    this.port=chrome.runtime.connectNative(HOST);
    this.tail=Promise.resolve(); this.closed=false; this.pending=null;
    this.port.onMessage.addListener(result=>{
      const pending=this.pending;
      if(!pending) return;
      this.pending=null; clearTimeout(pending.timer);
      if(result?.ok) pending.resolve(result.data);
      else pending.reject(Error(result?.error || '本地程序未响应'));
    });
    this.port.onDisconnect.addListener(()=>this.close(chrome.runtime.lastError?.message || '本地图片传输连接已断开'));
  }
  request(type,data={}) {
    const result=this.tail.catch(()=>{}).then(()=>new Promise((resolve,reject)=>{
      if(this.closed) return reject(Error('本地图片传输连接已断开'));
      const timer=setTimeout(()=>this.close('本地图片传输响应超时'),45000);
      this.pending={resolve,reject,timer};
      try { this.port.postMessage({type,data}); }
      catch(e) { this.close(e.message); }
    }));
    this.tail=result;
    return result;
  }
  close(reason='本地图片传输连接已关闭') {
    if(this.closed) return;
    this.closed=true;
    if(this.pending) {
      clearTimeout(this.pending.timer); this.pending.reject(Error(reason)); this.pending=null;
    }
    try { this.port.disconnect(); } catch {}
  }
}
