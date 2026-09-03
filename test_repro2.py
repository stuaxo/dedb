from dedb.convert.autoexec import convert_autoexec, autoexec_shims
from pathlib import Path
print(autoexec_shims(["MOUNT D SAVES"], working_dir=Path("/tmp/work")))
