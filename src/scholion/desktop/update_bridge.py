"""Narrow desktop bridge for application update trust and staging.

This bridge intentionally exposes no arbitrary URL, path, header, command, or installer
argument. The release endpoint and artifact selection remain application policy.
"""

from __future__ import annotations

from importlib.metadata import version
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scholion.app.app_container import AppContainer
from scholion.desktop.host_protocol import (
    failure_response,
    run_stdio_bridge,
    success_response,
)
from scholion.update_channel.service import (
    UpdateChannelError,
    UpdateChannelService,
    UpdateStateStore,
)


class _UpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: Literal[1]
    request_id: str = Field(min_length=1, max_length=128)
    method: Literal["updates.status", "updates.check", "updates.stage"]
    params: dict[str, object] = Field(default_factory=dict)


class _NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _service() -> UpdateChannelService:
    container = AppContainer()
    config = container.config()
    return UpdateChannelService(
        current_version=version("scholion"),
        cache_dir=config.CACHE_DIR,
        state_store=UpdateStateStore(config.STATE_DIR, container.file_manager()),
        # Production verification is deliberately not guessed here. A release build must
        # compose a reviewed native verifier and pinned public key before update network
        # activity can be enabled.
        verifier=None,
    )


def handle_request(
    payload: object,
    update_service: UpdateChannelService | None = None,
) -> dict[str, object]:
    try:
        request = _UpdateRequest.model_validate(payload)
        _NoParams.model_validate(request.params)
    except ValidationError:
        request_id = (
            payload.get("request_id", "unknown")
            if isinstance(payload, dict)
            else "unknown"
        )
        return failure_response(
            str(request_id)[:128],
            code="invalid_request",
            message="The update request was invalid",
        )

    service = update_service or _service()
    try:
        if request.method == "updates.status":
            result = service.status()
        elif request.method == "updates.check":
            result = service.check()
        else:
            result = service.stage()
    except UpdateChannelError:
        return failure_response(
            request.request_id,
            code="update_trust_failed",
            message="Scholion could not complete the trusted update request",
        )
    return success_response(request.request_id, result)


def main() -> int:
    return run_stdio_bridge(
        handle_request,
        oversized_message="The update request exceeded the safe size limit",
        invalid_json_message="The update request was not valid JSON",
    )


if __name__ == "__main__":
    raise SystemExit(main())
