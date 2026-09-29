import { Button } from "@astryxdesign/core/Button";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { useState } from "react";
import * as stylex from "@stylexjs/stylex";
import { useConsole } from "../../app/console-context";
import { StandardDialog } from "../core/standard-dialog";
import { AppIcon } from "../core/icons";
import { ui } from "../core/ui.stylex";
export function ActivityLog() {
  const [open, setOpen] = useState(false);
  const { logs, clearLogs } = useConsole();
  return (
    <>
      <Button
        label="运行记录"
        variant="ghost"
        isIconOnly
        icon={<AppIcon name="audit" />}
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
            {...stylex.props(ui.tight, ui.padding, ui.divider)}
            key={entry.id}
          >
            <Text wordBreak="break-word">{entry.message}</Text>
            <div {...stylex.props(ui.row)}>
              <Text size="sm" color="secondary">
                {new Date(entry.at).toLocaleTimeString("zh-CN", {
                  hour12: false,
                })}
              </Text>
              <Token
                label={entry.level}
                color={
                  entry.level === "error"
                    ? "red"
                    : entry.level === "warning"
                      ? "yellow"
                      : "default"
                }
              />
            </div>
          </div>
        ))}
      </StandardDialog>
    </>
  );
}
