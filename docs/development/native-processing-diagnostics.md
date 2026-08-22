# Native Processing diagnostics

Use this page when the Processing screen stays on **Checking…**, reports that Scholion cannot inspect the computer, or behaves differently from the CLI.

The goal is to isolate the failing layer without changing user data.

## 1. Verify the Python application layer

From the repository root with Scholion's `.venv` active:

```bash
scholion doctor
scholion runner --json
scholion strategies --json
scholion models --json
```

If these fail, fix the Python environment or local prerequisite first. If they succeed, continue.

## 2. Test the exact Processing bridge methods

Machine readiness:

```bash
printf '%s\n' \
'{"protocol_version":1,"request_id":"debug-readiness","method":"processing.readiness","params":{"profile":"balanced"}}' \
| python -m scholion.desktop.bridge \
| python -m json.tool
```

Job history:

```bash
printf '%s\n' \
'{"protocol_version":1,"request_id":"debug-jobs","method":"processing.jobs.list","params":{}}' \
| python -m scholion.desktop.bridge \
| python -m json.tool
```

A healthy result has `"ok": true`. If both calls succeed but the desktop does not, the failure is above the Python bridge.

## 3. Check for an interpreter override

macOS/Linux:

```bash
echo "SCHOLION_PYTHON=${SCHOLION_PYTHON-<unset>}"
```

PowerShell:

```powershell
Get-Item Env:SCHOLION_PYTHON -ErrorAction SilentlyContinue
```

`SCHOLION_PYTHON` is an explicit developer override. If it points to an old environment, remove it for the current shell and retry.

macOS/Linux:

```bash
unset SCHOLION_PYTHON
```

PowerShell:

```powershell
Remove-Item Env:SCHOLION_PYTHON -ErrorAction SilentlyContinue
```

## 4. Verify native source prerequisites

From `frontend/`:

```bash
npm ci
npm run doctor:desktop
```

Then launch:

```bash
npm run tauri dev
```

On Linux/Wayland, if WebKitGTK terminates with `Error 71 (Protocol error) dispatching to Wayland display`, retry only that launch with:

```bash
WEBKIT_DISABLE_DMABUF_RENDERER=1 npm run tauri dev
```

Do not make the workaround a global environment setting.

## 5. Force the known repository interpreter for one launch

macOS/Linux:

```bash
SCHOLION_PYTHON="$(realpath ../.venv/bin/python)" npm run tauri dev
```

Linux/Wayland when the DMABUF workaround is also required:

```bash
WEBKIT_DISABLE_DMABUF_RENDERER=1 \
SCHOLION_PYTHON="$(realpath ../.venv/bin/python)" \
npm run tauri dev
```

PowerShell:

```powershell
$env:SCHOLION_PYTHON = (Resolve-Path ..\.venv\Scripts\python.exe)
npm.cmd run tauri dev
```

Unset the override after diagnosis if it is not intended to persist.

## 6. Read the Rust bridge diagnostics

Debug builds log a narrow lifecycle line for each Python bridge request. The log includes only:

- bridge module;
- protocol method;
- selected Python executable;
- child exit status; and
- stdout/stderr byte counts.

It deliberately does **not** log request params, evidence paths, transcript text, or model/source contents.

A successful request should show a `bridge start` line followed by `bridge finish`. If start appears without finish, the Python child did not return. If finish appears and a `bridge parse failure` follows, the child returned bytes that were not one valid protocol JSON response.

## 7. Processing-specific behavior

The Processing screen now treats machine readiness as the primary operation. Once readiness returns, the hardware/model UI renders without waiting for job history or remembered-folder discovery.

The machine check is bounded to 15 seconds. A timeout is surfaced as an explicit error instead of leaving the card on `Checking…` forever. Job-history and recording-discovery refreshes are independently bounded and cannot blank an otherwise healthy readiness result.

## 8. What browser E2E does not prove

`/?e2e=1` intentionally injects mock clients. That is appropriate for browser interaction and accessibility coverage, but it does not execute:

```text
React → Tauri invoke → Rust host → Python bridge
```

Release qualification therefore needs at least one real native transport smoke on every supported OS, plus representative CPU-only and CUDA-capable machines.

See [Project-local developer toolchain](project-local-toolchain.md) for environment setup and [Desktop source-build troubleshooting](troubleshooting.md) for broader OS-specific failures.
