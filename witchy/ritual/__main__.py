"""python3 -I -B ~/.claude/witchy/ritual [--full | --omen | --sky | --caret] [--debug] [--date YYYY-MM-DD]"""
import signal
import sys
from pathlib import Path

signal.signal(signal.SIGINT, signal.SIG_DFL)  # a Ctrl-C while a shell starts must end the greeting silently
MAX_LINES = 20  # log.MAX_LINES and log.MAX_CHARS; a test keeps them equal
MAX_CHARS = 300


def _log_failure(exc: Exception) -> None:
    """Append one line to the ritual log with stdlib calls only: the log module may be what failed to import."""
    try:
        import time
        path = Path.home() / ".cache" / "witchy" / "ritual.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        message = " ".join(f"greeting: {exc!r}".split())[:MAX_CHARS]
        lines.append(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {message}")
        path.write_text("\n".join(lines[-MAX_LINES:]) + "\n", encoding="utf-8")
    except Exception:
        pass


try:
    if __package__:  # python3 -m witchy.ritual, from the repository
        from .cli import main
    else:  # the installed copy, run as a directory
        # Load this folder as the package "ritual" without adding its parent to sys.path: a stray json.py
        # there would shadow the stdlib, and appending it instead would let another "ritual" stand in for this one.
        import importlib.util
        here = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location("ritual", here / "__init__.py",
                                                      submodule_search_locations=[str(here)])
        sys.modules["ritual"] = package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        from ritual.cli import main
    sys.exit(main())
except Exception as exc:  # the greeting never breaks a shell, even when the install is half-finished
    _log_failure(exc)
    sys.exit(0)
