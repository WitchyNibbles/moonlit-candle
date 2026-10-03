"""Stand-ins for the Windows side, so no test runs cmd.exe or reg.exe."""
import subprocess


def fake_windows(echo=None, reg_query="", reg_add_code=0, calls=None):
    """A ``run`` that answers like a Windows host.

    ``cmd.exe /c echo %VAR%`` prints ``echo[VAR]`` (cmd.exe prints ``%VAR%`` back when a variable is unset),
    ``reg.exe query`` prints ``reg_query`` and ``reg.exe add`` exits with ``reg_add_code``. Any other command
    fails the test. Every call is appended to ``calls`` when it is a list.
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
            return subprocess.CompletedProcess(args, 0, stdout=reg_query, stderr="")
        if args[:2] == ["reg.exe", "add"]:
            return subprocess.CompletedProcess(args, reg_add_code, stdout="", stderr="")
        raise AssertionError(f"unexpected command in a test: {args}")
    return run
