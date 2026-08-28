import {
  Button,
  Card,
  Chip,
  Description,
  Drawer,
  EmptyState,
  ErrorMessage,
  Input,
  Label,
  ListBox,
  ProgressBar,
  Radio,
  RadioGroup,
  ScrollShadow,
  Select,
  Slider,
  TextField,
  Tooltip,
} from '@heroui/react';
import { buttonVariants } from '@heroui/styles';
import {
  Activity,
  Camera,
  Check,
  CirclePause,
  CirclePlay,
  ImagePlus,
  Logs,
  Map,
  RefreshCcw,
  Square,
  Trash2,
  UserRound,
} from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { backend } from '../backend/client';
import { useConsole } from '../app/console-context';
import type { RuntimePhase, RuntimeSnapshot, ScreenKind } from '../domain/types';

const phaseLabels: Record<RuntimePhase, string> = {
  idle: '待机',
  fastForwarding: '快速推进',
  enteringName: '输入名字',
  enteringBirthday: '输入生日',
  scanning: '识别地图',
  awaitingDecision: '等待决定',
  restarting: '重开游戏',
  paused: '已暂停',
  error: '异常停止',
};

const screenLabels: Record<ScreenKind, string> = {
  noSignal: '无信号',
  loading: '加载中',
  nameKeyboard: '名字键盘',
  birthdayPicker: '生日选择',
  styleChoice: '初始造型',
  appearanceEditor: '形象编辑',
  choiceDialog: '选项确认',
  mapSelection: '四岛地图',
  homeMenu: 'Switch 主界面',
  accountPicker: '游玩账号',
  dialogue: '对话',
  startupPrompt: '启动提示',
  unknown: '等待识别',
};

const configuredCriteria = [
  { label: '完整双礁石', hard: true },
  { label: '机场与广场轴线协调', hard: true },
  { label: '指定宽浮岛结构', hard: true },
  { label: '狐狸海滩贴近左/右边缘', hard: true },
  { label: '圆润海岸线', hard: true },
  { label: '双入海口且非双南', hard: true },
];

const daysInMonth = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

function formatTime(timestamp: number): string {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(timestamp);
}

function formatElapsed(startedAt: number | null): string {
  if (!startedAt) return '00:00';
  const seconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1_000));
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border-border min-w-16 border-l px-3 text-right first:border-l-0">
      <span className="text-muted block text-xs">{label}</span>
      <strong className="mt-1 block font-mono text-sm font-semibold">{value}</strong>
    </div>
  );
}

function flowProgressColor(phase: RuntimePhase) {
  if (phase === 'error') return 'danger' as const;
  if (phase === 'awaitingDecision') return 'success' as const;
  if (phase === 'paused') return 'warning' as const;
  if (phase === 'idle') return 'default' as const;
  return 'accent' as const;
}

function calculateFlowProgress(runtime: RuntimeSnapshot, stableFrames: number) {
  if (runtime.phase === 'idle') return 0;
  if (runtime.phase === 'restarting') return 5;
  if (runtime.phase === 'awaitingDecision') return 100;
  if (runtime.phase === 'scanning') {
    const scanProgress = Math.min(1, runtime.stableHitCount / Math.max(1, stableFrames));
    return Math.round(90 + scanProgress * 8);
  }
  if (runtime.phase === 'enteringName') return 35;
  if (runtime.phase === 'enteringBirthday') return 55;

  switch (runtime.currentScreen) {
    case 'nameKeyboard': return 30;
    case 'birthdayPicker': return 50;
    case 'styleChoice': return 65;
    case 'appearanceEditor': return 75;
    case 'mapSelection': return 90;
    case 'homeMenu': return 8;
    case 'accountPicker': return 10;
    case 'choiceDialog': return 20;
    case 'dialogue': return 18;
    case 'startupPrompt': return 12;
    default: return 10;
  }
}

function flowStageLabel(progress: number) {
  if (progress >= 100) return '等待决定';
  if (progress >= 90) return '识别地图';
  if (progress >= 70) return '确认形象';
  if (progress >= 45) return '填写生日';
  if (progress >= 25) return '填写名字';
  return '启动游戏';
}

function runtimeProgressMessage(runtime: RuntimeSnapshot) {
  return runtime.lastMessage
    .replace(runtime.currentScreen, screenLabels[runtime.currentScreen])
    .replace(': ', '：');
}

export function CaptureCard({
  settingsView = false,
  panel,
}: {
  settingsView?: boolean;
  panel?: ReactNode;
}) {
  const {
    capture,
    runtime,
    settings,
    active,
    runAction,
  } = useConsole();
  const calculatedProgress = calculateFlowProgress(runtime, settings.stableFrames);
  const [flowProgress, setFlowProgress] = useState({
    runNumber: runtime.runNumber,
    value: calculatedProgress,
  });
  useEffect(() => {
    setFlowProgress((previous) => {
      const reset = runtime.phase === 'idle'
        || runtime.phase === 'restarting'
        || previous.runNumber !== runtime.runNumber;
      const value = reset
        ? calculatedProgress
        : runtime.phase === 'paused' || runtime.phase === 'error'
          ? previous.value
          : Math.max(previous.value, calculatedProgress);
      if (previous.runNumber === runtime.runNumber && previous.value === value) return previous;
      return { runNumber: runtime.runNumber, value };
    });
  }, [calculatedProgress, runtime.phase, runtime.runNumber]);

  return (
    <Card className="min-w-0 overflow-hidden">
      <Card.Header>
        <div className="flex w-full min-w-0 flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 flex-1">
            <div className="text-muted text-xs font-medium">实时视觉</div>
            <Card.Title>{settingsView ? '采集画面' : '实时选岛画面'}</Card.Title>
            <Card.Description className="truncate">
              {settingsView ? '检查采集卡的实时输入画面' : '采集卡实时画面'}
            </Card.Description>
          </div>
          <div className="flex shrink-0 items-stretch self-start sm:self-auto">
            <Metric label="轮次" value={runtime.runNumber || '—'} />
            <Metric label="用时" value={formatElapsed(runtime.startedAt)} />
            <Metric label="阈值" value={`${Math.round(settings.threshold * 100)}%`} />
          </div>
        </div>
      </Card.Header>

      <Card.Content className="p-4 pt-0">
        <div className="min-w-0 space-y-4">
          <div className="min-w-0 space-y-3">
            <div className="border-border relative aspect-video overflow-hidden rounded-2xl border bg-black">
          {capture.connected ? (
            <img className="size-full object-cover" src={backend.streamUrl} alt="采集卡实时画面" />
          ) : (
            <EmptyState className="absolute inset-0 z-10 m-auto max-w-sm text-center">
              <Camera className="mx-auto mb-3 text-muted" size={30} />
              <div className="font-semibold text-foreground">正在等待采集卡</div>
              <div className="mt-1 text-xs text-muted">{capture.error ?? `设备索引 ${settings.captureDeviceIndex}`}</div>
              <Button className="mt-4" size="sm" variant="secondary" onPress={() => void runAction('capture-reconnect')}>
                <RefreshCcw size={14} />重新连接
              </Button>
            </EmptyState>
          )}

          {runtime.phase === 'awaitingDecision' && runtime.selectedCandidate && (
            <Card className="absolute top-1/2 left-1/2 z-30 w-[min(32rem,calc(100%-2rem))] -translate-x-1/2 -translate-y-1/2 shadow-2xl" variant="default">
              <Card.Header>
                <div className="flex w-full items-start gap-3">
                  <div className="grid size-9 shrink-0 place-items-center rounded-full bg-success-soft text-success">
                    <Check size={18} />
                  </div>
                  <div className="min-w-0">
                    <Card.Title>发现候选岛 · 地图 {runtime.selectedCandidate.cardIndex + 1}</Card.Title>
                    <Card.Description>
                      综合得分 {(runtime.selectedCandidate.score * 100).toFixed(1)}%，等待你决定
                    </Card.Description>
                  </div>
                </div>
              </Card.Header>
              <Card.Content>
                <div className="grid w-full grid-cols-2 gap-2">
                  {runtime.selectedCandidate.factors.map((factor) => (
                    <Chip key={factor.key} color={factor.passed ? 'success' : 'danger'} size="sm" variant="soft">
                      <Chip.Label>{factor.label} · {Math.round(factor.score * 100)}</Chip.Label>
                    </Chip>
                  ))}
                </div>
              </Card.Content>
              <Card.Footer>
                <div className="grid w-full grid-cols-2 gap-2">
                  <Button fullWidth variant="primary" onPress={() => void runAction('accept')}>保留这个岛</Button>
                  <Button fullWidth variant="secondary" onPress={() => void runAction('reject')}>放弃并重来</Button>
                </div>
              </Card.Footer>
            </Card>
          )}
            </div>

            <div className="px-1 py-2">
              <div className="flex w-full min-w-0 flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
          <ProgressBar
            aria-label={`本轮自动选岛流程：${phaseLabels[runtime.phase]}，${flowStageLabel(flowProgress.value)}，${flowProgress.value}%`}
            className="min-w-0 flex-1"
            color={flowProgressColor(runtime.phase)}
            size="md"
            value={flowProgress.value}
          >
            <Label className="min-w-0 text-xs">
              <span className="flex min-w-0 items-center">
                <span className="shrink-0 text-sm font-semibold">{phaseLabels[runtime.phase]}</span>
                <span className="border-border text-muted ml-3 shrink-0 border-l pl-3">
                  {flowStageLabel(flowProgress.value)}
                </span>
                <span
                  className="border-border text-muted ml-3 min-w-0 truncate border-l pl-3"
                  title={`${runtimeProgressMessage(runtime)} · 页面识别 ${Math.round(runtime.screenConfidence * 100)}%`}
                >
                  {runtimeProgressMessage(runtime)}
                </span>
              </span>
            </Label>
            <ProgressBar.Output className="text-muted ml-3 text-xs font-mono font-semibold">
              {flowProgress.value}%
            </ProgressBar.Output>
            <ProgressBar.Track className="mt-1.5 rounded-full">
              <ProgressBar.Fill className="rounded-full" />
            </ProgressBar.Track>
          </ProgressBar>

          {!settingsView && (
            <div className="border-border flex shrink-0 flex-wrap justify-end gap-2 sm:border-l sm:pl-4">
              {runtime.phase === 'paused' ? (
                <Button size="sm" variant="secondary" onPress={() => void runAction('resume')}>
                  <CirclePlay size={15} />继续
                </Button>
              ) : active ? (
                <Button size="sm" variant="secondary" onPress={() => void runAction('pause')}>
                  <CirclePause size={15} />暂停
                </Button>
              ) : null}
              <Button size="sm" variant="ghost" isDisabled={runtime.phase === 'idle'} onPress={() => void runAction('stop')}>
                <Square size={13} />停止
              </Button>
            </div>
          )}
              </div>
            </div>
          </div>

          {panel && (
            <aside className="border-border bg-surface-secondary min-w-0 overflow-hidden rounded-2xl border">
              {panel}
            </aside>
          )}
        </div>
      </Card.Content>
    </Card>
  );
}

export function IdentityCard() {
  const {
    settings,
    settingsLoaded,
    settingsSyncState,
    active,
    identityReady,
    updateIdentity,
    updateName,
    updatePinyin,
  } = useConsole();
  const characters = Array.from(settings.identity.name);

  return (
    <section aria-busy={!settingsLoaded} className="space-y-4 p-4 md:p-5">
      <header className="flex items-start gap-3">
        <UserRound aria-hidden="true" className="text-muted mt-0.5 shrink-0" size={18} />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold">岛民资料</h3>
          <p className="text-muted mt-0.5 text-xs">
            {!settingsLoaded
              ? '正在从常驻后端读取'
              : settingsSyncState === 'saving'
                ? '正在保存到常驻后端'
                : settingsSyncState === 'error'
                  ? '保存失败，请检查后端'
                  : '已持久化到常驻后端 · 每轮自动填写'}
          </p>
        </div>
        <Chip color={identityReady ? 'success' : 'warning'} size="sm" variant="soft">
          <Chip.Label>{!settingsLoaded ? '读取中' : identityReady ? '已就绪' : '待补全'}</Chip.Label>
        </Chip>
      </header>
      <div className="space-y-4">
        <TextField
          fullWidth
          isDisabled={active || !settingsLoaded}
          isInvalid={settingsLoaded && characters.length === 0}
          value={settings.identity.name}
          onChange={updateName}
        >
          <Label>中文名字</Label>
          <Input placeholder="例如：小森" />
          <Description>最多 10 个汉字；逐字提供拼音即可</Description>
          {settingsLoaded && characters.length === 0 && <ErrorMessage>请输入岛民名字</ErrorMessage>}
        </TextField>

        {characters.length > 0 && (
          <div className="grid grid-cols-2 gap-3">
            {characters.map((character, index) => (
              <TextField
                fullWidth
                isDisabled={active || !settingsLoaded}
                isInvalid={!settings.identity.namePinyin[index]}
                key={`${character}-${index}`}
                value={settings.identity.namePinyin[index] ?? ''}
                onChange={(value) => updatePinyin(index, value)}
              >
                <Label>「{character}」的拼音</Label>
                <Input placeholder={index === 0 ? 'ming' : 'zao'} spellCheck={false} />
                {!settings.identity.namePinyin[index] && <ErrorMessage>需要拼音</ErrorMessage>}
              </TextField>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <Select
            fullWidth
            aria-label="出生月"
            isDisabled={active || !settingsLoaded}
            selectedKey={String(settings.identity.birthMonth)}
            onSelectionChange={(key) => {
              if (key === null) return;
              const birthMonth = Number(key);
              updateIdentity({
                birthMonth,
                birthDay: Math.min(settings.identity.birthDay, daysInMonth[birthMonth - 1]),
              });
            }}
          >
            <Label>出生月</Label>
            <Select.Trigger><Select.Value /><Select.Indicator /></Select.Trigger>
            <Select.Popover>
              <ListBox>
                {Array.from({ length: 12 }, (_, index) => (
                  <ListBox.Item id={String(index + 1)} key={index + 1} textValue={`${index + 1} 月`}>
                    {index + 1} 月
                    <ListBox.ItemIndicator />
                  </ListBox.Item>
                ))}
              </ListBox>
            </Select.Popover>
          </Select>

          <Select
            fullWidth
            aria-label="出生日"
            isDisabled={active || !settingsLoaded}
            selectedKey={String(settings.identity.birthDay)}
            onSelectionChange={(key) => {
              if (key !== null) updateIdentity({ birthDay: Number(key) });
            }}
          >
            <Label>出生日</Label>
            <Select.Trigger><Select.Value /><Select.Indicator /></Select.Trigger>
            <Select.Popover>
              <ListBox>
                {Array.from({ length: daysInMonth[settings.identity.birthMonth - 1] }, (_, index) => (
                  <ListBox.Item id={String(index + 1)} key={index + 1} textValue={`${index + 1} 日`}>
                    {index + 1} 日
                    <ListBox.ItemIndicator />
                  </ListBox.Item>
                ))}
              </ListBox>
            </Select.Popover>
          </Select>
        </div>

        <RadioGroup
          isDisabled={active || !settingsLoaded}
          value={settings.identity.initialStyle}
          onChange={(initialStyle) => updateIdentity({ initialStyle: initialStyle as 'left' | 'right' })}
        >
          <Label>默认初始造型</Label>
          <div className="grid grid-cols-2 gap-3">
            <Radio value="left">
              <Radio.Content className="border-border bg-surface-secondary flex min-h-12 w-full items-center gap-3 rounded-xl border p-3">
                <Radio.Control><Radio.Indicator /></Radio.Control>
                <Label>左侧造型</Label>
              </Radio.Content>
            </Radio>
            <Radio value="right">
              <Radio.Content className="border-border bg-surface-secondary flex min-h-12 w-full items-center gap-3 rounded-xl border p-3">
                <Radio.Control><Radio.Indicator /></Radio.Control>
                <Label>右侧造型</Label>
              </Radio.Content>
            </Radio>
          </div>
        </RadioGroup>
      </div>
    </section>
  );
}

export function TargetCard() {
  const { settings, active, updateSettings, addTargets, removeTarget } = useConsole();
  const fileInput = useRef<HTMLInputElement>(null);

  return (
    <section className="space-y-4 p-4 md:p-5">
      <header className="flex items-start gap-3">
        <Map aria-hidden="true" className="text-muted mt-0.5 shrink-0" size={18} />
        <div>
          <h3 className="text-sm font-semibold">目标岛条件</h3>
          <p className="text-muted mt-0.5 text-xs">硬条件全部通过才会交给你确认</p>
        </div>
      </header>
      <div className="space-y-5">
        <div className="flex flex-wrap gap-2">
          {configuredCriteria.map((criterion) => (
            <Chip color={criterion.hard ? 'warning' : 'default'} size="sm" variant="soft" key={criterion.label}>
              <Chip.Label>{criterion.label}</Chip.Label>
            </Chip>
          ))}
        </div>

        <Slider
          aria-label="综合条件阈值"
          isDisabled={active}
          minValue={55}
          maxValue={95}
          step={1}
          value={Math.round(settings.threshold * 100)}
          onChange={(value) => {
            const threshold = Array.isArray(value) ? value[0] : value;
            updateSettings({ threshold: threshold / 100 });
          }}
        >
          <div className="mb-2 flex items-center justify-between text-xs">
            <span className="font-medium">综合评分阈值</span>
            <strong className="text-accent">{Math.round(settings.threshold * 100)}%</strong>
          </div>
          <Slider.Track><Slider.Fill /><Slider.Thumb /></Slider.Track>
        </Slider>

        <Button fullWidth variant="secondary" isDisabled={active} onPress={() => fileInput.current?.click()}>
          <ImagePlus size={17} />添加辅助地图样例
        </Button>
        <input
          ref={fileInput}
          hidden
          type="file"
          accept="image/png,image/jpeg,image/webp"
          multiple
          disabled={active}
          onChange={(event) => void addTargets(event.target.files)}
        />

        {settings.targets.length > 0 && (
          <ScrollShadow className="max-h-48 space-y-2 pr-1" hideScrollBar>
            {settings.targets.map((target) => (
              <div className="flex items-center gap-3 rounded-xl border border-border bg-surface-secondary p-2" key={target.id}>
                <img className="size-10 rounded-lg object-cover" src={target.previewUrl} alt="" />
                <span className="min-w-0 flex-1 truncate text-xs font-medium" title={target.name}>{target.name}</span>
                <Tooltip delay={350}>
                  <Button
                    isIconOnly
                    aria-label={`移除 ${target.name}`}
                    size="sm"
                    variant="ghost"
                    isDisabled={active}
                    onPress={() => removeTarget(target.id)}
                  >
                    <Trash2 aria-hidden="true" size={14} />
                  </Button>
                  <Tooltip.Content>移除 {target.name}</Tooltip.Content>
                </Tooltip>
              </div>
            ))}
          </ScrollShadow>
        )}
      </div>
    </section>
  );
}

export function ActivityLogDrawer() {
  const { logs, clearLogs } = useConsole();

  return (
    <Drawer>
      <Tooltip delay={350}>
        <Drawer.Trigger
          aria-label="查看运行记录"
          className={buttonVariants({ isIconOnly: true, size: 'sm', variant: 'ghost' })}
        >
          <Logs aria-hidden="true" size={16} />
        </Drawer.Trigger>
        <Tooltip.Content>查看运行记录</Tooltip.Content>
      </Tooltip>
      <Drawer.Backdrop>
        <Drawer.Content placement="right">
          <Drawer.Dialog>
            <Drawer.Header>
              <div className="min-w-0 flex-1">
                <Drawer.Heading>运行记录</Drawer.Heading>
                <p className="text-muted mt-0.5 text-xs">最近活动 · {logs.length} 条</p>
              </div>
              <Drawer.CloseTrigger aria-label="关闭运行记录" />
            </Drawer.Header>
            <Drawer.Body className="p-0">
              {logs.length === 0 ? (
                <EmptyState className="py-10 text-center text-muted">
                  <Activity className="mx-auto mb-2" size={20} />
                  <div className="text-sm">开始运行后，识别与控制事件会显示在这里</div>
                </EmptyState>
              ) : (
                <div className="divide-border divide-y">
                  {logs.map((entry) => (
                    <div className="flex items-start gap-3 px-4 py-3" key={entry.id}>
                      <span
                        className={`mt-1.5 size-2 shrink-0 rounded-full ${
                          entry.level === 'error'
                            ? 'bg-danger'
                            : entry.level === 'warning'
                              ? 'bg-warning'
                              : entry.level === 'success'
                                ? 'bg-success'
                                : 'bg-muted/50'
                        }`}
                        aria-hidden="true"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm leading-5">{entry.message}</p>
                        <div className="text-muted mt-0.5 flex items-center gap-2 text-xs">
                          <time className="font-mono">{formatTime(entry.at)}</time>
                          <span aria-label={`级别 ${entry.level}`}>{entry.level}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Drawer.Body>
            <Drawer.Footer>
              <Button
                fullWidth
                isDisabled={!logs.length}
                variant="secondary"
                onPress={() => void clearLogs()}
              >
                <Trash2 size={14} />清空运行记录
              </Button>
            </Drawer.Footer>
          </Drawer.Dialog>
        </Drawer.Content>
      </Drawer.Backdrop>
    </Drawer>
  );
}
