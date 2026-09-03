# DOSBox to DOSEMU2: the details

Background to the conversion section of
[ARCHITECTURE.md](../ARCHITECTURE.md). The goal is to run a DOSBox
program under DOSEMU2 without changing its files; making it run at all
comes first.

## Seeing what a conf needs

`dedb dosboxconf CONF --issues` lists the autoexec commands DOSEMU2 can't
run as-is, before you convert anything (`CONF` is a `.conf` path or a
`gog://<id>` target). It runs the real shim pipeline, so it matches what
ends up in `userhook.bat`. Compact output - one workaround name per
severity band:

```
[issues]
Commands not supported as-is under DOSEMU2:
'imgmount'
Commands only partially supported:
'choice'
'mount'
```

`-v` expands each band to every line and its rewrite. A conf that needs
no shims reports `(none)`.

## Drive mapping

DOSBox maps drives and disk images with `MOUNT` and `IMGMOUNT`. DOSEMU2
has neither. dedb handles it three ways:

- `C:` is set to the game directory with `--Fdrive_c`, before
  `userhook.bat` runs.
- simple secondary `MOUNT`s become `LREDIR -f`, via an autoexec shim.
- `IMGMOUNT` and overlay `MOUNT`s have no equivalent - a shim comments
  them out.

A further `MOUNT C` in the autoexec is commented out too: LREDIR has no
overlay support, so re-mounting `C:` would re-map the drive `userhook.bat`
is being read from. This breaks menu-driven packs (e.g. `catacombs_pack`)
that re-point `C:` at subdirectories on the fly.

## DPMI memory

DOSBox shares one `memsize` across XMS, EMS and DPMI; DOSEMU2 sizes each
pool separately. Copying `memsize` straight into `$_dpmi` badly
under-provisions DPMI - GOG confs often set `memsize` to 16 MB. dedb uses
it as a floor against DOSEMU2's 128 MB default instead. Over-provisioning
DPMI is safe; under-provisioning is fatal.
