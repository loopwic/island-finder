import { useEffect, useMemo, useState } from "react";
import {
  backend,
  type AuditSummary,
  type SelectionAudit,
} from "../../backend/client";

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
    const refresh = async () => {
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
          setHistoryError(
            reason instanceof Error ? reason.message : "无法读取审计记录",
          );
      } finally {
        if (!disposed) {
          setHistoryLoading(false);
          timer = window.setTimeout(() => void refresh(), 5000);
        }
      }
    };
    void refresh();
    return () => {
      disposed = true;
      if (timer !== undefined) window.clearTimeout(timer);
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
          setDetailError(
            reason instanceof Error ? reason.message : "无法读取这轮审计详情",
          );
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
