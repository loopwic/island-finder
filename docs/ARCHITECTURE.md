# 工程架构

## 设计原则

- 单一识别来源：Python/OpenCV 负责页面分类、地图裁切、地图评分和自动流程。
- 人工最终决策：候选只进入 `awaitingDecision`，保留或取消由用户触发。
- 输入必须可证明：每次按键依赖当前页面识别、控制器执行确认与全释放。
- 硬件身份稳定：采集设备按名称和硬件 ID 保存，索引不作为长期身份。
- 证据可回放：四岛原图、固定裁切图、算法版本和评分写入本机审计。
- 本地最小暴露：所有 HTTP 服务只绑定 `127.0.0.1`。

## 运行组件

### Web 控制台

`src/` 使用 React、TanStack Router、HeroUI 和 Tailwind。它负责资料配置、设备选择、状态展示、审计查看和候选决策。地图框、页面锚点和地图评分不属于浏览器职责。

浏览器在开发环境连接 `127.0.0.1:48197`；生产构建由同一后端直接提供，避免另起静态文件服务。

### 视觉后端

`vision_service/server.py` 提供本地 API，`backend.py` 管理配置、采集、状态机、稳定帧门禁、三轮页面切换重试和审计。`screen_classifier.py` 判断页面，`candidate_ocr.py` 与 `birthday_ocr.py` 处理文字/数值识别，`analyzer.py` 负责地图因素。

运行配置与审计默认存放在项目根目录的 `data/`。该目录已被 Git 忽略；需要隔离测试实例时可通过 `ISLAND_FINDER_DATA_DIR` 覆盖。后端会过滤旧结构中的未知字段并把地图区域重置为当前固定坐标。

### 平台采集

macOS 使用 `scripts/capture-stream.swift` 和 `scripts/run-capture-stream.sh`，通过 AVFoundation 按稳定设备 ID 输出 JPEG 帧流。Windows 使用 `cv2-enumerate-cameras` 获取 DirectShow 的真实设备名称、硬件信息和 OpenCV 编码索引，再由 OpenCV 以 DirectShow + UVC MJPEG 打开采集卡。Linux 保留 OpenCV `CAP_ANY` 兼容路径，但不属于当前实机支持范围。

预览与识别共享同一采集所有权，但使用不同节奏：原生链路持续取帧，OpenCV 只按状态机需要分析，前端预览不会驱动识别规则。

### 控制器服务

`vision_service/controller_server.py` 与 `pabotbase2.py` 是 macOS/Windows 共用的 Python 服务。它通过 pyserial 与 PABotBase2/ESP32-S3 通信，等待固件执行完成后才返回 HTTP 成功，并在取消或退出时发送全释放。`native/macos-controller/` 仅作为已经实机验证过的协议参考和 macOS 兼容构建，不再是默认运行时。

## 状态与安全门禁

核心阶段为：

```text
idle → restarting/fastForwarding → enteringName → enteringBirthday
     → scanning → awaitingDecision
```

`paused` 和 `error` 可从运行阶段进入。只有明确的用户动作才能从 `awaitingDecision` 进入保留或重开流程。

状态机的关键门禁：

- 无信号、加载中和未知页面不发送盲目推进；
- 名字候选必须经连续 OCR 确认；
- 页面提交后的重试要求仍识别为原页面；
- 四岛页先通过完整度、等待时间和连续变化量检查；
- 地图必须全部硬条件通过、达到阈值并连续命中；
- 选中候选后不确认，只暂停等待用户。

## 启动与停止

`scripts/run-stack.mjs` 是唯一全栈入口，可由 macOS 或 Windows 上的 npm 调用，支持 `dev`、`production` 和 `headless`。它会：

1. 检查外部命令和端口；
2. 启动 Python PABotBase2 控制器并等待健康端点；
3. 启动 Python 后端并等待 `/health`；
4. 开发模式启动 Vite HMR，生产模式使用后端静态页面；
5. 收到退出信号时终止自己创建的全部子进程。

它不会杀死占用端口的未知进程。这样既避免双实例向 Switch 发送输入，也不会误停用户正在使用的服务。

## 依赖与质量

- npm 依赖使用精确版本并由 `package-lock.json` 固定。
- Python 运行时直接使用 `uv`，依赖由 `uv.lock` 固定；Windows 专用依赖通过平台标记安装。
- Swift Package 仅在 macOS 的统一检查中作为协议兼容实现构建，Windows 不依赖 Swift。
- `npm run check` 是本地质量门禁，覆盖前端测试、后端与控制器测试、类型/生产构建和协议自检。

修改地图算法时，应先向 Pytest 加入审计裁切回归，再用 `vision:reanalyze-audits` 对现有证据重算。不得在浏览器端增加另一个地图评分实现。
