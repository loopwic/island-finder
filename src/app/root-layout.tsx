import { Alert, Button, Tooltip, useTheme } from "@heroui/react";
import { Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  AlertTriangle,
  ClipboardCheck,
  Gauge,
  Map,
  Moon,
  Power,
  RefreshCw,
  ScanSearch,
  Sun,
  WifiOff,
} from "lucide-react";
import { useEffect } from "react";
import { useConsole } from "./console-context";

function ThemeButton() {
  const { resolvedTheme, setTheme } = useTheme("system");
  const dark = resolvedTheme === "dark";

  useEffect(() => {
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", dark ? "#111113" : "#ffffff");
  }, [dark]);

  return (
    <Button
      fullWidth
      aria-label={`切换至${dark ? "浅色" : "深色"}模式`}
      className="justify-between px-3"
      variant="ghost"
      onPress={() => setTheme(dark ? "light" : "dark")}
    >
      <span>{dark ? "深色模式" : "浅色模式"}</span>
      {dark ? (
        <Moon aria-hidden="true" className="text-accent" size={17} />
      ) : (
        <Sun aria-hidden="true" className="text-muted" size={17} />
      )}
    </Button>
  );
}

export function RootLayout() {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (routerState) => routerState.location.pathname });
  const {
    runtime,
    notice,
    ready,
    connectionStatus,
    connectionError,
    runAction,
    reconnect,
  } = useConsole();
  const isSettings = pathname === "/settings";
  const isAudit = pathname === "/audit";
  const isWorkbench = !isSettings && !isAudit;
  const pageTitle = isSettings ? "设备与识别" : isAudit ? "选图审计" : "运行控制台";
  const automationEnabled = !["idle", "error"].includes(runtime.phase);
  const backendConnected = connectionStatus === "connected";

  return (
    <div className="bg-background text-foreground min-h-screen lg:grid lg:grid-cols-[16rem_minmax(0,1fr)]">
      <aside className="border-border bg-surface/90 flex flex-col gap-3 border-b p-3 backdrop-blur-xl lg:sticky lg:top-0 lg:h-screen lg:border-r lg:border-b-0 lg:p-4">
        <div className="flex items-center gap-3 px-2 py-2">
          <div className="bg-accent-soft text-accent grid size-10 shrink-0 place-items-center rounded-xl">
            <Map size={21} strokeWidth={2.1} />
          </div>
          <div className="min-w-0">
            <div className="truncate text-base font-semibold tracking-tight">Island Finder</div>
            <div className="text-muted text-xs">自动选岛</div>
          </div>
        </div>

        <nav
          className="grid grid-cols-3 gap-1.5 lg:mt-3 lg:flex lg:flex-col lg:gap-2"
          aria-label="主导航"
        >
          <Button
            fullWidth
            aria-current={isWorkbench ? "page" : undefined}
            className="justify-start"
            variant={isWorkbench ? "secondary" : "ghost"}
            onPress={() => void navigate({ to: "/" })}
          >
            <Gauge aria-hidden="true" size={17} />
            <span>运行控制台</span>
          </Button>
          <Button
            fullWidth
            aria-current={isAudit ? "page" : undefined}
            className="justify-start"
            variant={isAudit ? "secondary" : "ghost"}
            onPress={() => void navigate({ to: "/audit" })}
          >
            <ClipboardCheck aria-hidden="true" size={17} />
            <span>选图审计</span>
          </Button>
          <Button
            fullWidth
            aria-current={isSettings ? "page" : undefined}
            className="justify-start"
            variant={isSettings ? "secondary" : "ghost"}
            onPress={() => void navigate({ to: "/settings" })}
          >
            <ScanSearch aria-hidden="true" size={17} />
            <span>设备与识别</span>
          </Button>
        </nav>

        <div className="hidden flex-1 lg:block" />

        <ThemeButton />
      </aside>

      <div className="min-w-0">
        <header className="border-border bg-surface/85 sticky top-0 z-30 border-b backdrop-blur-xl">
          <div className="mx-auto flex min-h-14 w-full max-w-375 items-center justify-between gap-3 px-4 md:px-5">
            <h1 className="truncate text-lg font-semibold tracking-tight">{pageTitle}</h1>
            <Tooltip delay={350}>
              <Button
                isIconOnly
                aria-label={automationEnabled ? "停止自动选岛" : "开始自动选岛"}
                aria-pressed={automationEnabled}
                isDisabled={!backendConnected || (!automationEnabled && !ready)}
                size="sm"
                variant={automationEnabled ? "secondary" : "ghost"}
                onPress={() => void runAction(automationEnabled ? "stop" : "start")}
              >
                <Power aria-hidden="true" size={16} />
              </Button>
              <Tooltip.Content>
                {automationEnabled ? "停止自动选岛" : "开始自动选岛"}
              </Tooltip.Content>
            </Tooltip>
          </div>
        </header>

        {!backendConnected && (
          <div className="mx-auto w-full max-w-375 px-3 pt-3 md:px-4 lg:px-5">
            <Alert status={connectionStatus === "disconnected" ? "danger" : "warning"} role="alert">
              <Alert.Indicator>
                {connectionStatus === "disconnected" ? (
                  <WifiOff aria-hidden="true" size={18} />
                ) : (
                  <RefreshCw aria-hidden="true" className="animate-spin" size={18} />
                )}
              </Alert.Indicator>
              <Alert.Content>
                <Alert.Title>
                  {connectionStatus === "disconnected"
                    ? "后端连接已中断"
                    : connectionStatus === "recovering"
                      ? "后端正在自动恢复"
                      : "正在连接后端"}
                </Alert.Title>
                <Alert.Description>
                  {connectionError ?? "桌面窗口会保持打开，恢复后自动继续读取状态。"}
                </Alert.Description>
              </Alert.Content>
              <Button
                className="shrink-0"
                size="sm"
                variant="secondary"
                isDisabled={connectionStatus === "connecting"}
                onPress={() => void reconnect()}
              >
                <RefreshCw aria-hidden="true" size={15} />
                重新连接
              </Button>
            </Alert>
          </div>
        )}

        <main className="mx-auto w-full max-w-375 p-3 md:p-4 lg:p-5">
          <Outlet />
        </main>
      </div>

      {notice && (
        <Alert
          status="warning"
          className="fixed right-4 bottom-4 z-50 max-w-md shadow-lg"
          role="status"
        >
          <Alert.Indicator>
            <AlertTriangle size={18} />
          </Alert.Indicator>
          <Alert.Content>
            <Alert.Title>操作未完成</Alert.Title>
            <Alert.Description>{notice}</Alert.Description>
          </Alert.Content>
        </Alert>
      )}
    </div>
  );
}
