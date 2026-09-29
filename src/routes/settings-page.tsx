import { Layout, LayoutContent, VStack } from "@astryxdesign/core/Layout";
import { Tab, TabList } from "@astryxdesign/core/TabList";
import { Divider } from "@astryxdesign/core/Divider";
import { useState } from "react";
import { CaptureSettings } from "../components/settings/capture-settings";
import { ControllerSettings } from "../components/settings/controller-settings";
import { RecognitionSettings } from "../components/settings/recognition-settings";
import { FirmwarePanel } from "../components/firmware/firmware-panel";
import { AppIcon } from "../components/core/icons";
import { settingsStyles } from "../components/settings/settings.stylex";

export function SettingsPage() {
  const [tab, setTab] = useState("devices");
  return (
    <Layout
      height="auto"
      contentWidth={880}
      padding={8}
      content={
        <LayoutContent>
          <VStack gap={8}>
            <TabList
              value={tab}
              onChange={setTab}
              aria-label="设备与识别设置"
              role="tablist"
              layout="hug"
              size="lg"
              hasDivider
            >
              <Tab
                xstyle={settingsStyles.tab}
                value="devices"
                label="设备连接"
                panelId="settings-panel"
                icon={<AppIcon name="camera" />}
              />
              <Tab
                xstyle={settingsStyles.tab}
                value="recognition"
                label="识别设置"
                panelId="settings-panel"
                icon={<AppIcon name="settings" />}
              />
              <Tab
                xstyle={settingsStyles.tab}
                value="firmware"
                label="开发板固件"
                panelId="settings-panel"
                icon={<AppIcon name="cpu" />}
              />
            </TabList>
            <div
              id="settings-panel"
              role="tabpanel"
              aria-label={
                tab === "devices"
                  ? "设备连接"
                  : tab === "firmware"
                    ? "开发板固件"
                    : "识别设置"
              }
            >
              {tab === "devices" ? (
                <VStack gap={8}>
                  <CaptureSettings />
                  <Divider />
                  <ControllerSettings />
                </VStack>
              ) : tab === "firmware" ? (
                <FirmwarePanel />
              ) : (
                <RecognitionSettings />
              )}
            </div>
          </VStack>
        </LayoutContent>
      }
    />
  );
}
