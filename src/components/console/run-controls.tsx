import { Button } from "@astryxdesign/core/Button";
import { useConsole } from "../../app/console-context";
import { AppIcon } from "../core/icons";
import { ActivityLog } from "./activity-log";

/** Run commands for the console, kept together in the app header. */
export function RunControls() {
  const { runtime, active, connectionStatus, startBlocker, runAction } =
    useConsole();
  const running = runtime.phase !== "idle" && runtime.phase !== "error";
  const connected = connectionStatus === "connected";
  return (
    <>
      <ActivityLog />
      {runtime.phase === "paused" ? (
        <Button
          label="继续"
          size="sm"
          icon={<AppIcon name="play" size={14} />}
          isDisabled={!connected}
          clickAction={() => runAction("resume")}
        />
      ) : (
        active && (
          <Button
            label="暂停"
            size="sm"
            icon={<AppIcon name="pause" size={14} />}
            isDisabled={!connected}
            clickAction={() => runAction("pause")}
          />
        )
      )}
      <Button
        label={running ? "停止选岛" : "开始选岛"}
        size="sm"
        variant={running ? "secondary" : "primary"}
        icon={<AppIcon name={running ? "stop" : "play"} size={14} />}
        isDisabled={!connected || (!running && startBlocker !== null)}
        tooltip={!running ? (startBlocker ?? undefined) : undefined}
        clickAction={() => runAction(running ? "stop" : "start")}
      />
    </>
  );
}
