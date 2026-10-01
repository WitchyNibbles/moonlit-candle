"""python3 -m witchy validate | build | install [--dry-run] [--wt-settings PATH] | uninstall [--dry-run]"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import build, install, validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m witchy", description="Moonlit Candle theme for Claude Code")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="check palette contrast, tokens and content")
    commands.add_parser("build", help="validate, then write dist/")
    install_parser = commands.add_parser("install", help="build and put every piece in place")
    install_parser.add_argument("--dry-run", action="store_true", help="show the changes without writing anything")
    install_parser.add_argument("--wt-settings", type=Path, help="path to Windows Terminal settings.json")
    uninstall_parser = commands.add_parser("uninstall", help="give back everything install changed")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="show the changes without writing anything")
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
    ctx = install.Context(home=Path.home(), env=os.environ, out=sys.stdout, dry_run=args.dry_run,
                          wt_settings=getattr(args, "wt_settings", None))
    return install.install(ctx) if args.command == "install" else install.uninstall(ctx)


if __name__ == "__main__":
    sys.exit(main())
