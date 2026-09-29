import { Button } from "@astryxdesign/core/Button";
import { Banner } from "@astryxdesign/core/Banner";
import { Card } from "@astryxdesign/core/Card";
import { Grid } from "@astryxdesign/core/Grid";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import * as stylex from "@stylexjs/stylex";
import { useState } from "react";
import { backend, type SelectionAudit } from "../../backend/client";
import { StandardDialog } from "../core/standard-dialog";
import { Metric } from "../core/panel";
import { ui } from "../core/ui.stylex";
import { auditLabels, runLabel, formatAuditTime } from "./audit-display";
import { auditStyles } from "./audit.stylex";
import { presentation } from "../core/presentation.stylex";
import { AppIcon } from "../core/icons";

export function AuditDetail({ record }: { record: SelectionAudit }) {
  const [zoom, setZoom] = useState<{ url: string; label: string } | null>(null);
  const frame = backend.auditImageUrl(record.id, record.frameFile);
  return (
    <VStack gap={6} xstyle={auditStyles.detail}>
      <VStack gap={3}>
        <HStack hAlign="between" vAlign="center" gap={3} wrap="wrap">
          <HStack gap={3} vAlign="center">
            <Text as="h2" type="display-3" weight="semibold">
              {runLabel(record.runNumber)}
            </Text>
            <Token {...(auditLabels[record.status] ?? auditLabels.stopped)} />
          </HStack>
          <Button
            label="查看原始画面"
            icon={<AppIcon name="image" />}
            variant="ghost"
            onClick={() => setZoom({ url: frame, label: "四岛完整画面" })}
          />
        </HStack>
        <HStack gap={4} wrap="wrap">
          <Text size="sm" color="secondary">
            {formatAuditTime(record.createdAt)}
          </Text>
          <Text size="sm" color="secondary">
            规则 {record.candidates[0]?.analysisRevision ?? "旧版"}
          </Text>
          <Text size="sm" color="secondary">
            {record.frameWidth}×{record.frameHeight}
          </Text>
        </HStack>
        <Text xstyle={auditStyles.summary}>{record.summary}</Text>
        {record.decision && record.decision !== record.summary && (
          <Text color="secondary">{record.decision}</Text>
        )}
      </VStack>
      <Grid
        columns={{ minWidth: 120, max: 4 }}
        gap={4}
        xstyle={presentation.metricStrip}
      >
        <Metric
          label="判定阈值"
          value={`${(record.threshold * 100).toFixed(0)}%`}
        />
        <Metric
          label="最高评分"
          value={
            record.bestScore === null
              ? "—"
              : `${(record.bestScore * 100).toFixed(1)}%`
          }
        />
        <Metric
          label="最高地图"
          value={
            record.bestCardIndex === null
              ? "—"
              : `地图 ${record.bestCardIndex + 1}`
          }
        />
        <Metric label="稳定门槛" value={`${record.stableFrames} 帧`} />
      </Grid>
      {record.reanalyzedAt && (
        <Banner
          status="info"
          title="已用当前规则离线重算"
          description={`${formatAuditTime(record.reanalyzedAt)} 重算下方因子；仍保留当时的操作结论，历史版本 ${record.previousAnalyses?.map((item) => item.analysisRevision ?? "旧版").join(" → ") ?? "旧版"} 未被覆盖。`}
        />
      )}
      <Grid columns={{ minWidth: 280, max: 2 }} gap={5} align="start">
        {record.cards.map((card) => {
          const candidate = record.candidates.find(
            (item) => item.cardIndex === card.cardIndex,
          );
          const url = backend.auditImageUrl(record.id, card.file);
          return (
            <Card
              key={card.cardIndex}
              padding={0}
              xstyle={
                record.selectedCardIndex === card.cardIndex
                  ? ui.selected
                  : undefined
              }
            >
              <HStack padding={4} hAlign="between" vAlign="center" gap={3}>
                <VStack gap={1}>
                  <Text as="h3" type="large" weight="semibold">
                    地图 {card.cardIndex + 1}
                  </Text>
                  <Text size="sm" color="secondary">
                    识别可信度{" "}
                    {candidate
                      ? `${Math.round(candidate.analysisConfidence * 100)}%`
                      : "—"}
                  </Text>
                </VStack>
                <Token
                  label={
                    candidate
                      ? `${(candidate.score * 100).toFixed(1)}%`
                      : "无结果"
                  }
                  color={candidate?.hardPass ? "green" : "default"}
                />
              </HStack>
              <div {...stylex.props(auditStyles.preview)}>
                <img
                  {...stylex.props(ui.image, auditStyles.mapImage)}
                  src={url}
                  alt={`${runLabel(record.runNumber)}地图 ${card.cardIndex + 1}`}
                  loading="lazy"
                />
              </div>
              <Button
                label={`放大地图 ${card.cardIndex + 1}`}
                width="100%"
                variant="ghost"
                onClick={() =>
                  setZoom({ url, label: `地图 ${card.cardIndex + 1}` })
                }
              />
              <VStack
                gap={0}
                paddingInline={4}
                paddingBlockEnd={2}
                role="group"
                aria-label={`地图 ${card.cardIndex + 1} 判定依据`}
              >
                {candidate?.factors.map((factor) => (
                  <Collapsible
                    key={factor.key}
                    xstyle={auditStyles.factor}
                    defaultIsOpen={false}
                    trigger={
                      <div {...stylex.props(auditStyles.factorLabel)}>
                        <HStack
                          gap={2}
                          vAlign="center"
                          xstyle={auditStyles.factorName}
                        >
                          <span
                            {...stylex.props(
                              factor.passed
                                ? auditStyles.passed
                                : auditStyles.failed,
                            )}
                          >
                            <AppIcon
                              name={factor.passed ? "success" : "close"}
                              size={16}
                            />
                          </span>
                          <Text>{factor.label}</Text>
                        </HStack>
                        <Text size="sm" color="secondary" hasTabularNumbers>
                          {factor.passed ? "通过" : "未通过"}{" "}
                          {Math.round(factor.score * 100)}%
                        </Text>
                      </div>
                    }
                  >
                    <VStack gap={2} paddingBlockStart={2} paddingBlockEnd={1}>
                      <Text size="sm" color="secondary">
                        {factor.hard ? "硬条件" : "偏好"}：
                        {factor.passed ? "通过" : "未通过"}
                      </Text>
                      <Text color="secondary" xstyle={ui.wrap}>
                        {factor.summary}
                      </Text>
                    </VStack>
                  </Collapsible>
                ))}
              </VStack>
            </Card>
          );
        })}
      </Grid>
      {record.frameSha256 && (
        <Text size="sm" color="secondary">
          同帧证据 #{record.evidenceRevision ?? 1}，原始画面与裁切图已关联。
        </Text>
      )}
      <StandardDialog
        open={Boolean(zoom)}
        title={zoom?.label ?? "地图预览"}
        onClose={() => setZoom(null)}
        actions={
          <Button
            label="打开原始图片"
            href={zoom?.url}
            target="_blank"
            rel="noreferrer"
          />
        }
      >
        {zoom && (
          <img {...stylex.props(ui.image)} src={zoom.url} alt={zoom.label} />
        )}
      </StandardDialog>
    </VStack>
  );
}
