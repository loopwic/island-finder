export function isTauriDesktop(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

export async function restartDesktopRuntime(): Promise<boolean> {
  if (!isTauriDesktop()) return false;
  const { invoke } = await import('@tauri-apps/api/core');
  await invoke('restart_runtime');
  return true;
}
