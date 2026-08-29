import { chmod, copyFile, cp, mkdir, rm } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
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

if (!options.binary || !options.output) {
  console.error('用法：node scripts/prepare-desktop-artifact.mjs --binary <path> --output <path>');
  process.exit(1);
}

const sourceBinary = path.resolve(projectRoot, options.binary);
const outputRoot = path.resolve(projectRoot, options.output);
const packageRoot = path.join(outputRoot, 'Island-Finder');
const executableName = sourceBinary.toLowerCase().endsWith('.exe')
  ? 'Island-Finder.exe'
  : 'Island-Finder';

await rm(outputRoot, { recursive: true, force: true });
await mkdir(path.join(packageRoot, 'scripts'), { recursive: true });
await copyFile(sourceBinary, path.join(packageRoot, executableName));
if (executableName === 'Island-Finder') {
  await chmod(path.join(packageRoot, executableName), 0o755);
}

await cp(path.join(projectRoot, 'vision_service'), path.join(packageRoot, 'vision_service'), {
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
  await copyFile(path.join(projectRoot, source), path.join(packageRoot, source));
}
await chmod(path.join(packageRoot, 'scripts/run-capture-stream.sh'), 0o755);

for (const source of [
  'README.md',
  'LICENSE',
  'NOTICE.md',
  'pyproject.toml',
  'uv.lock',
]) {
  await copyFile(path.join(projectRoot, source), path.join(packageRoot, source));
}

console.log(`已准备桌面发布目录：${packageRoot}`);
