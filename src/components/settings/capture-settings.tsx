import { Button } from "@astryxdesign/core/Button";
import { Selector } from "@astryxdesign/core/Selector";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useConsole } from "../../app/console-context";
import { backend, type CaptureDevice } from "../../backend/client";
import { CapturePreview } from "../console/capture-preview";
import { Panel, ErrorDialog } from "../core/panel";
import { AppIcon } from "../core/icons";

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
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  const options = useMemo(() => {
    const result = devices.map((device) => ({
      value: String(device.index),
      label: device.name,
      description: `USB ${device.usbLinkMbps ?? "—"} Mbps，${device.transportCodec ?? "UVC"}`,
    }));
    if (!devices.some((device) => device.index === settings.captureDeviceIndex))
      result.unshift({
        value: String(settings.captureDeviceIndex),
        label: settings.captureDeviceName || "未识别的视频设备",
        description: "当前不可用",
      });
    return result;
  }, [devices, settings.captureDeviceIndex, settings.captureDeviceName]);
  return (
    <>
      <Panel
        title="视频采集"
        icon={<AppIcon name="camera" />}
        description="选择连接 Switch 的 UVC 采集卡"
        actions={
          <Token
            label={capture.connected ? "在线" : "离线"}
            color={capture.connected ? "green" : "default"}
          />
        }
      >
        <VStack gap={4}>
          <HStack gap={3} vAlign="end">
            <Selector
              label="视频采集设备"
              isLabelHidden
              width="100%"
              value={String(settings.captureDeviceIndex)}
              options={options}
              isDisabled={
                active || !settingsLoaded || loading || !devices.length
              }
              onChange={(value) => {
                const device = devices.find(
                  (item) => item.index === Number(value),
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
          <HStack hAlign="between" vAlign="center" gap={3}>
            <Text color="secondary">
              {loading ? "正在读取设备" : `${devices.length} 张外接采集卡`}
            </Text>
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
              {capture.error ?? "连接采集卡后刷新设备列表。"}
            </Text>
          )}
        </VStack>
      </Panel>
      <ErrorDialog
        title="设备列表读取失败"
        error={error}
        onClose={() => setError(null)}
        onRetry={() => void refresh()}
      />
    </>
  );
}
