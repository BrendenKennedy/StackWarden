"""Logging configuration for Stacksmith.

Uses rich for console output. Supports verbose mode and per-build log files.
"""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from stacksmith.paths import get_logs_root
_console = Console(stderr=True)


def setup_logging(*, verbose: bool = False, log_dir: Path | None = None) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = RichHandler(
        console=_console,
        show_path=False,
        rich_tracebacks=True,
        markup=True,
    )
    handlers: list[logging.Handler] = [handler]

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_path = log_dir / "stacksmith.log"
        fh = logging.FileHandler(file_path)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handlers.append(fh)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
        force=True,
    )


def get_build_log_path(artifact_id: str, log_dir: Path | None = None) -> Path:
    d = log_dir or get_logs_root()
    d.mkdir(parents=True, exist_ok=True)
    safe_name = artifact_id.replace("/", "_").replace("..", "_")
    result = (d / f"{safe_name}.log").resolve()
    if not result.is_relative_to(d.resolve()):
        raise ValueError(f"Invalid artifact_id for log path: {artifact_id!r}")
    return result


def add_file_handler(logger: logging.Logger, path: Path) -> logging.FileHandler:
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(fh)
    return fh


def get_console() -> Console:
    return _console
