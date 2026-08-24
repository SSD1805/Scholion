# Production trust inputs

This document freezes the remaining **production inputs** for Scholion's application-update and model-trust channels without pretending that packaging, private-key custody, or reviewed upstream model snapshots already exist.

The application-side mechanics are already implemented: exact signed payload bytes, key IDs, expiry, rollback/equivocation protection, stable-channel enforcement, fixed-endpoint manual checking, signed platform selection, exact size/SHA-256 staging, and fail-closed source builds. The work here is about deciding what production releases will plug into those seams.

## Application release verifier decision

Scholion's first packaged release should use **`ed25519-dalek` 3.0.0** in the native Rust host for Ed25519 verification.

Reviewed upstream characteristics at the time of this decision:

- package: `ed25519-dalek`
- selected version: `3.0.0`
- upstream repository: `dalek-cryptography/curve25519-dalek`, `ed25519-dalek/`
- license: BSD-3-Clause
- declared minimum Rust version: 1.85
- intended API: `VerifyingKey::from_bytes` plus `VerifyingKey::verify_strict`
- no signing API is required by the installed application
- do not enable `legacy_compatibility`
- do not enable `hazmat`
- use verification-only/default-feature-minimized configuration unless packaging proves a required feature explicitly

The original standalone `dalek-cryptography/ed25519-dalek` GitHub repository is archived and points to the maintained monorepo above. Dependency review therefore follows the monorepo package, not the archived repository.

### Why this choice

The update manifest already uses raw Ed25519 public keys/signatures and exact payload bytes. `ed25519-dalek` matches that protocol directly and exposes strict verification without requiring Scholion to implement curve arithmetic, signature parsing, or a new minisign-specific envelope.

The project should not add a second updater framework merely to obtain one cryptographic primitive. Tauri's update plugin is useful precedent for native signed updates, but Scholion already owns a narrower metadata/staging protocol with different privacy and rollback semantics.

### When the dependency is added

The Cargo dependency and lockfile change belong to the **packaging milestone**, together with the actual bundled public-key resource and native activation boundary. Until those assets exist, source/development builds remain `Updates off` and perform no update request.

Packaging should pin the reviewed version exactly and rerun:

- `cargo check --locked`;
- `cargo test --locked`;
- cargo-deny source/license policy;
- RustSec audit;
- native update-verification tests using known valid/invalid Ed25519 vectors; and
- the full Scholion Quality / Static Analysis workflows.

Do not hand-edit a generated Cargo lockfile merely to make the dependency appear integrated.

## Public-key custody and rotation

The installed application receives **public verification material only**.

A production key record needs:

- a bounded key ID such as `release-2026-a`;
- algorithm `ed25519`;
- exactly 32 public-key bytes; and
- a lifecycle state known to the release process.

The corresponding private signing key must never be:

- committed to this repository;
- embedded in the application;
- stored in a GitHub Actions variable/artifact merely for convenience;
- printed into CI logs; or
- accepted by Scholion's release-metadata builder.

`scripts/build_release_metadata.py` intentionally accepts only an externally produced public signature.

### Rotation rule

Key rotation is an application release event, not a mutable server-side setting.

1. Ship release **N** with the current key and the next public key both trusted by the installed client.
2. Only after release N is available should release **N+1** begin signing metadata with the new key ID.
3. Keep the previous verification key only for the documented overlap window needed by supported older clients.
4. Removing a key requires a later signed application release and a new manifest sequence.
5. Reusing a sequence for corrected metadata or a different key is forbidden.

A compromised signing key requires an incident-specific recovery plan. A client that has only the compromised key cannot learn a trustworthy replacement key from metadata signed solely by that compromised key.

## Real faster-whisper model trust review

The repository contains generation/verification machinery but intentionally no guessed production model hashes. A model becomes Scholion policy only through this review sequence.

For each model ID intended for the first packaged release:

1. select the exact upstream repository and immutable 40-hex revision deliberately;
2. review source ownership, model card, license identifier/text, and license URL;
3. acquire that exact revision into an isolated review cache;
4. run `scripts/generate_model_trust_entry.py` against the deliberately selected snapshot and cache root;
5. review the generated **complete** logical file set, byte sizes, SHA-256 values, and in-cache symlink resolution;
6. run representative transcription/regression checks using that exact revision;
7. record why the revision was selected and any material differences from the previously trusted revision;
8. commit the reviewed catalog entry in an ordinary code review; and
9. ship it only inside an OS-signed / Scholion-signed application release.

The generator measures bytes. It does not confer trust.

### Do not use

- upstream `main` / `HEAD`;
- whichever snapshot happened to exist on a developer machine;
- hashes copied from an unreviewed third-party page;
- partial file lists;
- mutable runtime model policy fetched from a hosted Scholion service; or
- a model revision that has not been exercised with the engine version shipped by the candidate release.

## What remains external/manual

These items cannot be truthfully completed by repository code alone:

- creating and safeguarding the real private release-signing key;
- deciding which real upstream faster-whisper revisions/licenses are approved after live source review;
- generating the final public-key resource from that private key;
- OS signing/notarization credentials; and
- representative native qualification using the actual packaged key/catalog.

They are release inputs and evidence, not missing application architecture.

## Relationship to packaging

Packaging is deliberately the next milestone after pre-packaging cleanup. It will:

- add the reviewed Rust verifier dependency and generated lockfile;
- bundle the approved public-key set;
- wire native verification into the already-implemented update channel;
- bundle the reviewed model-trust catalog;
- activate Tauri installers/bundles and managed runtime dependencies; and
- qualify the resulting signed artifacts.

Until then, the safe behavior remains simple: **no production verifier means no update network request**.
