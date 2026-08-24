import { spawnSync } from "node:child_process";
import {
  access,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rm,
  unlink,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const TOOL_ROOT = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(TOOL_ROOT, "..", "..");
const SOURCE_ROOT = path.join(ROOT, "docs", "diagrams", "src");
const OUTPUT_ROOT = path.join(ROOT, "docs", "diagrams", "generated");
const MANIFEST_PATH = path.join(ROOT, "docs", "diagrams", "manifest.json");
const CONFIG_PATH = path.join(TOOL_ROOT, "mermaid.config.json");
const MMDC_PATH = path.join(
  TOOL_ROOT,
  "node_modules",
  "@mermaid-js",
  "mermaid-cli",
  "src",
  "cli.js",
);
const BACKGROUND = "#FFFDF7";
const MERMAID_BLOCK = /```mermaid\r?\n([\s\S]*?)\r?\n```/g;
const LEGACY_FALLBACK = /\n*<details>\s*<summary>Static diagram fallback[^<]*<\/summary>[\s\S]*?<\/details>\s*/g;
const LEGACY_STATIC_FILES = [
  "docs-family-portrait.svg",
  "product-roadmap.svg",
  "recording-to-evidence.svg",
  "system-architecture.svg",
];

function fail(message) {
  console.error(`Mermaid docs check failed: ${message}`);
  process.exitCode = 1;
}

async function exists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

function toPosix(value) {
  return value.split(path.sep).join("/");
}

function repoRelative(filePath) {
  return toPosix(path.relative(ROOT, filePath));
}

function markdownLink(fromDocument, target) {
  let relative = toPosix(path.relative(path.dirname(fromDocument), target));
  if (!relative.startsWith(".") && !relative.startsWith("/")) {
    relative = `./${relative}`;
  }
  return relative;
}

async function walkFiles(directory, suffix) {
  if (!(await exists(directory))) {
    return [];
  }
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await walkFiles(target, suffix)));
    } else if (entry.isFile() && entry.name.endsWith(suffix)) {
      files.push(target);
    }
  }
  return files.sort();
}

async function markdownFiles() {
  const files = [path.join(ROOT, "README.md"), path.join(ROOT, "ROADMAP.md")];
  files.push(...(await walkFiles(path.join(ROOT, "docs"), ".md")));
  return files;
}

function cleanHeading(raw) {
  return raw
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[`*_~]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/[\[\]]/g, "");
}

function headingBefore(text, offset, fallback) {
  const before = text.slice(0, offset);
  const headings = [...before.matchAll(/^#{1,6}\s+(.+?)\s*$/gm)];
  if (headings.length === 0) {
    return fallback;
  }
  return cleanHeading(headings.at(-1)[1]) || fallback;
}

function diagramPaths(documentPath, index) {
  const documentRelative = path.relative(ROOT, documentPath);
  const stem = documentRelative.replace(/\.md$/i, "");
  const relativeDiagram = `${stem}-${index}`;
  return {
    source: path.join(SOURCE_ROOT, `${relativeDiagram}.mmd`),
    output: path.join(OUTPUT_ROOT, `${relativeDiagram}.svg`),
  };
}

function renderOne(source, output) {
  const result = spawnSync(
    process.execPath,
    [
      MMDC_PATH,
      "--input",
      source,
      "--output",
      output,
      "--configFile",
      CONFIG_PATH,
      "--backgroundColor",
      BACKGROUND,
      "--quiet",
    ],
    {
      cwd: ROOT,
      encoding: "utf8",
      maxBuffer: 10 * 1024 * 1024,
    },
  );
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    const detail = [result.stdout, result.stderr].filter(Boolean).join("\n").trim();
    throw new Error(
      `mmdc failed for ${repoRelative(source)}${detail ? `\n${detail}` : ""}`,
    );
  }
}

async function migrateInline() {
  if (await exists(MANIFEST_PATH)) {
    throw new Error(
      "docs/diagrams/manifest.json already exists; inline migration is intentionally one-shot",
    );
  }

  const manifest = { version: 1, diagrams: [] };
  let migrated = 0;

  for (const documentPath of await markdownFiles()) {
    const original = await readFile(documentPath, "utf8");
    const matches = [...original.matchAll(MERMAID_BLOCK)];
    if (matches.length === 0) {
      continue;
    }

    let cursor = 0;
    let updated = "";
    for (let position = 0; position < matches.length; position += 1) {
      const match = matches[position];
      const index = position + 1;
      const { source, output } = diagramPaths(documentPath, index);
      const heading = headingBefore(
        original,
        match.index,
        path.basename(documentPath, ".md"),
      );
      const alt = `${heading} diagram`;
      const sourceLink = markdownLink(documentPath, source);
      const outputLink = markdownLink(documentPath, output);

      await mkdir(path.dirname(source), { recursive: true });
      await writeFile(source, `${match[1].trimEnd()}\n`, "utf8");

      updated += original.slice(cursor, match.index);
      updated += `![${alt}](${outputLink})\n\n[Diagram source (Mermaid)](${sourceLink})`;
      cursor = match.index + match[0].length;

      manifest.diagrams.push({
        document: repoRelative(documentPath),
        source: repoRelative(source),
        output: repoRelative(output),
        alt,
      });
      migrated += 1;
    }
    updated += original.slice(cursor);
    updated = updated.replace(LEGACY_FALLBACK, "\n\n");
    await writeFile(documentPath, updated, "utf8");
  }

  if (migrated === 0) {
    throw new Error("no inline Mermaid fences were found to migrate");
  }

  manifest.diagrams.sort((left, right) => left.source.localeCompare(right.source));
  await mkdir(path.dirname(MANIFEST_PATH), { recursive: true });
  await writeFile(MANIFEST_PATH, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

  for (const name of LEGACY_STATIC_FILES) {
    const candidate = path.join(ROOT, "docs", "diagrams", name);
    if (await exists(candidate)) {
      await unlink(candidate);
    }
  }

  console.log(`Migrated ${migrated} Mermaid diagram(s) to canonical .mmd sources.`);
}

async function loadManifest() {
  const parsed = JSON.parse(await readFile(MANIFEST_PATH, "utf8"));
  if (parsed.version !== 1 || !Array.isArray(parsed.diagrams)) {
    throw new Error("docs/diagrams/manifest.json has an unsupported schema");
  }
  return parsed;
}

function absoluteFromManifest(value) {
  const absolute = path.resolve(ROOT, value);
  if (absolute !== ROOT && !absolute.startsWith(`${ROOT}${path.sep}`)) {
    throw new Error(`manifest path escapes repository: ${value}`);
  }
  return absolute;
}

async function validateManifest(manifest) {
  const seenSources = new Set();
  const seenOutputs = new Set();
  const expectedSources = new Set();
  const expectedOutputs = new Set();

  for (const entry of manifest.diagrams) {
    for (const field of ["document", "source", "output", "alt"]) {
      if (typeof entry[field] !== "string" || entry[field].trim() === "") {
        throw new Error(`manifest diagram has an invalid ${field}`);
      }
    }

    const documentPath = absoluteFromManifest(entry.document);
    const source = absoluteFromManifest(entry.source);
    const output = absoluteFromManifest(entry.output);
    if (!source.startsWith(`${SOURCE_ROOT}${path.sep}`) || !source.endsWith(".mmd")) {
      throw new Error(`manifest source is outside docs/diagrams/src: ${entry.source}`);
    }
    if (!output.startsWith(`${OUTPUT_ROOT}${path.sep}`) || !output.endsWith(".svg")) {
      throw new Error(
        `manifest output is outside docs/diagrams/generated: ${entry.output}`,
      );
    }
    if (seenSources.has(entry.source) || seenOutputs.has(entry.output)) {
      throw new Error(`manifest contains a duplicate source/output: ${entry.source}`);
    }
    seenSources.add(entry.source);
    seenOutputs.add(entry.output);
    expectedSources.add(path.resolve(source));
    expectedOutputs.add(path.resolve(output));

    if (!(await exists(documentPath)) || !(await exists(source))) {
      throw new Error(`manifest references a missing document/source: ${entry.source}`);
    }

    const markdown = await readFile(documentPath, "utf8");
    const expectedImage = `![${entry.alt}](${markdownLink(documentPath, output)})`;
    const expectedSource = `[Diagram source (Mermaid)](${markdownLink(documentPath, source)})`;
    if (!markdown.includes(expectedImage) || !markdown.includes(expectedSource)) {
      throw new Error(
        `document does not reference its generated SVG/source exactly: ${entry.document}`,
      );
    }
  }

  const actualSources = new Set(
    (await walkFiles(SOURCE_ROOT, ".mmd")).map((item) => path.resolve(item)),
  );
  const actualOutputs = new Set(
    (await walkFiles(OUTPUT_ROOT, ".svg")).map((item) => path.resolve(item)),
  );

  for (const source of actualSources) {
    if (!expectedSources.has(source)) {
      throw new Error(`unregistered Mermaid source: ${repoRelative(source)}`);
    }
  }
  for (const source of expectedSources) {
    if (!actualSources.has(source)) {
      throw new Error(`manifest Mermaid source is missing: ${repoRelative(source)}`);
    }
  }
  for (const output of actualOutputs) {
    if (!expectedOutputs.has(output)) {
      throw new Error(`unregistered generated SVG: ${repoRelative(output)}`);
    }
  }

  return { expectedOutputs };
}

async function assertNoInlineMermaid() {
  const offenders = [];
  for (const documentPath of await markdownFiles()) {
    const text = await readFile(documentPath, "utf8");
    if (/```mermaid(?:\r?\n|\s)/.test(text)) {
      offenders.push(repoRelative(documentPath));
    }
  }
  if (offenders.length > 0) {
    throw new Error(
      `inline Mermaid fences bypass generated SVG custody: ${offenders.join(", ")}`,
    );
  }
}

async function renderWrite(manifest) {
  await mkdir(OUTPUT_ROOT, { recursive: true });
  const expected = new Set(manifest.diagrams.map((entry) => path.resolve(ROOT, entry.output)));
  for (const existing of await walkFiles(OUTPUT_ROOT, ".svg")) {
    if (!expected.has(path.resolve(existing))) {
      await unlink(existing);
    }
  }

  for (const entry of manifest.diagrams) {
    const source = absoluteFromManifest(entry.source);
    const output = absoluteFromManifest(entry.output);
    await mkdir(path.dirname(output), { recursive: true });
    renderOne(source, output);
  }
}

async function renderCheck(manifest) {
  const tempRoot = await mkdtemp(path.join(os.tmpdir(), "scholion-mermaid-"));
  const stale = [];
  try {
    for (const entry of manifest.diagrams) {
      const source = absoluteFromManifest(entry.source);
      const committed = absoluteFromManifest(entry.output);
      if (!(await exists(committed))) {
        stale.push(`${entry.output} (missing)`);
        continue;
      }
      const rendered = path.join(tempRoot, entry.output);
      await mkdir(path.dirname(rendered), { recursive: true });
      renderOne(source, rendered);
      const [expected, actual] = await Promise.all([
        readFile(rendered),
        readFile(committed),
      ]);
      if (!expected.equals(actual)) {
        stale.push(entry.output);
      }
    }
  } finally {
    await rm(tempRoot, { recursive: true, force: true });
  }

  if (stale.length > 0) {
    throw new Error(
      `generated SVGs are stale: ${stale.join(", ")}\nRun: npm --prefix tools/mermaid run render`,
    );
  }
}

async function main() {
  const args = new Set(process.argv.slice(2));
  const modes = ["--check", "--write", "--migrate-inline"].filter((mode) =>
    args.has(mode),
  );
  if (modes.length !== 1 || args.size !== 1) {
    throw new Error(
      "usage: node tools/mermaid/render.mjs --check|--write|--migrate-inline",
    );
  }

  if (args.has("--migrate-inline")) {
    await migrateInline();
    const manifest = await loadManifest();
    await assertNoInlineMermaid();
    await renderWrite(manifest);
    await validateManifest(manifest);
    console.log("Mermaid migration and deterministic SVG generation complete.");
    return;
  }

  if (!(await exists(MANIFEST_PATH))) {
    throw new Error("missing docs/diagrams/manifest.json");
  }
  if (!(await exists(MMDC_PATH))) {
    throw new Error(
      "Mermaid CLI is not installed; run npm ci --prefix tools/mermaid first",
    );
  }

  const manifest = await loadManifest();
  await assertNoInlineMermaid();
  await validateManifest(manifest);

  if (args.has("--write")) {
    await renderWrite(manifest);
    await validateManifest(manifest);
    console.log(`Rendered ${manifest.diagrams.length} deterministic SVG diagram(s).`);
    return;
  }

  await renderCheck(manifest);
  console.log(
    `Verified ${manifest.diagrams.length} Mermaid source/SVG pair(s) are deterministic and current.`,
  );
}

main().catch((error) => {
  fail(error instanceof Error ? error.message : String(error));
});
