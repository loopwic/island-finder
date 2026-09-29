import { NumberInput } from "@astryxdesign/core/NumberInput";
import { VStack } from "@astryxdesign/core/Layout";
import { Switch } from "@astryxdesign/core/Switch";
import { useConsole } from "../../app/console-context";
import { Panel } from "../core/panel";
import { SettingRow } from "../core/setting-row";
import { AppIcon } from "../core/icons";

export function RecognitionSettings() {
  const { settings, settingsLoaded, active, updateSettings } = useConsole();
  const disabled = active || !settingsLoaded;
  return (
    <Panel
      title="识别与运行"
      description="调整采集节奏、稳定帧和自动重开行为"
      icon={<AppIcon name="settings" />}
    >
      <VStack gap={0}>
        <SettingRow
          label="采集 / 预览 FPS"
          description="每秒采集的画面数量，范围 3–30 帧"
        >
          <NumberInput
            label="采集 / 预览 FPS"
            isLabelHidden
            width={136}
            units="FPS"
            min={3}
            max={30}
            isIntegerOnly
            value={settings.captureFps}
            isDisabled={disabled}
            onChange={(captureFps) => updateSettings({ captureFps })}
          />
        </SettingRow>
        <SettingRow label="扫描间隔" description="两次地图识别之间的等待时间">
          <NumberInput
            label="扫描间隔"
            isLabelHidden
            width={136}
            units="ms"
            min={100}
            max={5000}
            step={10}
            isIntegerOnly
            value={settings.scanIntervalMs}
            isDisabled={disabled}
            onChange={(scanIntervalMs) => updateSettings({ scanIntervalMs })}
          />
        </SettingRow>
        <SettingRow label="连续稳定帧" description="相同结果达到此数量后才推进">
          <NumberInput
            label="连续稳定帧"
            isLabelHidden
            width={136}
            units="帧"
            min={1}
            max={12}
            isIntegerOnly
            value={settings.stableFrames}
            isDisabled={disabled}
            onChange={(stableFrames) => updateSettings({ stableFrames })}
          />
        </SettingRow>
      </VStack>
      <Switch
        label="自动拒绝不合格地图"
        description="未通过全部硬条件时自动重开"
        labelPosition="start"
        labelSpacing="spread"
        width="100%"
        value={settings.autoReject}
        isDisabled={disabled}
        onChange={(autoReject) => updateSettings({ autoReject })}
      />
    </Panel>
  );
}
