"""Tests for `dedb completion` and the committed completion scripts.

The scripts under completions/ are click's own output, installed by the
Debian package (debian/python3-dedb.install). These tests fail if they
drift from what the installed click produces - regenerate with
`python completions/_generate.py`.
"""

from pathlib import Path

import pytest
from click.shell_completion import get_completion_class
from click.testing import CliRunner

from dedb.cli import cli

COMPLETIONS = Path(__file__).parent.parent / "completions"


@pytest.mark.parametrize(
    ("shell", "filename"),
    [("bash", "dedb.bash"), ("zsh", "dedb.zsh"), ("fish", "dedb.fish")],
)
def test_committed_script_matches_click_output(shell: str, filename: str) -> None:
    comp_cls = get_completion_class(shell)
    assert comp_cls is not None
    expected = comp_cls(cli, {}, "dedb", "_DEDB_COMPLETE").source()

    assert (COMPLETIONS / filename).read_text() == expected, (
        f"completions/{filename} is stale - run `python completions/_generate.py`"
    )


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_completion_command_prints_the_script(shell: str) -> None:
    result = CliRunner().invoke(cli, ["completion", shell])

    assert result.exit_code == 0
    assert "_dedb_completion" in result.output


def test_completion_rejects_unknown_shell() -> None:
    result = CliRunner().invoke(cli, ["completion", "tcsh"])

    assert result.exit_code != 0


def test_completion_resolves_a_command_name() -> None:
    # The mechanism the installed scripts drive: click resolving a
    # partial command via the _DEDB_COMPLETE protocol.
    from click.shell_completion import ShellComplete

    comp = ShellComplete(cli, {}, "dedb", "_DEDB_COMPLETE")
    matches = [c.value for c in comp.get_completions(["comp"], "comp")]

    assert "completion" in matches
