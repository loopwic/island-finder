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

export type AuditHistoryResponse = {
  audits: SelectionAudit[];
  limit: number;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BACKEND_URL}${path}`, { cache: 'no-store', ...init });
  const payload = await response.json().catch(() => ({})) as T & { error?: string };
  if (!response.ok) throw new Error(payload.error ?? `后端返回 ${response.status}`);
  return payload;
}

export const backend = {
  state: () => request<BackendState>('/v1/state'),
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
  action: (action: string, instanceId: string) => request<BackendState>(`/v1/actions/${action}`, {
    method: 'POST',
    headers: { 'X-Island-Finder-Instance': instanceId },
  }),
  clearLogs: () => request<{ ok: true }>('/v1/logs/clear', { method: 'POST' }),
  streamUrl: `${BACKEND_URL}/v1/stream.mjpg`,
};
