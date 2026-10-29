# 实际测试结果与真机验证清单

测试日期：2026-10-23（Asia/Shanghai）。环境：Linux、Python 3.12、Pillow 12.3.0、Node.js 24、Playwright 1.62.1、本机 Chromium。项目支持 Python 3.11+，本次没有额外运行 Python 3.11。未在 Windows、真正 Chrome 扩展安装或 BitComet 上执行集成操作。

## 已执行

- Python unittest：**24 项通过**。
- Chromium DOM 提取：**24 个断言通过**。
- Popup 界面（模拟 Chrome API）：**7 个断言通过**。
- Python 编译检查、扩展 JavaScript 语法检查通过。
- 对用户上传的完整真实 HTML，以惰性 DOMParser 解析、拦截全部页面网络请求，不执行附件网页脚本：完整标题、完整 Magnet 和两张原图地址精确匹配。
- 最终回归使用去掉脚本、账号及会话字段的真实 DOM 摘录，同样通过。
- `popup-preview.png` 是模拟数据的 UI 截图，**不是 Windows / 真 Chrome 扩展运行证明**。

机器可读结果在 `test-results.json`。Python 原始日志在 `python-tests.txt`。

## 对照需求测试项

| 要求 | 验证情况 |
|---|---|
| 标题提取 | Chromium 验证主标题、HTML 实体、外侧分类标签、完整真实标题及内部空格保留 |
| 中文目录 | Python 创建含中文/日文目录并测试相同标题来源冲突隔离 |
| Windows 文件名 | 非法字符、CON.txt、尾点、UTF-16 截断；规则在 Linux 验证，Windows 文件系统实际行为待验证 |
| 两张图定位 | 首帖预览范围、附件文件名配对，不选择 Logo/头像/回复图 |
| 原图提取 | 外层图片链接、data-original、Discuz zoomfile/file、懒加载、srcset；真实 HTML 两个随机哈希地址精确匹配 |
| Magnet 提取 | 可见文本、href、复制字段、input、textarea、真实 `.blockcode li`；BTv1/v2 合法性 |
| Magnet 去重 | DOM 去重、Base32 / hex 别名、跨帖子日志和主动重发 |
| Native Messaging | 真 Python 子进程读取/写入二进制帧、Unicode、多消息、坏类型、超限与截断；Chrome 与 Windows 注册联动待验证 |
| BitComet 检测 | 无效路径验证与非 Windows 检测结果；实际注册表和路径检测待 Windows 验证 |
| 重复采集 | 图片 SHA-256 跳过、保留视频及未知已有图片、磁力文本去重、不重复调用 launch（mock） |
| Popup 关闭后任务 | 实际关闭 Python Host stdin、Host 退出后独立 worker 完成；UI 重开查询采用模拟 Chrome API。真正 Popup 关闭测试待 Windows 验证 |
| 文件路径边界 | `..`、根目录、符号链接越界均拒绝；Windows junction 行为待真机验证 |
| 下载失败 | 模拟 HTTP 403 导致部分完成、保留磁力和 metadata；校验 PNG 字节/MIME、大小上限、逐重定向安全检查和固定公开 IP 连接 |

所有图片下载成功/失败场景使用本地生成图片与网络 mock，不代表已访问真实图片服务器。没有下载影片、没有真实提交任何 Magnet。

## 待 Windows 真机验证

1. Windows 10/11 上运行 build_exe.bat，确认生成的 EXE 能启动和通过 stdio 自检；记录 Python、Pillow、PyInstaller 及 BitComet 的具体版本。
2. 当前用户安装脚本正确写入 HKCU、allowed_origins 与真实扩展 ID 匹配；Chrome 设置页面显示“已连接”。
3. 在授权的真实帖子中打开 Popup：标题分类完整、两张图来源正确、只识别首帖 Magnet，无需复制 URL 或刷新。
4. 设置一个新的中文本地保存根目录，取消勾选 BitComet，先测试原图保存；核对 JPEG/PNG 等内容、扩展名、MIME 和 metadata。
5. 若图床要求登录 Cookie、代理或防盗链规则，首版可能失败。应报告具体错误并继续适配，不能视为下载已成功。
6. 采集中关闭 Popup，等待后重新打开：查询同一 task_id、查看进度、文件完整。测试 Chrome 退出、机器重启后的 interrupted 状态和主动补采。
7. 再次采集同帖，确认视频和已有图片未覆盖、默认不重发 Magnet；“检查缺失文件”不发 Magnet。
8. 在用户明确确认后，选择自己有权下载的测试链接，使用 tests/windows_integration.py --submit 并输入 SEND。确认 Windows 打开 BitComet；在添加窗口手动选择影片目录。
9. 保持 BitComet 运行/关闭分别调用，核对软件版本是否自动开始任务、是否弹出添加窗口；不要假定程序能控制其现有偏好。
10. 确认界面始终只报告“系统协议请求”，没有虚构任务添加或下载完成状态。
11. 测试取消、根目录不可写、磁盘空间不足、图床 HTTP 错误和软件未关联时的错误提示。
12. 等待后台任务结束后卸载，确认注册与 EXE 移除，影片、设置、日志、历史仍保留。

## 尚未实现

- 浏览器会话图片分块传输 / 受 Cookie 保护图片的本地保存。
- BitComet 自动指定 Magnet 单任务目录、任务确认回执或真实下载进度。
- 开机自动恢复异常中断的任务；异常遗留锁需要确认无任务运行后手工清理。
- 预构建、签名过的 Windows EXE 或安装发行包；已交付打包及用户级安装/卸载脚本。
- 跨代理环境的本地图片下载适配、网络共享根目录、任意附件命名规则的泛化。

这些限制没有通过模拟测试“冒充完成”。
