import { DEFAULT_SETTINGS } from './defaults';
import type { FinderSettings } from './types';

const STORAGE_KEY = 'island-finder.settings.v2';

export function loadSettings(): FinderSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT_SETTINGS);
    const parsed = JSON.parse(raw) as Partial<FinderSettings>;
    const merged = { ...structuredClone(DEFAULT_SETTINGS), ...parsed };
    return {
      identity: { ...DEFAULT_SETTINGS.identity, ...parsed.identity },
      birthdayCursorOrigin: {
        ...DEFAULT_SETTINGS.birthdayCursorOrigin,
        ...parsed.birthdayCursorOrigin,
      },
      threshold: merged.threshold,
      stableFrames: merged.stableFrames,
      scanIntervalMs: merged.scanIntervalMs,
      autoReject: merged.autoReject,
      dryRun: merged.dryRun,
      captureDeviceIndex: merged.captureDeviceIndex,
      captureDeviceId: merged.captureDeviceId,
      captureDeviceName: merged.captureDeviceName,
      captureWidth: merged.captureWidth,
      captureHeight: merged.captureHeight,
      captureFps: merged.captureFps,
      autoConnectController: merged.autoConnectController,
      cardRegions: DEFAULT_SETTINGS.cardRegions.map((region) => ({ ...region })),
      targets: Array.isArray(parsed.targets) ? parsed.targets : [],
    };
  } catch {
    return structuredClone(DEFAULT_SETTINGS);
  }
}

export function saveSettings(settings: FinderSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}
