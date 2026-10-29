import os, sys, logging
from config_manager import settings, state_dir, update_settings
from protocol import read_message, write_message
import task_manager
from bitcomet import check_bitcomet
from tls_config import trust_status

def dispatch(request):
    kind=request.get('type'); data=request.get('data',{})
    if not isinstance(data,dict): raise ValueError('data 必须为对象')
    if kind=='get_status': return {'connected':True,'version':'0.1.7','history':task_manager.history(),'bitcomet':check_bitcomet(settings()),'https':trust_status()}
    if kind=='get_settings': return settings()
    if kind=='update_settings': return update_settings(data)
    if kind=='start_collection': return task_manager.start(data)
    if kind=='prepare_collection': return task_manager.start(data,prepare=True)
    if kind=='finish_preparation': return task_manager.finish_preparation(data)
    if kind=='fail_preparation': return task_manager.fail_preparation(data)
    if kind=='image_transfer':
        from browser_images import transfer
        return transfer(data)
    if kind=='get_task_status': return task_manager.task_status(data.get('task_id'))
    if kind=='cancel_task': return task_manager.cancel(data.get('task_id'))
    if kind=='check_bitcomet': return check_bitcomet(settings())
    if kind=='open_folder':
        from collector import open_folder
        return open_folder(data.get('folder',''))
    raise ValueError('不支持的消息类型')

def main():
    logging.basicConfig(filename=state_dir()/'collector.log',level=getattr(logging,settings()['log_level']),format='%(asctime)s %(levelname)s %(message)s')
    if len(sys.argv)==3 and sys.argv[1]=='--worker':
        from collector import run
        run(sys.argv[2]); return
    if os.name=='nt':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(),os.O_BINARY); msvcrt.setmode(sys.stdout.fileno(),os.O_BINARY)
    while True:
        try:
            request=read_message(sys.stdin.buffer)
            if request is None: break
            try: response={'ok':True,'data':dispatch(request)}
            except Exception as e: response={'ok':False,'error':str(e)}
            write_message(sys.stdout.buffer,response)
        except (EOFError,ValueError) as e:
            logging.warning('协议错误: %s',e); break

if __name__=='__main__': main()
