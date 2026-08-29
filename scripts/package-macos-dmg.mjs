import { access, mkdir, mkdtemp, rm, symlink } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const projectRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const options = Object.fromEntries(
  process.argv.slice(2).reduce((entries, value, index, values) => {
    if (!value.startsWith('--')) return entries;
    const next = values[index + 1];
    if (!next || next.startsWith('--')) return entries;
    entries.push([value.slice(2), next]);
    return entries;
  }, []),
);

if (process.platform !== 'darwin') {
  throw new Error('DMG 只能在 macOS 上生成');
}
if (!options.app || !options.output) {
  throw new Error('用法：node scripts/package-macos-dmg.mjs --app <app> --output <dmg>');
}

const appPath = path.resolve(projectRoot, options.app);
const outputPath = path.resolve(projectRoot, options.output);
await access(appPath);
await mkdir(path.dirname(outputPath), { recursive: true });

function run(command, args) {
  const result = spawnSync(command, args, { stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} 执行失败，退出码 ${result.status}`);
  }
}

run('/usr/bin/codesign', ['--force', '--deep', '--sign', '-', appPath]);
run('/usr/bin/codesign', ['--verify', '--deep', '--strict', '--verbose=2', appPath]);

const stagingRoot = await mkdtemp(path.join(os.tmpdir(), 'island-finder-dmg-'));
try {
  run('/usr/bin/ditto', [appPath, path.join(stagingRoot, 'Island Finder.app')]);
  await symlink('/Applications', path.join(stagingRoot, 'Applications'), 'dir');
  run('/usr/bin/hdiutil', [
    'create',
    '-volname',
    'Island Finder',
    '-srcfolder',
    stagingRoot,
    '-ov',
    '-format',
    'UDZO',
    outputPath,
  ]);
} finally {
  await rm(stagingRoot, { recursive: true, force: true });
}

console.log(`已生成 macOS 安装镜像：${outputPath}`);
