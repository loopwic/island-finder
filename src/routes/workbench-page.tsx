import { Layout, LayoutContent } from "@astryxdesign/core/Layout";
import { Grid } from "@astryxdesign/core/Grid";
import { CapturePanel } from "../components/console/capture-panel";
import { RunConfiguration } from "../components/console/run-configuration";
import { workbenchStyles } from "../components/console/workbench.stylex";

export function WorkbenchPage() {
  return (
    <Layout
      height="auto"
      contentWidth={1200}
      padding={8}
      content={
        <LayoutContent isScrollable={false}>
          <Grid gap={8} align="start" xstyle={workbenchStyles.columns}>
            <CapturePanel />
            <RunConfiguration />
          </Grid>
        </LayoutContent>
      }
    />
  );
}
