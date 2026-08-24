from scholion.app.app_container import AppContainer
from scholion.app.update_composition import build_update_channel_service


def test_source_update_composition_is_fail_closed_without_verifier() -> None:
    service = build_update_channel_service(AppContainer())

    status = service.status()

    assert status["enabled"] is False
    assert status["state"] == "off"
