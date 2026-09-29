import type { TokenColor } from "@astryxdesign/core/Token";
import type { AuditStatus } from "../../backend/client";

export const auditLabels: Record<
  AuditStatus,
  { label: string; color: TokenColor }
> = {
  reviewing: { label: "判定中", color: "yellow" },
  candidate: { label: "待确认", color: "green" },
  accepted: { label: "已保留", color: "green" },
  rejected: { label: "自动放弃", color: "default" },
  userRejected: { label: "人工放弃", color: "default" },
  paused: { label: "已暂停", color: "yellow" },
  stopped: { label: "已停止", color: "default" },
  superseded: { label: "已被新轮替代", color: "default" },
  error: { label: "异常中止", color: "red" },
};
export const runLabel = (run: number) =>
  run > 0 ? `第 ${run} 轮` : "实测补录";
export const formatAuditTime = (time: number) =>
  new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(time);
