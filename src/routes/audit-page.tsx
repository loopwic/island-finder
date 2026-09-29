import { Button } from "@astryxdesign/core/Button";
import { Banner } from "@astryxdesign/core/Banner";
import {
  Layout,
  LayoutHeader,
  LayoutContent,
  LayoutPanel,
  HStack,
  VStack,
} from "@astryxdesign/core/Layout";
import { List, ListItem } from "@astryxdesign/core/List";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { useMediaQuery } from "@astryxdesign/core/hooks";
import { useEffect, useState } from "react";
import { useAudits } from "../components/audit/use-audits";
import { AuditDetail } from "../components/audit/audit-detail";
import {
  auditLabels,
  runLabel,
  formatAuditTime,
} from "../components/audit/audit-display";
import { EmptyView, ErrorDialog } from "../components/core/panel";
import { auditStyles } from "../components/audit/audit.stylex";

export function AuditPage() {
  const a = useAudits();
  const narrow = useMediaQuery("(max-width: 1100px)");
  const [dismissed, setDismissed] = useState<string | null>(null);
  const error = a.historyError ?? a.detailError;
  const errorKey = error
    ? `${a.historyError ? "history" : a.selectedId}:${error}`
    : null;
  useEffect(() => {
    if (!error) setDismissed(null);
  }, [error]);
  const retry = a.historyError ? a.retryHistory : a.retryDetail;
  const records = (
    <Layout
      height={narrow ? "auto" : "fill"}
      padding={0}
      header={
        <LayoutHeader hasDivider padding={0}>
          <HStack
            hAlign="between"
            vAlign="center"
            paddingBlock={4}
            paddingInline={5}
          >
            <Text weight="semibold">选图记录</Text>
            <Text color="secondary">
              {a.audits.length} / {a.limit}
            </Text>
          </HStack>
        </LayoutHeader>
      }
      content={
        <LayoutContent
          padding={0}
          xstyle={narrow ? auditStyles.mobileRecords : undefined}
        >
          <List
            density="balanced"
            aria-label="选图记录"
            xstyle={auditStyles.records}
          >
            {a.audits.map((record) => (
              <ListItem
                key={record.id}
                xstyle={auditStyles.row}
                isSelected={record.id === a.selectedId}
                onClick={() => a.setSelectedId(record.id)}
                label={
                  <HStack hAlign="between" vAlign="center" gap={2}>
                    <Text weight="semibold">{runLabel(record.runNumber)}</Text>
                    <Token
                      {...(auditLabels[record.status] ?? auditLabels.stopped)}
                    />
                  </HStack>
                }
                description={
                  <VStack gap={1}>
                    <Text size="sm" color="secondary" maxLines={1}>
                      {record.summary}
                    </Text>
                    <HStack hAlign="between" gap={2}>
                      <Text size="sm" color="secondary">
                        {formatAuditTime(record.createdAt)}
                      </Text>
                      <Text size="sm">
                        {record.bestScore === null
                          ? "无评分"
                          : `${(record.bestScore * 100).toFixed(1)}%`}
                      </Text>
                    </HStack>
                  </VStack>
                }
              />
            ))}
          </List>
        </LayoutContent>
      }
    />
  );
  const detail = a.record ? (
    <AuditDetail key={a.record.id} record={a.record} />
  ) : a.detailLoading ? (
    <EmptyView title="正在读取这轮详情" loading />
  ) : (
    <EmptyView
      title="这轮详情暂不可用"
      action={<Button label="重试详情" onClick={a.retryDetail} />}
    />
  );
  return (
    <>
      {a.historyLoading && !a.audits.length ? (
        <EmptyView title="正在读取选图记录" loading />
      ) : !a.audits.length ? (
        <EmptyView
          title={a.historyError ? "选图记录暂不可用" : "还没有选图记录"}
          description={
            a.historyError
              ? "连接恢复后可以再次读取。"
              : "识别到四岛地图后，会保存原始画面和判定依据。"
          }
          action={
            a.historyError ? (
              <Button label="重新读取" onClick={a.retryHistory} />
            ) : undefined
          }
        />
      ) : (
        <Layout
          height={narrow ? "auto" : "fill"}
          padding={0}
          start={
            narrow ? undefined : (
              <LayoutPanel width={300} padding={0} hasDivider label="选图记录">
                {records}
              </LayoutPanel>
            )
          }
          content={
            <LayoutContent padding={narrow ? 4 : 6}>
              <VStack gap={6}>
                {error && (
                  <Banner
                    status="warning"
                    title="当前显示上一次读取结果"
                    description="连接恢复后会自动刷新，历史记录不会被清除。"
                    endContent={<Button label="重新读取" onClick={retry} />}
                  />
                )}
                {narrow && records}
                {detail}
              </VStack>
            </LayoutContent>
          }
        />
      )}
      <ErrorDialog
        title={a.historyError ? "选图记录读取失败" : "审计详情读取失败"}
        error={errorKey !== dismissed ? error : null}
        onClose={() => setDismissed(errorKey)}
        onRetry={() => {
          setDismissed(errorKey);
          retry();
        }}
      />
    </>
  );
}
