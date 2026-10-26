import { useEffect, useMemo, useState } from "react";
import {
  backend,
  type AuditSummary,
  type SelectionAudit,
} from "../../backend/client";
import { errorMessage } from "../../domain/errors";

const HISTORY_POLL_MS = 5_000;

export function useAudits() {
  const [audits, setAudits] = useState<AuditSummary[]>([]);
  const [limit, setLimit] = useState(100);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [record, setRecord] = useState<SelectionAudit | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyRevision, setHistoryRevision] = useState(0);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailRevision, setDetailRevision] = useState(0);
  useEffect(() => {
    let disposed = false;
    let timer: number | undefined;
    setHistoryLoading(true);
    const schedule = () => {
      if (disposed) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => void refresh(), HISTORY_POLL_MS);
    };
    const refresh = async () => {
      // A hidden window has nobody reading the list; the visibility listener
      // refreshes immediately when it is shown again.
      if (document.hidden) return;
      try {
        const response = await backend.auditHistory();
        if (disposed) return;
        setAudits(response.audits);
        setLimit(response.limit);
        setSelectedId((current) =>
          current && response.audits.some((item) => item.id === current)
            ? current
            : (response.audits[0]?.id ?? null),
        );
        setHistoryError(null);
      } catch (reason) {
        if (!disposed)
          setHistoryError(errorMessage(reason, "无法读取审计记录"));
      } finally {
        if (!disposed) {
          setHistoryLoading(false);
          schedule();
        }
      }
    };
    const onVisibilityChange = () => {
      if (!document.hidden) void refresh();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    void refresh();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [historyRevision]);
  const summary = useMemo(
    () => audits.find((item) => item.id === selectedId) ?? null,
    [audits, selectedId],
  );
  useEffect(() => {
    if (!selectedId) {
      setRecord(null);
      setDetailError(null);
      setDetailLoading(false);
      return;
    }
    let disposed = false;
    setDetailLoading(true);
    setDetailError(null);
    setRecord((current) => (current?.id === selectedId ? current : null));
    void backend
      .audit(selectedId)
      .then((value) => {
        if (!disposed) setRecord(value);
      })
      .catch((reason) => {
        if (!disposed)
          setDetailError(errorMessage(reason, "无法读取这轮审计详情"));
      })
      .finally(() => {
        if (!disposed) setDetailLoading(false);
      });
    return () => {
      disposed = true;
    };
  }, [detailRevision, selectedId, summary?.updatedAt]);
  return {
    audits,
    limit,
    selectedId,
    setSelectedId,
    record: record?.id === selectedId ? record : null,
    historyLoading,
    historyError,
    detailLoading,
    detailError,
    retryHistory: () => setHistoryRevision((value) => value + 1),
    retryDetail: () => setDetailRevision((value) => value + 1),
  };
}
