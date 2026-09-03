with open("src/dedb/convert/autoexec.py", "r") as f:
    content = f.read()

# Fix the stub implementations for tests
replacement = """def unsupported_command(cmd):
    def shim(line):
        rest = line[1:] if line.startswith("@") else line
        tokens = rest.split()
        if tokens and tokens[0].lower() == cmd.lower():
            return f"REM {line}"
        return line
    return shim

def unsupported_mount_option(option):
    def shim(line):
        _prefix, tokens = _split_line(line)
        if not tokens or tokens[0].lower() != "mount":
            return line
        if not any(token.lower() == option.lower() for token in tokens):
            return line
        return f"REM {line}"
    return shim
"""

import re
content = re.sub(r'def unsupported_command\(cmd\):.*return shim', replacement, content, flags=re.DOTALL)

with open("src/dedb/convert/autoexec.py", "w") as f:
    f.write(content)
