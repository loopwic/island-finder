import { create } from "@stylexjs/stylex";
import { spacingVars } from "@astryxdesign/core/theme/tokens.stylex";

// Figma layout/page-gutter: the header title, view tabs' text, banners and a
// list's first column all start 16px in. Reading content (record details)
// uses layout/reading-inset, 48px.
export const pageStyles = create({
  workspace: {
    boxSizing: "border-box",
    width: "100%",
    minWidth: 0,
    padding: spacingVars["--spacing-4"],
  },
  reading: {
    boxSizing: "border-box",
    width: "100%",
    minWidth: 0,
    paddingBlock: spacingVars["--spacing-8"],
    paddingInline: {
      default: spacingVars["--spacing-12"],
      "@media (max-width: 640px)": spacingVars["--spacing-4"],
    },
  },
  // View tabs: pills start at 8px so their text sits on the 16px gutter.
  tabRow: {
    display: "flex",
    alignItems: "center",
    minHeight: spacingVars["--spacing-11"],
    paddingInline: spacingVars["--spacing-2"],
  },
  limit: (maxWidth: string) => ({ maxWidth, minWidth: 0 }),
});
