"""Game references: the ``<scheme>:<id>`` / ``<scheme>://<id>`` spellings
and the resolved :class:`Target`. Imports nothing from dedb - every other
core module can depend on this one freely.
"""

from dataclasses import dataclass


def short_target(scheme: str, identifier: str) -> str:
    """``<scheme>:<identifier>`` - the compact game reference."""
    return f"{scheme}:{identifier}"


def long_target(scheme: str, identifier: str) -> str:
    """``<scheme>://<identifier>`` - the URL-style game reference."""
    return f"{scheme}://{identifier}"


@dataclass(frozen=True)
class Target:
    """A resolved game reference: which backend, which game, and (GOG
    only) which launch profile. ``raw`` is the string the user typed."""

    scheme: str
    identifier: str
    profile: "str | None"
    raw: str

    @property
    def url(self) -> str:
        base = long_target(self.scheme, self.identifier)
        return f"{base}?profile={self.profile}" if self.profile else base
