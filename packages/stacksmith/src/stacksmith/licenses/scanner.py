"""Best-effort license scanner.

Runs post-build only.  Currently uses the SPDX map; future versions may
parse ``pip show`` output from the built image or query package indices.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from stacksmith.domain.models import StackSpec
from stacksmith.licenses.policy import ComponentLicense, evaluate_components
from stacksmith.licenses.spdx import SpdxMap

log = logging.getLogger(__name__)


def scan_stack_licenses(
    stack: StackSpec,
    spdx_map: SpdxMap | None = None,
) -> list[ComponentLicense]:
    """Scan a stack's pip dependencies for license information.

    This is a best-effort scan using the SPDX mapping file.
    """
    if spdx_map is None:
        spdx_map = SpdxMap.load()

    results = evaluate_components(stack, spdx_map)

    known = sum(1 for r in results if r.source != "unknown")
    total = len(results)
    if total:
        log.info("License scan: %d/%d packages mapped", known, total)

    return results


def scan_sbom_licenses(
    sbom_path: Path,
    spdx_map: SpdxMap | None = None,
) -> list[ComponentLicense]:
    """Parse component licenses from an SBOM file (SPDX-JSON or CycloneDX-JSON)."""
    if spdx_map is None:
        spdx_map = SpdxMap.load()

    try:
        data = json.loads(sbom_path.read_text())
    except (json.JSONDecodeError, FileNotFoundError) as exc:
        log.warning("Failed to parse SBOM at %s: %s", sbom_path, exc)
        return []

    if "packages" in data:
        return _parse_spdx_json(data, spdx_map)
    if "components" in data:
        return _parse_cyclonedx_json(data, spdx_map)

    log.warning("Unrecognized SBOM format in %s", sbom_path)
    return []


def _parse_spdx_json(data: dict, spdx_map: SpdxMap) -> list[ComponentLicense]:
    results: list[ComponentLicense] = []
    for pkg in data.get("packages", []):
        name = pkg.get("name", "")
        version = pkg.get("versionInfo", "")
        spdx_id = pkg.get("licenseDeclared", "NOASSERTION")
        info = spdx_map.lookup(name)
        results.append(ComponentLicense(
            name=name,
            version=version,
            spdx=spdx_id if spdx_id != "NOASSERTION" else info.spdx,
            severity=info.severity,
            source="sbom",
        ))
    return results


def _parse_cyclonedx_json(data: dict, spdx_map: SpdxMap) -> list[ComponentLicense]:
    results: list[ComponentLicense] = []
    for comp in data.get("components", []):
        name = comp.get("name", "")
        version = comp.get("version", "")
        licenses = comp.get("licenses", [])
        spdx_id = ""
        if licenses:
            lic = licenses[0]
            if "license" in lic:
                spdx_id = lic["license"].get("id", "")
        info = spdx_map.lookup(name)
        results.append(ComponentLicense(
            name=name,
            version=version,
            spdx=spdx_id or info.spdx,
            severity=info.severity,
            source="sbom",
        ))
    return results
