from typing import Any, cast

from scholion.desktop.update_bridge import handle_request


class _Service:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail = False

    def _result(self, method: str) -> dict[str, object]:
        self.calls.append(method)
        if self.fail:
            from scholion.update_channel.service import UpdateChannelError

            raise UpdateChannelError("private transport detail")
        return {
            "enabled": method != "status",
            "state": "off" if method == "status" else method,
            "current_version": "0.1.0",
        }

    def status(self) -> dict[str, object]:
        return self._result("status")

    def check(self) -> dict[str, object]:
        return self._result("check")

    def stage(self) -> dict[str, object]:
        return self._result("stage")


def _request(
    method: str, *, params: dict[str, object] | None = None
) -> dict[str, object]:
    return {
        "protocol_version": 1,
        "request_id": "update-request",
        "method": method,
        "params": params or {},
    }


def test_update_bridge_exposes_only_closed_no_param_methods() -> None:
    service = _Service()

    status = handle_request(_request("updates.status"), cast(Any, service))
    check = handle_request(_request("updates.check"), cast(Any, service))
    stage = handle_request(_request("updates.stage"), cast(Any, service))

    assert status["ok"] is True
    assert check["ok"] is True
    assert stage["ok"] is True
    assert service.calls == ["status", "check", "stage"]


def test_update_bridge_rejects_urls_paths_and_unknown_methods() -> None:
    service = _Service()

    with_url = handle_request(
        _request("updates.check", params={"url": "https://evil.invalid"}),
        cast(Any, service),
    )
    unknown = handle_request(
        _request("updates.install"),
        cast(Any, service),
    )

    assert with_url["ok"] is False
    assert unknown["ok"] is False
    assert service.calls == []


def test_update_failures_cross_as_one_bounded_public_error() -> None:
    service = _Service()
    service.fail = True

    response = handle_request(_request("updates.check"), cast(Any, service))

    assert response["ok"] is False
    assert response["error"] == {
        "code": "update_trust_failed",
        "message": "Scholion could not complete the trusted update request",
    }
    assert "private transport detail" not in str(response)
