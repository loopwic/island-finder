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

连接诊断与主机协议自检（不是实际刷写或固件执行测试）：

```bash
npm run controller:diagnose
npm run controller:self-test
```

控制器实现仅位于 `vision_service/pabotbase2.py` 与 `vision_service/controller_server.py`，macOS 与 Windows 共用同一份协议和状态机。

## 固件安装与更新

应用内入口位于“设备与识别 → 设备连接 → 开发板固件”。默认使用随应用内置的官方完整 `PABotBase2-ESP32-S3-2026090200.bin`，固定从 `0x0` 写入，不支持任意地址、单独 Bootloader、其他芯片或加密固件。接线参见 [官方指南](https://pokemonautomation.github.io/SetupGuide/Controllers/Controller-ESP32-S3.html)。

内置文件位于 `vision_service/firmware_assets/`，与版本清单、SHA-256、固定上游提交链接和非商业用途声明一起打入 macOS/Windows 安装资源。启动加载与桌面打包都校验文件大小及 SHA-256；文件缺失或损坏时明确报错，不联网下载、不静默回退。内置固件自身可离线使用（应用第一次配置 Python 运行依赖仍可能需要联网）。高级入口允许选择其他官方完整文件，切换文件会使旧确认失效；重启应用恢复默认内置版。

后端先验证镜像头、芯片 ID、Bootloader/应用校验和及 SHA-256、分区表 MD5 和应用描述符，再要求限时、单次确认。确认绑定当前后端会话、上传文件及 USB 串口身份。正式写入前再次校验文件、识别实际芯片与 Flash 容量，并拒绝安全启动或 Flash 加密设备。结构校验不能替代固件来源验证。

烧录任务由后端持有，通过固定版本的 Espressif `esptool` 子进程执行。自动化必须处于停止状态，控制器进入独占维护模式，配对和手柄输入均被阻止。界面默认直接烧录，完整备份由用户按需开启；确认页会再次展示本次选择。共同流程为芯片和容量检查 → 写入 → Flash 校验 → 重启 → 无按键的 PABotBase2 握手。开启备份时，在写入前插入整片 Flash 读取与落盘校验，备份失败不会写入。跳过备份不跳过安全检查或写入校验。校验或握手失败不会被显示为全部成功；页面重连不重启任务，写入失败也不自动重刷。

进度经现有 WebSocket 状态通道推送；备份显示百分比、已读取容量、速率和预计剩余时间，每秒最多更新一次。读取保留 esptool 的包长检查和设备端 MD5 校验，完成后仍须落盘并校验 SHA-256 才能写入。桌面正常关闭和退出会在烧录期间被拦截。强制结束进程、拔线或断电仍可能中断烧录；重新启动后会提示中断，不会自动继续。总时限根据所选速率及支持的最大容量计算，高速至少 30 分钟，兼容速率为较大的全片备份留出协议开销余量。

临时烧录程序先以 `115200` 上传并完成握手，再切换到用户选择的传输速率，与 esptool CLI 的顺序一致。原始串口读取设置 8 秒超时，防止启动回复丢失后无限等待。初始化阶段另有 60 秒看门狗；进入备份阶段后不再使用这一短时限。界面分别显示连接、临时烧录程序启动、Flash 配置、备份与写入，不将握手失败误显示为仍在等待 BOOT。

macOS 烧录连接使用单独的 `firmware_transport.py` 适配层：pyserial 3.5 的 select 超时更新只改变软件截止时间，不重复调用 `IOSSIOSPEED` 重设高速串口。真实波特率、线路配置和复位操作保持原行为。Windows/Linux 仍由 esptool 使用原生串口实现，不应用 macOS 的处理方式。备份读取中的串口超时由 esptool 设为 3 秒；通信错误与摘要不匹配都直接失败，不跳过损坏的数据，也不自动重刷。

备份与任务记录放在当前数据目录的 `firmware/` 下，不进入安装资源或 Git。原始 Flash 备份需要用户自行保管；恢复备份属于单独维护操作，当前界面不提供一键还原。

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
