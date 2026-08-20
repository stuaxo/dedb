"""Shims for a game's autoexec, applied only to the userhook.bat DOSEMU2
sees - what real DOSBox sees (via -conf) is never touched.

Each shim takes one autoexec line and returns a replacement line, passing
through any line it doesn't recognize unchanged. Too early to generalize
beyond that single-line shape - keep it all in this one module until a
shim actually needs more (e.g. whole-autoexec context).
"""

from typing import Callable

SinglelineShim = Callable[[str], str]


def choice_shim(line: str) -> str:
    """DOS CHOICE's flags (/C, /N, /S, /T...) are known to break keyboard
    input in some environments - strip every flag, keeping only the
    command itself and its prompt message."""
    # A leading '@' suppresses DOS echoing that one line (e.g. "@choice
    # ..."), same as "echo off" for just this command - strip it before
    # matching the command word, but keep it in the output.
    prefix, rest = ("@", line[1:]) if line.startswith("@") else ("", line)
    tokens = rest.split()
    if not tokens or tokens[0].lower() != "choice":
        return line
    kept = [tokens[0]] + [token for token in tokens[1:] if not token.startswith("/")]
    return prefix + " ".join(kept)


def unsupported_command(command: str) -> SinglelineShim:
    """Build a shim for a command dedb doesn't support. By default,
    comments out any line invoking it."""

    def shim(line: str) -> str:
        rest = line[1:] if line.startswith("@") else line
        tokens = rest.split()
        if tokens and tokens[0].lower() == command.lower():
            return f"REM {line}"
        return line

    return shim


unsupported_imgmount = unsupported_command("imgmount")

# Active by default. unsupported_imgmount isn't here - imgmount works fine
# under real DOSBox, it's only DOSEMU2 conversion that can't translate it
# yet.
SHIMS: list[SinglelineShim] = [choice_shim]


def autoexec_shims(autoexec: list[str]) -> list[str]:
    """Run every line of autoexec through each active shim, in order."""
    result = []
    for line in autoexec:
        for shim in SHIMS:
            line = shim(line)
        result.append(line)
    return result
