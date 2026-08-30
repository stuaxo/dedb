# Development

See [RELEASE.md](RELEASE.md) for the release process.
See [doc/backends.md](doc/backends.md) for how game-source backends
(`gog://`, `archive://`, ...) are registered and resolved.

## Local builds

To build the Debian package locally:

```bash
dpkg-buildpackage -us -uc
```
