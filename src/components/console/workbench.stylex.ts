import { create } from "@stylexjs/stylex";
import { spacingVars } from "@astryxdesign/core/theme/tokens.stylex";

export const workbenchStyles = create({
  metrics: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: spacingVars["--spacing-4"],
  },
  columns: {
    gridTemplateColumns: {
      default: "minmax(0, 1fr) 288px",
      "@media (max-width: 1100px)": "minmax(0, 1fr)",
    },
  },
});
