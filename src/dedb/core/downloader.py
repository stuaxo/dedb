"""Template for "download + extract one game/item into its layout".

`gog` and `archive` do the same dance - clean out a stale download,
skip/refresh one that's already there, otherwise fetch into a staging
dir, extract into ``game/``, write ``metadata.json`` and (unless
``--keep``) drop the staging dir. Only the fetch, the extract and the
metadata differ, so those are the hooks a subclass fills.
"""


class Downloader:
    def ensure(self, layout, *, keep: bool, refresh_metadata: bool, redownload: bool) -> None:
        """Bring ``layout`` up to date: download + extract if missing,
        re-fetch if ``redownload``, just re-write metadata if
        ``refresh_metadata``, nothing if it's already current."""
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
            self._rm_staging(layout)
            layout.rm_dosemu()  # derived from the extracted files; regenerated on the next --dosemu run

        if layout.is_downloaded():
            print(f"Skipping: {layout.name} (already downloaded)")
            if refresh_metadata or not layout.metadata_json.is_file():
                ctx = self._prepare(layout, refresh=refresh_metadata)
                self._write_metadata(layout, ctx, refresh=refresh_metadata)
            self._post_extract(layout)
            return

        ctx = self._prepare(layout, refresh=refresh_metadata)
        layout.dir.mkdir(parents=True, exist_ok=True)

        print(f"Downloading: {layout.name}")
        if self._fetch(layout, ctx) is False:
            return

        print(f"Extracting: {layout.name}")
        layout.game.mkdir(parents=True, exist_ok=True)
        self._extract(layout, ctx)

        self._post_extract(layout)
        self._write_metadata(layout, ctx, refresh=refresh_metadata)

        if not keep:
            self._rm_staging(layout)

    # --- hooks -----------------------------------------------------------

    def _prepare(self, layout, *, refresh: bool):
        """Validate the item is downloadable and return whatever ``_fetch``
        / ``_write_metadata`` need (the resolved metadata, an id, ...).
        Raise ``click.ClickException`` if it can't be downloaded."""
        return None

    def _fetch(self, layout, ctx) -> bool | None:
        """Download the item into its staging dir. Return ``False`` to
        abort quietly (e.g. nothing matched); anything else continues."""
        raise NotImplementedError

    def _extract(self, layout, ctx) -> None:
        """Unpack the staging dir into ``layout.game``."""
        raise NotImplementedError

    def _post_extract(self, layout) -> None:
        """Run after every extraction (and on a metadata refresh). No-op by default."""

    def _write_metadata(self, layout, ctx, *, refresh: bool) -> None:
        """Write ``layout.metadata_json``."""
        raise NotImplementedError

    def _rm_staging(self, layout) -> None:
        """Delete the download staging dir (``installer/`` / ``download/``)."""
        raise NotImplementedError
