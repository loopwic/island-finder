import { create } from "@stylexjs/stylex";
import {
  borderVars,
  colorVars,
  radiusVars,
  shadowVars,
  spacingVars,
} from "@astryxdesign/core/theme/tokens.stylex";

export const workbenchStyles = create({
  main: { display: "grid", gap: spacingVars["--spacing-6"], minWidth: 0 },
  status: { display: "grid", gap: spacingVars["--spacing-2"], minWidth: 0 },
  // Figma 属性栏: groups inset 16px, starting 20px down, 24px apart.
  aside: {
    display: "grid",
    alignContent: "start",
    gap: spacingVars["--spacing-6"],
    paddingBlockStart: spacingVars["--spacing-5"],
    paddingBlockEnd: spacingVars["--spacing-4"],
    paddingInline: spacingVars["--spacing-4"],
    minWidth: 0,
  },
  // The candidate decision is the one card on the console: the only state
  // that waits for the user.
  decision: {
    display: "grid",
    gap: spacingVars["--spacing-3"],
    padding: spacingVars["--spacing-4"],
    borderWidth: borderVars["--border-width"],
    borderStyle: "solid",
    borderColor: colorVars["--color-border"],
    borderRadius: radiusVars["--radius-container"],
    backgroundColor: colorVars["--color-background-card"],
    boxShadow: shadowVars["--shadow-low"],
  },
});
