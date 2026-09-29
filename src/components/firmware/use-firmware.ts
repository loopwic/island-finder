import { useEffect, useRef, useState } from 'react';
import { useConsole } from '../../app/console-context';
import {
  backend,
  type FirmwareConfirmation,
  type FirmwareImage,
  type FirmwarePort,
  type FirmwareStatus,
} from '../../backend/client';

export function useFirmware() {
  const { state, runtime, connectionStatus } = useConsole();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<'setup' | 'confirm' | 'progress'>('setup');
  const [ports, setPorts] = useState<FirmwarePort[]>([]);
  const [port, setPort] = useState('');
  const [image, setImage] = useState<FirmwareImage | null | undefined>();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<FirmwareConfirmation | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [baud, setBaud] = useState(460800);
  const [backupRequested, setBackupRequested] = useState(false);
  const [started, setStarted] = useState<FirmwareStatus | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const instance = state?.instanceId;
  const session = useRef(instance);
  session.current = instance;
  const remote = state?.firmware;
  const status = started && (started.startedAt ?? 0) > (remote?.startedAt ?? 0) ? started : remote;
  const busy = Boolean(status?.busy);
  const unavailable = !instance || connectionStatus !== 'connected' || !remote;
  const currentImage = image === undefined ? remote?.image : image;

  useEffect(() => {
    setImage(undefined);
    setStarted(null);
    setPorts([]);
    setPort('');
    setConfirmation(null);
    setAcknowledged(false);
    setPending(false);
    setError(null);
    setUncertain(false);
    setStep('setup');
  }, [instance]);
  useEffect(() => {
    if (busy) {
      setOpen(true);
      setStep('progress');
      setUncertain(false);
    }
  }, [busy]);
  useEffect(() => {
    if (!busy) return;
    const protect = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', protect);
    return () => window.removeEventListener('beforeunload', protect);
  }, [busy]);

  async function perform(task: (isCurrent: () => boolean) => Promise<void>) {
    const owner = instance;
    const isCurrent = () => session.current === owner;
    setPending(true);
    setError(null);
    try {
      await task(isCurrent);
    } catch (reason) {
      if (isCurrent()) setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      if (isCurrent()) setPending(false);
    }
  }
  const refreshPorts = () =>
    perform(async (current) => {
      const result = await backend.firmwarePorts(instance!);
      if (!current()) return;
      setPorts(result.ports);
      if (!result.ports.some((item) => item.path === port))
        setPort(result.ports.length === 1 ? result.ports[0].path : '');
      if (!result.ports.length)
        throw new Error('未发现 USB 串口，请检查数据线、UART 接口和串口驱动。');
    });
  const show = () => {
    setOpen(true);
    setStep(busy || uncertain ? 'progress' : 'setup');
    if (!busy && !unavailable) void refreshPorts();
  };
  const prepare = () =>
    perform(async (current) => {
      const value = await backend.firmwarePrepare(port, instance!);
      if (current()) {
        setConfirmation(value);
        setAcknowledged(false);
        setStep('confirm');
      }
    });
  const flash = () =>
    perform(async (current) => {
      if (!confirmation) return;
      const selected = confirmation;
      setConfirmation(null);
      setStep('progress');
      setUncertain(true);
      const result = await backend.firmwareFlash(
        selected.confirmationToken,
        baud,
        instance!,
        backupRequested,
      );
      if (current()) {
        setStarted(result);
        setUncertain(false);
      }
    });
  const recover = () =>
    perform(async (current) => {
      const latest = await backend.firmwareStatus();
      if (current()) {
        setStarted(latest);
        setUncertain(false);
        setStep('progress');
      }
    });
  const useBundled = () =>
    perform(async (current) => {
      const value = await backend.firmwareUseBundled(instance!);
      if (current()) setImage(value);
    });
  const upload = (file: File) =>
    perform(async (current) => {
      setImage(null);
      if (file.size > 16 * 1024 * 1024) throw new Error('固件不能超过 16 MiB');
      const value = await backend.firmwareUpload(file, instance!);
      if (current()) setImage(value);
    });
  return {
    open,
    setOpen,
    step,
    setStep,
    ports,
    port,
    setPort,
    pending,
    error,
    confirmation,
    acknowledged,
    setAcknowledged,
    baud,
    setBaud,
    backupRequested,
    setBackupRequested,
    status,
    busy,
    unavailable,
    currentImage,
    uncertain,
    disabled: pending || busy || unavailable || uncertain,
    automationIdle: runtime.phase === 'idle',
    bundledError: remote?.bundledError,
    show,
    refreshPorts,
    prepare,
    flash,
    recover,
    useBundled,
    upload,
  };
}
