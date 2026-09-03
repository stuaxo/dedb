with open("src/dedb/convert/autoexec.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith("from typing import Any"):
        continue
    new_lines.append(line)

with open("src/dedb/convert/autoexec.py", "w") as f:
    f.writelines(new_lines)
