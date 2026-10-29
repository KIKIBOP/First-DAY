"""Persistence and registration behavior across fresh, real Python processes."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'native-host'))
from protocol import read_message, write_message


class SettingsPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.host = Path(__file__).resolve().parents[1] / 'native-host'
        self.env = os.environ | {'MEDIA_COLLECTOR_STATE': str(self.state), 'PYTHONIOENCODING': 'utf-8'}

    def request(self, kind, data=None):
        packet = io.BytesIO()
        write_message(packet, {'type': kind, 'data': data or {}})
        result = subprocess.run([sys.executable, str(self.host / 'main.py')], input=packet.getvalue(),
                                capture_output=True, env=self.env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return read_message(io.BytesIO(result.stdout))

    def configure(self, *args):
        # The supplied Windows runtime has ../native-host in python313._pth.
        # Standard development Python resolves the script directory normally.
        return subprocess.run([sys.executable, str(self.host / 'portable_configure.py'), *args],
                              capture_output=True, text=True, encoding='utf-8', env=self.env, timeout=10)

    def save(self, **changes):
        reply = self.request('update_settings', {'root': str(self.root / '中文目录'),
                             'save_images': False, 'save_magnet': False, 'skip_existing': False,
                             'auto_bitcomet': False, 'retries': 4} | changes)
        self.assertTrue(reply['ok'], reply)
        return reply['data']

    def test_fresh_native_process_restores_all_saved_settings(self):
        saved = self.save()
        self.assertEqual(self.request('get_settings')['data'], saved)
        self.assertEqual(json.loads((self.state / 'settings.json').read_text()), saved)

    def test_existing_root_check_preserves_every_setting(self):
        self.save()
        before = (self.state / 'settings.json').read_bytes()
        result = self.configure('--check-existing')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('沿用已保存', result.stdout)
        self.assertEqual((self.state / 'settings.json').read_bytes(), before)

    def test_first_registration_requests_root_without_creating_settings(self):
        result = self.configure('--check-existing')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse((self.state / 'settings.json').exists())

    def test_unavailable_root_fails_without_erasing_settings(self):
        saved = self.save()
        Path(saved['root']).rmdir()
        before = (self.state / 'settings.json').read_bytes()
        result = self.configure('--check-existing')
        self.assertEqual(result.returncode, 1)
        self.assertIn('原设置已保留', result.stderr)
        self.assertEqual((self.state / 'settings.json').read_bytes(), before)

    def test_selecting_new_root_keeps_existing_options(self):
        saved = self.save()
        changed = self.configure(str(self.root / '新目录'))
        self.assertEqual(changed.returncode, 0, changed.stderr)
        current = self.request('get_settings')['data']
        self.assertEqual(current, saved | {'root': str((self.root / '新目录').resolve())})

    def test_rejected_update_does_not_overwrite_saved_settings(self):
        saved = self.save()
        self.assertFalse(self.request('update_settings', {'retries': 99})['ok'])
        self.assertEqual(self.request('get_settings')['data'], saved)
