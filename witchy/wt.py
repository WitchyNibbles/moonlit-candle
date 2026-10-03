"""Windows Terminal: find the current user's settings.json and the profile running us."""
from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from .records import put_back, snapshot

PACKAGE = "Microsoft.WindowsTerminal_8wekyb3d8bbwe"
USERS_ROOT = Path("/mnt/c/Users")


def windows_username(run: Callable[..., Any] = subprocess.run) -> str | None:
    """The Windows user of this WSL session. Several users can have Windows Terminal installed."""
    try:
        # cwd=/mnt/c keeps cmd.exe from warning about a UNC working directory. cmd.exe answers in the OEM code
        # page, so a name like "José" is not valid UTF-8: replace instead of raising, the mangled name then
        # fails the is_file() check in locate_settings.
        done = run(["cmd.exe", "/c", "echo %USERNAME%"], capture_output=True, text=True, errors="replace",
                   timeout=5, cwd="/mnt/c")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    name = (done.stdout or "").strip()
    return name if done.returncode == 0 and name and "%" not in name else None


def settings_path_for(user: str, users_root: Path = USERS_ROOT) -> Path:
    return users_root / user / "AppData" / "Local" / "Packages" / PACKAGE / "LocalState" / "settings.json"


def locate_settings(explicit: Path | None, run: Callable[..., Any] = subprocess.run,
                    users_root: Path = USERS_ROOT) -> Path | None:
    if explicit is not None:
        return explicit if explicit.is_file() else None
    user = windows_username(run)
    if not user:
        return None
    path = settings_path_for(user, users_root)
    return path if path.is_file() else None


def _profiles(data: Any) -> list | None:
    if not isinstance(data, dict):
        return None
    profiles = data.get("profiles")
    if isinstance(profiles, list):
        return profiles
    if isinstance(profiles, dict) and isinstance(profiles.get("list"), list):
        return profiles["list"]
    return None


def _profile(data: Any, guid: str) -> dict | None:
    for profile in _profiles(data) or []:
        if isinstance(profile, dict) and str(profile.get("guid", "")).lower() == guid.lower():
            return profile
    return None


def profile(data: Any, guid: str) -> dict | None:
    """The profile with this GUID (case-insensitive), or None."""
    return _profile(data, guid)


def find_profile(data: Any, env: Mapping[str, str]) -> tuple[str | None, str | None]:
    """The profile to theme: WT_PROFILE_ID if it exists, else the one WSL profile named after the distro."""
    profiles = _profiles(data)
    if profiles is None:
        return None, "profiles list not found in Windows Terminal settings"
    wanted = env.get("WT_PROFILE_ID", "").strip()
    if wanted:
        profile = _profile(data, wanted)
        if profile is not None:
            return profile["guid"], None
    distro = env.get("WSL_DISTRO_NAME", "")
    matches = [p for p in profiles if isinstance(p, dict) and distro
               and p.get("source") == "Microsoft.WSL" and p.get("name") == distro]
    if len(matches) == 1:
        return matches[0]["guid"], None
    return None, (f"no profile matches WT_PROFILE_ID={wanted or 'unset'} and found {len(matches)} "
                  f"WSL profiles named {distro!r}")


def _scheme_index(schemes: list, name: str) -> int | None:
    return next((i for i, scheme in enumerate(schemes) if isinstance(scheme, dict) and scheme.get("name") == name), None)


def _scheme_in_use(data: Any, name: str) -> bool:
    holders = list(_profiles(data) or [])
    profiles = data.get("profiles") if isinstance(data, dict) else None
    if isinstance(profiles, dict) and isinstance(profiles.get("defaults"), dict):
        holders.append(profiles["defaults"])
    for holder in holders:
        value = holder.get("colorScheme") if isinstance(holder, dict) else None
        if value == name or (isinstance(value, dict) and name in value.values()):
            return True
    return False


def apply_scheme(data: dict, scheme: dict, guid: str, recorded: dict | None) -> tuple[dict, dict]:
    """Add or replace the scheme and point one profile at it. A reinstall keeps the first record."""
    result = copy.deepcopy(data)
    schemes_key_absent = "schemes" not in result
    schemes = result.setdefault("schemes", [])
    if not isinstance(schemes, list):
        raise ValueError("schemes in Windows Terminal settings is not a list")
    profile = _profile(result, guid)
    if profile is None:
        raise ValueError(f"profile {guid} not found")
    index = _scheme_index(schemes, scheme["name"])
    fresh = {
        "profile_guid": profile["guid"],
        "previous_color_scheme": snapshot(profile, "colorScheme"),
        "previous_scheme": {"value": copy.deepcopy(schemes[index])} if index is not None else {"absent": True},
        "schemes_key_absent": schemes_key_absent,
    }
    record = {key: copy.deepcopy(recorded[key]) if recorded else value for key, value in fresh.items()}
    record["installed_color_scheme"] = scheme["name"]
    if index is None:
        schemes.append(copy.deepcopy(scheme))
    else:
        schemes[index] = copy.deepcopy(scheme)
    profile["colorScheme"] = scheme["name"]
    return result, record


def restore_scheme(data: dict, record: dict) -> tuple[dict, list[str]]:
    """Undo apply_scheme, leaving alone whatever the user changed since."""
    result = copy.deepcopy(data)
    warnings = []
    name = record["installed_color_scheme"]
    profile = _profile(result, record["profile_guid"])
    if profile is None:
        warnings.append(f"Windows Terminal profile {record['profile_guid']} no longer exists; its colour scheme was not restored.")
    elif profile.get("colorScheme") == name:
        put_back(profile, "colorScheme", record["previous_color_scheme"])
    elif snapshot(profile, "colorScheme") == record["previous_color_scheme"]:
        pass  # already given back, for example by an uninstall that stopped part-way
    else:
        warnings.append("The Windows Terminal profile colour scheme was changed after install; leaving it as it is.")
    schemes = result.get("schemes")
    index = _scheme_index(schemes, name) if isinstance(schemes, list) else None
    if index is not None:
        previous = record["previous_scheme"]
        if not previous.get("absent"):
            schemes[index] = copy.deepcopy(previous["value"])
        elif _scheme_in_use(result, name):
            warnings.append(f"The Windows Terminal scheme {name!r} is still used by a profile; keeping it.")
        else:
            del schemes[index]
            if record["schemes_key_absent"] and not schemes:
                del result["schemes"]
    return result, warnings


def manual_snippet(scheme: dict, guid: str) -> str:
    body = json.dumps(scheme, indent=4, ensure_ascii=False)
    return (
        'Add this object to the "schemes" list:\n'
        f"{body}\n"
        f'Then, in the profile with "guid": "{guid}", set:\n'
        f'    "colorScheme": "{scheme["name"]}"'
    )
