# Notes on running DOSBOX programs in DOSEMU2

The ultimate goal is to run these programs without modifying their directory structure,
however that comes after making them work at all.


## Startup: autoexec to `userhook.bat`

DOSBox stores startup commands in the `[autoexec]` section of `dosbox.conf`.
The `[autoexec]` section used to create a `userhook.bat` script.

**shims** are used to comment out unsupported commands and translate others where possible.


## Drive Mapping

DOSBOX uses `MOUNT` and `IMGMOUNT` commands to map drives and disk images to directories.

In DOSBOX MOUNT not only is used for simple mappings, but can do overlay mounts to the same drive,
games can have multiple MOUNT commands for the same drive.

IMGMOUNT can be used to mount disk images to drives, there is no runtime equivalent in DOSEMU2.


Drive handling relies on a hybrid approach:

- **Initial `C:` Mapping:** Driven by passing `--Fdrive_c` to set the `C:` drive to the game directory _before_
  `userhook.bat` executes.
- **Secondary Drives:** Handled by the autoexec shims, which translate simple `MOUNT` commands into `LREDIR -f`.
- **Unsupported Features:** `IMGMOUNT` and overlay mounts are not supported and are commented out by the shims.

**The `C:` Re-mapping Limitation:**

Since LREDIR doesn't support overlay mounts there is shim to comment out further MOUNT commands (without overlay
support this would be re-MOUNTing the drive that usermount.bat itself is on).


_Multi-game edge case:_ This limitation breaks menu-driven packs (e.g., `catacombs_pack`) that attempt to re-map `C:` to
different subdirectories on the fly.


## DPMI Memory

DOSBox shares a single `memsize` value across XMS, EMS, and DPMI.
DOSEMU2 sizes these pools independently.

Directly mapping DOSBox's `memsize` to DOSEMU2's `$_dpmi` causes severe under-provisioning, as GOG configs frequently
set `memsize` as low as 16MB. Instead, we use `memsize` as a floor against DOSEMU2's 128MB default. Over-provisioning
DPMI is safe; under-provisioning is fatal.
