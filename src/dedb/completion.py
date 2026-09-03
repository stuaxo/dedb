"""Shell completion scripts for the ``dedb`` command.

zsh and fish use click's own output unchanged. bash uses a variant:
click's default bash script splits the current word on ``:``, so it
can't complete ``gog:<id>`` / ``archive:<id>`` past the colon. This one
asks the bash-completion package to keep such a word whole
(``_get_comp_words_by_ref -n :``) and trims the prefix back off the
results (``__ltrim_colon_completions``); without that package present it
falls back to click's behaviour.
"""

from click.shell_completion import get_completion_class

PROG_NAME = "dedb"
COMPLETE_VAR = "_DEDB_COMPLETE"

_BASH_SCRIPT = r"""_dedb_completion() {
    local IFS=$'\n'
    local response cur words cword

    if type _get_comp_words_by_ref &>/dev/null; then
        _get_comp_words_by_ref -n : cur words cword
    else
        cur="${COMP_WORDS[COMP_CWORD]}"
        words=("${COMP_WORDS[@]}")
        cword=$COMP_CWORD
    fi

    response=$(env COMP_WORDS="${words[*]}" COMP_CWORD="$cword" _DEDB_COMPLETE=bash_complete "$1")

    for completion in $response; do
        IFS=',' read type value <<< "$completion"

        if [[ $type == 'dir' ]]; then
            COMPREPLY=()
            compopt -o dirnames
        elif [[ $type == 'file' ]]; then
            COMPREPLY=()
            compopt -o default
        elif [[ $type == 'plain' ]]; then
            COMPREPLY+=("$value")
        fi
    done

    if type __ltrim_colon_completions &>/dev/null; then
        __ltrim_colon_completions "$cur"
    fi

    return 0
}

_dedb_completion_setup() {
    complete -o nosort -F _dedb_completion dedb
}

_dedb_completion_setup;
"""

SHELLS = ("bash", "zsh", "fish")


def completion_script(shell: str, cli) -> str:
    """The completion script for ``shell`` ("bash" / "zsh" / "fish")."""
    if shell == "bash":
        return _BASH_SCRIPT
    comp_cls = get_completion_class(shell)
    if comp_cls is None:  # pragma: no cover - zsh/fish are built into click
        raise ValueError(f"click has no {shell} completion support.")
    return comp_cls(cli, {}, PROG_NAME, COMPLETE_VAR).source()
