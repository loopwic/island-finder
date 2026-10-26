import { Button } from "@astryxdesign/core/Button";
import { useListFocus } from "@astryxdesign/core/hooks";
import * as stylex from "@stylexjs/stylex";
import { pillTabListStyles } from "./pill-tab-list.stylex";

export type PillTabItem<Value extends string> = {
  value: Value;
  label: string;
  tabId: string;
  panelId: string;
};

/** Compact view switcher with roving focus; the caller owns the panels. */
export function PillTabList<Value extends string>({
  label,
  items,
  value,
  onChange,
}: {
  label: string;
  items: readonly PillTabItem<Value>[];
  value: Value;
  onChange: (value: Value) => void;
}) {
  const { handleFocus, handleKeyDown, listRef } = useListFocus<HTMLDivElement>({
    hasRovingTabIndex: true,
    itemSelector: '[role="tab"]',
    orientation: "horizontal",
  });
  return (
    <div
      {...stylex.props(pillTabListStyles.root)}
      ref={listRef}
      role="tablist"
      aria-label={label}
      tabIndex={-1}
      onFocus={handleFocus}
      onKeyDown={handleKeyDown}
    >
      {items.map((item) => {
        const isSelected = item.value === value;
        return (
          <Button
            key={item.value}
            id={item.tabId}
            role="tab"
            aria-controls={item.panelId}
            aria-selected={isSelected}
            tabIndex={isSelected ? 0 : -1}
            type="button"
            size="sm"
            variant="ghost"
            label={item.label}
            xstyle={[
              pillTabListStyles.tab,
              isSelected && pillTabListStyles.selected,
            ]}
            onClick={() => onChange(item.value)}
          />
        );
      })}
    </div>
  );
}
