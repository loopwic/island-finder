import { Dialog, DialogHeader } from "@astryxdesign/core/Dialog";
import {
  Layout,
  LayoutContent,
  LayoutFooter,
  HStack,
  VStack,
} from "@astryxdesign/core/Layout";
import { useMediaQuery } from "@astryxdesign/core/hooks";
import { type ReactNode } from "react";
import { ui } from "./ui.stylex";
import { dialogStyles } from "./dialog.stylex";

export function StandardDialog({
  open,
  title,
  children,
  actions,
  onClose,
  locked = false,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  actions?: ReactNode;
  onClose: () => void;
  locked?: boolean;
}) {
  const narrow = useMediaQuery("(max-width: 640px)");
  const onOpenChange = (next: boolean) => {
    if (!next && !locked) onClose();
  };
  return (
    <Dialog
      isOpen={open}
      onOpenChange={onOpenChange}
      purpose={locked ? "required" : "form"}
      variant={narrow ? "fullscreen" : "standard"}
      width={narrow ? "100%" : "38rem"}
      maxHeight={narrow ? "100dvh" : "85dvh"}
      padding={4}
      xstyle={ui.dialog}
    >
      <Layout
        header={
          <DialogHeader
            title={title}
            xstyle={dialogStyles.header}
            onOpenChange={locked ? undefined : onOpenChange}
            hasDivider={false}
          />
        }
        content={
          <LayoutContent>
            <VStack gap={4}>{children}</VStack>
          </LayoutContent>
        }
        footer={
          actions ? (
            <LayoutFooter padding={4} hasDivider>
              <HStack hAlign="end" gap={2} wrap="wrap">
                {actions}
              </HStack>
            </LayoutFooter>
          ) : undefined
        }
      />
    </Dialog>
  );
}
