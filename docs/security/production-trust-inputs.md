# Production trust inputs

This document defines the remaining **production inputs** for Scholion's application-update and model-trust channels without pretending that private-key custody, reviewed upstream model snapshots, OS signing credentials, or representative-device evidence already exist.

The application-side trust mechanics are implemented: exact signed payload bytes, key IDs, expiry, rollback/equivocation protection, stable-channel enforcement, fixed-endpoint manual checking, signed platform selection, exact size/SHA-256 staging, and fail-closed source builds. The Windows/macOS packaging foundation, deterministic package provenance/lifecycle qualification, repository-owned packaged FFmpeg/FFprobe custody, and strict native Ed25519 verification are complete through PRs #164, #166, #167, and #170.

The remaining #168 work is therefore about **real production trust material**: deliberately reviewed model snapshots, the approved public update-verification key set derived from externally safeguarded signing material, and qualification/provenance that binds those exact inputs to the candidate package.

## Application release verifier

Merged PR #170 implemented Scholion's first packaged-release verifier using **`ed25519-dalek` 3.0.0** in the native Rust host.

The reviewed implementation contract is:

- package: `ed25519-dalek`
- selected version: exactly `3.0.0`
- upstream repository: `dalek-cryptography/curve25519-dalek`, `ed25519-dalek/`
- license: BSD-3-Clause
- declared minimum Rust version: 1.85
- verification API: `VerifyingKey::from_bytes` plus `VerifyingKey::verify_strict`
- no signing API is required by the installed application
- default features disabled
- no `legacy_compatibility`
- no `hazmat`

The original standalone `dalek-cryptography/ed25519-dalek` GitHub repository is archived and points to the maintained monorepo above. Dependency review follows the monorepo package, not the archived repository.

PR #170 exact-pinned the dependency, let Cargo generate the lockfile, kept verification at the native application boundary, and passed the locked Rust, dependency-policy, Security, Quality, Acceptance, and Windows/macOS Release Qualification gates before merge.

### Why this choice

The update manifest already uses raw Ed25519 public keys/signatures and exact payload bytes. `ed25519-dalek` matches that protocol directly and exposes strict verification without requiring Scholion to implement curve arithmetic, signature parsing, or a second updater-specific envelope.

The project does not add another updater framework merely to obtain one cryptographic primitive. Scholion already owns a narrower metadata/staging protocol with explicit privacy, rollback, and evidence semantics.

## Public-key custody and rotation

The installed application receives **public verification material only**.

A production key record contains:

- a bounded key ID such as `release-2026-a`;
- algorithm `ed25519`;
- exactly 32 public-key bytes encoded as lowercase hexadecimal; and
- lifecycle state `current` or `next`.

The catalog contains one or two unique keys and exactly one `current` key. Duplicate IDs, duplicate key bytes, malformed records, unknown fields, unsupported algorithms, ambiguous current state, and invalid encodings fail closed.

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

## Deterministic custody of reviewed trust inputs

PR #172 introduces the repository-owned handoff for real trust material without creating that material itself.

The intended production flow is:

1. review and approve the real `update-keys.json` and `model-trust.json` source inputs;
2. run `scripts/prepare_release_trust_inputs.py` with those exact files;
3. re-validate both documents through Scholion's strict schemas;
4. stage their bytes under `build/release-trust-inputs/` together with deterministic `release-trust-inputs.json` evidence;
5. pass that prepared directory explicitly to `scripts/build_desktop_runtime.py --release-trust-dir ...`;
6. verify the exact packaged copies with `scripts/verify_packaged_release_trust_inputs.py`; and
7. bind the staged trust-input identities into release provenance with repeatable `scripts/build_release_provenance.py --input ...` arguments.

The preparation evidence records only public/semantic identity needed for review and reproducibility: input filename, size, SHA-256, public key IDs/states, model IDs, engines, repository IDs, immutable revisions, and license identifiers. It does not record workstation paths or any private signing material.

Preparation never treats generation as approval. It preserves the exact approved input bytes, overwrites only its fixed generated outputs, and leaves unrelated files alone. Runtime installation copies only the verified allowlist, not arbitrary neighboring files from the preparation directory.

### Packaged locations

The reviewed model catalog is installed at the Python package location inside the frozen runtime:

```text
runtime/_internal/scholion/supply_chain/model-trust.json
```

The public update-key catalog and its custody evidence are installed at:

```text
runtime/release-trust/update-keys.json
runtime/release-trust/release-trust-inputs.json
```

The native Tauri host resolves `update-keys.json` only through this package-relative runtime location. It does not search `PATH`, accept an update-supplied key path, or inherit an ambient verifier override. Ordinary preview/source builds that omit `--release-trust-dir` remain trust-free and update checking stays off.

The staged `build/release-trust-inputs/` directory is ignored by Git because it is build-time handoff material. A deliberately reviewed source policy may be committed separately in an ordinary review; generated staging evidence is not the policy source of truth.

## First-release faster-whisper model set

The **model IDs** for the first Windows/macOS release are deliberately fixed to:

- `tiny`
- `small`
- `medium`

This is not an arbitrary expansion of scope. These are exactly the model IDs exposed by Scholion's current strategy catalog across screening, balanced, and accuracy quality tiers; the CPU and CUDA strategy variants reuse the same three model identities. Shipping enforced model trust while omitting one would make an advertised execution/quality tier impossible to admit.

The current provider mapping in `src/scholion/model_management/catalog.py` is:

- `tiny` → `Systran/faster-whisper-tiny`
- `small` → `Systran/faster-whisper-small`
- `medium` → `Systran/faster-whisper-medium`

That mapping is **not itself production approval**. Each repository's immutable revision, ownership/model card, license identifier/text/URL, exact snapshot file set, and engine compatibility still require live upstream review before a production `model-trust.json` entry can be approved.

## Real faster-whisper model trust review

The repository contains generation/verification machinery but intentionally no guessed production model hashes. A model becomes Scholion policy only through this review sequence.

For each of the three first-release model IDs:

1. confirm the exact upstream repository and select an immutable 40-hex revision deliberately;
2. review source ownership, model card, license identifier/text, license URL, and material upstream constraints;
3. acquire that exact revision into an isolated review cache;
4. run `scripts/generate_model_trust_entry.py` against the deliberately selected snapshot and cache root;
5. review the generated **complete** logical file set, byte sizes, SHA-256 values, and in-cache symlink resolution;
6. run representative transcription/regression checks using that exact revision and the engine version shipped by the candidate;
7. record why the revision was selected and any material differences from the previously trusted revision;
8. commit the reviewed catalog entry in an ordinary code review; and
9. ship it only inside the appropriately signed production application release.

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
- live review and approval of the immutable upstream faster-whisper revisions/licenses;
- generating/reviewing the final public-key resource from the selected release key;
- production-shaped signed update fixtures made without exposing the private signer to CI;
- OS signing/notarization credentials; and
- representative native qualification using the actual packaged key/catalog.

They are release inputs and evidence, not missing application architecture.

## Release qualification for the real inputs

Once the actual reviewed inputs exist, the Windows/macOS candidate must prove all of the following before #168 is complete:

- the prepared input evidence matches the approved source bytes exactly;
- the frozen runtime contains the exact reviewed model catalog and public-key catalog;
- the mounted macOS DMG and installed Windows NSIS package preserve those exact bytes;
- the native verifier accepts a production-shaped valid signature and rejects mutation, wrong/unknown keys, malformed signatures, and malformed catalogs;
- model installation/revalidation uses the immutable catalog revision and complete file-set/hash policy;
- offline transcription succeeds after the reviewed model is installed;
- legacy locally valid but now-untrusted models remain inspectable/removable but cannot be admitted for a new trusted run; and
- deterministic package provenance names and hashes the exact trust inputs bound to that candidate.

`release_ready` remains false until later OS signing/notarization, native installer activation, and representative-device evidence are complete.

## Sequence after #168

After production trust inputs are qualified, the intended Windows/macOS release sequence is:

1. OS signing/notarization;
2. native update activation;
3. representative-device qualification (#114); and
4. MVP release publication binding checksums, provenance, SBOM material, signatures, and device evidence to the same candidate.

Official public Linux packaging remains separately blocked by #135.
