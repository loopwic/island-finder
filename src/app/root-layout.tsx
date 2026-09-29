import { AppShell } from "@astryxdesign/core/AppShell";
import { Card } from "@astryxdesign/core/Card";
import { SideNav, SideNavItem } from "@astryxdesign/core/SideNav";
import {
  HStack,
  Layout,
  LayoutContent,
  VStack,
} from "@astryxdesign/core/Layout";
import { Text } from "@astryxdesign/core/Text";
import * as stylex from "@stylexjs/stylex";
import { presentation } from "../components/core/presentation.stylex";
import { Button } from "@astryxdesign/core/Button";
import { Banner } from "@astryxdesign/core/Banner";
import { useTheme } from "@astryxdesign/core/theme";
import { Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { useState } from "react";
import { useConsole } from "./console-context";
import { useThemeMode } from "./theme-mode-context";
import { AppIcon } from "../components/core/icons";
import { ErrorDialog } from "../components/core/panel";
import { ActivityLog } from "../components/console/activity-log";
import { shellStyles } from "./shell.stylex";
import { AppHeader } from "../components/core/app-header";

const pages = [
  { to: "/", label: "运行控制台", icon: "dashboard" },
  { to: "/audit", label: "选图审计", icon: "audit" },
  { to: "/settings", label: "设备与识别", icon: "settings" },
] as const;

export function RootLayout() {
  const navigate = useNavigate();
  const pathname = useRouterState({
    select: (route) => route.location.pathname,
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const {
    runtime,
    notice,
    dismissNotice,
    retrySettings,
    settingsSyncState,
    ready,
    connectionStatus,
    connectionError,
    runAction,
    reconnect,
  } = useConsole();
  const { mode } = useTheme();
  const { toggle } = useThemeMode();
  const enabled = !["idle", "error"].includes(runtime.phase);
  const connected = connectionStatus === "connected";
  const page = pages.find((item) => item.to === pathname) ?? pages[0];

  return (
    <>
      <AppShell
        variant="wash"
        contentPadding={2}
        height="fill"
        mobileNav={{
          breakpoint: "md",
          hasToggle: false,
          isOpen: mobileOpen,
          onOpenChange: setMobileOpen,
        }}
        sideNav={
          <SideNav
            xstyle={shellStyles.navigation}
            header={
              <HStack
                gap={3}
                vAlign="center"
                paddingBlock={4}
                paddingInline={2}
              >
                <span {...stylex.props(presentation.identity)}>
                  <AppIcon name="map" />
                </span>
                <VStack gap={1}>
                  <Text weight="semibold">Island Finder</Text>
                  <Text size="sm" color="secondary">
                    {import.meta.env.DEV ? "开发模式" : "本地自动选岛"}
                  </Text>
                </VStack>
              </HStack>
            }
            footer={
              <SideNavItem
                label={mode === "dark" ? "浅色模式" : "深色模式"}
                icon={
                  <AppIcon name={mode === "dark" ? "sun" : "moon"} size={18} />
                }
                onClick={toggle}
              />
            }
          >
            <VStack gap={1}>
              {pages.map((item) => (
                <SideNavItem
                  key={item.to}
                  label={item.label}
                  size="lg"
                  icon={<AppIcon name={item.icon} size={18} />}
                  isSelected={pathname === item.to}
                  onClick={() => {
                    setMobileOpen(false);
                    void navigate({ to: item.to });
                  }}
                />
              ))}
            </VStack>
          </SideNav>
        }
      >
        <Card padding={0} height="100%" width="100%">
          <Layout
            padding={0}
            header={
              <AppHeader
                title={page.label}
                actions={
                  <>
                    {pathname === "/" && (
                      <>
                        <ActivityLog />
                        <Button
                          label={enabled ? "停止选岛" : "开始选岛"}
                          variant={enabled ? "secondary" : "primary"}
                          icon={<AppIcon name={enabled ? "stop" : "play"} />}
                          isDisabled={!connected || (!enabled && !ready)}
                          clickAction={() =>
                            runAction(enabled ? "stop" : "start")
                          }
                        />
                      </>
                    )}
                  </>
                }
              />
            }
            content={
              <LayoutContent padding={0}>
                <VStack gap={0} xstyle={shellStyles.route}>
                  {!connected && (
                    <Banner
                      status="warning"
                      title={
                        connectionStatus === "disconnected"
                          ? "后端连接中断"
                          : "正在恢复连接"
                      }
                      description={
                        connectionError ??
                        "当前任务由后端继续持有，恢复连接后同步。"
                      }
                      endContent={
                        <Button
                          label="重新连接"
                          clickAction={reconnect}
                          isDisabled={connectionStatus === "connecting"}
                        />
                      }
                    />
                  )}
                  <Outlet />
                </VStack>
              </LayoutContent>
            }
          />
        </Card>
      </AppShell>
      <ErrorDialog
        error={notice}
        title={settingsSyncState === "error" ? "配置尚未保存" : "操作提示"}
        onClose={dismissNotice}
        onRetry={
          settingsSyncState === "error" ? () => void retrySettings() : undefined
        }
      />
    </>
  );
}
