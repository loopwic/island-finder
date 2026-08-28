import net from 'node:net';
import process from 'node:process';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const projectRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const mode = process.argv[2];
const supportedModes = new Set(['dev', 'production', 'headless']);

if (!supportedModes.has(mode)) {
  console.error('用法：node scripts/run-stack.mjs <dev|production|headless>');
  process.exit(2);
}

const isWindows = process.platform === 'win32';
const npmCommand = isWindows ? 'npm.cmd' : 'npm';
const uvCommand = isWindows ? 'uv.exe' : 'uv';
const children = [];
let shuttingDown = false;

function runBlocking(command, args, label) {
  const result = spawnSync(command, args, {
    cwd: projectRoot,
    env: process.env,
    stdio: 'inherit',
    shell: isWindows && command === npmCommand,
  });
  if (result.error) {
    throw new Error(`${label}无法启动：${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`${label}失败，退出码 ${result.status ?? 'unknown'}`);
  }
}

function portIsOpen(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: '127.0.0.1', port });
    const finish = (open) => {
      socket.destroy();
      resolve(open);
    };
    socket.setTimeout(350);
    socket.once('connect', () => finish(true));
    socket.once('timeout', () => finish(false));
    socket.once('error', () => finish(false));
  });
}

async function assertPortFree(port, label) {
  if (await portIsOpen(port)) {
    throw new Error(`${label}端口 ${port} 已被占用；请先停止已有服务，避免启动两套自动化。`);
  }
}

function startManaged(command, args, label, extraEnv = {}) {
  const child = spawn(command, args, {
    cwd: projectRoot,
    env: { ...process.env, ...extraEnv },
    stdio: 'inherit',
    detached: !isWindows,
    shell: isWindows && command === npmCommand,
  });
  child.label = label;
  children.push(child);
  child.once('error', (error) => {
    console.error(`${label}无法启动：${error.message}`);
  });
  child.once('exit', (code, signal) => {
    if (shuttingDown) return;
    console.error(`${label}已退出（退出码 ${code ?? 'none'}，信号 ${signal ?? 'none'}），正在停止其余服务。`);
    void cleanup(code ?? 1);
  });
  return child;
}

async function waitForUrl(url, label, child) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    if (child.exitCode !== null) {
      throw new Error(`${label}在就绪前退出`);
    }
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1_000) });
      if (response.ok) return;
    } catch {
      // The service is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`${label}在 20 秒内没有就绪：${url}`);
}

function stopChild(child) {
  if (!child.pid || child.exitCode !== null) return;
  if (isWindows) {
    spawnSync('taskkill.exe', ['/pid', String(child.pid), '/t', '/f'], {
      stdio: 'ignore',
    });
    return;
  }
  try {
    process.kill(-child.pid, 'SIGTERM');
  } catch {
    child.kill('SIGTERM');
  }
}

async function cleanup(exitCode = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  try {
    await fetch('http://127.0.0.1:32145/v1/pairing/stop', {
      method: 'POST',
      signal: AbortSignal.timeout(1_000),
    });
  } catch {
    // The controller may never have started or may already be gone.
  }
  for (const child of children) stopChild(child);
  await new Promise((resolve) => setTimeout(resolve, 250));
  process.exit(exitCode);
}

process.once('SIGINT', () => void cleanup(0));
process.once('SIGTERM', () => void cleanup(0));

async function main() {
  if (mode === 'production') {
    runBlocking(npmCommand, ['run', 'build'], '生产构建');
  }

  await assertPortFree(32_145, '控制器服务');
  await assertPortFree(48_197, '视觉后端');
  if (mode === 'dev') await assertPortFree(4_173, 'Vite 开发服务');

  const controller = startManaged(
    uvCommand,
    ['run', '--frozen', 'python', 'vision_service/controller_server.py'],
    '控制器服务',
  );
  await waitForUrl('http://127.0.0.1:32145/v1/status', '控制器服务', controller);

  const visionArgs = ['run', '--frozen', 'python', 'vision_service/server.py'];
  if (mode === 'headless') visionArgs.push('--autostart');
  const vision = startManaged(uvCommand, visionArgs, '视觉后端');
  await waitForUrl('http://127.0.0.1:48197/health', '视觉后端', vision);

  if (mode === 'dev') {
    const web = startManaged(npmCommand, ['run', 'dev:web'], 'Vite 开发服务');
    await waitForUrl('http://127.0.0.1:4173/', 'Vite 开发服务', web);
    console.log('Island Finder 已启动：http://127.0.0.1:4173/');
  } else {
    console.log('Island Finder 已启动：http://127.0.0.1:48197/');
  }

  await new Promise(() => {});
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  void cleanup(1);
});
