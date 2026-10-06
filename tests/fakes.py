"""Stand-ins for the Windows side and for fish, so no test runs cmd.exe or reg.exe or needs a real Tide."""
import hashlib
import io
import re
import shutil
import struct
import subprocess
import tarfile
import zipfile
from pathlib import Path


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
              prompt=FAKE_PROMPT, plugins=None, globals=None, parses=None):
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

    A new interactive shell (doctor's read) sees ``globals``: names set with ``set -g`` by config.fish or conf.d,
    each with its value.

    ``fish --no-execute <file>`` (the syntax check of a file witchy would edit) passes unless ``parses``, given the
    file's bytes, says False.
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
        if args[:4] == ["fish", "-i", "-c", fish.GLOBALS_SCRIPT] and args[4] == "--":
            fields = []
            for name in args[5:]:
                if name in (globals or {}):
                    fields += [name, str(len(globals[name])), *globals[name]]
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
        if args[:2] == ["fish", "--no-execute"] and len(args) == 3:
            return (0 if parses is None or parses(Path(args[2]).read_bytes()) else 127), None
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


# What `fisher install` fetches in tests: fisher 4.4.5 and a cut-down Tide 6.1.1, as files below fisher's folder.
FISHER_FILE = b"function fisher\n    echo 'fisher, version 4.4.5'\nend\n"
TIDE_FILES = {"functions/tide.fish": b"function tide\n    echo 'tide, version 6.1.1'\nend\n",
              "functions/fish_prompt.fish": b"function fish_prompt\n    echo '> '\nend\n",
              "functions/tide/configure/icons.fish": b"tide_pwd_icon x\n",
              "conf.d/_tide_init.fish": b"function _tide_init_install --on-event _tide_init_install\nend\n"}
RELEASES = {"jorgebucaran/fisher@4.4.5": {"functions/fisher.fish": FISHER_FILE,
                                          "completions/fisher.fish": b"complete -c fisher\n"},
            "ilancosman/tide@v6.1.1": TIDE_FILES}


def release_tarball(files):
    """A gzip tarball like GitHub's release download: every path below one top folder."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(f"owner-repo-abc1234/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def fake_pins(releases=None, bootstrap=FISHER_FILE):
    """content/pins.json for ``releases``: the bootstrap file's hash and each plugin's file hashes."""
    def digest(data):
        return hashlib.sha256(data).hexdigest()

    return {"bootstrap": {"url": "https://example.invalid/fisher.fish", "sha256": digest(bootstrap)},
            "plugins": {name: {path: digest(data) for path, data in files.items()}
                        for name, files in (RELEASES if releases is None else releases).items()}}


class FakeFisher:
    """fish with fisher, whose plugins are real files in ``config`` (a temporary fish folder), so witchy can hash
    them.

    ``installed`` maps the plugins there at the start (by fisher's name, such as ``ilancosman/tide``) to their files;
    ``served`` is what `fisher install` can fetch, by ``owner/repo@ref``. fisher is a function when
    functions/fisher.fish exists or while a bootstrap script runs; `fisher --version` and `tide --version` print the
    version their file holds, and fish_prompt comes from functions/fish_prompt.fish, or from stdin ("-") while an
    active `starship init` or `oh-my-posh init` line in config.fish or conf.d sources one, as `fish -c` does. The
    fake does not read `if status is-interactive` guards (`fish -c` skips what they hold), so tests that want such a
    line to define fish_prompt write it unguarded. Like the real fisher, install
    refuses a file that is already there (unless it updates that plugin), remove deletes the plugin's files, and
    removing Tide erases every universal tide_ variable. Other fish calls go to fake_fish with ``variables`` (and
    ``parses``, for the syntax check).
    ``calls`` gets each command.
    """

    VERSION = re.compile(rb"version (\S+)'")

    def __init__(self, config, installed=None, served=None, variables=None, calls=None, missing=False, parses=None):
        self.config, self.missing, self.bootstrapping = config, missing, False
        self.served = RELEASES if served is None else served
        self.variables = {} if variables is None else variables
        self.calls = [] if calls is None else calls
        self.plugins = {}
        for name, files in (installed or {}).items():
            self._write(name, files)
        self.inner = fake_fish(self.variables, parses=parses)

    def _write(self, name, files):
        tops = set()
        for relative, data in files.items():
            path = self.config / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            tops.add("/".join(relative.split("/")[:2]))
        self.plugins[name] = sorted(tops)

    def _version(self, relative):
        path = self.config / relative
        if not path.is_file():
            return None
        match = self.VERSION.search(path.read_bytes())
        return match.group(1).decode() if match else ""

    def probe(self):
        fisher, tide = self._version("functions/fisher.fish"), self._version("functions/tide.fish")
        prompt = self.config / "functions" / "fish_prompt.fish"
        fields = ["fisher", f"fisher, version {fisher}"] if fisher is not None else ["no-fisher"]
        fields += ["tide", f"tide, version {tide}"] if tide is not None else ["no-tide"]
        fields.append("-" if self._sourced_prompt() else str(prompt) if prompt.is_file() else "n/a")
        for name, tops in self.plugins.items():
            fields += [name, str(len(tops)), *(str(self.config / top) for top in tops)]
        return fields

    def _sourced_prompt(self):
        """An active line that sources another prompt's fish_prompt, as fish -c reads config.fish and conf.d."""
        from witchy import takeover

        conf_d = self.config / "conf.d"
        files = [self.config / "config.fish"] + (sorted(conf_d.glob("*.fish")) if conf_d.is_dir() else [])
        return any(takeover.owner(line) in ("starship init", "oh-my-posh init")
                   for path in files if path.is_file()
                   for line in path.read_text(encoding="utf-8", errors="surrogateescape").splitlines())

    def fisher(self, command, names):
        if not self.bootstrapping and not (self.config / "functions" / "fisher.fish").is_file():
            return 127, "", "fish: Unknown command: fisher\n"
        done, errors = 0, ""
        for name in names:
            key = name.lower()
            if command == "remove":
                if key not in self.plugins:
                    errors += f'fisher: Plugin not installed: "{key}"\n'
                    continue
                for top in self.plugins.pop(key):
                    path = self.config / top
                    shutil.rmtree(path) if path.is_dir() else path.unlink(missing_ok=True)
                if key.split("@")[0] == "ilancosman/tide":
                    for variable in [variable for variable in self.variables if variable.startswith("tide_")]:
                        del self.variables[variable]
                done += 1
                continue
            if key not in self.served:
                errors += f'fisher: Invalid plugin name or host unavailable: "{key}"\n'
                continue
            files = self.served[key]
            tops = sorted({"/".join(relative.split("/")[:2]) for relative in files})
            conflicts = [] if key in self.plugins else [top for top in tops if (self.config / top).exists()]
            if conflicts:
                errors += (f'fisher: Cannot install "{key}": please remove or move conflicting files first:\n'
                           + "".join(f"        {self.config / top}\n" for top in conflicts))
                continue
            self._write(key, files)
            done += 1
        return (0 if done else 1), f"fisher {command} version 4.4.5\n", errors

    def run(self, args, input=None, text=False, errors="strict", **kwargs):
        from witchy import fishprobe
        from witchy.components import tide

        args = list(args)
        self.calls.append(args)
        if self.missing:
            raise FileNotFoundError(2, "No such file or directory", "fish")
        if args == ["fish", "-c", fishprobe.PROBE_SCRIPT]:
            stdout = "".join(f"{field}\0" for field in [fishprobe.SENTINEL, *self.probe()]).encode("utf-8")
            return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr=b"")
        if args[:4] == ["fish", "-c", tide.FISHER_SCRIPT, "--"]:
            code, out, err = self.fisher(args[4], args[5:])
        elif args[:4] == ["fish", "-c", tide.BOOTSTRAP_SCRIPT, "--"]:
            if b"function fisher" not in Path(args[4]).read_bytes():
                code, out, err = 127, "", "fish: Unknown command: fisher\n"
            else:
                self.bootstrapping = True
                code, out, err = self.fisher("install", args[5:])
                self.bootstrapping = False
        elif args[:4] == ["fish", "-c", tide.SWAP_SCRIPT, "--"]:
            kept = {name: value for name, value in self.variables.items() if name.startswith("tide_")}
            code, out, err = 0, "", ""
            if args[4]:
                code, out, err = self.fisher("remove", [args[4]])
            if args[5]:
                code, out, err = self.fisher("install", [args[5]])
            self.variables.update(kept)
        else:
            return self.inner(args, input=input, text=text, errors=errors, **kwargs)
        if not text:
            out, err = out.encode("utf-8"), err.encode("utf-8")
        return subprocess.CompletedProcess(args, code, stdout=out, stderr=err)


# A stand-in for fisher 4.4.5 for real fish: it installs a plugin from $WITCHY_FAKE_PLUGINS/<escaped name> instead
# of downloading it, and otherwise keeps fisher's records the way fisher does (_fisher_plugins, and each plugin's
# files in _fisher_<escaped name>_files with ~ for HOME), refuses a file that is already there, sources what it
# installs and emits the conf.d install and uninstall events.
FAKE_FISHER_FISH = r"""function fisher --argument-names cmd
    switch "$cmd"
        case -v --version
            echo "fisher, version 4.4.5"
        case install remove
            set -l code 1
            for plugin in (string lower -- $argv[2..])
                set -l var _fisher_(string escape --style=var -- $plugin)_files
                set -l targets (string replace -- \~ ~ $$var)
                if test $cmd = remove
                    if not contains -- $plugin $_fisher_plugins
                        echo "fisher: Plugin not installed: \"$plugin\"" >&2
                        continue
                    end
                    for name in (string replace --filter --regex -- '.+/conf\.d/([^/]+)\.fish$' '$1' $targets)
                        emit {$name}_uninstall
                    end
                    command rm -rf $targets
                    functions --erase (string replace --filter --regex -- '.+/functions/([^/]+)\.fish$' '$1' $targets)
                    set -e -U _fisher_plugins[(contains --index -- $plugin $_fisher_plugins)]
                    set -e -U $var
                    set code 0
                    continue
                end
                set -l source $WITCHY_FAKE_PLUGINS/(string escape --style=var -- $plugin)
                if not test -d $source
                    echo "fisher: Invalid plugin name or host unavailable: \"$plugin\"" >&2
                    continue
                end
                set -l files $source/{functions,themes,conf.d,completions}/*
                set targets (string replace -- $source $__fish_config_dir $files)
                if not contains -- $plugin $_fisher_plugins
                    set -l conflicts
                    for target in $targets
                        test -e $target; and set -a conflicts $target
                    end
                    if set -q conflicts[1]
                        echo "fisher: Cannot install \"$plugin\": please remove or move conflicting files first:" >&2
                        printf '        %s\n' $conflicts >&2
                        continue
                    end
                end
                command mkdir -p $__fish_config_dir/{functions,themes,conf.d,completions}
                for file in $files
                    command cp -RLf $file (string replace -- $source $__fish_config_dir $file)
                end
                set -U $var (string replace -- ~ \~ $targets)
                contains -- $plugin $_fisher_plugins; or set -U -a _fisher_plugins $plugin
                for file in (string match --regex -- '.+/[^/]+\.fish$' $targets)
                    source $file
                    if set -l name (string replace --regex -- '.+conf\.d/([^/]+)\.fish$' '$1' $file)
                        emit {$name}_install
                    end
                end
                set code 0
            end
            return $code
    end
end
"""
# A stand-in for a Tide release: the version, a prompt, a nested folder (as functions/tide/ is), and Tide's own
# install and uninstall handlers, which set two of its variables and erase every universal tide_ variable.
FAKE_TIDE_INIT = """\
function _tide_init_install --on-event _tide_init_install
    set -U tide_pwd_icon lean
    set -U tide_character_icon '❯'
end
function _tide_init_uninstall --on-event _tide_init_uninstall
    set -e -U (set -U --names | string match --entire -r '^_?tide')
end
"""


def fake_tide_tree(version="6.1.1"):
    return {"functions/tide.fish": f"function tide\n    echo 'tide, version {version}'\nend\n".encode(),
            "functions/fish_prompt.fish": b"function fish_prompt\n    echo 'tide> '\nend\n",
            "functions/_tide_remove_unusable_items.fish": b"function _tide_remove_unusable_items\nend\n",
            "functions/tide/configure/icons.fish": b"tide_pwd_icon x\n",
            "conf.d/_tide_init.fish": FAKE_TIDE_INIT.encode()}


def serve_plugins(folder, releases, env):
    """Write each release (``owner/repo@ref`` -> files) where FAKE_FISHER_FISH looks for it, under ``folder``.

    ``env`` is the temporary HOME's environment: fish names the folders.
    """
    names = subprocess.run([shutil.which("fish"), "-c", "string escape --style=var -- $argv", "--", *releases],
                           capture_output=True, text=True, check=True, timeout=20, env=env).stdout.split()
    for escaped, files in zip(names, releases.values()):
        for relative, data in files.items():
            path = Path(folder) / escaped / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
