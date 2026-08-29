import { describe, expect, it } from 'vitest';
import {
  BACKEND_DISCONNECT_THRESHOLD,
  nextConnectionPollDelay,
  statusAfterFailure,
} from './connection';

describe('backend connection recovery', () => {
  it('treats the first two failures as a recoverable interruption', () => {
    expect(statusAfterFailure(1)).toBe('recovering');
    expect(statusAfterFailure(BACKEND_DISCONNECT_THRESHOLD - 1)).toBe('recovering');
  });

  it('reports a persistent disconnect after the third failure', () => {
    expect(statusAfterFailure(BACKEND_DISCONNECT_THRESHOLD)).toBe('disconnected');
    expect(statusAfterFailure(BACKEND_DISCONNECT_THRESHOLD + 2)).toBe('disconnected');
  });

  it('backs off polling while disconnected without stopping it', () => {
    expect(nextConnectionPollDelay('connected')).toBe(500);
    expect(nextConnectionPollDelay('recovering')).toBe(800);
    expect(nextConnectionPollDelay('disconnected')).toBe(2_000);
  });
});
