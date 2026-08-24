# Deterministic Mermaid documentation

Scholion uses Mermaid as **source**, not as a GitHub runtime rendering dependency.

The editable definitions live under `docs/diagrams/src/`. The checked-in SVGs under `docs/diagrams/generated/` are derived from those definitions with the pinned official Mermaid CLI in this directory. `docs/diagrams/manifest.json` gives every diagram one stable semantic ID and binds that ID to the Markdown document that displays it. The renderer derives both artifact paths from that ID:

```text
docs/diagrams/src/<diagram-id>.mmd
docs/diagrams/generated/<diagram-id>.svg
```

The ID describes what the diagram *is*, not where it happens to appear. Positional or version-looking IDs such as `corpus-search-1` are rejected.

## Normal edit

Install the locked docs-only toolchain once:

```bash
npm ci --prefix tools/mermaid
```

Edit the relevant `.mmd` source, then regenerate the checked-in SVGs:

```bash
npm --prefix tools/mermaid run render
```

The existing `.svg` for that semantic ID is overwritten. A render does not create a new numbered copy. Commit the `.mmd` change and its generated `.svg` together. Never hand-edit a generated SVG.

## Verify without rewriting

```bash
npm --prefix tools/mermaid run check
```

`check` validates semantic IDs, manifest ownership, and Markdown references; rejects positional IDs, inline Mermaid fences, and unregistered diagram files; renders every source into a temporary directory; and byte-compares the result with the committed SVG. It does not modify the repository.

The `mermaid-docs` Quality job runs the same check on pull requests and `main`. The job has read-only repository permission. On current Ubuntu GitHub-hosted runners it enables the kernel user-namespace facility that Chromium's normal sandbox requires; it does not launch Chromium with `--no-sandbox`.

## Add a diagram

1. Choose a short lowercase semantic ID such as `canonical-hashing-stale-refusal`. Do not use document position or an artificial version suffix.
2. Add `docs/diagrams/src/<diagram-id>.mmd`.
3. Add one manifest entry containing that `id`, the owning Markdown `document`, and meaningful `alt` text. Source/output paths are derived and do not belong in the manifest.
4. In the Markdown document, embed `docs/diagrams/generated/<diagram-id>.svg` using the correct relative path and add an adjacent `[Diagram source (Mermaid)](...)` link to the matching `.mmd` file.
5. Run `npm --prefix tools/mermaid run render`, inspect the SVG, then run `npm --prefix tools/mermaid run check` before committing.

Keep the semantic ID stable once published. Reordering a document, inserting another diagram, changing a heading, opening another PR, merging, or rerunning CI does not change that identity and therefore does not create another SVG. A deliberate diagram rename is still allowed, but it is an explicit manifest/source/output/Markdown identity change.

## Reproducibility boundary

- `package-lock.json` freezes Mermaid CLI, Puppeteer, its browser package, and transitive tooling dependencies.
- `mermaid.config.json` freezes deterministic IDs, the ID seed, font family, security level, and flowchart label mode.
- The background is fixed by `render.mjs` rather than inherited from GitHub page CSS.
- Generated SVGs are rebuildable artifacts. `.mmd` source and manifest ownership are the maintained inputs.

A renderer or dependency upgrade is therefore deliberate: update the lock/config as needed, regenerate the complete SVG set, review the visual diff, and let CI prove the new toolchain reproduces its own checked-in output.
