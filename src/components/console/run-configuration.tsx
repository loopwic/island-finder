import { Button } from "@astryxdesign/core/Button";
import { Text } from "@astryxdesign/core/Text";
import * as stylex from "@stylexjs/stylex";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useConsole } from "../../app/console-context";
import { StandardDialog } from "../core/standard-dialog";
import { Section } from "../core/panel";
import {
  PropertyControl,
  PropertyList,
  PropertyRow,
} from "../core/property-list";
import { StatusLabel } from "../core/status-label";
import { ui } from "../core/ui.stylex";
import { IdentityPanel } from "./identity-panel";
import { TargetPanel } from "./target-panel";
import { workbenchStyles } from "./workbench.stylex";

export function RunConfiguration() {
  const [editing, setEditing] = useState<"identity" | "target" | null>(null);
  const navigate = useNavigate();
  const {
    connectionStatus,
    capture,
    controller,
    settings,
    settingsLoaded,
    identityReady,
    state,
  } = useConsole();
  const identity = settings.identity;
  const firmwareBusy = Boolean(state?.firmware?.busy);
  return (
    <div {...stylex.props(workbenchStyles.aside)}>
      <Section title="本轮设置" isInset>
        <PropertyList label="本轮设置">
          <PropertyRow label="岛民" isControl>
            <PropertyControl
              label="编辑岛民资料"
              icon="user"
              onClick={() => setEditing("identity")}
            >
              {!settingsLoaded
                ? "正在读取"
                : identityReady
                  ? identity.name
                  : identity.name
                    ? "拼音未填写完整"
                    : "尚未填写"}
            </PropertyControl>
          </PropertyRow>
          <PropertyRow label="生日" icon="calendar">
            {identity.birthMonth} 月 {identity.birthDay} 日
          </PropertyRow>
          <PropertyRow label="选岛目标" isControl>
            <PropertyControl
              label="编辑选岛目标"
              icon="target"
              onClick={() => setEditing("target")}
            >
              硬条件全部通过，≥ {Math.round(settings.threshold * 100)}%
            </PropertyControl>
          </PropertyRow>
          <PropertyRow label="按键" icon="keyboard">
            {settings.dryRun ? "演练，不发送" : "发送到 Switch"}
          </PropertyRow>
        </PropertyList>
      </Section>
      <Section
        title="连接"
        isInset
        actions={
          <Button
            label="管理设备"
            variant="ghost"
            size="sm"
            onClick={() =>
              void navigate({ to: "/settings", search: { tab: "devices" } })
            }
          />
        }
      >
        <PropertyList label="连接状态">
          <PropertyRow label="后端">
            <StatusLabel
              tone={
                connectionStatus === "connected"
                  ? "success"
                  : connectionStatus === "disconnected"
                    ? "error"
                    : "warning"
              }
              label={
                connectionStatus === "connected"
                  ? "已连接"
                  : connectionStatus === "disconnected"
                    ? "未响应"
                    : "正在恢复"
              }
            />
          </PropertyRow>
          <PropertyRow label="采集">
            <StatusLabel
              tone={capture.connected ? "success" : "warning"}
              label={
                !capture.connected
                  ? "采集卡未就绪"
                  : capture.width
                    ? `${capture.width}×${capture.height}`
                    : "在线"
              }
            />
          </PropertyRow>
          <PropertyRow label="手柄">
            {firmwareBusy ? (
              <StatusLabel tone="warning" label="固件任务进行中" />
            ) : settings.dryRun ? (
              <StatusLabel tone="neutral" label="演练模式无需连接" />
            ) : (
              <StatusLabel
                tone={controller.connected ? "success" : "warning"}
                label={controller.connected ? "已连接" : "未连接"}
              />
            )}
          </PropertyRow>
        </PropertyList>
        {!settings.dryRun && !controller.connected && !firmwareBusy && (
          <Text
            type="supporting"
            color="secondary"
            xstyle={ui.sectionInset}
          >
            {controller.message}
          </Text>
        )}
      </Section>
      <StandardDialog
        open={editing !== null}
        title={editing === "identity" ? "岛民资料" : "选岛目标"}
        onClose={() => setEditing(null)}
      >
        {editing === "identity" ? (
          <IdentityPanel />
        ) : editing === "target" ? (
          <TargetPanel />
        ) : null}
      </StandardDialog>
    </div>
  );
}
