import { Button } from "@astryxdesign/core/Button";
import { Selector } from "@astryxdesign/core/Selector";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Text } from "@astryxdesign/core/Text";
import { StatusLabel } from "../core/status-label";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useConsole } from "../../app/console-context";
import { backend, type CaptureDevice } from "../../backend/client";
import { CapturePreview } from "../console/capture-preview";
import { Section, ErrorDialog } from "../core/panel";
import { AppIcon } from "../core/icons";
import { errorMessage } from "../../domain/errors";

// Devices are bound by their stable hardware ID; the OS index can change
// between launches and is only a fallback for devices that report no ID.
const deviceKey = (device: { id?: string; index: number }) =>
  device.id || `index:${device.index}`;

export function CaptureSettings() {
  const { capture, settings, settingsLoaded, active, updateSettings } =
    useConsole();
  const [devices, setDevices] = useState<CaptureDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDevices((await backend.captureDevices()).devices);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  const selectedKey = deviceKey({
    id: settings.captureDeviceId,
    index: settings.captureDeviceIndex,
  });
  const options = useMemo(() => {
    const result = devices.map((device) => ({
      value: deviceKey(device),
      label: device.name,
      description: `USB ${device.usbLinkMbps ?? "—"} Mbps，${device.transportCodec ?? "UVC"}`,
    }));
    if (!devices.some((device) => deviceKey(device) === selectedKey))
      result.unshift({
        value: selectedKey,
        label: settings.captureDeviceName || "未识别的视频设备",
        description: "当前不可用",
      });
    return result;
  }, [devices, selectedKey, settings.captureDeviceName]);
  return (
    <>
      <Section
        title="视频采集"
        description="选择连接 Switch 的 UVC 采集卡"
        actions={
          <StatusLabel
            tone={capture.connected ? "success" : "neutral"}
            label={capture.connected ? "在线" : "离线"}
          />
        }
      >
        <VStack gap={3}>
          <HStack gap={2} vAlign="end">
            <Selector
              label="视频采集设备"
              isLabelHidden
              width="100%"
              value={selectedKey}
              options={options}
              isDisabled={
                active || !settingsLoaded || loading || !devices.length
              }
              onChange={(value) => {
                const device = devices.find(
                  (item) => deviceKey(item) === value,
                );
                if (device)
                  updateSettings({
                    captureDeviceIndex: device.index,
                    captureDeviceId: device.id,
                    captureDeviceName: device.name,
                  });
              }}
            />
            <Button
              label="刷新设备"
              isIconOnly
              icon={<AppIcon name="refresh" />}
              isLoading={loading}
              clickAction={refresh}
            />
          </HStack>
          {capture.connected ? (
            <Collapsible
              defaultIsOpen={false}
              trigger={<Text color="secondary">查看采集画面</Text>}
            >
              <VStack paddingBlockStart={4}>
                <CapturePreview />
              </VStack>
            </Collapsible>
          ) : (
            <Text color="secondary">
              {loading
                ? "正在读取设备"
                : !devices.length
                  ? "未检测到外接采集卡，请检查 USB 连接后刷新"
                  : (capture.error ?? "采集卡尚未输出画面")}
            </Text>
          )}
        </VStack>
      </Section>
      <ErrorDialog
        title="设备列表读取失败"
        error={error}
        onClose={() => setError(null)}
        onRetry={() => void refresh()}
      />
    </>
  );
}
