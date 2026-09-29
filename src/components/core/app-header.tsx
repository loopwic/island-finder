import { HStack, LayoutHeader } from "@astryxdesign/core/Layout";
import { MobileNavToggle } from "@astryxdesign/core/MobileNav";
import { Text } from "@astryxdesign/core/Text";
import { TopNav } from "@astryxdesign/core/TopNav";
import type { ReactNode } from "react";
import { headerStyles } from "./header.stylex";

export function AppHeader({
  title,
  actions,
}: {
  title: string;
  actions?: ReactNode;
}) {
  return (
    <LayoutHeader padding={0} hasDivider>
      <TopNav
        label="页面导航"
        xstyle={headerStyles.frame}
        startContent={
          <Text as="h1" type="large" weight="semibold">
            {title}
          </Text>
        }
        endContent={
          <HStack gap={2} vAlign="center">
            {actions}
            <MobileNavToggle label="打开主导航" />
          </HStack>
        }
      />
    </LayoutHeader>
  );
}
