import { Button } from "@astryxdesign/core/Button";
import { Switch } from "@astryxdesign/core/Switch";
import { VStack } from "@astryxdesign/core/Layout";
import { StatusLabel } from "../core/status-label";
import { useConsole } from "../../app/console-context";
import { Section } from "../core/panel";
import { SettingRow } from "../core/setting-row";

export function ControllerSettings() {
  const {
    controller,
    settings,
    settingsLoaded,
    active,
    state,
    runtime,
    updateSettings,
    runAction,
  } = useConsole();
  const disabled = active || !settingsLoaded;
  // The backend refuses a dry-run switch mid-run, including while paused.
  const runStopped = runtime.phase === "idle" || runtime.phase === "error";
  return (
    <Section
      title="手柄连接"
      description="ESP32-S3 模拟 Pro Controller"
      actions={
        <StatusLabel
          tone={controller.connected ? "success" : "neutral"}
          label={controller.connected ? "已连接" : "未连接"}
        />
      }
    >
      <VStack gap={0}>
        <SettingRow label="配对" description={controller.message}>
          <Button
            label={controller.active ? "停止配对" : "启动配对"}
            size="sm"
            isDisabled={Boolean(state?.firmware?.busy)}
            clickAction={() =>
              runAction(
                controller.active
                  ? "controller-disconnect"
                  : "controller-connect",
              )
            }
          />
        </SettingRow>
        <SettingRow
          label="自动连接手柄"
          description="打开应用后寻找已配置的手柄服务"
        >
          <Switch
            label="自动连接手柄"
            isLabelHidden
            value={settings.autoConnectController}
            isDisabled={disabled}
            onChange={(autoConnectController) =>
              updateSettings({ autoConnectController })
            }
          />
        </SettingRow>
        <SettingRow
          label="演练模式"
          description="只进行识别和状态推进，不发送真实按键"
        >
          <Switch
            label="演练模式"
            isLabelHidden
            value={settings.dryRun}
            isDisabled={!runStopped || !settingsLoaded}
            disabledMessage={runStopped ? undefined : "停止自动选岛后才能切换"}
            onChange={(dryRun) => updateSettings({ dryRun })}
          />
        </SettingRow>
      </VStack>
    </Section>
  );
}
