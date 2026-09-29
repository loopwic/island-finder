import type {
  RuntimePhase,
  RuntimeSnapshot,
  ScreenKind,
} from "../../domain/types";
export const phaseLabels: Record<RuntimePhase, string> = {
  idle: "待机",
  fastForwarding: "快速推进",
  enteringName: "输入名字",
  enteringBirthday: "输入生日",
  scanning: "识别地图",
  awaitingDecision: "等待决定",
  restarting: "重开游戏",
  paused: "已暂停",
  error: "异常停止",
};
export const screenLabels: Record<ScreenKind, string> = {
  noSignal: "无信号",
  loading: "加载中",
  nameKeyboard: "名字键盘",
  birthdayPicker: "生日选择",
  styleChoice: "初始造型",
  appearanceEditor: "形象编辑",
  choiceDialog: "选项确认",
  mapSelection: "四岛地图",
  homeMenu: "Switch 主界面",
  accountPicker: "游玩账号",
  dialogue: "对话",
  startupPrompt: "启动提示",
  unknown: "等待识别",
};
export function calculateFlowProgress(
  runtime: RuntimeSnapshot,
  stableFrames: number,
) {
  if (runtime.phase === "idle") return 0;
  if (runtime.phase === "restarting") return 5;
  if (runtime.phase === "awaitingDecision") return 100;
  if (runtime.phase === "scanning")
    return Math.round(
      90 + Math.min(1, runtime.stableHitCount / Math.max(1, stableFrames)) * 8,
    );
  if (runtime.phase === "enteringName") return 35;
  if (runtime.phase === "enteringBirthday") return 55;
  const progress: Partial<Record<ScreenKind, number>> = {
    nameKeyboard: 30,
    birthdayPicker: 50,
    styleChoice: 65,
    appearanceEditor: 75,
    mapSelection: 90,
    homeMenu: 8,
    accountPicker: 10,
    choiceDialog: 20,
    dialogue: 18,
    startupPrompt: 12,
  };
  return progress[runtime.currentScreen] ?? 10;
}
export function formatElapsed(startedAt: number | null) {
  const seconds = startedAt
    ? Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
    : 0;
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
