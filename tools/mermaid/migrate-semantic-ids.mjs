import { access, mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const TOOL_ROOT = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(TOOL_ROOT, "..", "..");
const SOURCE_ROOT = path.join(ROOT, "docs", "diagrams", "src");
const OUTPUT_ROOT = path.join(ROOT, "docs", "diagrams", "generated");
const MANIFEST_PATH = path.join(ROOT, "docs", "diagrams", "manifest.json");

const IDS = new Map([
  ["docs/diagrams/src/README-1.mmd", "recording-to-useful-evidence"],
  ["docs/diagrams/src/ROADMAP-1.mmd", "scholion-roadmap"],
  ["docs/diagrams/src/docs/README-1.mmd", "scholion-family-portrait"],
  ["docs/diagrams/src/docs/architecture/README-1.mmd", "system-shape"],
  ["docs/diagrams/src/docs/architecture/adaptive-heterogeneous-execution-1.mmd", "adaptive-execution-overview"],
  ["docs/diagrams/src/docs/architecture/adaptive-heterogeneous-execution-2.mmd", "bounded-pipeline-overlap"],
  ["docs/diagrams/src/docs/architecture/corpus-search-1.mmd", "corpus-search-overview"],
  ["docs/diagrams/src/docs/architecture/corpus-search-2.mmd", "canonical-hashing-stale-refusal"],
  ["docs/diagrams/src/docs/architecture/diarization-1.mmd", "anonymous-speaker-diarization"],
  ["docs/diagrams/src/docs/architecture/diarization-2.mmd", "speaker-display-labels"],
  ["docs/diagrams/src/docs/architecture/library-locations-1.mmd", "library-locations"],
  ["docs/diagrams/src/docs/architecture/media-and-timeline-1.mmd", "media-timeline-overview"],
  ["docs/diagrams/src/docs/architecture/media-and-timeline-2.mmd", "shared-evidence-time-axis"],
  ["docs/diagrams/src/docs/architecture/model-management-1.mmd", "model-management"],
  ["docs/diagrams/src/docs/architecture/processing-capabilities-1.mmd", "processing-capabilities"],
  ["docs/diagrams/src/docs/architecture/research-state-1.mmd", "durable-research-state"],
  ["docs/diagrams/src/docs/architecture/speech-enhancement-1.mmd", "speech-enhancement"],
  ["docs/diagrams/src/docs/architecture/word-alignment-1.mmd", "word-alignment-timeline"],
  ["docs/diagrams/src/docs/architecture/word-alignment-2.mmd", "speaker-handoffs"],
  ["docs/diagrams/src/docs/development/benchmarking-1.mmd", "benchmarking-measurements"],
  ["docs/diagrams/src/docs/development/semantic-retrieval-testing-1.mmd", "semantic-rebuild-failure-preservation"],
  ["docs/diagrams/src/docs/documentation-style-1.mmd", "documentation-mermaid-palette"],
  ["docs/diagrams/src/docs/evidence-navigation-1.mmd", "search-to-evidence"],
  ["docs/diagrams/src/docs/evidence-navigation-2.mmd", "durable-research-coordinate-system"],
  ["docs/diagrams/src/docs/library-discovery-1.mmd", "library-discovery"],
  ["docs/diagrams/src/docs/research-notes-1.mmd", "research-notes"],
  ["docs/diagrams/src/docs/research-search-1.mmd", "research-search-intent"],
  ["docs/diagrams/src/docs/semantic-search-1.mmd", "semantic-search-overview"],
  ["docs/diagrams/src/docs/semantic-search-2.mmd", "embedding-concept"],
  ["docs/diagrams/src/docs/semantic-search-3.mmd", "semantic-model-upgrade"],
  ["docs/diagrams/src/docs/time-navigation-1.mmd", "word-timestamps"],
  ["docs/diagrams/src/docs/time-navigation-2.mmd", "declared-media-timecode"],
]);

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

function absolute(repoPath) {
  const result = path.resolve(ROOT, repoPath);
  if (result !== ROOT && !result.startsWith(`${ROOT}${path.sep}`)) {
    throw new Error(`path escapes repository: ${repoPath}`);
  }
  return result;
}

function markdownLink(documentPath, targetPath) {
  let relative = toPosix(path.relative(path.dirname(documentPath), targetPath));
  if (!relative.startsWith(".") && !relative.startsWith("/")) {
    relative = `./${relative}`;
  }
  return relative;
}

async function main() {
  const manifest = JSON.parse(await readFile(MANIFEST_PATH, "utf8"));
  if (manifest.version !== 1 || !Array.isArray(manifest.diagrams)) {
    throw new Error("semantic-ID migration requires manifest version 1");
  }
  if (manifest.diagrams.length !== IDS.size) {
    throw new Error(
      `expected ${IDS.size} diagrams, found ${manifest.diagrams.length}; refuse partial migration`,
    );
  }

  const seenIds = new Set();
  const updatesByDocument = new Map();
  const nextEntries = [];

  for (const entry of manifest.diagrams) {
    const id = IDS.get(entry.source);
    if (!id) {
      throw new Error(`no reviewed semantic ID for ${entry.source}`);
    }
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(id) || /-\d+$/.test(id)) {
      throw new Error(`invalid semantic diagram ID: ${id}`);
    }
    if (seenIds.has(id)) {
      throw new Error(`duplicate semantic diagram ID: ${id}`);
    }
    seenIds.add(id);

    const documentPath = absolute(entry.document);
    const oldSource = absolute(entry.source);
    const oldOutput = absolute(entry.output);
    const newSource = path.join(SOURCE_ROOT, `${id}.mmd`);
    const newOutput = path.join(OUTPUT_ROOT, `${id}.svg`);

    if (!(await exists(oldSource)) || !(await exists(oldOutput))) {
      throw new Error(`missing legacy pair for ${entry.source}`);
    }
    if ((await exists(newSource)) || (await exists(newOutput))) {
      throw new Error(`semantic target already exists for ${id}`);
    }

    const oldImage = `![${entry.alt}](${markdownLink(documentPath, oldOutput)})`;
    const oldSourceLink = `[Diagram source (Mermaid)](${markdownLink(documentPath, oldSource)})`;
    const newImage = `![${entry.alt}](${markdownLink(documentPath, newOutput)})`;
    const newSourceLink = `[Diagram source (Mermaid)](${markdownLink(documentPath, newSource)})`;

    const replacements = updatesByDocument.get(entry.document) ?? [];
    replacements.push([oldImage, newImage], [oldSourceLink, newSourceLink]);
    updatesByDocument.set(entry.document, replacements);

    nextEntries.push({ id, document: entry.document, alt: entry.alt });
  }

  if (seenIds.size !== IDS.size) {
    throw new Error("semantic-ID mapping contains an unused legacy entry");
  }

  for (const [document, replacements] of updatesByDocument) {
    const documentPath = absolute(document);
    let markdown = await readFile(documentPath, "utf8");
    for (const [before, after] of replacements) {
      if (!markdown.includes(before)) {
        throw new Error(`expected diagram reference missing in ${document}: ${before}`);
      }
      markdown = markdown.replace(before, after);
    }
    await writeFile(documentPath, markdown, "utf8");
  }

  for (const entry of manifest.diagrams) {
    const id = IDS.get(entry.source);
    const oldSource = absolute(entry.source);
    const oldOutput = absolute(entry.output);
    const newSource = path.join(SOURCE_ROOT, `${id}.mmd`);
    const newOutput = path.join(OUTPUT_ROOT, `${id}.svg`);
    await mkdir(path.dirname(newSource), { recursive: true });
    await mkdir(path.dirname(newOutput), { recursive: true });
    await rename(oldSource, newSource);
    await rename(oldOutput, newOutput);
  }

  nextEntries.sort((left, right) => left.id.localeCompare(right.id));
  await writeFile(
    MANIFEST_PATH,
    `${JSON.stringify({ version: 2, diagrams: nextEntries }, null, 2)}\n`,
    "utf8",
  );

  await rm(path.join(SOURCE_ROOT, "docs"), { recursive: true, force: true });
  await rm(path.join(OUTPUT_ROOT, "docs"), { recursive: true, force: true });

  console.log(`Migrated ${nextEntries.length} diagrams to stable semantic IDs.`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
