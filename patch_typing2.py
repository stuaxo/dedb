with open("src/dedb/convert/autoexec.py", "r") as f:
    content = f.read()

# Add from typing import Any near other imports
content = content.replace("from pathlib import Path\n", "from pathlib import Path\nfrom typing import Any\n")

with open("src/dedb/convert/autoexec.py", "w") as f:
    f.write(content)
