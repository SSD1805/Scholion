from __future__ import annotations

from scholion.media.tools import configure_frozen_media_tool_path

configure_frozen_media_tool_path()

from scholion.desktop.runtime import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
