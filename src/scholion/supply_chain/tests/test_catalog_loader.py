import json
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
