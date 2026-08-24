# Architecture and redundancy audit

This audit removes duplicated **meaning and ownership**, not merely repeated lines. Scholion deliberately keeps narrow adapters where playback, custody, updates, transcript tools, processing, research, and ordinary desktop operations carry different authority.

## Status: complete, re-audited after the update-channel tranche

The original pre-identity audit closed three cleanup tranches:

1. trusted-host transport and composition consolidation;
2. Research saved-question and evidence-contract consolidation; and
3. broad desktop transport/composition closure.

Issue #145 re-opened the question briefly after merged PR #144 added the application update channel. The post-#144 audit found two pieces of genuine duplicate plumbing and no evidence of a broader architectural fork:

- the update desktop adapter was constructing `UpdateChannelService` itself instead of receiving composition from the application layer; and
- model-trust catalog generation and release metadata generation each carried the same bounded file SHA-256 implementation.

Both are now consolidated. The update service is composed by `scholion.app.update_composition`, leaving `update_bridge.py` as validation/dispatch only. Supply-chain file hashing has one capability-blind implementation in `scholion.supply_chain.digests`.

The exit criterion remains met: remaining similarity is intentional authority separation, explicit compatibility, readable boundary validation, or ordinary interaction-local state rather than unresolved evolutionary residue.

## Reconsolidation rules

### Capability-blind shared plumbing

Share mechanics that cannot grant new authority.

`scholion.desktop.host_protocol` owns bounded JSON stdin/stdout transport and the versioned response envelope. It knows nothing about methods, services, paths, databases, update hosts, or Tauri commands.

The general desktop, playback-authorization, transcript-tools, custody, and update bridges use that same capability-blind helper while retaining separate request schemas, dispatchers, public-error policy, and application capability.

`scholion.supply_chain.digests.sha256_file` similarly owns only bounded local file hashing. Release metadata and model-trust catalog generation reuse it rather than carrying two identical digest loops.

### Authority-preserving adapters

A shared transport does not imply a shared capability. `desktop_request`, `transcript_tools_request`, `lifecycle_request`, and `update_request` remain separate fixed Tauri commands because their authority differs.

The update adapter in particular must not become a generic network bridge. React cannot supply an update URL, header, path, artifact, command, or installer argument. Endpoint selection, platform selection, trust verification, anti-rollback state, and staging remain application policy.

Playback also remains separate because Rust returns opaque media-session state and byte-range authority rather than a normal desktop protocol response.

### Application-layer composition

Desktop adapters do not quietly construct service graphs.

`AppContainer` remains the primary application dependency graph for ordinary services including playback authorization, speaker presentation, transcript tools, Research search controls, model management, and Processing Center.

The update channel has one dedicated application-layer composition function in `scholion.app.update_composition`. That seam is intentionally separate from the desktop adapter because the production verifier/public-key input is owned by later packaging/release provisioning rather than by React or the bridge. Source builds call the same composition seam with no verifier and therefore remain fail-closed/off.

This preserves the same architectural rule as the original audit without forcing release-key provisioning into an unrelated general container provider prematurely.

### Fixed-command frontend transport

`frontend/src/api/nativeProtocol.ts` owns the shared versioned request envelope, response validation, request IDs, fixed Tauri invocation, and public-error unwrapping used by ordinary desktop, Processing bounded requests, transcript tools, Research anchor maintenance, lifecycle calls, and Updates.

Its command type is closed to:

- `desktop_request`;
- `transcript_tools_request`;
- `lifecycle_request`; and
- `update_request`.

Adding Updates therefore did not create a second frontend native protocol implementation.

Processing task launch/status/cancellation intentionally remain separate. They use dedicated Rust commands for supervised long-running child-process lifetime and return a different task-status contract, not the one-shot Python request/response envelope.

### Fixed Rust Python-module wrappers

`frontend/src-tauri/src/backend.rs` has one private request runner and tiny wrappers bound to hard-coded Python modules. The WebView cannot select a module name. `update_request` follows this existing pattern by hard-coding `scholion.desktop.update_bridge`.

Keep that shape. A dynamic module dispatcher would save lines while weakening the threat model.

### Shared Research contract, not shared policy

`scholion.desktop.research_serialization` maps already-authorized evidence into one frontend shape. It does not choose generations, resolve evidence, query storage, or expose canonical/source paths.

`scholion.desktop.research_validation` owns the stable label invariant shared by Research adapters: trim, reject invalid values, de-duplicate case-insensitively, and preserve display spelling.

Search policy and durable saved-question lifecycle remain application/library authority.

### One saved-question desktop authority

The earlier Research UI exposed two management surfaces and two desktop API families over the same SQLite `SavedSearch` / `SavedSearchIntent` objects. The richer typed Research search surface now owns list, create, inspect, replace, run, and optimistic-concurrency delete.

The older desktop ingress and duplicate browser mock store are gone. CLI/internal domain capability remains available. No authoritative research data migration was required.

### Release-policy checks before signing

The post-#144 pass also tightened the release-builder side of an existing policy seam. First-release metadata generation now refuses a non-stable channel, invalid SemVer text, and non-UTC signing timestamps before exact payload bytes are produced for the offline signer.

Runtime verification still owns distrust of remote metadata. Release tooling owns preventing the project from signing a payload that the stable client would predictably reject. Those are complementary lifecycle responsibilities, not competing trust roots.

## Intentionally retained boundaries

### Short requests versus supervised processing tasks

`backend.rs` and `processing.rs` both launch Python, but they do different jobs. The former performs bounded request/response IPC; the latter owns long-lived child-process supervision, task identity, cancellation, and process cleanup. Combining them would erase a useful lifetime and authority boundary.

### Update trust state versus model/research state

Update anti-rollback state, model-policy evidence, and research authority all persist local information, but they are not one generic state problem.

- update trust state exists to remember monotonic signed-release history and the last trusted manifest for re-verification;
- model-policy evidence describes exact executable model bytes under the current bundled policy; and
- research state is durable human-authored knowledge.

A universal persistence abstraction here would hide materially different recovery, authority, and deletion semantics.

### Explicit Pydantic request models

Repeated `ConfigDict(extra="forbid")` is a visible security property. A generic validation hierarchy would make unexpected-field refusal harder to inspect for little practical gain.

### Domain-visible E2E fixtures

Browser mocks deliberately repeat some DTO shape. They are executable examples of what the WebView can see, and they keep path-disclosure, trust-state, and human-copy assertions legible. Centralizing every fixture would reduce textual repetition while obscuring the boundary being tested.

### Interaction-local React state

Loading, error, confirmation, editing, update-check, and staging state can resemble one another without sharing lifecycle semantics. There is no evidence of policy drift that justifies a generic interaction-state framework.

## Pre-release compatibility cleanup

The earlier audit retired the deprecated runner `ModelTier` and `recommended_model_tier` wire field before distribution could turn internal residue into a released compatibility contract. No canonical evidence, authoritative research, or checkpoint format depended on that marker.

The same rule now governs release work: preserve real user-owned and released contracts aggressively; do not manufacture permanence for obsolete internal shapes merely because tests once serialized them.

## Test policy

The audit does not add source-text, existence-only, or self-fulfilling tests.

Qualification relies on observable contracts:

- shared host transport tests bound input size, malformed JSON, response versioning, dispatch suppression, and stdout isolation;
- application composition tests protect the source-build update-off state;
- desktop bridge tests exercise closed allowlists, strict request validation, public error masking, path non-disclosure, and delegation;
- Research tests preserve optimistic concurrency and exact-generation evidence behavior;
- update-channel tests cover signature/timestamp/channel/platform/rollback/equivocation/staging failure behavior;
- release tooling tests reject invalid signing inputs before offline signing;
- frontend parser tests protect compatible/incompatible native envelopes; and
- feature-level Playwright/axe flows exercise user-visible paths using the same conceptual authority graph as production.

Mutation testing remains targeted at decision-heavy policy rather than becoming a blanket frontend tax.

## Audit exit criterion

The audit is closed when all of the following are true:

- capability-blind trusted-host transport has one implementation;
- application services are composed outside presentation adapters;
- the frontend's bounded native protocol has one fixed-command implementation;
- Research saved-question and evidence presentation contracts no longer have duplicate desktop authorities;
- update authority remains narrow rather than becoming generic network/filesystem/process authority;
- capability-blind supply-chain digest mechanics have one owner;
- no stale compatibility layer is mistaken for current policy; and
- remaining repetition has an explicit readability, security, compatibility, authority, or lifecycle reason.

Those conditions are satisfied after the #145 re-audit. The next major engineering milestone is packaging, not another architecture rewrite.
