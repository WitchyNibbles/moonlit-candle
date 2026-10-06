"""Stand-ins for the Windows side and for fish, so no test runs cmd.exe or reg.exe or needs a real Tide."""
import io
import shutil
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


# The machine fake_fish stands for: fisher 4.4.5 and Tide 6.1.1 installed by fisher in /home/user.
FAKE_FUNCTIONS = "/home/user/.config/fish/functions"
FAKE_PROMPT = f"{FAKE_FUNCTIONS}/fish_prompt.fish"
FAKE_TIDE_FILES = [FAKE_PROMPT, f"{FAKE_FUNCTIONS}/tide.fish", f"{FAKE_FUNCTIONS}/_tide_item_git.fish"]


def fake_fish(variables=None, tide="6.1.1", fail_at=None, missing=False, noise="", calls=None, fisher="4.4.5",
              prompt=FAKE_PROMPT, plugins=None):
    """A ``run`` that answers witchy's fish scripts the way fish would, byte for byte.

    ``variables`` maps names to ``{"value": [...], "exported": bool}`` and is changed in place by the set
    script. A value stands for its UTF-8 bytes with surrogate escapes, so it can hold any byte but NUL.
    Standard input and output are handled as ``subprocess.run`` handles them: bytes, or text that is decoded
    with ``errors`` and has its newlines translated. ``fail_at`` names a variable whose set fails (the script
    stops there, exit 1); ``missing`` makes fish absent; ``noise`` is what config.fish prints first. Every
    call is appended to ``calls``, with its input as a string.

    The fisher and Tide probe (witchy.fishprobe) sees: ``fisher``, the version ``fisher --version`` reports (None:
    fisher is not installed); ``tide``, the version ``tide --version`` reports (None or False: Tide is not
    installed); ``prompt``, the file fish_prompt comes from (None: not defined); and ``plugins``, fisher's plugins
    and their files. By default ``plugins`` lists fisher and Tide (``FAKE_TIDE_FILES``) when they are installed.
    """
    from witchy import fishprobe
    from witchy.components import fish

    store = {} if variables is None else variables
    if plugins is None:
        plugins = {}
        if fisher is not None:
            plugins["jorgebucaran/fisher"] = [f"{FAKE_FUNCTIONS}/fisher.fish"]
        if tide:
            plugins["ilancosman/tide"] = list(FAKE_TIDE_FILES)

    def answer(args, received):
        if args == ["fish", "-c", fishprobe.PROBE_SCRIPT]:
            fields = ["fisher", f"fisher, version {fisher}"] if fisher is not None else ["no-fisher"]
            fields += ["tide", f"tide, version {tide}"] if tide else ["no-tide"]
            fields.append(prompt if prompt is not None else "n/a")
            for name, files in plugins.items():
                fields += [name, str(len(files)), *files]
            return 0, fields
        if args[:3] == ["fish", "-c", fish.SNAPSHOT_SCRIPT] and args[3] == "--":
            # The names asked for, then every other universal tide_ variable (never Tide's private _tide_ ones).
            fields = []
            for name in args[4:] + sorted(name for name in store if name.startswith("tide_") and name not in args[4:]):
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
        printed = noise + ("" if fields is None else "".join(f"{field}\0" for field in [fishprobe.SENTINEL, *fields]))
        stdout = printed.encode("utf-8", "surrogateescape")
        if text:
            stdout = stdout.decode("utf-8", errors).replace("\r\n", "\n").replace("\r", "\n")
            return subprocess.CompletedProcess(args, code, stdout=stdout, stderr="")
        return subprocess.CompletedProcess(args, code, stdout=stdout, stderr=b"")
    return run


def fake_tide(fish_config, env):
    """Make the real fish behind ``env`` see Tide 6.1.1 installed by fisher in the folder ``fish_config``.

    It writes a ``tide`` function that reports version 6.1.1 and a stand-in for Tide's fish_prompt, and sets the
    universal variables fisher keeps for an installed plugin. ``env`` must point HOME and XDG_CONFIG_HOME at
    temporary folders.
    """
    functions = fish_config / "functions"
    functions.mkdir(parents=True, exist_ok=True)
    (functions / "tide.fish").write_text("function tide\n    echo 'tide, version 6.1.1'\nend\n", encoding="utf-8")
    (functions / "fish_prompt.fish").write_text("function fish_prompt\n    echo '> '\nend\n", encoding="utf-8")
    subprocess.run([shutil.which("fish"), "-c", "set -U _fisher_plugins ilancosman/tide; "
                    "set -U _fisher_ilancosman_2F_tide_files $argv", "--",
                    str(functions / "tide.fish"), str(functions / "fish_prompt.fish")],
                   env=env, check=True, timeout=20, capture_output=True)
