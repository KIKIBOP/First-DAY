# 网页影片一键采集助手 v0.1.6

Windows 11 辅助程序与 Chrome Manifest V3 扩展：从当前帖子提取标题、两张原图和磁力链接，保存图片，并按选项请求 BitComet。开发约定见 [AGENTS.md](AGENTS.md)。

本版本以用户上传的 `MediaCollector-Portable-x64.7z` 为基础，保留运行目录中已放宽的预览图后缀规则，并同步到源码。扩展和本地协议版本统一为 `0.1.6`。

## 修复内容

- v0.1.6：根据用户反馈恢复固定 500×580 单栏菜单，撤回尺寸调节；根节点提供明确像素尺寸，避免依赖弹窗初始视口计算。保留精简顶部、折叠来源、底部按钮和快捷键。
- v0.1.5：新增打开菜单的快捷键，并精简顶部文字。
- v0.1.4：修复设置页在标签页中打开时被后台误拦的回归，恢复读取设置、保存及 BitComet 检测。未读到设置时禁用空表单；重连后恢复本机配置。重复注册沿用已有可用的保存目录，日常使用无需重复注册。
- v0.1.3：补充明确加载的公共 CA 资源，增加证书链错误说明和本地信任库自检；不关闭证书及主机名校验。

- 新建目录按清理后的帖子标题命名，不再追加 `[b78f945859]` 一类摘要。不同帖子真正重名时使用 `标题 (2)`、`标题 (3)`，不覆盖已有目录。
- 原图优先通过 Chrome 当前网络和可用会话获取，再分块传给本地程序校验、保存，补上旧版 Python 直接下载不能使用浏览器会话及代理的路径。
- 支持附件服务器返回通用二进制 MIME 或不返回 MIME；仍完整解码图片，拒绝 HTML、截断数据及明确冲突的图片 MIME。
- 已有完整原图按记录和 SHA-256 跳过；只获取缺失或不匹配的图片。浏览器获取失败时记录原因，再尝试原有本地下载器。

用户错误日志已确认两张原图均在 TLS 阶段因 `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate` 失败。v0.1.3 将原包 pip 随附、经校验的 certifi 2026.10.19 公共 CA 列表作为独立应用资源，在系统默认信任库之外加载，保留证书链与主机名校验；自检显示信任库状态。无法仅凭日志判定是缺少根证书、服务器中间证书不全还是代理证书配置。若 Chrome 可正常查看，先使用浏览器取图；若两端都拒绝，需继续检查站点或网络证书配置。实际测试及限制见 [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md)。

## 便携版使用与更新

1. 等待当前采集结束，将完整便携包解压或更新到固定本地目录，保留整个 `runtime` 文件夹。
2. 首次使用或移动过程序目录时，双击 `首次使用-注册.bat`。已有可用保存目录会沿用，仅未配置时才询问目录；日常使用直接打开 Chrome 插件。
3. Chrome 打开 `chrome://extensions`，加载 `extension` 文件夹；已有扩展点击“重新加载”。
4. 扩展设置中确认本地程序已连接，打开帖子并检查标题、两张原图地址和磁力。
5. 首次保存图片时，允许 Chrome 访问**所识别的图片站点**；可在扩展详情中撤销授权。
6. 如启用 BitComet，在其添加任务界面确认保存目录；发送磁力不代表添加成功或下载完成。

本包带 Windows x64 启动器、Python 和 Pillow，普通用户无需安装 Python 或编译。固定扩展 ID 保持原值。本地程序和扩展必须一起更新；旧程序不支持新图片传输消息。

从 GitHub 源码 ZIP 更新现有便携包时：停止采集并备份，将源码中的 `extension/`、`native-host/` 两个目录和根目录 `register.ps1` 覆盖到**原便携包根目录**（与 `runtime/`、`MediaCollectorHost.exe` 同层）。保留原运行环境；运行“运行自检.bat”并在 Chrome 重新加载原扩展。源码 ZIP 不包含运行环境，不能单独作为免安装包运行。

设置页“未连接”不代表磁盘设置被删除。设置、勾选项与历史仍存于 `%LOCALAPPDATA%\ChromeMediaCollector`；先确认本地程序连接后再检测 BitComet。若确实移动了程序或注册指向旧目录，重新注册会保留已有可用设置。检测到安装不等于磁力协议已关联；需要用户在 Windows 默认应用中设置，程序不自动修改关联。

## 弹窗大小和快捷键

菜单采用固定宽 500、高 580 像素的单栏布局，保留去掉顶部宣传文字、缩短间距、折叠来源地址和固定操作区等优化。内容较多时滚动中间区域，底部按钮保持可见。旧版保存的弹窗尺寸不再使用，无需清空 Chrome 存储；影片根目录、勾选项和采集历史保持原有保存方式。真实 Chrome 弹窗显示仍需 Windows 验证。

在 Chrome 当前窗口中，默认按 **Alt+Shift+Y** 打开同一采集菜单，不直接启动采集。若该按键已被占用或升级后未分配，打开“设置 → 设置快捷键”，或直接访问 `chrome://extensions/shortcuts`，为本扩展指定按键。设置页优先显示 Chrome 返回的实际分配结果，不擅自覆盖用户的按键设置；较早的 Chrome 可能无法查询动作快捷键，此时直接在 Chrome 页面确认。

实现依据：[Chrome Commands](https://developer.chrome.com/docs/extensions/reference/api/commands)、[Chrome Action](https://developer.chrome.com/docs/extensions/reference/api/action)。真实快捷键触发尚未在本开发环境验证。

## 保存内容及旧目录

```text
影片保存根目录/
  清理后的帖子标题/
    封面原图.jpg
    预览原图.jpg
    metadata.json
    磁力链接.txt       # 仅开启“保存磁力链接”时写入
```

扩展名取自真实图片格式，保存原始字节，不使用缩略图或重新编码。`metadata.json` 仍用于来源识别、去重和完整性检查；本次未改变 JSON 的保存位置。

**新命名规则只用于新建目录。** 已有带摘要目录在来源记录匹配时继续复用，保持 BitComet 的原保存路径可用。若需整理旧目录，先停止相关下载，保留 `metadata.json` 并在资源管理器改名，再更新 BitComet 中的路径；重新采集后刷新历史任务路径。标题及数字重名目录可重新识别。

用户视频和未知同名文件不会被删除或覆盖。状态、历史、日志和传输暂存位于 `%LOCALAPPDATA%\ChromeMediaCollector`。正常结束或取消后清理暂存；超过一天的异常遗留暂存在下一次准备任务时清理。

## 图片获取与权限

后台浏览器请求使用当前可用 Cookie 和代理，不读取 Cookie 值，也不把 Cookie 传给本地程序。临时 Referer 规则仅匹配本扩展对所选原图路径的请求，使用帖子站点来源，不转发帖子查询参数；请求结束移除规则。

每块最多 192 KiB 原始字节，单条 Native 消息低于 900000 字节；单图最多 25 MiB、最多 6000 万像素，Pillow 完整验证后才发布文件。权限被拒绝、取消、超时及错误页均有处理，图片失败不会显示为已保存。

浏览器路径不自动跟随重定向；此类情况回退到原本逐跳验证的 Native 下载器。图片站点访问条件、Chrome 第三方 Cookie 设置或系统网络限制仍可能导致失败，应保留具体提示进一步适配。浏览器路径只获取主动授权的图片站点，拒绝 IP 字面量、本机域名和非 HTTP(S) URL。

本地回退路径继续验证公开 DNS、标准端口、重定向及 HTTPS 证书/SNI；仍为直接连接，不使用浏览器代理。两种路径的权限和网络条件不同。

实现依据：[Chrome 跨域请求](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests)、[可选站点权限](https://developer.chrome.com/docs/extensions/reference/api/permissions)、[Cookie 行为](https://developer.chrome.com/docs/extensions/develop/concepts/storage-and-cookies)、[请求规则](https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest)。

## 开发与验证

源码要求 Python 3.11+，运行依赖为 Pillow。开发测试另需 Node.js、Playwright 和本机 Chromium。Windows 设置 `CHROMIUM_PATH` 为实际 chrome.exe 路径。

```bat
py -3 -m pip install -r requirements.txt
py -3 -m unittest discover -s tests -p "test_*.py" -v
npm install
npm test
```

浏览器测试拦截页面网络，Chrome 权限、Native 及规则 API 使用模拟；不能代替 Windows 11 的真实 Chrome/BitComet 联动测试。Windows 手工检测可运行 `py -3 tests\windows_integration.py`，默认不提交磁力。

## Windows 构建与源码恢复

在 Windows 11 从源码构建独立 EXE：

```bat
installer\build_exe.bat
```

脚本使用 PyInstaller 将 CA 数据目录一并打包，生成 `dist\MediaCollectorHost.exe`，随后通过 `installer\install_host.bat` 注册。当前会话未执行 Windows EXE 编译或真机测试。

利用已有便携包重新生成完整便携 ZIP：

```bat
py -3 tools\build_portable.py --base-package "D:\旧版便携包\MediaCollector-Portable-x64" --out-dir "D:\新构建目录"
```

源码需位于 Git 工作区并已加入暂存区。脚本校验旧包的运行文件，复用其 Windows x64 启动器和 Python/Pillow；同步当前扩展及本地源码，重建 `source-code.zip` 和所有交付文件的 SHA-256。此操作不表示重新编译或验证了 Windows 二进制。

ZIP 时间戳来自 Git 提交时间或 `SOURCE_DATE_EPOCH`。源码包包含受版本管理的源码、资源、配置、测试和构建说明，不含 `.git` 历史、运行环境、缓存或产物。解压源码包后可在独立目录初始化 Git、安装依赖并构建。旧版历史说明保留在 `docs/LEGACY_README.md`，不作为当前操作指南。

## 项目结构与版本管理

`extension/` 包含界面、网站适配器及浏览器图片传输；`native-host/` 包含协议、任务、目录及图片处理；`installer/` 和 `tools/` 提供 Windows 安装、构建入口；`tests/`、`docs/` 保存验证与说明。

Host 名称为 `com.chrome_media_collector.host`，协议见 [docs/PROTOCOL.md](docs/PROTOCOL.md)。日志为 `%LOCALAPPDATA%\ChromeMediaCollector\collector.log`。取消不会撤回已交给 BitComet 的任务。

默认只保存合理的本地提交，不自动 Push 或创建 PR；远程同步前按 `AGENTS.md` 检查敏感信息和无关文件。
