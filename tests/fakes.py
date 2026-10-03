"""Stand-ins for the Windows side, so no test runs cmd.exe or reg.exe."""
import io
import struct
import subprocess
import zipfile


def fake_windows(echo=None, reg_query="", reg_add_code=0, calls=None):
    """A ``run`` that answers like a Windows host.

    ``cmd.exe /c echo %VAR%`` prints ``echo[VAR]`` (cmd.exe prints ``%VAR%`` back when a variable is unset),
    ``reg.exe query`` prints ``reg_query`` and ``reg.exe add`` exits with ``reg_add_code``. Any other command
    fails the test. Every call is appended to ``calls`` when it is a list.
    """
    def run(args, **kwargs):
        args = list(args)
        if calls is not None:
            calls.append(args)
        if args[:2] == ["cmd.exe", "/c"] and args[2].startswith("echo %"):
            variable = args[2][len("echo %"):-1]
            stdout = (echo or {}).get(variable, f"%{variable}%\r\n")
            return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")
        if args[:2] == ["reg.exe", "query"]:
            return subprocess.CompletedProcess(args, 0, stdout=reg_query, stderr="")
        if args[:2] == ["reg.exe", "add"]:
            return subprocess.CompletedProcess(args, reg_add_code, stdout="", stderr="")
        raise AssertionError(f"unexpected command in a test: {args}")
    return run


REG_KEY_LINE = "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts"


def reg_listing(values):
    """What ``reg.exe query <key>`` prints for these values."""
    lines = "".join(f"    {name}    REG_SZ    {data}\r\n" for name, data in values.items())
    return f"\r\n{REG_KEY_LINE}\r\n{lines}\r\n"


def make_ttf(full_name):
    """The smallest TrueType file whose name table holds ``full_name`` as name ID 4 (Windows, en-US)."""
    encoded = full_name.encode("utf-16-be")
    name_table = struct.pack(">HHH", 0, 1, 18) + struct.pack(">HHHHHH", 3, 1, 0x409, 4, len(encoded), 0) + encoded
    header = struct.pack(">IHHHH", 0x00010000, 1, 16, 0, 0)
    record = struct.pack(">4sIII", b"name", 0, 12 + 16, len(name_table))
    return header + record + name_table


def make_zip(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()
