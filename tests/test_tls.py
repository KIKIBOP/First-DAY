"""Offline certificate-chain handshakes; generated test private keys stay in temp."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'native-host'))
from tls_config import CA_BUNDLE, ImageCertificateError, create_context, trust_status
from image_downloader import fetch
from collector import run
from config_manager import update_settings
from task_manager import start, task_status


def handshake(client_context, server_context, hostname='images.example.com'):
    client_in, client_out, server_in, server_out = (ssl.MemoryBIO() for _ in range(4))
    client = client_context.wrap_bio(client_in, client_out, server_hostname=hostname)
    server = server_context.wrap_bio(server_in, server_out, server_side=True)
    client_done = server_done = False
    for _ in range(100):
        try:
            client.do_handshake()
            client_done = True
        except ssl.SSLWantReadError:
            pass
        payload = client_out.read()
        if payload:
            server_in.write(payload)
        try:
            server.do_handshake()
            server_done = True
        except ssl.SSLWantReadError:
            pass
        payload = server_out.read()
        if payload:
            client_in.write(payload)
        if client_done and server_done:
            return client.version()
    raise AssertionError('In-memory TLS handshake did not complete')


class TLSConfigurationTests(unittest.TestCase):
    def test_default_store_remains_verified_and_has_public_roots(self):
        context = create_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreater(context.cert_store_stats()['x509_ca'], 0)
        self.assertTrue(trust_status()['bundled_public_ca'])

    def test_bundle_matches_recorded_provenance(self):
        provenance = json.loads((CA_BUNDLE.parent / 'provenance.json').read_text())
        self.assertEqual(hashlib.sha256(CA_BUNDLE.read_bytes()).hexdigest(), provenance['sha256'])
        self.assertNotIn(b'PRIVATE KEY', CA_BUNDLE.read_bytes())

    def test_missing_or_invalid_bundle_fails_without_disabling_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'ca.pem'
            with self.assertRaises(FileNotFoundError):
                create_context(path)
            path.write_text('not a certificate')
            with self.assertRaises(ssl.SSLError):
                create_context(path)

    def test_download_explains_certificate_failure_and_closes_socket(self):
        error = ssl.SSLCertVerificationError(1, 'certificate verify failed')
        error.verify_code = 20
        error.verify_message = 'unable to get local issuer certificate'
        context = Mock()
        context.wrap_socket.side_effect = error
        sock, connection = Mock(), Mock()
        with patch('image_downloader.public_addresses', return_value=[(2, ('8.8.8.8', 443))]), \
             patch('image_downloader.socket.socket', return_value=sock), \
             patch('image_downloader.http.client.HTTPConnection', return_value=connection), \
             patch('image_downloader.create_context', return_value=context):
            with self.assertRaisesRegex(ImageCertificateError, 'issuer certificate'):
                fetch('https://images.example.com/cover.jpg', 'https://forum.example.com/thread')
        context.wrap_socket.assert_called_once_with(sock, server_hostname='images.example.com')
        sock.close.assert_called_once()
        connection.close.assert_called_once()
        connection.request.assert_not_called()

    def test_certificate_failure_is_not_retried_with_weaker_settings(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'MEDIA_COLLECTOR_STATE': temporary + '/state'}):
            update_settings({'root': temporary + '/movies', 'auto_bitcomet': False, 'retries': 5})
            data = {'title': 'TLS 测试影片', 'url': 'https://forum.example.com/thread',
                    'images': [{'url': 'https://images.example.com/a.jpg'}, {'url': 'https://images.example.com/b.jpg'}],
                    'magnets': [], 'options': {}}
            with patch('task_manager._spawn'):
                task_id = start(data)['task_id']
            with patch('collector.fetch', side_effect=ImageCertificateError('证书链无法验证')) as download:
                run(task_id)
            self.assertEqual(download.call_count, 2)
            self.assertEqual(task_status(task_id)['state'], 'partial')
            self.assertEqual(len(task_status(task_id)['errors']), 2)


@unittest.skipUnless(shutil.which('openssl'), 'OpenSSL CLI required only for generating temporary TLS test certificates')
class TLSHandshakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.folder = Path(cls.tmp.name)
        cls.ca = cls.folder / 'ca.pem'

        def command(*args):
            subprocess.run(['openssl', *args], cwd=cls.folder, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)

        command('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key', '-out', 'ca.pem',
                '-days', '2', '-subj', '/CN=MediaCollector Isolated Test CA',
                '-addext', 'basicConstraints=critical,CA:TRUE',
                '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-addext', 'subjectKeyIdentifier=hash')
        command('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'server.key',
                '-out', 'server.csr', '-subj', '/CN=images.example.com')
        (cls.folder / 'extensions.txt').write_text(
            'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n'
            'extendedKeyUsage=serverAuth\nsubjectAltName=DNS:images.example.com\n'
            'subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n')
        command('x509', '-req', '-in', 'server.csr', '-CA', 'ca.pem', '-CAkey', 'ca.key',
                '-CAcreateserial', '-out', 'server.pem', '-days', '1', '-extfile', 'extensions.txt')
        help_result=subprocess.run(['openssl','x509','-help'],capture_output=True,text=True)
        cls.supports_dates='-not_after' in help_result.stderr+help_result.stdout
        if cls.supports_dates:
            command('x509', '-req', '-in', 'server.csr', '-CA', 'ca.pem', '-CAkey', 'ca.key',
                    '-CAcreateserial', '-out', 'expired.pem', '-not_before', '20200101000000Z',
                    '-not_after', '20200102000000Z', '-extfile', 'extensions.txt')

    def server(self, filename='server.pem'):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.folder / filename, self.folder / 'server.key')
        return context

    def test_unknown_issuer_reproduces_reported_certificate_error(self):
        with self.assertRaises(ssl.SSLCertVerificationError) as caught:
            handshake(ssl.create_default_context(), self.server())
        self.assertIn('CERTIFICATE_VERIFY_FAILED', str(caught.exception))
        self.assertEqual(caught.exception.verify_code, 20)

    def test_adding_the_correct_ca_completes_a_verified_handshake(self):
        self.assertTrue(handshake(create_context(self.ca), self.server()).startswith('TLS'))

    def test_trusted_ca_does_not_allow_wrong_hostname(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            handshake(create_context(self.ca), self.server(), hostname='wrong.example.com')

    def test_trusted_ca_does_not_allow_expired_certificate(self):
        if not self.supports_dates: self.skipTest('OpenSSL CLI lacks explicit validity-date options')
        with self.assertRaises(ssl.SSLCertVerificationError):
            handshake(create_context(self.ca), self.server('expired.pem'))
