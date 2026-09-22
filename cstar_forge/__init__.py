"""``cstar_forge`` has moved into C-Star.

Everything this package used to provide ships inside ``cstar-ocean`` (>= 0.15.0):
the forge application under ``cstar.applications.forge``, the catalog under
``cstar.catalog``, the wizard under ``cstar.wizard``, the ``cstar forge`` command
group, and ``cstar env register-kernel``. This distribution is a compatibility
shim: importing any ``cstar_forge`` module emits a :class:`DeprecationWarning` and
returns a proxy that forwards every attribute to the module that now holds the
code, so ``from cstar_forge.forge.forge_blueprint import ForgeBlueprint`` still
yields the real class. It declares no ``cstar.cli`` / ``cstar.applications`` entry
points -- the core ``cstar forge`` command is the only one.

Update your imports (see the module table in ``MODULE_ALIASES``) and remove the
shim with ``pip uninstall cstar-forge``.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import sys
import warnings
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType

_FORGE = "cstar.applications.forge"
_WIZARD = "cstar.wizard"

#: Old dotted module name -> the ``cstar`` module that now holds its contents.
MODULE_ALIASES: dict[str, str] = {
    "cstar_forge.cli": "cstar.cli.forge",
    "cstar_forge.config": f"{_FORGE}.config",
    "cstar_forge.domain_catalog": "cstar.catalog.domain_catalog",
    "cstar_forge.forge": _FORGE,
    "cstar_forge.forge._yaml_representers": f"{_FORGE}._yaml_representers",
    "cstar_forge.forge.app": f"{_FORGE}.app",
    "cstar_forge.forge.executor": f"{_FORGE}.executor",
    "cstar_forge.forge.forge_blueprint": f"{_FORGE}.blueprint",
    "cstar_forge.forge.forge_blueprint_engine": f"{_FORGE}.engine",
    "cstar_forge.forge.glorys_subchunk": f"{_FORGE}.glorys_subchunk",
    "cstar_forge.forge.host": f"{_FORGE}.host",
    "cstar_forge.forge.input_data": f"{_FORGE}.input_data",
    "cstar_forge.forge.namelist_model": f"{_FORGE}.namelist_model",
    "cstar_forge.forge.settings": f"{_FORGE}.settings",
    "cstar_forge.forge.source_datasets": f"{_FORGE}.source_datasets",
    "cstar_forge.forge.source_registry": f"{_FORGE}.source_registry",
    "cstar_forge.forge.user_files": f"{_FORGE}.user_files",
    "cstar_forge.forge.util": f"{_FORGE}.util",
    "cstar_forge.forge.xarray_lockfix": f"{_FORGE}.xarray_lockfix",
    "cstar_forge.forge_blueprint_resolve": f"{_FORGE}.resolve",
    "cstar_forge.forge_blueprint_wizard": f"{_WIZARD}.wizard",
    "cstar_forge.models": f"{_FORGE}.models",
    "cstar_forge.register_kernel": "cstar.cli.environment.register_kernel",
    "cstar_forge.run": f"{_FORGE}.runtime",
    "cstar_forge.ui": f"{_WIZARD}.ui",
    "cstar_forge.ui.branding": f"{_WIZARD}.ui.branding",
    "cstar_forge.ui.catalog_bar": f"{_WIZARD}.ui.catalog_bar",
    "cstar_forge.ui.components": f"{_WIZARD}.ui.components",
    "cstar_forge.ui.labels": f"{_WIZARD}.ui.labels",
    "cstar_forge.ui.shell": f"{_WIZARD}.ui.shell",
}

#: Names that were importable directly off ``cstar_forge`` (its old lazy exports):
#: name -> (module, attribute-or-None). ``None`` means the name *is* the module.
ATTRIBUTE_ALIASES: dict[str, tuple[str, str | None]] = {
    "config": (f"{_FORGE}.config", None),
    "models": (f"{_FORGE}.models", None),
    "settings": (f"{_FORGE}.settings", None),
    "source_datasets": (f"{_FORGE}.source_datasets", None),
    "DomainCatalog": ("cstar.catalog.domain_catalog", "DomainCatalog"),
    "LayeredCatalog": ("cstar.catalog.domain_catalog", "LayeredCatalog"),
    "build_catalog_stack": ("cstar.catalog.domain_catalog", "build_catalog_stack"),
    "default_catalog": ("cstar.catalog.domain_catalog", "default_catalog"),
    "default_catalog_stack": ("cstar.catalog.domain_catalog", "default_catalog_stack"),
    "user_catalog_root": ("cstar.catalog.domain_catalog", "user_catalog_root"),
    "ForgeExecutor": (f"{_FORGE}.executor", "ForgeExecutor"),
}

__all__ = ["ATTRIBUTE_ALIASES", "MODULE_ALIASES"]


def _warn_moved(old: str, new: str, *, stacklevel: int) -> None:
    warnings.warn(
        f"{old!r} has moved to {new!r}. The cstar-forge package is a compatibility "
        "shim over cstar-ocean and will be removed; update the import and "
        "`pip uninstall cstar-forge`.",
        DeprecationWarning,
        stacklevel=stacklevel,
    )


class _AliasLoader(importlib.abc.Loader):
    """Populate an alias module as a forwarding proxy for its ``cstar`` target."""

    def __init__(self, old: str, new: str) -> None:
        self.old = old
        self.new = new

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> None:
        return None  # default module creation

    def exec_module(self, module: ModuleType) -> None:
        target = importlib.import_module(self.new)
        _warn_moved(self.old, self.new, stacklevel=6)

        def __getattr__(name: str) -> Any:  # PEP 562 module getattr
            try:
                return getattr(target, name)
            except AttributeError:
                raise AttributeError(
                    f"module {self.old!r} (now {self.new!r}) has no attribute {name!r}"
                ) from None

        def __dir__() -> list[str]:
            return sorted(set(dir(target)) | set(vars(module)))

        public: Sequence[str] = getattr(target, "__all__", None) or [
            n for n in vars(target) if not n.startswith("_")
        ]
        module.__dict__.update(
            __doc__=target.__doc__,
            __all__=list(public),
            __getattr__=__getattr__,
            __dir__=__dir__,
            __cstar_target__=target,
        )


class _AliasFinder(importlib.abc.MetaPathFinder):
    """Resolve ``cstar_forge.*`` module names from :data:`MODULE_ALIASES`."""

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        new = MODULE_ALIASES.get(fullname)
        if new is None:
            return None
        is_package = any(k.startswith(fullname + ".") for k in MODULE_ALIASES)
        return importlib.machinery.ModuleSpec(
            fullname, _AliasLoader(fullname, new), is_package=is_package
        )


if not any(isinstance(f, _AliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

warnings.warn(
    "cstar_forge is a compatibility shim: C-Star Forge now ships inside cstar-ocean "
    "(cstar.applications.forge, cstar.catalog, cstar.wizard, `cstar forge`). "
    "Update your imports and `pip uninstall cstar-forge`.",
    DeprecationWarning,
    stacklevel=2,
)


def __getattr__(name: str) -> Any:
    """Resolve the old top-level lazy exports (PEP 562) with a deprecation warning."""
    try:
        module_name, attr = ATTRIBUTE_ALIASES[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    _warn_moved(
        f"cstar_forge.{name}",
        module_name if attr is None else f"{module_name}.{attr}",
        stacklevel=3,
    )
    module = importlib.import_module(module_name)
    return module if attr is None else getattr(module, attr)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(ATTRIBUTE_ALIASES))
