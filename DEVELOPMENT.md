# Development

This document outlines the development and release process for dedb.

## Release process

You must follow these steps to release a new version of the software.

1. Update the version number in `pyproject.toml`.
2. Update `debian/changelog` with the new version and release notes.
3. Commit these changes.
4. Create a Git tag for the new version. The tag must start with `v` (for example, `v1.0.0`).
5. Push the Git tag to the remote repository.

Pushing the tag will trigger the GitHub Actions workflow. The workflow will automatically build the Debian packages and create a GitHub Release.

## Local builds

You can build the Debian package locally to test your changes.

To build the package, run:

```bash
dpkg-buildpackage -us -uc
```
