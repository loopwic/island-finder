import { create } from "@stylexjs/stylex";
import {
  borderVars,
  colorVars,
  radiusVars,
  spacingVars,
} from "@astryxdesign/core/theme/tokens.stylex";

export const presentation = create({
  identity: {
    display: "grid",
    placeItems: "center",
    flexShrink: 0,
    width: spacingVars["--spacing-10"],
    height: spacingVars["--spacing-10"],
    borderRadius: radiusVars["--radius-container"],
    backgroundColor: colorVars["--color-neutral"],
    color: colorVars["--color-icon-secondary"],
    fontSize: spacingVars["--spacing-5"],
  },
  smallIdentity: {
    width: spacingVars["--spacing-8"],
    height: spacingVars["--spacing-8"],
    borderRadius: radiusVars["--radius-element"],
    fontSize: spacingVars["--spacing-4"],
  },
  metricValue: {
    letterSpacing: "-0.025em",
  },
  metricStrip: {
    paddingBlock: spacingVars["--spacing-5"],
    borderBlockStartWidth: borderVars["--border-width"],
    borderBlockStartStyle: "solid",
    borderBlockStartColor: colorVars["--color-border"],
    borderBlockEndWidth: borderVars["--border-width"],
    borderBlockEndStyle: "solid",
    borderBlockEndColor: colorVars["--color-border"],
  },
  settingRow: {
    display: "grid",
    gridTemplateColumns: {
      default: "minmax(0, 1fr) auto",
      "@media (max-width: 380px)": "minmax(0, 1fr)",
    },
    alignItems: "center",
    gap: spacingVars["--spacing-4"],
    paddingBlock: spacingVars["--spacing-4"],
    borderBlockEndWidth: borderVars["--border-width"],
    borderBlockEndStyle: "solid",
    borderBlockEndColor: colorVars["--color-border"],
  },
  settingControl: { flexShrink: 0, minWidth: 0, maxWidth: "100%" },
});
