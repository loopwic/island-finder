import { describe, expect, it } from 'vitest';
import { isTauriDesktop, restartDesktopRuntime } from './desktop-runtime';

describe('desktop runtime bridge', () => {
  it('does not invoke a native restart from the ordinary web build', async () => {
    expect(isTauriDesktop()).toBe(false);
    await expect(restartDesktopRuntime()).resolves.toBe(false);
  });
});
