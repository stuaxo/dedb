_dedb_completion() {
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
