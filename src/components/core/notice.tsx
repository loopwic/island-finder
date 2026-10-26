import { Banner } from "@astryxdesign/core/Banner";
import { Text } from "@astryxdesign/core/Text";
import { create, props } from "@stylexjs/stylex";
import type { ReactNode } from "react";

// Astryx pulls banner actions up 4px to center them on the title line;
// Figma aligns the button with the banner's top inset instead.
// The description sits 2px under the title line.
const styles = create({
  action: { marginBlockStart: "4px" },
  description: { display: "block", marginBlockStart: "2px" },
});

/**
 * Figma 反馈/提示条. Astryx colors the banner's own title and description
 * by status; the design keeps them in the body text colors (title 13/500,
 * description 13/400 secondary), so the text comes in as Text nodes.
 * `section` is the full-width bar under a header, `card` sits in content.
 */
export function Notice({
  status,
  title,
  description,
  action,
  container = "card",
}: {
  status: "info" | "warning" | "error" | "success";
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  container?: "card" | "section";
}) {
  return (
    <Banner
      status={status}
      container={container}
      title={
        <Text weight="medium" color="primary">
          {title}
        </Text>
      }
      description={
        description && (
          <Text
            color="secondary"
            wordBreak="break-word"
            xstyle={styles.description}
          >
            {description}
          </Text>
        )
      }
      endContent={action && <div {...props(styles.action)}>{action}</div>}
    />
  );
}
