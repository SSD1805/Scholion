# Processing Center

The Processing Center is Scholion's desktop control surface for local transcription work. It is intentionally a productization layer over existing backend authorities, not a second scheduler or transcription implementation.

## Authority boundaries

### Python application services own decisions

Python remains authoritative for:

- health and machine-resource inspection;
- processing-profile policy;
- strategy feasibility and recommendation;
- model inventory, local revalidation, installation provenance, removal safety, and policy-trust checks when that stronger policy is enabled;
- media probing and audio-stream selection;
- whether a multi-track recording requires explicit stream confirmation;
- transcription preflight and resource admission;
- checkpoint compatibility and resume contracts;
- transcription execution correctness;
- diarization requests and explicit model-download consent;
- canonical transcript publication and derived exports;
- durable private job lifecycle state.

The desktop bridge exposes bounded typed operations only. It does not expose arbitrary shell, filesystem, SQL, database, or model-provider access.

### Tauri owns long-running child-process lifetime

The existing `desktop_request` bridge is deliberately short-lived: it starts Python, sends one bounded request, waits for one response, and exits. Long transcription or model-management work must not turn that RPC into an hour-long request.

Tauri therefore supervises a small allowlist of long-running task kinds:

- new transcription;
- checkpoint resume;
- fresh retry;
- model installation;
- model removal.

The native host does not decide which strategy is safe, which audio stream should be used, or whether a model is valid. It receives already-shaped intent, starts only allowlisted Python worker commands, owns the child handle, exposes status/cancel, rejects duplicate task identities, and terminates supervised children during desktop shutdown.

Only one supervised long-running Processing task may be active in a desktop session at a time. That native invariant matches React's one-current-task presentation model and prevents a second launch from orphaning the UI's reference to an earlier child.

A cancelled or externally terminated transcription is recovered through Python's durable lifecycle/checkpoint rules. Tauri does not maintain a competing job database.

Long-running workers return one bounded, versioned public outcome envelope. Successful completion carries no debug payload. A known application failure may cross only as Scholion's approved public error code/message. Tracebacks, exception causes, request bodies, transcript content, recording paths, and model-cache paths are not a task-status API.

### React owns presentation and explicit user intent

The normal Processing Center UI leads with outcome-oriented profiles:

- **Quick draft** for provisional screening;
- **Balanced** for the ordinary default;
- **Best locally safe** for the highest-quality feasible local strategy.

Ordinary users are not required to choose Whisper model sizes, thread counts, compute types, or memory limits. Expert strategy controls remain explicit advanced options and are revalidated by Python before execution.

Audio-track selection is different because it can change **which evidence is transcribed**. A single-track source needs no user decision. When Python reports more than one embedded audio stream and no stream was explicitly requested, the preflight DTO sets `audio_stream_selection_required=true`. React then presents the bounded stream facts returned by Python and keeps Start disabled. Selecting a track sends its exact integer stream index back through the existing typed preflight call; Python replans against that stream before the UI treats the choice as confirmed.

React does not score or recommend tracks. Source-declared title, language, and container-default disposition are displayed as clues only. They are bounded by the backend and remain untrusted descriptive metadata. Codec, sample rate, and channel count are also presentation facts, not selection policy.

Model acquisition is never silently inferred from selecting a profile. The UI shows the recommended model and whether Scholion currently has a usable managed local snapshot. Installing or removing a model is an explicit long-running action, and the affected row shows an explicit indeterminate running state while work is active.

The consumer explanation stays consequence-first: models download only when the user chooses, remain on this computer in Scholion's private app storage, and can be used offline after installation. The UI should not use a bare word such as “verified” to imply stronger supply-chain guarantees than the backend has actually established.

Today's managed-model path records an immutable provider revision and locally revalidates repository/revision/layout expectations. Issue #110 defines the stronger policy-trust layer: the exact approved upstream revision plus the complete allowed file set, sizes, and SHA-256 values must match before a model can be called policy-trusted. See **[Signed update and model trust channel](../security/update-model-trust.md)**.

Optional diarization keeps its network/dependency boundary separate from transcription-model custody. Processing asks Python for a read-only speaker-labeling capability state before offering the option. If the optional runtime is missing, unverifiable, or security-held, the control is disabled with a safe reason rather than inviting a task the backend is guaranteed to reject.

Derived TXT/SRT/VTT files remain disposable views; canonical transcript JSON remains evidence.

## Start flow

1. User selects a recording and processing intent.
2. React asks Python for preflight.
3. Python probes the recording, inspects current resources, assesses strategies, revalidates managed model custody, and returns a minimized preflight DTO.
4. If the source has several embedded audio streams and no explicit stream was requested, Python marks stream confirmation as required. The desktop presents the available tracks but does not treat the probe default as user intent.
5. The user chooses one track. React submits only that stream index and Python re-runs preflight with the exact selection bound into the plan.
6. The user reviews the resulting profile/strategy/resource plan.
7. React asks Tauri to start an allowlisted transcription worker for the exact preflight job identity and selected stream.
8. Python owns lifecycle state and checkpoints while the native host owns child-process lifetime.
9. The Processing Center polls bounded task status and durable job lifecycle state.
10. If a worker fails, the approved public reason is shown immediately and durable lifecycle state is still refreshed for Resume/Retry decisions.
11. Successful execution publishes canonical transcript evidence and any explicitly requested derived exports.

Private source/output/model-cache paths are not part of the general Processing Center overview DTOs. Path-bearing execution intent is kept to the narrow operation that actually needs it.

The selected stream index is not merely presentation state. Planning validates it, FFmpeg maps exactly that stream during normalization, canonical source provenance records it, and checkpoint resume restores it.

## Multi-track metadata inspection

Scholion preserves the original hardened FFprobe query for normal media inspection. If that first query discovers more than one audio stream, the probe performs one additional bounded metadata-only query under the same file-only protocol whitelist and output-size limit.

That extra query asks only for stream index, title, language, and default disposition. Title and language are length-bounded before they can enter `MediaStream`. The metadata helps a user identify a track but is not added to cryptographic source identity and is not trusted as a Scholion recommendation.

This feature covers **multiple embedded audio streams inside one file**. It does not synchronize several separate source files. See **[Audio tracks](../audio-tracks.md)** for the product distinction.

## Resume, retry, cancel, and discard

These operations are deliberately distinct:

- **Resume** restores the interrupted job's checkpointed execution contract and re-admits it against current hardware. It does not silently change profile, strategy, audio stream, or enhancement settings.
- **Retry** creates a new plan from the source recording. It is allowed to use current defaults or a newly selected track/strategy.
- **Cancel** terminates the supervised child. Valid checkpoints remain subject to the normal resumability rules.
- **Discard private job state** removes disposable lifecycle/checkpoint state only. It never deletes original recordings, published canonical transcript evidence, or human research state. The request is bound to the job's current `updated_at` value so stale UI state cannot delete a newer lifecycle generation.

A job reported as `running` whose recorded process identity is no longer active is reconciled by the Python lifecycle store to `interrupted`. This makes recovery durable across application restarts without treating native in-memory task state as authoritative.

Background readiness/job/discovery refresh failures have a separate presentation lifecycle from explicit user-action failures. A successful retry clears the stale background warning; it cannot overwrite or preserve an unrelated action error forever.

## Playback is a separate guarantee

Explicit multi-track transcription does not imply that verified native playback may choose among embedded tracks. Transcription owns FFmpeg extraction and can prove which stream entered ASR. Current WebView playback of the original container does not provide Scholion a portable guarantee that the canonical stream will be the rendered stream.

For that reason multi-track transcription is supported while multi-track verified playback still fails closed. See **[Verified native playback](../native-playback.md)**.

## Failure and privacy semantics

Processing Center errors crossing into the desktop are public, bounded messages. Backend exceptions, raw provider errors, and private filesystem detail are not rendered directly into the UI.

Readiness and job overview responses expose only what is necessary to explain local execution state, such as platform, effective CPU count, available-memory budget, profile, model identity, progress, resumability, capability availability, and safe failure categories. Multi-track preflight adds bounded stream identity/display fields but no filesystem paths.

Model-storage copy describes custody without exposing the cache path or granting React a generic path opener. If Scholion later adds **Show model folder**, that must remain a narrow host-owned action for the known managed-model directory, not arbitrary filesystem authority.

The design preserves Scholion's central custody rule: recordings, canonical transcript evidence, and human research remain authoritative user-owned material; execution indexes, checkpoints, derived exports, model cache bytes, and native task handles are supporting machinery and may be rebuilt or discarded according to their contracts.

## Qualification boundary

Browser Playwright proves presentation and accessibility states but intentionally uses mock clients for native Processing. It cannot qualify the real React → Tauri → Rust → Python task transport.

Release qualification therefore still requires representative native evidence on CPU-only and accelerator-capable machines, including readiness, model tasks, transcription start/failure/success behavior, bounded public failure propagation, cancellation, and durable recovery. This remaining real-device evidence is tracked under issue #114 rather than being represented as browser-test coverage.