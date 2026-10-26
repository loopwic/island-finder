import { create } from "@stylexjs/stylex";
import {
  borderVars,
  colorVars,
  shadowVars,
  spacingVars,
} from "@astryxdesign/core/theme/tokens.stylex";

export const shellStyles = create({
  // Figma: a 244px sidebar, the main panel inset 8px from the other edges.
  // AppShell already adds that 8px, so the nav itself is 236px.
  navigation: {
    width: { default: 236, "@media (max-width: 768px)": "100%" },
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: spacingVars["--spacing-2"],
    minWidth: 0,
    minHeight: spacingVars["--spacing-11"],
    paddingInline: spacingVars["--spacing-2"],
  },
  // The main panel is background/surface on the body color; its 0.5px
  // border/default frame comes from Card itself.
  contentFrame: {
    backgroundColor: colorVars["--color-background-surface"],
    boxShadow: shadowVars["--shadow-low"],
  },
  route: { minWidth: 0, minHeight: 0, height: "100%" },
  // Astryx layout dividers are a fixed 1px; Figma rules are --border-width.
  headerDivider: { borderBlockEndWidth: borderVars["--border-width"] },
  startDivider: { borderInlineEndWidth: borderVars["--border-width"] },
  endDivider: { borderInlineStartWidth: borderVars["--border-width"] },
});
