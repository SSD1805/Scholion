# Scholion security design notes

Scholion is local-first, but local-first is not synonymous with automatically safe. Security work covers evidence custody, hostile media parsing, process capability, dependency/model provenance, update authenticity, secret/key storage, and recovery semantics.

## Current release-hardening plan

See **[Pre-release security hardening roadmap](release-hardening.md)** for the current gate structure covering:

- signed application metadata and privacy-preserving manual updates;
- curated model policy rooted in signed Scholion releases;
- native package signing/activation and representative qualification;
- hostile-media parser containment and the boundary between current controls and a real OS sandbox; and
- deliberately deferred keychain/application-layer encryption work that requires a concrete threat/recovery model.

The application-side update/model-trust mechanics were completed in merged PR #144. Issue #145 is the current **pre-packaging** milestone: production trust-input decisions, post-update redundancy cleanup, documentation truth-sync, and final product icon/brand assets. Packaging itself follows after #145.

See **[Signed update and model trust channel](update-model-trust.md)** for the implemented exact-byte signed update envelope, anti-rollback/expiry/equivocation semantics, privacy-preserving update behavior, and project-owned pinned model metadata with complete file-set/size/SHA-256 verification.

See **[Production trust inputs](production-trust-inputs.md)** for the frozen native verifier choice (`ed25519-dalek` 3.0.0), key-rotation/custody rules, and the required human review procedure for real faster-whisper trust entries. Real private signing material and real model approval evidence are release inputs, not repository placeholders.

Issue #114 remains qualification-only for representative native Processing task transport. Issue #135 remains the upstream-blocked official Linux binary gate.

Backup/restore, packaged semantic custody, and broader research-native features are post-MVP product work rather than pre-packaging security blockers. Repository vulnerability reporting and disclosure policy remain in the root **[SECURITY.md](../../SECURITY.md)**.
