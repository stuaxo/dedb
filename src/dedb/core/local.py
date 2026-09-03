"""The model for a program that has been downloaded and extracted onto
disk - the local end of the pipeline that starts at ``GOGGame`` /
``ArchiveItemInfo``.

Every backend assembles a :class:`LocalGame` for one of its downloads
(``BackendBase.local_game``); the CLI (``dedb ls``) and any future
consumer read it instead of poking at the download directory directly.

Pure core: this module imports only the stdlib, pydantic and
``dedb.core.refs`` - never a backend model - so ``core`` keeps depending
only on itself.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .refs import long_target, short_target


class LaunchProfile(BaseModel):
    """One way to start a local game - the backend-agnostic view of a GOG
    launch profile (``dedb run ... --profile <slug>``).

    GOG games have one per conf-referencing playTask (``Play``,
    ``Multiplayer Host``, ...); archive.org items and profile-less GOG
    games have a single default profile. This is display / validation
    metadata only - the actual conf files and working directory are still
    resolved from the extracted files at launch time (see
    ``dedb.gog.profiles``).
    """

    model_config = ConfigDict(frozen=True)

    # None => the unsuffixed dosemu.conf / userhook.bat pair (the default
    # profile); otherwise the GogLayout slug (dosemu_<slug>.conf), which
    # is also what `--profile <slug>` accepts.
    slug: str | None = None
    name: str = "default"
    is_default: bool = False


class GameDescription(BaseModel):
    """The fields that describe one game - identity plus what little we
    record about it. Shared by the persisted ``metadata.json`` envelope
    (:class:`dedb.core.metadata_file.GameMetadataFile`) and the in-memory
    :class:`LocalGame` the CLI reads; each adds its own extra fields."""

    scheme: str
    identifier: str
    title: str | None = None
    year: str | None = None
    # "dosbox" / "scummvm" / "none" / ... - None when it was never recorded.
    classification: str | None = None
    downloaded_at: datetime | None = None
    launch_profiles: list[LaunchProfile] = []


class LocalGame(GameDescription):
    """A downloaded, extracted program: its identity, what little we know
    about it, and how it can be launched."""

    model_config = ConfigDict(frozen=True)

    converted: bool = False  # at least one dosemu.conf has been generated

    @property
    def target(self) -> str:
        """``<scheme>:<identifier>`` - pasteable into ``dedb run``."""
        return short_target(self.scheme, self.identifier)

    @property
    def url(self) -> str:
        """``<scheme>://<identifier>``."""
        return long_target(self.scheme, self.identifier)
