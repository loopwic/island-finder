import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import {
  backend,
  type BackendState,
  type BackendStateStreamMessage,
} from '../backend/client';
import type { BackendConnectionStatus } from '../backend/connection';
import { detectNameInputMode, normalizePinyin, validateName } from '../domain/name-input';
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
  connectionStatus: BackendConnectionStatus;
  connectionError: string | null;
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
  reconnect: () => Promise<void>;
};

const ConsoleContext = createContext<ConsoleContextValue | null>(null);

function isIdentityReady(identity: FinderSettings['identity']): boolean {
  try {
    validateName(identity.name, identity.namePinyin);
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
  const [connectionStatus, setConnectionStatus] = useState<BackendConnectionStatus>('connecting');
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const settingsHydrated = useRef(false);
  const settingsDirty = useRef(false);
  const settingsEditRevision = useRef(0);
  const saveTimer = useRef<number | null>(null);
  const reconnectStateStream = useRef<(() => void) | null>(null);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let reconnectAttempt = 0;
    let openedAt = Date.now();
    let lastMessageAt = 0;
    let hydratingSettings = false;
    let pendingInitialState: BackendState | null = null;
    let syncSettingsOnNextState = true;

    const clearReconnectTimer = () => {
      if (reconnectTimer === null) return;
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    };

    const acceptState = (next: BackendState) => {
      lastMessageAt = Date.now();
      reconnectAttempt = 0;
      setState(next);
      setConnectionStatus('connected');
      setConnectionError(null);

      if (settingsHydrated.current) {
        if (syncSettingsOnNextState && !settingsDirty.current) {
          setSettings(next.settings);
          setSettingsSyncState('saved');
        }
        syncSettingsOnNextState = false;
        return;
      }

      pendingInitialState = next;
      if (hydratingSettings) return;
      hydratingSettings = true;
      void (async () => {
        try {
          let initial = pendingInitialState;
          pendingInitialState = null;
          if (!initial) return;
          const local = loadSettings();
          if (!initial.settings.identity.name && local.identity.name) {
            const migrated = await backend.saveSettings({ ...initial.settings, ...local });
            if (cancelled) return;
            initial = { ...initial, settings: migrated };
            setState(initial);
            setNotice('已将浏览器里的旧配置迁移到常驻后端');
          }
          if (cancelled) return;
          setSettings(initial.settings);
          settingsHydrated.current = true;
          settingsDirty.current = false;
          syncSettingsOnNextState = false;
          setSettingsLoaded(true);
          setSettingsSyncState('saved');
        } catch (error) {
          if (cancelled) return;
          setSettingsSyncState('error');
          setNotice(error instanceof Error ? error.message : String(error));
        } finally {
          hydratingSettings = false;
        }
      })();
    };

    const scheduleReconnect = () => {
      if (cancelled || reconnectTimer !== null) return;
      const delay = Math.min(5_000, 400 * (2 ** Math.min(reconnectAttempt, 4)));
      reconnectAttempt += 1;
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, delay);
    };

    const connect = () => {
      if (cancelled) return;
      clearReconnectTimer();
      openedAt = Date.now();
      lastMessageAt = 0;
      setConnectionStatus((current) => current === 'connected' ? 'recovering' : 'connecting');
      try {
        const nextSocket = backend.openStateStream();
        socket = nextSocket;
        nextSocket.addEventListener('open', () => {
          if (cancelled || socket !== nextSocket) return;
          openedAt = Date.now();
        });
        nextSocket.addEventListener('message', (event) => {
          if (cancelled || socket !== nextSocket) return;
          try {
            const message = JSON.parse(String(event.data)) as BackendStateStreamMessage;
            lastMessageAt = Date.now();
            setConnectionStatus('connected');
            setConnectionError(null);
            if (message.type === 'state' && message.state) acceptState(message.state);
          } catch {
            setConnectionStatus('recovering');
            setConnectionError('后端状态通道返回了无法解析的数据，正在等待下一帧');
          }
        });
        nextSocket.addEventListener('close', () => {
          if (cancelled || socket !== nextSocket) return;
          socket = null;
          setConnectionStatus('recovering');
          setConnectionError('后端状态通道已断开，正在自动重连');
          scheduleReconnect();
        });
        nextSocket.addEventListener('error', () => {
          if (cancelled || socket !== nextSocket) return;
          setConnectionStatus('recovering');
        });
      } catch (error) {
        setConnectionStatus('recovering');
        setConnectionError(error instanceof Error ? error.message : String(error));
        scheduleReconnect();
      }
    };

    reconnectStateStream.current = () => {
      clearReconnectTimer();
      reconnectAttempt = 0;
      syncSettingsOnNextState = true;
      const previous = socket;
      socket = null;
      previous?.close(1000, 'manual reconnect');
      connect();
    };

    const staleTimer = window.setInterval(() => {
      const staleFor = Date.now() - (lastMessageAt || openedAt);
      if (staleFor < 10_000) return;
      if (staleFor < 30_000) {
        setConnectionStatus('recovering');
        setConnectionError('状态流暂时没有新消息，自动化仍在后端运行');
        return;
      }
      setConnectionStatus('disconnected');
      setConnectionError('状态流已超过 30 秒没有响应，正在重新建立连接');
      const previous = socket;
      socket = null;
      previous?.close(4000, 'state stream stale');
      scheduleReconnect();
    }, 1_000);

    connect();
    return () => {
      cancelled = true;
      reconnectStateStream.current = null;
      clearReconnectTimer();
      window.clearInterval(staleTimer);
      const previous = socket;
      socket = null;
      previous?.close(1000, 'view closed');
    };
  }, []);

  const reconnect = async () => {
    setConnectionStatus('connecting');
    setConnectionError(null);
    reconnectStateStream.current?.();
  };

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
    const truncated = Array.from(value).slice(0, 10).join('');
    const name = /^[a-z]*$/i.test(truncated) ? truncated.toLowerCase() : truncated;
    if (!markSettingsDirty()) return;
    setSettings((current) => ({
      ...current,
      identity: {
        ...current.identity,
        name,
        namePinyin: detectNameInputMode(name) === 'english'
          ? []
          : Array.from(name).map((_, index) => current.identity.namePinyin[index] ?? ''),
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
      const startToken = name === 'start'
        ? (await backend.armStart(state.instanceId)).startToken
        : undefined;
      setState(await backend.action(name, state.instanceId, startToken));
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
      connectionStatus,
      connectionError,
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
      reconnect,
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
