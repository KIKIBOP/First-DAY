# BitComet 接入依据与首版边界

查阅日期：2026-10-23。官方文档：

- [Command-line Usage](https://wiki.bitcomet.com/bitcomet-command-line/)
- [命令行用法](https://wiki-zh.bitcomet.com/bitcomet%E5%91%BD%E4%BB%A4%E8%A1%8C/)
- [Connection / Integration options](https://wiki.bitcomet.com/bitcomet-options/)

官方命令行页为 `.torrent` 文件列出了 `--output` 目录参数。该页的 URL 模式列举 HTTP、HTTPS、FTP 和 BC 链接，未为 Magnet 明确给出可验证的“URI + 单任务目录”组合。这不能推断新版本一定不支持，只能说明当前文档不足以把此组合当成可靠接口。

因此首版使用 Windows 已配置的 Magnet 协议。不会把 `.torrent` 参数套用到 Magnet，不改全局默认目录，不编辑 Downloads.xml，也不直接控制其他任务。后续可针对用户具体 BitComet 版本研究经过认证的 WebUI/正式接口；首版未实现它们。

程序从 UserChoice ProgId、HKCU/HKCR 的协议 command 和 App Paths 检查关联。只有识别出的可执行文件存在且名称为 BitComet.exe / BitComet_x64.exe 才请求 `os.startfile(magnet)`。这不是数字签名验证，也不能保证 Windows 在调用瞬间没有改变关联。

请在扩展设置中检测。首次使用前自行确认 BitComet 的添加任务选项：系统协议调用可能触发已有软件的自动开始设置。本工具无法保证一定弹出任务对话框。请先在 BitComet 中启用需要的确认行为，再在本次任务中选影片目录。工具只在用户点击采集且勾选 BitComet 时调用，不自动发送测试任务。

调用成功只证明 Windows 接受了“打开 URI”的请求。不能据此证明 BitComet 收到了任务、已确认添加、正在下载或已经完成。界面只显示“已发送至系统磁力链接处理程序，请在 BitComet 中确认”。

下载文件夹必须在 BitComet 添加任务窗口自行确认；首版**没有自动设置本任务保存位置**。用户可直接复制 Popup 任务状态/历史中显示的目录，或点击打开目录，在资源管理器地址栏复制。

真实调用和目录确认流程：**待 Windows 10/11 + 用户实际 BitComet 版本真机验证**。
