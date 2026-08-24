# Deterministic Mermaid documentation

Scholion uses Mermaid as **source**, not as a GitHub runtime rendering dependency.

The editable definitions live under `docs/diagrams/src/`. The checked-in SVGs under `docs/diagrams/generated/` are derived from those definitions with the pinned official Mermaid CLI in this directory. `docs/diagrams/manifest.json` binds each source and generated asset to the Markdown document that displays it.

## Normal edit

Install the locked docs-only toolchain once:

```bash
npm ci --prefix tools/mermaid
```

Edit the relevant `.mmd` source, then regenerate the checked-in SVGs:

```bash
npm --prefix tools/mermaid run render
```

Commit the `.mmd` change and its generated `.svg` together. Never hand-edit a generated SVG.

## Verify without rewriting

```bash
npm --prefix tools/mermaid run check
```

`check` validates the manifest and Markdown references, rejects inline Mermaid fences and unregistered diagram files, renders every source into a temporary directory, and byte-compares the result with the committed SVG. It does not modify the repository.

The `mermaid-docs` Quality job runs the same check on pull requests and `main`. The job has read-only repository permission. On current Ubuntu GitHub-hosted runners it enables the kernel user-namespace facility that Chromium's normal sandbox requires; it does not launch Chromium with `--no-sandbox`.

## Add a diagram

1. Add a `.mmd` source under `docs/diagrams/src/`, mirroring the owning document's path where practical.
2. Add one entry to `docs/diagrams/manifest.json` with the owning Markdown file, source path, generated SVG path, and meaningful alt text.
3. In the Markdown document, embed that exact SVG path and add an adjacent `[Diagram source (Mermaid)](...)` link to the `.mmd` file.
4. Run `npm --prefix tools/mermaid run render` and inspect the SVG.
5. Run `npm --prefix tools/mermaid run check` before committing.

Keep source and output names stable once published. Renaming is allowed, but it should be an explicit manifest/Markdown/source/output change rather than an incidental renderer side effect.

## Reproducibility boundary

- `package-lock.json` freezes Mermaid CLI, Puppeteer, its browser package, and transitive tooling dependencies.
- `mermaid.config.json` freezes deterministic IDs, the ID seed, font family, security level, and flowchart label mode.
- The background is fixed by `render.mjs` rather than inherited from GitHub page CSS.
- Generated SVGs are rebuildable artifacts. `.mmd` source and manifest ownership are the maintained inputs.

A renderer or dependency upgrade is therefore deliberate: update the lock/config as needed, regenerate the complete SVG set, review the visual diff, and let CI prove the new toolchain reproduces its own checked-in output.
