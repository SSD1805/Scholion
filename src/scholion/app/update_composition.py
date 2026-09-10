from __future__ import annotations

from importlib.metadata import version

from scholion.app.app_container import AppContainer
from scholion.supply_chain.native_update_verifier import (
    discover_packaged_native_verifier,
)
from scholion.supply_chain.update_manifest import SignatureVerifier
from scholion.update_channel.service import UpdateChannelService, UpdateStateStore


def build_update_channel_service(
    container: AppContainer,
    *,
    verifier: SignatureVerifier | None = None,
) -> UpdateChannelService:
    """Compose update authority outside the desktop adapter.

    Explicitly injected verifiers remain available to tests. Otherwise only a frozen
    packaged runtime may discover the Tauri host that launched it. Source builds and
    packages without production native verification material remain fail-closed/off.
    """
    config = container.config()
    resolved_verifier = verifier or discover_packaged_native_verifier()
    return UpdateChannelService(
        current_version=version("scholion"),
        cache_dir=config.CACHE_DIR,
        state_store=UpdateStateStore(config.STATE_DIR, container.file_manager()),
        verifier=resolved_verifier,
    )
