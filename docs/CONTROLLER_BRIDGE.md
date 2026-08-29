# 控制器后端与安全协议

当前唯一受支持的真实输入链路是 ESP32-S3 + PABotBase2。macOS 或 Windows 电脑从开发板 UART/COM 口发送可靠串口命令，开发板从独立 USB/OTG 口向 Switch 2 枚举为有线手柄。主机服务已统一为 Python/pyserial，两个系统使用同一份协议实现。

```text
Island Finder Python 后端
    │ HTTP 127.0.0.1:32145
Python island-controller-service
    │ 921600 baud PABotBase2，UART/COM
ESP32-S3
    │ NS2 Wired Controller，USB/OTG
Nintendo Switch 2
```

普通 2.4 GHz 手柄接收器、macOS 内置蓝牙、Windows 的 ViGEm/vJoy 或一根普通电脑 USB-C 数据线都不能代替这条双口链路：它们只能让电脑接收或在电脑内创建输入设备，不能让电脑的 USB 端口直接以 Switch 2 手柄身份工作。

## 连接与启动

1. 开发板 UART/COM 接电脑，USB/OTG 接 Switch 2 或底座。
2. 先保持前端演练模式开启。
3. 用 Tauri 桌面栈启动 `npm run dev`，或仅在维护控制器时单独运行 `npm run controller:start`。
4. 等待状态显示 PABotBase2、NS2 有线手柄和主机输入均已就绪。
5. 首次连接时单独验证 `A`、方向、`HOME` 和 `X`，并确认每次输入都会释放。

诊断与固件自检：

```bash
npm run controller:diagnose
npm run controller:self-test
```

控制器实现仅位于 `vision_service/pabotbase2.py` 与 `vision_service/controller_server.py`，macOS 与 Windows 共用同一份协议和状态机。

默认会优先选择描述中包含 ESP32、USB Serial、UART、CP210 或 CH340 的串口。在 Windows 上需要固定端口时使用：

```powershell
$env:ISLAND_CONTROLLER_SERIAL_PORT = "COM12"
npm run controller:diagnose
npm run dev
```

## 本地 API

服务只绑定 `127.0.0.1:32145`：

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/v1/status` | 后端、串口、NS2 主机和输入就绪状态 |
| `POST` | `/v1/pairing/start` | 连接 PABotBase2 并启用有线手柄 |
| `POST` | `/v1/pairing/stop` | 释放按键并停止配对 |
| `POST` | `/v1/press` | 发送一项限时按键 |
| `POST` | `/v1/release-all` | 立即取消队列并释放全部按键 |

示例：

```json
{"type":"press","button":"A","hold_ms":70}
```

支持 `A`、`B`、`X`、`Y`、`L`、`R`、`PLUS`、`MINUS`、`HOME`、`UP`、`DOWN`、`LEFT`、`RIGHT`。方向键按 D-pad 发送，`hold_ms` 限制为 20–2000 毫秒。JSON 结构由 [firmware/command.schema.json](../firmware/command.schema.json) 约束。

## 完成语义

`POST /v1/press` 成功表示以下步骤全部完成，而不只是串口数据已经写出：

1. 请求和按键范围验证通过；
2. 固件执行按下报告；
3. 保持指定时间；
4. 固件执行全释放报告；
5. 两条固件命令都返回完成通知。

暂停、停止、串口断开、请求失败和服务退出都会取消固件队列并请求全释放。Python 自动化只在已识别页面上调用此 API；页面提交后仍停留在原页面时，最多进行三轮有页面确认的重试，之后转为错误状态。

## 上机安全检查

1. 自动化处于停止或演练状态。
2. `/v1/status` 显示控制器可接收输入。
3. 单键验证均能自动释放。
4. 无信号或低置信度页面不会触发输入。
5. 四岛候选命中后只进入等待决定，不自动确认。
6. 关闭终端或按 `Ctrl-C` 后，开发板和服务状态确认无按键保持。

本项目不修改电脑蓝牙身份、不注入 Switch 游戏进程、不刷写 Switch，也不提供未知 HID 报告穷举工具。
