import { create } from "@stylexjs/stylex";
import {
  colorVars,
  focusVars,
  radiusVars,
  spacingVars,
  typeScaleVars,
} from "@astryxdesign/core/theme/tokens.stylex";

// Figma 属性栏: 36px rows with 12px insets, a 96px label column, and values
// led by a 16px semantic icon 8px before the text.
export const propertyStyles = create({
  list: { display: "grid", margin: 0, minWidth: 0 },
  row: {
    display: "flex",
    alignItems: "center",
    minHeight: spacingVars["--spacing-9"],
    paddingInline: spacingVars["--spacing-3"],
    minWidth: 0,
  },
  label: {
    flexBasis: "5.625rem",
    flexShrink: 0,
    margin: 0,
    color: colorVars["--color-text-secondary"],
    fontSize: typeScaleVars["--text-body-size"],
    lineHeight: typeScaleVars["--text-body-leading"],
  },
  value: {
    display: "flex",
    alignItems: "center",
    flex: 1,
    gap: spacingVars["--spacing-2"],
    minWidth: 0,
    margin: 0,
    paddingInline: spacingVars["--spacing-1-5"],
    fontSize: typeScaleVars["--text-body-size"],
    lineHeight: typeScaleVars["--text-body-leading"],
    color: colorVars["--color-text-primary"],
  },
  controlValue: { paddingInline: 0 },
  icon: {
    display: "inline-flex",
    flexShrink: 0,
    fontSize: spacingVars["--spacing-4"],
    color: colorVars["--color-icon-secondary"],
  },
  control: {
    display: "inline-flex",
    alignItems: "center",
    gap: spacingVars["--spacing-2"],
    minHeight: spacingVars["--spacing-7"],
    maxWidth: "100%",
    minWidth: 0,
    paddingBlock: 0,
    paddingInline: spacingVars["--spacing-1-5"],
    borderWidth: 0,
    borderRadius: radiusVars["--radius-full"],
    backgroundColor: {
      default: "transparent",
      ":hover": colorVars["--color-overlay-hover"],
      ":active": colorVars["--color-overlay-pressed"],
    },
    color: "inherit",
    font: "inherit",
    textAlign: "start",
    cursor: "pointer",
    outline: {
      default: "none",
      ":focus-visible": `2px solid ${focusVars["--focus-outline-color"]}`,
    },
  },
  controlText: {
    minWidth: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
});
