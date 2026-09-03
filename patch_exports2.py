with open("src/dedb/convert/autoexec.py", "r") as f:
    content = f.read()

active_workaround_func = """
def active_workarounds(*args, **kwargs):
    # Stub for backwards compatibility with __init__.py exports.
    return []
"""

if "def active_workarounds" not in content:
    content += active_workaround_func

with open("src/dedb/convert/autoexec.py", "w") as f:
    f.write(content)

with open("src/dedb/convert/__init__.py", "r") as f:
    init_content = f.read()
# Let's not remove it from __init__.py because we added it as a stub.
