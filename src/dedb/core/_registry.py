"""The scheme -> backend-instance registry and its ``@register_backend``
decorator, split out on their own so ``dedb.core.backends`` (which defines
``BackendBase``) and ``dedb.core.registry`` (which populates and reads the
registry) can both depend on it without a cycle. Imports nothing.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .backends import BackendBase

# scheme -> backend instance. Populated by register_backend, which each
# dedb.<app>.backend module calls at import time (see dedb.core.get_backends).
_REGISTRY: "dict[str, BackendBase]" = {}


def register_backend(scheme: str):
    """Class decorator: instantiate the (zero-required-arg) backend class
    and store it under ``scheme``. Returns the class unchanged."""

    def decorator(cls: "type[BackendBase]") -> "type[BackendBase]":
        _REGISTRY[scheme] = cls()
        return cls

    return decorator
