"""dedb: DOSEMU2 configuration tooling."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dedb")
except PackageNotFoundError:  # running from a source tree that isn't installed
    __version__ = "0.0.0+unknown"
