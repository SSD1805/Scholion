from __future__ import annotations

from pathlib import Path

from scripts import prepare_dev_environment as prepare


def test_project_uv_path_stays_inside_repository_tools(tmp_path: Path) -> None:
    uv = prepare._project_uv(tmp_path)

    assert uv.is_relative_to(tmp_path / ".tools" / "uv")
    assert uv.name in {"uv", "uv.exe"}


def test_existing_project_uv_never_requires_path_lookup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    uv = prepare._project_uv(tmp_path)
    uv.parent.mkdir(parents=True)
    uv.touch()

    def unexpected_run(*args: str, cwd: Path) -> None:
        raise AssertionError("existing project-local uv should not bootstrap")

    monkeypatch.setattr(prepare, "_run", unexpected_run)

    assert prepare._ensure_project_uv(tmp_path) == uv


def test_missing_project_uv_bootstraps_repository_owned_tool(
    tmp_path: Path,
    monkeypatch,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    bootstrap = scripts / "bootstrap_python.py"
    bootstrap.write_text("# test bootstrap\n", encoding="utf-8")
    uv = prepare._project_uv(tmp_path)
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_run(*args: str, cwd: Path) -> None:
        calls.append((args, cwd))
        uv.parent.mkdir(parents=True, exist_ok=True)
        uv.touch()

    monkeypatch.setattr(prepare, "_run", fake_run)

    assert prepare._ensure_project_uv(tmp_path) == uv
    assert calls == [((prepare.sys.executable, str(bootstrap)), tmp_path)]
