from pathlib import Path
from dedb.convert.autoexec import convert_autoexec

def test_repro():
    working_dir = Path("/tmp/work")
    res = convert_autoexec(["MOUNT D SAVES"], working_dir=working_dir)
    print("Result:", res)

test_repro()
