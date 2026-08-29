import { afterEach, describe, expect, it, vi } from 'vitest';
import { backend } from './client';

describe('backend client', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('aborts an audit request instead of leaving the page loading forever', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => (
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new DOMException('The operation was aborted', 'AbortError'));
        });
      })
    )));

    const rejection = expect(backend.auditHistory()).rejects.toThrow(
      '后端请求超过 8 秒，请重试',
    );

    await vi.advanceTimersByTimeAsync(8_000);
    await rejection;
  });
});
