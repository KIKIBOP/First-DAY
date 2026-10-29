import io, json, os, sys, tempfile, unittest, hashlib, subprocess, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'native-host'))
from protocol import read_message, write_message
from folder_manager import safe_name, contained, movie_folder
from validation import magnet, collection, magnet_keys
from image_downloader import image_extension, public_addresses, fetch
from config_manager import atomic_json, settings, update_settings, state_dir, load_json
from task_manager import task_path, task_status, start, cancel
from collector import run
from bitcomet import check_bitcomet
from PIL import Image
M='magnet:?xt=urn:btih:'+'a'*40+'&dn=test'

def png():
    b=io.BytesIO();Image.new('RGB',(3,3),'blue').save(b,format='PNG');return b.getvalue()

class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.env=patch.dict(os.environ,{'MEDIA_COLLECTOR_STATE':self.tmp.name+'/state'})
        self.env.start();self.addCleanup(self.env.stop)
        self.root=Path(self.tmp.name)/'影片收藏'
        update_settings({'root':str(self.root),'auto_bitcomet':False})
    def data(self): return dict(title='[高清] 中文日本語 ABC-123',url='https://example.com/thread-1.html',images=[{'url':'https://cdn.example.com/a'},{'url':'https://cdn.example.com/b'}],magnets=[M],options={})
    def queued(self):
        tid='a'*32;atomic_json(task_path(tid),dict(id=tid,state='queued',heartbeat=time.time(),data=self.data(),events=[],folder=''));return tid
    def test_native_roundtrip_unicode(self):
        b=io.BytesIO();write_message(b,{'标题':'中文'});b.seek(0);self.assertEqual(read_message(b),{'标题':'中文'})
    def test_native_size_and_truncation(self):
        for payload in (b'\xff'*4,b'\x04\0\0\0{}'):
            with self.assertRaises((ValueError,EOFError)):read_message(io.BytesIO(payload))
    def test_invalid_json_type(self):
        with self.assertRaises(ValueError):read_message(io.BytesIO(b'\x02\0\0\0[]'))
    def test_chinese_folder_and_collision(self):
        a=movie_folder(self.root,'中文影片','a');b=movie_folder(self.root,'中文影片','b')
        self.assertIn('中文影片',a.name);self.assertNotEqual(a,b)
        self.assertEqual(a,movie_folder(self.root,'中文影片','a'))
    def test_windows_names(self):
        self.assertEqual(safe_name('CON.txt'),'_CON.txt')
        self.assertNotRegex(safe_name('a<>:"/\\|?*.'),r'[<>:"/\\|?*]')
        self.assertLessEqual(len(safe_name('😀'*200).encode('utf-16-le')),160)
    def test_path_traversal_and_symlink(self):
        with self.assertRaises(ValueError):contained(self.root,self.root/'../outside')
        self.root.mkdir(exist_ok=True);outside=Path(self.tmp.name)/'outside';outside.mkdir();(self.root/'link').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):contained(self.root,self.root/'link'/'image')
    def test_magnets_v1_v2(self):
        self.assertEqual(magnet(M),M)
        magnet('magnet:?xt=urn:btmh:1220'+'1'*64)
        magnet('magnet:?xt=urn:btih:'+'A'*32)
        for x in ('magnet:?xt=bad',M+'\n','file:///x'):
            with self.assertRaises(ValueError):magnet(x)
    def test_magnet_base32_and_hybrid_aliases(self):
        import base64
        infohash=bytes.fromhex('a'*40)
        encoded=base64.b32encode(infohash).decode()
        self.assertEqual(magnet_keys(M),magnet_keys('magnet:?xt=urn:btih:'+encoded))
        hybrid=M+'&xt=urn:btmh:1220'+'1'*64
        self.assertTrue(set(magnet_keys(M)) & set(magnet_keys(hybrid)))
    def test_input_validation(self):
        d=self.data();d['magnets']=[M,M]
        with self.assertRaises(ValueError):collection(d)
        d=self.data();d['images']=[{'url':'file:///etc/passwd'}]
        with self.assertRaises(ValueError):collection(d)
        with self.assertRaises(ValueError):update_settings({'retries':-1})
        with self.assertRaises(ValueError):update_settings({'root':'relative'})
    def test_image_actual_format_and_mime(self):
        self.assertEqual(image_extension(png(),'image/png'),'.png')
        with self.assertRaises(ValueError):image_extension(png(),'image/jpeg')
        with self.assertRaises(Exception):image_extension(b'<html>Error</html>','image/png')
    def test_ssrf(self):
        for ip in ('127.0.0.1','10.1.2.3','169.254.169.254','::1'):
            with patch('socket.getaddrinfo',return_value=[(2,1,6,'',(ip,443))]):
                with self.assertRaises(ValueError):public_addresses('evil.example',443)
    def test_redirect_rechecks_destination(self):
        from unittest.mock import Mock
        response=Mock();response.status=302;response.getheader.return_value='http://127.0.0.1/private'
        conn=Mock();conn.getresponse.return_value=response
        with patch('image_downloader.public_addresses',side_effect=[[(2,('8.8.8.8',80))],ValueError('本地网络')]) as resolve, patch('image_downloader.socket.socket'),patch('image_downloader.http.client.HTTPConnection',return_value=conn):
            with self.assertRaisesRegex(ValueError,'本地网络'):fetch('http://public.example/a','https://forum.example/thread')
            self.assertEqual(resolve.call_count,2)
            self.assertEqual(resolve.call_args.args[0],'127.0.0.1')
    def test_download_size_limit(self):
        from unittest.mock import Mock
        response=Mock();response.status=200;response.getheader.side_effect=lambda key,*args:'100' if key=='Content-Length' else 'image/png'
        conn=Mock();conn.getresponse.return_value=response
        with patch('image_downloader.public_addresses',return_value=[(2,('8.8.8.8',80))]),patch('image_downloader.socket.socket'),patch('image_downloader.http.client.HTTPConnection',return_value=conn),patch('image_downloader.MAX_BYTES',10):
            with self.assertRaisesRegex(ValueError,'超过'):fetch('http://public.example/a','https://forum.example/thread')
    def test_pinned_download_checks_bytes(self):
        from unittest.mock import Mock
        response=Mock();response.status=200;response.getheader.side_effect=lambda key,*args:'image/png' if key=='Content-Type' else None
        response.read.side_effect=[png(),b'']
        conn=Mock();conn.getresponse.return_value=response; sock=Mock()
        with patch('image_downloader.public_addresses',return_value=[(2,('8.8.8.8',80))]),patch('image_downloader.socket.socket',return_value=sock),patch('image_downloader.http.client.HTTPConnection',return_value=conn):
            data,ext=fetch('http://public.example/a','https://forum.example/thread?token=private')
            self.assertEqual(ext,'.png');self.assertEqual(data,png());sock.connect.assert_called_once_with(('8.8.8.8',80))
            self.assertEqual(conn.request.call_args.kwargs['headers']['Referer'],'https://forum.example/')
    def test_download_failure_and_metadata(self):
        tid=self.queued();update_settings({'retries':0})
        with patch('collector.fetch',side_effect=ValueError('HTTP 403')):run(tid)
        task=task_status(tid);self.assertEqual(task['state'],'partial');self.assertEqual(len(task['errors']),2)
        self.assertTrue((Path(task['folder'])/'磁力链接.txt').exists())
    def test_duplicate_collection_preserves_video(self):
        tid=self.queued()
        with patch('collector.fetch',return_value=(png(),'.png')) as fetcher:run(tid)
        task=task_status(tid);folder=Path(task['folder']);(folder/'video.mp4').write_bytes(b'user-video')
        self.assertEqual(fetcher.call_count,2)
        tid=self.queued()
        with patch('collector.fetch',side_effect=AssertionError('must skip')):run(tid)
        self.assertEqual(task_status(tid)['state'],'completed');self.assertEqual((folder/'video.mp4').read_bytes(),b'user-video')
        self.assertEqual((folder/'磁力链接.txt').read_text().count(M),1)
    def test_duplicate_dispatch_once(self):
        tid=self.queued();update_settings({'save_images':False,'auto_bitcomet':True})
        with patch('collector.launch',return_value='sent') as send:
            run(tid);self.queued();run(tid)
            self.assertEqual(send.call_count,1)
    def test_dispatch_global_and_explicit_resubmit(self):
        tid=self.queued();update_settings({'save_images':False,'auto_bitcomet':True})
        with patch('collector.launch',return_value='sent') as send:
            run(tid)
            self.queued();t=load_json(task_path(tid));t['data']['url']='https://example.com/thread-2.html';atomic_json(task_path(tid),t);run(tid)
            self.assertEqual(send.call_count,1)
            self.queued();t=load_json(task_path(tid));t['data']['options']['resubmit']=True;atomic_json(task_path(tid),t);run(tid)
            self.assertEqual(send.call_count,2)
    def test_user_image_never_overwritten(self):
        tid=self.queued();d=self.data();folder=movie_folder(self.root,d['title'],d['url'])
        original=folder/'封面原图.png';original.write_bytes(b'user-image')
        with patch('collector.fetch',return_value=(png(),'.png')):run(tid)
        self.assertEqual(original.read_bytes(),b'user-image')
        self.assertTrue(list(folder.glob('封面原图-*.png')))
    def test_cancel(self):
        tid=self.queued();cancel(tid);run(tid);self.assertEqual(task_status(tid)['state'],'cancelled')
    def test_bitcomet_bad_config(self):
        with self.assertRaises(ValueError):update_settings({'bitcomet_path':str(self.root/'unknown.exe')})
        result=check_bitcomet(settings());self.assertIn('associated',result)
    def test_worker_survives_native_disconnect(self):
        # A real native host process launches the worker, then its stdin closes.
        d=self.data();d['images']=[];d['options']={'save_images':False,'auto_bitcomet':False}
        packet=io.BytesIO();write_message(packet,{'type':'start_collection','data':d})
        host=Path(__file__).resolve().parents[1]/'native-host/main.py'
        completed=subprocess.run([sys.executable,str(host)],input=packet.getvalue(),capture_output=True,timeout=10)
        self.assertEqual(completed.returncode,0,completed.stderr)
        reply=read_message(io.BytesIO(completed.stdout));self.assertTrue(reply['ok']);tid=reply['data']['task_id']
        for _ in range(100):
            task=task_status(tid)
            if task['state'] in ('completed','partial','failed'):break
            time.sleep(.05)
        self.assertEqual(task['state'],'completed',task)
        self.assertTrue((Path(task['folder'])/'metadata.json').exists())
    def test_stale_task(self):
        tid=self.queued();t=load_json(task_path(tid));t['heartbeat']=0;atomic_json(task_path(tid),t)
        self.assertEqual(task_status(tid)['state'],'interrupted')
    def test_protocol_process_multiple_messages(self):
        packet=io.BytesIO();write_message(packet,{'type':'get_settings'});write_message(packet,{'type':'unsupported'})
        host=Path(__file__).resolve().parents[1]/'native-host/main.py'
        p=subprocess.run([sys.executable,str(host)],input=packet.getvalue(),capture_output=True,timeout=5)
        output=io.BytesIO(p.stdout);self.assertTrue(read_message(output)['ok']);self.assertFalse(read_message(output)['ok']);self.assertIsNone(read_message(output))

if __name__=='__main__':unittest.main(verbosity=2)
