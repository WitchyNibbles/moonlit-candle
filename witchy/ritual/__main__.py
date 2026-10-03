"""python3 -I -B ~/.claude/witchy/ritual [--full | --omen | --sky] [--debug] [--date YYYY-MM-DD]"""
import signal
import sys
from pathlib import Path

signal.signal(signal.SIGINT, signal.SIG_DFL)  # a Ctrl-C while a shell starts must end the greeting silently


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
        message = " ".join(repr(exc).split())[:300]
        lines.append(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} greeting: {message}")
        path.write_text("\n".join(lines[-20:]) + "\n", encoding="utf-8")  # 20 is log.MAX_LINES
    except Exception:
        pass


try:
    if __package__:  # python3 -m witchy.ritual, from the repository
        from .cli import main
    else:  # the installed copy, run as a directory
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from ritual.cli import main
    sys.exit(main())
except Exception as exc:  # the greeting never breaks a shell, even when the install is half-finished
    _log_failure(exc)
    sys.exit(0)
