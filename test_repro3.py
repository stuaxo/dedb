import sys
from pathlib import Path
from dedb.convert.converter import build_from_parsed

working_dir = Path("/tmp/work")
target, lines = build_from_parsed({"autoexec": "MOUNT D SAVES"}, ["MOUNT D SAVES"], working_dir=working_dir)
print(lines)
