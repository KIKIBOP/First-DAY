# HTTPS 公共 CA 列表

`cacert.pem` 来自用户提供的便携包中 pip 26.2.2 随附的 certifi 2026.10.19；复制前核对了原包 `SHA256SUMS.txt`。原始路径和固定 SHA-256 见 `provenance.json`，许可证见 `CERTIFI-LICENSE.txt`。

这是 Mozilla 公共 CA 列表，不含私钥，也不包含用户会话或为某个图片站点临时添加的证书。应用在系统默认信任库之外显式加载此资源，同时保持证书链、有效期与主机名校验。

更新时从 certifi 官方发布获取，更新来源、版本和 SHA-256 并重新执行 TLS 回归与打包验证。不要根据未知网页或报错内容直接添加站点叶证书或不明根证书。

PyInstaller 构建必须包含 `certs` 数据目录；便携包直接随 `native-host` 一起复制。自检只验证信任库能加载，不代表已与目标站点成功建立 TLS。

参考：[Python ssl](https://docs.python.org/3.13/library/ssl.html)、[certifi](https://pypi.org/project/certifi/2026.10.19/)。
