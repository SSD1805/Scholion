# Native release qualification checklist

Browser mocks are necessary but insufficient evidence for a desktop application. Before a release candidate is considered qualified, exercise the real native seams on representative machines.

## Processing transport

For each supported OS, verify through the native Tauri window that:

- Processing readiness leaves `Checking…` and renders actual CPU/RAM/accelerator information;
- model inventory appears from the real Python bridge;
- previous-job history loads independently from readiness;
- a missing/broken Python interpreter produces a bounded, useful error;
- a child process that exits non-zero produces a bounded, useful error;
- an invalid protocol response produces a bounded, useful error;
- a stalled readiness request does not spin forever;
- debug diagnostics do not include evidence paths, transcript text, or request params.

## Representative machines

Minimum evidence set:

- Windows 8 GB CPU-only;
- Windows or Linux 16 GB commodity system;
- Apple Silicon macOS;
- NVIDIA dGPU laptop/workstation;
- 32/64 GB high-end workstation.

Hardware policy must remain conservative on small devices and must not artificially disable feasible acceleration on capable devices.

## Linux desktop stack

Qualify at least one Wayland and one X11 session. Record whether WebKitGTK requires the per-launch `WEBKIT_DISABLE_DMABUF_RENDERER=1` workaround. Do not silently persist that environment variable system-wide.

## Dependency/bootstrap recovery

From a clean checkout on each OS:

1. bootstrap Python with the project-local toolchain;
2. delete `.venv` and prove it can be recreated without deleting `.tools/uv`;
3. run `npm ci` from `frontend/`;
4. run `npm run doctor:desktop`;
5. run the locked native Cargo compile;
6. launch the native app and exercise Processing readiness.

Also qualify a pull in which one or more lockfiles changed. The contributor workflow should identify which disposable installed state must be synchronized instead of recommending global package upgrades.

## Supply-chain and containment gates

Before public distribution, execute the acceptance criteria in [Pre-release security hardening](../security/release-hardening.md) for signed manifests/update/model trust and hostile-input/process containment.

Application-layer encryption/keychain work follows its documented threat model and recovery contract rather than being inferred from this checklist.
