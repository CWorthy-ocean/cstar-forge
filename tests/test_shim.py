"""The cstar_forge shim: every old import path resolves, with a warning, to the
``cstar`` object that now holds the code, and the distribution registers no CLI or
application plugins (the core ``cstar forge`` command is the only one).
"""

import importlib
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _public_names(module) -> list[str]:
    return list(
        getattr(module, "__all__", None)
        or [n for n in vars(module) if not n.startswith("_")]
    )


def _aliases() -> dict[str, str]:
    with pytest.warns(DeprecationWarning):
        sys.modules.pop("cstar_forge", None)
        import cstar_forge
    return dict(cstar_forge.MODULE_ALIASES)


def test_top_level_import_warns_in_a_fresh_interpreter():
    proc = subprocess.run(
        [sys.executable, "-W", "error::DeprecationWarning", "-c", "import cstar_forge"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "compatibility shim" in proc.stderr


@pytest.mark.parametrize("old", sorted(_aliases()))
def test_module_alias_forwards_to_its_cstar_target(old):
    new = _aliases()[old]
    sys.modules.pop(old, None)
    with pytest.warns(DeprecationWarning, match="has moved to"):
        proxy = importlib.import_module(old)
    target = importlib.import_module(new)

    assert proxy.__cstar_target__ is target
    assert proxy.__all__ == _public_names(target)
    for name in _public_names(target):
        assert getattr(proxy, name) is getattr(target, name), f"{old}.{name}"
    with pytest.raises(AttributeError, match=new):
        proxy.definitely_not_a_real_name


def test_from_import_yields_the_real_class():
    sys.modules.pop("cstar_forge.forge.forge_blueprint", None)
    with pytest.warns(DeprecationWarning):
        from cstar_forge.forge.forge_blueprint import ForgeBlueprint
    from cstar.applications.forge.blueprint import ForgeBlueprint as Real

    assert ForgeBlueprint is Real


def test_package_alias_allows_submodule_import():
    for name in ("cstar_forge.forge", "cstar_forge.forge.executor"):
        sys.modules.pop(name, None)
    with pytest.warns(DeprecationWarning):
        import cstar_forge.forge.executor as executor
    from cstar.applications.forge.executor import ForgeExecutor

    assert executor.ForgeExecutor is ForgeExecutor
    assert hasattr(sys.modules["cstar_forge.forge"], "__path__")


def test_old_top_level_lazy_exports_still_resolve():
    sys.modules.pop("cstar_forge", None)
    with pytest.warns(DeprecationWarning):
        import cstar_forge
    from cstar.applications.forge import config
    from cstar.applications.forge.executor import ForgeExecutor
    from cstar.catalog.domain_catalog import DomainCatalog, user_catalog_root

    with pytest.warns(DeprecationWarning, match="cstar_forge.ForgeExecutor"):
        assert cstar_forge.ForgeExecutor is ForgeExecutor
    with pytest.warns(DeprecationWarning):
        assert cstar_forge.DomainCatalog is DomainCatalog
        assert cstar_forge.user_catalog_root is user_catalog_root
        assert cstar_forge.config is config
    with pytest.raises(AttributeError):
        cstar_forge.no_such_export
    assert "ForgeExecutor" in dir(cstar_forge)


def test_distribution_declares_no_cstar_plugins():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert "entry-points" not in pyproject["project"]
    assert "scripts" not in pyproject["project"]
    assert pyproject["project"]["dependencies"] == ["cstar-ocean>=0.15.0"]


def test_forge_cli_group_comes_from_cstar_core():
    from cstar.cli.forge import app as core_forge_app

    sys.modules.pop("cstar_forge.cli", None)
    with pytest.warns(DeprecationWarning):
        import cstar_forge.cli as shim_cli
    assert shim_cli.app is core_forge_app
