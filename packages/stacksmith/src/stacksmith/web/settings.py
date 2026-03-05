"""Web UI settings, loaded from environment variables."""

from __future__ import annotations

import logging

from pydantic_settings import BaseSettings

log = logging.getLogger(__name__)


class WebSettings(BaseSettings):
    model_config = {"env_prefix": "STACKSMITH_WEB_"}

    host: str = "127.0.0.1"
    port: int = 8765
    token: str | None = None
    admin_token: str | None = None
    dev: bool = False
    blocks_first_enabled: bool = True
    # Deprecated: kept for backward compatibility until removal.
    blocks_first_dual_validate: bool = False

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        if self.blocks_first_dual_validate:
            log.warning(
                "STACKSMITH_WEB_BLOCKS_FIRST_DUAL_VALIDATE is deprecated and has no effect."
            )
