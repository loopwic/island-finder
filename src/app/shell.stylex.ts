import { create } from "@stylexjs/stylex";
import { spacingVars } from "@astryxdesign/core/theme/tokens.stylex";

export const shellStyles = create({
  navigation: {
    width: { default: 224, "@media (max-width: 768px)": "100%" },
    paddingInline: spacingVars["--spacing-3"],
  },
  route: { minWidth: 0, minHeight: 0, height: "100%" },
});
