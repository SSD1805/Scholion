import { spawnSync } from "node:child_process";
import {
  access,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rm,
  unlink,
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
const SEMANTIC_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const POSITIONAL_ID = /-\d+$/;

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
  return [
    path.join(ROOT, "README.md"),
    path.join(ROOT, "ROADMAP.md"),
    ...(await walkFiles(path.join(ROOT, "docs"), ".md")),
  ];
}

function absoluteFromManifest(value) {
  const absolute = path.resolve(ROOT, value);
  if (absolute !== ROOT && !absolute.startsWith(`${ROOT}${path.sep}`)) {
    throw new Error(`manifest path escapes repository: ${value}`);
  }
  return absolute;
}

function diagramPaths(id) {
  return {
    source: path.join(SOURCE_ROOT, `${id}.mmd`),
    output: path.join(OUTPUT_ROOT, `${id}.svg`),
  };
}

async function loadManifest() {
  const parsed = JSON.parse(await readFile(MANIFEST_PATH, "utf8"));
  if (parsed.version !== 2 || !Array.isArray(parsed.diagrams)) {
    throw new Error("docs/diagrams/manifest.json has an unsupported schema");
  }
  return parsed;
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

async function validateManifest(manifest) {
  const seenIds = new Set();
  const expectedSources = new Set();
  const expectedOutputs = new Set();

  for (const entry of manifest.diagrams) {
    for (const field of ["id", "document", "alt"]) {
      if (typeof entry[field] !== "string" || entry[field].trim() === "") {
        throw new Error(`manifest diagram has an invalid ${field}`);
      }
    }

    if (!SEMANTIC_ID.test(entry.id)) {
      throw new Error(`diagram ID is not a lowercase semantic slug: ${entry.id}`);
    }
    if (POSITIONAL_ID.test(entry.id)) {
      throw new Error(
        `diagram ID must describe meaning, not position/version: ${entry.id}`,
      );
    }
    if (seenIds.has(entry.id)) {
      throw new Error(`manifest contains duplicate diagram ID: ${entry.id}`);
    }
    seenIds.add(entry.id);

    const documentPath = absoluteFromManifest(entry.document);
    const { source, output } = diagramPaths(entry.id);
    expectedSources.add(path.resolve(source));
    expectedOutputs.add(path.resolve(output));

    if (!(await exists(documentPath)) || !(await exists(source))) {
      throw new Error(`manifest references a missing document/source: ${entry.id}`);
    }

    const markdown = await readFile(documentPath, "utf8");
    const expectedImage = `![${entry.alt}](${markdownLink(documentPath, output)})`;
    const expectedSource = `[Diagram source (Mermaid)](${markdownLink(documentPath, source)})`;
    if (!markdown.includes(expectedImage) || !markdown.includes(expectedSource)) {
      throw new Error(
        `document does not reference its generated SVG/source exactly: ${entry.document} (${entry.id})`,
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

async function renderWrite(manifest) {
  await mkdir(OUTPUT_ROOT, { recursive: true });
  const expected = new Set(
    manifest.diagrams.map((entry) => path.resolve(diagramPaths(entry.id).output)),
  );

  for (const existing of await walkFiles(OUTPUT_ROOT, ".svg")) {
    if (!expected.has(path.resolve(existing))) {
      await unlink(existing);
    }
  }

  for (const entry of manifest.diagrams) {
    const { source, output } = diagramPaths(entry.id);
    await mkdir(path.dirname(output), { recursive: true });
    renderOne(source, output);
  }
}

async function renderCheck(manifest) {
  const tempRoot = await mkdtemp(path.join(os.tmpdir(), "scholion-mermaid-"));
  const stale = [];

  try {
    for (const entry of manifest.diagrams) {
      const { source, output: committed } = diagramPaths(entry.id);
      if (!(await exists(committed))) {
        stale.push(`${repoRelative(committed)} (missing)`);
        continue;
      }

      const rendered = path.join(tempRoot, `${entry.id}.svg`);
      renderOne(source, rendered);
      const [expected, actual] = await Promise.all([
        readFile(rendered),
        readFile(committed),
      ]);
      if (!expected.equals(actual)) {
        stale.push(repoRelative(committed));
      }
    }
  } finally {
    await rm(tempRoot, { recursive: true, force: true });
  }

  if (stale.length > 0) {
    throw new Error(
      `generated SVGs are stale: ${stale.join(", ")}\n` +
        "Run: npm --prefix tools/mermaid run render",
    );
  }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length !== 1 || !["--check", "--write"].includes(args[0])) {
    throw new Error("usage: node tools/mermaid/render.mjs --check|--write");
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

  if (args[0] === "--write") {
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
  console.error(
    `Mermaid docs check failed: ${error instanceof Error ? error.message : String(error)}`,
  );
  process.exitCode = 1;
});
