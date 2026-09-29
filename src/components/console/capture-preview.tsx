import { Button } from "@astryxdesign/core/Button";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import * as stylex from "@stylexjs/stylex";
import { useConsole } from "../../app/console-context";
import { backend } from "../../backend/client";
import { AppIcon } from "../core/icons";
import { ui } from "../core/ui.stylex";
import { presentation } from "../core/presentation.stylex";

export function CapturePreview() {
  const { capture, settings, runAction } = useConsole();
  return (
    <div {...stylex.props(ui.preview, !capture.connected && ui.previewEmpty)}>
      {capture.connected ? (
        <img
          {...stylex.props(ui.previewImage)}
          src={backend.streamUrl}
          alt="采集卡实时画面"
        />
      ) : (
        <EmptyState
          title="等待采集画面"
          description={
            capture.error ?? `设备索引 ${settings.captureDeviceIndex}`
          }
          icon={
            <span {...stylex.props(presentation.identity)}>
              <AppIcon name="camera" size={24} />
            </span>
          }
          actions={
            <Button
              label="重新连接采集"
              icon={<AppIcon name="refresh" />}
              clickAction={() => runAction("capture-reconnect")}
            />
          }
        />
      )}
    </div>
  );
}
