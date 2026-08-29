import { spawnSync } from 'node:child_process';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const projectRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const desktopRoot = path.join(projectRoot, 'apps/desktop');
const tauri = path.join(
  projectRoot,
  'node_modules',
  '@tauri-apps',
  'cli',
  'tauri.js',
);
const bundles = process.platform === 'darwin'
  ? 'app'
  : process.platform === 'win32'
    ? 'nsis'
    : 'appimage';

const result = spawnSync(
  process.execPath,
  [tauri, 'build', '--ci', '--bundles', bundles, '--', '--locked'],
  {
    cwd: desktopRoot,
    env: process.env,
    stdio: 'inherit',
  },
);

if (result.error) throw result.error;
process.exit(result.status ?? 1);
