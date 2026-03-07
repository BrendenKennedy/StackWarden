from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "packages" / "stackwarden" / "src" / "stackwarden"

LEGACY_ALIAS_PATTERNS = (
    r"\bcreate_block\b",
    r"\bupdate_block\b",
    r"\bdry_run_block\b",
    r"\bprepare_block\b",
    r"\bbuild_block\b",
    r"\brun_block_create_wizard\b",
)

# Allow only explicit compatibility shims and exports.
ALLOWED_FILES = {
    "application/create_flows.py",
    "ui/wizard_entities/block.py",
    "ui/wizard_entities/__init__.py",
}


def test_legacy_block_alias_usage_is_contained() -> None:
    offenders: list[str] = []
    for path in PACKAGE_ROOT.glob("**/*.py"):
        rel = str(path.relative_to(PACKAGE_ROOT)).replace("\\", "/")
        source = path.read_text(encoding="utf-8")
        if any(re.search(pattern, source) for pattern in LEGACY_ALIAS_PATTERNS):
            if rel not in ALLOWED_FILES:
                offenders.append(rel)

    assert not offenders, (
        "Legacy block alias usage leaked beyond approved compatibility files: "
        + ", ".join(sorted(offenders))
    )
