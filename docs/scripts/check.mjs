import { promises as fs } from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const docsRoot = path.resolve(scriptDir, '..');
const docsContentRoot = path.join(docsRoot, 'content', 'docs');
const generateScript = path.join(scriptDir, 'generate-reference.mjs');

function run(command, args, cwd, { capture = false } = {}) {
  const result = spawnSync(command, args, {
    cwd,
    encoding: 'utf8',
    stdio: capture ? ['ignore', 'pipe', 'pipe'] : 'inherit'
  });

  if (result.status !== 0) {
    const stderr = result.stderr?.trim();
    throw new Error(
      `Command failed: ${command} ${args.join(' ')}${
        stderr ? `\n${stderr}` : ''
      }`,
    );
  }

  return result;
}

async function walkMdxFiles(dir, acc = []) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      await walkMdxFiles(fullPath, acc);
      continue;
    }

    if (entry.isFile() && entry.name.endsWith('.mdx')) {
      acc.push(fullPath);
    }
  }

  return acc;
}

function normalizeRoute(route) {
  if (!route.startsWith('/')) {
    return route;
  }
  if (route === '/docs/') {
    return '/docs';
  }
  return route.length > 1 && route.endsWith('/') ? route.slice(0, -1) : route;
}

function mdxPathToRoute(filePath) {
  const relativePath = path.relative(docsContentRoot, filePath).replaceAll('\\', '/');
  const withoutExt = relativePath.slice(0, -'.mdx'.length);
  if (withoutExt === 'index') {
    return '/docs';
  }
  if (withoutExt.endsWith('/index')) {
    return normalizeRoute(`/docs/${withoutExt.slice(0, -'/index'.length)}`);
  }
  return normalizeRoute(`/docs/${withoutExt}`);
}

function splitFrontmatter(raw) {
  if (!raw.startsWith('---\n')) {
    return null;
  }
  const endMarker = '\n---\n';
  const endIndex = raw.indexOf(endMarker, 4);
  if (endIndex < 0) {
    return null;
  }
  return {
    frontmatter: raw.slice(4, endIndex),
    body: raw.slice(endIndex + endMarker.length),
  };
}

function parseFrontmatter(frontmatterRaw) {
  const values = {};
  for (const line of frontmatterRaw.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }
    const match = /^([A-Za-z0-9_-]+):\s*(.+)\s*$/.exec(line);
    if (!match) {
      continue;
    }
    const [, key, value] = match;
    values[key] = value.trim().replace(/^['"]|['"]$/g, '');
  }
  return values;
}

function lineAtOffset(text, offset) {
  return text.slice(0, offset).split('\n').length;
}

function collectLinks(body) {
  const links = [];
  const linkRegex = /\[[^\]]+\]\((\/docs[^)\s]*)\)/g;
  let match;
  while ((match = linkRegex.exec(body)) !== null) {
    const rawTarget = match[1];
    const withoutHash = rawTarget.split('#')[0]?.split('?')[0] ?? rawTarget;
    links.push({
      target: normalizeRoute(withoutHash),
      line: lineAtOffset(body, match.index),
    });
  }
  return links;
}

function collectHeadings(body) {
  const headings = [];
  const headingRegex = /^(#{1,6})\s+(.+)$/gm;
  let match;
  while ((match = headingRegex.exec(body)) !== null) {
    headings.push({
      level: match[1].length,
      text: match[2].trim(),
      line: lineAtOffset(body, match.index),
    });
  }
  return headings;
}

function checkHeadingSanity(headings) {
  const issues = [];
  let previousLevel = 0;
  for (const heading of headings) {
    if (heading.level === 1) {
      issues.push(`line ${heading.line}: avoid \`#\` H1 headings in MDX body (DocsTitle already renders page title).`);
    }
    if (previousLevel > 0 && heading.level - previousLevel > 1) {
      issues.push(
        `line ${heading.line}: heading level jumps from H${previousLevel} to H${heading.level} ("${heading.text}").`,
      );
    }
    previousLevel = heading.level;
  }
  return issues;
}

async function main() {
  run(process.execPath, [generateScript, '--check'], docsRoot);

  const files = (await walkMdxFiles(docsContentRoot)).sort();
  const routes = new Set(files.map(mdxPathToRoute));
  const errors = [];

  for (const filePath of files) {
    const relativePath = path.relative(docsRoot, filePath);
    const raw = await fs.readFile(filePath, 'utf8');
    const parsed = splitFrontmatter(raw);

    if (!parsed) {
      errors.push(`${relativePath}: missing valid YAML frontmatter block.`);
      continue;
    }

    const frontmatter = parseFrontmatter(parsed.frontmatter);
    if (!frontmatter.title || !frontmatter.title.trim()) {
      errors.push(`${relativePath}: missing required frontmatter field \`title\`.`);
    }
    if (!frontmatter.description || !frontmatter.description.trim()) {
      errors.push(`${relativePath}: missing required frontmatter field \`description\`.`);
    }

    for (const headingError of checkHeadingSanity(collectHeadings(parsed.body))) {
      errors.push(`${relativePath}: ${headingError}`);
    }

    for (const link of collectLinks(parsed.body)) {
      if (!routes.has(link.target)) {
        errors.push(`${relativePath}: line ${link.line}: unresolved internal docs link \`${link.target}\`.`);
      }
    }
  }

  if (errors.length > 0) {
    console.error('Docs check failed:');
    for (const error of errors) {
      console.error(`- ${error}`);
    }
    process.exit(1);
  }

  console.log(`Docs check passed for ${files.length} MDX files.`);
}

await main();
