# Signed update and model trust channel

Scholion has two related but distinct supply-chain trust problems: application releases and local model snapshots. Both need project-owned trust roots, but neither should turn a local-first application into a telemetry client or make an upstream distribution host authoritative for what Scholion executes.

This document defines the first-release contract tracked by issue #110.

## Trust boundaries

### Application releases

The native desktop host owns application-update trust. A release check must fetch only a bounded signed metadata envelope from a fixed Scholion update endpoint. The request must not include an installation identifier, corpus metadata, hardware inventory, recording names, research state, model inventory, or behavioral telemetry.

The envelope carries exact signed payload bytes plus a key identifier, signature algorithm, and signature. The signed payload is typed data only: release sequence, channel, version, publication/expiry timestamps, release-notes URL, and per-platform artifact URL/size/SHA-256. Unknown envelope or payload fields fail closed.

The signature covers the exact payload bytes rather than a re-serialized JSON object. This avoids cross-language JSON canonicalization becoming part of the security boundary.

The production verifier belongs in the native/Tauri layer and must use a reviewed signature implementation with public keys pinned in the application. Scholion must not implement Ed25519 arithmetic itself in Python.

### Models

The application package owns a curated model-trust catalog. A model entry identifies:

- Scholion model ID and engine;
- exact upstream repository identity;
- immutable 40-character upstream revision;
- source URL;
- license ID and license URL; and
- every allowed snapshot file with exact relative path, byte size, and SHA-256.

A distribution service such as Hugging Face transports bytes. It does not decide which revision or file hashes Scholion trusts.

The provider must eventually request the exact curated revision and verify the downloaded snapshot against the bundled trust entry before writing a local managed-model manifest or reporting the model as trusted/ready. Snapshot verification rejects path escape, cache escape, missing files, undeclared files, size mismatch, and hash mismatch.

Integrity/local revalidation and policy trust are separate states. A snapshot can match expected repository/revision/layout rules without being trusted by Scholion policy. Consumer UI and documentation must not collapse those states into one word such as “verified.”

## Update manifest v1

The wire envelope is deliberately small:

```json
{
  "schema_version": 1,
  "key_id": "release-2026",
  "algorithm": "ed25519",
  "payload_base64": "<exact signed payload bytes>",
  "signature_base64": "<64-byte signature>"
}
```

After signature verification, the payload is parsed as:

```json
{
  "schema_version": 1,
  "sequence": 42,
  "channel": "stable",
  "version": "1.0.0",
  "published_at": "2026-08-23T15:00:00Z",
  "expires_at": "2026-08-30T15:00:00Z",
  "release_notes_url": "https://updates.example.invalid/releases/1.0.0",
  "artifacts": [
    {
      "platform": "linux-x86_64",
      "url": "https://updates.example.invalid/artifacts/scholion-linux-x86_64.tar.zst",
      "size_bytes": 123,
      "sha256": "<64 lowercase hexadecimal characters>"
    }
  ]
}
```

The repository examples use `.invalid` hosts intentionally. A production endpoint and signing keys must be provisioned separately.

### Replay, downgrade, and freeze policy

The native client persists the highest successfully trusted manifest sequence. A subsequently signed manifest with a lower sequence is rejected. Re-seeing the same sequence is allowed so a user can check repeatedly without manufacturing state changes.

Signed metadata expires. Expired metadata cannot authorize an update, which limits indefinite replay of old signed metadata after hosting compromise. A client that stays offline past expiry continues to run normally; it simply cannot authorize a new update until it can obtain fresh signed metadata.

A valid signature does not mean “install immediately.” Version/channel/platform policy and explicit user intent are separate decisions after trust verification.

## Model trust catalog v1

The bundled catalog shape is:

```json
{
  "schema_version": 1,
  "models": [
    {
      "model_id": "tiny",
      "engine": "faster-whisper",
      "repository_id": "Systran/faster-whisper-tiny",
      "revision": "<40 lowercase hexadecimal characters>",
      "source_url": "https://huggingface.co/Systran/faster-whisper-tiny",
      "license_id": "<reviewed license identifier>",
      "license_url": "<reviewed HTTPS license URL>",
      "files": [
        {
          "path": "model.bin",
          "size_bytes": 123,
          "sha256": "<64 lowercase hexadecimal characters>"
        }
      ]
    }
  ]
}
```

Production entries must be generated from a deliberately reviewed immutable upstream revision. Do not guess hashes, copy mutable `main`/`HEAD`, or treat whatever revision happened to download during development as trusted policy.

Changing a trusted model revision is a security-sensitive repository change. The review should record why the revision changed, source/license changes, file-set changes, regression evidence, and regenerated hashes/sizes. The new catalog ships with a signed Scholion release.

## Threat model

| Threat | Control | Residual risk / follow-up |
|---|---|---|
| Upstream model repository compromised | Bundled exact revision + full allowed-file SHA-256/size set; downloaded bytes do not become trusted merely because upstream served them | A malicious revision intentionally approved into Scholion remains a review failure; review and regression evidence are required |
| Release hosting/CDN compromised | Manifest signature is verified independently of HTTPS; artifact hash is signed metadata | Availability can still be denied; connection metadata remains visible to host/CDN |
| Malicious mirror/artifact replacement | Signed artifact SHA-256/size must match staged bytes before installation | Native staged-download/atomic activation is still implementation work |
| Old signed metadata replayed | Monotonic sequence rejects rollback; expiry limits freeze/replay window | Long-term offline users cannot check for updates until online again, but local operation remains unaffected |
| Update metadata injects remote commands/config | Strict schemas reject unknown fields; only typed release/artifact metadata exists | Future schema changes require an explicit versioned review |
| Update request leaks product behavior | Request is a metadata GET with no installation ID, corpus, hardware, research, or usage payload | IP address, request time, TLS/client/network metadata remain visible to network/hosting layers |
| Signing key compromise | Key IDs permit explicit rotation/revocation policy; release and model-signing roles should remain separable | Concrete key custody, rotation, and revocation implementation is still release work |
| Local model cache is tampered with | File set, size, hash, path, and cache containment are rechecked before trust | Local machine compromise outside Scholion's threat boundary can also alter the application binary or pinned keys |

## User-visible behavior

### Update checks

The default first-release behavior is manual: **Check for updates** is an explicit user action. Periodic checks, if added, are separately opt-in and must be easy to disable.

A manual check should communicate four states without implying telemetry-free networking:

1. update checks are off / have not been requested;
2. checking the signed release metadata requires a network request and exposes ordinary connection metadata such as IP address and time to the hosting/CDN layer;
3. no trusted newer release is available; or
4. a trusted newer release is available, with version/release notes and an explicit install/download action.

Network failure, offline mode, signature failure, expiry, rollback, or unsupported platform must never block opening Scholion or using existing local recordings, transcripts, models, or research.

### Model downloads

Ordinary product copy should explain the consequences a user actually needs to know:

> **Models download only when you choose. After download, they stay on this computer in Scholion's private app storage, so transcription can run offline.**

Do not make the primary workflow explain repository cache layouts, digest algorithms, trust-root rotation, or signed-manifest internals. Those are legitimate details, but they are not the job the person is trying to complete.

Until #110's production integration is complete, ordinary UI also must not say or imply that the current managed snapshot is “policy-trusted” or “cryptographically verified.” Today the managed-model path provides explicit installation, immutable resolved-revision custody, containment, and structural/provider revalidation. The stronger curated byte-for-byte trust check is a separate unfinished layer.

### Three presentation layers

Use one consistent layering rule across Processing, Settings, help, and documentation:

1. **Ordinary UI: consequence.** Say whether a network request happens, what stays local, what is optional, whether something works offline, and whether an action changes evidence or only app-managed state.
2. **Technical details: provenance.** Show repository/source identity, exact revision, local revalidation state, policy-trust state, license/source metadata, update version/channel, and signature/trust status when those fields are useful to a technically curious user.
3. **Security/developer docs: mechanism.** Explain exact signed payload bytes, key IDs, signature implementation, sequence/expiry rules, hashes, cache containment, threat model, and release process.

This keeps Scholion transparent without turning normal use into an architecture lecture. The UI should never hide a material consequence merely because the underlying mechanism is technical, and it should never inflate a weaker backend guarantee into a stronger consumer-facing trust claim.

## What this foundation implements

The `scholion.supply_chain` package currently provides:

- strict curated model catalog parsing;
- immutable-revision validation;
- exact model snapshot file-set/size/SHA-256 verification;
- path/cache containment checks;
- strict signed-update envelope and payload parsing;
- an explicit signature-verifier interface;
- expiry and anti-rollback sequence enforcement; and
- tests for tampering, unknown keys, stale metadata, hostile paths, undeclared files, and malformed/extra remote configuration.

## Remaining work under #110

This foundation deliberately does **not** claim #110 is complete. Before closing the issue:

- choose and pin the production native signature-verification implementation and public key(s);
- implement fixed-endpoint manual update checking in the Tauri host;
- persist highest trusted sequence without creating an identifier sent to the server;
- stage downloads, enforce signed size/hash, and use platform-appropriate signed/atomic installation;
- implement explicit update UI and separately opt-in periodic checks;
- review real upstream faster-whisper revisions and generate the production curated model catalog;
- wire `ModelManager`/`HuggingFaceModelProvider` to request only the curated revision and require trust verification before registration;
- record trusted policy identity in the local model manifest and expose local-revalidation versus “trusted by Scholion policy” accurately; and
- add native/offline regression qualification across supported platforms.

Until those steps land, current local/offline workflows remain unchanged and no update service is required for Scholion to run.