# Island Finder

Island Finder 是一个在本机运行的《集合啦！动物森友会》开局选岛工具。它读取采集卡画面，自动完成开局对话、姓名与生日输入，并检查四张候选地图；找到符合条件的岛后会暂停，由你决定保留还是放弃。

[![CI](https://github.com/loopwic/island-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/loopwic/island-finder/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/loopwic/island-finder)](https://github.com/loopwic/island-finder/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 能做什么

- 自动识别开机、账户选择、对话、姓名、生日、人物设置和四岛选择页面。
- 中文姓名按“汉字 + 无声调拼音”输入，也支持英文姓名。
- 对话过程中自动使用 `B` 加速，并跳过允许跳过的动画。
- 等待四岛页面稳定后再裁切和评分，避免把转场画面当成地图。
- 页面偶尔卡顿时最多重试三轮；无法确认页面时会停止或重开，不持续盲按。
- 找到满足硬条件和分数阈值的岛后停在候选项上，不替你按 `A` 确认。
- 每轮保存本机审计记录，方便回看地图和评分原因。

## 使用前准备

你需要：

- Nintendo Switch 或 Switch 2，以及《集合啦！动物森友会》。
- 一张能输出 1920×1080 画面的 UVC HDMI 采集卡。
- 一块运行 PABotBase2 固件的 ESP32-S3 双 USB 口开发板。
- 两根连接线：开发板 UART/COM 口连接电脑，USB/OTG 口连接 Switch 或底座。
- macOS 13 及以上，或 Windows 10/11 x64。
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)。下载版会在第一次启动时用它准备本地 Python 环境。

macOS 还需要 Xcode Command Line Tools，用于编译项目自带的 AVFoundation 采集程序：

```bash
xcode-select --install
```

Windows 通常已经安装 WebView2；如果程序窗口无法打开，请安装 [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)。

## 下载和启动

从 [GitHub Releases](https://github.com/loopwic/island-finder/releases/latest) 下载与你的系统对应的文件：

- macOS：`island-finder-macos.tar.gz`
- Windows：`island-finder-windows-x64.zip`

解压后请保留整个 `Island-Finder` 文件夹，不要只移动其中的可执行文件。

### macOS

进入解压后的文件夹并运行：

```bash
cd Island-Finder
./Island-Finder
```

如果系统阻止第一次打开，可以在“系统设置 → 隐私与安全性”中允许打开。本项目目前未提供 Apple 公证签名。

### Windows

双击：

```text
Island-Finder.exe
```

第一次启动需要联网下载锁定版本的 Python 依赖，后续会直接复用本机缓存。

## 连接设备

```text
Switch / Switch 2 ── HDMI ── UVC 采集卡 ── USB ── 电脑
Switch / Switch 2 ── USB/OTG ── ESP32-S3 ── UART/COM ── 电脑
```

1. 打开 Switch，并确认采集卡能够输出 1920×1080 画面。
2. 将开发板 UART/COM 口接到电脑。
3. 将开发板 USB/OTG 口接到 Switch 或底座。
4. 启动 Island Finder，进入“设备与识别”。
5. 按设备名称选择采集卡，并确认手柄链路显示已连接。

如果 Windows 连接了多个串口，可以在启动前指定开发板端口：

```powershell
$env:ISLAND_CONTROLLER_SERIAL_PORT = "COM12"
./Island-Finder.exe
```

## 第一次配置

1. 填写岛民姓名、生日和初始人物样式。
2. 中文姓名需要给每个汉字填写无声调拼音，例如“明”填写 `ming`。
3. 设置希望保留的地图条件和综合分阈值。
4. 首次运行保持“演练模式”，检查姓名候选、生日游标、采集画面和页面识别。
5. 确认 Switch 能收到测试按键且按键会正常释放后，再关闭演练模式。

四张地图的裁切区域由后端固定管理，不需要手动拖动或校准前端方框。

## 开始选岛

1. 在运行控制台打开“自动选岛”。
2. 程序会从当前页面开始识别和推进。
3. 命中候选后，程序会暂停并显示四张地图的评分理由。
4. 选择“保留”时由你继续在 Switch 上确认；选择“放弃并重来”时程序会重新开始下一轮。

自动选岛只适用于尚未确认初始岛屿的新游戏流程，不会删除现有存档。

## 停止

关闭桌面窗口会停止视觉和手柄服务，并释放所有按键。

如果窗口已经消失但服务仍在运行，可以在源码目录执行：

```bash
npm run stop
```

遇到无信号、未知页面、识别置信度不足或控制器断开时，程序不会继续盲按。

## 本机数据

以下内容只保存在解压目录中的 `data/`：

- 姓名、生日和设备设置：`data/settings.json`
- 每轮地图画面和评分记录：`data/selection-audits/`

项目不会上传采集画面、姓名、生日、账户数据或游戏数据。删除 `data/` 即可清除本机配置和历史记录。

## 从源码运行

开发者需要 Node.js 22.12+、npm 10+、Python 3.11/3.12、`uv` 和 Rust stable：

```bash
git clone https://github.com/loopwic/island-finder.git
cd island-finder
npm run setup
npm run dev
```

提交前运行：

```bash
npm run check
```

更多资料：

- [Windows 安装与排障](docs/WINDOWS.md)
- [控制器连接与安全协议](docs/CONTROLLER_BRIDGE.md)
- [画面与识别校准](docs/CALIBRATION.md)
- [工程架构](docs/ARCHITECTURE.md)
- [参与开发](CONTRIBUTING.md)

## 声明

本项目与 Nintendo、任天堂、PABotBase2 及其关联公司无隶属、授权或背书关系。Nintendo Switch、《集合啦！动物森友会》及相关标识属于各自权利人。本项目不提供游戏文件、密钥、账户数据或官方固件。

项目使用 [MIT License](LICENSE)。测试图片的权利说明见 [NOTICE.md](NOTICE.md)。
