"""Tests for `dedb completion` and the committed completion scripts.

The scripts under completions/ are installed by the Debian package
(debian/dedb.install). zsh/fish are click's output; bash is a
colon-aware variant (dedb.completion). These tests fail if the files
drift - regenerate with `python completions/_generate.py`.
"""

from pathlib import Path

import pytest
from click.shell_completion import ShellComplete
from click.testing import CliRunner

from dedb.cli import cli
from dedb.completion import SHELLS, completion_script

COMPLETIONS = Path(__file__).parent.parent / "completions"


@pytest.mark.parametrize("shell", SHELLS)
def test_committed_script_is_current(shell: str) -> None:
    expected = completion_script(shell, cli)

    assert (COMPLETIONS / f"dedb.{shell}").read_text() == expected, (
        f"completions/dedb.{shell} is stale - run `python completions/_generate.py`"
    )


def test_bash_script_keeps_scheme_targets_in_one_word() -> None:
    # click's stock bash script splits the word on ":"; ours must not.
    script = completion_script("bash", cli)
    assert "_get_comp_words_by_ref -n :" in script
    assert "__ltrim_colon_completions" in script


@pytest.mark.parametrize("shell", SHELLS)
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
    comp = ShellComplete(cli, {}, "dedb", "_DEDB_COMPLETE")
    matches = [c.value for c in comp.get_completions(["comp"], "comp")]

    assert "completion" in matches


def test_game_arguments_complete_scheme_prefixes() -> None:
    # run / download / rm / refreshmetadata route GAME through complete_target;
    # import / dosboxconf / dosemuconf route SOURCES through complete_source.
    comp = ShellComplete(cli, {}, "dedb", "_DEDB_COMPLETE")
    commands = ("run", "download", "rm", "refreshmetadata", "import", "dosboxconf", "dosemuconf")
    for command in commands:
        matches = [c.value for c in comp.get_completions([command], "")]
        assert "gog:" in matches, command
        assert "archive:" in matches, command
