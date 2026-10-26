import { create } from "@stylexjs/stylex";
import {
  colorVars,
  radiusVars,
  spacingVars,
} from "@astryxdesign/core/theme/tokens.stylex";

export const presentation = create({
  brandMark: {
    display: "grid",
    placeItems: "center",
    flexShrink: 0,
    width: spacingVars["--spacing-6"],
    height: spacingVars["--spacing-6"],
    borderRadius: radiusVars["--radius-inner"],
    backgroundColor: colorVars["--color-overlay-pressed"],
    color: colorVars["--color-icon-secondary"],
    fontSize: spacingVars["--spacing-4"],
  },
  identity: {
    display: "grid",
    placeItems: "center",
    flexShrink: 0,
    width: spacingVars["--spacing-10"],
    height: spacingVars["--spacing-10"],
    borderRadius: radiusVars["--radius-container"],
    backgroundColor: colorVars["--color-overlay-pressed"],
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
  settingRow: {
    display: "grid",
    gridTemplateColumns: {
      default: "minmax(0, 1fr) auto",
      "@media (max-width: 380px)": "minmax(0, 1fr)",
    },
    alignItems: "center",
    gap: spacingVars["--spacing-4"],
    paddingBlock: spacingVars["--spacing-3"],
  },
  settingControl: { flexShrink: 0, minWidth: 0, maxWidth: "100%" },
});
