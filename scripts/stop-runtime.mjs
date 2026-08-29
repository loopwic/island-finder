import path from 'node:path';
import { fileURLToPath } from 'node:url';

const endpoint = 'http://127.0.0.1:32146';
const projectRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

try {
  const statusResponse = await fetch(`${endpoint}/health`, {
    signal: AbortSignal.timeout(1_000),
  });
  const status = await statusResponse.json();
  if (
    !statusResponse.ok
    || status?.service !== 'island-finder-runtime'
    || status?.projectRoot !== projectRoot
  ) {
    throw new Error('端口 32146 不是当前项目的 Island Finder 运行时');
  }
  const response = await fetch(`${endpoint}/shutdown`, {
    method: 'POST',
    signal: AbortSignal.timeout(1_000),
  });
  if (!response.ok) throw new Error(`停止请求失败：HTTP ${response.status}`);
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 100));
    try {
      await fetch(`${endpoint}/health`, { signal: AbortSignal.timeout(300) });
    } catch {
      console.log('Island Finder 桌面运行时已安全停止。');
      process.exit(0);
    }
  }
  throw new Error('Island Finder 运行时未能在 10 秒内停止');
} catch (error) {
  if (error?.cause?.code === 'ECONNREFUSED') {
    console.log('Island Finder 桌面运行时当前未启动。');
    process.exit(0);
  }
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
