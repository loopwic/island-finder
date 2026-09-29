import { create } from "@stylexjs/stylex";
import { typeScaleVars } from "@astryxdesign/core/theme/tokens.stylex";

export const dialogStyles = create({
  header: {
    boxSizing: "border-box",
    "--text-heading-2-leading": typeScaleVars["--text-body-leading"],
    "--text-heading-2-size": typeScaleVars["--text-body-size"],
  },
});
