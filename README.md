# Island Finder

Island Finder 是一个只在本机运行的《集合啦！动物森友会》开局选岛系统。它从 UVC 采集卡读取 Switch 画面，由 Python/OpenCV 判断当前页面、输入预先配置的中文或英文姓名与生日、快速推进对话，并分析四张候选地图。候选岛满足全部硬条件且达到阈值后，系统只移动光标并进入 `awaitingDecision`，最终保留或放弃由用户决定。

[![CI](https://github.com/loopwic/island-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/loopwic/island-finder/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

本项目与 Nintendo、任天堂、PABotBase2 及其关联公司无隶属、授权或背书关系。Nintendo Switch、《集合啦！动物森友会》及相关标识属于各自权利人。项目只处理用户自己设备输出的本地画面，不提供游戏文件、密钥、账户数据或官方固件。

## 系统边界

```text
React + TanStack Router + HeroUI 控制台
                │ HTTP / MJPEG（仅 127.0.0.1）
Python/OpenCV 常驻后端 ─── AVFoundation（macOS）/ DirectShow（Windows）
                │ HTTP（仅 127.0.0.1:32145）
Python 控制器服务 ─── ESP32-S3 / PABotBase2 ─── Switch 2
```

- Python 后端是识别、状态机、地图裁切和评分的唯一来源；浏览器不再维护第二套地图规则。
- 四个地图裁切区域固定在后端，基于 1920×1080 中文四岛页实测坐标。前端不显示、也不能修改裁切框。
- UVC 设备按硬件名称与 ID 保存，数值索引只作兼容信息，避免设备重新枚举后选错采集源。
- 正式流程只在已识别页面上发送输入。地图页必须通过渲染完整度和连续稳定帧门禁后才会评分。
- 页面提交后若机器短暂停顿，最多执行三轮、仍由当前页面识别确认的重试；耗尽后停止，不盲按。
- 命中候选后不会自动按 `A` 确认。停止、暂停、服务退出或控制链路异常都会取消队列并释放全部按键。

## 环境要求

- macOS 13 或更新版本，或 Windows 10/11 x64
- Node.js 22.12 或更新版本、npm 10 或更新版本
- Python 3.11/3.12 与 [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Switch / Switch 2、UVC HDMI 采集卡
- 真实输入需要 ESP32-S3 双 USB 口开发板：UART/COM 接电脑，USB/OTG 接 Switch 2

macOS 会使用项目内的 AVFoundation 原生采集优化，因此在 macOS 上还需要 Xcode Command Line Tools/Swift。Windows 不需要 Swift，摄像头名称和硬件 ID 由 DirectShow 枚举，画面由 OpenCV 读取。

依赖版本由 `package-lock.json` 与 `uv.lock` 固定。首次安装：

```bash
npm run setup
```

Windows PowerShell 使用相同命令。如果自动串口选择不正确，可在启动前固定开发板 COM 口：

```powershell
$env:ISLAND_CONTROLLER_SERIAL_PORT = "COM12"
npm run dev
```

## 启动方式

开发模式（含 Vite HMR、视觉后端与手柄服务）：

```bash
npm run dev
```

打开 `http://127.0.0.1:4173/`。生产模式会先执行类型检查和前端构建，再由视觉后端提供静态页面：

```bash
npm start
```

打开 `http://127.0.0.1:48197/`。不需要网页的自动启动模式：

```bash
npm run start:headless
```

统一启动器不会清理或抢占已被使用的端口；发现已有服务会直接报错退出，避免同时运行两套自动化。端口约定如下：

| 服务 | 地址 |
|---|---|
| Vite HMR | `127.0.0.1:4173` |
| Python/OpenCV 后端与生产页面 | `127.0.0.1:48197` |
| Python/PABotBase2 手柄服务 | `127.0.0.1:32145` |

单独维护某一层时可使用：

```bash
npm run dev:web
npm run vision:start
npm run controller:start
npm run controller:diagnose
npm run controller:self-test
```

## 使用流程

1. 在“设备与识别”中选择按名称显示的 UVC 采集设备，并确认画面为 1920×1080。
2. 配置纯中文或纯英文姓名、生日和初始人物样式；中文姓名还需为每个字填写无声调拼音。
3. 首次运行保持演练模式，确认名字候选、生日游标、人物页面与四岛页面都能稳定识别。
4. 设置综合分阈值和连续命中帧数。任何硬条件失败时，降低综合阈值也不会放行。
5. 关闭演练模式前确认 PABotBase2 已连接、Switch 2 能收到输入且所有按键都会自动释放。
6. 候选满足条件后，系统暂停并等待用户选择“保留”或“放弃并重来”。

姓名、生日、采集设备和规则配置默认保存在项目目录内：

```text
./data/settings.json
```

每轮四岛页原图、固定裁切图和评分证据保存在 `./data/selection-audits/`，用于回归分析。`data/` 已加入 `.gitignore`，不会意外提交用户资料或截图。可用 `npm run vision:reanalyze-audits` 按当前算法重算历史审计；它不会向 Switch 发送输入。需要临时改位置时仍可设置 `ISLAND_FINDER_DATA_DIR`。

Windows 首次部署见 [Windows 安装与排障](docs/WINDOWS.md)。详细画面约束见 [画面与识别校准](docs/CALIBRATION.md)，控制链路见 [控制器后端与安全协议](docs/CONTROLLER_BRIDGE.md)，模块职责见 [工程架构](docs/ARCHITECTURE.md)。

## 质量门禁

提交前执行统一检查：

```bash
npm run check
```

它会依次运行：

- Vitest 前端单元测试；
- Pytest/OpenCV 后端测试；
- TypeScript 类型检查与 Vite 生产构建；
- PABotBase2 协议和跨平台控制器 HTTP 契约自检；
- macOS 上额外执行旧 Swift 控制器兼容构建。

常用的独立命令：

```bash
npm test
npm run vision:test
npm run typecheck
npm run build
npm run controller:self-test
```

构建和测试不会自动启动选岛流程，也不会发送真实手柄输入。

## 目录

```text
src/
  app/                    前端后端状态同步与操作上下文
  backend/                本地 HTTP API 客户端
  components/             HeroUI/Tailwind 控制台
  domain/                 前端配置与运行状态类型
  routes/                 TanStack Router 三个工作页面
  vision/                 目标参考图的浏览器端特征提取
contracts/                前端与后端共同执行的行为契约样例
vision_service/           OpenCV 识别、状态机、跨平台手柄服务、审计与测试
scripts/                  Node 跨平台启动/检查与 macOS 原生采集入口
docs/                     架构、画面与控制链路说明
firmware/                 本地按键命令 JSON Schema
```

`node_modules/`、`.venv/`、`dist/` 和 `.build/` 都是可重建产物，不属于源码并已加入 `.gitignore`。

## 安全限制

- 本项目不删除存档，只支持尚未确认初始岛屿的新游戏流程。
- 名字与生日在游戏内确认后不可修改；真实运行前必须在演练模式核对。
- 水果、机场颜色、花种等在四岛页不可见，不属于当前评分条件。
- 当前页面、无信号、低置信度或地图转场未稳定时不会发送推进输入。
- 用户候选决策是硬门禁；系统不会替用户确认保留岛屿。

## 参与开发

项目使用 MIT 许可证开放源代码。提交问题或改动前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)；安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。测试裁切图的权利说明见 [NOTICE.md](NOTICE.md)。
