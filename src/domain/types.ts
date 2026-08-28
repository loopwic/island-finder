export type NormalizedRegion = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type FeatureVector = {
  luminance: number[];
  chroma: number[];
  edges: number[];
  colorHistogram: number[];
};

export type ScreenKind =
  | 'noSignal'
  | 'loading'
  | 'nameKeyboard'
  | 'birthdayPicker'
  | 'styleChoice'
  | 'appearanceEditor'
  | 'choiceDialog'
  | 'mapSelection'
  | 'homeMenu'
  | 'accountPicker'
  | 'dialogue'
  | 'startupPrompt'
  | 'unknown';

export type ScreenObservation = {
  kind: ScreenKind;
  confidence: number;
  signals: Record<string, number>;
};

export type TargetReference = {
  id: string;
  name: string;
  previewUrl: string;
  feature: FeatureVector;
};

export type IslandFactorKey =
  | 'coastalRocks'
  | 'airportPlaza'
  | 'peninsula'
  | 'foxBeach'
  | 'beachShape'
  | 'riverMouths';

export type FactorAssessment = {
  key: IslandFactorKey;
  label: string;
  score: number;
  passed: boolean;
  hard: boolean;
  summary: string;
};

export type IslanderIdentity = {
  name: string;
  namePinyin: string[];
  birthMonth: number;
  birthDay: number;
  initialStyle: 'left' | 'right';
};

export type FinderSettings = {
  identity: IslanderIdentity;
  birthdayCursorOrigin: { month: number; day: number };
  threshold: number;
  stableFrames: number;
  scanIntervalMs: number;
  autoReject: boolean;
  dryRun: boolean;
  captureDeviceIndex: number;
  captureDeviceId: string;
  captureDeviceName: string;
  captureWidth: number;
  captureHeight: number;
  captureFps: number;
  autoConnectController: boolean;
  cardRegions: NormalizedRegion[];
  targets: TargetReference[];
};

export type CandidateMatch = {
  analysisRevision?: string;
  analysisInputSha256?: string;
  cardIndex: number;
  score: number;
  targetId: string | null;
  targetName: string | null;
  hardPass: boolean;
  factors: FactorAssessment[];
  visualSimilarity: number | null;
  analysisConfidence: number;
  visionEngine: 'opencv';
};

export type RuntimePhase =
  | 'idle'
  | 'fastForwarding'
  | 'enteringName'
  | 'enteringBirthday'
  | 'scanning'
  | 'awaitingDecision'
  | 'restarting'
  | 'paused'
  | 'error';

export type RuntimeSnapshot = {
  phase: RuntimePhase;
  runNumber: number;
  startedAt: number | null;
  lastMessage: string;
  candidates: CandidateMatch[];
  selectedCandidate: CandidateMatch | null;
  currentScreen: ScreenKind;
  screenConfidence: number;
  stableHitCount: number;
};

export type LogLevel = 'info' | 'success' | 'warning' | 'error';

export type RuntimeLog = {
  id: number;
  at: number;
  level: LogLevel;
  message: string;
};
