import { HStack, LayoutHeader } from "@astryxdesign/core/Layout";
import { MobileNavToggle } from "@astryxdesign/core/MobileNav";
import { Text } from "@astryxdesign/core/Text";
import { TopNav } from "@astryxdesign/core/TopNav";
import * as stylex from "@stylexjs/stylex";
import type { ReactNode } from "react";
import { AppIcon, type AppIconName } from "./icons";
import { headerStyles } from "./header.stylex";
import { shellStyles } from "../../app/shell.stylex";

export function AppHeader({
  title,
  icon,
  actions,
}: {
  title: string;
  icon: AppIconName;
  actions?: ReactNode;
}) {
  return (
    <LayoutHeader padding={0} hasDivider xstyle={shellStyles.headerDivider}>
      <TopNav
        label="页面导航"
        xstyle={headerStyles.frame}
        startContent={
          <div {...stylex.props(headerStyles.identity)}>
            <span {...stylex.props(headerStyles.icon)} aria-hidden>
              <AppIcon name={icon} />
            </span>
            <Text as="h1" weight="medium">
              {title}
            </Text>
          </div>
        }
        endContent={
          <HStack gap={1} vAlign="center">
            {actions}
            <MobileNavToggle label="打开主导航" />
          </HStack>
        }
      />
    </LayoutHeader>
  );
}
