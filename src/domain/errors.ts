export function errorMessage(reason: unknown, fallback?: string): string {
  if (reason instanceof Error) return reason.message;
  return fallback ?? String(reason);
}
