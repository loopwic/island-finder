import { VStack } from "@astryxdesign/core/Layout";
import * as stylex from "@stylexjs/stylex";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { CaptureSettings } from "../components/settings/capture-settings";
import { ControllerSettings } from "../components/settings/controller-settings";
import { RecognitionSettings } from "../components/settings/recognition-settings";
import { FirmwarePanel } from "../components/firmware/firmware-panel";
import { PageContent } from "../components/core/page";
import { pageStyles } from "../components/core/page.stylex";
import { PillTabList } from "../components/core/pill-tab-list";
import { settingsTabs } from "./settings-tabs";

const tabItems = settingsTabs.map((item) => ({
  value: item.value,
  label: item.label,
  tabId: `settings-tab-${item.value}`,
  panelId: "settings-panel",
}));

export function SettingsPage() {
  const navigate = useNavigate();
  const { tab = "devices" } = useSearch({ from: "/settings" });
  return (
    <>
      <div {...stylex.props(pageStyles.tabRow)}>
        <PillTabList
          label="设备与识别设置"
          items={tabItems}
          value={tab}
          onChange={(next) =>
            void navigate({
              to: "/settings",
              search: { tab: next },
              replace: true,
            })
          }
        />
      </div>
      <PageContent inset="reading" maxWidth="45rem">
        <div
          id="settings-panel"
          role="tabpanel"
          aria-labelledby={`settings-tab-${tab}`}
        >
          {tab === "devices" ? (
            <VStack gap={8}>
              <CaptureSettings />
              <ControllerSettings />
            </VStack>
          ) : tab === "firmware" ? (
            <FirmwarePanel />
          ) : (
            <RecognitionSettings />
          )}
        </div>
      </PageContent>
    </>
  );
}
