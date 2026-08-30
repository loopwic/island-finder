import type {
  CandidateMatch,
  FinderSettings,
  NormalizedRegion,
  RuntimeLog,
  RuntimeSnapshot,
} from '../domain/types';

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:48197';

export const BACKEND_URL = import.meta.env.VITE_ISLAND_FINDER_BACKEND_URL?.trim()
  || DEFAULT_BACKEND_URL;

export const BACKEND_STATE_STREAM_URL = (() => {
  const url = new URL('/v1/ws', BACKEND_URL);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.toString();
})();

export type BackendCaptureState = {
  connected: boolean;
  deviceIndex: number | null;
  deviceId?: string | null;
  deviceName?: string | null;
  width: number;
  height: number;
  fps: number;
  error: string | null;
  lastFrameAt?: number;
  captureBackend?: string | null;
};

export type CaptureDevice = {
  index: number;
  id: string;
  name: string;
  modelId?: string;
  devicePath?: string | null;
  backend?: number;
  vendorId?: number | null;
  productId?: number | null;
  preferred: boolean;
  usbLinkMbps: number | null;
  transportCodec: string | null;
};

export type CaptureDevicesResponse = {
  devices: CaptureDevice[];
  selectedIndex: number;
  selectedId: string;
  selectedName: string;
};

export type BackendControllerState = {
  active: boolean;
  connected: boolean;
  message: string;
  transport: string | null;
  serialPort?: string | null;
};

export type BackendState = {
  ok: true;
  mode: 'headless-backend';
  version: string;
  instanceId: string;
  runtime: RuntimeSnapshot;
  capture: BackendCaptureState;
  controller: BackendControllerState;
  settings: FinderSettings;
  logs: RuntimeLog[];
};

export type BackendStateStreamMessage = {
  type: 'state' | 'heartbeat';
  sequence: number;
  sentAt: number;
  state?: BackendState;
};

export type AuditStatus =
  | 'reviewing'
  | 'candidate'
  | 'accepted'
  | 'rejected'
  | 'userRejected'
  | 'paused'
  | 'stopped'
  | 'superseded'
  | 'error';

export type AuditCard = {
  cardIndex: number;
  file: string;
  width: number;
  height: number;
  sha256?: string;
  analysisInputSha256?: string;
};

export type SelectionAudit = {
  id: string;
  createdAt: number;
  updatedAt: number;
  runNumber: number;
  status: AuditStatus;
  summary: string;
  decision: string | null;
  threshold: number;
  stableFrames: number;
  autoReject: boolean;
  frameWidth: number;
  frameHeight: number;
  frameFile: string;
  frameSha256?: string;
  evidenceRevision?: number;
  regions: NormalizedRegion[];
  cards: AuditCard[];
  candidates: CandidateMatch[];
  decisionCandidates?: CandidateMatch[];
  bestCardIndex: number | null;
  bestScore: number | null;
  decisionBestCardIndex?: number | null;
  decisionBestScore?: number | null;
  selectedCardIndex?: number | null;
  stableHitCount?: number;
  scanSampleCount?: number;
  reanalyzedAt?: number;
  previousAnalyses?: Array<{
    analysisRevision?: string;
    archivedAt: number;
    candidates: CandidateMatch[];
  }>;
};

export type AuditSummary = Pick<
  SelectionAudit,
  | 'id'
  | 'createdAt'
  | 'updatedAt'
  | 'runNumber'
  | 'status'
  | 'summary'
  | 'decision'
  | 'bestCardIndex'
  | 'bestScore'
  | 'selectedCardIndex'
>;

export type AuditHistoryResponse = {
  audits: AuditSummary[];
  limit: number;
};

async function request<T>(path: string, init?: RequestInit, timeoutMs = 8_000): Promise<T> {
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BACKEND_URL}${path}`, {
      cache: 'no-store',
      ...init,
      signal: controller.signal,
    });
    const payload = await response.json().catch(() => ({})) as T & { error?: string };
    if (!response.ok) throw new Error(payload.error ?? `后端返回 ${response.status}`);
    return payload;
  } catch (reason) {
    if (controller.signal.aborted) {
      throw new Error(`后端请求超过 ${Math.round(timeoutMs / 1_000)} 秒，请重试`);
    }
    if (reason instanceof TypeError) {
      throw new Error('无法连接本机后端，系统正在尝试恢复');
    }
    throw reason;
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

export const backend = {
  state: () => request<BackendState>('/v1/state', undefined, 2_500),
  openStateStream: () => new WebSocket(BACKEND_STATE_STREAM_URL),
  captureDevices: () => request<CaptureDevicesResponse>('/v1/capture-devices'),
  auditHistory: () => request<AuditHistoryResponse>('/v1/audits'),
  audit: (auditId: string) => request<SelectionAudit>(`/v1/audits/${encodeURIComponent(auditId)}`),
  auditImageUrl: (auditId: string, filename: string) => (
    `${BACKEND_URL}/v1/audits/${encodeURIComponent(auditId)}/images/${encodeURIComponent(filename)}`
  ),
  saveSettings: (settings: FinderSettings) => request<FinderSettings>('/v1/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  }),
  armStart: (instanceId: string) => request<{ startToken: string }>('/v1/actions/arm-start', {
    method: 'POST',
    headers: { 'X-Island-Finder-Instance': instanceId },
  }),
  action: (action: string, instanceId: string, startToken?: string) => request<BackendState>(`/v1/actions/${action}`, {
    method: 'POST',
    headers: {
      'X-Island-Finder-Instance': instanceId,
      ...(startToken ? { 'X-Island-Finder-Start-Token': startToken } : {}),
    },
  }),
  clearLogs: () => request<{ ok: true }>('/v1/logs/clear', { method: 'POST' }),
  streamUrl: `${BACKEND_URL}/v1/stream.mjpg`,
};
