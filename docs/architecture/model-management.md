# Local model management 📦🔐

## The human version

Scholion needs speech models to transcribe locally. Those model files are large,
versioned execution dependencies, not mysterious cache confetti.

So Scholion keeps one very deliberate boundary around them:

> **Downloading a model is an explicit action. Running transcription uses a model that
> Scholion has already installed, locally revalidated, and pinned to an immutable
> provider revision.**

That gives ordinary users a simpler experience and gives maintainers something they can
actually reason about.

```mermaid
flowchart LR
    A[Model catalog] --> B[Recommend]
    B --> C[Explicit install]
    C --> D[Disk admission]
    D --> E[Provider download]
    E --> F[Local revalidation]
    F --> G[Private managed manifest]
    G --> H[Local transcription plan]
    H --> I[Local-only execution]

    classDef info fill:#D8EEFF,stroke:#2E617B,stroke-width:2px,color:#12222A
    classDef network fill:#E8D9FF,stroke:#68469B,stroke-width:2px,color:#1F1630
    classDef evidence fill:#FFF0B8,stroke:#8A6B18,stroke-width:2px,color:#2C260F
    classDef run fill:#DDF5E3,stroke:#347A46,stroke-width:2px,color:#142719

    class A,B,D info
    class C,E network
    class F,G evidence
    class H,I run
```

That diagram describes the current default source-build path. The #110 policy-trust path
adds an exact project-owned revision/file allowlist between provider download and managed
registration once a reviewed production trust catalog is bundled and enforcement is
enabled.

## Why Scholion does not just trust whatever is in a cache

The Hugging Face cache is a useful byte-level storage layout. Scholion does not need to
copy model weights into a proprietary format.

But “some files exist in a cache directory” is not enough to answer:

- which model Scholion intended to install;
- which provider repository it came from;
- which immutable revision was resolved;
- whether the expected files are still present; or
- whether a transcription plan can safely refer to that exact dependency later.

So the provider cache remains the physical home of the bytes while Scholion owns private
**managed manifests** describing snapshots it deliberately installed and locally
revalidated.

A pre-existing cache entry is not silently adopted as managed state.

## What a managed manifest records

The current contract records at least:

- logical model ID and engine;
- provider repository ID;
- requested provider revision, when supplied;
- resolved immutable revision;
- absolute local snapshot path;
- measured snapshot size; and
- local revalidation method.

A manifest can now also record a separate policy-trust receipt when installation was
performed against a supplied curated Scholion trust catalog. That receipt contains the
catalog schema version, policy model identity and revision, exact-verification method,
verified file count, and verified byte count.

The manifest is a receipt and dependency record, not a second copy of the model. A
recorded policy receipt is also not a permanent trust bit: current policy verification is
recomputed when the managed state is read under a loaded trust catalog.

## The main responsibilities

`ModelCatalog` describes the finite set of models Scholion knows how to reason about.
For faster-whisper, quality/cache metadata is derived from the transcription strategy
catalog instead of duplicated.

`ModelManager` owns application-level inventory, explicit installation, manifest custody,
local revalidation, resolved-revision lookup, removal, and the boundary that applies
project-owned model policy when a curated catalog is supplied.

`ModelProvider` owns provider-specific mechanics such as obtaining a Hugging Face
snapshot, validating its cache layout, and removing an exact cached revision.

`ModelStorageAdmitter` checks disk capacity before acquisition starts.

`scholion.supply_chain` owns the stronger project policy itself: exact approved
repository/revision identity plus the full allowed file set, byte sizes, SHA-256 values,
source/license metadata, and fail-closed snapshot verification.

The split matters because “what models does Scholion support?”, “how does this provider
download bytes?”, and “which exact bytes did the project approve?” are different
questions. The #110 integration deliberately composes those authorities instead of
turning provider-local validation and project policy into one vague “verified” state.

## Install transaction without a production policy catalog

The current default application composition follows this order:

1. resolve the model ID through the catalog;
2. reject an invalid/blank requested revision;
3. admit the estimated cache requirement against current disk capacity;
4. create private model/cache/registry directories only after admission succeeds;
5. ask the provider to acquire the requested repository/revision;
6. reject a returned snapshot outside Scholion's configured model cache;
7. bind the snapshot path to the declared provider repository cache directory;
8. require the snapshot directory name to equal the resolved immutable revision;
9. require the provider-specific files to exist and be non-empty;
10. measure the installed snapshot and construct provenance; and
11. commit the private Scholion manifest **last**.

That ordering is intentional.

A disk refusal should not begin a giant download. A malformed provider result should not
become managed state. A manifest should mean “the install made it through the current
local validation contract,” not “we started trying.”

🦝 The raccoon gets a receipt after the groceries are actually in the pantry.

## Policy-enforced install seam

The #110 integration adds a stricter transaction when `ModelManager` receives a curated
`ModelTrustCatalog`:

1. resolve the ordinary model catalog entry and the matching project trust entry;
2. require model ID, engine, and provider repository identity to agree across both
   catalogs;
3. reject a caller-supplied revision that differs from the curated immutable revision
   **before** provider acquisition starts;
4. ask the provider for exactly the curated revision;
5. retain the normal provider/cache/repository validation boundary;
6. require the returned resolved revision to equal the curated revision;
7. require the observed snapshot file set to equal the curated file set exactly;
8. verify every curated file's byte size and SHA-256 while enforcing path/cache
   containment;
9. create separate policy-trust evidence from the successful exact verification; and
10. commit the managed manifest only after both local/provider validation and policy
    validation succeed.

When `enforce_policy_trust=True`, a missing catalog entry or a previously managed
manifest without current policy evidence fails closed. Existing manifests remain
parseable so upgrading the manifest format does not itself destroy local custody state.

This mechanism does **not** manufacture the production policy. Tests use synthetic local
bytes and synthetic immutable revisions. The real faster-whisper entries still require a
deliberate upstream review and must ship as part of a signed Scholion release.

## User surface

The normal flow is deliberately boring. After the repository environment is bootstrapped
and activated:

```bash
scholion models recommend
scholion models install small
scholion transcribe recording.m4a
```

Inventory is offline:

```bash
scholion models
```

Removal is explicit:

```bash
scholion models remove small
```

The CLI requires confirmation unless `--yes` is supplied.

In the desktop, ordinary copy should explain consequences rather than implementation:
models download only when the user chooses, stay on this computer in Scholion's private
app storage, and can be used offline after installation. Repository IDs, exact revisions,
hashes, licenses, and policy-trust evidence belong under technical details or security
documentation.

Until a reviewed production catalog is actually bundled and enforcement is enabled in
application composition, ordinary UI must continue to describe the default managed model
as locally revalidated rather than policy-trusted.

## Inventory and local revalidation

Inventory and resolved-revision lookup are offline and side-effect free. They do not
create directories, download models, or repair provider state.

When a managed manifest exists, Scholion revalidates it before claiming the model is
usable under the current custody contract. Validation checks that:

- manifest identity still matches the catalog model/repository;
- the snapshot remains inside Scholion's configured model cache;
- the snapshot belongs to the declared provider repository cache directory;
- the path agrees with the recorded resolved revision;
- the local verification method is supported; and
- required provider files remain present/non-empty.

If the manager has a current trust catalog and the manifest carries policy-trust
evidence, it additionally recomputes the exact file-set/size/SHA-256 verification and
requires the resulting evidence to match the recorded receipt. With policy enforcement
enabled, a manifest without current policy evidence is rejected.

If external deletion or tampering makes that managed state stale, Scholion fails closed.
A same-length byte mutation therefore cannot preserve policy trust merely because the
provider-local required-file check still passes.

The receipt is evidence of what Scholion checked earlier. It is not allowed to become a
magic amulet that makes missing or modified bytes reappear.

## Local revalidation is not policy trust

Default faster-whisper revalidation establishes structural/provider provenance: expected
cache layout, repository/revision identity, and required non-empty files.

It does **not** by itself prove that every installed byte matches a project-approved
cryptographic allowlist. Do not describe that default state simply as “verified” where a
reader could reasonably infer the stronger claim.

The #110 code path for the stronger guarantee is now integrated into `ModelManager`: a
supplied curated policy pins the revision, exact-verifies before registration, persists a
separate policy receipt, and revalidates that receipt later. What remains before the
product can rely on that guarantee is release content and composition rather than another
parallel verification mechanism: review real upstream faster-whisper revisions, generate
and bundle the production catalog, enable enforcement in the application container,
expose the distinction in technical model state, and make new-transcription admission
require current policy trust.

See **[Signed update and model trust channel](../security/update-model-trust.md)** for the
full trust model and privacy boundary.

## Transcription custody boundary

There is one ASR model path.

A new transcription plan currently resolves the selected faster-whisper model through
the locally revalidated managed registry.

If the model is not installed and locally revalidated, planning fails with an
install-first message.

A successful plan therefore records a non-empty immutable resolved revision.

At execution time, faster-whisper loads that exact local revision with
`local_files_only=True`.

There is no:

- transcription-time ASR download flag;
- ambient-cache fallback;
- arbitrary configuration revision override; or
- silent substitution of a newer model because the old one is inconvenient.

Resume restores the exact managed model revision recorded in the checkpoint contract.
It never downloads a replacement as a side effect.

Once the production catalog is bundled and enforcement is enabled, “usable for a new
transcription” must additionally require current Scholion policy trust. That admission
switch is intentionally not enabled against synthetic or unreviewed trust data.

## Network boundary 🔐

`scholion models install MODEL` is the explicit network-bearing ASR model action.

Inventory, recommendation, planning with an already-managed model, and execution do not
need to contact the model provider.

Model management never uploads source media, transcripts, job metadata, or application
telemetry to the provider.

This is why the install boundary is visible to the user instead of being buried inside
`transcribe`.

## Removal transaction

Removal is intentionally asymmetric with installation:

1. resolve and validate the managed manifest;
2. reconstruct the exact installed snapshot identity;
3. ask the provider to remove that resolved revision from the local cache; and
4. delete the Scholion manifest **only after provider removal succeeds**.

If provider removal fails, the manifest is retained.

Scholion should not forget that it owns bytes it failed to remove.

## Failure semantics

Private registry/model state lives under Scholion's application model root.

These conditions fail closed:

- corrupt registry data;
- path escape;
- repository mismatch;
- stale/missing snapshot;
- unsupported local verification method;
- required-file verification failure;
- storage refusal; and
- provider removal failure.

With a trust catalog supplied, these conditions also fail closed before policy-trusted
registration or revalidation:

- missing required trust entry when enforcement is enabled;
- catalog/model identity mismatch;
- moving or unapproved revision;
- undeclared or missing file;
- byte-size mismatch;
- SHA-256 mismatch; and
- persisted policy evidence that no longer matches current verification.

Routine public errors should describe the application failure without leaking private
internal paths.

## Reusing the custody pattern for future local models

Future model-backed capabilities should reuse the same ideas:

- capability-specific catalog/qualified profiles;
- provider adapters for acquisition;
- immutable resolved revisions;
- private manifests;
- disk admission before acquisition;
- offline inventory/revalidation;
- project-owned trust policy when executable/model bytes are distributed; and
- execution through managed, policy-qualified model identity where that policy exists.

The current FFmpeg speech-noise-suppression provider is model-free, so it does not
pretend to have a model manifest.

If a future neural enhancement, alignment, source-separation, or embedding provider adds
weights, those weights should enter through this custody/trust family rather than
inventing a new hidden download path.

## Generalize only when reality asks

The first implementation manages faster-whisper models. Semantic embeddings currently
have their own strict-local profile/snapshot boundary and are not yet a locked managed
extra.

A broader shared model-custody abstraction should emerge when a second qualified
model-backed capability exposes real common variation.

Scholion does not need a speculative universal model marketplace merely because such an
abstraction would look impressive on a diagram.

## Current deliberate limits

Model management does not currently provide:

- automatic/background model updates;
- adoption of arbitrary cache entries;
- generic arbitrary model hubs;
- model quota/garbage-collection policy;
- hosted inventory/telemetry;
- a reviewed production faster-whisper policy catalog bundled into application releases;
- production `AppContainer` policy enforcement and new-transcription admission; or
- a finished technical-details UI for local revalidation versus current policy trust.

The stable rule is:

> **Scholion should know which local model dependency it chose, where it came from,
> which immutable revision it installed, what level of trust/revalidation has actually
> been established, whether it is still present, and when it is safe to use or remove.**

Not glamorous. Extremely useful. 💃
