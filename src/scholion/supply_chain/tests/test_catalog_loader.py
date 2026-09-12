import json
import sys
from pathlib import Path

import pytest

from scholion.supply_chain import catalog_loader


def _catalog_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "models": [
            {
                "model_id": "tiny",
                "engine": "faster-whisper",
                "repository_id": "Systran/faster-whisper-tiny",
                "revision": "a" * 40,
                "source_url": "https://huggingface.co/Systran/faster-whisper-tiny",
                "license_id": "MIT",
                "license_url": "https://opensource.org/license/mit",
                "files": [
                    {
                        "path": "model.bin",
                        "size_bytes": 3,
                        "sha256": "b" * 64,
                    }
                ],
            }
        ],
    }


def test_parse_model_trust_catalog_accepts_strict_utf8_json() -> None:
    catalog = catalog_loader.parse_model_trust_catalog(
        json.dumps(_catalog_document()).encode("utf-8")
    )

    assert catalog.schema_version == 1
    assert catalog.require("tiny").revision == "a" * 40


@pytest.mark.parametrize(
    "payload, message",
    [
        (b"\xff", "valid UTF-8 JSON"),
        (b"{", "valid UTF-8 JSON"),
        (b"[]", "JSON object"),
    ],
)
def test_parse_model_trust_catalog_rejects_invalid_documents(
    payload: bytes, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        catalog_loader.parse_model_trust_catalog(payload)


def test_load_model_trust_catalog_reads_explicit_file(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(_catalog_document()), encoding="utf-8")

    catalog = catalog_loader.load_model_trust_catalog(path)

    assert catalog.require("tiny").repository_id == "Systran/faster-whisper-tiny"


def test_load_model_trust_catalog_hides_local_path_on_failure(tmp_path: Path) -> None:
    path = tmp_path / "private-secret-directory" / "missing.json"

    with pytest.raises(ValueError, match="catalog is unavailable") as caught:
        catalog_loader.load_model_trust_catalog(path)

    assert "private-secret-directory" not in str(caught.value)


def test_bundled_loader_returns_none_when_build_has_no_catalog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(catalog_loader, "files", lambda _package: tmp_path)

    assert catalog_loader.load_bundled_model_trust_catalog() is None


def test_bundled_loader_parses_packaged_catalog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "model-trust.json").write_text(
        json.dumps(_catalog_document()), encoding="utf-8"
    )
    monkeypatch.setattr(catalog_loader, "files", lambda _package: tmp_path)

    catalog = catalog_loader.load_bundled_model_trust_catalog()

    assert catalog is not None
    assert catalog.require("tiny").model_id == "tiny"


def test_frozen_loader_uses_only_meipass_catalog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frozen_root = tmp_path / "_internal"
    catalog_path = frozen_root / "scholion" / "supply_chain" / "model-trust.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text(json.dumps(_catalog_document()), encoding="utf-8")
    monkeypatch.setattr(catalog_loader.sys, "frozen", True, raising=False)
    monkeypatch.setattr(catalog_loader.sys, "_MEIPASS", str(frozen_root), raising=False)
    monkeypatch.setattr(
        catalog_loader,
        "files",
        lambda _package: (_ for _ in ()).throw(
            AssertionError("resource fallback used")
        ),
    )

    catalog = catalog_loader.load_bundled_model_trust_catalog()

    assert catalog is not None
    assert catalog.require("tiny").revision == "a" * 40


def test_frozen_loader_does_not_fallback_to_source_resources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frozen_root = tmp_path / "_internal"
    frozen_root.mkdir()
    source_resources = tmp_path / "source-resources"
    source_resources.mkdir()
    (source_resources / "model-trust.json").write_text(
        json.dumps(_catalog_document()), encoding="utf-8"
    )
    monkeypatch.setattr(catalog_loader.sys, "frozen", True, raising=False)
    monkeypatch.setattr(catalog_loader.sys, "_MEIPASS", str(frozen_root), raising=False)
    monkeypatch.setattr(catalog_loader, "files", lambda _package: source_resources)

    assert catalog_loader.load_bundled_model_trust_catalog() is None


def test_frozen_loader_returns_none_without_valid_meipass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(catalog_loader.sys, "frozen", True, raising=False)
    monkeypatch.delattr(catalog_loader.sys, "_MEIPASS", raising=False)

    assert catalog_loader.load_bundled_model_trust_catalog() is None


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlink creation is not reliable in CI"
)
def test_frozen_loader_rejects_catalog_symlink_escape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frozen_root = tmp_path / "_internal"
    catalog_path = frozen_root / "scholion" / "supply_chain" / "model-trust.json"
    catalog_path.parent.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(_catalog_document()), encoding="utf-8")
    catalog_path.symlink_to(outside)
    monkeypatch.setattr(catalog_loader.sys, "frozen", True, raising=False)
    monkeypatch.setattr(catalog_loader.sys, "_MEIPASS", str(frozen_root), raising=False)

    assert catalog_loader.load_bundled_model_trust_catalog() is None
