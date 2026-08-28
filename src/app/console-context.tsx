import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { backend, type BackendState } from '../backend/client';
import { normalizePinyin, validateChineseName } from '../controller/keyboard';
import { DEFAULT_SETTINGS, INITIAL_RUNTIME } from '../domain/defaults';
import { loadSettings } from '../domain/storage';
import type { FinderSettings } from '../domain/types';
import { referenceFromFile } from '../vision/features';

type ConsoleContextValue = {
  state: BackendState | null;
  settings: FinderSettings;
  settingsLoaded: boolean;
  settingsSyncState: 'loading' | 'saving' | 'saved' | 'error';
  runtime: BackendState['runtime'];
  capture: BackendState['capture'];
  controller: BackendState['controller'];
  logs: BackendState['logs'];
  notice: string | null;
  active: boolean;
  identityReady: boolean;
  ready: boolean;
  updateSettings: (patch: Partial<FinderSettings>) => void;
  updateIdentity: (patch: Partial<FinderSettings['identity']>) => void;
  updateName: (value: string) => void;
  updatePinyin: (index: number, value: string) => void;
  runAction: (name: string) => Promise<void>;
  addTargets: (files: FileList | null) => Promise<void>;
  removeTarget: (id: string) => void;
  clearLogs: () => Promise<void>;
};

const ConsoleContext = createContext<ConsoleContextValue | null>(null);

function isIdentityReady(identity: FinderSettings['identity']): boolean {
  try {
    validateChineseName(identity.name, identity.namePinyin);
    return true;
  } catch {
    return false;
  }
}

export function ConsoleProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<BackendState | null>(null);
  const [settings, setSettings] = useState<FinderSettings>(() => structuredClone(DEFAULT_SETTINGS));
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [settingsSyncState, setSettingsSyncState] = useState<'loading' | 'saving' | 'saved' | 'error'>('loading');
  const [notice, setNotice] = useState<string | null>(null);
  const settingsHydrated = useRef(false);
  const settingsDirty = useRef(false);
  const settingsEditRevision = useRef(0);
  const saveTimer = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    const refresh = async (showError = false, syncSettings = false) => {
      try {
        let next = await backend.state();
        if (cancelled) return;

        if (!settingsHydrated.current) {
          const local = loadSettings();
          if (!next.settings.identity.name && local.identity.name) {
            const migrated = await backend.saveSettings({ ...next.settings, ...local });
            if (cancelled) return;
            next = { ...next, settings: migrated };
            setNotice('已将浏览器里的旧配置迁移到常驻后端');
          }
          setSettings(next.settings);
          settingsHydrated.current = true;
          settingsDirty.current = false;
          setSettingsLoaded(true);
          setSettingsSyncState('saved');
        } else if (syncSettings && !settingsDirty.current) {
          setSettings(next.settings);
          setSettingsSyncState('saved');
        }
        setState(next);
      } catch (error) {
        if (!cancelled) {
          setState(null);
          if (showError) setNotice(error instanceof Error ? error.message : String(error));
        }
      }
    };

    const syncSettingsOnFocus = () => void refresh(false, true);

    void refresh(true, true);
    const interval = window.setInterval(() => void refresh(false), 500);
    window.addEventListener('focus', syncSettingsOnFocus);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
      window.removeEventListener('focus', syncSettingsOnFocus);
    };
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(null), 3_500);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  useEffect(() => {
    if (!settingsLoaded || !settingsDirty.current) return;
    if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);
    const editRevision = settingsEditRevision.current;
    saveTimer.current = window.setTimeout(() => {
      saveTimer.current = null;
      void backend.saveSettings(settings)
        .then((saved) => {
          if (editRevision !== settingsEditRevision.current) return;
          settingsDirty.current = false;
          setSettings(saved);
          setSettingsSyncState('saved');
        })
        .catch((error) => {
          if (editRevision !== settingsEditRevision.current) return;
          setSettingsSyncState('error');
          setNotice(error instanceof Error ? error.message : String(error));
        });
    }, 450);
    return () => {
      if (saveTimer.current !== null) {
        window.clearTimeout(saveTimer.current);
        saveTimer.current = null;
      }
    };
  }, [settings, settingsLoaded]);

  const markSettingsDirty = (): boolean => {
    if (!settingsHydrated.current) return false;
    settingsDirty.current = true;
    settingsEditRevision.current += 1;
    setSettingsSyncState('saving');
    return true;
  };

  const updateSettings = (patch: Partial<FinderSettings>) => {
    if (!markSettingsDirty()) return;
    setSettings((current) => ({
      ...current,
      ...patch,
      ...(patch.captureDeviceIndex !== undefined
        && patch.captureDeviceIndex !== current.captureDeviceIndex
        && patch.captureDeviceId === undefined
        ? { captureDeviceId: '', captureDeviceName: '' }
        : {}),
    }));
  };

  const updateIdentity = (patch: Partial<FinderSettings['identity']>) => {
    if (!markSettingsDirty()) return;
    setSettings((current) => ({
      ...current,
      identity: { ...current.identity, ...patch },
    }));
  };

  const updateName = (value: string) => {
    const name = Array.from(value).slice(0, 10).join('');
    if (!markSettingsDirty()) return;
    setSettings((current) => ({
      ...current,
      identity: {
        ...current.identity,
        name,
        namePinyin: Array.from(name).map((_, index) => current.identity.namePinyin[index] ?? ''),
      },
    }));
  };

  const updatePinyin = (index: number, value: string) => {
    if (!markSettingsDirty()) return;
    setSettings((current) => {
      const namePinyin = [...current.identity.namePinyin];
      namePinyin[index] = normalizePinyin(value);
      return {
        ...current,
        identity: { ...current.identity, namePinyin },
      };
    });
  };

  const runAction = async (name: string) => {
    try {
      if (!state?.instanceId) throw new Error('后端会话尚未就绪，请稍后重试');
      if (name === 'start' && !settingsLoaded) throw new Error('后端配置尚未读取完成，请稍后重试');
      if (saveTimer.current !== null) {
        window.clearTimeout(saveTimer.current);
        saveTimer.current = null;
      }
      if (settingsDirty.current) {
        const editRevision = settingsEditRevision.current;
        const saved = await backend.saveSettings(settings);
        if (editRevision === settingsEditRevision.current) {
          settingsDirty.current = false;
          setSettings(saved);
          setSettingsSyncState('saved');
        }
      }
      setState(await backend.action(name, state.instanceId));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  };

  const addTargets = async (files: FileList | null) => {
    if (!files?.length) return;
    try {
      const references = await Promise.all([...files].map(referenceFromFile));
      if (!markSettingsDirty()) return;
      setSettings((current) => ({ ...current, targets: [...current.targets, ...references] }));
      setNotice(`已添加 ${references.length} 张辅助地图样例`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  };

  const removeTarget = (id: string) => {
    if (!markSettingsDirty()) return;
    setSettings((current) => ({
      ...current,
      targets: current.targets.filter((target) => target.id !== id),
    }));
  };

  const clearLogs = async () => {
    try {
      await backend.clearLogs();
      setState((current) => current ? { ...current, logs: [] } : current);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  };

  const runtime = state?.runtime ?? INITIAL_RUNTIME;
  const capture = state?.capture ?? {
    connected: false,
    deviceIndex: null,
    width: 0,
    height: 0,
    fps: 0,
    error: '正在连接常驻后端',
  };
  const controller = state?.controller ?? {
    active: false,
    connected: false,
    message: '正在连接常驻后端',
    transport: null,
  };
  const logs = state?.logs ?? [];
  const active = !['idle', 'paused', 'error'].includes(runtime.phase);
  const identityReady = settingsLoaded && isIdentityReady(settings.identity);
  const ready = settingsLoaded && capture.connected && identityReady && (settings.dryRun || controller.connected);

  return (
    <ConsoleContext.Provider value={{
      state,
      settings,
      settingsLoaded,
      settingsSyncState,
      runtime,
      capture,
      controller,
      logs,
      notice,
      active,
      identityReady,
      ready,
      updateSettings,
      updateIdentity,
      updateName,
      updatePinyin,
      runAction,
      addTargets,
      removeTarget,
      clearLogs,
    }}>
      {children}
    </ConsoleContext.Provider>
  );
}

export function useConsole(): ConsoleContextValue {
  const value = useContext(ConsoleContext);
  if (!value) throw new Error('useConsole must be used inside ConsoleProvider');
  return value;
}
