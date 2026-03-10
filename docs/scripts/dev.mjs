import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const docsRoot = path.resolve(scriptDir, '..');
const generateScript = path.join(scriptDir, 'generate-reference.mjs');

const generate = spawnSync(process.execPath, [generateScript], {
  cwd: docsRoot,
  stdio: 'inherit'
});

if (generate.status !== 0) {
  process.exit(generate.status ?? 1);
}

const child = spawn('pnpm', ['exec', 'next', 'dev', ...process.argv.slice(2)], {
  cwd: docsRoot,
  stdio: 'inherit'
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
