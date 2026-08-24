from __future__ import annotations

from importlib.metadata import version

from scholion.app.app_container import AppContainer
from scholion.supply_chain.update_manifest import SignatureVerifier
from scholion.update_channel.service import UpdateChannelService, UpdateStateStore


def build_update_channel_service(
    container: AppContainer,
    *,
    verifier: SignatureVerifier | None = None,
) -> UpdateChannelService:
    """Compose the update channel outside the desktop adapter.

    Production packaging owns the verifier/public-key input. Source builds deliberately
    pass no verifier, which keeps update networking fail-closed and off.
    """
    config = container.config()
    return UpdateChannelService(
        current_version=version("scholion"),
        cache_dir=config.CACHE_DIR,
        state_store=UpdateStateStore(config.STATE_DIR, container.file_manager()),
        verifier=verifier,
    )
