import { Text } from "@astryxdesign/core/Text";
import { Button } from "@astryxdesign/core/Button";
import { Heading } from "@astryxdesign/core/Heading";
import { Spinner } from "@astryxdesign/core/Spinner";
import { Grid } from "@astryxdesign/core/Grid";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import * as stylex from "@stylexjs/stylex";
import type { ReactNode } from "react";
import { ui } from "./ui.stylex";
import { StandardDialog } from "./standard-dialog";

/** A titled block on the canvas. The heading stays small; content leads. */
export function Section({
  title,
  description,
  actions,
  isInset = false,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  /** Align the title with property rows, which carry a 12px inset. */
  isInset?: boolean;
  children: ReactNode;
}) {
  return (
    <section {...stylex.props(ui.section)} aria-label={title}>
      <HStack
        hAlign="between"
        vAlign="center"
        gap={3}
        xstyle={isInset ? ui.sectionInset : undefined}
      >
        <VStack gap={0.5} xstyle={ui.grow}>
          <Heading level={5} accessibilityLevel={2} color="secondary">
            {title}
          </Heading>
          {description && (
            <Text type="supporting" color="secondary">
              {description}
            </Text>
          )}
        </VStack>
        {actions}
      </HStack>
      {children}
    </section>
  );
}

export type MetricItem = { label: string; value: ReactNode };

export function MetricList({ items }: { items: MetricItem[] }) {
  return (
    <dl {...stylex.props(ui.bare)}>
      <Grid columnGap={8} rowGap={4} columns={{ minWidth: 112, repeat: "fit" }}>
        {items.map((item) => (
          <VStack key={item.label} gap={1}>
            <dt {...stylex.props(ui.bare)}>
              <Text type="supporting" color="secondary" display="block">
                {item.label}
              </Text>
            </dt>
            <dd {...stylex.props(ui.bare)}>
              <Text as="div" size="base" weight="semibold" hasTabularNumbers>
                {item.value}
              </Text>
            </dd>
          </VStack>
        ))}
      </Grid>
    </dl>
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
        onRetry && <Button label="重试" variant="primary" onClick={onRetry} />
      }
    >
      <Text wordBreak="break-word">{error ?? ""}</Text>
    </StandardDialog>
  );
}
