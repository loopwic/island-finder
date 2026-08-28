import {
  Button,
  Card,
  Chip,
  Description,
  Label,
  ListBox,
  NumberField,
  Select,
  Switch,
  Tabs,
  Tooltip,
} from '@heroui/react';
import {
  Camera,
  Gamepad2,
  Gauge,
  RefreshCcw,
  ServerCog,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useConsole } from '../app/console-context';
import { backend, type CaptureDevice } from '../backend/client';
import { CaptureCard } from '../components/console-ui';

function IntegerField({
  label,
  description,
  value,
  minValue,
  maxValue,
  step = 1,
  disabled,
  onChange,
}: {
  label: string;
  description?: string;
  value: number;
  minValue: number;
  maxValue: number;
  step?: number;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <NumberField
      fullWidth
      isDisabled={disabled}
      value={value}
      minValue={minValue}
      maxValue={maxValue}
      step={step}
      onChange={onChange}
    >
      <Label>{label}</Label>
      <NumberField.Group>
        <NumberField.DecrementButton />
        <NumberField.Input />
        <NumberField.IncrementButton />
      </NumberField.Group>
      {description && <Description>{description}</Description>}
    </NumberField>
  );
}

function SettingSwitch({
  label,
  description,
  selected,
  disabled,
  onChange,
}: {
  label: string;
  description: string;
  selected: boolean;
  disabled?: boolean;
  onChange: (selected: boolean) => void;
}) {
  return (
    <Switch className="w-full" isSelected={selected} isDisabled={disabled} onChange={onChange}>
      <Switch.Content className="flex min-h-16 w-full items-center gap-3 px-3 py-2.5">
        <div className="min-w-0 flex-1">
          <div className="text-foreground text-sm font-medium">{label}</div>
          <div className="text-muted mt-0.5 text-xs leading-5">{description}</div>
        </div>
        <Switch.Control><Switch.Thumb /></Switch.Control>
      </Switch.Content>
    </Switch>
  );
}

export function SettingsPage() {
  const [captureDevices, setCaptureDevices] = useState<CaptureDevice[]>([]);
  const [loadingDevices, setLoadingDevices] = useState(true);
  const [deviceError, setDeviceError] = useState<string | null>(null);
  const {
    capture,
    controller,
    settings,
    active,
    updateSettings,
    runAction,
  } = useConsole();

  const refreshDevices = useCallback(async () => {
    setLoadingDevices(true);
    setDeviceError(null);
    try {
      const response = await backend.captureDevices();
      setCaptureDevices(response.devices);
    } catch (error) {
      setDeviceError(error instanceof Error ? error.message : String(error));
    } finally {
      setLoadingDevices(false);
    }
  }, []);

  useEffect(() => {
    void refreshDevices();
  }, [refreshDevices]);

  const deviceOptions = useMemo(() => {
    if (captureDevices.some((device) => device.index === settings.captureDeviceIndex)) {
      return captureDevices.map((device) => ({ ...device, unavailable: false }));
    }
    return [
      {
        index: settings.captureDeviceIndex,
        id: settings.captureDeviceId,
        name: settings.captureDeviceName || '未识别的视频设备',
        modelId: '',
        preferred: false,
        usbLinkMbps: null,
        transportCodec: null,
        unavailable: true,
      },
      ...captureDevices.map((device) => ({ ...device, unavailable: false })),
    ];
  }, [captureDevices, settings.captureDeviceId, settings.captureDeviceIndex, settings.captureDeviceName]);

  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] items-start gap-5 xl:grid-cols-[minmax(0,1fr)_26rem]">
      <section className="min-w-0 xl:sticky xl:top-20">
        <CaptureCard settingsView />
      </section>

      <aside className="min-w-0 space-y-4">
        <Tabs className="w-full" defaultSelectedKey="devices" variant="secondary">
          <Tabs.ListContainer>
            <Tabs.List aria-label="设备与识别设置" className="w-full">
              <Tabs.Tab className="flex-1" id="devices">
                <Gamepad2 size={15} />设备连接<Tabs.Indicator />
              </Tabs.Tab>
              <Tabs.Tab className="flex-1" id="recognition">
                <Gauge size={15} />识别性能<Tabs.Indicator />
              </Tabs.Tab>
            </Tabs.List>
          </Tabs.ListContainer>

          <Tabs.Panel className="p-0" id="devices">
            <Card className="min-w-0">
          <Card.Header>
            <div className="flex w-full items-start gap-3">
              <ServerCog aria-hidden="true" className="text-muted mt-0.5 shrink-0" size={19} />
              <div className="min-w-0">
                <Card.Title>采集与手柄</Card.Title>
                <Card.Description>本机设备连接与真实输入链路</Card.Description>
              </div>
            </div>
          </Card.Header>
          <Card.Content className="space-y-5">
            <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-end gap-2">
              <Select
                fullWidth
                className="min-w-0"
                aria-label="视频采集设备"
                isDisabled={active || loadingDevices || captureDevices.length === 0}
                selectedKey={String(settings.captureDeviceIndex)}
                onSelectionChange={(key) => {
                  if (key === null) return;
                  const selected = captureDevices.find((device) => device.index === Number(key));
                  if (!selected) return;
                  updateSettings({
                    captureDeviceIndex: selected.index,
                    captureDeviceId: selected.id,
                    captureDeviceName: selected.name,
                  });
                }}
              >
                <Label>视频采集设备</Label>
                <Select.Trigger><Select.Value /><Select.Indicator /></Select.Trigger>
                <Select.Popover>
                  <ListBox>
                    {deviceOptions.map((device) => (
                      <ListBox.Item
                        id={String(device.index)}
                        isDisabled={device.unavailable}
                        key={`${device.index}-${device.id || device.name}`}
                        textValue={device.name}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="truncate font-medium">{device.name}</span>
                            {device.preferred && (
                              <Chip color="success" size="sm" variant="soft"><Chip.Label>推荐</Chip.Label></Chip>
                            )}
                            {device.unavailable && (
                              <Chip size="sm" variant="soft"><Chip.Label>当前不可用</Chip.Label></Chip>
                            )}
                          </div>
                          <div className="text-muted mt-0.5 text-xs">
                            按硬件 ID 绑定
                            {device.usbLinkMbps ? ` · USB ${device.usbLinkMbps} Mbps` : ''}
                            {device.transportCodec ? ` · ${device.transportCodec}` : ''}
                          </div>
                        </div>
                        <ListBox.ItemIndicator />
                      </ListBox.Item>
                    ))}
                  </ListBox>
                </Select.Popover>
                <Description>
                  {loadingDevices
                    ? '正在读取视频设备…'
                    : deviceError
                      ? `设备枚举失败：${deviceError}`
                      : `已发现 ${captureDevices.length} 张外接 UVC 采集卡；内置摄像头已排除`}
                </Description>
              </Select>
              <Tooltip delay={350}>
                <Button
                  isIconOnly
                  aria-label="刷新视频设备列表"
                  variant="secondary"
                  isDisabled={loadingDevices}
                  onPress={() => void refreshDevices()}
                >
                  <RefreshCcw aria-hidden="true" size={17} />
                </Button>
                <Tooltip.Content>刷新视频设备列表</Tooltip.Content>
              </Tooltip>
            </div>

            <div className="border-border bg-surface-secondary divide-border overflow-hidden rounded-xl border divide-y">
              <div className="flex min-h-16 flex-wrap items-center gap-3 px-3 py-2.5">
                <Camera className="text-muted shrink-0" size={18} />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{capture.deviceName || settings.captureDeviceName || '采集画面'}</div>
                  <div className="text-muted truncate text-xs">
                    {capture.connected
                      ? `${capture.width}×${capture.height} · ${capture.fps.toFixed(1)} fps · ${
                          capture.captureBackend === 'opencv-directshow'
                            ? 'DirectShow 采集'
                            : capture.captureBackend === 'native-avfoundation-jpeg-pipe'
                              ? 'AVFoundation 原生采集'
                              : 'OpenCV 采集'
                        }`
                      : capture.error ?? '等待采集卡'}
                  </div>
                </div>
                <Chip color={capture.connected ? 'success' : 'default'} size="sm" variant="soft">
                  <Chip.Label>{capture.connected ? '在线' : '离线'}</Chip.Label>
                </Chip>
                <Button size="sm" variant="ghost" isDisabled={active} onPress={() => void runAction('capture-reconnect')}>
                  重新打开
                </Button>
              </div>

              <div className="flex min-h-16 flex-wrap items-center gap-3 px-3 py-2.5">
                <Gamepad2 className="text-muted shrink-0" size={19} />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">模拟 Pro Controller</div>
                  <div className="text-muted truncate text-xs">{controller.message}</div>
                </div>
                <Chip color={controller.connected ? 'success' : 'default'} size="sm" variant="soft">
                  <Chip.Label>{controller.connected ? '已连接' : '未连接'}</Chip.Label>
                </Chip>
                <Button
                  size="sm"
                  variant="ghost"
                  onPress={() => void runAction(controller.active ? 'controller-disconnect' : 'controller-connect')}
                >
                  {controller.active ? '停止配对' : '启动配对'}
                </Button>
              </div>
            </div>

            <div className="border-border bg-surface-secondary divide-border overflow-hidden rounded-xl border divide-y">
              <SettingSwitch
                label="自动连接手柄"
                description="后端启动后自动寻找已配置的手柄服务"
                selected={settings.autoConnectController}
                disabled={active}
                onChange={(autoConnectController) => updateSettings({ autoConnectController })}
              />
              <SettingSwitch
                label="演练模式"
                description="执行识别与状态机，但不向 Switch 发送真实按键"
                selected={settings.dryRun}
                disabled={active}
                onChange={(dryRun) => updateSettings({ dryRun })}
              />
            </div>
          </Card.Content>
            </Card>
          </Tabs.Panel>

          <Tabs.Panel className="p-0" id="recognition">
            <Card className="min-w-0">
          <Card.Header>
            <div className="flex w-full items-start gap-3">
              <Gauge aria-hidden="true" className="text-muted mt-0.5 shrink-0" size={19} />
              <div className="min-w-0">
                <Card.Title>识别性能</Card.Title>
                <Card.Description>采集节奏与稳定判定</Card.Description>
              </div>
            </div>
          </Card.Header>
          <Card.Content className="space-y-5">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
              <IntegerField
                label="采集/预览 FPS"
                description="后端 MJPEG 预览帧率"
                value={settings.captureFps}
                minValue={3}
                maxValue={30}
                disabled={active}
                onChange={(captureFps) => updateSettings({ captureFps })}
              />
              <IntegerField
                label="扫描间隔"
                description="毫秒"
                value={settings.scanIntervalMs}
                minValue={100}
                maxValue={5_000}
                step={10}
                disabled={active}
                onChange={(scanIntervalMs) => updateSettings({ scanIntervalMs })}
              />
            </div>
            <IntegerField
              label="连续稳定帧"
              description="相同结果达到此数量后才允许推进"
              value={settings.stableFrames}
              minValue={1}
              maxValue={12}
              disabled={active}
              onChange={(stableFrames) => updateSettings({ stableFrames })}
            />
            <div className="border-border bg-surface-secondary overflow-hidden rounded-xl border">
              <SettingSwitch
                label="自动拒绝不合格地图"
                description="候选地图未通过全部硬条件时自动重开"
                selected={settings.autoReject}
                disabled={active}
                onChange={(autoReject) => updateSettings({ autoReject })}
              />
            </div>
          </Card.Content>
            </Card>
          </Tabs.Panel>
        </Tabs>
      </aside>
    </div>
  );
}
