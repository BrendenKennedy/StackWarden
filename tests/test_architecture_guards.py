from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "packages" / "stackwarden" / "src" / "stackwarden"


def _imports_for(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def test_routes_do_not_import_route_internals() -> None:
    routes_dir = PACKAGE_ROOT / "web" / "routes"
    for path in routes_dir.glob("*.py"):
        if path.name == "create.py":
            continue
        imports = _imports_for(path)
        assert "stackwarden.web.routes.create" not in imports, f"{path} imports route internals"


def test_adapters_are_not_cross_layer_coupled() -> None:
    cli_imports = _imports_for(PACKAGE_ROOT / "cli.py")
    assert not any(mod.startswith("stackwarden.web.routes") for mod in cli_imports)

    routes_dir = PACKAGE_ROOT / "web" / "routes"
    for path in routes_dir.glob("*.py"):
        imports = _imports_for(path)
        assert not any(mod.startswith("stackwarden.cli") for mod in imports), f"{path} imports cli"


def test_application_layer_not_coupled_to_web_utilities() -> None:
    app_dir = PACKAGE_ROOT / "application"
    for path in app_dir.glob("*.py"):
        imports = _imports_for(path)
        if path.name in {"spec_validation.py", "serialization.py"}:
            # Transitional adapter shims isolate existing behavior while
            # create/update flows migrate off web utility internals.
            continue
        assert not any(mod.startswith("stackwarden.web.util") for mod in imports), (
            f"{path} imports web utilities directly"
        )


def test_only_allowlisted_modules_import_web_schemas() -> None:
    """Keep transport DTO imports from spreading across internal layers."""
    allowlist: set[str] = set()

    for path in PACKAGE_ROOT.glob("**/*.py"):
        rel = str(path.relative_to(PACKAGE_ROOT)).replace("\\", "/")
        if rel.startswith("web/"):
            continue
        imports = _imports_for(path)
        if "stackwarden.web.schemas" not in imports:
            continue
        assert rel in allowlist, f"{path} imports stackwarden.web.schemas but is not allowlisted"
