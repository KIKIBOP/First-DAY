import base64
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'native-host'))
from PIL import Image
from browser_images import transfer, read_image, transfer_dir
from collector import run
from config_manager import atomic_json, update_settings, load_json
from folder_manager import movie_folder
from image_downloader import image_extension
from protocol import write_message, read_message
from task_manager import start, finish_preparation, cancel, task_status


def png():
    output = io.BytesIO()
    Image.new('RGB', (5, 3), 'green').save(output, format='PNG')
    return output.getvalue()


class FixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {'MEDIA_COLLECTOR_STATE': self.tmp.name + '/state'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.root = Path(self.tmp.name) / 'movies'
        update_settings({'root': str(self.root), 'auto_bitcomet': False, 'save_magnet': False})

    def data(self):
        return {'title': '测试影片 ABC-123', 'url': 'https://forum.example/thread-1.html',
                'images': [{'url': 'https://cdn.example/cover.jpg'}, {'url': 'https://cdn.example/preview.jpg'}],
                'magnets': [], 'options': {}}

    def prepare(self):
        return start(self.data(), prepare=True)['task_id']

    def upload(self, task_id, slot, payload=None, mime='application/octet-stream'):
        payload = png() if payload is None else payload
        transfer({'task_id': task_id, 'slot': slot, 'action': 'begin', 'mime': mime})
        for offset in range(0, len(payload), 7):
            transfer({'task_id': task_id, 'slot': slot, 'action': 'chunk', 'offset': offset,
                      'content': base64.b64encode(payload[offset:offset + 7]).decode()})
        return transfer({'task_id': task_id, 'slot': slot, 'action': 'finish'})

    def test_title_only_and_numbered_collisions(self):
        a = movie_folder(self.root, '完整标题', 'post-a')
        b = movie_folder(self.root, '完整标题', 'post-b')
        self.assertEqual(a.name, '完整标题')
        self.assertEqual(b.name, '完整标题 (2)')
        self.assertEqual(movie_folder(self.root, '完整标题', 'post-a'), a)
        self.assertEqual(movie_folder(self.root, '完整标题', 'post-b'), b)

    def test_unrelated_user_directory_is_preserved(self):
        original = self.root / 'Title'
        original.mkdir(parents=True)
        video = original / 'video.mp4'
        video.write_bytes(b'user video')
        allocated = movie_folder(self.root, 'title', 'post-a')
        self.assertEqual(allocated.name, 'title (2)')
        self.assertEqual(video.read_bytes(), b'user video')

    def test_legacy_destination_is_reused_without_renaming(self):
        identity = self.data()['url']
        legacy = self.root / ('完整标题 [' + hashlib.sha256(identity.encode()).hexdigest()[:10] + ']')
        legacy.mkdir(parents=True)
        atomic_json(legacy / 'metadata.json', {'source_url': identity})
        self.assertEqual(movie_folder(self.root, '完整标题', identity), legacy)
        self.assertFalse((self.root / '完整标题').exists())

    def test_generic_mime_preserves_original_bytes(self):
        for mime in ('application/octet-stream', 'binary/octet-stream', '', 'image/png; charset=binary'):
            self.assertEqual(image_extension(png(), mime), '.png')
        for data, mime in [(b'<html>login</html>', 'application/octet-stream'), (png(), 'text/html')]:
            with self.assertRaises(Exception):
                image_extension(data, mime)

    def test_browser_originals_save_even_when_native_network_would_fail(self):
        task_id = self.prepare()
        for slot in range(2):
            self.upload(task_id, slot)
        with patch('task_manager._spawn'):
            finish_preparation({'task_id': task_id})
        with patch('collector.fetch', side_effect=AssertionError('must use browser original')):
            run(task_id)
        task = task_status(task_id)
        self.assertEqual(task['state'], 'completed')
        folder = Path(task['folder'])
        self.assertEqual(folder.name, self.data()['title'])
        self.assertEqual((folder / '封面原图.png').read_bytes(), png())
        self.assertEqual((folder / '预览原图.png').read_bytes(), png())
        self.assertFalse((folder / '磁力链接.txt').exists())
        self.assertFalse((Path(self.tmp.name) / 'state/browser-images' / task_id).exists())

    def test_failed_browser_download_falls_back_and_records_reason(self):
        task_id = self.prepare()
        self.upload(task_id, 0)
        with patch('task_manager._spawn'):
            finish_preparation({'task_id': task_id, 'errors': ['预览原图浏览器获取失败：HTTP 403']})
        with patch('collector.fetch', return_value=(png(), '.png')) as fetch:
            run(task_id)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(task_status(task_id)['state'], 'completed')
        self.assertTrue(any('HTTP 403' in line for line in task_status(task_id)['events']))

    def test_complete_existing_images_are_not_downloaded_again(self):
        task_id=self.prepare()
        for slot in range(2): self.upload(task_id,slot)
        with patch('task_manager._spawn'): finish_preparation({'task_id':task_id})
        run(task_id)
        next_task=start(self.data(),prepare=True)
        self.assertEqual(next_task['image_slots'],[])
        folder=Path(task_status(task_id)['folder'])
        (folder/'预览原图.png').unlink()
        self.assertEqual(start(self.data(),prepare=True)['image_slots'],[1])

    def test_interrupted_preparation_is_marked_failed(self):
        from task_manager import fail_preparation
        task_id=self.prepare()
        self.upload(task_id,0)
        fail_preparation({'task_id':task_id})
        self.assertEqual(task_status(task_id)['state'],'failed')
        self.assertFalse((Path(self.tmp.name)/'state/browser-images'/task_id).exists())

    def test_lost_finish_response_does_not_remove_active_worker_images(self):
        from task_manager import fail_preparation
        task_id=self.prepare()
        self.upload(task_id,0)
        with patch('task_manager._spawn'): finish_preparation({'task_id':task_id})
        fail_preparation({'task_id':task_id})
        self.assertEqual(read_image(task_id,0,self.data()['images'][0]['url'])[0],png())

    def test_out_of_order_or_invalid_chunk_is_rejected(self):
        task_id = self.prepare()
        transfer({'task_id': task_id, 'slot': 0, 'action': 'begin', 'mime': 'image/png'})
        for offset, content in [(3, 'YWJj'), (0, '!!!')]:
            with self.assertRaises(ValueError):
                transfer({'task_id': task_id, 'slot': 0, 'action': 'chunk', 'offset': offset, 'content': content})
        self.assertEqual((transfer_dir(task_id) / '0.part').stat().st_size, 0)

    def test_html_is_not_published_as_an_image(self):
        task_id = self.prepare()
        with self.assertRaises(Exception):
            self.upload(task_id, 0, b'<html>Please log in</html>')
        self.assertFalse((transfer_dir(task_id) / '0.ready').exists())

    def test_size_limit_and_task_boundaries(self):
        task_id = self.prepare()
        transfer({'task_id': task_id, 'slot': 0, 'action': 'begin', 'mime': 'image/png'})
        with patch('browser_images.MAX_BYTES', 2):
            with self.assertRaisesRegex(ValueError, '超过'):
                transfer({'task_id': task_id, 'slot': 0, 'action': 'chunk', 'offset': 0, 'content': 'YWJj'})
        for slot in [-1, 2, True, '../x']:
            with self.assertRaises(ValueError):
                transfer({'task_id': task_id, 'slot': slot, 'action': 'begin'})

    def test_url_or_byte_tampering_is_rejected(self):
        task_id = self.prepare()
        self.upload(task_id, 0)
        with self.assertRaises(ValueError):
            read_image(task_id, 0, 'https://other.example/image')
        (transfer_dir(task_id) / '0.ready').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            read_image(task_id, 0, self.data()['images'][0]['url'])

    def test_cancel_preparation_prevents_worker_and_cleans_cache(self):
        task_id = self.prepare()
        self.upload(task_id, 0)
        cancel(task_id)
        with patch('task_manager._spawn') as spawn:
            with self.assertRaises(InterruptedError):
                finish_preparation({'task_id': task_id})
            spawn.assert_not_called()
        self.assertEqual(task_status(task_id)['state'], 'cancelled')
        self.assertFalse((Path(self.tmp.name) / 'state/browser-images' / task_id).exists())

    def test_real_native_protocol_accepts_chunks_then_worker_saves_images(self):
        task_id = self.prepare()
        packet = io.BytesIO()
        count = 0
        for slot in range(2):
            requests = [dict(type='image_transfer', data=dict(task_id=task_id, slot=slot, action='begin', mime='application/octet-stream')),
                        dict(type='image_transfer', data=dict(task_id=task_id, slot=slot, action='chunk', offset=0, content=base64.b64encode(png()).decode())),
                        dict(type='image_transfer', data=dict(task_id=task_id, slot=slot, action='finish'))]
            for request in requests:
                write_message(packet, request)
                count += 1
        write_message(packet, {'type': 'finish_preparation', 'data': {'task_id': task_id}})
        host = Path(__file__).resolve().parents[1] / 'native-host/main.py'
        process = subprocess.run([sys.executable, str(host)], input=packet.getvalue(), capture_output=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        responses = io.BytesIO(process.stdout)
        for _ in range(count + 1):
            response = read_message(responses)
            self.assertTrue(response and response.get('ok'), response)
        self.assertIsNone(read_message(responses))
        for _ in range(100):
            task = task_status(task_id)
            if task['state'] in ('completed', 'partial', 'failed'):
                break
            time.sleep(.05)
        self.assertEqual(task['state'], 'completed', task)
        self.assertEqual((Path(task['folder']) / '预览原图.png').read_bytes(), png())
