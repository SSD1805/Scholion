# Project-local developer toolchain

Scholion source development deliberately separates **tools that build/manage the repository** from **libraries that belong to the application**.

The supported project-local layout is:

```text
Scholion/
├── .tools/
│   └── uv/              disposable project-local tool bootstrap
├── .venv/               Scholion's locked Python environment
├── frontend/
│   └── node_modules/    locked JavaScript dependencies
├── uv.lock
├── pyproject.toml
└── frontend/package-lock.json
```

`.tools/` and `.venv/` are disposable developer state and are ignored by Git. They are not user evidence and are not application data.

## Why `uv` is outside `.venv`

`uv` manages `.venv`. If `uv` is installed *inside* the environment it manages, deleting a stale `.venv` also deletes the tool needed to recreate it:

```text
uv manages .venv
     ↓
uv lives inside .venv
     ↓
delete stale .venv
     ↓
uv is gone
     ↓
need uv to recreate .venv
```

Keeping the bootstrap tool in `.tools/uv` avoids that cycle while still preventing a system-wide install.

A shared user-local `uv` installation is also technically valid because each repository still has its own lockfile and `.venv`. Scholion nevertheless documents the project-local path because it gives contributors a stricter tool-version boundary and avoids relying on shell PATH state.

## Bootstrap on Linux or macOS

Use Python 3.12 to run the repository bootstrap from the repository root:

```bash
python3.12 scripts/bootstrap_python.py
```

If `python` already resolves to Python 3.12:

```bash
python scripts/bootstrap_python.py
```

The script:

1. creates `.tools/uv` with the invoking Python 3.12 interpreter;
2. installs the repository-pinned `uv` version into that tool environment;
3. runs `.tools/uv/bin/uv sync --locked --extra transcription`;
4. verifies that `.venv` can import Scholion; and
5. leaves system package-manager state untouched.

Activate the resulting application environment with:

```bash
source .venv/bin/activate
```

The prompt may display `(scholion)` rather than `(.venv)`. The prompt text is a friendly environment name. The authoritative check is:

```bash
which python
```

which should resolve to the repository's `.venv/bin/python`.

## Bootstrap on Windows PowerShell

From the repository root:

```powershell
py -3.12 scripts\bootstrap_python.py
```

Then activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

If local PowerShell policy prevents activation, activation is optional. Run the environment explicitly instead:

```powershell
.\.venv\Scripts\python.exe -m scholion --help
```

The bootstrap itself does not change PowerShell execution policy.

## Lockfile ownership

Different ecosystems have different project-local dependency graphs:

| Layer | Tool | Repository authority | Installed state |
|---|---|---|---|
| Python application | project-local `uv` | `pyproject.toml` + `uv.lock` | `.venv/` |
| JavaScript desktop | npm | `frontend/package.json` + `frontend/package-lock.json` | `frontend/node_modules/` |
| Rust/Tauri host | Cargo | `frontend/src-tauri/Cargo.toml` + `Cargo.lock` | Cargo user cache + `frontend/src-tauri/target/` |

Do not delete or regenerate a lockfile merely to make a version conflict disappear. Lockfiles are part of the source-build contract. Disposable installed state can be rebuilt from them.

## Recovering from a stale or deleted virtual environment

Symptoms can include:

```text
(.venv) ...
bash: /path/to/Scholion/.venv/bin/uv: No such file or directory
```

or:

```text
bash: uv: command not found
```

First leave any stale activation and clear Bash's executable-location cache:

```bash
deactivate 2>/dev/null || true
hash -r
type -a uv || true
```

A surviving interpreter under `~/.local/share/uv/python/...` does not imply that the `uv` executable still exists. `uv` may previously have downloaded that Python runtime while its own executable was later removed.

For Scholion, recover without a system-wide install:

```bash
python3.12 scripts/bootstrap_python.py
source .venv/bin/activate
```

Then verify:

```bash
python --version
which python
scholion doctor
scholion runner --json
scholion strategies --json
scholion models --json
```

## Why `.venv/bin/pip` may be absent

A uv-managed environment does not require `pip` inside the application environment. Absence of `.venv/bin/pip` alone is not evidence that `.venv` is broken.

The separate `.tools/uv` bootstrap environment *does* use its own pip to install the pinned `uv` tool. That pip belongs to the disposable tool bootstrap, not to Scholion's runtime dependency graph.

## Do not use system-wide installation as the default recovery step

Do not reflexively run `sudo pacman -S uv`, `sudo apt install ...`, or an equivalent system-level package command merely because `uv` is missing. A contributor may intentionally keep development tools isolated from operating-system package state.

Likewise, do not present `curl ... | sh` as an unexplained incantation. A remote installer script is code fetched over HTTPS and immediately executed. If a contributor chooses a user-local upstream installer instead of Scholion's project-local bootstrap, they should understand and inspect that trust boundary.

## After pulling new source

A Git pull updates the repository. It does not automatically synchronize every installed dependency tree. When lockfiles changed, rebuild the relevant disposable state:

```bash
python3.12 scripts/bootstrap_python.py
cd frontend
npm ci
npm run doctor:desktop
```

For the native host, `cargo check --locked --manifest-path frontend/src-tauri/Cargo.toml` is the authoritative compile check.

See [Desktop source-build troubleshooting](troubleshooting.md) for platform-specific failures and [Desktop development prerequisites](desktop-development.md) for the complete native stack.
