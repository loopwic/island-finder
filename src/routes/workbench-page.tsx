import { Alert, Button, Chip, Separator, Tabs } from '@heroui/react';
import { useNavigate } from '@tanstack/react-router';
import { CheckCircle2, Circle, ClipboardCheck, Map, Settings2, UserRound } from 'lucide-react';
import { useConsole } from '../app/console-context';
import { BACKEND_URL } from '../backend/client';
import { ActivityLogDrawer, CaptureCard, IdentityCard, TargetCard } from '../components/console-ui';

function ReadinessPanel() {
  const navigate = useNavigate();
  const { state, capture, controller, settings, settingsLoaded, identityReady, ready } = useConsole();
  const checks = [
    { label: '常驻后端', detail: state ? `v${state.version}` : '未响应', ready: state !== null },
    { label: '视频采集', detail: capture.connected ? `${capture.width}×${capture.height}` : '未就绪', ready: capture.connected },
    {
      label: '岛民资料',
      detail: !settingsLoaded ? '正在读取' : identityReady ? settings.identity.name : '需要补全',
      ready: identityReady,
    },
    {
      label: settings.dryRun ? '演练输入' : '手柄链路',
      detail: !settingsLoaded ? '正在读取' : settings.dryRun ? '按键隔离' : controller.connected ? '已连接' : '未连接',
      ready: settingsLoaded && (settings.dryRun || controller.connected),
    },
  ];

  return (
    <section className="space-y-3 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">启动门禁</h3>
        <Chip color={ready ? 'success' : 'warning'} size="sm" variant="soft">
          <Chip.Label>{!settingsLoaded ? '检查中' : ready ? '已就绪' : '存在阻塞'}</Chip.Label>
        </Chip>
      </div>
      <div className="border-border bg-surface-secondary divide-border overflow-hidden rounded-xl border divide-y">
        {checks.map((check) => (
          <div className="flex min-w-0 items-center gap-2.5 px-3 py-2.5" key={check.label}>
            {check.ready
              ? <CheckCircle2 size={16} className="text-success shrink-0" />
              : <Circle size={16} className="text-muted shrink-0" />}
            <span className="text-sm">{check.label}</span>
            <small className="text-muted ml-auto truncate text-xs">{check.detail}</small>
          </div>
        ))}
      </div>
      {settingsLoaded && !ready && (
        <Button fullWidth size="sm" variant="secondary" onPress={() => void navigate({ to: '/settings' })}>
          <Settings2 size={14} />处理阻塞项
        </Button>
      )}
    </section>
  );
}

function RunPreparationPanel() {
  return (
    <section aria-labelledby="run-preparation-title" className="min-w-0">
      <header className="flex items-center gap-3 p-4">
        <ClipboardCheck aria-hidden="true" className="text-muted shrink-0" size={19} />
        <div className="min-w-0">
          <h2 className="text-sm font-semibold" id="run-preparation-title">运行准备</h2>
          <p className="text-muted mt-0.5 text-xs">启动检查、岛民资料与目标条件</p>
        </div>
        <div className="ml-auto shrink-0">
          <ActivityLogDrawer />
        </div>
      </header>
      <Separator />
      <Tabs className="w-full" defaultSelectedKey="readiness" variant="secondary">
        <Tabs.ListContainer className="px-4 pt-2">
          <Tabs.List aria-label="运行准备分栏" className="w-full">
            <Tabs.Tab className="flex-1" id="readiness">
              <CheckCircle2 size={15} />准备<Tabs.Indicator />
            </Tabs.Tab>
            <Tabs.Tab className="flex-1" id="identity">
              <UserRound size={15} />资料<Tabs.Indicator />
            </Tabs.Tab>
            <Tabs.Tab className="flex-1" id="target">
              <Map size={15} />目标<Tabs.Indicator />
            </Tabs.Tab>
          </Tabs.List>
        </Tabs.ListContainer>
        <Tabs.Panel className="p-0" id="readiness"><ReadinessPanel /></Tabs.Panel>
        <Tabs.Panel className="p-0" id="identity"><IdentityCard /></Tabs.Panel>
        <Tabs.Panel className="p-0" id="target"><TargetCard /></Tabs.Panel>
      </Tabs>
    </section>
  );
}

export function WorkbenchPage() {
  const { state, capture, settings, controller } = useConsole();
  const backendOffline = state === null;
  const inputOffline = !settings.dryRun && !controller.connected;

  return (
    <div className="space-y-4">
      {(backendOffline || !capture.connected || inputOffline) && (
        <Alert status={backendOffline ? 'danger' : 'warning'}>
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Title>{backendOffline ? '后端未响应' : '启动条件未满足'}</Alert.Title>
            <Alert.Description>
              {backendOffline
                ? `${BACKEND_URL} 没有返回运行状态。`
                : !capture.connected
                  ? '视频采集尚未就绪，自动输入保持锁定。'
                  : '真实手柄链路未连接；可先切换为演练模式。'}
            </Alert.Description>
          </Alert.Content>
        </Alert>
      )}

      <section className="min-w-0">
        <CaptureCard panel={<RunPreparationPanel />} />
      </section>
    </div>
  );
}
