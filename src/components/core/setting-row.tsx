import { VStack } from "@astryxdesign/core/Layout";
import { Text } from "@astryxdesign/core/Text";
import * as stylex from "@stylexjs/stylex";
import type { ReactNode } from "react";
import { presentation } from "./presentation.stylex";

export function SettingRow({
  label,
  description,
  children,
}: {
  label: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <div
      {...stylex.props(presentation.settingRow)}
      role="group"
      aria-label={label}
    >
      <VStack gap={0.5}>
        <Text>{label}</Text>
        <Text type="supporting" color="secondary">
          {description}
        </Text>
      </VStack>
      <div {...stylex.props(presentation.settingControl)}>{children}</div>
    </div>
  );
}
