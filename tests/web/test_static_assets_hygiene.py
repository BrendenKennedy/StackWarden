from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT / "packages" / "stackwarden" / "src" / "stackwarden" / "web" / "static"
ASSETS_DIR = STATIC_DIR / "assets"
INDEX_HTML = STATIC_DIR / "index.html"


def test_index_html_referenced_index_assets_exist() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    referenced = set(re.findall(r"/assets/(index-[^\"']+\.(?:js|css))", html))

    assert referenced, "No index-* assets referenced by static index.html."
    missing = [name for name in sorted(referenced) if not (ASSETS_DIR / name).exists()]
    assert not missing, f"index.html references missing assets: {missing}"


def test_no_stale_index_assets_left_in_static_assets() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    referenced = set(re.findall(r"/assets/(index-[^\"']+\.(?:js|css))", html))
    packaged = {path.name for path in ASSETS_DIR.glob("index-*.*") if path.suffix in {".js", ".css"}}

    stale = sorted(packaged - referenced)
    assert not stale, (
        "Stale hashed index assets found in packaged static directory. "
        f"Remove stale files so only currently referenced index assets remain: {stale}"
    )
