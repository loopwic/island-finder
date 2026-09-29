import { Button } from "@astryxdesign/core/Button";
import { Banner } from "@astryxdesign/core/Banner";
import { CheckboxInput } from "@astryxdesign/core/CheckboxInput";
import { Switch } from "@astryxdesign/core/Switch";
import { Selector } from "@astryxdesign/core/Selector";
import { ProgressBar } from "@astryxdesign/core/ProgressBar";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { useRef } from "react";
import * as stylex from "@stylexjs/stylex";
import { Panel, Metric } from "../core/panel";
import { StandardDialog } from "../core/standard-dialog";
import { AppIcon } from "../core/icons";
import { ui } from "../core/ui.stylex";
import { useFirmware } from "./use-firmware";
import { SettingRow } from "../core/setting-row";

const GUIDE =
  "https://pokemonautomation.github.io/SetupGuide/Controllers/Controller-ESP32-S3.html";
export function FirmwarePanel() {
  const f = useFirmware();
  const firmwareInput = useRef<HTMLInputElement>(null);
  const status = f.status;
  const close = () => {
    if (!f.pending) f.setOpen(false);
  };
  const progressActions = f.uncertain ? (
    <Button
      label="查询任务状态"
      variant="primary"
      isLoading={f.pending}
      clickAction={f.recover}
    />
  ) : (
    <>
      <Button label={f.busy ? "后台继续" : "关闭"} onClick={close} />
      {!f.busy && (
        <Button label="返回烧录设置" onClick={() => f.setStep("setup")} />
      )}
    </>
  );
  return (
    <>
      <Panel
        title="开发板固件"
        description="使用内置官方 PABotBase2 固件更新 ESP32-S3"
        icon={<AppIcon name="cpu" />}
      >
        <SettingRow
          label="当前固件"
          description={
            f.currentImage
              ? `${f.currentImage.chip} / ${f.currentImage.release}`
              : "未选择固件"
          }
        >
          <Button
            label={f.busy ? "查看烧录进度" : "管理固件"}
            variant={f.busy ? "secondary" : "primary"}
            onClick={f.show}
          />
        </SettingRow>
        <Text color="secondary" size="sm">
          完整备份可选；写入前会核对芯片和固件，完成后校验内容。
        </Text>
      </Panel>
      <StandardDialog
        open={f.open}
        title={
          f.step === "confirm"
            ? "确认写入固件"
            : f.step === "progress"
              ? "固件任务"
              : "开发板固件"
        }
        onClose={close}
        locked={f.pending}
        actions={
          f.step === "progress" ? (
            progressActions
          ) : f.step === "confirm" ? (
            <>
              <Button
                label="返回"
                isDisabled={f.pending}
                onClick={() => f.setStep("setup")}
              />
              <Button
                label={f.backupRequested ? "备份后烧录" : "直接烧录"}
                variant="destructive"
                isDisabled={!f.acknowledged || f.disabled || !f.confirmation}
                isLoading={f.pending}
                clickAction={f.flash}
              />
            </>
          ) : (
            <>
              <Button
                label="检查并继续"
                variant="primary"
                isLoading={f.pending}
                isDisabled={
                  f.disabled || !f.port || !f.currentImage || !f.automationIdle
                }
                clickAction={f.prepare}
              />
            </>
          )
        }
      >
        {f.error && (
          <Banner status="error" title="操作未完成" description={f.error} />
        )}
        {f.unavailable && (
          <Banner
            status="warning"
            title="后端未就绪"
            description="请等待连接恢复，页面不会自动重复烧录。"
          />
        )}
        {f.step === "setup" && (
          <>
            <Text color="secondary">
              断开开发板与 Switch 的 USB/OTG 连线，只保留 UART/COM 接电脑。
            </Text>
            <HStack gap={3} vAlign="end">
              <div {...stylex.props(ui.grow)}>
                <Selector
                  label="开发板串口"
                  width="100%"
                  value={f.port}
                  placeholder="选择 USB 串口"
                  isDisabled={f.disabled}
                  options={f.ports.map((item) => ({
                    value: item.path,
                    label: item.description,
                    description: item.path,
                  }))}
                  onChange={f.setPort}
                />
              </div>
              <Button
                label="刷新固件串口"
                isIconOnly
                icon={<AppIcon name="refresh" />}
                isDisabled={f.disabled}
                clickAction={f.refreshPorts}
              />
            </HStack>
            <Selector
              label="传输速率"
              width="100%"
              value={String(f.baud)}
              onChange={(value) => f.setBaud(Number(value))}
              isDisabled={f.disabled}
              options={[
                { value: "460800", label: "高速 460800" },
                { value: "115200", label: "兼容 115200" },
              ]}
            />
            <Switch
              label="烧录前完整备份"
              description="可选。保留原固件、自定义补丁和设备配置；16MB 高速备份约需 7 分钟。"
              labelPosition="start"
              labelSpacing="spread"
              width="100%"
              value={f.backupRequested}
              onChange={f.setBackupRequested}
              isDisabled={f.disabled}
            />
            <Text size="sm" color="secondary">
              {f.backupRequested
                ? "只有备份完成并校验通过后才开始写入。"
                : "不读取整片 Flash；芯片检查、文件检查和写入后校验仍然执行。"}
            </Text>
            {f.currentImage && (
              <div {...stylex.props(ui.tight, ui.padding, ui.panel)}>
                <Text weight="semibold">
                  {f.currentImage.source === "bundled"
                    ? `内置官方固件 ${f.currentImage.release}`
                    : "手动选择的固件"}
                </Text>
                <Text size="sm" xstyle={ui.wrap}>
                  {f.currentImage.filename}
                </Text>
                <HStack gap={4} wrap="wrap">
                  <Text size="sm" color="secondary">
                    {f.currentImage.chip}
                  </Text>
                  <Text size="sm" color="secondary">
                    {(f.currentImage.size / 1048576).toFixed(2)} MiB
                  </Text>
                  <Text size="sm" color="secondary">
                    写入地址 {f.currentImage.flashOffset}
                  </Text>
                </HStack>
              </div>
            )}
            {f.bundledError && (
              <Banner
                status="error"
                title="内置固件不可用"
                description={f.bundledError}
              />
            )}
            <Collapsible
              defaultIsOpen={false}
              trigger={<Text color="secondary">高级选项与固件来源</Text>}
            >
              <VStack gap={4} paddingBlockStart={4}>
                <Text size="sm" xstyle={ui.wrap}>
                  SHA-256：{f.currentImage?.sha256 ?? "—"}
                </Text>
                {f.currentImage?.sourceUrl && (
                  <a
                    {...stylex.props(ui.link)}
                    href={f.currentImage.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    查看官方来源
                  </a>
                )}
                <Text size="sm" color="secondary">
                  PABotBase 固件仅限非商业用途。仅接受官方完整 ESP32-S3 固件。
                </Text>
                <Button
                  label="选择其他官方版本"
                  isDisabled={f.disabled}
                  onClick={() => firmwareInput.current?.click()}
                />
                <input
                  ref={firmwareInput}
                  hidden
                  aria-label="选择官方完整固件"
                  type="file"
                  accept=".bin"
                  disabled={f.disabled}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.target.value = "";
                    if (file) void f.upload(file);
                  }}
                />
                {f.currentImage?.source !== "bundled" && (
                  <Button
                    label="恢复内置官方固件"
                    isDisabled={f.disabled}
                    clickAction={f.useBundled}
                  />
                )}
              </VStack>
            </Collapsible>
            {!f.automationIdle && (
              <Banner
                status="warning"
                title="请先停止自动选岛"
                description="暂停不等于停止，请在控制台结束当前自动化。"
              />
            )}
            <div {...stylex.props(ui.row, ui.between)}>
              <Button
                label="接线与 BOOT 操作说明"
                variant="ghost"
                icon={<AppIcon name="external" />}
                href={GUIDE}
                target="_blank"
                rel="noreferrer"
              />
              {status?.jobId && (
                <Button
                  label="上次任务详情"
                  variant="ghost"
                  onClick={() => f.setStep("progress")}
                />
              )}
            </div>
          </>
        )}
        {f.step === "confirm" && (
          <>
            <div {...stylex.props(ui.tight)}>
              <Text weight="semibold" xstyle={ui.wrap}>
                {f.confirmation?.port}
              </Text>
              <Text color="secondary" xstyle={ui.wrap}>
                {f.confirmation?.image.filename}
              </Text>
            </div>
            <div {...stylex.props(ui.metrics)}>
              <Metric label="传输速率" value={f.baud} />
              <Metric
                label="完整备份"
                value={f.backupRequested ? "开启" : "不备份，直接写入"}
              />
            </div>
            <Banner
              status="warning"
              title="原固件将被覆盖"
              description={`官方完整固件会替换 Bootloader 和自定义关灯补丁。${f.backupRequested ? "先备份整片 Flash，校验成功才开始写入。" : "本次不会创建恢复备份；如果需要保留原始内容，请返回开启备份。"}`}
            />
            <CheckboxInput
              label="已核对串口和固件来源，已断开 Switch 连线，并会保持供电直到完成"
              value={f.acknowledged}
              onChange={f.setAcknowledged}
              isDisabled={f.pending}
            />
          </>
        )}
        {f.step === "progress" && (
          <>
            {f.uncertain ? (
              <Banner
                status="warning"
                title="正在确认任务是否已启动"
                description="请求可能已被后端接收。请查询状态，不要再次提交烧录。"
              />
            ) : (
              <>
                <Token
                  label={
                    status?.busy
                      ? "进行中"
                      : status?.stage === "succeeded"
                        ? "已完成"
                        : status?.stage === "needs_reconnect"
                          ? "需要重新连接"
                          : "未完成"
                  }
                  color={
                    status?.stage === "succeeded"
                      ? "green"
                      : status?.stage === "failed"
                        ? "red"
                        : "default"
                  }
                />
                <Text xstyle={ui.wrap}>
                  {status?.message ?? "没有任务记录"}
                </Text>
                {f.busy && (
                  <ProgressBar
                    label={
                      status?.stage === "backing_up"
                        ? "原始固件备份"
                        : "固件写入与校验"
                    }
                    value={status?.percent}
                    hasValueLabel={status?.stage === "backing_up"}
                    isIndeterminate={status?.stage !== "backing_up"}
                  />
                )}
                {status?.stage === "backing_up" && (
                  <div {...stylex.props(ui.metrics)}>
                    <Metric
                      label="已读取"
                      value={`${((status.bytesRead ?? 0) / 1048576).toFixed(1)} / ${((status.totalBytes ?? 0) / 1048576).toFixed(0)} MiB`}
                    />
                    <Metric
                      label="读取速度"
                      value={`${((status.bytesPerSecond ?? 0) / 1024).toFixed(1)} KiB/s`}
                    />
                    <Metric
                      label="预计剩余"
                      value={
                        status.estimatedSeconds == null
                          ? "计算中"
                          : `约 ${Math.ceil(status.estimatedSeconds / 60)} 分钟`
                      }
                    />
                  </div>
                )}
                {f.busy && (
                  <Text size="sm" color="secondary">
                    请勿拔线、断电或退出应用。关闭此弹窗后任务仍在后台继续。
                  </Text>
                )}
                {status?.backupPath && (
                  <Text size="sm" xstyle={ui.wrap}>
                    原始 Flash 备份：{status.backupPath}
                  </Text>
                )}
                {status?.backupRequested === false && (
                  <Text size="sm" color="secondary">
                    本次选择直接烧录，未创建新备份。
                  </Text>
                )}
                {!!status?.logs.length && (
                  <Collapsible
                    defaultIsOpen={false}
                    trigger={<Text color="secondary">查看详细日志</Text>}
                  >
                    <pre {...stylex.props(ui.code)}>
                      {status.logs.join("\n")}
                    </pre>
                  </Collapsible>
                )}
              </>
            )}
          </>
        )}
      </StandardDialog>
    </>
  );
}
