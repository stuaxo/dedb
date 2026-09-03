with open("src/dedb/convert/autoexec.py", "r") as f:
    content = f.read()

# Fix autoexec_shims kwargs! The old signature was:
# def autoexec_shims(autoexec: list[str], working_dir: Path | None = None) -> list[str]
# But convert_autoexec is:
# def convert_autoexec(dosbox_lines, conf=None, working_dir=None)

replacement = """def autoexec_shims(autoexec: list[str], working_dir: Path | None = None) -> list[str]:
    return convert_autoexec(autoexec, conf=None, working_dir=working_dir)
"""

content = content.replace("autoexec_shims = convert_autoexec", replacement)

with open("src/dedb/convert/autoexec.py", "w") as f:
    f.write(content)
