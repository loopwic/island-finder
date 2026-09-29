import { defineTheme, Theme } from '@astryxdesign/core/theme';
import { neutralTheme } from '@astryxdesign/theme-neutral/built';
import { useState, type ReactNode } from 'react';
import { ThemeModeContext } from './theme-mode-context';
import { iconRegistry } from '../components/core/icons';

const theme = defineTheme({ name: 'island-finder', extends: neutralTheme, icons: iconRegistry });
export function AppTheme({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<'light' | 'dark' | 'system'>(() => {
    try {
      const saved = localStorage.getItem('island-finder-theme');
      return saved === 'dark' || saved === 'light' ? saved : 'system';
    } catch {
      return 'system';
    }
  });
  const toggle = () =>
    setMode((current) => {
      const next =
        current === 'dark' ||
        (current === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
          ? 'light'
          : 'dark';
      try {
        localStorage.setItem('island-finder-theme', next);
      } catch {
        /* Theme remains usable without storage. */
      }
      return next;
    });
  return (
    <ThemeModeContext value={{ toggle }}>
      <Theme theme={theme} mode={mode}>
        {children}
      </Theme>
    </ThemeModeContext>
  );
}
