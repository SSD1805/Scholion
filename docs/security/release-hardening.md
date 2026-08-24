# Pre-release security hardening roadmap

This document turns Scholion's remaining security work into explicit release gates rather than a pile of unrelated checkboxes. Scholion is local-first, but local software still processes hostile media, stores sensitive research, downloads model/application artifacts, and crosses a WebView → Rust → Python boundary. Privacy therefore depends on both custody and containment.

The implementation status below is deliberately conservative. Repository mechanics, production release inputs, packaging, and representative qualification are separate things.

## Release gate A: supply-chain trust

### Signed application metadata

**Implemented in repository code:**

- strict versioned signed-envelope and payload schemas;
- exact signed payload bytes rather than JSON re-serialization;
- Ed25519 verifier interface with bounded key IDs and signature encoding;
- publication-time and expiry enforcement;
- monotonic release sequence rollback protection;
- rejection of same-sequence signed-content equivocation;
- explicit stable-channel enforcement;
- exact per-platform artifact URL, byte size, and SHA-256 authorization;
- unknown-field rejection; and
- tests for payload tampering, unknown keys, expiry, rollback, channel mismatch, malformed metadata, and conflicting same-sequence metadata.

**Verifier decision frozen for packaging:** Scholion will use exact-pinned **`ed25519-dalek` 3.0.0** in the native Rust host, using strict verification and without `legacy_compatibility` or `hazmat`. The current source-build Cargo graph intentionally does not add that dependency yet because the generated lockfile, bundled production public-key resource, and native activation boundary belong to the packaging milestone. Do not hand-edit Cargo.lock to simulate integration.

**Production gate still required:** create/provision the real public verification material and key-rotation set during packaging. Source/development builds therefore keep update checking fail-closed/off and make no update request.

The private signing key is intentionally outside the repository and application. `scripts/build_release_metadata.py` produces deterministic exact payload bytes for an offline signer and can wrap only the resulting public signature. There is no repository tool that accepts or stores a private signing key.

See **[Production trust inputs](production-trust-inputs.md)** for the reviewed verifier choice, public-key lifecycle, and rotation rules.

### Privacy-preserving manual update channel

**Implemented in repository code:**

- one fixed GitHub-hosted manifest location;
- manual check only, with no periodic background check;
- HTTPS-only bounded metadata transport;
- no installation ID, corpus/recording/transcript/research data, hardware inventory, model inventory, or behavioral telemetry in requests;
- generic update-specific User-Agent without a device identifier;
- private local highest-trusted-sequence state;
- exact platform selection from signed metadata;
- streamed staging with signed size and SHA-256 enforcement;
- private temporary files, fsync, and atomic replacement into the staged cache;
- signed metadata re-verification immediately before staging;
- a closed desktop bridge that accepts no caller URL, path, header, shell command, or installer argument;
- WebView CSP without general external network authority; and
- explicit UI states for Off, Never checked, Checking, Up to date, Trusted update available, Staging/Staged, and bounded failure.

The user-facing copy states the network truth plainly: GitHub/CDN still sees ordinary connection metadata such as IP address and request time. A failed/offline update check never blocks the local evidence workspace.

**Production gate still required:** native package activation plus platform signing/notarization. A staged hash-matching package is not called installed or executable merely because Scholion downloaded it successfully.

### Curated model trust root

**Implemented in repository code:**

- project-owned catalog schema with model/engine/repository identity;
- immutable 40-character upstream revision;
- source/license metadata;
- exact complete file set, byte sizes, and SHA-256;
- cache/path containment;
- provider-local validation kept separate from Scholion policy trust;
- `ModelManager` policy pinning, pre-registration exact verification, policy receipts, and re-verification;
- application enforcement automatically enabled when a reviewed catalog is bundled;
- legacy installed-but-untrusted models remain visible/removable but are refused for new-transcription admission;
- Processing UI distinguishes installation from current policy trust; and
- `scripts/generate_model_trust_entry.py` deterministically measures a deliberately selected snapshot, including safe Hugging Face-style in-cache symlinks.

The generator measures bytes. It does not decide that a model is trustworthy.

**Production gate still required:** deliberately review real faster-whisper revisions, licenses, file sets, regression behavior, and generated entries, then commit/bundle that catalog in a signed release. Development cache contents, guessed hashes, `main`, and `HEAD` are not acceptable trust inputs.

The exact review sequence is frozen in **[Production trust inputs](production-trust-inputs.md)** so packaging does not invent model policy ad hoc.

See **[Signed update and model trust channel](update-model-trust.md)** for schemas and threat-model detail.

## Release metadata operations

For a production candidate:

1. build the platform artifacts from the reviewed release commit;
2. run `scripts/build_release_metadata.py payload` with a strictly increasing sequence, stable channel, valid SemVer version, explicit UTC timestamps, release-notes URL, and each `PLATFORM::LOCAL_PATH::HTTPS_URL` artifact;
3. publish/review the generated `SHA256SUMS` as human-auditable checksums, without treating an unsigned checksum file as a trust root;
4. send the exact generated payload bytes to the offline Ed25519 signing process;
5. run `scripts/build_release_metadata.py envelope` with the exact payload, public signature bytes, and approved key ID;
6. verify the resulting envelope with the same production public-key verifier used by the desktop client before publication; and
7. publish only after OS code signing/notarization and native qualification also pass.

The metadata builder now refuses a non-stable first-release channel, invalid SemVer text, and non-UTC signing timestamps before the offline signer sees payload bytes.

A new release sequence must not be reused for different signed content. Key rotation, metadata correction, or artifact replacement requires a new sequence.

## Release gate B: hostile-input containment

### Current parser controls

Scholion already treats media parsing as hostile input in several concrete ways:

- FFprobe and FFmpeg are invoked without a shell;
- network protocols are restricted to `file` for media probe/decode;
- parser/decode calls have explicit timeouts;
- FFmpeg has no interactive stdin;
- FFprobe metadata is schema-checked and subject to an application output-size boundary;
- media input is fingerprinted and checked for mutation while inspected; and
- decode output goes only to a planned private workspace path and is validated before use.

These are valuable controls, but **they are not an OS sandbox**.

### Remaining parser sandbox hardening

Before describing Scholion as highly hardened against malicious media, qualify a real least-privilege parser boundary per supported OS:

- Linux seccomp/namespaces or an appropriate maintained sandbox launcher;
- macOS hardened-runtime/sandbox capability reduction;
- Windows AppContainer/restricted-token/job-object equivalent;
- read-only source authority where practical;
- no ambient workspace/home-directory access from parser helpers;
- explicit CPU/memory/time/output limits; and
- malformed/truncated/adversarial-media tests through the native desktop path.

This cannot be replaced by browser mocks or by calling a subprocess with `shell=False`.

This hardening remains important, but it is not being turned into an indefinite blocker for source builds or an early packaged preview. The claim boundary is explicit: current controls are substantial, but Scholion should not call itself OS-sandboxed until it actually is.

### Process isolation already present

The React WebView cannot select Python modules, execute arbitrary shell commands, receive raw private filesystem authority, choose update URLs, or submit installer commands. One-shot native bridge requests are bounded and serialized where they cross shared DuckDB state. Long-running Processing work uses a separately supervised worker path with bounded typed tasks, cancellation/status, and controlled public failures.

Further OS process-capability reduction belongs with the parser sandbox work above.

## Release gate C: data at rest

### OS keychain integration

If Scholion later stores application secrets or at-rest encryption keys, those keys should be wrapped by the platform credential/key facility rather than stored beside encrypted data.

Key loss and recovery semantics must be designed before this becomes a default dependency.

### Application-layer encryption

Application-layer encryption is **not an MVP launch blocker**. It needs a threat model explaining what it protects beyond filesystem/full-disk encryption and how backup, restore, portability, corruption recovery, key rotation, multi-machine use, and evidence export work.

Decide independently for authoritative research state, canonical transcript evidence, remembered locations/preferences, checkpoints/temp state, model cache, and rebuildable search indexes. Do not create new irreplaceable key-bound state merely to say “encrypted.”

Backup/restore and research portability are now explicitly post-MVP product work. That sequencing is another reason not to introduce application-layer encryption prematurely.

## Native and release qualification

Browser Playwright intentionally swaps in mock clients and is not native evidence. Public release qualification still needs:

- real React → Tauri → Rust → Python update/Processing calls;
- bounded behavior when child processes fail/hang;
- no evidence/request parameters in routine native diagnostics;
- model install/revalidation/offline transcription with the actual reviewed catalog;
- update-check/offline/failure/staging behavior with the actual production public key;
- Windows and macOS package signature verification;
- Linux Wayland/WebKitGTK qualification once the upstream dependency gate permits public Linux packaging;
- representative CPU-only and accelerator-capable devices; and
- verification that installed/notarized artifacts match the release metadata/checksums.

Issue #114 tracks representative native task-transport qualification. Issue #135 remains the upstream-blocked Linux GTK/GLib dependency gate.

## Current milestone boundary

Issue #145 owns the last pre-packaging cleanup:

1. complete the post-#144 redundancy re-audit;
2. freeze production verifier/key-rotation and real-model review procedure;
3. keep invalid release-signing inputs out of the offline-signing path;
4. truth-sync the docs/trackers; and
5. replace the placeholder application icon/master asset.

Packaging itself intentionally waits until that milestone closes.

## Ordered residual work after #145

The remaining **MVP release gates** are narrow and concrete:

1. package Windows/macOS with the exact-pinned native verifier and approved public-key set;
2. review real faster-whisper revisions and bundle the generated catalog;
3. implement/qualify native package activation with OS signing/notarization;
4. qualify real packaged devices/offline behavior, including #114; and
5. release the MVP when those gates pass.

Official Linux binary distribution remains blocked by #135 until a stable/reviewed upstream-supported Tauri stack removes the affected dependency generation.

Post-MVP backup/restore, packaged semantic custody, parser OS sandboxing, and any justified keychain/application-layer encryption should not be mislabeled as unfinished core transcription/research product work.

None of the real release inputs above should be “completed” by placeholder keys, synthetic hashes, CI browser mocks, or credentials committed to the repository.
