from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from scholion.app import processing_center
from scholion.app.processing_center import ProcessingCenterService
from scholion.model_management.models import (
    ManagedModelManifest,
    ModelInventoryItem,
    ModelSpec,
)
from scholion.runner.models import ProcessingProfile


class _Health:
    def run(self) -> object:
        return SimpleNamespace(status=SimpleNamespace(value="healthy"), checks=())


class _Topology:
    def inspect(self) -> object:
        resources = SimpleNamespace(
            platform="TestOS",
            machine="test",
            processor_name="test cpu",
            effective_cpus=4,
            memory_total_bytes=8_000,
            memory_available_bytes=6_000,
            effective_memory_available_bytes=6_000,
            constraints=(),
        )
        return SimpleNamespace(resources=resources, accelerators=())


class _Policy:
    def plan(self, resources: object, profile: ProcessingProfile) -> object:
        return SimpleNamespace(
            profile=profile,
            provisional=False,
            cpu_threads=3,
            memory_budget_bytes=4_000,
            constraints=(),
        )


class _Planner:
    def assess_strategies(self, **_: object) -> tuple[dict[str, object], ...]:
        return (
            {
                "strategy": {
                    "strategy_id": "small-cpu-int8",
                    "model": "small",
                    "device": "cpu",
                    "compute_type": "int8",
                    "estimated_peak_device_memory_bytes": 0,
                    "model_cache_bytes": 100,
                },
                "effective_peak_memory_bytes": 1_000,
                "feasible": True,
                "rejection_reasons": [],
                "recommended": True,
            },
        )


class _Models:
    def __init__(self, *, enforced: bool, trusted: bool) -> None:
        self.enforce_policy_trust = enforced
        spec = ModelSpec(
            model_id="small",
            engine="faster-whisper",
            repository_id="Systran/faster-whisper-small",
            estimated_cache_bytes=100,
            quality_rank=1,
        )
        manifest = ManagedModelManifest(
            schema_version=1,
            model_id="small",
            engine="faster-whisper",
            repository_id="Systran/faster-whisper-small",
            requested_revision=None,
            resolved_revision="legacy-or-trusted",
            snapshot_path=Path("/models/small"),
            size_bytes=90,
            verification="local",
        )
        self.item = ModelInventoryItem(
            spec=spec,
            manifest=manifest,
            policy_trusted=trusted,
        )

    def inventory(self) -> tuple[ModelInventoryItem, ...]:
        return (self.item,)


class _Lifecycle:
    def list_records(self) -> tuple[object, ...]:
        return ()


def _service(models: _Models) -> ProcessingCenterService:
    return ProcessingCenterService(
        health_check=cast(Any, _Health()),
        topology_inspector=cast(Any, _Topology()),
        policy_planner=cast(Any, _Policy()),
        planner=cast(Any, _Planner()),
        model_manager=cast(Any, models),
        lifecycle_store=cast(Any, _Lifecycle()),
    )


@pytest.fixture(autouse=True)
def _speaker_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        processing_center,
        "diarization_runtime_status",
        lambda: SimpleNamespace(to_dict=lambda: {"available": False}),
    )


def test_unenforced_build_treats_locally_installed_model_as_ready() -> None:
    result = _service(_Models(enforced=False, trusted=False)).readiness(
        ProcessingProfile.BALANCED
    )

    assert result["model_policy_enforced"] is False
    assert result["model_policy_trust"] == {"small": False}
    assert result["recommended_model_installed"] is True
    assert result["recommended_model_ready"] is True


def test_enforced_build_keeps_untrusted_install_visible_but_not_ready() -> None:
    result = _service(_Models(enforced=True, trusted=False)).readiness(
        ProcessingProfile.BALANCED
    )

    assert result["model_policy_enforced"] is True
    assert result["model_policy_trust"] == {"small": False}
    assert result["recommended_model_installed"] is True
    assert result["recommended_model_ready"] is False


def test_enforced_build_reports_current_policy_trusted_model_ready() -> None:
    result = _service(_Models(enforced=True, trusted=True)).readiness(
        ProcessingProfile.BALANCED
    )

    assert result["model_policy_trust"] == {"small": True}
    assert result["recommended_model_ready"] is True
