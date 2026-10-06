"""fisher, Tide and the active prompt as fish sees them, read in one fish call (spec 5.1, 9.2 and D19)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .components.base import Command, ComponentFailed, run_command

FISH = "fish"
SENTINEL = "witchy-fish"  # whatever config.fish prints comes before it
TIDE_VERSION = "6.1.1"
TIDE_PLUGIN = "ilancosman/tide"
FISHER_PLUGIN = "jorgebucaran/fisher"

# Prints the sentinel; "fisher" and its --version text, or "no-fisher"; "tide" and its --version text, or
# "no-tide"; where fish_prompt comes from ("n/a" when it is not defined); then, for each fisher plugin, its name,
# its file count and its files. fisher records files with "~" for HOME; they are printed with HOME spelled out.
# Every field ends in NUL. A plugin's files are rewritten one at a time: `string replace` given no value would
# read standard input.
PROBE_SCRIPT = """\
printf '%s\\0' witchy-fish
if functions -q fisher
    printf '%s\\0' fisher "$(fisher --version 2>/dev/null)"
else
    printf '%s\\0' no-fisher
end
if functions -q tide
    printf '%s\\0' tide "$(tide --version 2>/dev/null)"
else
    printf '%s\\0' no-tide
end
printf '%s\\0' "$(functions --details fish_prompt)"
for plugin in $_fisher_plugins
    set -l files _fisher_(string escape --style=var -- $plugin)_files
    set -l paths
    for path in $$files
        set -a paths (string replace -- \\~ ~ $path)
    end
    printf '%s\\0' $plugin (count $paths) $paths
end
"""


@dataclass(frozen=True)
class Probe:
    fisher: str | None  # fisher's version, None when `fisher` is not a function
    tide: str | None  # the version `tide --version` prints, None when `tide` is not a function
    prompt_path: str | None  # `functions --details fish_prompt`, None when fish_prompt is not defined
    plugins: dict[str, list[str]]  # each fisher plugin (from _fisher_plugins), as installed, -> its files


def fields(stdout: str) -> list[str]:
    """The NUL-terminated fields printed after the sentinel."""
    head, found, rest = stdout.partition(SENTINEL + "\0")
    if not found:
        raise ValueError("fish printed no answer")
    return rest.split("\0")[:-1]


def _version(text: str, program: str) -> str:
    """``fisher, version 4.4.5`` -> ``4.4.5``; any other text is kept as printed."""
    prefix = f"{program}, version "
    return text[len(prefix):] if text.startswith(prefix) else text


def probe(ctx: Any) -> Probe:
    """Ask fish once. Raises ComponentFailed; its cause is FileNotFoundError when fish is missing."""
    done = run_command(ctx, Command((FISH, "-c", PROBE_SCRIPT), "read fisher and Tide", exact=True))
    try:
        found = fields(done.stdout)
        versions: dict[str, str | None] = {}
        index = 0
        for program in ("fisher", "tide"):
            if found[index] == program:
                versions[program], index = _version(found[index + 1], program), index + 2
            elif found[index] == f"no-{program}":
                versions[program], index = None, index + 1
            else:
                raise ValueError(f"unexpected field {found[index]!r}")
        prompt = found[index]
        index += 1
        plugins = {}
        while index < len(found):
            name, count = found[index], int(found[index + 1])
            files = found[index + 2:index + 2 + count]
            if len(files) != count:
                raise ValueError(f"the file list of {name} is cut short")
            plugins[name] = files
            index += 2 + count
    except (ValueError, IndexError) as exc:
        raise ComponentFailed(f"could not read fisher and Tide ({exc})") from exc
    return Probe(fisher=versions["fisher"], tide=versions["tide"],
                 prompt_path=None if prompt in ("n/a", "") else prompt, plugins=plugins)


def plugin_files(found: Probe, plugin: str) -> list[str] | None:
    """The files of ``plugin`` (``owner/repo``, in any case, installed with or without an ``@ref``), or None."""
    for name, files in found.plugins.items():
        base = name.lower().split("@", 1)[0]
        if base == plugin:
            return files
    return None


def tide_ready(found: Probe) -> str | None:
    """None when Tide 6.1.1 is installed and its fish_prompt is the active one; otherwise a short reason."""
    if found.tide is None:
        return "Tide not found"
    if found.tide != TIDE_VERSION:
        return f"Tide is {found.tide or 'of an unknown version'}, not {TIDE_VERSION}"
    if found.prompt_path is None or found.prompt_path not in (plugin_files(found, TIDE_PLUGIN) or []):
        return f"fish_prompt is not Tide's ({found.prompt_path or 'no fish_prompt'})"
    return None
