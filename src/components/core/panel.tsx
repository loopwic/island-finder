import { Text } from "@astryxdesign/core/Text";
import { Button } from "@astryxdesign/core/Button";
import { Spinner } from "@astryxdesign/core/Spinner";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import * as stylex from "@stylexjs/stylex";
import type { ReactNode } from "react";
import { ui } from "./ui.stylex";
import { StandardDialog } from "./standard-dialog";
import { presentation } from "./presentation.stylex";

export function Panel({
  title,
  description,
  actions,
  icon,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <VStack gap={4} role="region" aria-label={title}>
      <HStack hAlign="between" vAlign="center" gap={3}>
        {icon && (
          <span {...stylex.props(presentation.identity)} aria-hidden="true">
            {icon}
          </span>
        )}
        <VStack gap={1} xstyle={ui.grow}>
          <Text as="h2" type="large" weight="semibold">
            {title}
          </Text>
          {description && (
            <Text size="sm" color="secondary">
              {description}
            </Text>
          )}
        </VStack>
        {actions}
      </HStack>
      <VStack gap={4}>{children}</VStack>
    </VStack>
  );
}
export function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div {...stylex.props(ui.tight)}>
      <Text size="sm" color="secondary">
        {label}
      </Text>
      <Text
        type="display-3"
        weight="semibold"
        hasTabularNumbers
        xstyle={presentation.metricValue}
      >
        {value}
      </Text>
    </div>
  );
}
export function EmptyView({
  title,
  description,
  loading = false,
  action,
}: {
  title: string;
  description?: string;
  loading?: boolean;
  action?: ReactNode;
}) {
  return (
    <EmptyState
      title={title}
      description={description}
      actions={action}
      icon={loading ? <Spinner label={title} /> : undefined}
      xstyle={ui.empty}
    />
  );
}
export function ErrorDialog({
  title = "操作未完成",
  error,
  onClose,
  onRetry,
}: {
  title?: string;
  error: string | null;
  onClose: () => void;
  onRetry?: () => void;
}) {
  return (
    <StandardDialog
      open={Boolean(error)}
      title={title}
      onClose={onClose}
      actions={
        <>
          <Button label="关闭" onClick={onClose} />
          {onRetry && (
            <Button label="重试" variant="primary" onClick={onRetry} />
          )}
        </>
      }
    >
      <Text wordBreak="break-word">{error ?? ""}</Text>
    </StandardDialog>
  );
}
