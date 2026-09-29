import { Button } from "@astryxdesign/core/Button";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { List, ListItem } from "@astryxdesign/core/List";
import { Text } from "@astryxdesign/core/Text";
import { StatusDot } from "@astryxdesign/core/StatusDot";
import { Divider } from "@astryxdesign/core/Divider";
import * as stylex from "@stylexjs/stylex";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useConsole } from "../../app/console-context";
import { StandardDialog } from "../core/standard-dialog";
import { IdentityPanel } from "./identity-panel";
import { TargetPanel } from "./target-panel";
import { AppIcon } from "../core/icons";
import { presentation } from "../core/presentation.stylex";

function ConnectionState({
  connected,
  label,
}: {
  connected: boolean;
  label: string;
}) {
  return (
    <HStack gap={2} vAlign="center">
      <StatusDot variant={connected ? "success" : "neutral"} label={label} />
      <Text size="sm" color="secondary">
        {label}
      </Text>
    </HStack>
  );
}

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
  } = useConsole();
  return (
    <>
      <VStack gap={8}>
        <VStack gap={3} role="region" aria-label="本轮设置">
          <Text as="h2" type="large" weight="semibold">
            本轮设置
          </Text>
          <List density="balanced">
            <ListItem
              label="岛民资料"
              startContent={
                <span
                  {...stylex.props(
                    presentation.identity,
                    presentation.smallIdentity,
                  )}
                >
                  {settings.identity.name.slice(0, 1) || "岛"}
                </span>
              }
              description={
                settingsLoaded
                  ? settings.identity.name || "尚未填写"
                  : "正在读取"
              }
              onClick={() => setEditing("identity")}
              endContent={<AppIcon name="right" />}
            />
            <ListItem
              label="选岛目标"
              startContent={
                <span
                  {...stylex.props(
                    presentation.identity,
                    presentation.smallIdentity,
                  )}
                >
                  <AppIcon name="map" />
                </span>
              }
              description={`全部硬条件通过，评分 ≥ ${Math.round(settings.threshold * 100)}%`}
              onClick={() => setEditing("target")}
              endContent={<AppIcon name="right" />}
            />
          </List>
          {!identityReady && settingsLoaded && (
            <Text color="secondary">开始前请补全岛民资料。</Text>
          )}
        </VStack>
        <Divider />
        <VStack gap={3} role="region" aria-label="连接状态">
          <HStack hAlign="between" vAlign="center">
            <Text as="h2" type="large" weight="semibold">
              连接状态
            </Text>
            <Button
              label="管理设备"
              variant="ghost"
              size="sm"
              onClick={() => void navigate({ to: "/settings" })}
            />
          </HStack>
          <List density="compact">
            <ListItem
              label="后端服务"
              endContent={
                <ConnectionState
                  connected={connectionStatus === "connected"}
                  label={connectionStatus === "connected" ? "已连接" : "未响应"}
                />
              }
            />
            <ListItem
              label="视频采集"
              endContent={
                <ConnectionState
                  label={capture.connected ? "在线" : "未就绪"}
                  connected={capture.connected}
                />
              }
            />
            <ListItem
              label={settings.dryRun ? "演练模式" : "手柄连接"}
              endContent={
                <ConnectionState
                  label={
                    settings.dryRun
                      ? "不发按键"
                      : controller.connected
                        ? "已连接"
                        : "未连接"
                  }
                  connected={controller.connected}
                />
              }
            />
          </List>
        </VStack>
      </VStack>
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
    </>
  );
}
