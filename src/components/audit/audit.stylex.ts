import { create } from "@stylexjs/stylex";
import {
  colorVars,
  spacingVars,
  borderVars,
  radiusVars,
} from "@astryxdesign/core/theme/tokens.stylex";
export const auditStyles = create({
  mobileRecords: { maxHeight: "18rem", overflowY: "auto" },
  row: {
    padding: spacingVars["--spacing-3"],
    borderRadius: radiusVars["--radius-element"],
  },
  records: { padding: spacingVars["--spacing-2"] },
  detail: { maxWidth: 1120, width: "100%", marginInline: "auto" },
  factor: {
    paddingBlock: spacingVars["--spacing-3"],
    borderBlockEndWidth: borderVars["--border-width"],
    borderBlockEndStyle: "solid",
    borderBlockEndColor: colorVars["--color-border"],
    ":last-child": { borderBlockEndWidth: 0 },
  },
  factorLabel: {
    display: "flex",
    flex: 1,
    minWidth: 0,
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacingVars["--spacing-2"],
    paddingInlineEnd: spacingVars["--spacing-2"],
  },
  factorName: { width: 128, minWidth: 0 },
  passed: { color: colorVars["--color-text-green"] },
  failed: { color: colorVars["--color-text-red"] },
  preview: { paddingInline: spacingVars["--spacing-3"] },
  mapImage: { borderRadius: radiusVars["--radius-element"] },
  summary: {
    paddingBlock: spacingVars["--spacing-3"],
    paddingInline: spacingVars["--spacing-4"],
    backgroundColor: colorVars["--color-neutral"],
    borderRadius: radiusVars["--radius-element"],
  },
});
