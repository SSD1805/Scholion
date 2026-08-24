from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from scholion.supply_chain.model_trust import ModelTrustCatalog

_BUNDLED_MODEL_TRUST_CATALOG = "model-trust.json"


def parse_model_trust_catalog(document_bytes: bytes) -> ModelTrustCatalog:
    """Parse one strict UTF-8 curated model-trust catalog."""
    try:
        document = json.loads(document_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("model trust catalog must be valid UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("model trust catalog must be a JSON object")
    return ModelTrustCatalog.from_dict(document)


def load_model_trust_catalog(path: Path) -> ModelTrustCatalog:
    """Load an explicitly selected catalog without leaking its local path on failure."""
    try:
        payload = path.expanduser().resolve(strict=False).read_bytes()
    except OSError as exc:
        raise ValueError("model trust catalog is unavailable") from exc
    return parse_model_trust_catalog(payload)


def load_bundled_model_trust_catalog() -> ModelTrustCatalog | None:
    """Load the catalog shipped inside Scholion, if this build intentionally includes one."""
    candidate = files("scholion.supply_chain").joinpath(_BUNDLED_MODEL_TRUST_CATALOG)
    if not candidate.is_file():
        return None
    try:
        payload = candidate.read_bytes()
    except OSError as exc:
        raise ValueError("bundled model trust catalog is unavailable") from exc
    return parse_model_trust_catalog(payload)
