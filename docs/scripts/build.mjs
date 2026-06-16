import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const docsRoot = path.resolve(scriptDir, '..');
const checkScript = path.join(scriptDir, 'check.mjs');

const check = spawnSync(process.execPath, [checkScript], {
  cwd: docsRoot,
  stdio: 'inherit'
});

if (check.status !== 0) {
  process.exit(check.status ?? 1);
}

const nextBin = process.platform === 'win32' ? 'next.cmd' : 'next';

const build = spawnSync(nextBin, ['build', ...process.argv.slice(2)], {
  cwd: docsRoot,
  stdio: 'inherit'
});

process.exit(build.status ?? 0);
