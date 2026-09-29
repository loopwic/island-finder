import { Button } from "@astryxdesign/core/Button";
import { Slider } from "@astryxdesign/core/Slider";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import * as stylex from "@stylexjs/stylex";
import { useRef } from "react";
import { useConsole } from "../../app/console-context";
import { ui } from "../core/ui.stylex";
import { AppIcon } from "../core/icons";
const criteria = [
  "完整礁石结构",
  "机场与广场轴线协调",
  "指定浮岛结构",
  "狐狸海滩靠侧边",
  "圆润海岸线",
  "双入海口且非双南",
];
export function TargetPanel() {
  const {
    settings,
    active,
    settingsLoaded,
    updateSettings,
    addTargets,
    removeTarget,
  } = useConsole();
  const fileInput = useRef<HTMLInputElement>(null);
  const disabled = active || !settingsLoaded;
  return (
    <div {...stylex.props(ui.stack)}>
      <Text size="sm" color="secondary">
        全部硬条件通过后，才会等待你确认。这里不改变识别规则。
      </Text>
      <div {...stylex.props(ui.row)}>
        {criteria.map((label) => (
          <Token key={label} label={label} />
        ))}
      </div>
      <Slider
        label="综合评分阈值"
        value={Math.round(settings.threshold * 100)}
        min={55}
        max={95}
        step={1}
        valueDisplay="text"
        formatValue={(value) => `${value}%`}
        onChange={(value: number) => updateSettings({ threshold: value / 100 })}
        isDisabled={disabled}
        width="100%"
      />
      <Button
        label="添加辅助地图样例"
        icon={<AppIcon name="image" />}
        isDisabled={disabled}
        onClick={() => fileInput.current?.click()}
      />
      <input
        ref={fileInput}
        hidden
        type="file"
        accept="image/png,image/jpeg,image/webp"
        multiple
        disabled={disabled}
        onChange={(event) => {
          void addTargets(event.target.files);
          event.target.value = "";
        }}
      />
      <div {...stylex.props(ui.tight, ui.scroll)}>
        {settings.targets.map((target) => (
          <div
            {...stylex.props(ui.row, ui.padding, ui.divider)}
            key={target.id}
          >
            <img {...stylex.props(ui.thumb)} src={target.previewUrl} alt="" />
            <Text xstyle={ui.grow} maxLines={1}>
              {target.name}
            </Text>
            <Button
              label={`移除 ${target.name}`}
              icon={<AppIcon name="delete" />}
              isIconOnly
              variant="ghost"
              isDisabled={disabled}
              onClick={() => removeTarget(target.id)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
