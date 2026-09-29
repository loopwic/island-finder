import { TextInput } from "@astryxdesign/core/TextInput";
import { Selector } from "@astryxdesign/core/Selector";
import { Text } from "@astryxdesign/core/Text";
import { FormLayout } from "@astryxdesign/core/FormLayout";
import * as stylex from "@stylexjs/stylex";
import { useConsole } from "../../app/console-context";
import { detectNameInputMode } from "../../domain/name-input";
import { ui } from "../core/ui.stylex";
const daysInMonth = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
export function IdentityPanel() {
  const {
    settings,
    settingsLoaded,
    active,
    updateIdentity,
    updateName,
    updatePinyin,
  } = useConsole();
  const identity = settings.identity;
  const mode = detectNameInputMode(identity.name);
  const disabled = active || !settingsLoaded;
  return (
    <FormLayout aria-busy={!settingsLoaded}>
      <Text size="sm" color="secondary">
        每轮自动填写；名字支持 1–10 个汉字或纯英文字母。
      </Text>
      <TextInput
        label="岛民名字"
        value={identity.name}
        onChange={updateName}
        isDisabled={disabled}
        width="100%"
        placeholder="小森 / nook"
        status={
          settingsLoaded && ["empty", "unsupported"].includes(mode)
            ? {
                type: "error",
                message: "请使用全中文或纯英文，不要混入数字或符号",
              }
            : undefined
        }
        statusVariant="detached"
      />
      {mode === "chinese" && (
        <div {...stylex.props(ui.fields)}>
          {Array.from(identity.name).map((character, index) => (
            <TextInput
              key={`${character}-${index}`}
              label={`「${character}」的拼音`}
              value={identity.namePinyin[index] ?? ""}
              onChange={(value) => updatePinyin(index, value)}
              isDisabled={disabled}
              width="100%"
              status={
                !identity.namePinyin[index]
                  ? { type: "error", message: "请填写拼音" }
                  : undefined
              }
              statusVariant="detached"
            />
          ))}
        </div>
      )}
      <div {...stylex.props(ui.fields)}>
        <Selector
          label="出生月"
          value={String(identity.birthMonth)}
          width="100%"
          isDisabled={disabled}
          options={Array.from({ length: 12 }, (_, i) => ({
            value: String(i + 1),
            label: `${i + 1} 月`,
          }))}
          onChange={(value) =>
            updateIdentity({
              birthMonth: Number(value),
              birthDay: Math.min(
                identity.birthDay,
                daysInMonth[Number(value) - 1],
              ),
            })
          }
        />
        <Selector
          label="出生日"
          value={String(identity.birthDay)}
          width="100%"
          isDisabled={disabled}
          options={Array.from(
            { length: daysInMonth[identity.birthMonth - 1] },
            (_, i) => ({
              value: String(i + 1),
              label: `${i + 1} 日`,
            }),
          )}
          onChange={(value) => updateIdentity({ birthDay: Number(value) })}
        />
      </div>
      <Selector
        label="初始造型"
        value={identity.initialStyle}
        isDisabled={disabled}
        width="100%"
        options={[
          { value: "left", label: "左侧造型" },
          { value: "right", label: "右侧造型" },
        ]}
        onChange={(value) =>
          updateIdentity({ initialStyle: value as "left" | "right" })
        }
      />
    </FormLayout>
  );
}
