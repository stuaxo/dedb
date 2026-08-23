# Release

Follow these steps to release a new version of dedb:

1. Update the version in `pyproject.toml`.
2. Update `debian/changelog` with the new version and release notes.
3. Commit these changes.
4. Create a Git tag starting with `v` (e.g., `v1.0.0`).
5. Push the Git tag to trigger the GitHub Actions workflow, which builds the Debian packages and creates a GitHub Release.
