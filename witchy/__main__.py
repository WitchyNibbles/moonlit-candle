"""python3 -m witchy validate | build | install | uninstall | doctor | mood"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import build, components, runner, validate
from .context import Context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m witchy",
                                     description="Moonlit Candle theme for Claude Code and Windows Terminal")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="check palette contrast, tokens and content")
    commands.add_parser("build", help="validate, then write dist/")
    install_parser = commands.add_parser("install", help="build and put every piece in place")
    install_parser.add_argument("--dry-run", action="store_true", help="show the changes without writing anything")
    install_parser.add_argument("--wt-settings", type=Path, help="path to Windows Terminal settings.json")
    install_parser.add_argument("--only", action="append", choices=components.NAMES, metavar="NAME",
                                help=f"install only this component (repeatable): {', '.join(components.NAMES)}")
    uninstall_parser = commands.add_parser("uninstall", help="give back everything install changed")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="show the changes without writing anything")
    uninstall_parser.add_argument("--only", action="append", choices=components.NAMES, metavar="NAME",
                                  help="uninstall only this component (repeatable)")
    commands.add_parser("doctor", help="check every installed piece and say how to fix it")
    mood_parser = commands.add_parser("mood", help="show or switch the colour variant")
    mood_parser.add_argument("variant", nargs="?", help="variant to switch to")
    args = parser.parse_args(argv)

    if args.command == "validate":
        failures = validate.validate_all()
        for failure in failures:
            print(failure)
        if not failures:
            print("Moonlit Candle: all checks passed")
        return 1 if failures else 0
    if args.command == "build":
        failures = build.build()
        for failure in failures:
            print(failure)
        if failures:
            print("Validation failed; dist/ was not written.")
            return 1
        print(f"Wrote {build.DIST}")
        return 0
    ctx = Context(home=Path.home(), env=os.environ, out=sys.stdout, dry_run=getattr(args, "dry_run", False),
                  wt_settings=getattr(args, "wt_settings", None), only=tuple(getattr(args, "only", None) or ()))
    if args.command == "install":
        return runner.install(ctx)
    if args.command == "uninstall":
        return runner.uninstall(ctx)
    if args.command == "doctor":
        return runner.doctor(ctx)
    return runner.mood(ctx, args.variant)


if __name__ == "__main__":
    sys.exit(main())
