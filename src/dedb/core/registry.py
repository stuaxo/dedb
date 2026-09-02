"""App and backend discovery: turn ``Settings.app_paths()`` into the
click commands (``get_apps``) and the registered backend instances
(``get_backends``) the CLI needs.

Depends on ``_registry`` (the bare dict) and ``settings``, never on
``backends`` - so ``backends.resolve()`` can import ``get_backends`` from
here at module level.
"""

from collections import OrderedDict
from importlib import import_module

from . import settings
from ._registry import _REGISTRY


def get_apps() -> dict[str, list]:
    """Resolve the installed apps into each one's contributed click commands,
    keyed by short app name (`dedb.dosbox` -> `dosbox`). `dedb.dedb` first,
    then Settings.apps in order."""
    return {
        path.split(".")[-1]: import_module(f"{path}.cli").commands
        for path in settings.get_settings().app_paths()
    }


def get_backends() -> "OrderedDict[str, object]":
    """Import each app's optional `backend` module (which self-registers via
    dedb.core.register_backend) and return the registry, keyed by scheme
    (== app short name) in Settings.apps order. Apps without a backend module
    (e.g. dedb.dosbox) are skipped."""
    app_paths = settings.get_settings().app_paths()
    for dotted_path in app_paths:
        try:
            import_module(f"{dotted_path}.backend")
        except ModuleNotFoundError as exc:
            # Only swallow "there is no such backend module"; a genuine
            # broken import *inside* an existing backend module must surface.
            if exc.name != f"{dotted_path}.backend":
                raise

    backends: OrderedDict[str, object] = OrderedDict()
    for dotted_path in app_paths:
        short_name = dotted_path.rsplit(".", 1)[-1]
        if short_name in _REGISTRY:
            backends[short_name] = _REGISTRY[short_name]
    return backends
