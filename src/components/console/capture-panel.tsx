import { Button } from "@astryxdesign/core/Button";
import { ProgressBar } from "@astryxdesign/core/ProgressBar";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import * as stylex from "@stylexjs/stylex";
import { useEffect, useState } from "react";
import { useConsole } from "../../app/console-context";
import { CapturePreview } from "./capture-preview";
import { Panel, Metric } from "../core/panel";
import { ui } from "../core/ui.stylex";
import { AppIcon } from "../core/icons";
import { presentation } from "../core/presentation.stylex";
import { workbenchStyles } from "./workbench.stylex";
import {
  calculateFlowProgress,
  formatElapsed,
  phaseLabels,
  screenLabels,
} from "./runtime-display";

export function CapturePanel() {
  const { runtime, settings, active, runAction } = useConsole();
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
  const candidate =
    runtime.phase === "awaitingDecision" ? runtime.selectedCandidate : null;
  return (
    <Panel
      title="实时画面"
      actions={
        <Token
          label={phaseLabels[runtime.phase]}
          color={runtime.phase === "error" ? "red" : "default"}
        />
      }
    >
      <CapturePreview />
      <div {...stylex.props(presentation.metricStrip, workbenchStyles.metrics)}>
        <Metric label="轮次" value={runtime.runNumber || "—"} />
        <Metric label="用时" value={formatElapsed(runtime.startedAt)} />
        <Metric
          label="综合阈值"
          value={`${Math.round(settings.threshold * 100)}%`}
        />
      </div>
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
      <Text size="sm" color="secondary">
        {runtime.lastMessage
          .replace(runtime.currentScreen, screenLabels[runtime.currentScreen])
          .replace(": ", "：")}
      </Text>
      {(active || runtime.phase === "paused") && (
        <div {...stylex.props(ui.row, ui.end)}>
          {runtime.phase === "paused" ? (
            <Button
              label="继续"
              icon={<AppIcon name="play" />}
              clickAction={() => runAction("resume")}
            />
          ) : (
            active && (
              <Button
                label="暂停"
                icon={<AppIcon name="pause" />}
                clickAction={() => runAction("pause")}
              />
            )
          )}
        </div>
      )}
      {candidate && (
        <section
          {...stylex.props(ui.stack, ui.padding, ui.panel, ui.selected)}
          aria-label="候选岛确认"
        >
          <Text weight="semibold">
            发现候选岛：地图 {candidate.cardIndex + 1}
          </Text>
          <Text color="secondary">
            综合评分 {(candidate.score * 100).toFixed(1)}%，等待你决定
          </Text>
          <div {...stylex.props(ui.row)}>
            {candidate.factors.map((factor) => (
              <Token
                key={factor.key}
                label={`${factor.label} ${Math.round(factor.score * 100)}%`}
                color={factor.passed ? "green" : "red"}
              />
            ))}
          </div>
          <div {...stylex.props(ui.row)}>
            <Button
              label="保留这个岛"
              variant="primary"
              clickAction={() => runAction("accept")}
            />
            <Button
              label="放弃并重来"
              clickAction={() => runAction("reject")}
            />
          </div>
        </section>
      )}
    </Panel>
  );
}
