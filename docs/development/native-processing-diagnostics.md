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

In a debug source build, Rust automatically prefers the repository `.venv` interpreter when `../.venv/bin/python` (or the Windows equivalent) exists. An explicit `SCHOLION_PYTHON` override is normally unnecessary.

## 5. Force the known repository interpreter for one launch

Only use an override when diagnosing interpreter selection.

On macOS/Linux, preserve the `.venv/bin/python` path itself:

```bash
SCHOLION_PYTHON="../.venv/bin/python" npm run tauri dev
```

Linux/Wayland when the DMABUF workaround is also required:

```bash
WEBKIT_DISABLE_DMABUF_RENDERER=1 \
SCHOLION_PYTHON="../.venv/bin/python" \
npm run tauri dev
```

If an absolute path is useful, construct it without resolving the final `python` symlink:

```bash
SCHOLION_PYTHON="$(pwd)/../.venv/bin/python" npm run tauri dev
```

**Do not run `realpath` or `readlink -f` on `.venv/bin/python`.** On Unix, virtual-environment launchers are commonly symlinks to a base interpreter. Resolving that symlink first can turn the command into the underlying uv/Python runtime path, bypass the virtual environment's `pyvenv.cfg`, and make `python -m scholion...` fail with `ModuleNotFoundError` even though `.venv` itself is healthy.

PowerShell can use the repository path directly:

```powershell
$env:SCHOLION_PYTHON = "..\.venv\Scripts\python.exe"
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

If every bridge exits immediately with status 1, `stdout_bytes=0`, and a small nonzero stderr after an explicit `SCHOLION_PYTHON` override, first run:

```bash
"$SCHOLION_PYTHON" -c "import sys, scholion; print(sys.executable); print(sys.prefix); print(scholion.__file__)"
```

An import failure means the selected executable is not entering Scholion's application environment. Remove the override and let the debug host select the repository `.venv`, or point the override at `.venv/bin/python` without resolving symlinks.

## 7. Processing-specific behavior

The Processing screen now treats machine readiness as the primary operation. Once readiness returns, the hardware/model UI renders without waiting for job history or remembered-folder discovery.

The machine check is bounded to 15 seconds. A timeout is surfaced as an explicit error instead of leaving the card on `Checking…` forever. Job-history and recording-discovery refreshes are independently bounded and cannot blank an otherwise healthy readiness result.

Repeated success/failure alternation for identical native calls can indicate overlapping one-shot bridge processes contending for the same local database-backed state. Native source builds serialize those bridge processes so one control-plane request crosses the database boundary at a time. Long-running transcription/model workers use their separate task process path.

## 8. What browser E2E does not prove

`/?e2e=1` intentionally injects mock clients. That is appropriate for browser interaction and accessibility coverage, but it does not execute:

```text
React → Tauri invoke → Rust host → Python bridge
```

Release qualification therefore needs at least one real native transport smoke on every supported OS, plus representative CPU-only and CUDA-capable machines.

See [Project-local developer toolchain](project-local-toolchain.md) for environment setup and [Desktop source-build troubleshooting](troubleshooting.md) for broader OS-specific failures.
