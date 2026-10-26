import {
  Layout,
  LayoutContent,
  LayoutPanel,
} from "@astryxdesign/core/Layout";
import { useMediaQuery } from "@astryxdesign/core/hooks";
import { CapturePanel } from "../components/console/capture-panel";
import { RunConfiguration } from "../components/console/run-configuration";
import { PageContent } from "../components/core/page";
import { shellStyles } from "../app/shell.stylex";

export function WorkbenchPage() {
  const narrow = useMediaQuery("(max-width: 1100px)");
  return (
    <Layout
      height={narrow ? "auto" : "fill"}
      padding={0}
      content={
        <LayoutContent padding={0}>
          <PageContent>
            <CapturePanel />
          </PageContent>
          {narrow && <RunConfiguration />}
        </LayoutContent>
      }
      end={
        narrow ? undefined : (
          <LayoutPanel
            width={376}
            padding={0}
            hasDivider
            label="本轮配置"
            xstyle={shellStyles.endDivider}
          >
            <RunConfiguration />
          </LayoutPanel>
        )
      }
    />
  );
}
