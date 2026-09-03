with open("src/dedb/convert/autoexec.py", "r") as f:
    content = f.read()

stubs = """
# Stubs for backwards compatibility in tests and __init__.py

choice_shim = shim_choice

def mount_lredir_shim(working_dir):
    def shim(line):
        return shim_mount(line, working_dir=working_dir)
    return shim

def unsupported_command(cmd):
    def shim(line):
        if cmd == "imgmount":
            return shim_imgmount(line)
        return line
    return shim

def unsupported_mount_option(opt):
    def shim(line):
        return shim_unsupported_mount_option(line)
    return shim
"""

if "choice_shim =" not in content:
    content += stubs

with open("src/dedb/convert/autoexec.py", "w") as f:
    f.write(content)
