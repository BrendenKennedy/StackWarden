"""Console entrypoint for Stacksmith web with dependency guard."""

from __future__ import annotations

import sys


def main() -> None:
    try:
        from stacksmith.web.app import main as web_main
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", "unknown")
        raise SystemExit(
            "The web UI dependencies are not installed "
            f"(missing: {missing}). Install with: pip install 'stacksmith[web]'"
        ) from exc
    web_main()
