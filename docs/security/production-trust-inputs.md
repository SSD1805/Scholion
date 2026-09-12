# Production trust inputs

This document defines the remaining production inputs for Scholion's Windows/macOS release path without pretending that private-key custody, reviewed upstream model snapshots, OS signing credentials, or representative-device evidence already exist.

The application-side trust mechanics are implemented. Exact signed payload bytes, key IDs, expiry, rollback/equivocation protection, stable-channel enforcement, fixed-endpoint manual checking, signed platform selection, exact size/SHA-256 staging, and fail-closed source behavior are already repository-owned.

The package/runtime side is also substantially complete:

- PR #164 established the managed frozen runtime and exact unsigned Windows NSIS/macOS DMG package foundation;
- PR #166 added deterministic release provenance and evidence-safe Windows install/uninstall/reinstall qualification;
- PR #167 made packaged FFmpeg/FFprobe repository-owned and exact-byte reviewable;
- PR #170 completed strict native Ed25519 update verification; and
- PR #172 completed deterministic custody, package handoff, and provenance binding for reviewed production trust inputs.

The remaining #168 work is now about **real production trust material** and **production-shaped qualification**. It is not missing application architecture.

`release_ready` remains false.

## Current release-trust split

The remaining work is tracked explicitly:

- **#177** owns creation/custody of the real Scholion Ed25519 release-signing key and the reviewed public `update-keys.json` catalog.
- **#178** owns live upstream review of the first-release faster-whisper `tiny`, `small`, and `medium` snapshots, including immutable revisions, licenses/model cards, complete file sets, sizes, hashes, and engine compatibility.
- **#168** remains the parent gate that binds those exact public inputs into a production-shaped package and proves update/model behavior end to end.
- **#173** follows #168 for Windows code signing and macOS Developer ID signing/notarization.
- **#174** follows platform signing for explicit user-authorized native activation of a trusted staged update.
- **#114** remains representative real-device qualification.
- **#175** owns final production release publication, including checksums, provenance, SBOM, signatures, signed update metadata, and GitHub Release artifacts.

Official Linux binary distribution remains separately blocked by #135.

## Application release verifier

Merged PR #170 implemented Scholion's packaged release verifier using exactly `ed25519-dalek` 3.0.0 in the native Rust host.

The reviewed implementation contract is:

- package: `ed25519-dalek`
- selected version: exactly `3.0.0`
- upstream repository: `dalek-cryptography/curve25519-dalek`, `ed25519-dalek/`
- license: BSD-3-Clause
- declared minimum Rust version: 1.85
- verification API: `VerifyingKey::from_bytes` plus `VerifyingKey::verify_strict`
- no signing API required by the installed application
- default features disabled
- no `legacy_compatibility`
- no `hazmat`

PR #170 exact-pinned the dependency, let Cargo generate the lockfile, kept verification at the native application boundary, and passed locked Rust, dependency-policy, Security, Quality, Acceptance, and Windows/macOS Release Qualification gates before merge.

The project does not add another updater framework merely to obtain one cryptographic primitive. Scholion already owns a narrower metadata/staging protocol with explicit privacy, rollback, and evidence semantics.

## Public-key custody and rotation

The installed application receives public verification material only.

A production key record contains:

- a bounded key ID such as `release-2026-a`;
- algorithm `ed25519`;
- exactly 32 public-key bytes encoded as lowercase hexadecimal; and
- lifecycle state `current` or `next`.

The catalog contains one or two unique keys and exactly one `current` key. Duplicate IDs, duplicate key bytes, malformed records, unknown fields, unsupported algorithms, ambiguous current state, and invalid encodings fail closed.

The corresponding private signing key must never be:

- committed to this repository;
- embedded in the application;
- stored in ordinary GitHub Actions variables/artifacts for convenience;
- printed into CI logs;
- pasted into issues, PRs, fixtures, or ChatGPT; or
- accepted by Scholion's release-metadata builder.

`scripts/build_release_metadata.py` intentionally accepts only an externally produced public signature.

### Rotation rule

Key rotation is an application release event, not a mutable server-side setting.

1. Ship release N with the current key and the next public key both trusted by the installed client.
2. Only after release N is available should release N+1 begin signing metadata with the new key ID.
3. Keep the previous verification key only for the documented overlap window needed by supported older clients.
4. Removing a key requires a later signed application release and a new manifest sequence.
5. Reusing a sequence for corrected metadata or a different key is forbidden.

A compromised signing key requires an incident-specific recovery plan. A client that has only the compromised key cannot learn a trustworthy replacement key from metadata signed solely by that compromised key.

## Deterministic custody of reviewed trust inputs

Merged PR #172 completed the repository-owned handoff for real trust material without creating that material itself.

The production flow is:

1. review and approve the real `update-keys.json` and `model-trust.json` source inputs;
2. run `scripts/prepare_release_trust_inputs.py` with those exact files;
3. revalidate both documents through Scholion's strict schemas;
4. stage their exact bytes under `build/release-trust-inputs/` together with deterministic `release-trust-inputs.json` evidence;
5. pass that prepared directory explicitly to `scripts/build_desktop_runtime.py --release-trust-dir ...`;
6. verify the exact packaged copies with `scripts/verify_packaged_release_trust_inputs.py`; and
7. bind the staged trust-input identities into release provenance with repeatable `scripts/build_release_provenance.py --input ...` arguments.

The preparation evidence records only public/semantic identity needed for review and reproducibility: input filename, size, SHA-256, public key IDs/states, model IDs, engines, repository IDs, immutable revisions, and license identifiers. It does not record workstation paths or any private signing material.

Preparation never treats generation as approval. It preserves the exact approved input bytes, overwrites only its fixed generated outputs, and leaves unrelated files alone. Runtime installation copies only the verified allowlist, not arbitrary neighboring files from the preparation directory.

### Packaged locations

The reviewed model catalog is installed at:

```text
runtime/_internal/scholion/supply_chain/model-trust.json
```

The public update-key catalog and custody evidence are installed at:

```text
runtime/release-trust/update-keys.json
runtime/release-trust/release-trust-inputs.json
```

The native Tauri host resolves `update-keys.json` only through this package-relative runtime location. It does not search `PATH`, accept an update-supplied key path, or inherit an ambient verifier override. Ordinary preview/source builds that omit `--release-trust-dir` remain trust-free and update checking stays off.

The staged `build/release-trust-inputs/` directory is ignored by Git because it is build-time handoff material. A deliberately reviewed source policy may be committed separately in ordinary review; generated staging evidence is not the policy source of truth.

PR #172 merged after exact-head Quality #1342 and Release Qualification #101 passed.

## First-release faster-whisper model set

The first Windows/macOS release model IDs are deliberately fixed to:

- `tiny`
- `small`
- `medium`

These are exactly the model identities exposed by Scholion's current screening, balanced, and accuracy strategy tiers. CPU and CUDA strategy variants reuse the same three model identities.

The current provider mapping in `src/scholion/model_management/catalog.py` is:

- `tiny` → `Systran/faster-whisper-tiny`
- `small` → `Systran/faster-whisper-small`
- `medium` → `Systran/faster-whisper-medium`

That mapping is not production approval. Each repository's immutable revision, ownership/model card, license identifier/text/URL, exact snapshot file set, and engine compatibility still require live upstream review under #178 before a production `model-trust.json` entry can be approved.

## Real faster-whisper model trust review

For each of the three first-release model IDs:

1. confirm the exact upstream repository and select an immutable 40-hex revision deliberately;
2. review source ownership, model card, license identifier/text, license URL, and material upstream constraints;
3. acquire that exact revision into an isolated review cache;
4. run `scripts/generate_model_trust_entry.py` against the deliberately selected snapshot and cache root;
5. review the generated complete logical file set, byte sizes, SHA-256 values, and in-cache symlink resolution;
6. run representative transcription/regression checks using that exact revision and the engine version shipped by the candidate;
7. record why the revision was selected and any material compatibility notes;
8. assemble the three approved entries into the reviewed production `model-trust.json`; and
9. ship the policy only inside the appropriately signed production application release.

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

- creating and safeguarding the real private Scholion release-signing key (#177);
- live review and approval of the immutable faster-whisper revisions/licenses (#178);
- generating/reviewing the final public-key resource from the selected release key;
- creating production-shaped signed update fixtures without exposing the private signer to CI;
- Windows/macOS platform-signing credentials (#173); and
- representative native qualification using the actual packaged key/catalog (#114).

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

`release_ready` remains false until the later release gates are complete.

## OS signing is separate from Scholion update signing

Scholion's Ed25519 release signature and OS platform signing solve different problems.

- Scholion's Ed25519 signature proves that release metadata and staged artifact identity were authorized by the Scholion project.
- Windows code signing lets Windows identify/trust the publisher of the distributed Windows artifact.
- macOS Developer ID signing and notarization let Gatekeeper evaluate a directly distributed macOS build.

The planned macOS path does **not** require Mac App Store publication. See `os-signing-and-notarization.md` and #173.

## Sequence after #168

After production trust inputs are qualified, the intended Windows/macOS release sequence is:

1. #173 OS signing/notarization;
2. #174 native update activation;
3. #114 representative-device qualification; and
4. #175 MVP release publication binding checksums, provenance, SBOM material, signatures, signed update metadata, and device evidence to the same candidate.

Official public Linux packaging remains separately blocked by #135.

Related: #168, #177, #178, #173, #174, #114, #175, #135, merged PRs #144, #164, #166, #167, #170, #172, `update-model-trust.md`, `os-signing-and-notarization.md`.
