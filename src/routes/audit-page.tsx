import { Alert, Button, Card, Chip, Separator } from '@heroui/react';
import {
  CheckCircle2,
  ChevronRight,
  CircleX,
  Clock3,
  ExternalLink,
  FileImage,
  LoaderCircle,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  backend,
  type AuditStatus,
  type SelectionAudit,
} from '../backend/client';

const formatter = new Intl.DateTimeFormat('zh-CN', {
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

const auditStatus: Record<AuditStatus, {
  label: string;
  color: 'default' | 'success' | 'warning' | 'danger';
}> = {
  reviewing: { label: '判定中', color: 'warning' },
  candidate: { label: '待确认', color: 'success' },
  accepted: { label: '已保留', color: 'success' },
  rejected: { label: '自动放弃', color: 'danger' },
  userRejected: { label: '人工放弃', color: 'danger' },
  paused: { label: '已暂停', color: 'warning' },
  stopped: { label: '已停止', color: 'default' },
  superseded: { label: '已被新轮替代', color: 'default' },
  error: { label: '异常中止', color: 'danger' },
};

function StatusChip({ status }: { status: AuditStatus }) {
  const meta = auditStatus[status] ?? auditStatus.stopped;
  return (
    <Chip color={meta.color} size="sm" variant="soft">
      <Chip.Label>{meta.label}</Chip.Label>
    </Chip>
  );
}

function runLabel(runNumber: number) {
  return runNumber > 0 ? `第 ${runNumber} 轮` : '实测补录';
}

function RecordList({
  audits,
  limit,
  selectedId,
  onSelect,
}: {
  audits: SelectionAudit[];
  limit: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <Card className="min-w-0 overflow-hidden xl:sticky xl:top-20">
      <Card.Header>
        <div className="flex w-full items-center gap-3">
          <Clock3 aria-hidden="true" className="text-muted shrink-0" size={19} />
          <div className="min-w-0">
            <Card.Title>选图记录</Card.Title>
            <Card.Description>最新判定优先</Card.Description>
          </div>
          <Chip className="ml-auto shrink-0" size="sm" variant="soft">
            <Chip.Label>{audits.length} / {limit}</Chip.Label>
          </Chip>
        </div>
      </Card.Header>
      <Separator />
      <Card.Content className="p-2 xl:max-h-[calc(100vh-12rem)] xl:overflow-y-auto">
        <div className="grid gap-1 sm:grid-cols-2 xl:grid-cols-1">
          {audits.map((record) => {
            const selected = record.id === selectedId;
            return (
              <Button
                fullWidth
                aria-pressed={selected}
                aria-current={selected ? 'true' : undefined}
                className="h-auto justify-start rounded-xl p-3 text-left"
                key={record.id}
                variant={selected ? 'secondary' : 'ghost'}
                onPress={() => onSelect(record.id)}
              >
                <div className="w-full min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <strong className="text-sm font-semibold">{runLabel(record.runNumber)}</strong>
                    <div className="flex shrink-0 items-center gap-1">
                      <StatusChip status={record.status} />
                      <ChevronRight className={selected ? 'text-accent shrink-0' : 'text-muted shrink-0'} size={15} />
                    </div>
                  </div>
                  <p className="text-muted mt-2 line-clamp-2 text-xs leading-5">{record.summary}</p>
                  <div className="text-muted mt-2 flex items-center justify-between gap-2 text-xs">
                    <time dateTime={new Date(record.createdAt).toISOString()}>
                      {formatter.format(record.createdAt)}
                    </time>
                    <span className="font-medium">
                      {record.bestScore === null ? '无评分' : `${(record.bestScore * 100).toFixed(1)}%`}
                    </span>
                  </div>
                </div>
              </Button>
            );
          })}
        </div>
      </Card.Content>
    </Card>
  );
}

function AuditDetail({ record }: { record: SelectionAudit }) {
  const frameUrl = backend.auditImageUrl(record.id, record.frameFile);
  return (
    <div className="min-w-0 space-y-4">
      <Card className="min-w-0 overflow-hidden">
        <Card.Header>
          <div className="flex w-full flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Card.Title>{runLabel(record.runNumber)}选图证据</Card.Title>
                <StatusChip status={record.status} />
              </div>
              <Card.Description className="mt-1">
                {formatter.format(record.createdAt)} · {record.frameWidth}×{record.frameHeight} · 识别规则 {record.candidates[0]?.analysisRevision ?? '旧版'}
                {record.frameSha256 ? ` · 同帧证据 #${record.evidenceRevision ?? 1}` : ''}
              </Card.Description>
            </div>
            <a
              className="text-accent inline-flex items-center gap-1.5 text-sm font-medium hover:underline"
              href={frameUrl}
              rel="noreferrer"
              target="_blank"
            >
              查看原图<ExternalLink size={14} />
            </a>
          </div>
        </Card.Header>
        <Separator />
        <Card.Content className="space-y-4 p-4">
          <div className="border-border bg-black/85 overflow-hidden rounded-xl border">
            <img
              alt={`第 ${record.runNumber} 轮四岛选择完整画面`}
              className="aspect-video h-auto w-full object-contain"
              src={frameUrl}
            />
          </div>
          <div className="border-border bg-border grid gap-px overflow-hidden rounded-xl border sm:grid-cols-2 lg:grid-cols-4">
            <div className="bg-surface p-3">
              <div className="text-muted text-xs">判定阈值</div>
              <div className="mt-1 text-sm font-semibold">{(record.threshold * 100).toFixed(0)}%</div>
            </div>
            <div className="bg-surface p-3">
              <div className="text-muted text-xs">最高评分</div>
              <div className="mt-1 text-sm font-semibold">
                {record.bestScore === null ? '—' : `${(record.bestScore * 100).toFixed(1)}%`}
              </div>
            </div>
            <div className="bg-surface p-3">
              <div className="text-muted text-xs">最高地图</div>
              <div className="mt-1 text-sm font-semibold">
                {record.bestCardIndex === null ? '—' : `地图 ${record.bestCardIndex + 1}`}
              </div>
            </div>
            <div className="bg-surface p-3">
              <div className="text-muted text-xs">稳定门槛</div>
              <div className="mt-1 text-sm font-semibold">{record.stableFrames} 帧</div>
            </div>
          </div>
          <Alert status={record.status === 'accepted' || record.status === 'candidate' ? 'success' : record.status === 'error' ? 'danger' : 'warning'}>
            <Alert.Indicator />
            <Alert.Content>
              <Alert.Title>{record.decision ?? '识别结论'}</Alert.Title>
              <Alert.Description>{record.summary}</Alert.Description>
            </Alert.Content>
          </Alert>
          {record.reanalyzedAt && (
            <Alert status="default">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Title>已用当前规则离线重算</Alert.Title>
                <Alert.Description>
                  {formatter.format(record.reanalyzedAt)} 使用 {record.candidates[0]?.analysisRevision ?? '当前版本'} 重算下方因子；
                  顶部仍保留当时的自动操作结论，历史版本 {record.previousAnalyses?.map((item) => item.analysisRevision ?? '旧版').join(' → ') ?? '旧版'} 均未被覆盖。
                </Alert.Description>
              </Alert.Content>
            </Alert>
          )}
        </Card.Content>
      </Card>

      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        {record.cards.map((card) => {
          const candidate = record.candidates.find((item) => item.cardIndex === card.cardIndex);
          const selected = record.selectedCardIndex === card.cardIndex;
          return (
            <Card
              className={`min-w-0 overflow-hidden ${selected ? 'ring-success ring-2' : ''}`}
              key={card.cardIndex}
            >
              <Card.Header>
                <div className="flex w-full items-center justify-between gap-3">
                  <div className="min-w-0">
                    <Card.Title>地图 {card.cardIndex + 1}</Card.Title>
                    <Card.Description>
                      {card.width}×{card.height} · 识别可信度 {candidate ? `${(candidate.analysisConfidence * 100).toFixed(0)}%` : '—'}
                    </Card.Description>
                  </div>
                  <Chip color={candidate?.hardPass ? 'success' : 'danger'} size="sm" variant="soft">
                    <Chip.Label>
                      {candidate ? `${(candidate.score * 100).toFixed(1)}%` : '无结果'}
                    </Chip.Label>
                  </Chip>
                </div>
              </Card.Header>
              <div className="border-border bg-black/85 border-y">
                <img
                  alt={`第 ${record.runNumber} 轮地图 ${card.cardIndex + 1} 裁切图`}
                  className="aspect-[1.72] h-auto w-full object-contain"
                  loading="lazy"
                  src={backend.auditImageUrl(record.id, card.file)}
                />
              </div>
              <Card.Content className="p-0">
                {candidate?.factors.map((factor, index) => (
                  <div key={factor.key}>
                    {index > 0 && <Separator />}
                    <div className="flex items-start gap-3 px-4 py-3">
                      {factor.passed
                        ? <CheckCircle2 className="text-success mt-0.5 shrink-0" size={17} />
                        : <CircleX className="text-danger mt-0.5 shrink-0" size={17} />}
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <strong className="text-sm font-medium">{factor.label}</strong>
                          <div className="flex items-center gap-2">
                            {factor.hard && (
                              <Chip color="warning" size="sm" variant="soft">
                                <Chip.Label>硬条件</Chip.Label>
                              </Chip>
                            )}
                            <span className="text-muted text-xs">{(factor.score * 100).toFixed(0)}%</span>
                          </div>
                        </div>
                        <p className="text-muted mt-1 text-xs leading-5">{factor.summary}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </Card.Content>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

export function AuditPage() {
  const [audits, setAudits] = useState<SelectionAudit[]>([]);
  const [limit, setLimit] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    const refresh = async () => {
      try {
        const response = await backend.auditHistory();
        if (disposed) return;
        setAudits(response.audits);
        setLimit(response.limit);
        setSelectedId((current) => (
          current && response.audits.some((record) => record.id === current)
            ? current
            : response.audits[0]?.id ?? null
        ));
        setError(null);
      } catch (reason) {
        if (!disposed) setError(reason instanceof Error ? reason.message : '无法读取审计记录');
      } finally {
        if (!disposed) setLoading(false);
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, []);

  const selected = useMemo(
    () => audits.find((record) => record.id === selectedId) ?? null,
    [audits, selectedId],
  );

  if (loading) {
    return (
      <div className="text-muted grid min-h-[28rem] place-items-center text-sm">
        <span className="flex items-center gap-2"><LoaderCircle className="animate-spin" size={18} />正在读取后端审计记录</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <Alert status="danger">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Title>审计接口未响应</Alert.Title>
            <Alert.Description>{error}</Alert.Description>
          </Alert.Content>
        </Alert>
      )}

      {audits.length === 0 ? (
        <Card>
          <Card.Content className="p-8">
            <div className="grid min-h-[20rem] w-full place-items-center text-center">
              <div>
                <FileImage className="text-muted mx-auto" size={30} />
                <h2 className="mt-3 text-base font-semibold">还没有选图记录</h2>
                <p className="text-muted mt-1 max-w-md text-sm leading-6">
                  后端第一次可靠识别到四岛地图页时，会自动保存原始画面、四张地图裁切和因素判定。
                </p>
              </div>
            </div>
          </Card.Content>
        </Card>
      ) : (
        <div className="grid min-w-0 items-start gap-4 xl:grid-cols-[21rem_minmax(0,1fr)]">
          <RecordList audits={audits} limit={limit} selectedId={selectedId} onSelect={setSelectedId} />
          {selected && <AuditDetail record={selected} />}
        </div>
      )}
    </div>
  );
}
