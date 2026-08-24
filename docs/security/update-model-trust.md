# Signed update and model trust channel

Scholion has two related but distinct supply-chain trust problems: application releases and local model snapshots. Both need project-owned trust roots, but neither should turn a local-first application into a telemetry client or make an upstream distribution host authoritative for what Scholion executes.

This document describes the implemented first-release trust mechanics and the remaining production provisioning gates. The separate **[Production trust inputs](production-trust-inputs.md)** document freezes the native verifier/key-rotation decision and the real-model review procedure that packaging will consume.

## Trust boundaries

### Application releases

Scholion's update policy is a strict signed metadata envelope. The signature covers the **exact payload bytes**, not a re-serialized JSON object. The payload can authorize only typed release metadata: release sequence, channel, version, publication/expiry timestamps, release-notes URL, and per-platform artifact URL/size/SHA-256. Unknown envelope/payload fields fail closed.

The production signature verifier belongs at the native application boundary. The pre-packaging decision is now frozen: packaging will exact-pin **`ed25519-dalek` 3.0.0**, use strict Ed25519 verification, and avoid `legacy_compatibility`/`hazmat`. The source-build Cargo graph intentionally remains unchanged until packaging can generate/audit the lockfile and bundle the actual approved public-key set at the same time. Scholion does not implement Ed25519 arithmetic itself in Python.

The repository contains the complete application-side orchestration around that verifier:

- one fixed GitHub-hosted metadata location;
- manual checks only;
- bounded HTTPS-only metadata transport;
- local highest-trusted-sequence state;
- publication/expiry and rollback enforcement;
- same-sequence signed-content equivocation rejection;
- explicit stable-channel enforcement;
- signed platform selection;
- staged artifact download with exact signed size and SHA-256 enforcement;
- signed metadata re-verification immediately before staging;
- private temporary staging plus fsync/atomic replacement;
- a closed Tauri command with no caller-provided URL/path/header/command/installer argument; and
- explicit user-facing update/privacy states.

A source/development build that has no production verifier remains **Updates off** and makes no update request. This is intentional fail-closed behavior, not a fallback to unsigned HTTPS trust.

### Models

The application package owns a curated model-trust catalog. Each entry identifies:

- Scholion model ID and engine;
- exact upstream repository identity;
- immutable 40-character upstream revision;
- source URL and license metadata; and
- every allowed snapshot file with exact relative path, byte size, and SHA-256.

A distribution service such as Hugging Face transports bytes. It does not decide which revision or file hashes Scholion trusts.

`ModelManager` applies the policy transactionally. When a curated trust catalog is bundled, installation pins the exact approved revision, rejects conflicting caller revisions before acquisition, verifies the complete snapshot before committing managed state, records policy evidence separately from provider-local validation, and re-runs exact verification for later trust/admission reads.

Application composition loads packaged `model-trust.json`. If the build contains a valid catalog, policy enforcement is automatically enabled. If no catalog is bundled, current source/development builds remain on the provider/local-revalidation path. There is no runtime policy fetch and no remotely mutable model-policy service.

The repository deliberately still contains **no production faster-whisper trust entries**. `scripts/generate_model_trust_entry.py` can deterministically measure a deliberately selected immutable snapshot, including safe Hugging Face-style in-cache symlinks, but generated JSON becomes policy only after human review and inclusion in a signed Scholion release.

## Update manifest v1

The signed envelope is:

```json
{
  "schema_version": 1,
  "key_id": "release-2026",
  "algorithm": "ed25519",
  "payload_base64": "<exact signed payload bytes>",
  "signature_base64": "<64-byte signature>"
}
```

After signature verification, the payload is:

```json
{
  "schema_version": 1,
  "sequence": 42,
  "channel": "stable",
  "version": "1.0.0",
  "published_at": "2026-08-24T15:00:00Z",
  "expires_at": "2026-08-31T15:00:00Z",
  "release_notes_url": "https://github.com/SSD1805/Scholion/releases/tag/v1.0.0",
  "artifacts": [
    {
      "platform": "windows-x86_64",
      "url": "https://github.com/SSD1805/Scholion/releases/download/v1.0.0/scholion.exe",
      "size_bytes": 123,
      "sha256": "<64 lowercase hexadecimal characters>"
    }
  ]
}
```

The fixed first-release metadata location is:

`https://github.com/SSD1805/Scholion/releases/latest/download/scholion-update.json`

That mutable transport location is **not** the trust root. A compromised/misconfigured host can deny availability or serve garbage, but a payload cannot authorize an update unless it passes the independent signature and local policy checks.

### Replay, downgrade, and equivocation

The client persists the highest successfully trusted manifest sequence. A lower signed sequence is rejected. Re-seeing the exact same signed metadata at the same sequence is allowed. Reusing the same sequence for different signed content is rejected so a split-brain/mistaken release cannot silently replace already trusted metadata without advancing sequence.

Signed metadata expires. Expired metadata cannot authorize a new update or staging operation. A client that remains offline continues to run normally; it simply cannot authorize a new release until fresh signed metadata is available.

The stable client requires `channel == "stable"`. A correctly signed beta/nightly payload cannot accidentally flow through the stable endpoint.

### Local anti-rollback state

Update trust state is stored privately under Scholion's app state directory. It records only:

- schema version;
- highest trusted release sequence;
- last trusted update state/version; and
- the last trusted signed manifest needed for re-verification before staging.

It does **not** generate an installation identifier and it is never sent to the update host.

This protects against network/hosting rollback. It is not a defense against a same-user local attacker who can arbitrarily rewrite both application state and application binaries. That stronger local-compromise model belongs to OS code signing/protected-storage policy.

## Update transport and staging

`HttpsUpdateTransport` enforces:

- credential-free HTTPS request/final redirect URLs;
- 64 KiB maximum metadata response;
- finite network timeout;
- generic update-specific User-Agent with no device identifier;
- streamed artifact reads;
- immediate failure if bytes exceed the signed size;
- exact final byte-count and SHA-256 match;
- private temporary file on supported filesystems;
- fsync before activation into staged custody; and
- atomic local replacement of the staged file.

A staged package is **not installed**. Native platform activation remains a separate trust boundary because Windows/macOS/Linux packaging, application signatures/notarization, rollback behavior, and process replacement are platform responsibilities. The UI says this explicitly instead of presenting staging as installation.

## Release metadata generation

`scripts/build_release_metadata.py` separates deterministic metadata construction from private-key custody.

`payload` mode:

- measures each local release artifact;
- computes exact size and SHA-256 through the shared supply-chain digest helper;
- accepts only the first-release `stable` channel;
- rejects invalid SemVer text before signing;
- requires explicit UTC publication/expiry timestamps before signing;
- sorts platform entries deterministically;
- re-parses generated bytes through the runtime update schema;
- emits the exact payload bytes for signing; and
- emits deterministic `SHA256SUMS` for human/release auditing.

`envelope` mode:

- accepts the exact payload bytes;
- accepts only the public 64-byte signature produced by an external signer;
- validates the strict envelope; and
- writes `scholion-update.json`.

There is deliberately no private-key option in this repository tool. Public checksums are useful auditing material but are not treated as a substitute for the signed manifest.

## Model trust catalog v1

The bundled catalog shape remains:

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

Production entries must come from a deliberately reviewed immutable upstream revision. Do not guess hashes, copy mutable `main`/`HEAD`, or treat whatever happened to download during development as project policy.

Changing a trusted model revision is a security-sensitive repository change. Review should record why the revision changed, source/license changes, file-set changes, regression/qualification evidence, and regenerated hashes/sizes. The new catalog ships only with a signed Scholion release.

The required human workflow is specified in **[Production trust inputs](production-trust-inputs.md)**: deliberate upstream revision selection, source/license review, isolated-cache acquisition, deterministic measurement, complete entry review, regression checks, ordinary code review, and only then inclusion in a signed release.

### Managed policy evidence

A managed-model manifest can carry a separate policy-trust receipt containing catalog schema version, model identity, exact revision, policy verification method, verified file count, and verified byte count. It does not replace provider-local provenance such as repository identity, resolved revision, cache path, measured size, or provider validation method.

The receipt is not a permanent trust bit. With a current catalog loaded, `ModelManager` recomputes exact verification and requires observed evidence to match the receipt. Same-length byte mutation, undeclared/missing files, size change, revision change, or current-policy mismatch therefore invalidates current trust.

Existing manifests without policy evidence remain parseable. Under enforcement Scholion separates **custody** from **new-execution admission**:

- inventory can still show a locally valid legacy model as installed;
- current policy trust is false;
- new-transcription revision resolution rejects it;
- removal remains available; and
- Processing offers a trusted reinstall through the curated path.

Historical cache revisions are not automatically purged during trusted reinstall because an interrupted checkpoint may legitimately need its exact earlier model revision for reproducible resume. Future model garbage collection must therefore understand checkpoint references instead of deleting old bytes by assumption.

## User-visible behavior

The first-release update behavior is manual. There is no periodic background check in this tranche.

The Updates screen distinguishes:

1. **Updates off**: this build has no production trust key/verifier; no network request occurs.
2. **Never checked**: a verifier exists but the user has not requested a check.
3. **Checking**: one bounded request is being made to the fixed metadata location.
4. **Up to date**: trusted metadata contains no newer stable release.
5. **Trusted update available**: a newer signed stable release for this platform is authorized.
6. **Staging/Staged**: exact signed package bytes are being downloaded/verified or have been staged.
7. **Failure**: network/trust/platform failure is presented as one bounded public error without private diagnostics.

The UI states that GitHub/CDN can observe ordinary connection metadata such as IP address and request time. It also states what is **not** sent: installation ID, recordings, transcript/research content, hardware inventory, model inventory, and behavioral telemetry.

Local recordings, transcripts, models, and research remain usable when update checking is off, unavailable, offline, expired, or rejected.

## Threat model

| Threat | Control | Residual risk / follow-up |
|---|---|---|
| Upstream model repository compromised | Bundled exact revision + complete allowed-file size/SHA-256 set | Human approval of a malicious revision remains a review failure |
| Release hosting/CDN compromised | Independent signed metadata; signed artifact size/hash | Availability and ordinary network metadata remain exposed |
| Malicious artifact replacement | Streamed exact signed size/hash before staging | Native OS-signed activation still required |
| Old signed metadata replayed | Monotonic sequence + expiry | Same-user state tampering is outside the network rollback boundary |
| Same sequence serves different signed content | Persisted-manifest equality check rejects equivocation | Release process must advance sequence for every correction/key rotation |
| Beta/nightly metadata reaches stable endpoint | Stable channel enforced after signature verification | Separate future channels require separate explicit client policy |
| Remote metadata injects commands/config | Strict exact schemas; no command/config fields | Schema evolution requires explicit versioned review |
| Update request becomes telemetry | Fixed metadata GET; no identifier/corpus/hardware/research/behavior payload | Host/CDN still sees IP/time/TLS/network metadata |
| Signing key compromise | Pinned key IDs/rotation design and offline private-key custody | Incident recovery cannot be solved by metadata signed only by the compromised key |
| Local model cache tampered | File set/size/hash/path/cache containment rechecked | Full local machine compromise can also alter application binaries/keys |
| Legacy model survives policy upgrade | Custody visible, new jobs require current trust, curated reinstall available | Resume/cache retention remains a reproducibility concern, not new-job authorization |

## Implemented versus production-provisioned

Repository mechanics now cover the update/model trust architecture, local update state, fixed transport, staging/hash verification, UI states, deterministic release/model metadata generation, and extensive synthetic trust tests.

Issue #145 owns only the remaining **pre-packaging** decisions/cleanup. Once that milestone is complete, packaging still must provide:

- the exact-pinned reviewed Rust verifier dependency and generated/audited lockfile;
- the approved production public-key/key-rotation resource, never the private signer;
- deliberately reviewed real faster-whisper revisions and generated catalog entries;
- platform package signing/notarization and native installation/activation;
- representative native/offline qualification with the actual production key/catalog; and
- resolution of the separate upstream Linux dependency gate before calling Linux packaging production-ready.

Those are real release inputs and qualification evidence. They are not replaced by placeholder keys, guessed hashes, synthetic test fixtures, or browser mocks.
