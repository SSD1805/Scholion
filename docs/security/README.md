# Scholion security design notes

Scholion is local-first, but local-first is not synonymous with automatically safe. Security work covers evidence custody, hostile media parsing, process capability, dependency/model provenance, update authenticity, secret/key storage, and recovery semantics.

## Current release-hardening plan

See **[Pre-release security hardening roadmap](release-hardening.md)** for the ordered work covering:

- application-layer encryption;
- OS keychain integration;
- cryptographic signatures for manifests;
- sandboxing native parsers;
- tighter process isolation;
- a secure update framework; and
- a model-signing trust root.

The roadmap groups these into supply-chain trust, hostile-input containment, and data-at-rest/key custody. It also records native React → Tauri → Rust → Python qualification as a release gate after real-device testing exposed a gap that browser mocks cannot cover.

Repository vulnerability reporting and disclosure policy remain in the root **[SECURITY.md](../../SECURITY.md)**.
