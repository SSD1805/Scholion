# Native release qualification checklist

Browser mocks are necessary but insufficient evidence for a desktop application. Before a release candidate is considered qualified, exercise the real native seams on representative machines.

Issue #114 owns the remaining representative native Processing task-transport evidence. Passing Playwright/axe, Rust tests, and hosted platform smoke is valuable but does not by itself close that requirement.

## Processing transport

For each supported OS, verify through the native Tauri window that:

- Processing readiness leaves `Checking…` and renders actual CPU/RAM/accelerator information;
- model inventory appears from the real Python bridge;
- previous-job history loads independently from readiness;
- model install/remove shows the relevant row in an explicit running state;
- transcription/model workers return only bounded public success/failure outcomes;
- a known safe application failure is shown immediately without a traceback/path/content leak;
- durable job state still refreshes after failure so Resume/Retry decisions are correct;
- speaker labeling is disabled with the backend's safe reason when the optional runtime is missing or security-held;
- the native host refuses a second supervised long-running Processing task while one is active;
- cancellation terminates the supervised child without turning native in-memory task state into job authority;
- a missing/broken Python interpreter produces a bounded, useful error;
- a child process that exits non-zero produces a bounded, useful error;
- an invalid protocol response produces a bounded, useful error;
- a stalled readiness request does not spin forever;
- a successful background refresh clears an older background warning without erasing an unrelated action error; and
- debug diagnostics do not include evidence paths, transcript text, request params, model-cache paths, or private exception details.

## Representative machines

Minimum evidence set:

- Windows 8 GB CPU-only;
- Windows or Linux 16 GB commodity system;
- Apple Silicon macOS;
- NVIDIA dGPU laptop/workstation;
- 32/64 GB high-end workstation.

Hardware policy must remain conservative on small devices and must not artificially disable feasible acceleration on capable devices.

### Current qualification status

| Class | Current evidence | Status |
|---|---|---|
| CPU-only representative machine | Hosted CI exercises CPU code paths, but no representative real-device #114 task-transport qualification has been recorded | **Pending** |
| Accelerator-capable Linux source build | Development dogfooding proved real native readiness, model inventory/download, Tauri → Rust → Python transport, and accelerator discovery before the complete #116 task-feedback tranche landed | **Partial; rerun current main** |
| Apple Silicon | Platform smoke exists, representative native desktop/task qualification not yet recorded | **Pending** |
| Windows 8/16 GB | Platform smoke exists, representative native desktop/task qualification not yet recorded | **Pending** |

Do not upgrade a `Partial` row to qualified based only on browser mocks or hosted CI. Record the date/version, operating-system class, CPU/RAM class, accelerator class (if any), exercised flows, and pass/fail result without publishing local usernames, hostnames, home-directory paths, recording names, or copied private logs.

## Linux desktop stack

Qualify at least one Wayland and one X11 session. Record whether WebKitGTK requires the per-launch `WEBKIT_DISABLE_DMABUF_RENDERER=1` workaround. Do not silently persist that environment variable system-wide.

The current GTK3-era Tauri graph is separately release-blocked by issue #135 because of the tracked GLib unsoundness. Passing this functional checklist does not waive that dependency gate.

## Dependency/bootstrap recovery

From a clean checkout on each OS:

1. bootstrap Python with the project-local toolchain (`python3.12 scripts/bootstrap_python.py` or the documented Windows equivalent);
2. delete `.venv` and prove it can be recreated without deleting `.tools/uv`;
3. run `npm ci` from `frontend/`;
4. run `npm run doctor:desktop`;
5. run the locked native Cargo compile;
6. launch the native app and exercise Processing readiness and one supervised long-running task.

Also qualify a pull in which one or more lockfiles changed. The contributor workflow should identify which disposable installed state must be synchronized instead of recommending global package upgrades.

## Supply-chain and containment gates

Before public distribution, execute the acceptance criteria in [Pre-release security hardening](../security/release-hardening.md) for signed manifests/update/model trust and hostile-input/process containment.

Issue #110 currently has the signed-update/model-trust schema and verification primitives, but production native signature verification, pinned release key(s), fixed-endpoint update checking, staged artifact activation, and real curated faster-whisper policy entries remain release work. This checklist must not treat the trust foundation as a finished update channel.

Application-layer encryption/keychain work follows its documented threat model and recovery contract rather than being inferred from this checklist.