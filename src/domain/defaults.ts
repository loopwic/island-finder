import type { FinderSettings, RuntimeSnapshot } from './types';

export const DEFAULT_SETTINGS: FinderSettings = {
  identity: {
    name: '',
    namePinyin: [],
    birthMonth: 1,
    birthDay: 1,
    initialStyle: 'right',
  },
  birthdayCursorOrigin: { month: 1, day: 1 },
  threshold: 0.76,
  stableFrames: 3,
  scanIntervalMs: 320,
  autoReject: true,
  dryRun: true,
  captureDeviceIndex: 0,
  captureDeviceId: '',
  captureDeviceName: '',
  captureWidth: 1920,
  captureHeight: 1080,
  captureFps: 30,
  autoConnectController: true,
  cardRegions: [
    { x: 0.249, y: 0.291, width: 0.232, height: 0.253 },
    { x: 0.52, y: 0.296, width: 0.232, height: 0.251 },
    { x: 0.2495, y: 0.5715, width: 0.23, height: 0.247 },
    { x: 0.5205, y: 0.5685, width: 0.2305, height: 0.2525 },
  ],
  targets: [],
};

export const INITIAL_RUNTIME: RuntimeSnapshot = {
  phase: 'idle',
  runNumber: 0,
  startedAt: null,
  lastMessage: '等待配置',
  candidates: [],
  selectedCandidate: null,
  currentScreen: 'unknown',
  screenConfidence: 0,
  stableHitCount: 0,
};
