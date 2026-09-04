# Release

Follow these steps to release a new version of dedb:

1. Update the version in `pyproject.toml`.
2. Update `debian/changelog` with the new version and release notes.
3. Regenerate the man pages so their `.TH` header carries the new
   version: `uv run python man/_generate.py` (`test_manpage.py` fails
   otherwise).
4. Commit these changes.
5. Create a Git tag starting with `v` (e.g., `v1.0.0`).
6. Push the Git tag to trigger the GitHub Actions workflow, which
   builds the Debian packages, the Python wheel and sdist, and attaches
   them all to a GitHub Release. The release notes are GitHub's
   auto-generated commit list followed by `.github/release-body.md`
   (with `@VERSION@` and `@REF@` filled in); edit that file to change
   how the assets are described.
