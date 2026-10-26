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

// Figma 对话框/标准对话框: compact 480 for short forms, form 750 for wide content.
const dialogWidths = { compact: "480px", form: "750px" } as const;

export function StandardDialog({
  open,
  title,
  children,
  actions,
  onClose,
  locked = false,
  size = "compact",
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  actions?: ReactNode;
  onClose: () => void;
  locked?: boolean;
  size?: keyof typeof dialogWidths;
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
      width={narrow ? "100%" : `min(${dialogWidths[size]}, calc(100vw - 32px))`}
      maxHeight={narrow ? "100dvh" : "85dvh"}
      padding={0}
      xstyle={ui.dialog}
    >
      <Layout
        padding={0}
        header={
          <DialogHeader
            title={title}
            xstyle={dialogStyles.header}
            onOpenChange={locked ? undefined : onOpenChange}
            hasDivider={false}
          />
        }
        content={
          <LayoutContent padding={0} xstyle={dialogStyles.content}>
            <VStack gap={4}>{children}</VStack>
          </LayoutContent>
        }
        footer={
          actions ? (
            <LayoutFooter padding={0} xstyle={dialogStyles.footer}>
              <HStack hAlign="end" vAlign="center" gap={2} wrap="wrap">
                {actions}
              </HStack>
            </LayoutFooter>
          ) : undefined
        }
      />
    </Dialog>
  );
}
