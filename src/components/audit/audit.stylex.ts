import { create } from "@stylexjs/stylex";
import {
  borderVars,
  colorVars,
  focusVars,
  radiusVars,
  shadowVars,
  spacingVars,
} from "@astryxdesign/core/theme/tokens.stylex";

export const auditStyles = create({
  mobileRecords: { maxHeight: "18rem", overflowY: "auto" },
  recordsHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacingVars["--spacing-2"],
    minHeight: spacingVars["--spacing-11"],
    paddingInline: spacingVars["--spacing-4"],
  },
  // Rows inset 8px like Figma's list bands, so their text lands on 16px.
  records: {
    paddingInline: spacingVars["--spacing-2"],
    paddingBlockEnd: spacingVars["--spacing-2"],
  },
  row: {
    paddingBlock: spacingVars["--spacing-2"],
    paddingInline: spacingVars["--spacing-2"],
    borderRadius: radiusVars["--radius-element"],
  },
  detail: { maxWidth: "60rem", width: "100%" },
  // One map: a card (Figma Shadow/Low) with equal 16px insets.
  card: {
    display: "grid",
    gap: spacingVars["--spacing-3"],
    padding: spacingVars["--spacing-4"],
    borderWidth: borderVars["--border-width"],
    borderStyle: "solid",
    borderColor: colorVars["--color-border"],
    borderRadius: radiusVars["--radius-container"],
    backgroundColor: colorVars["--color-background-card"],
    boxShadow: shadowVars["--shadow-low"],
    minWidth: 0,
  },
  selectedCard: { borderColor: colorVars["--color-accent"] },
  factor: { paddingBlock: spacingVars["--spacing-1-5"] },
  factorLabel: {
    display: "flex",
    flex: 1,
    minWidth: 0,
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacingVars["--spacing-2"],
    paddingInlineEnd: spacingVars["--spacing-2"],
  },
  factorName: { flexBasis: "8rem", flexShrink: 0, minWidth: 0 },
  metaIcon: {
    display: "inline-flex",
    color: colorVars["--color-icon-secondary"],
  },
  passed: { display: "inline-flex", color: colorVars["--color-success"] },
  failed: { display: "inline-flex", color: colorVars["--color-error"] },
  zoomButton: {
    display: "block",
    width: "100%",
    padding: 0,
    borderWidth: 0,
    backgroundColor: "transparent",
    borderRadius: radiusVars["--radius-element"],
    cursor: "zoom-in",
    outline: {
      default: "none",
      ":focus-visible": `2px solid ${focusVars["--focus-outline-color"]}`,
    },
    outlineOffset: 2,
    opacity: { default: 1, ":hover": 0.92 },
  },
  mapImage: { borderRadius: radiusVars["--radius-element"] },
});
