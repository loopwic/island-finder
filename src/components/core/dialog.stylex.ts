import { create } from "@stylexjs/stylex";
import {
  spacingVars,
  typeScaleVars,
} from "@astryxdesign/core/theme/tokens.stylex";

// Figma 对话框: title 15/22 semibold, 20px insets, a 56px action edge.
export const dialogStyles = create({
  header: {
    boxSizing: "border-box",
    paddingInline: spacingVars["--spacing-5"],
    paddingBlockStart: spacingVars["--spacing-5"],
    "--text-heading-2-size": typeScaleVars["--text-heading-3-size"],
    "--text-heading-2-leading": typeScaleVars["--text-heading-3-leading"],
    "--text-heading-2-weight": "600",
  },
  content: {
    paddingInline: spacingVars["--spacing-5"],
    paddingBlock: spacingVars["--spacing-4"],
  },
  footer: {
    minHeight: "56px",
    paddingInline: spacingVars["--spacing-5"],
    paddingBlock: spacingVars["--spacing-3"],
  },
});
