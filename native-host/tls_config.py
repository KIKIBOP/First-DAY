"""Verified HTTPS using platform trust plus the bundled Mozilla public CA set."""
from pathlib import Path
import ssl

CA_BUNDLE = Path(__file__).resolve().parent / 'certs' / 'cacert.pem'


class ImageCertificateError(ValueError):
    """A failed certificate must never be retried with verification disabled."""


def create_context(cafile=None):
    path = Path(cafile) if cafile is not None else CA_BUNDLE
    if not path.is_file():
        raise FileNotFoundError('缺少 HTTPS 根证书资源，请完整更新本地程序')
    context = ssl.create_default_context()
    # Retain Windows/system roots (including administratively trusted roots).
    # Supplement, rather than replace, the default store with public Mozilla CAs.
    context.load_verify_locations(cafile=str(path))
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise RuntimeError('HTTPS 证书或主机名校验配置无效')
    return context


def trust_status():
    context = create_context()
    return {'certificate_verification': True, 'hostname_verification': True,
            'trusted_ca_count': context.cert_store_stats()['x509_ca'],
            'bundled_public_ca': True}


def certificate_error(error):
    reason = getattr(error, 'verify_message', '') or '无法验证证书签发链'
    code = getattr(error, 'verify_code', None)
    return ImageCertificateError(
        f'HTTPS 证书验证失败：{reason}（代码 {code}）。'
        '已加载系统及内置公共根证书；请检查 Chrome 能否正常打开原图。'
        '若仍失败，需检查服务器证书链或代理/安全软件的证书配置；证书校验保持开启。')
