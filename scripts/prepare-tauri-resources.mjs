import { access, chmod, copyFile, cp, mkdir, rm } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const projectRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const resourcesRoot = path.join(projectRoot, 'apps/desktop/src-tauri/resources');
const runtimeRoot = path.join(resourcesRoot, 'runtime');
const executableName = process.platform === 'win32' ? 'uv.exe' : 'uv';

async function findUv() {
  const candidates = [];
  if (process.env.ISLAND_FINDER_UV_BIN) {
    candidates.push(process.env.ISLAND_FINDER_UV_BIN);
  }
  for (const directory of (process.env.PATH ?? '').split(path.delimiter)) {
    if (directory) candidates.push(path.join(directory, executableName));
  }
  for (const candidate of candidates) {
    try {
      await access(candidate);
      return candidate;
    } catch {
      // Continue searching the inherited executable path.
    }
  }
  throw new Error('未找到 uv；请先安装 uv，或设置 ISLAND_FINDER_UV_BIN');
}

await rm(resourcesRoot, { recursive: true, force: true });
await mkdir(path.join(runtimeRoot, 'scripts'), { recursive: true });
await mkdir(path.join(runtimeRoot, 'bin'), { recursive: true });

await cp(path.join(projectRoot, 'vision_service'), path.join(runtimeRoot, 'vision_service'), {
  recursive: true,
  filter: (source) => {
    const relative = path.relative(path.join(projectRoot, 'vision_service'), source);
    return !relative.split(path.sep).some((part) => (
      part === 'tests'
      || part === '__pycache__'
      || part === '.pytest_cache'
    )) && !source.endsWith('.pyc');
  },
});

for (const source of [
  'scripts/capture-stream.swift',
  'scripts/run-capture-stream.sh',
]) {
  await copyFile(path.join(projectRoot, source), path.join(runtimeRoot, source));
}

for (const source of [
  'README.md',
  'LICENSE',
  'NOTICE.md',
  'pyproject.toml',
  'uv.lock',
]) {
  await copyFile(path.join(projectRoot, source), path.join(runtimeRoot, source));
}

await copyFile(await findUv(), path.join(runtimeRoot, 'bin', executableName));
if (process.platform !== 'win32') {
  await chmod(path.join(runtimeRoot, 'bin', executableName), 0o755);
  await chmod(path.join(runtimeRoot, 'scripts/run-capture-stream.sh'), 0o755);
}

console.log(`已准备 Tauri 运行资源：${runtimeRoot}`);
