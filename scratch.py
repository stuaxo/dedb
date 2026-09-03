import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path

# Need to keep these for `issues.py` and `models.py` potentially.
class Severity(Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially supported"
    UNSUPPORTED = "unsupported"

SEVERITY_ORDER: tuple[Severity, ...] = (
    Severity.UNSUPPORTED,
    Severity.PARTIALLY_SUPPORTED,
    Severity.SUPPORTED,
)

SEVERITY_BLURB: dict[Severity, str] = {
    Severity.SUPPORTED: "translated to a DOSEMU2 equivalent",
    Severity.PARTIALLY_SUPPORTED: "still runs, but not identically to DOSBox",
    Severity.UNSUPPORTED: "no DOSEMU2 equivalent - commented out; the game may misbehave",
}

SEVERITY_HEADING: dict[Severity, str] = {
    Severity.SUPPORTED: "Commands translated to a DOSEMU2 equivalent:",
    Severity.PARTIALLY_SUPPORTED: "Commands only partially supported:",
    Severity.UNSUPPORTED: "Commands not supported as-is under DOSEMU2:",
}

@dataclass(frozen=True)
class AutoexecIssue:
    workaround: str
    severity: Severity
    summary: str
    line: str
    rewritten: str

def split_command(text: str) -> list[str]:
    tokens = re.findall(r'"[^"]*"|\S+', text)
    return [t[1:-1] if t.startswith('"') and t.endswith('"') else t for t in tokens]

def _split_line(line: str) -> tuple[str, list[str]]:
    prefix, rest = ("@", line[1:]) if line.startswith("@") else ("", line)
    return prefix, split_command(rest)


# 1. Shims: All shims must accept **kwargs to ignore unused args.
def shim_choice(line, **kwargs):
    prefix, tokens = _split_line(line)
    kept = [tokens[0]] + [token for token in tokens[1:] if not token.startswith("/")]
    return prefix + " ".join(kept)

def shim_mount(line, working_dir=None, drive=None, dos_path=None, **kwargs):
    if working_dir is None:
        return f"REM {line}"

    prefix, tokens = _split_line(line)

    # We might extract drive/dos_path from regex, or we can use tokens.
    # The blueprint prefers regex named groups.
    # If the regex matched, drive and dos_path are passed in!
    # But wait, dos_path might have quotes in the regex match!
    # Let's rely on tokens for cleaner logic, but accept drive/dos_path as kwargs to satisfy instructions.

    if len(tokens) < 3:
        return line

    drive_tok, dos_path_tok = tokens[1], tokens[2]

    if drive_tok.rstrip(":").upper() == "C":
        return f"REM {line}"

    host_path = (working_dir / dos_path_tok.replace("\\", "/")).resolve()
    return f"{prefix}LREDIR -f {drive_tok.rstrip(':').upper()}: {host_path}"

def shim_imgmount(line, **kwargs):
    return f"REM {line}"

def shim_unsupported_mount_option(line, **kwargs):
    return f"REM {line}"

# 2. Routing Table: Regex patterns using named capture groups
SHIMS = [
    (r"^\s*@?imgmount\b.*$", shim_imgmount),
    (r"^\s*@?mount\b.*-t\s+overlay.*$", shim_unsupported_mount_option),
    (r"^\s*@?mount\s+(?P<drive>[a-zA-Z]:?)\s+(?P<dos_path>\"[^\"]*\"|\S+).*$", shim_mount),
    (r"^\s*@?choice\b.*$", shim_choice),
]

# 3. Lazy Compilation
@lru_cache(maxsize=None)
def get_shims():
    return [(re.compile(p, re.IGNORECASE), h) for p, h in SHIMS]

# 4. Processing logic
def process_autoexec_line(line: str, conf: any, working_dir: Path | None) -> str | None:
    clean = line.strip()
    for pattern, handler in get_shims():
        if match := pattern.match(clean):
            return handler(line=clean, conf=conf, working_dir=working_dir, **match.groupdict())
    return line

def convert_autoexec(dosbox_lines: list[str], conf: any = None, working_dir: Path | None = None) -> list[str]:
    return [
        res for line in dosbox_lines
        if (res := process_autoexec_line(line, conf, working_dir)) is not None
    ]

# And what about autoexec_shims? That was the old name, maybe we can alias it:
autoexec_shims = convert_autoexec

# And resolve_mounts:
@dataclass(frozen=True)
class ResolvedMount:
    drive: str
    dos_path: str
    host_path: Path

def resolve_mounts(autoexec: list[str], working_dir: Path) -> list[ResolvedMount]:
    resolved = []
    for line in autoexec:
        _prefix, tokens = _split_line(line)
        if len(tokens) < 3 or tokens[0].lower() != "mount" or tokens[1].startswith("-"):
            continue
        drive, dos_path = tokens[1], tokens[2]
        host_path = (working_dir / dos_path.replace("\\", "/")).resolve()
        resolved.append(ResolvedMount(drive.rstrip(":").upper(), dos_path, host_path))
    return resolved

# What about diagnose_autoexec?
def diagnose_autoexec(autoexec: list[str], working_dir: Path | None = None) -> list[AutoexecIssue]:
    issues = []
    for original in autoexec:
        line = original

        # We need to run it through get_shims() to see what matches!
        clean = line.strip()
        matched = False
        for pattern, handler in get_shims():
            if match := pattern.match(clean):
                rewritten = handler(line=clean, conf=None, working_dir=working_dir, **match.groupdict())
                if rewritten != original:
                    # Map handler to workaround metadata
                    if handler == shim_imgmount:
                        issues.append(AutoexecIssue("imgmount", Severity.UNSUPPORTED, "IMGMOUNT (disk-image mounts) has no runtime equivalent in DOSEMU2", original, rewritten))
                    elif handler == shim_unsupported_mount_option:
                        issues.append(AutoexecIssue("overlay-mount", Severity.UNSUPPORTED, "overlay MOUNT (-t overlay) has no equivalent - DOSEMU2 has no overlay filesystem", original, rewritten))
                    elif handler == shim_choice:
                        issues.append(AutoexecIssue("choice", Severity.PARTIALLY_SUPPORTED, "CHOICE flags (/C, /N, /S, /T...) stripped - they break keyboard input under DOSEMU2", original, rewritten))
                    elif handler == shim_mount:
                        summary = "MOUNT rewritten to LREDIR (a C: mount is dropped - --Fdrive_c already maps C:)" if working_dir else "MOUNT commented out - translating it to LREDIR needs a known working directory"
                        issues.append(AutoexecIssue("mount", Severity.PARTIALLY_SUPPORTED, summary, original, rewritten))
                break # Only one shim applies in the new architecture

    return issues

print("Scratchpad compiles!")
