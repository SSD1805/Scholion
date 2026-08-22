# Pre-release security hardening roadmap

This document turns the remaining security ideas into an ordered release-hardening program rather than seven unrelated checkboxes. Scholion is local-first, but local software still processes hostile media, stores sensitive research, downloads executable/model artifacts, and crosses a WebView → Rust → Python boundary. Privacy therefore depends on both custody and containment.

## Release gate A: supply-chain trust

### Cryptographic signatures for manifests

Application/model manifests must be signed with an offline-controlled signing identity. Verification happens before a manifest can authorize an application update, model revision, or hash set. Signature failure, unknown key ID, malformed metadata, rollback, and expired metadata fail closed.

Acceptance evidence:

- signed manifest fixture verifies;
- modified bytes fail verification;
- unknown/revoked key fails;
- rollback to an older trusted version is rejected according to explicit policy;
- verification is independent of transport security.

### Secure update framework

Application updates need a signed metadata framework with rollback/freeze protection, explicit channel/version semantics, staged download, hash verification, and atomic activation. An update check may make an outbound request without becoming telemetry; the privacy contract must state what network metadata is exposed.

Do not ship an auto-updater that trusts only HTTPS or a mutable release URL.

### Model-signing trust root

The curated model catalog must resolve to a trusted manifest containing repository/source identity, immutable revision, required files, sizes, hashes, license/source metadata, and a Scholion-trusted signature. Hugging Face or another transport host is a distribution mechanism, not the trust root.

Application update signing and model signing may share verification primitives, but should use separable signing roles/keys so compromise of one authority does not automatically authorize the other.

## Release gate B: hostile-input containment

### Sandboxing native parsers

FFmpeg/FFprobe, native decoders, archive/parsing helpers, and future media parsers should be treated as hostile-input surfaces. The goal is to make a parser compromise materially less useful.

Platform work should evaluate:

- Linux seccomp/namespaces or an appropriate sandbox launcher;
- macOS sandbox/hardened-runtime entitlements;
- Windows AppContainer/job-object/restricted-token options;
- read-only source handles where practical;
- no ambient access to the whole Scholion workspace during probe/decode;
- explicit CPU/memory/time/output limits.

The sandbox boundary must be tested with malformed/truncated media and intentional parser failure.

### Tighter process isolation

Long-running transcription, probing, model verification, and helper processes should receive only the filesystem/network/device capabilities they need. Process supervision should include bounded startup/response time, cancellation, exit-state capture, and cleanup after crashes.

The React WebView never receives arbitrary Python-module selection, shell-command capability, or raw filesystem authority.

## Release gate C: data-at-rest protection

### OS keychain integration

If Scholion protects application secrets or encryption keys, those secrets should be wrapped by the operating system's credential/key facility where available rather than stored beside encrypted data.

Target abstractions:

- Windows Credential Manager/DPAPI or platform-appropriate protected storage;
- macOS Keychain;
- Linux Secret Service/libsecret when available, with an explicit fallback policy for headless/minimal systems.

Key loss/recovery behavior must be documented before encryption becomes default.

### Application-layer encryption

Application-layer encryption is not an automatic launch blocker until the threat model defines what it protects beyond filesystem/full-disk encryption. It materially changes backup, restore, portability, corruption recovery, key rotation, multi-machine use, and evidence export.

Before implementation, decide independently for:

- authoritative research SQLite;
- canonical transcript evidence;
- remembered locations/preferences;
- processing checkpoints/temp state;
- model cache;
- derived search indexes.

Do not encrypt rebuildable projections in a way that creates new irreplaceable key-bound state. Do not make canonical evidence unrecoverable without an explicit recovery/export story.

## Ordering and dependencies

Recommended sequence:

1. define trust-root/key-rotation policy;
2. signed application/model manifests;
3. secure update framework + model-signing trust root;
4. parser sandbox and process-capability reduction;
5. native end-to-end qualification across supported OSes;
6. keychain abstraction and recovery design;
7. application-layer encryption only after a documented threat model and portability/backup contract.

The first five are release-hardening work. Keychain/encryption may be release blockers if the threat model shows an unacceptable at-rest risk; otherwise they should not be bolted on without recovery semantics.

## Native transport qualification discovered during real-device testing

Browser Playwright uses `?e2e=1` and intentionally swaps in mock clients. That is useful UI evidence but does not prove React → Tauri → Rust → Python wiring works on a real machine.

Before release, qualification must include:

- real `processing.readiness` and `processing.jobs.list` through the native Tauri command;
- bounded failure when the Python child never responds;
- useful controlled error propagation when spawn/exit/JSON parsing fails;
- no evidence/request parameters in routine native diagnostics;
- Linux Wayland/WebKitGTK qualification including the known DMABUF workaround path;
- Windows and macOS native transport smoke;
- representative CPU-only and CUDA-capable devices.

This is a release seam, not a browser-mock seam.
