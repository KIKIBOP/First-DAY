# 网页影片一键采集助手

Chrome Manifest V3 扩展 + Python 3.11+ Native Messaging Host + Windows Magnet 协议。第一阶段实现源码，不是已在 Windows 验证过的发行版。

已根据用户上传的真实 Discuz HTML 完成 DOM 提取验证：完整帖子标题（包括外侧分类标签）、首帖中两张附件原图、代码块磁力。Windows 安装、原图服务器的实际下载、Chrome 与 Windows Host 联动、BitComet 调用：**待真机验证**。

## 快速开始（Windows 10/11）

### 1. 构建本地 EXE（开发者只需构建一次）

安装 Python 3.11 或更新版本，勾选 Python Launcher。双击 `installer\build_exe.bat`。此脚本安装依赖并用 PyInstaller 生成：

```
dist\MediaCollectorHost.exe
```

当前交付**不包含已构建的 Windows EXE**。在 Linux 环境无法可靠生成、运行或验证该 EXE。开发者完成 Windows 构建后，把整个项目文件夹（包括 `dist`）交给普通用户；普通用户只需 Chrome 和 BitComet，**不必安装 Python**。

`--console` 是 Native Messaging 二进制标准流所必需，不应改成 `--windowed`。不要单独双击 Host EXE，Chrome 会自动启动它。耗时采集由独立后台进程完成。

### 2. 安装 Chrome 扩展

1. 把项目解压到固定位置，例如 `D:\Apps\chrome-media-collector`。
2. Chrome 打开 `chrome://extensions`，启用“开发者模式”。
3. 点击“加载已解压的扩展程序”，选择项目下的 **extension** 文件夹。
4. 复制扩展卡片上 32 位扩展 ID。

### 3. 注册本地程序（当前 Windows 用户，无需管理员）

双击 `installer\install_host.bat`，输入上述扩展 ID，再输入保存根目录，例如 `D:\影片收藏`。空根目录会使用当前用户“视频”文件夹下的 `CollectedMovies`。首版支持本地磁盘绝对路径；不支持 UNC 网络共享。根目录长度最多 110 字符，以兼容传统 Windows 路径限制。

安装脚本会复制 EXE 到 `%LOCALAPPDATA%\ChromeMediaCollector`，生成严格匹配 ID 的 Host manifest，注册 HKCU，保留已有设置，并测试 EXE 的真实二进制 stdio 协议、输出 BitComet 检测信息。此自检**不等于** Chrome 到 Host 的联动已验证。

重启 Chrome，打开扩展的“设置”，确认显示“本地辅助程序已连接”。这是浏览器到 Host 的实际通信检查。点击“检测 BitComet”，确认 `associated: true`。如未关联，请在 BitComet 的集成设置及 Windows 默认应用中把 Magnet 关联到 BitComet。

也可命令行安装：

```bat
installer\install_host.bat -ExtensionId 这里填写真实的32位ID -Root "D:\影片收藏"
```

不内置任何临时扩展 ID。迁移未打包扩展的路径可能改变 ID，须重新注册。开发时保持绝对目录固定；正式发行可用 Chrome 打包功能生成密钥，再将对应的公钥 `key` 写入 manifest 固定 ID。私钥由发行者离线保管，不能打包进源码。Web Store 版本必须按最终商店 ID 重新安装 Host。

### 4. 日常使用

1. 在 Chrome 中正常打开有权访问、保存及下载的影片帖子，不必复制 URL、不必运行辅助脚本。
2. 点击扩展图标，自动读取当前页面，检查完整标题、两张图和磁力。
3. 磁力只有一条时自动选中；多条时必须手动选一条。原图来源有歧义时需要勾选确认。
4. 点击“一键采集并下载”。后台创建影片目录、保存原图和磁力、请求系统 Magnet 处理程序。
5. 在 BitComet 中确认任务，**把保存目录设置为本次影片文件夹**。本工具不会自动设置该目录，也不会修改全局默认目录。
6. 关闭 Popup 后后台任务继续，重新打开可查询最近同页面任务。

“复制目录”仅在用户主动点击时写入目录到剪贴板，不读取原有剪贴板内容。“检查缺失文件”保存缺失文件且不会调用 BitComet。“一键采集并下载”也可用于重新采集；只有主动勾选“再次发送磁力”才会重发此前请求过的链接。取消仅中止采集程序的后续操作，不能撤回已经交给 BitComet 的任务。

图片缩略图仅从已加载页面、且浏览器允许读取的图片像素生成；跨域画布受限时显示占位和已识别地址。Popup 不重新请求网页提供的远程图片，防止向本地服务发起不可信请求。**缩略图仅用于界面预览，不会作为“原图”保存。**

## 保存内容与重复保护

```
D:\影片收藏\清理后的帖子标题 [帖子标识摘要]\
    封面原图.jpg      # 扩展名由真实图片格式决定
    预览原图.jpg
    磁力链接.txt
    metadata.json
```

目录名处理 Windows 非法字符、保留名、尾随点和空格；按 UTF-16 长度截断，追加来源 URL 摘要防止同名/清理后重名。完整标题和保留内部空格的原始标题写入 metadata。原始图片 URL、文件名、SHA-256、来源网页和磁力提交状态也会记录。

已有完整且匹配来源的图片按 SHA-256 跳过。发现同名未知图片时保留原文件，为新图片使用摘要后缀。视频文件永远不会被删除或覆盖。图片先写临时文件，再原子发布；系统异常中断可能留下 `.image-*` 临时文件，可确认没有任务运行后手动清理。

同一帖子串行处理；不同帖子可以并行。跨帖子全局磁力日志防重复提交，兼容 BTv1 十六进制 / Base32 和混合链接的哈希别名。调用前先持久化“提交意图”，进程异常退出时也不会盲目重发。若调用失败或不确定是否已接收，修复关联后主动勾选“再次发送磁力”。这里的去重记录表示“请求过”，不表示 BitComet 真的添加成功。

## 真实网站适配情况

已解析用户上传的 `thread-3855581-1-1.html`，没有执行原网页脚本，也没有向网站发送测试磁力或下载影片。

- 主标题：`h1.ts` 内 `#thread_subject`，并合并同级 `typeid` 分类链接。
- 正文：首个 `td.t_f[id^=postmessage_]` / 相应首帖 DOM。
- 预览：`ignore_js_op` 附件块；文件名来自 `aimg_<ID>_menu` 的 `p strong`。
- 两张图：从标题提取影片编号，匹配“编号.jpg”和“编号-C.mp4.jpg”附件名，而不是匹配随机哈希 URL，也不按全页最大两图排序。
- 原图：优先 `zoomfile` / `file` 等字段，不使用 `static/image/common/none.gif` 占位图。
- 磁力：读取首帖 `.blockcode li`，无需点击复制，不读写系统剪贴板。

这些规则是通用代码，不硬编码范例的标题、磁力或两张图片 URL。附件命名模式不同或网站结构变化时会提示缺失/歧义，需要扩展适配器。示例适配器还支持明确的 `[data-film-preview]` 区域。

`tests/fixtures/actual-thread-minimal.html` 是从上传 HTML 摘出的最小真实 DOM，已去除账号信息、会话字段和脚本；`user-reference.html` 是早期重建的示例，图片 URL 为 example.com 占位。两者性质不同。线上登录态、网络和防盗链兼容性仍待真机验证。

## 图片下载与限制

本地程序通过 HTTP(S) 下载，携带受限 Referer，绝不读取、导出或上传 Chrome Cookie。只允许标准 HTTP(S) 端口；校验每次 DNS 和重定向，拒绝本地/私网/保留地址，并固定解析后的公开地址连接，HTTPS 保留原主机证书验证与 SNI。禁止 HTTPS 降级。单图最多 25 MiB、最多 6000 万像素；逐请求 socket 超时 20 秒、总时限约 90 秒（受单次读和 DNS 等待影响）；重试 0–5 次。

Pillow 校验 MIME、实际格式、完整解码和图片尺寸，再按 JPEG / PNG / WebP / GIF / BMP / AVIF 保存原始字节，不能把 HTML 当图片保存。格式支持还取决于 Windows 构建时 Pillow 的解码器；不支持的格式明确失败。

**首版尚未实现浏览器登录会话图片分块传输。** 如果图片服务器要求 Cookie、特殊 Referer、代理或其他访问授权，本地下载可能失败，任务显示“部分完成”并保留已成功内容。不会通过绕过访问控制来处理，也不会要求账号密码。Native 下载器当前使用直接公开连接，不自动使用浏览器或系统代理。

## BitComet 配置与诚实状态

详见 [docs/BITCOMET.md](docs/BITCOMET.md)。首版只有 Windows Magnet 协议请求：

> 已发送至系统磁力链接处理程序，请在 BitComet 中确认。

程序检查 Windows UserChoice/协议注册信息、可执行文件路径及 BitComet 文件名；还检查 App Paths 的 32/64 位注册信息。不假定安装在 C 盘。设置中填写的 BitComet 路径用于检查，不会改变系统关联，也不会作为未经证实的命令行接口调用。

目前没有 BitComet 任务确认、下载中、下载完成的可验证回执，不提供假进度。

## 开发与测试

```bat
py -3 -m pip install -r requirements.txt
py -3 -m unittest discover -s tests -p test_native.py -v
npm install
npm test
```

浏览器测试使用 Playwright 和本机 Chromium。Linux 默认 `/usr/bin/chromium`；Windows 运行前设置 `CHROMIUM_PATH` 为 chrome.exe 的完整路径，例如：

```bat
set "CHROMIUM_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe"
npm test
```

这只是测试命令示例，不是 BitComet 安装目录假设。`tests/browser.cjs` 在 Chromium 惰性 DOM 中验证页面提取；`tests/popup.cjs` 使用模拟 Chrome API 验证界面交互，不能替代真实 Native Messaging 联动测试。所有页面网络请求都被测试拦截，不自动下载图片或提交 Magnet。

Windows 手工集成检测（默认不提交任务）：

```bat
py -3 tests\windows_integration.py
```

只有明确传 `--submit`、输入自己有权下载的磁力、再输入 `SEND` 才会真实请求提交。完整测试结果与真机清单见 [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md)。

## 协议与代码结构

```
extension/          MV3、中文 Popup、后台桥接、适配器和设置
native-host/        协议、配置、任务进程、目录、图片下载和协议调用
installer/          Windows 用户级安装/卸载及 EXE 构建脚本
tests/              Python 测试、Chromium DOM/UI 测试和 Fixture
docs/               协议、BitComet 调研、实际测试和未验证事项
```

Host 名称为 `com.chrome_media_collector.host`。Native 消息是 4 字节小端长度加 UTF-8 JSON；stdout 仅用于协议。消息上限取 900000 字节，低于 Chrome Host 到扩展的 1 MiB 上限。日志在 `%LOCALAPPDATA%\ChromeMediaCollector\collector.log`。协议细节见 [docs/PROTOCOL.md](docs/PROTOCOL.md)。

本工具没有本地 HTTP 控制服务，也不接受任意命令。任务、设置、日志和全局磁力记录都在当前用户本地，不上传第三方。

## 卸载与故障处理

先等待/取消采集，再双击 `installer\uninstall_host.bat`，然后在 Chrome 移除扩展。脚本只移除注册、EXE 和 manifest，保留设置、历史和全部影片文件。

- **本地程序未连接**：核对扩展 ID 与 `%LOCALAPPDATA%\ChromeMediaCollector\com.chrome_media_collector.host.json` 的 `allowed_origins` 完全一致，核对 HKCU 路径及 EXE 是否存在，然后重启 Chrome。
- **EXE 更新失败**：可能旧后台进程仍在执行，先等待完成，不要强制终止未知任务。
- **403 / 图片失败**：确认浏览器当前有权访问；首版不传 Cookie，不支持浏览器代理；提供去除敏感信息后的结构/错误日志继续适配。
- **显示已中断**：任务心跳超过 180 秒未更新，可能重启或进程退出。不会自动重放任务，检查已存文件后主动重试。
- **同帖锁超时**：异常退出可能留下 `%LOCALAPPDATA%\ChromeMediaCollector\lock-*` 目录。确认没有任何 Host 工作进程运行后才可删除对应空锁目录，不要删除磁力日志。
- **打开目录失败**：只允许当前配置根目录内的影片子目录；改过根目录后，旧目录可能被安全校验拒绝。可通过资源管理器手动访问旧路径。

仅处理用户拥有访问、保存和下载权限的资源。不会批量爬取、刷新帖子、绕过登录/付费/验证码、改动 BitComet 其他任务或自动运行下载文件。
