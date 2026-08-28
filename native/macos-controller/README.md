# macOS 本地手柄服务

这个 Swift 服务把 Island Finder 的本地 HTTP 按键命令发送到 ESP32-S3/PABotBase2，并把开发板切换成 NS2 有线手柄。服务不再包含未用于实机流程的 Mac 蓝牙实验实现。

> ESP32-S3/PABotBase2 路径已在本机完成固件刷写、921600 baud 串口握手、`0x1010` 模式读回、主机连接状态查询、固件命令完成确认，以及 NS2 HOME 页 `A`/`B`/方向键实机验证。

## 启动

在项目根目录运行：

```bash
npm run controller:diagnose
npm run controller:self-test
npm run controller:start
```

服务只监听 `127.0.0.1:32145`。Island Finder 中点击“启动配对”后，服务会自动打开开发板 UART/COM 口并启用 NS2 有线手柄。UART/COM 接 Mac，开发板的另一个 USB/OTG 口接 NS2。

也可以通过项目统一入口同时启动网页、视觉服务和控制服务：

```bash
npm run dev
```

## 第一次连接

1. 把 ESP32-S3 的 UART/COM 口接 Mac、USB/OTG 口接 NS2。
2. 运行 `npm run dev`，打开网页并点击“启动配对”。
3. 等待网页显示“NS2 有线手柄可接收按键”。
4. 第一下按键可能只用于让 NS2 建立有线手柄玩家连接；随后单独验证 `A`、方向键、`HOME` 和 `X`。
5. 确认每次按键都会自动释放，再关闭演练模式运行完整流程。

停止配对或按 `Ctrl-C` 会先取消固件队列、发送全释放状态，再让开发板回到安全模式。

## 本地 API

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/v1/status` | 读取后端、串口、主机连接和输入就绪状态 |
| `POST` | `/v1/pairing/start` | 连接 PABotBase2 并启用 NS2 有线手柄 |
| `POST` | `/v1/pairing/stop` | 释放按键并停止控制器后端 |
| `POST` | `/v1/press` | 发送一个限时按键 |
| `POST` | `/v1/release-all` | 立即释放全部按键 |

按键请求示例：

```json
{"type":"press","button":"A","hold_ms":70}
```

`hold_ms` 被限制在 20–2000 毫秒。服务会等待开发板报告“按下”和“释放”都执行完成；暂停、停止、串口断开或 HTTP 取消时都会执行全释放。

## 技术边界

- PABotBase2 连接使用带 CRC32C 的可靠分包协议；连接层确认只表示串口包到达，服务还会等待固件命令队列的完成通知。
- NS2 有线控制器使用标准 8-byte HID 报告；PABotBase2 命令承载其中 7-byte 控制器状态，固件负责 USB 报告封装。
- 服务只绑定回环地址，不接受局域网连接，也不上传个人资料或采集画面。
- 原生服务只保留当前实机使用的 PABotBase2 串口传输，不修改 Mac 蓝牙身份或系统蓝牙设置。
