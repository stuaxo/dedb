with open("src/dedb/convert/autoexec.py", "r") as f:
    content = f.read()

workaround_class = """
@dataclass(frozen=True)
class Workaround:
    \"\"\"For backwards compatibility with __init__.py exports.\"\"\"
    name: str
    severity: Severity
    summary: str
    shim: Any
"""

if "class Workaround:" not in content:
    content += workaround_class

with open("src/dedb/convert/autoexec.py", "w") as f:
    f.write(content)
