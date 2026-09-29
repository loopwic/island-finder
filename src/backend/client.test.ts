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

  it('binds firmware confirmation to the current session and never retries a flash POST', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('network lost'));
    vi.stubGlobal('fetch', fetchMock);
    await expect(backend.firmwareFlash('single-use-token', 115200, 'current-session', false)).rejects.toThrow('无法连接');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: 'POST',
      headers: { 'X-Island-Finder-Instance': 'current-session' },
      body: JSON.stringify({ confirmationToken: 'single-use-token', baud: 115200, acknowledged: true, backupRequested: false }),
    });
  });
});
