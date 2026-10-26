import * as stylex from "@stylexjs/stylex";
import type { ReactNode } from "react";
import { pageStyles } from "./page.stylex";

/** Route body on the shared gutters; `maxWidth` caps the line length only. */
export function PageContent({
  inset = "workspace",
  maxWidth,
  children,
}: {
  inset?: "workspace" | "reading";
  maxWidth?: string;
  children: ReactNode;
}) {
  return (
    <div {...stylex.props(pageStyles[inset])}>
      {maxWidth ? (
        <div {...stylex.props(pageStyles.limit(maxWidth))}>{children}</div>
      ) : (
        children
      )}
    </div>
  );
}
