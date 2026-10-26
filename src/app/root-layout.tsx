import { AppShell } from "@astryxdesign/core/AppShell";
import { Card } from "@astryxdesign/core/Card";
import { SideNav, SideNavItem } from "@astryxdesign/core/SideNav";
import { Layout, LayoutContent, VStack } from "@astryxdesign/core/Layout";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { Button } from "@astryxdesign/core/Button";
import { useTheme } from "@astryxdesign/core/theme";
import * as stylex from "@stylexjs/stylex";
import { Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { useState } from "react";
import { useConsole } from "./console-context";
import { useThemeMode } from "./theme-mode-context";
import { AppIcon } from "../components/core/icons";
import { ErrorDialog } from "../components/core/panel";
import { RunControls } from "../components/console/run-controls";
import { presentation } from "../components/core/presentation.stylex";
import { shellStyles } from "./shell.stylex";
import { AppHeader } from "../components/core/app-header";
import { Notice } from "../components/core/notice";

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
    notice,
    dismissNotice,
    retrySettings,
    settingsSyncState,
    connectionStatus,
    connectionError,
    reconnect,
  } = useConsole();
  const { mode } = useTheme();
  const { toggle } = useThemeMode();
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
            aria-label="主导航"
            xstyle={shellStyles.navigation}
            header={
              <div {...stylex.props(shellStyles.brand)}>
                <span {...stylex.props(presentation.brandMark)}>
                  <AppIcon name="map" />
                </span>
                <Text weight="medium" maxLines={1}>
                  Island Finder
                </Text>
                {import.meta.env.DEV && <Token label="开发" size="sm" />}
              </div>
            }
            footer={
              <SideNavItem
                label={mode === "dark" ? "浅色模式" : "深色模式"}
                icon={<AppIcon name={mode === "dark" ? "sun" : "moon"} />}
                onClick={toggle}
              />
            }
          >
            <VStack gap={0.5}>
              {pages.map((item) => (
                <SideNavItem
                  key={item.to}
                  label={item.label}
                  icon={<AppIcon name={item.icon} />}
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
        <Card
          padding={0}
          height="100%"
          width="100%"
          xstyle={shellStyles.contentFrame}
        >
          <Layout
            padding={0}
            header={
              <AppHeader
                title={page.label}
                icon={page.icon}
                actions={pathname === "/" ? <RunControls /> : undefined}
              />
            }
            content={
              <LayoutContent padding={0}>
                <VStack gap={0} xstyle={shellStyles.route}>
                  {connectionStatus !== "connected" && (
                    <Notice
                      status="warning"
                      container="section"
                      title={
                        connectionStatus === "disconnected"
                          ? "后端连接中断"
                          : "正在恢复连接"
                      }
                      description={
                        connectionError ??
                        "当前任务由后端继续持有，恢复连接后同步。"
                      }
                      action={
                        <Button
                          label="重新连接"
                          size="sm"
                          icon={<AppIcon name="refresh" size={14} />}
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
