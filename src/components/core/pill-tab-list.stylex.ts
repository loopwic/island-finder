import { create } from "@stylexjs/stylex";
import {
  borderVars,
  colorVars,
  durationVars,
  easeVars,
  radiusVars,
  shadowVars,
  spacingVars,
  typeScaleVars,
} from "@astryxdesign/core/theme/tokens.stylex";

// Figma 页签: 28px full-radius pills, 4px apart. Resting pills sit on the
// card color with a 9% ring and the panel shadow; the selected pill takes
// control/pill-selected (accent/muted) with the ring only.
// The ghost-variant selectors outrank Astryx's own ghost button colors.
export const pillTabListStyles = create({
  root: {
    display: "flex",
    alignItems: "center",
    gap: spacingVars["--spacing-1"],
    minWidth: 0,
    overflowX: "auto",
  },
  tab: {
    flexShrink: 0,
    height: spacingVars["--spacing-7"],
    minInlineSize: spacingVars["--spacing-7"],
    paddingBlock: {
      default: 0,
      ":is([role='tab'][data-variant='ghost'])": 0,
    },
    paddingInline: {
      default: "0.625rem",
      ":is([role='tab'][data-variant='ghost'])": "0.625rem",
    },
    borderRadius: radiusVars["--radius-full"],
    borderStyle: {
      default: "solid",
      ":is([role='tab'][data-variant='ghost'])": "solid",
    },
    borderWidth: {
      default: 0,
      ":is([role='tab'][data-variant='ghost'])": 0,
    },
    boxShadow: `0 0 0 ${borderVars["--border-width"]} light-dark(#00000017, #ffffff24), ${shadowVars["--shadow-low"]}`,
    backgroundImage: "none",
    backgroundColor: {
      default: colorVars["--color-background-card"],
      ":is([role='tab'][data-variant='ghost'])":
        colorVars["--color-background-card"],
      ":is([role='tab'][data-variant='ghost']:hover:where(:not(:disabled,[aria-disabled='true'])))":
        colorVars["--color-accent-muted"],
    },
    color: {
      default: colorVars["--color-text-secondary"],
      ":is([role='tab'][data-variant='ghost'])":
        colorVars["--color-text-secondary"],
      ":is([role='tab'][data-variant='ghost']:hover:where(:not(:disabled,[aria-disabled='true'])))":
        colorVars["--color-text-primary"],
    },
    fontSize: typeScaleVars["--text-label-size"],
    fontWeight: typeScaleVars["--text-label-weight"],
    lineHeight: typeScaleVars["--text-label-leading"],
    transitionProperty: "background-color, color",
    transitionDuration: {
      default: durationVars["--duration-fast"],
      "@media (prefers-reduced-motion: reduce)": "0s",
    },
    transitionTimingFunction: easeVars["--ease-standard"],
  },
  selected: {
    boxShadow: `0 0 0 ${borderVars["--border-width"]} light-dark(#00000017, #ffffff24)`,
    backgroundColor: {
      default: colorVars["--color-accent-muted"],
      ":is([role='tab'][data-variant='ghost'])": colorVars["--color-accent-muted"],
    },
    color: {
      default: colorVars["--color-text-primary"],
      ":is([role='tab'][data-variant='ghost'])": colorVars["--color-text-primary"],
    },
  },
});
