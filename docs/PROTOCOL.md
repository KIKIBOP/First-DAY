# Native Messaging 协议 v0.1

Host: `com.chrome_media_collector.host`。安装器只允许用户给出的一个扩展 origin，不使用通配符。没有 HTTP 控制接口。

请求：`{"type":"get_settings","data":{}}`。

成功：`{"ok":true,"data":{...}}`；失败：`{"ok":false,"error":"中文错误信息"}`。每次 native bridge 请求都可启动一个短生命周期 Host。Chrome stdin 断开不杀死独立 worker。设置/状态写入磁盘使用临时文件 + 原子替换。

| type | data | data 返回 |
|---|---|---|
| get_status | {} | connected、version、history 最近100条、bitcomet 检测 |
| get_settings | {} | 本地设置 |
| update_settings | 设置字段 | 验证并保存后的完整设置 |
| start_collection | title、可选 raw_title、url、images、magnets、options | task_id |
| get_task_status | task_id | state、events、folder、errors/error、原始请求等 |
| cancel_task | task_id | requested，发出合作式取消标记 |
| open_folder | folder | opened，仅当前保存根目录内子目录 |
| check_bitcomet | {} | associated、protocol_command、protocol_executable、候选路径等 |

示例采集 payload：

```json
{
  "title": "[高清] 示例影片 ABC-123",
  "raw_title": "[高清] 示例影片 ABC-123",
  "url": "https://example.com/thread-123.html",
  "images": [{"url":"https://cdn.example.com/cover.png"},{"url":"https://cdn.example.com/preview.webp"}],
  "magnets": ["magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"],
  "options": {"save_images":true,"save_magnet":true,"auto_bitcomet":false,"resubmit":false}
}
```

示例仅展示数据格式，不应向真实下载客户端发送未经确认的测试磁力。

最多两张图，最多一条磁力，多个磁力必须在 UI 选一条。未选择图片/磁力时允许只采集其他字段；若要求保存图片但不足两张，报告部分完成。标题、URL、选项类型、消息长度、绝对根目录、目标路径边界均由本地程序再次验证，网页不能指定命令或执行文件。

任务状态：queued / running / completed / partial / failed / cancelled / interrupted。completed 表示采集流程完成，不是 BitComet 下载完成。取消不会撤回已经发出的 URI 请求。stale heartbeat 只表示任务状态无法继续确认；不自动恢复/重发任务。

日志和提交意图先落盘，异常情况下优先避免重复任务；人工确认后可 resubmit。Host stdout 只有长度帧，诊断写文件或 stderr。Windows stdin/stdout 用 msvcrt 设置二进制模式。


## v0.1.2 浏览器原图传输

扩展保持 `connectNative` 长连接，依次发送请求并等待响应。

1. `prepare_collection`：与 `start_collection` 相同的采集数据，返回 `task_id` 和需要获取的 `image_slots`；任务先保持 queued，写入准备事件。已有完整图片不会再次下载。
2. `image_transfer`：包含 `task_id`、`slot`、`action`。`begin` 携带 MIME；`chunk` 携带从零递增的原始字节 `offset` 和严格 Base64 `content`；`finish` 验证原始图片后发布暂存文件；`heartbeat` 更新准备阶段心跳。
3. 每块最多 192 KiB，单图最多 25 MiB。每个槽位绑定任务中已验证的原图 URL，不接受外部本地路径；任务 JSON 不保存图片 Base64 或 Cookie。
4. `finish_preparation` 携带 task_id 及最多两条浏览器失败说明，启动原有独立采集进程。Worker 优先采用校验通过的浏览器原图，缺失时调用 Native 下载器。
5. `fail_preparation` 将仍处于准备阶段的任务标记失败并清理暂存，不删除已启动 Worker 的原图。`cancel_task` 可以取消准备阶段；已取消任务不能启动 Worker。

任务状态仍为 queued/running/completed/partial/failed/cancelled/interrupted。queued 中的准备事件表示浏览器正在取图，不表示文件已保存。原图先经完整解码，再原子发布到影片目录；完成或取消后清理当前暂存。
