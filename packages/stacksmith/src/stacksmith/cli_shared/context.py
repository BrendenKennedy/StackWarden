"""CLI context bootstrap helpers."""

from __future__ import annotations

from pathlib import Path

from stacksmith.config import AppConfig
from stacksmith.logging import setup_logging


def setup_cli(verbose: bool = False) -> None:
    cfg = AppConfig.load()
    log_dir = Path(cfg.log_dir).expanduser() if cfg.log_dir else None
    setup_logging(verbose=verbose, log_dir=log_dir)
