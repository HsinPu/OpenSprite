import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

for (const args of [
  [resolve('node_modules/typescript/bin/tsc'), '-p', 'tsconfig.node.json'],
  [resolve('node_modules/vite/bin/vite.js'), 'build', '--config', 'apps/web/vite.config.ts'],
]) {
  const result = spawnSync(process.execPath, args, { stdio: 'inherit', shell: false });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
