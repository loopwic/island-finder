import { create } from "@stylexjs/stylex";
import {
  colorVars,
  radiusVars,
  spacingVars,
} from "@astryxdesign/core/theme/tokens.stylex";

// Status is a colored mark beside plain text; the color names the state
// (Figma status/*), the text stays readable in either mode.
export const statusStyles = create({
  root: {
    display: "inline-flex",
    alignItems: "center",
    gap: spacingVars["--spacing-1-5"],
    minWidth: 0,
  },
  mark: {
    flexShrink: 0,
    width: spacingVars["--spacing-2"],
    height: spacingVars["--spacing-2"],
    borderRadius: radiusVars["--radius-full"],
  },
  success: { backgroundColor: colorVars["--color-success"] },
  warning: { backgroundColor: colorVars["--color-warning"] },
  error: { backgroundColor: colorVars["--color-error"] },
  running: { backgroundColor: colorVars["--color-icon-blue"] },
  neutral: { backgroundColor: colorVars["--color-icon-disabled"] },
});
