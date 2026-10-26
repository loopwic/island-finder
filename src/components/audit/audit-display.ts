import type { AuditStatus } from "../../backend/client";
import type { StatusTone } from "../core/status-label";

export const auditLabels: Record<
  AuditStatus,
  { label: string; tone: StatusTone }
> = {
  reviewing: { label: "判定中", tone: "running" },
  candidate: { label: "待确认", tone: "warning" },
  accepted: { label: "已保留", tone: "success" },
  rejected: { label: "自动放弃", tone: "neutral" },
  userRejected: { label: "人工放弃", tone: "neutral" },
  paused: { label: "已暂停", tone: "warning" },
  stopped: { label: "已停止", tone: "neutral" },
  superseded: { label: "已被新轮替代", tone: "neutral" },
  error: { label: "异常中止", tone: "error" },
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
