import { Text } from "@astryxdesign/core/Text";
import * as stylex from "@stylexjs/stylex";
import { statusStyles } from "./status-label.stylex";

export type StatusTone = "success" | "warning" | "error" | "running" | "neutral";

export function StatusLabel({
  tone,
  label,
  size = "body",
}: {
  tone: StatusTone;
  label: string;
  size?: "body" | "supporting";
}) {
  return (
    <span {...stylex.props(statusStyles.root)}>
      <span {...stylex.props(statusStyles.mark, statusStyles[tone])} aria-hidden />
      <Text type={size} color={size === "supporting" ? "secondary" : "primary"}>
        {label}
      </Text>
    </span>
  );
}
