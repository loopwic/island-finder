import { Button } from "@astryxdesign/core/Button";
import { Text } from "@astryxdesign/core/Text";
import { StatusLabel, type StatusTone } from "../core/status-label";
import { useState } from "react";
import * as stylex from "@stylexjs/stylex";
import { useConsole } from "../../app/console-context";
import { StandardDialog } from "../core/standard-dialog";
import { AppIcon } from "../core/icons";
import { ui } from "../core/ui.stylex";
import type { LogLevel } from "../../domain/types";

const levelLabels: Record<LogLevel, { label: string; tone: StatusTone }> = {
  info: { label: "信息", tone: "neutral" },
  success: { label: "完成", tone: "success" },
  warning: { label: "注意", tone: "warning" },
  error: { label: "错误", tone: "error" },
};

export function ActivityLog() {
  const [open, setOpen] = useState(false);
  const { logs, clearLogs } = useConsole();
  return (
    <>
      <Button
        label="运行记录"
        tooltip="运行记录"
        variant="ghost"
        size="sm"
        isIconOnly
        icon={<AppIcon name="audit" size={14} />}
        onClick={() => setOpen(true)}
      />
      <StandardDialog
        title={`运行记录（${logs.length} 条）`}
        open={open}
        onClose={() => setOpen(false)}
        actions={
          <Button
            label="清空运行记录"
            isDisabled={!logs.length}
            clickAction={clearLogs}
          />
        }
      >
        {!logs.length && (
          <Text color="secondary">
            开始运行后，识别与控制事件会显示在这里。
          </Text>
        )}
        {logs.map((entry) => (
          <div
            {...stylex.props(ui.tight)}
            key={entry.id}
          >
            <Text wordBreak="break-word">{entry.message}</Text>
            <div {...stylex.props(ui.row)}>
              <Text size="sm" color="secondary">
                {new Date(entry.at).toLocaleTimeString("zh-CN", {
                  hour12: false,
                })}
              </Text>
              <StatusLabel
                size="supporting"
                {...(levelLabels[entry.level] ?? levelLabels.info)}
              />
            </div>
          </div>
        ))}
      </StandardDialog>
    </>
  );
}
