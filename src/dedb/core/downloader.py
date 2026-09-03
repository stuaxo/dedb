"""Template for "download + extract one game/item into its layout".

`gog` and `archive` do the same dance - clean out a stale download,
skip/refresh one that's already there, otherwise fetch into a staging
dir, extract into ``game/``, write ``metadata.json`` and (unless
``--keep``) drop the staging dir. Only the fetch, the extract and the
metadata differ, so those are the hooks a subclass fills.

A ``Downloader`` is bound to one ``layout`` at construction and used
once. ``_prepare`` validates the item and stashes whatever the later
hooks need on ``self``; the base class threads nothing between them.
"""


class Downloader:
    def __init__(self, layout) -> None:
        self.layout = layout

    def run(
        self, *, keep: bool = False, refresh_metadata: bool = False, redownload: bool = False
    ) -> None:
        """Bring ``self.layout`` up to date: download + extract if missing,
        re-fetch if ``redownload``, just re-write metadata if
        ``refresh_metadata``, nothing if it's already current."""
        layout = self.layout
        if (
            layout.is_downloaded()
            and layout.metadata_json.is_file()
            and not (redownload or refresh_metadata)
        ):
            print(f"Skipping: {layout.name} (already downloaded)")
            return

        if redownload and layout.is_downloaded():
            print(f"Removing existing download: {layout.name}")
            layout.rm_game()
            layout.rm_staging()
            layout.rm_dosemu()  # derived from the extracted files; regenerated on the next --dosemu run

        if layout.is_downloaded():
            print(f"Skipping: {layout.name} (already downloaded)")
            if refresh_metadata or not layout.metadata_json.is_file():
                self.rewrite_metadata(refresh=refresh_metadata)
            else:
                self._post_extract()
            return

        self._prepare(refresh=refresh_metadata)
        layout.dir.mkdir(parents=True, exist_ok=True)

        print(f"Downloading: {layout.name}")
        if self._fetch() is False:
            return

        print(f"Extracting: {layout.name}")
        layout.game.mkdir(parents=True, exist_ok=True)
        self._extract()

        self._post_extract()
        self._write_metadata(refresh=refresh_metadata)

        if not keep:
            layout.rm_staging()

    def rewrite_metadata(self, *, refresh: bool = True) -> None:
        """Redo just the metadata step for an already-extracted game -
        ``_prepare`` + ``_write_metadata`` (+ ``_post_extract``), rewriting
        ``self.layout.metadata_json`` without touching the game files.
        ``refresh`` re-fetches cached backend metadata."""
        self._prepare(refresh=refresh)
        self._write_metadata(refresh=refresh)
        self._post_extract()

    # --- hooks -----------------------------------------------------------

    def _prepare(self, *, refresh: bool) -> None:
        """Validate the item is downloadable and stash whatever ``_fetch``
        / ``_extract`` / ``_write_metadata`` need on ``self`` (the
        resolved metadata, an id, ...). Raise ``click.ClickException`` if
        it can't be downloaded."""

    def _fetch(self) -> bool | None:
        """Download the item into its staging dir. Return ``False`` to
        abort quietly (e.g. nothing matched); anything else continues."""
        raise NotImplementedError

    def _extract(self) -> None:
        """Unpack the staging dir into ``self.layout.game``."""
        raise NotImplementedError

    def _post_extract(self) -> None:
        """Run after every extraction (and on a metadata refresh). No-op by default."""

    def _write_metadata(self, *, refresh: bool) -> None:
        """Write ``self.layout.metadata_json``."""
        raise NotImplementedError
