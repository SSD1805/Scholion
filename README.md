# Scholion 🦝✨

**A private, local-first workspace for recorded evidence.**

Scholion turns audio and video into reproducible canonical transcripts, preserves source and processing provenance, lets people search a private corpus and navigate results back to exact verified evidence, and keeps notes, tags, collections, speaker labels, and saved research questions as durable user-owned knowledge.

Transcription is the engine room, not the whole product. Scholion also inspects the machine, chooses a safe local execution strategy, manages model custody, survives interrupted work, keeps word-level timing and anonymous-speaker evidence, publishes portable transcript views, incrementally reconciles an evolving library, plays verified local source evidence, and gives deletion the same explicit custody rules as creation.

Canonical transcript JSON is authoritative transcript evidence. Human-authored research state is authoritative user knowledge. DuckDB search/research projections and publication formats are rebuildable. The original recording is read-only throughout normal processing and can only be deleted through a separate explicit provenance-checked operation.

> **Scholion's product rule:** do complicated work locally, keep the evidence understandable, portable, and owned by the user.

## Why Scholion?

A *scholion* is an explanatory, critical, or interpretive note attached to a text; the plural is *scholia*. The name matches the product's evidence model: the recording and canonical transcript remain the source evidence, while human notes, labels, collections, and saved research questions accumulate around verified passages without replacing the source. See **[Product identity](docs/product-identity.md)** for the canonical naming contract.

Start with **[docs/README.md](docs/README.md)** for human-facing documentation or **[Getting started](docs/getting-started.md)** for the shortest clone-to-transcript path. The desktop also keeps contextual help available inside the app so ordinary use does not depend on having repository docs open.

## What can it do right now?

Scholion is pre-production, but the backend and desktop cover a coherent path from importing a recording through local processing, evidence search, durable research, transcript/speaker management, verified local playback, custody-aware storage management, and explicit privacy-preserving update checks.

| Area | Current foundation |
|---|---|
| Local transcription | faster-whisper CPU/int8 and CUDA-capable strategies with explicit managed model revisions |
| Hardware awareness | process-visible CPU/RAM, affinity/cgroup limits, accelerator topology, engine capability negotiation, resource admission |
| Media handling | FFprobe inspection, explicit embedded-audio-track confirmation for multi-track files, deterministic exact-stream FFmpeg canonicalization, exact source-relative work windows |
| Reliability | private checkpoints, validated resume, contiguous checkpoint ordering, bounded accelerated prefetch |
| Languages | multilingual decoding plus conservative local text-language attribution |
| Speakers | optional anonymous recording-scoped diarization, word-level handoffs, generation-bound display labels, honest overlap/mixed presentation |
| Difficult audio | optional deterministic FFmpeg noise suppression with provenance/timeline checks |
| Model custody | explicit inventory, install/revalidation and immutable revision receipts plus project-owned exact revision/file-set/size/SHA-256 policy enforcement when a reviewed catalog is bundled |
| Transcript output | canonical JSON plus deterministic TXT, SRT, WebVTT publication views |
| Search | private BM25 lexical retrieval, optional semantic retrieval, hybrid reciprocal-rank fusion |
| Evidence navigation | canonical-hash verification, aligned highlights, bounded context, speaker presentation, source seek coordinates |
| Verified playback | exact-generation/source re-verification, opaque Tauri media sessions, bounded native range streaming, current/older evidence coordinates; multi-track sources currently fail closed for playback |
| Research workspace | authoritative SQLite notes/tags/collections, rebuildable DuckDB projection, desktop browse/create/edit/delete/filter/anchor maintenance |
| Unified discovery | grouped transcript/note/tag/collection query without fabricated cross-type scores |
| Saved searches | durable typed query intent that re-resolves current evidence instead of freezing result snapshots |
| Safe lifecycle | typed plan-bound deletion scopes plus private execution-state retention, exposed through a native Storage workspace with plan review, source second guard, and resume-loss warnings |
| Incremental library | cheap refresh/reconciliation plus durable transcript and recording locations |
| Processing Center | readiness, machine/model state, preflight, explicit multi-track stream confirmation, supervised start/cancel, resume versus retry, job-state discard, diarization/enhancement/publication intent |
| Transcript tools | generation-bound transcript/provenance inspection, speaker naming/removal, overlap-aware transcript view, post-hoc TXT/SRT/VTT publication |
| Updates | fixed-endpoint manual signed-metadata checks, expiry/rollback/equivocation/channel/platform verification, exact size/SHA-256 staging, explicit offline/failure states, no background request in source builds without a production verifier |
| Desktop guidance | persistent screen/overview help plus contextual Evidence, Playback, Transcript, multi-track preflight, Storage, and Updates explanations without duplicating backend policy |
| Desktop presentation | Tauri + React Intake, Processing, Library, verified evidence reader/playback, Research, Storage, Updates, transcript tools, and eight semantic-token themes |
| Accessibility | keyboard/semantic-role tests, axe, non-hover contextual help, explicit light/dark browser schemes, and an eight-skin contrast matrix |
| Architecture hygiene | capability-blind transport, app-layer service composition, one typed saved-question surface, one Research evidence presentation contract; re-audited after the update-channel tranche |
| Quality | Linux/macOS/Windows CI, strict typing, lint/format/security, complexity/dead-code, branch coverage, dependency audit, Playwright/axe, native Rust tests, package verification, targeted mutation qualification |

Model trust has two deliberately separate concepts. Provider/local custody proves what Scholion downloaded and currently observes. Project policy trust proves that the exact repository revision and complete file set match a catalog deliberately approved by the Scholion release. The policy machinery is implemented; the repository intentionally contains no guessed production faster-whisper entries. See **[Signed update and model trust channel](docs/security/update-model-trust.md)** and **[Production trust inputs](docs/security/production-trust-inputs.md)**.

## From recording to useful evidence

```mermaid
flowchart LR
    A[Original recording] --> B[Inspect source and machine]
    B --> C[Choose safe local strategy]
    C --> D[Transcribe and checkpoint]
    D --> E[Canonical transcript JSON]
    E --> F[TXT SRT WebVTT]
    E --> G[Lexical semantic hybrid search]
    G --> H[Verify canonical evidence]
    H --> I[Context highlights and seek]
    I --> J[Durable notes tags collections]
    J --> G
    G --> K[Unified discovery]
    J --> K
    K --> L[Saved searches navigation]
    E --> M[Custody-aware deletion planning]
    J --> M
    D --> M

    classDef source fill:#F9D5E5,stroke:#7B2E52,stroke-width:2px,color:#22151B
    classDef process fill:#E8D9FF,stroke:#68469B,stroke-width:2px,color:#1F1630
    classDef evidence fill:#FFF0B8,stroke:#8A6B18,stroke-width:2px,color:#2C260F
    classDef view fill:#DDF5E3,stroke:#347A46,stroke-width:2px,color:#142719
    classDef inspect fill:#D8EEFF,stroke:#2E617B,stroke-width:2px,color:#12222A
    classDef stop fill:#FFD6D6,stroke:#9E3434,stroke-width:2px,color:#351616

    class A source
    class B,C,D process
    class E,H evidence
    class F,G,K,L view
    class I inspect
    class J source
    class M stop
```

<details>
<summary>Static diagram fallback if rich rendering is unavailable</summary>

![Scholion recording-to-evidence static diagram](docs/diagrams/recording-to-evidence.svg)

</details>

Text fallback: source media is inspected and transcribed locally into canonical JSON; rebuildable search finds passages; canonical verification turns results back into evidence; durable human research attaches to that evidence; custody planning keeps destructive work explicit.

Search ranking is not source truth. A result points back to canonical transcript coordinates, and navigation verifies that generation before presenting precise evidence or accepting a durable note anchor.

## Desktop status

The Tauri + React desktop currently provides:

- native file/folder selection and remembered-location permissions;
- recording discovery without automatic processing side effects;
- a Processing Center for readiness, model state, job state, preflight, explicit embedded-audio-track confirmation, launch, cancel, resume/retry distinction, and private-state discard;
- Library search across transcripts, notes, tags, and collections;
- verified evidence context and source-relative cursor coordinates;
- generation/source-verified local audio/video playback from that evidence cursor without exposing source paths to React;
- Research note create/edit/delete, tag/collection navigation, saved-search lifecycle, typed retrieval controls, exact-generation evidence return, and explicit anchor review;
- transcript details/provenance, generation-safe speaker-name management, explicit speaker-overlap presentation, and post-hoc derived publication;
- a Storage workspace for backend-planned transcript custody changes, explicit source protection, and previewed old-processing cleanup;
- an Updates workspace with explicit Off / Never checked / Checking / Up to date / Trusted update available / Staging / Staged / Failure states;
- persistent **How this screen works** and **How Scholion works** guidance plus contextual Evidence/Playback/Transcript/multi-track/Storage/Updates explanations;
- eight accessible presentation skins through one compact theme picker; and
- persisted presentation preference without mixing theme state into evidence or research.

The browser/webview does **not** receive canonical/source filesystem paths for evidence navigation, transcript tools, playback, or lifecycle plans. It also does not choose update URLs, headers, artifacts, installer commands, or trust keys. Rust owns native desktop capability and opened media sessions; Python owns application/evidence/custody/media-selection/update policy; React owns presentation and explicit user intent.

When a file contains several embedded audio streams, Python reports that explicit confirmation is required. The desktop shows bounded source-declared title/language/default metadata when available, accepts the user's stream choice, and sends only that exact index back to Python for a fresh preflight. Start remains disabled until the backend returns a plan bound to that stream. Canonical provenance records the exact stream index and resume restores it. See **[Audio tracks](docs/audio-tracks.md)**.

Transcript tools are generation-bound. A long-lived UI cannot silently rename a speaker in a newer transcript generation: every inspect/mutation/publication request carries the exact canonical SHA-256 the user opened, and Python rejects stale identity. See **[Transcript and speaker tools](docs/transcript-tools.md)**.

Playback follows the same evidence discipline. Python re-verifies the exact canonical generation, original source bytes, bounded coordinate, and audio-stream identity; Rust then turns the approved source into an opaque local media session. Multi-track transcription is supported, but multi-track playback currently fails closed because the system WebView cannot yet prove it rendered the same embedded stream that produced the transcript. See **[Verified native playback](docs/native-playback.md)**.

Storage follows the same authority split. React requests a plan and renders the backend's effective scopes/actions; a separate fixed Tauri command can invoke only the custody bridge; Python recalculates the plan at execution and refuses stale confirmation tokens. Source and canonical paths are stripped before the response reaches React. See **[Storage and lifecycle controls](docs/storage-lifecycle.md)**.

Updates follow a similarly narrow boundary. React can request only status, check, or stage. The update endpoint and platform artifact remain application policy. Source/development builds without production verification material report **Update checking is off** and make no request. A manual check is network activity, not behavioral telemetry: GitHub/CDN can observe ordinary connection metadata such as IP address/time, but Scholion sends no installation ID, corpus/research content, hardware/model inventory, or product-behavior data. A staged artifact is not called installed until the later native packaging/signing boundary can activate it safely.

In-app guidance is deliberately re-openable and non-hover-only where popovers are used. It explains contracts where users encounter them but carries no filesystem/database/process authority and does not recreate application policy in React. See **[In-app guidance](docs/in-app-guidance.md)**.

There are still no end-user installers or Releases. The supported path remains a source build while pre-packaging cleanup and the later packaging/first-run milestone are completed.

## Themes and accessibility

Scholion ships **Archive, Midnight, Paper, Moss, Plum, Ember, Pride, and Monochrome**. They are not eight independent CSS systems. Every skin supplies the same semantic roles for background, surfaces, text, borders, accent/on-accent, controls, focus, errors, and selection.

Pride adds a decorative rainbow edge while leaving status meaning in text/structure. Monochrome is intentionally grayscale rather than another tinted dark theme. Every registered skin declares its native browser `color-scheme` and automatically enters the same Playwright WCAG-oriented contrast matrix and axe qualification.

Read **[Desktop themes and accessibility](docs/development/desktop-accessibility.md)** for the contract.

## Install the current source build

The supported development/source path uses Python 3.12 and Scholion's repository-local bootstrap. A system-wide `uv` installation is not required:

```bash
git clone https://github.com/SSD1805/Scholion.git
cd Scholion
python3.12 scripts/bootstrap_python.py
source .venv/bin/activate
scholion init
scholion doctor
```

On Windows, use `py -3.12 scripts\bootstrap_python.py`; activation is optional if you invoke `.venv\Scripts\python.exe` explicitly. See **[Project-local developer toolchain](docs/development/project-local-toolchain.md)** for the complete cross-platform contract and **[Desktop development prerequisites](docs/development/desktop-development.md)** for the native desktop.

## Plan, transcribe, and resume from the CLI

```bash
scholion models recommend
scholion models install small
scholion transcribe interview.m4a --dry-run
scholion transcribe interview.m4a
```

For a source with several embedded audio tracks, bind the exact FFmpeg stream index:

```bash
scholion transcribe meeting.mkv --audio-stream 3 --dry-run
scholion transcribe meeting.mkv --audio-stream 3
```

Add derived publication formats when useful:

```bash
scholion transcribe interview.m4a --export txt --export srt --export vtt
```

Resume a validated interrupted job:

```bash
scholion transcribe interview.m4a --resume JOB_ID
```

Model acquisition is explicit and network-bearing. Resume rechecks source identity and current resource admission rather than silently changing the execution contract, including its selected audio stream.

## Search, annotate, and name speakers

```bash
scholion library rebuild
scholion library search "housing insecurity"
scholion library find "housing insecurity" --context-segments 1
scholion library speakers list JOB_ID
scholion library speakers name JOB_ID speaker-02 "Dr. Chen"
scholion library speakers transcript JOB_ID
```

Speaker names are durable user-authored state. `speaker-02` remains anonymous machine-produced evidence; the human label is separate and generation-bound.

Research metadata can constrain retrieval, and saved searches persist the question rather than today's result snapshot. See **[Research search](docs/research-search.md)** and **[Research notes](docs/research-notes.md)**.

## Delete exactly what you mean

Deletion remains dry-run first from the CLI:

```bash
scholion library delete JOB_ID --scope library-view
```

The plan prints actions and a confirmation token. Nothing changes until the same request is repeated with that token. `canonical-transcript` does **not** imply `research-notes`, `saved-searches`, or `source-recording`.

The native desktop exposes the same contract under **Storage**: select explicit scopes, preview the backend-calculated plan, review any scope expansion/preservation consequences, then apply that exact plan. Source recording removal requires an additional acknowledgment and provenance check.

Age-based retention is narrower:

```bash
scholion library retention --execution-days 30
```

The Storage workspace can preview the same private-state cleanup and marks interrupted/failed candidates whose resume capability would be lost. Retention preserves canonical transcripts, human research, source media, and lightweight lifecycle manifests.

Read **[Storage and lifecycle controls](docs/storage-lifecycle.md)** and **[Safe deletion and retention](docs/architecture/safe-deletion-retention.md)** for the exact contract.

## What belongs to you?

| Artifact | Role | Rebuildable? |
|---|---|---|
| Original recording | source evidence | **No** |
| Canonical transcript JSON | authoritative transcript evidence | **No** |
| Speaker display labels | user-authored knowledge | **No** |
| Notes, tags, collections, evidence anchors | user-authored knowledge | **No** |
| Saved searches | user-authored query intent | **No** |
| Remembered locations | durable machine-local app preference | **No** |
| Theme preference | presentation preference | Yes / non-evidence |
| TXT/SRT/WebVTT | publication views | Yes |
| Normalized/enhanced working audio | private processing material | Yes |
| Lexical/semantic/research query projections | private derived state | Yes |

A database is allowed to make evidence useful. It is not allowed to become the only place unique evidence or human research exists.

## For maintainers

Start with **[docs/architecture/README.md](docs/architecture/README.md)**, **[Architecture and redundancy audit](docs/architecture/redundancy-audit.md)**, **[Processing Center](docs/architecture/processing-center.md)**, **[Audio tracks](docs/audio-tracks.md)**, **[Local model management](docs/architecture/model-management.md)**, **[Signed update and model trust channel](docs/security/update-model-trust.md)**, **[Production trust inputs](docs/security/production-trust-inputs.md)**, **[Transcript and speaker tools](docs/transcript-tools.md)**, **[Verified native playback](docs/native-playback.md)**, **[Storage and lifecycle controls](docs/storage-lifecycle.md)**, **[In-app guidance](docs/in-app-guidance.md)**, **[Safe deletion and retention](docs/architecture/safe-deletion-retention.md)**, and **[frontend/SECURITY.md](frontend/SECURITY.md)**.

Normal qualification includes Ruff, strict mypy, Vulture, Radon, branch coverage, dependency audit, package verification, TypeScript/build/audit gates, native Cargo compilation/tests, Playwright/axe, the eight-theme contrast matrix, targeted Poodle mutation workflows, and Linux/macOS/Windows CI. See **[Frontend testing strategy](docs/development/frontend-testing.md)** for frontend/backend test ownership.

## Where the project goes next

Research/search, Processing, explicit embedded-track transcription, desktop comprehension/themes, transcript/speaker tools, verified native playback, contextual guidance, desktop lifecycle/retention controls, architecture consolidation, product identity, and the application-side update/model-trust mechanics are complete MVP foundations.

The current sequence is intentionally narrow:

1. **#145 pre-packaging release readiness:** final redundancy pass, production trust-input decisions, documentation truth-sync, and final Scholion icon/brand master;
2. **packaging:** managed runtime/native dependencies, Windows/macOS installers, real public update keys/model catalog, OS signing/notarization, update activation, first-run/repair/uninstall semantics; official Linux binary packaging remains blocked by #135;
3. **representative release qualification:** real packaged CPU-only/accelerator/Apple/Windows behavior, including #114's remaining native task-transport evidence; and
4. **MVP release.**

Backup/restore + research portability, packaged semantic-model custody, and freeform research notebook/memo features remain valuable **post-MVP** work. They are no longer being treated as reasons to postpone the first useful packaged Scholion build.

See **[ROADMAP.md](ROADMAP.md)** for the capability audit and sequencing.
