import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const projectRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const isWindows = process.platform === 'win32';
const npmCommand = isWindows ? 'npm.cmd' : 'npm';
const uvCommand = isWindows ? 'uv.exe' : 'uv';

function run(command, args, label) {
  console.log(`\n[check] ${label}`);
  const result = spawnSync(command, args, {
    cwd: projectRoot,
    env: process.env,
    stdio: 'inherit',
    shell: isWindows && command === npmCommand,
  });
  if (result.error) {
    console.error(`${label}无法启动：${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}

run(process.execPath, ['--check', 'scripts/run-stack.mjs'], '检查跨平台启动器');
run(uvCommand, ['lock', '--check'], '检查 Python 锁文件');
run(npmCommand, ['run', 'test'], '前端测试');
run(npmCommand, ['run', 'vision:test'], 'Python/OpenCV 与控制器测试');
run(npmCommand, ['run', 'build'], 'TypeScript 与生产构建');
run(npmCommand, ['run', 'controller:self-test'], 'PABotBase2 协议自检');
