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

run(uvCommand, ['lock', '--check'], '检查 Python 锁文件');
run(npmCommand, ['run', 'desktop:fmt'], '检查 Tauri Rust 格式');
run(npmCommand, ['run', 'desktop:check'], '检查 Tauri 桌面进程管理器');
run(npmCommand, ['run', 'desktop:lint'], '检查 Tauri Rust Clippy');
run(
  npmCommand,
  ['exec', '--', 'turbo', 'run', 'test', 'build', 'self-test', '--force'],
  'Turbo 工作区测试、类型检查、生产构建与控制器自检',
);
