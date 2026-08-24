# Welcome to Scholion 🦝✨

Scholion is a **private, local-first workspace for recorded evidence**.

It can inspect a recording, choose a safe way to run on the computer you actually have, transcribe locally, survive interruptions, preserve provenance, search a private corpus, navigate results back to verified canonical evidence, keep research notes attached to that evidence, save reusable research questions, manage generation-bound speaker labels, inspect transcript provenance, publish derived transcript views, play verified local source evidence, manage storage through reviewed custody plans, and perform explicit privacy-preserving application update checks in a native desktop shell.

You do **not** need to understand CUDA, DuckDB, SQLite, BM25, model revisions, signatures, or desktop IPC to use the product. Those are implementation details. The desktop should speak in recordings, transcripts, searches, notes, processing, speakers, playback, storage, updates, and evidence. Persistent in-app guidance explains unusual concepts at the point of use instead of assuming this documentation is open beside the app.

> **The short version:** your recording stays yours, canonical JSON remains inspectable evidence, your notes/speaker names/saved searches remain your knowledge, and most machinery built around those things can be thrown away and rebuilt.

## What can Scholion do today?

| You want to… | Scholion currently… |
|---|---|
| Transcribe privately | runs faster-whisper locally from a model you explicitly install and Scholion revalidates before use |
| Avoid melting a smaller laptop | inspects effective CPU/RAM and compatible acceleration before choosing a strategy |
| Process from the desktop | provides readiness, model state, preflight, supervised start/cancel, progress, resume versus retry, and private-state discard |
| Survive interruption | checkpoints completed work and validates the original contract on resume |
| Keep the original intact | treats source media as read-only during normal processing and writes artifacts separately |
| Handle audio/video | selects one audio stream deterministically, requires an explicit user choice when a file contains multiple audio tracks, and canonicalizes the chosen track locally |
| Understand several embedded tracks | shows bounded source-declared title/language/default metadata, then re-runs backend preflight with the exact selected stream |
| Clean noisy audio | optionally applies deterministic local suppression with provenance/timeline checks |
| Work across languages | supports multilingual decoding plus conservative local language attribution |
| Distinguish speakers | preserves anonymous recording-scoped speaker evidence without claiming identity |
| Name known speakers | stores human display names separately and binds them to the exact canonical generation |
| Read handoffs/overlap | presents single-speaker, overlap, mixed, and unattributed spans without flattening uncertainty |
| Inspect a transcript | shows verified generation, selected audio stream, source availability, and processing provenance |
| Publish useful formats | produces canonical JSON plus rebuildable TXT/SRT/WebVTT, including post-hoc desktop publication |
| Search a private corpus | supports lexical BM25, optional semantic retrieval, hybrid RRF, and inspectable Research search options |
| Follow a result to evidence | verifies canonical generation and returns justified segment/word/context/seek coordinates |
| Play the cited recording | re-verifies the exact transcript generation and source before opening an opaque native audio/video session; multi-track sources currently refuse playback rather than risk the wrong embedded track |
| Keep durable research | stores evidence-anchored notes/tags/collections in authoritative private SQLite |
| Reuse questions | stores and edits full typed saved-search intent, then re-resolves current evidence |
| Remember libraries | persists explicit transcript/recording permissions without copying user media |
| Refresh an evolving corpus | incrementally reconciles changed canonical generations and can verify tracked evidence |
| Remove something safely | previews backend-calculated custody scopes/actions, requires an exact plan-bound confirmation, and gives source media its own second guard |
| Clean old processing state | previews eligible private workspaces and marks resumable interrupted/failed jobs before cleanup |
| Check for application updates | performs one explicit signed-metadata request to a fixed GitHub-hosted location; source builds without production verification material remain Updates off and make no request |
| Understand an unfamiliar screen | keeps re-openable, keyboard/touch-accessible contextual help in the app instead of relying on hover-only tips |
| Change appearance | offers Archive, Midnight, Paper, Moss, Plum, Ember, Pride, and Monochrome through one accessible Theme picker |

### Model trust in plain language

Model installation is explicit. Scholion records the immutable provider revision it received, keeps that managed state local, and revalidates the snapshot before using it.

The stronger project-policy layer is also implemented now. When a reviewed model-trust catalog ships inside a Scholion release, installation requests the exact approved upstream revision and the complete downloaded file set, sizes, and SHA-256 values must match before that model can be called **trusted by this Scholion build**. Legacy locally valid models can remain visible/removable without being admitted for new transcription under enforcement.

What does **not** exist yet is a guessed production catalog. Real faster-whisper revisions, licenses, file sets, and regression behavior must be reviewed deliberately before generated trust entries are bundled. Hugging Face remains transport, not the trust authority.

See **[Signed update and model trust channel](security/update-model-trust.md)** and **[Production trust inputs](security/production-trust-inputs.md)**.

### Update trust in plain language

Scholion's update UI is manual. It distinguishes Off, Never checked, Checking, Up to date, Trusted update available, Staging/Staged, and bounded failure. Signed metadata must pass key/signature, publication/expiry, stable-channel, platform, anti-rollback, and equivocation checks before it can authorize an artifact. A downloaded artifact must then match the signed byte count and SHA-256 exactly.

A staged package is **not installed**. Native activation plus Windows/macOS signing/notarization belongs to the later packaging milestone.

An update check is network activity, but it is not behavioral telemetry. GitHub/CDN can observe ordinary connection metadata such as IP address and request time. Scholion does not send an installation ID, corpus/research content, hardware/model inventory, or product-behavior data.

## Pick your doorway

- **[Getting started](getting-started.md)** for the source-build path, desktop path, and first transcript.
- **[Audio tracks](audio-tracks.md)** for single-track behavior, explicit multi-track selection, source-declared track labels, canonical stream provenance, and the current playback limitation.
- **[In-app guidance](in-app-guidance.md)** for persistent help controls and why they describe rather than duplicate backend policy.
- **[Processing Center](architecture/processing-center.md)** for the desktop processing authority split.
- **[Transcript and speaker tools](transcript-tools.md)** for generation-bound details, speaker management, overlap presentation, and post-hoc publication.
- **[Verified native playback](native-playback.md)** for source re-verification, opaque media sessions, exact seek coordinates, and the multi-audio fail-closed rule.
- **[Storage and lifecycle controls](storage-lifecycle.md)** for plan-first transcript custody, source protection, private-state retention, and native boundary details.
- **[Find things across the whole local library](library-discovery.md)** for grouped Library discovery.
- **[Research search](research-search.md)** for Match, Search options, saved searches, and the typed backend contract beneath the ordinary UI.
- **[Your notes should survive the machinery](research-notes.md)** for evidence notes, tags, collections, saved research intent, anchor maintenance, and the future freeform-notebook distinction.
- **[From search result to the exact evidence](evidence-navigation.md)** for verified canonical navigation and the evidence reader/cursor.
- **[Transcript time without calculator gymnastics](time-navigation.md)** for timeline and source-relative coordinates.
- **[Give the anonymous speakers names](speaker-names.md)** for human-authored display labels and generation semantics.
- **[Semantic search, without the mystery box](semantic-search.md)** for local semantic/hybrid retrieval.
- **[Signed update and model trust channel](security/update-model-trust.md)** for implemented supply-chain mechanics and privacy boundaries.
- **[Production trust inputs](security/production-trust-inputs.md)** for the frozen native verifier/key-rotation decision and real-model review procedure.
- **[Pre-release security hardening](security/release-hardening.md)** for what still qualifies as a release gate versus post-MVP hardening.
- **[Desktop themes and accessibility](development/desktop-accessibility.md)** for the eight-skin semantic token system and contrast qualification.
- **[Frontend testing strategy](development/frontend-testing.md)** for frontend/backend test ownership and mutation policy.
- **[Architecture and redundancy audit](architecture/redundancy-audit.md)** for the completed architecture consolidation, post-update re-audit, and intentional remaining boundaries.
- **[Safe deletion and retention](architecture/safe-deletion-retention.md)** for the underlying custody contract.
- **[Post-MVP research roadmap](post-mvp-roadmap.md)** for later research-native workflows.
- **[SECURITY.md](../SECURITY.md)** for repository security reporting.
- **[Architecture](architecture/README.md)** and **[Development docs](development/)** for maintainers.

## The Scholion family portrait

```mermaid
flowchart LR
    A[Your recording] --> B[Local transcription]
    B --> C[Canonical transcript]
    C --> D[Lexical semantic hybrid search]
    D --> E[Verified evidence navigation]
    E --> F[Research authority]
    F --> D
    D --> G[Unified discovery]
    F --> G
    G --> H[Saved searches]
    C --> I[Typed custody planning]
    F --> I
    B --> I
    H --> J[Incremental refresh]
    J --> K[Desktop Library]
    E --> K
    F --> L[Desktop Research]
    K --> M[Updates and release trust]

    classDef source fill:#F9D5E5,stroke:#7B2E52,stroke-width:2px,color:#22151B
    classDef process fill:#E8D9FF,stroke:#68469B,stroke-width:2px,color:#1F1630
    classDef evidence fill:#FFF0B8,stroke:#8A6B18,stroke-width:2px,color:#2C260F
    classDef view fill:#DDF5E3,stroke:#347A46,stroke-width:2px,color:#142719
    classDef inspect fill:#D8EEFF,stroke:#2E617B,stroke-width:2px,color:#12222A
    classDef stop fill:#FFD6D6,stroke:#9E3434,stroke-width:2px,color:#351616

    class A source
    class B,M process
    class C,E,F evidence
    class D,G,H,J view
    class I stop
    class K inspect
    class L process
```

<details>
<summary>Static diagram fallback if rich rendering is unavailable</summary>

![Scholion family portrait static diagram](diagrams/docs-family-portrait.svg)

</details>

Text fallback: canonical evidence feeds rebuildable search; search resolves back to verified evidence; durable notes/tags/collections, speaker labels, and saved searches remain authoritative human knowledge; lifecycle and refresh reuse those identities; the desktop Processing, Library, transcript-tools, playback, Research, Storage, and Updates surfaces consume the same application authorities.

## What belongs to you, and what can the raccoon rebuild? 🦝

| Data | What it is | Rebuildable? |
|---|---|---|
| Original recording | source evidence | **No** |
| Canonical transcript JSON | authoritative transcript evidence | **No** |
| Speaker display labels | user-authored knowledge | **No** |
| Research notes, tags, collections, anchors | user-authored knowledge | **No** |
| Saved searches | user-authored query intent | **No** |
| Remembered locations | machine-local app preference | **No, but reconcile on another machine** |
| Theme preference | presentation preference | Yes / non-evidence |
| TXT / SRT / WebVTT | publication views | Yes |
| Normalized/enhanced working audio | private processing material | Yes |
| Checkpoint workspace after publication | execution/recovery state | Usually disposable |
| Lexical/semantic/research databases | derived projections | Yes |

If deleting a search projection destroys unique human-authored information, something has gone very wrong.

## The desktop today

Research/search, Processing, desktop comprehension/themes, transcript/speaker tools, verified native playback, re-openable contextual guidance, custody-aware Storage, and manual trusted-update presentation are coherent MVP slices.

Research uses ordinary product language by default. Processing presents backend planning/admission rather than duplicating it. Multi-track selection is backend-required and backend-replanned. Transcript tools pass exact generation identity into Python for details, speaker mutation, and publication. Playback does the same for source authorization, then Rust owns an opaque opened-file session.

Storage follows the same rule: React sends typed lifecycle intent and renders a plan calculated by application authority; Python recalculates at apply time and refuses stale confirmation. Updates likewise exposes only status/check/stage intent while application code owns endpoint, platform, trust state, and artifact selection.

The architecture/redundancy audit remains closed after a post-#144 re-audit. The only new duplicate authority found was update-service construction inside the adapter, now moved back to application-layer composition. Duplicate supply-chain file hashing was also consolidated. The update bridge itself remains separate because network/trust/staging authority is not the same capability as ordinary desktop, playback, custody, or supervised Processing work.

## What comes next

The Scholion identity migration and application-side update/model-trust mechanics are complete. The current milestone is issue #145:

1. finish the pre-packaging redundancy/trust-input/documentation cleanup and final product icon;
2. **then** package Windows/macOS with the managed runtime/native dependencies, real public verification keys, reviewed model catalog, OS signing/notarization, update activation, first-run/repair/uninstall semantics; official Linux binary packaging remains blocked by #135;
3. qualify the real packages on representative devices, including #114's remaining CPU-only/accelerator task-transport evidence; and
4. release the MVP.

Backup/restore + selected research portability, packaged semantic custody, and broader research-native features are useful **post-MVP** work. They are not reasons to hold the first packaged Scholion build hostage.

See **[ROADMAP.md](../ROADMAP.md)** for the capability audit and detailed sequencing. Editorial/Mermaid rules live in **[documentation-style.md](documentation-style.md)**.
