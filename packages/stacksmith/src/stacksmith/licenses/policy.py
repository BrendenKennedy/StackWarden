"""License policy evaluation engine.

Runs post-build only — never during resolve.  This is advisory, not legal advice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from stacksmith.domain.enums import LicenseSeverity
from stacksmith.domain.models import ArtifactComponent, StackSpec
from stacksmith.licenses.spdx import LicenseInfo, SpdxMap

log = logging.getLogger(__name__)


@dataclass
class ComponentLicense:
    name: str
    version: str
    spdx: str
    severity: LicenseSeverity
    source: str  # "spdx_map" | "scanner" | "unknown"


def evaluate_components(
    stack: StackSpec,
    spdx_map: SpdxMap,
) -> list[ComponentLicense]:
    """Evaluate license status for all pip components in a stack."""
    results: list[ComponentLicense] = []

    for dep in stack.components.pip:
        info = spdx_map.lookup(dep.name)
        results.append(ComponentLicense(
            name=dep.name,
            version=dep.version,
            spdx=info.spdx,
            severity=info.severity,
            source="spdx_map" if info.spdx != "UNKNOWN" else "unknown",
        ))

    return results


def has_restricted(results: list[ComponentLicense]) -> bool:
    return any(r.severity == LicenseSeverity.RESTRICTED for r in results)


def has_review(results: list[ComponentLicense]) -> bool:
    return any(r.severity == LicenseSeverity.REVIEW for r in results)


def evaluate_sbom(
    sbom_path: "Path",
    spdx_map: SpdxMap | None = None,
) -> list[ComponentLicense]:
    """Cross-reference SBOM components against the license policy.

    Optional enhancement — does not fail if SBOM is absent.
    """
    from pathlib import Path
    from stacksmith.licenses.scanner import scan_sbom_licenses

    if spdx_map is None:
        spdx_map = SpdxMap.load()
    return scan_sbom_licenses(Path(sbom_path), spdx_map)


def to_artifact_components(
    results: list[ComponentLicense],
    artifact_id: str,
) -> list[ArtifactComponent]:
    """Convert license evaluation results to catalog-ready component records."""
    return [
        ArtifactComponent(
            artifact_id=artifact_id,
            type="pip",
            name=r.name,
            version=r.version,
            license_spdx=r.spdx,
            license_severity=r.severity,
        )
        for r in results
    ]
