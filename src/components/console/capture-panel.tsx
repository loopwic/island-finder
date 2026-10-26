import { Button } from "@astryxdesign/core/Button";
import { HStack } from "@astryxdesign/core/Layout";
import { ProgressBar } from "@astryxdesign/core/ProgressBar";
import { Text } from "@astryxdesign/core/Text";
import * as stylex from "@stylexjs/stylex";
import { useEffect, useState } from "react";
import { useConsole } from "../../app/console-context";
import type { RuntimePhase } from "../../domain/types";
import { CapturePreview } from "./capture-preview";
import { MetricList, Section } from "../core/panel";
import { StatusLabel, type StatusTone } from "../core/status-label";
import { workbenchStyles } from "./workbench.stylex";
import {
  calculateFlowProgress,
  formatElapsed,
  phaseLabels,
  screenLabels,
  useNow,
} from "./runtime-display";

const phaseTones: Record<RuntimePhase, StatusTone> = {
  idle: "neutral",
  awaitingDecision: "success",
  paused: "warning",
  error: "error",
  fastForwarding: "running",
  enteringName: "running",
  enteringBirthday: "running",
  scanning: "running",
  restarting: "running",
};

export function CapturePanel() {
  const { runtime, settings, runAction } = useConsole();
  const calculated = calculateFlowProgress(runtime, settings.stableFrames);
  const [flow, setFlow] = useState({
    run: runtime.runNumber,
    value: calculated,
  });
  useEffect(
    () =>
      setFlow((previous) => {
        const reset =
          runtime.phase === "idle" ||
          runtime.phase === "restarting" ||
          previous.run !== runtime.runNumber;
        const value = reset
          ? calculated
          : ["paused", "error"].includes(runtime.phase)
            ? previous.value
            : Math.max(previous.value, calculated);
        return previous.run === runtime.runNumber && previous.value === value
          ? previous
          : { run: runtime.runNumber, value };
      }),
    [calculated, runtime.phase, runtime.runNumber],
  );
  const now = useNow(runtime.startedAt !== null && runtime.phase !== "idle");
  const candidate =
    runtime.phase === "awaitingDecision" ? runtime.selectedCandidate : null;
  return (
    <div {...stylex.props(workbenchStyles.main)}>
      <Section
        title="实时画面"
        actions={
          <StatusLabel
            tone={phaseTones[runtime.phase]}
            label={phaseLabels[runtime.phase]}
          />
        }
      >
        <CapturePreview />
        <div {...stylex.props(workbenchStyles.status)}>
          {runtime.phase !== "idle" && (
            <ProgressBar
              label={screenLabels[runtime.currentScreen]}
              value={flow.value}
              hasValueLabel
              variant={
                runtime.phase === "error"
                  ? "error"
                  : runtime.phase === "awaitingDecision"
                    ? "success"
                    : "neutral"
              }
            />
          )}
          <Text color="secondary" role="status">
            {runtime.lastMessage}
          </Text>
        </div>
      </Section>
      {candidate && (
        <section
          {...stylex.props(workbenchStyles.decision)}
          aria-label="候选岛确认"
        >
          <HStack hAlign="between" vAlign="center" gap={3} wrap="wrap">
            <Text weight="semibold">地图 {candidate.cardIndex + 1} 通过全部硬条件</Text>
            <Text color="secondary" hasTabularNumbers>
              综合 {(candidate.score * 100).toFixed(1)}%
            </Text>
          </HStack>
          <HStack gap={4} wrap="wrap">
            {candidate.factors.map((factor) => (
              <StatusLabel
                key={factor.key}
                size="supporting"
                tone={factor.passed ? "success" : "error"}
                label={`${factor.label} ${Math.round(factor.score * 100)}%`}
              />
            ))}
          </HStack>
          <HStack gap={2} wrap="wrap">
            <Button
              label="保留这个岛"
              variant="primary"
              clickAction={() => runAction("accept")}
            />
            <Button
              label="放弃并重来"
              clickAction={() => runAction("reject")}
            />
          </HStack>
        </section>
      )}
      <MetricList
        items={[
          { label: "轮次", value: runtime.runNumber || "—" },
          { label: "用时", value: formatElapsed(runtime.startedAt, now) },
          {
            label: "综合阈值",
            value: `${Math.round(settings.threshold * 100)}%`,
          },
        ]}
      />
    </div>
  );
}
