# Scholion roadmap 🗺️✨

Scholion is a **private, local-first workspace for recorded evidence**. Its job is not merely to transcribe audio. It turns local recordings into reproducible canonical transcript evidence, keeps provenance and user-authored research durable, makes private corpora searchable, and lets every useful result navigate back to exact verified evidence.

Modern Scholion restarted on August 2, 2026. The MVP product foundation is now substantially built: import, local processing, explicit embedded-audio-track choice, canonical evidence, lexical/semantic/hybrid retrieval, verified navigation, durable notes/tags/collections/saved searches, transcript and speaker tools, native source playback, lifecycle/retention controls, contextual guidance, accessibility themes, and signed update/model-trust mechanics all exist in repository code.

Issue #145 is complete. PR #164 established the Windows/macOS packaging foundation, PR #166 completed deterministic release provenance plus evidence-safe package lifecycle qualification, and PR #167 completed repository-owned packaged FFmpeg/FFprobe custody. Scholion now has a locked/audited managed frozen runtime, reviewed-master native icon generation, exact unsigned Windows NSIS and macOS DMG preview packages, real packaged-runtime acceptance, deterministic package evidence, evidence-preserving Windows uninstall/reinstall qualification, and self-contained reviewed media-tool custody. The active release tranche is now **production trust inputs**: real reviewed faster-whisper policy, approved public update verification material, and native Ed25519 verification. Signing/notarization, native update activation, and representative-device qualification remain later release gates.

![Scholion roadmap 🗺️✨ diagram](./docs/diagrams/generated/scholion-roadmap.svg)

[Diagram source (Mermaid)](./docs/diagrams/src/scholion-roadmap.mmd)

Text fallback: Scholion already spans local media, reliable transcription, canonical evidence, private retrieval, verified navigation, durable research, native desktop workflows, lifecycle/playback, signed update/model-trust mechanics, hosted cross-platform real-media acceptance, completed pre-packaging readiness, exact Windows/macOS preview-package qualification, deterministic release provenance, evidence-safe Windows package lifecycle, and repository-owned packaged FFmpeg/FFprobe. The next tranche provisions production update/model trust inputs and native verification before OS signing/notarization, native update activation, and representative physical-device qualification. Official Linux binary distribution remains separately blocked by issue #135.

# MVP foundation now

“Implemented” means the application authority exists in code and is protected by automated tests. It does not mean a production installer, production signing key, reviewed model catalog, or representative-device release evidence already exists.

## Local processing and model custody

Scholion inspects effective CPU/memory and accelerator topology before admitting a local strategy. FFprobe owns bounded media inspection; `AudioStreamSelector` owns deterministic exact-stream selection; FFmpeg owns canonical normalization and optional deterministic enhancement. Managed model installation is explicit, records the immutable provider revision actually installed, and locally revalidates repository/revision/layout expectations before transcription.

Project-owned model policy trust is now implemented. When a reviewed `model-trust.json` is bundled, `ModelManager` pins the exact approved upstream revision, verifies the complete file set/size/SHA-256 before registration and admission, records policy evidence separately from provider-local validation, and re-verifies current trust later. Legacy locally valid models remain visible/removable but cannot authorize new transcription under enforcement until a trusted reinstall succeeds.

The repository intentionally still contains **no guessed production faster-whisper trust entries**. Issue #145 froze the review procedure; the real immutable revisions, licenses, regression evidence, and measured entries remain deliberate release inputs for the next production-trust tranche.

Packaged Windows/macOS preview runtimes now own their FFmpeg/FFprobe dependency instead of inheriting ambient host PATH. PR #167 pins reviewed platform inputs, validates exact bytes, binds media-tool identity into release evidence, and makes frozen Scholion resolve only its bundled `media-tools` directory. Source/development mode may still use PATH for ordinary developer ergonomics. These custody controls are strong provenance and dependency-boundary controls, not an OS parser sandbox.

The Processing Center presents readiness, model state, preflight, supervised start/cancel, durable job status, checkpoint resume, fresh retry, private execution-state discard, bounded public task failures, in-place model task activity, and speaker-labeling capability gating. Python remains authoritative for planning, admission, model custody, stream-selection validation, resume compatibility, and transcript correctness. Tauri owns allowlisted long-running child-process lifetime. React submits intent and presents state.

See **[Audio tracks](docs/audio-tracks.md)**, **[Processing Center](docs/architecture/processing-center.md)**, **[Local model management](docs/architecture/model-management.md)**, **[Signed update and model trust channel](docs/security/update-model-trust.md)**, and **[Production trust inputs](docs/security/production-trust-inputs.md)**.

## Canonical evidence and research

Canonical JSON is authoritative transcript evidence. It retains source/execution provenance, source-relative segment and word timing, language evidence, optional anonymous speaker evidence, and enhancement provenance. TXT, SRT, and WebVTT are deterministic publications, not transcript authority.

Authoritative SQLite owns evidence notes, tags, collections, anchor history, and saved-search intent. DuckDB retrieval/research state is rebuildable. Search ranking never becomes source truth: evidence navigation verifies the canonical generation before presenting precise context, playback coordinates, or accepting a durable research anchor.

The first-release Research circuit is coherent: find evidence → verify → annotate → organize → save/replay a question → return to exact evidence → deliberately maintain an anchor when necessary.

## Transcript tools, playback, lifecycle, and locations

Transcript tools are generation-bound. Library results can inspect provenance, selected stream identity, speaker presentation, human display names, and deterministic transcript publications without giving React canonical/source paths.

Verified playback uses the same evidence discipline. Python re-verifies canonical generation, source identity, source bytes, coordinate bounds, and audio-stream identity. Rust owns the opened file handle and opaque media-session lifetime. Multi-track transcription is supported; multi-track playback fails closed until the native layer can prove the rendered stream matches canonical provenance.

Deletion is preview-first and plan-bound. Source-recording deletion requires its own scope, second UI guard, and provenance verification. Retention is intentionally narrower and never ages away canonical transcripts, source media, published transcripts, human research, or lightweight lifecycle manifests.

Remembered recording/transcript locations are durable permissions. Discovery itself does not hash, probe, copy, or transcribe candidate media. Automatic processing remains a separate explicit policy.

## Desktop presentation and accessibility

The desktop architecture remains:

```text
Scholion Desktop
├── React + TypeScript + Vite     presentation
├── Tauri / Rust                  narrow native capability host
└── Python Scholion               application and evidence rules
```

The shell has eight skins: **Archive, Midnight, Paper, Moss, Plum, Ember, Pride, and Monochrome**. They share one semantic token contract for surfaces, text, controls, focus, errors, selection, and accent foregrounds. Theme preference is local presentation state and never evidence/research state.

The desktop now also has an explicit **Updates** workspace. Manual checks use one fixed GitHub-hosted metadata location, expose honest network/privacy copy, and remain completely off in source/development builds that lack a production verification key.

# Capability → desktop audit

| Capability | Authority | Desktop status | Remaining MVP/release work |
|---|---|---|---|
| Machine/resource policy | Python runner/admission | implemented | representative-device calibration |
| Model custody | managed revision + project policy verification | implemented mechanics | deliberate real catalog review/provisioning for release |
| Import/locations | durable permissions/discovery | implemented | optional settings polish |
| Processing | plan, execute, checkpoint, resume/retry | implemented | representative native task qualification under #114 |
| Embedded audio tracks | Python probe/selector/planner + FFmpeg exact map | implemented | future proven multi-track playback; separate-file sync remains out of scope |
| Canonical JSON | authoritative evidence | implemented consumer views | package/qualification only |
| Speaker labels | generation-bound human state | implemented | optional organization polish |
| Provenance/details | canonical verified inspection | implemented | richer troubleshooting optional |
| TXT/SRT/WebVTT | deterministic publication | implemented | optional export organization |
| Lexical/semantic/hybrid search | private retrieval | implemented | current source dependency path is adequate for MVP; packaged semantic custody is post-MVP |
| Verified evidence navigation | exact generation + timing/seek | implemented | representative-device playback qualification |
| Notes/tags/collections | SQLite authority | implemented | optional organization polish; freeform memos later |
| Saved searches | durable typed intent | implemented | optional organization polish |
| Safe deletion/retention | typed plan-bound Python custody | implemented | representative-device/path qualification |
| Native source playback | Python authorization + Rust session | implemented | decoder/device qualification |
| Themes/accessibility | semantic palette + browser/native controls | 8 skins qualified | representative OS/forced-colors checks |
| Architecture/redundancy | capability-blind transport + app-layer composition + one Research contract | re-audited after #144 | no known duplicate authority remains in current milestone |
| Frontend tests | strict TS/build + Playwright/axe | primary surfaces including Updates covered | grow with features, avoid duplicated backend policy |
| Update trust | exact-byte signed manifest + fixed endpoint + rollback/expiry/equivocation + staging + UI | implemented mechanics | approved public key set, native verifier wiring, signed native activation |
| Packaging | managed frozen runtime + Tauri + repository-owned FFmpeg/FFprobe | Windows/macOS unsigned preview foundation, lifecycle/provenance, and managed media custody complete through #167 | production update/model trust inputs, signing/notarization, native activation, final release evidence; Linux public package blocked by #135 |
| Backup/restore | authority boundaries known | not implemented | **post-MVP** portability/data-safety feature |
| Representative hardware | platform CI + policy contracts | partial | real devices; #114 owns current task-transport evidence |

# MVP critical path

## 1. Core product workflows complete

Research/search, Processing, explicit embedded-track transcription, transcript/speaker tools, verified playback, lifecycle/retention, contextual guidance, themes/accessibility, architecture consolidation, and product identity are complete implementation foundations.

## 2. Signed update and model-trust mechanics complete

Merged PR #144 completed the application-side trust mechanics:

- fixed-endpoint manual **Check for updates**;
- no background update request in source builds without production verification material;
- exact-byte signed manifest verification seam;
- publication/expiry checks;
- monotonic sequence rollback protection;
- same-sequence equivocation rejection;
- stable-channel and platform enforcement;
- private local trust state without an installation ID;
- streamed artifact staging with exact signed byte count and SHA-256;
- explicit Off / Never checked / Checking / Up to date / Trusted update available / Staging / Staged / Failure UI states;
- project-owned model-trust catalog/enforcement mechanics; and
- deterministic release/model metadata generation tooling.

A staged update is deliberately **not** called installed. Native activation plus OS package signing/notarization remains a later packaging boundary.

## 3. Pre-packaging release readiness complete (#145)

Issue #145 closed the narrow cleanup that needed to be frozen before installer/update compatibility became real:

- complete the post-#144 redundancy re-audit;
- keep application-service construction out of desktop adapters;
- centralize capability-blind supply-chain helpers where authority is genuinely identical;
- freeze the production verifier/key-rotation decision without committing private signing material;
- define the human review procedure for real faster-whisper trust entries;
- reject invalid signing inputs before offline signing;
- truth-sync roadmap/README/security/release documentation and trackers; and
- replace the placeholder native icon with the final Scholion product mark/master asset.

The verifier decision is documented in **[Production trust inputs](docs/security/production-trust-inputs.md)**: the next production-trust tranche will exact-pin reviewed `ed25519-dalek` 3.0.0 at the native boundary and bundle approved public verification material. The Cargo lockfile change belongs with that implementation, where Cargo can generate and audit the dependency graph correctly.

## 4. Windows/macOS package foundation, lifecycle, and native-media custody complete

PR #164 completed the first packaging-foundation tranche:

- locked/audited managed Python runtime construction with exact PyInstaller custody;
- closed packaged runtime selection at the Tauri boundary;
- reviewed Scholion master → native icon generation;
- unsigned Windows NSIS and macOS DMG construction;
- real JFK transcription through the frozen runtime before bundling;
- exact NSIS install / exact DMG mount followed by packaged-runtime re-qualification; and
- SHA-256 artifact identity plus explicit `release_ready: false` qualification evidence.

Issue #165 / PR #166 then completed the lifecycle/evidence tranche:

- deterministic provenance bound to exact qualified package bytes, checksums, commit, lockfiles/config/master icon, and bounded build-tool identity;
- Windows install → real retained Scholion evidence/state → uninstall → preservation check → reinstall the same installer → second acceptance → final uninstall; and
- an honest macOS DMG mount/runtime/unmount qualification boundary without pretending a DMG has Windows-style installer lifecycle semantics.

PR #167 completed the managed-media custody tranche:

- reviewed, versioned FFmpeg/FFprobe inputs for supported packaged Windows/macOS candidates;
- deterministic preparation/identity evidence bound into release qualification and provenance;
- one media-tool resolver with a hard frozen-runtime boundary;
- no packaged fallback to ambient host PATH;
- probing, decode, enhancement, and health checks routed through the same authority;
- exact bundled media-tool identity checked during packaged real-media acceptance; and
- post-PyInstaller overlay on macOS so PyInstaller cannot silently rewrite the reviewed Mach-O media-tool bytes before custody verification.

These are artifact-level hosted-CI proofs, not production trust material, OS signatures, or representative-device evidence. `release_ready` remains false.

## 5. Production trust inputs ← current milestone

The next release tranche is deliberately narrower than “finish packaging.” It should:

- deliberately select and review the real faster-whisper revisions/licenses intended for the first release;
- generate, review, commit, and bundle the complete model-trust catalog entries for those exact snapshots;
- provision the approved public update verification-key set without committing private signing material;
- exact-pin `ed25519-dalek` 3.0.0 in the native Rust host and audit the generated lockfile/dependency graph;
- wire strict native Ed25519 verification to the existing exact-byte update manifest contract; and
- qualify fail-closed source behavior plus valid/invalid production-shaped verification vectors.

This tranche must not invent a private signing key, guess model hashes, or promote whichever development model cache happens to exist. The generator measures bytes; human review confers policy trust.

After production trust inputs are stable, the remaining release gates are:

- Windows code signing and macOS signing/notarization of the production-shaped package bytes;
- platform-safe native update activation that executes only an already trusted, OS-signed candidate;
- storage onboarding/repair/offline/update behavior that needs representative package/device evidence;
- final production release checksums/provenance/SBOM publication; and
- representative-device evidence-safe lifecycle qualification where hosted CI cannot substitute for a real machine.

Packaging must not silently move/delete user evidence. Uninstall should remove application/runtime/cache state only according to explicit rules while preserving original recordings, canonical transcript evidence, and authoritative research unless the user separately requests destruction.

Public **Linux** binary packaging remains blocked by issue #135 while the supported Tauri Linux graph contains the tracked GTK3/GLib security debt. Windows/macOS packaging should proceed independently. Do not force unsupported GTK/GLib overrides or maintain a Scholion-specific Tauri fork merely to make the advisory disappear.

## 6. Representative release qualification

Hosted Release Qualification now proves the frozen runtime and exact unsigned Windows/macOS preview package can process pinned real JFK media. PR #164 established that artifact boundary, PR #166 added stronger Windows lifecycle/evidence custody and deterministic provenance, and PR #167 removed ambient packaged FFmpeg/FFprobe dependency by proving the bundled reviewed media-tool bytes. This remains artifact-level CI evidence, not representative-device evidence. Continue by qualifying what users will actually run:

- Windows 8 GB CPU-only;
- ordinary 16 GB systems;
- Apple Silicon;
- accelerator-capable NVIDIA hardware;
- larger 32/64 GB systems;
- Unicode/long paths and external disks;
- low-disk and interrupted operations;
- offline update/model/transcription behavior;
- upgrades/reinstall;
- scaling/native controls/media codecs;
- keyboard/forced-colors/accessibility behavior; and
- package signature/notarization plus release-metadata byte identity.

Issue #114 specifically remains qualification-only until real CPU-only and accelerator-capable React → Tauri → Rust → Python task-transport evidence is recorded. Browser mocks and hosted CI are not a substitute for that evidence.

# Security hardening boundary

Current FFmpeg/FFprobe controls include repository-owned packaged custody, no-shell invocation, file-only media protocols, explicit timeouts, bounded metadata, source mutation checks, and private planned output. These materially reduce risk but are **not an OS sandbox**.

OS-level parser capability reduction remains worthwhile before describing Scholion as highly hardened against malicious media. It is not being converted into an endless blocker for source builds or an early packaged preview. Keychain/application-layer encryption likewise remains threat-model-driven and must not precede recovery/portability design merely because secure-sounding software often has encryption.

# Post-MVP / future state

The following remain valuable but are intentionally **not prerequisites for the MVP packaging milestone**.

## Backup/restore + research portability

Back up canonical evidence and authoritative research, rebuild projections on restore, reconcile machine-local paths, and export selected research with stable evidence identity. The backup manifest should describe stable authority and relationships, not turn derived views into source truth.

This is important data-safety work, especially before any future application-layer encryption, but it is a post-MVP product feature rather than a reason to withhold the first useful packaged Scholion build.

## Packaged semantic custody

The current optional semantic retrieval path is sufficient for source/MVP operation. A later productization tranche can lock/qualify embedding dependencies, immutable embedding-model acquisition, private cache/offline behavior, corpus compatibility, and upgrade semantics.

## Research-native expansion

Freeform research memos/notebook pages, snapshots/diffs, REFI-QDA interoperability, evidence packets, comparison workspaces, evidence-linked writing/script boards, portable research bundles, and live provisional capture remain intentionally separate from the MVP.

A future notebook page should live in authoritative SQLite as its own research-document type with optional explicit references to evidence notes/anchors. It should not weaken the current `ResearchNote` invariant by making evidence provenance nullable.

# Sequencing rule

The rule is now intentionally boring:

**provision production trust inputs → sign/notarize production-shaped packages → activate updates natively → qualify representative devices → publish the MVP release.**

Do not reopen completed product, lifecycle/provenance, or managed-media tranches merely because later research or portability features are interesting. Do not call production secrets, real upstream trust decisions, OS signing, native activation, or representative-device evidence “implemented” until they actually exist.
