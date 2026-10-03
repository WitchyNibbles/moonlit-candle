"""python3 -I ~/.claude/witchy/ritual [--full | --omen | --sky] [--debug] [--date YYYY-MM-DD]"""
import signal
import sys
from pathlib import Path

signal.signal(signal.SIGINT, signal.SIG_DFL)  # a Ctrl-C while a shell starts must end the greeting silently

if __package__:  # python3 -m witchy.ritual, from the repository
    from .cli import main
else:  # the installed copy, run as a directory
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ritual.cli import main

sys.exit(main())
