export type BackendConnectionStatus =
  | 'connecting'
  | 'connected'
  | 'recovering'
  | 'disconnected';

export const BACKEND_DISCONNECT_THRESHOLD = 3;

export function statusAfterFailure(failureCount: number): BackendConnectionStatus {
  return failureCount >= BACKEND_DISCONNECT_THRESHOLD ? 'disconnected' : 'recovering';
}

export function nextConnectionPollDelay(status: BackendConnectionStatus): number {
  switch (status) {
    case 'connected':
      return 500;
    case 'connecting':
    case 'recovering':
      return 800;
    case 'disconnected':
      return 2_000;
  }
}
