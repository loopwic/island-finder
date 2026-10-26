import { Button } from "@astryxdesign/core/Button";
import { Grid } from "@astryxdesign/core/Grid";
import { Heading } from "@astryxdesign/core/Heading";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { Text } from "@astryxdesign/core/Text";
import * as stylex from "@stylexjs/stylex";
import { useState, type ReactNode } from "react";
import {
  backend,
  type AuditCard,
  type SelectionAudit,
} from "../../backend/client";
import type { CandidateMatch } from "../../domain/types";
import { StandardDialog } from "../core/standard-dialog";
import { MetricList } from "../core/panel";
import { StatusLabel } from "../core/status-label";
import { ui } from "../core/ui.stylex";
import { auditLabels, runLabel, formatAuditTime } from "./audit-display";
import { auditStyles } from "./audit.stylex";
import { AppIcon, type AppIconName } from "../core/icons";
import { Notice } from "../core/notice";

type Zoom = { url: string; label: string };

function MetaItem({
  icon,
  label,
  children,
}: {
  icon: AppIconName;
  label: string;
  children: ReactNode;
}) {
  return (
    <HStack gap={1.5} vAlign="center">
      <span {...stylex.props(auditStyles.metaIcon)}>
        <AppIcon name={icon} />
      </span>
      <Text type="supporting" color="secondary" hasTabularNumbers>
        <span {...stylex.props(ui.visuallyHidden)}>{label}：</span>
        {children}
      </Text>
    </HStack>
  );
}

function MapCard({
  record,
  card,
  candidate,
  onZoom,
}: {
  record: SelectionAudit;
  card: AuditCard;
  candidate: CandidateMatch | undefined;
  onZoom: (zoom: Zoom) => void;
}) {
  const url = backend.auditImageUrl(record.id, card.file);
  const title = `地图 ${card.cardIndex + 1}`;
  return (
    <article
      {...stylex.props(
        auditStyles.card,
        record.selectedCardIndex === card.cardIndex && auditStyles.selectedCard,
      )}
      aria-label={title}
    >
      <HStack hAlign="between" vAlign="center" gap={3}>
        <VStack gap={0.5}>
          <Text weight="semibold">{title}</Text>
          <Text type="supporting" color="secondary">
            识别可信度{" "}
            {candidate
              ? `${Math.round(candidate.analysisConfidence * 100)}%`
              : "—"}
          </Text>
        </VStack>
        <StatusLabel
          tone={candidate?.hardPass ? "success" : "neutral"}
          label={candidate ? `${(candidate.score * 100).toFixed(1)}%` : "无结果"}
        />
      </HStack>
      <button
        type="button"
        {...stylex.props(auditStyles.zoomButton)}
        aria-label={`放大${title}`}
        title="点击放大"
        onClick={() => onZoom({ url, label: title })}
      >
        <img
          {...stylex.props(ui.image, auditStyles.mapImage)}
          src={url}
          alt={`${runLabel(record.runNumber)}${title}`}
          loading="lazy"
        />
      </button>
      <VStack gap={0} role="group" aria-label={`${title}判定依据`}>
        {candidate?.factors.map((factor) => (
          <Collapsible
            key={factor.key}
            xstyle={auditStyles.factor}
            defaultIsOpen={false}
            trigger={
              <div {...stylex.props(auditStyles.factorLabel)}>
                <HStack gap={2} vAlign="center" xstyle={auditStyles.factorName}>
                  <span
                    {...stylex.props(
                      factor.passed ? auditStyles.passed : auditStyles.failed,
                    )}
                  >
                    <AppIcon
                      name={factor.passed ? "success" : "close"}
                      size={14}
                    />
                  </span>
                  <Text>{factor.label}</Text>
                </HStack>
                <Text type="supporting" color="secondary" hasTabularNumbers>
                  {factor.passed ? "通过" : "未通过"}{" "}
                  {Math.round(factor.score * 100)}%
                </Text>
              </div>
            }
          >
            <VStack gap={1} paddingBlockStart={1} paddingBlockEnd={1}>
              <Text type="supporting" color="secondary">
                {factor.hard ? "硬条件" : "偏好"}
              </Text>
              <Text color="secondary" xstyle={ui.wrap}>
                {factor.summary}
              </Text>
            </VStack>
          </Collapsible>
        ))}
      </VStack>
    </article>
  );
}

export function AuditDetail({ record }: { record: SelectionAudit }) {
  const [zoom, setZoom] = useState<Zoom | null>(null);
  const frame = backend.auditImageUrl(record.id, record.frameFile);
  return (
    <VStack gap={8} xstyle={auditStyles.detail}>
      <VStack as="header" gap={3}>
        <HStack hAlign="between" vAlign="start" gap={4} wrap="wrap">
          <VStack gap={2}>
            <HStack gap={2} vAlign="center">
              <Text type="supporting" color="secondary">
                选图审计
              </Text>
              <StatusLabel
                size="supporting"
                {...(auditLabels[record.status] ?? auditLabels.stopped)}
              />
            </HStack>
            <Heading level={1}>{runLabel(record.runNumber)}</Heading>
            <HStack gap={4} wrap="wrap">
              <MetaItem icon="clock" label="记录时间">
                {formatAuditTime(record.createdAt)}
              </MetaItem>
              <MetaItem icon="revision" label="判定规则版本">
                {record.candidates[0]?.analysisRevision ?? "旧版"}
              </MetaItem>
              <MetaItem icon="resolution" label="画面分辨率">
                {record.frameWidth}×{record.frameHeight}
              </MetaItem>
            </HStack>
          </VStack>
          <Button
            label="查看原始画面"
            size="sm"
            variant="ghost"
            icon={<AppIcon name="image" size={14} />}
            onClick={() => setZoom({ url: frame, label: "四岛完整画面" })}
          />
        </HStack>
        <Text>{record.summary}</Text>
        {record.decision && record.decision !== record.summary && (
          <Text color="secondary">{record.decision}</Text>
        )}
      </VStack>
      <MetricList
        items={[
          {
            label: "判定阈值",
            value: `${(record.threshold * 100).toFixed(0)}%`,
          },
          {
            label: "最高评分",
            value:
              record.bestScore === null
                ? "—"
                : `${(record.bestScore * 100).toFixed(1)}%`,
          },
          {
            label: "最高地图",
            value:
              record.bestCardIndex === null
                ? "—"
                : `地图 ${record.bestCardIndex + 1}`,
          },
          { label: "稳定门槛", value: `${record.stableFrames} 帧` },
        ]}
      />
      {record.reanalyzedAt && (
        <Notice
          status="info"
          title="已用当前规则离线重算"
          description={`${formatAuditTime(record.reanalyzedAt)} 重算下方因子；仍保留当时的操作结论，历史版本 ${record.previousAnalyses?.map((item) => item.analysisRevision ?? "旧版").join(" → ") ?? "旧版"} 未被覆盖。`}
        />
      )}
      <Grid columns={{ minWidth: 280, max: 2 }} gap={4} align="start">
        {record.cards.map((card) => (
          <MapCard
            key={card.cardIndex}
            record={record}
            card={card}
            candidate={record.candidates.find(
              (item) => item.cardIndex === card.cardIndex,
            )}
            onZoom={setZoom}
          />
        ))}
      </Grid>
      <StandardDialog
        size="form"
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
