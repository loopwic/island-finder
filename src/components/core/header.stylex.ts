import { create } from "@stylexjs/stylex";
import {
  colorVars,
  spacingVars,
} from "@astryxdesign/core/theme/tokens.stylex";

// Figma 导航/页头: 44px, the page icon and 13/500 title on the 16px gutter.
export const headerStyles = create({
  frame: {
    minHeight: spacingVars["--spacing-11"],
    paddingInlineStart: spacingVars["--spacing-4"],
    paddingInlineEnd: spacingVars["--spacing-3"],
  },
  identity: {
    display: "flex",
    alignItems: "center",
    gap: spacingVars["--spacing-2"],
    minWidth: 0,
  },
  icon: {
    display: "inline-flex",
    fontSize: spacingVars["--spacing-4"],
    color: colorVars["--color-icon-secondary"],
  },
});
