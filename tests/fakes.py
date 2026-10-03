"""Stand-ins for the Windows side, so no test runs cmd.exe or reg.exe."""
import io
import struct
import subprocess
import zipfile


def fake_windows(echo=None, reg_query="", reg_query_code=0, reg_add_code=0, calls=None):
    """A ``run`` that answers like a Windows host.

    ``cmd.exe /c echo %VAR%`` prints ``echo[VAR]`` (cmd.exe prints ``%VAR%`` back when a variable is unset),
    ``reg.exe query`` prints ``reg_query`` and exits with ``reg_query_code``, and ``reg.exe add`` exits with
    ``reg_add_code``. Any other command fails the test. Every call is appended to ``calls`` when it is a list.
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
            return subprocess.CompletedProcess(args, reg_query_code, stdout=reg_query, stderr="")
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


def fake_fish(variables=None, tide=True, fail_at=None, missing=False, noise="", calls=None):
    """A ``run`` that answers witchy's fish scripts the way fish would, byte for byte.

    ``variables`` maps names to ``{"value": [...], "exported": bool}`` and is changed in place by the set
    script. A value stands for its UTF-8 bytes with surrogate escapes, so it can hold any byte but NUL.
    Standard input and output are handled as ``subprocess.run`` handles them: bytes, or text that is decoded
    with ``errors`` and has its newlines translated. ``fail_at`` names a variable whose set fails (the script
    stops there, exit 1); ``missing`` makes fish absent; ``noise`` is what config.fish prints first. Every
    call is appended to ``calls``, with its input as a string.
    """
    from witchy.components import fish

    store = {} if variables is None else variables

    def answer(args, received):
        if args[:3] == ["fish", "-c", fish.SNAPSHOT_SCRIPT] and args[3] == "--":
            fields = ["tide" if tide else "no-tide"]
            for name in args[4:]:
                if name in store:
                    value = store[name]
                    fields += [name, "exported" if value["exported"] else "unexported", str(len(value["value"])),
                               *value["value"]]
                else:
                    fields += [name, "absent"]
            return 0, fields
        if args == ["fish", "-c", fish.SET_SCRIPT]:
            items, done = received.split("\0")[:-1], []
            while items:
                name, mode, count = items[:3]
                values, items = items[3:3 + int(count)], items[3 + int(count):]
                if name == fail_at:
                    return 1, done
                if mode == "erase":
                    store.pop(name, None)
                else:
                    exported = mode == "exported" or store.get(name, {}).get("exported", False)
                    store[name] = {"value": values, "exported": exported}
                done.append(name)
            return 0, done
        if args == ["fish", "-c", fish.REFRESH_SCRIPT]:
            return 0, None
        raise AssertionError(f"unexpected command in a test: {args}")

    def run(args, input=None, text=False, errors="strict", **kwargs):
        args = list(args)
        if text and input is not None:
            input = input.encode("utf-8", errors)
        received = None if input is None else input.decode("utf-8", "surrogateescape")
        if calls is not None:
            calls.append((args, received))
        if missing:
            raise FileNotFoundError(2, "No such file or directory", "fish")
        code, fields = answer(args, received)
        printed = noise + ("" if fields is None else "".join(f"{field}\0" for field in [fish.SENTINEL, *fields]))
        stdout = printed.encode("utf-8", "surrogateescape")
        if text:
            stdout = stdout.decode("utf-8", errors).replace("\r\n", "\n").replace("\r", "\n")
            return subprocess.CompletedProcess(args, code, stdout=stdout, stderr="")
        return subprocess.CompletedProcess(args, code, stdout=stdout, stderr=b"")
    return run
