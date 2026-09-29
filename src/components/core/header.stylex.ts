import { create } from "@stylexjs/stylex";
import { sizeVars, spacingVars } from "@astryxdesign/core/theme/tokens.stylex";

export const headerStyles = create({
  frame: {
    height: `calc(${sizeVars["--size-element-md"]} + ${spacingVars["--spacing-6"]})`,
    minHeight: `calc(${sizeVars["--size-element-md"]} + ${spacingVars["--spacing-6"]})`,
    paddingInline: {
      default: spacingVars["--spacing-6"],
      "@media (max-width: 640px)": spacingVars["--spacing-4"],
    },
  },
});
