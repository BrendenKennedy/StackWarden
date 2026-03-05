"""SPDX license mapping loader.

Loads ``licenses/spdx_map.yaml`` and provides lookup by package name.
Unknown packages default to severity=review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from stacksmith.domain.enums import LicenseSeverity

log = logging.getLogger(__name__)

_DEFAULT_MAP_PATH = Path(__file__).resolve().parent / "spdx_map.yaml"


@dataclass(frozen=True)
class LicenseInfo:
    spdx: str
    severity: LicenseSeverity


_UNKNOWN = LicenseInfo(spdx="UNKNOWN", severity=LicenseSeverity.REVIEW)


class SpdxMap:
    """In-memory mapping from package name to license info."""

    def __init__(self, data: dict[str, dict[str, str]] | None = None) -> None:
        self._map: dict[str, LicenseInfo] = {}
        if data:
            for pkg, info in data.items():
                try:
                    self._map[pkg.lower()] = LicenseInfo(
                        spdx=info.get("spdx", "UNKNOWN"),
                        severity=LicenseSeverity(info.get("severity", "review")),
                    )
                except ValueError:
                    log.warning("Invalid severity for package '%s', defaulting to review", pkg)
                    self._map[pkg.lower()] = LicenseInfo(
                        spdx=info.get("spdx", "UNKNOWN"),
                        severity=LicenseSeverity.REVIEW,
                    )

    @classmethod
    def load(cls, path: Path | None = None) -> SpdxMap:
        p = path or _DEFAULT_MAP_PATH
        if not p.exists():
            log.warning("SPDX map not found at %s, using empty map", p)
            return cls()
        with open(p) as f:
            data = yaml.safe_load(f) or {}
        return cls(data)

    def lookup(self, package_name: str) -> LicenseInfo:
        return self._map.get(package_name.lower(), _UNKNOWN)

    def __len__(self) -> int:
        return len(self._map)
