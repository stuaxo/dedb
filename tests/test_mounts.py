"""Tests for dedb.convert.mounts - finding the MOUNT targets in an
autoexec and resolving them to host paths (used by the GOG downloader to
pre-create directories an installer script would have made).
"""

from pathlib import Path

from dedb.convert.mounts import parse_mount_command, resolve_mounts


def test_parse_mount_command_reads_drive_and_path():
    assert parse_mount_command('MOUNT C ".."') == ("C", "..")
    assert parse_mount_command("mount d GAME") == ("D", "GAME")
    assert parse_mount_command("@MOUNT E sub\\dir") == ("E", "sub\\dir")


def test_parse_mount_command_ignores_non_mounts():
    assert parse_mount_command("IMGMOUNT E disk.img") is None
    assert parse_mount_command("MOUNT -u D") is None  # an unmount
    assert parse_mount_command("GAME.EXE") is None


def test_resolve_mounts_resolves_each_target_against_the_working_dir(tmp_path: Path):
    autoexec = [
        'MOUNT C ".."',
        "MOUNT D GAME",
        "IMGMOUNT E disk.img",
        "MOUNT -u D",
    ]

    mounts = resolve_mounts(autoexec, tmp_path)

    assert [(m.dos_drive, m.dos_path) for m in mounts] == [("C", ".."), ("D", "GAME")]
    assert mounts[1].host_path == (tmp_path / "GAME").resolve()


def test_resolve_mounts_translates_dos_backslashes(tmp_path: Path):
    (mount,) = resolve_mounts(['MOUNT D "..\\cloud_saves"'], tmp_path)

    assert mount.host_path == (tmp_path.parent / "cloud_saves").resolve()
