"""Write content/tide-6.1.1-defaults.json from a Tide 6.1.1 source tree (spec 6.1).

Usage: python3 scripts/tide_defaults.py <tide source folder> [<output file>]

The source folder is the one that holds Tide's ``functions/`` folder: the v6.1.1 release, unpacked from
https://codeload.github.com/IlanCosman/tide/tar.gz/refs/tags/v6.1.1, or a fish config folder that release is
installed in. Nothing in it is changed. The values are Tide's Rainbow preset as ``tide configure`` loads it:
icons.fish, then configs/rainbow.fish. Tide's development branch also calls itself 6.1.1, so the two files read
must hold the release's bytes.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

VERSION = "6.1.1"
OUTPUT = Path(__file__).resolve().parent.parent / "content" / f"tide-{VERSION}-defaults.json"
TIDE = Path("functions/tide.fish")
SUB_CONFIGURE = Path("functions/_tide_sub_configure.fish")
DETECT_OS = Path("functions/_tide_detect_os.fish")
SOURCES = (Path("functions/tide/configure/icons.fish"), Path("functions/tide/configure/configs/rainbow.fish"))
# SHA-256 of SOURCES in the v6.1.1 release tag. A development build after 6.1.1 still prints "tide, version 6.1.1"
# but adds the bun item (three more variables), so its icons.fish and rainbow.fish differ.
RELEASE = {
    SOURCES[0]: "a800efbf63092067534c593127e0008dd8d6e3e4de2b022ca308bb659e8f0d87",
    SOURCES[1]: "01b12b0ec93f4ce54846c8987f4a93cf5c394b7acc0265e7a3906cf8620bc1bb",
}
# tide configure takes the OS branding from _tide_detect_os, which differs from one machine to the next.
# The file records Tide's generic Linux branding (Tux, 080808 on CED7CF): what Tide shows when it cannot
# tell the distribution.
GENERIC_LINUX = "set -lx defaultColor 080808 CED7CF"
OS_BRANDING = {"os_branding_icon": ["\uf17c"], "os_branding_color": ["080808"], "os_branding_bg_color": ["CED7CF"]}
TIDE_COLOR = re.compile(r"^set -g (_tide_color_\w+) ([0-9A-F]{6})$", re.MULTILINE)
VARIABLE = re.compile(r"\$(\w+)")
UNSUPPORTED = set('"()[]{}*?~;&|<>\\')


def words(line: str, variables: dict[str, list[str]]) -> list[str]:
    """The words of one line of a Tide config file, as fish would read them.

    Only the syntax these files use is accepted: bare words, single quotes (with \\' and \\\\), a whole-word
    ``$name`` from ``variables``, and a ``#`` comment. Anything else raises ValueError.
    """
    result: list[str] = []
    index = 0
    while index < len(line):
        char = line[index]
        if char.isspace():
            index += 1
            continue
        if char == "#":
            break
        if char == "'":
            word, index = "", index + 1
            while True:
                if index >= len(line):
                    raise ValueError(f"unclosed quote in: {line}")
                if line.startswith(("\\'", "\\\\"), index):
                    word, index = word + line[index + 1], index + 2
                elif line[index] == "'":
                    index += 1
                    break
                else:
                    word, index = word + line[index], index + 1
            result.append(word)
            continue
        end = index
        while end < len(line) and not line[end].isspace():
            end += 1
        word, index = line[index:end], end
        match = VARIABLE.fullmatch(word)
        if match:
            if match.group(1) not in variables:
                raise ValueError(f"unknown variable ${match.group(1)} in: {line}")
            result += variables[match.group(1)]
        elif "$" in word or "'" in word or UNSUPPORTED & set(word):
            raise ValueError(f"unsupported fish syntax in: {line}")
        else:
            result.append(word)
    return result


def defaults(root: Path, release: dict[Path, str] = RELEASE) -> dict[str, list[str]]:
    """Every universal variable Tide 6.1.1's Rainbow preset sets, by name, each as a fish list.

    ``release`` maps each file of SOURCES to its SHA-256 in the release; a tree that differs is refused.
    """
    if f"'tide, version {VERSION}'" not in (root / TIDE).read_text(encoding="utf-8"):
        raise ValueError(f"{root} is not Tide {VERSION}")
    for source, digest in release.items():
        if hashlib.sha256((root / source).read_bytes()).hexdigest() != digest:
            raise ValueError(f"{root / source} is not the one in the Tide {VERSION} release "
                             f"(a development build of Tide?)")
    if GENERIC_LINUX not in (root / DETECT_OS).read_text(encoding="utf-8"):
        raise ValueError(f"{root / DETECT_OS} no longer holds Tide's generic Linux branding")
    variables = {name: [value] for name, value in
                 TIDE_COLOR.findall((root / SUB_CONFIGURE).read_text(encoding="utf-8"))}
    variables.update(OS_BRANDING)
    found: dict[str, list[str]] = {}
    for source in SOURCES:
        for line in (root / source).read_text(encoding="utf-8").splitlines():
            parts = words(line, variables)
            if not parts:
                continue
            name, values = parts[0], parts[1:]
            if name in found:
                raise ValueError(f"{name} is set twice")
            found[name] = values
    return dict(sorted(found.items()))


def to_json(found: dict[str, list[str]]) -> str:
    """One variable per line, sorted, non-ASCII as \\u escapes (Nerd Font glyphs are invisible in most editors)."""
    lines = [f"  {json.dumps(name)}: {json.dumps(values)}" for name, values in sorted(found.items())]
    return "{\n" + ",\n".join(lines) + "\n}\n"


def main(argv: list[str]) -> int:
    if not 1 <= len(argv) <= 2:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    output = Path(argv[1]) if len(argv) == 2 else OUTPUT
    try:
        found = defaults(Path(argv[0]))
        output.write_text(to_json(found), encoding="ascii")
    except (OSError, ValueError) as exc:
        print(f"tide_defaults: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {len(found)} Tide variables to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
