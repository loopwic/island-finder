import { Button } from "@astryxdesign/core/Button";
import { FormLayout } from "@astryxdesign/core/FormLayout";
import { Switch } from "@astryxdesign/core/Switch";
import { HStack } from "@astryxdesign/core/Layout";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { useConsole } from "../../app/console-context";
import { Panel } from "../core/panel";
import { AppIcon } from "../core/icons";

export function ControllerSettings() {
  const {
    controller,
    settings,
    settingsLoaded,
    active,
    state,
    updateSettings,
    runAction,
  } = useConsole();
  const disabled = active || !settingsLoaded;
  return (
    <Panel
      title="手柄连接"
      icon={<AppIcon name="cpu" />}
      description="ESP32-S3 模拟 Pro Controller"
      actions={
        <Token
          label={controller.connected ? "已连接" : "未连接"}
          color={controller.connected ? "green" : "default"}
        />
      }
    >
      <HStack hAlign="between" vAlign="center" gap={4}>
        <Text color="secondary">{controller.message}</Text>
        <Button
          label={controller.active ? "停止配对" : "启动配对"}
          isDisabled={Boolean(state?.firmware?.busy)}
          clickAction={() =>
            runAction(
              controller.active
                ? "controller-disconnect"
                : "controller-connect",
            )
          }
        />
      </HStack>
      <FormLayout>
        <Switch
          label="自动连接手柄"
          description="打开应用后寻找已配置的手柄服务"
          labelPosition="start"
          labelSpacing="spread"
          width="100%"
          value={settings.autoConnectController}
          isDisabled={disabled}
          onChange={(autoConnectController) =>
            updateSettings({ autoConnectController })
          }
        />
        <Switch
          label="演练模式"
          description="只进行识别和状态推进，不发送真实按键"
          labelPosition="start"
          labelSpacing="spread"
          width="100%"
          value={settings.dryRun}
          isDisabled={disabled}
          onChange={(dryRun) => updateSettings({ dryRun })}
        />
      </FormLayout>
    </Panel>
  );
}
