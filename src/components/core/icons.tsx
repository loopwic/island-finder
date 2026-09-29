import { HugeiconsIcon } from "@hugeicons/react";
import {
  MapsIcon,
  DashboardSquare01Icon,
  Task01Icon,
  Settings02Icon,
  CpuIcon,
  ArrowReloadHorizontalIcon,
  Sun03Icon,
  Moon02Icon,
  Cancel01Icon,
  Alert02Icon,
  Tick02Icon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  ImageAdd02Icon,
  Delete02Icon,
  Camera01Icon,
  CheckmarkCircle02Icon,
  ArrowDown01Icon,
  ArrowRight01Icon,
  ArrowLeft01Icon,
  InformationCircleIcon,
  LinkSquare02Icon,
  Search01Icon,
  Menu01Icon,
} from "@hugeicons/core-free-icons";
import type { IconRegistry } from "@astryxdesign/core/Icon";
import {
  ArrowDown02Icon,
  ArrowUp02Icon,
  ArrowUpDownIcon,
  Calendar03Icon,
  TickDouble02Icon,
  ArrowLeftDoubleIcon,
  ArrowRightDoubleIcon,
  Clock01Icon,
  Copy01Icon,
  ViewOffIcon,
  FilterHorizontalIcon,
  Mic01Icon,
  MoreHorizontalIcon,
  LayoutTwoColumnIcon,
  Wrench01Icon,
  CancelCircleIcon,
} from "@hugeicons/core-free-icons";

const glyphs = {
  map: MapsIcon,
  dashboard: DashboardSquare01Icon,
  audit: Task01Icon,
  settings: Settings02Icon,
  cpu: CpuIcon,
  refresh: ArrowReloadHorizontalIcon,
  sun: Sun03Icon,
  moon: Moon02Icon,
  close: Cancel01Icon,
  warning: Alert02Icon,
  check: Tick02Icon,
  play: PlayIcon,
  pause: PauseIcon,
  stop: StopIcon,
  image: ImageAdd02Icon,
  delete: Delete02Icon,
  camera: Camera01Icon,
  success: CheckmarkCircle02Icon,
  down: ArrowDown01Icon,
  right: ArrowRight01Icon,
  left: ArrowLeft01Icon,
  info: InformationCircleIcon,
  external: LinkSquare02Icon,
  search: Search01Icon,
  menu: Menu01Icon,
};
export function AppIcon({
  name,
  size = "1em",
}: {
  name: keyof typeof glyphs;
  size?: number | string;
}) {
  return <HugeiconsIcon icon={glyphs[name]} size={size} aria-hidden="true" />;
}
export const iconRegistry: IconRegistry = {
  close: <AppIcon name="close" />,
  check: <AppIcon name="check" />,
  success: <AppIcon name="success" />,
  error: (
    <HugeiconsIcon icon={CancelCircleIcon} size="1em" aria-hidden="true" />
  ),
  warning: <AppIcon name="warning" />,
  info: <AppIcon name="info" />,
  chevronDown: <AppIcon name="down" />,
  chevronLeft: <AppIcon name="left" />,
  chevronRight: <AppIcon name="right" />,
  externalLink: <AppIcon name="external" />,
  search: <AppIcon name="search" />,
  menu: <AppIcon name="menu" />,
  arrowDown: (
    <HugeiconsIcon icon={ArrowDown02Icon} size="1em" aria-hidden="true" />
  ),
  arrowUp: <HugeiconsIcon icon={ArrowUp02Icon} size="1em" aria-hidden="true" />,
  arrowsUpDown: (
    <HugeiconsIcon icon={ArrowUpDownIcon} size="1em" aria-hidden="true" />
  ),
  calendar: (
    <HugeiconsIcon icon={Calendar03Icon} size="1em" aria-hidden="true" />
  ),
  checkDouble: (
    <HugeiconsIcon icon={TickDouble02Icon} size="1em" aria-hidden="true" />
  ),
  chevronsLeft: (
    <HugeiconsIcon icon={ArrowLeftDoubleIcon} size="1em" aria-hidden="true" />
  ),
  chevronsRight: (
    <HugeiconsIcon icon={ArrowRightDoubleIcon} size="1em" aria-hidden="true" />
  ),
  clock: <HugeiconsIcon icon={Clock01Icon} size="1em" aria-hidden="true" />,
  copy: <HugeiconsIcon icon={Copy01Icon} size="1em" aria-hidden="true" />,
  eyeSlash: <HugeiconsIcon icon={ViewOffIcon} size="1em" aria-hidden="true" />,
  funnel: (
    <HugeiconsIcon icon={FilterHorizontalIcon} size="1em" aria-hidden="true" />
  ),
  microphone: <HugeiconsIcon icon={Mic01Icon} size="1em" aria-hidden="true" />,
  moreHorizontal: (
    <HugeiconsIcon icon={MoreHorizontalIcon} size="1em" aria-hidden="true" />
  ),
  viewColumns: (
    <HugeiconsIcon icon={LayoutTwoColumnIcon} size="1em" aria-hidden="true" />
  ),
  wrench: <HugeiconsIcon icon={Wrench01Icon} size="1em" aria-hidden="true" />,
  stop: <AppIcon name="stop" />,
};
