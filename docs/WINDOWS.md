# Windows 安装与排障

Island Finder 的 Windows 运行时不依赖 Swift、zsh、AVFoundation 或 `mise`。Tauri 负责桌面窗口和统一进程生命周期，视觉与控制器服务使用 Python；摄像头走 DirectShow，开发板走 Windows COM 串口。

## 1. 安装运行时

安装以下 x64 版本，并确保命令能在 PowerShell 中直接运行：

- Node.js 22.12 或更新版本；
- Python 3.11 或 3.12；
- `uv`；
- Rust stable-msvc；
- Microsoft C++ Build Tools 中的“使用 C++ 的桌面开发”工作负载；
- Microsoft Edge WebView2 Runtime（Windows 10 1803 及以后通常已经安装）。

```powershell
node --version
npm --version
python --version
uv --version
rustc --version
```

然后在项目目录安装锁定依赖并执行无硬件协议自检：

```powershell
npm run setup
npm run controller:self-test
npm run check
```

`npm run check` 不启动自动选岛，也不会向 Switch 发送按键。

## 2. 确认两条硬件链路

1. 采集卡 HDMI 输入接 Switch 底座，USB 接 Windows；在“设置 > 隐私和安全性 > 相机”中允许桌面应用访问摄像头。
2. ESP32-S3 的 UART/COM 数据口接 Windows；另一个 USB/OTG 口接 Switch 2 或底座。
3. 在设备管理器的“端口 (COM 和 LPT)”中确认开发板端口，例如 `COM12`。

查看控制器服务能发现哪些端口：

```powershell
npm run controller:diagnose
```

如果电脑上有多个串口，先固定正确端口再启动：

```powershell
$env:ISLAND_CONTROLLER_SERIAL_PORT = "COM12"
npm run dev
```

需要永久保存时，可以在 Windows 用户环境变量中添加 `ISLAND_CONTROLLER_SERIAL_PORT`；不要把个人 COM 号写进项目源码。

## 3. 选择采集卡并进行演练

运行 `npm run dev` 后会自动打开 Island Finder 桌面窗口，进入“设备与识别”：

1. 从真实设备名称中选择外接 UVC/HDMI 采集卡；Windows 设备使用 DirectShow 硬件身份保存，而不是依赖不稳定的列表顺序。
2. 确认状态显示 `DirectShow 采集`、1920×1080 和实时帧率。
3. 首次启动保持“演练模式”，验证页面识别、姓名、生日和地图稳定帧门禁。
4. 只有在控制器显示已连接且演练完整通过后，才关闭演练模式。

## 4. 常见问题

### 列表里没有采集卡

- 关闭 OBS、相机、Discord 等可能独占采集卡的程序；
- 在设备管理器确认采集卡位于“相机”或“声音、视频和游戏控制器”；
- 检查 Windows 相机隐私权限；
- 拔插采集卡后，在页面点“刷新视频设备列表”。

### 能看到设备但打不开画面

- 确认没有其他程序占用同一 DirectShow 设备；
- 先在 Windows 相机或 OBS 中确认采集卡能输出画面，然后完全退出该程序；
- 重新选择采集卡并点“重新打开”。

### 找不到开发板或连接了错误的 COM 口

- 安装开发板对应的 CP210x/CH34x USB 串口驱动；
- 用 `npm run controller:diagnose` 核对候选端口；
- 用 `ISLAND_CONTROLLER_SERIAL_PORT` 固定端口；
- UART/COM 与 USB/OTG 是两条不同连接，不能只接其中一条。

### 端口已被占用

先运行 `npm run stop` 请求当前 supervisor 安全退出，再启动新实例。正常退出会先请求控制器停止配对并释放按键，然后关闭它创建的视觉与控制器进程。若端口仍被占用，说明占用者不是当前项目能验证的服务；Tauri 与 supervisor 都不会按端口盲目结束未知程序。
