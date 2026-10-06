# Plan H: Windows Terminal Purge, Seasonal Caret and Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows Terminal loses `PastelOneDark` (and gets it back on uninstall), the prompt caret wears the sabbat's colour on a sabbat and its eve, `python3 -m witchy preview` draws the prompt without fish or Tide, and the shell-ritual spec stops promising the pink prompt.

**Architecture:** `wt.purge_schemes` / `wt.restore_purged` / `wt.purged_uses` work on the parsed `settings.json` beside `apply_scheme` and `restore_scheme`, inside the write the `windows-terminal` component already makes (Task 1). A new `witchy/ritual/caret.py` turns a day into the caret cache, and the sky job writes it before it moves the sky (`ritual --sky`) or on its own (`ritual --caret`) (Task 2). `conf.d/witchy.fish` reads the cache with fish `read` in every shell, Tide's non-interactive prompt child included, and starts `ritual --caret` once a day (Task 3). doctor prints a `caret:` line and accepts the caret global only when it holds today's colour (Task 4). `witchy/preview.py` copies, for five sample states, what Tide 6.1.1 does when it draws the prompt, from `build.tide(variant)` (Task 5). Task 6 edits the shell-ritual spec.

**Tech Stack:** Python 3.10+ standard library only (`copy`, `re`, `tempfile`, `datetime`, `argparse`, `unittest`); fish 3.7 for the real-fish tests.

**Spec:** `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (revision 2, as Plans F and G left it), sections 8, the `windows-terminal` line of 9.1, 15.2, 15.3, the docs part of 13, the `test_wt.py`, `test_preview.py` and seasonal-caret lines of 12, and acceptance criteria 9 and 10. It builds on `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` ("ritual" below), sections 4.5 and 6. Tasks that change behaviour or correct the spec edit it in the same commit (15.2, 15.3, 13). Plan H is the last of three and executes after Plans F (prompt ownership) and G (the `tide` component, install banner, `install --fresh`, `doctor --fix`). It is written against `proto/plan-g` at `47cec01`, which holds both.

## Global Constraints

- Python 3.10 or newer, standard library only. Every test passes on `/usr/bin/python3` (3.12) and `/home/eimi/.pyenv/versions/3.10.0/bin/python3`.
- Test command, from the repo root: `/usr/bin/python3 -m unittest discover -s tests -t .`, and the same with the 3.10 interpreter. `python3 -m witchy validate` must print `Moonlit Candle: all checks passed`.
- No test touches the real `~/.claude`, `~/.cache`, `~/.config/fish`, fish universal variables, Windows Terminal, `cmd.exe`, `reg.exe`, the registry or the network. Use `tests/fakes.py`, `--wt-settings` with a fixture, and temporary folders. Tests that run real fish set `HOME` and `XDG_CONFIG_HOME` to a temporary folder and are skipped when fish is missing.
- **Every manual run of witchy code uses a temporary HOME and XDG_CONFIG_HOME** (`HOME=$(mktemp -d)`), including `preview`, `ritual --caret` and the fish templates. Never use `fish --no-config` for Tide work: it also turns off universal variables.
- Never run a real `install`, `uninstall` or `mood`. `install --dry-run` with `--wt-settings` pointing at a fixture in a temporary folder is allowed (Task 1, Step 6).
- Exit codes do not change anywhere.
- Messages, docstrings and comments are English and neutral in tone. Plan prose and code comments never use the witchy voice.
- Lines stay within 120 characters (a few older lines in `wt.py`, `windows_terminal.py`, `moon.py`, `test_fish_files.py`, `test_components_wt.py` and `test_install.py` are longer; leave them).
- Commit messages end with the `Co-Authored-By:` trailer of the model that wrote the commit. The commit blocks below show the prototype's message; keep the subject and body, and put your own trailer.
- SDD workspaces go under `.superpowers/sdd/` (git-excluded).

## Decisions

Given with the task:

1. **The caret cache is refreshed daily, not only when the moon-phase bin changes.** Before this plan the sky job started only when `_witchy_moon_bin` differed from `sky-bin`, and only in Windows Terminal with `ritual-config.json`. Task 3 makes `conf.d/witchy.fish` start the job as `ritual --caret` when the cache's first line is not today's date, on any interactive shell that is not doctor's, unless the job failed today. When the phase moved in Windows Terminal it starts `ritual --sky` instead, which writes the cache first; a shell starts at most one job. Task 2 gives the job its `--caret` mode.

Made while prototyping (each task's **Decisions** block has the details):

2. **Prototype first.** Every task was built test-first on `proto/plan-h` (on `proto/plan-g` at `47cec01`), one commit per task. Every stage is green on both interpreters with `validate` clean, and each task's new tests were run against the previous stage's source: the counts of failures are in each task's Step 2. Test counts: 766 → 781 → 797 → 809 → 818 → 829 → 829 (each run also reports `skipped=2`: Plan G's opt-in network tests).
3. **The caret cache holds two lines, today's and tomorrow's (spec deviation).** Spec 15.3 described one line. With one line, the first shell of a sabbat would read yesterday's file and stay gold until the job ran. With two, the job run on any day also covers the next one: `2026-10-30 FFB86B samhain` then `2026-10-31 FFB86B samhain`. Only the line whose date is today counts. Task 2 corrects spec 15.3.
4. **The caret is read before `status is-interactive`.** Tide draws the prompt in a background `fish -c` child, which sources `conf.d` but is not interactive; a global set only in the interactive shell never reaches it. Checked with Tide 6.1.1's own `_tide_item_character` in a temporary HOME: with today's cache the child prints `\e[38;2;255;184;107m❯` (`FFB86B`), with a stale one `\e[38;2;255;212;119m❯` (`FFD477`). The read costs one `date +%F` per prompt draw, and only when the cache file exists.
5. **Purge record and restore order (Task 1).** The entry's `purged` key holds `{"defaults": {"previous", "installed"} | null, "profiles": {guid: previous}, "schemes": [{"index", "value"}]}`; the first install's value of each wins, and later installs add what is new. Uninstall runs `restore_purged` before `restore_scheme`: while `profiles.defaults` still names "Moonlit Candle", `restore_scheme` would keep the witchy scheme as "still used by a profile".
6. **A `{"light": …, "dark": …}` colour-scheme pair that names a purged scheme is purged whole,** and given back whole (Task 1). A profile without a string `guid` is left alone: it could not be found again on uninstall.
7. **Caret write failures** are logged as `sky: could not write the caret cache (…)` and mark the day failed (`sky-fail`), like other sky-job errors; the sky step still runs (Task 2). doctor's existing `sky:` line shows them.
8. **doctor's `caret:` line (Task 4):** an info line (Plan G's `info` level, printed `·`, never a problem): `· caret: gold` or `· caret: samhain FFB86B (today's cache)`; ⚠ when the cache holds no line for today (`… was written on <date>, not today` or `… is damaged`, fix: show the log; `no caret cache yet; a new tab writes it`, no fix). A cache written yesterday holds today's line and passes. The global-shadow check accepts `tide_character_color` only when its value is exactly `[today's colour]`.
9. **preview (Task 5)** draws five samples at the terminal's width with today's moon and time; the golden files hold them at 80 columns on 2026-10-31 21:13 UTC. The failed command exits 2: with `character` on the left, Tide shows no status item for exit 1 and only turns the caret rose-red. Its escapes are fish's in effect, not byte for byte: `\e[0m` for fish's `\e(B\e[m`, `\e[49m` for `-b normal`, and no escape for an empty `set_color`. Compared once with Tide 6.1.1's `_tide_2_line_prompt` in a temporary HOME: the same glyphs, colours and order. `--variant` defaults to `palette.DEFAULT_VARIANT`, not the installed one. Plan F's rebuilt defaults (158 merged names, no `bun` item) change no sample: the golden files are the same bytes before and after the rebase onto Plan G.
10. **The shell-ritual spec's section 1 Success line also said "the pink Tide prompt"** (spec 13 named only line 438); Task 6 rewords both and records that in spec 13.
11. **Plan G interplay.** This plan does not touch `witchy/runner.py`, `witchy/components/__init__.py`, `witchy/components/base.py`, `witchy/components/tide.py` or `tests/fakes.py`. In `witchy/__main__.py` (Plan G's version, with `--fresh` and `doctor --fix`) it adds one import pair, one subparser and one dispatch block before the `Context` is built. Plan G's takeover never scans witchy's own fish files, so the `set -g tide_character_color $colour` that `conf.d/witchy.fish` now holds is never disabled. Every README and `__main__.py` block this plan quotes is the text as Plan G left it. `doctor --fix` is Plan G's; this plan only adds lines that `--fix` leaves alone (the caret ⚠ lines carry no witchy command).

## Review Focus

1. **This PC's `settings.json`, with the user editing it between install and uninstall:** `PastelOneDark` as the default, on PowerShell and cmd, and defined. Install removes every trace; uninstall gives back every byte, except what the user changed since, which stays with one warning each. Tests: Task 1 `test_this_pcs_pastel_one_dark_is_purged_and_uninstall_gives_back_every_byte`, `test_uninstall_gives_every_value_back_in_place`, `test_uninstall_leaves_what_the_user_changed_since`, `test_uninstall_twice_is_silent_and_a_deleted_profile_is_skipped`.
2. **Colour-scheme values and settings in other shapes:** a light/dark pair, a reinstall after the user put `PastelOneDark` back or gave it to a new profile, a `schemes` list the user deleted, an entry from before the purge, `profiles` that is not an object. Tests: Task 1 `test_a_light_and_dark_pair_that_names_a_purged_scheme_is_purged_whole`, `test_a_reinstall_keeps_the_first_record`, `test_a_reinstall_records_a_profile_that_took_the_scheme_since`, `test_uninstall_puts_back_a_schemes_list_the_user_deleted`, `test_an_entry_from_before_the_purge_restores_as_before`, `test_purged_uses_names_every_place`.
3. **A caret cache from another day, or damaged:** tomorrow's line only, yesterday's colour, lower-case hex, `#`, text that looks like fish code, an empty file, a folder, an unreadable file. Every shell stays gold and prints nothing; doctor warns. Tests: Task 3 `test_other_days_leave_it_gold`, `test_a_damaged_cache_leaves_it_gold`, `test_a_missing_or_unreadable_cache_leaves_it_gold`; Task 2 `test_read_skips_damaged_lines`; Task 4 `test_a_damaged_or_missing_cache_is_a_warning`, `test_a_stale_cache_is_a_warning_with_the_log`.
4. **Day boundaries and time zones:** the first shell of a sabbat before the job ran, the day after Samhain, a season sabbat a time zone moves, New Year into Imbolc, doctor with a time-zone-aware `now`. Tests: Task 3 `test_samhain_eve_and_day_are_amber_and_the_day_after_gold` (acceptance 10), `test_yesterdays_second_line_covers_the_first_shell_of_today`; Task 2 `test_a_time_zone_moves_a_season_date`, `test_across_new_year_and_into_imbolc`; Task 4 `test_an_aware_now_uses_the_local_day`.
5. **Which shells start a job, and how many:** Tide's non-interactive prompt children (one per prompt draw), doctor's `fish -i -c`, a failure today, no Python or greeting package, a moved phase in Windows Terminal (only `--sky`), outside Windows Terminal (`--caret`). And doctor accepts only the caret global with exactly today's colour. Tests: Task 3 `test_nothing_after_a_failure_today_in_the_doctors_shell_or_a_non_interactive_one`, `test_a_moved_phase_starts_only_the_sky_job_which_writes_the_caret_too`, `test_starts_it_outside_windows_terminal_and_without_the_sky_config`, `test_nothing_without_python_or_the_greeting_package`; Task 4 `test_the_caret_global_is_accepted_only_with_todays_colour`, `test_only_the_caret_colour_is_accepted`, real-fish `test_doctor_accepts_the_caret_global_only_while_it_holds_todays_colour`.

## Scope → tasks

| Task | Spec |
|---|---|
| 1 | 8 (purge, record, restore), 9.1 `windows-terminal` line, 12 `test_wt.py`, acceptance 2 (the Windows Terminal part) |
| 2 | 15.3 first and third bullets (the cache file, write failures), 12 seasonal caret (fixed dates) |
| 3 | 15.3 second bullet (fish `read`, today only), daily refresh (Decision 1), 12 seasonal caret (fish integration), acceptance 10 |
| 4 | 15.3 doctor bullet, 9.1 global-shadow exception |
| 5 | 15.2, 12 `test_preview.py`, acceptance 9, README entry |
| 6 | 13 docs part |

## File structure

| Task | Source | Tests | Data and docs |
|---|---|---|---|
| 1 | `witchy/palette.py`, `witchy/wt.py`, `witchy/components/windows_terminal.py` | `tests/test_wt.py`, `tests/test_components_wt.py`, `tests/test_install.py` | `README.md` |
| 2 | `witchy/ritual/caret.py` (new), `witchy/ritual/sky.py`, `witchy/ritual/cli.py`, `witchy/ritual/__main__.py` | `tests/test_caret.py` (new), `tests/test_sky_job.py`, `tests/test_ritual_cli.py` | spec 15.3 |
| 3 | `content/fish/conf.d/witchy.fish` | `tests/test_fish_files.py` | spec 15.3, `README.md` |
| 4 | `witchy/components/fish.py` | `tests/test_components_fish.py`, `tests/test_fish_integration.py` | spec 15.3, `README.md` |
| 5 | `witchy/preview.py` (new), `witchy/__main__.py` | `tests/test_preview.py` (new), `tests/golden/prompt-{home,git,unwritable,failed,jobs}.txt` (new) | spec 15.2, `README.md` |
| 6 | none | none | `docs/superpowers/specs/2026-10-02-shell-ritual-design.md`, spec 13 |

Order: Task 3 needs Task 2's `caret.write` (its acceptance test) and `ritual --caret`; Task 4 needs Task 2's `caret.read`; Tasks 1, 5 and 6 stand alone. Test counts in each step assume this order.

## Interfaces produced

```python
# witchy/palette.py
PURGED_SCHEMES: tuple[str, ...] = ("PastelOneDark",)

# witchy/wt.py
def purge_schemes(data: dict, names: Iterable[str], replacement: str, recorded: dict | None) -> tuple[dict, dict]
def restore_purged(data: dict, record: dict | None) -> tuple[dict, list[str]]
def purged_uses(data: Any, name: str) -> list[str]     # "schemes", "profiles.defaults", "profile '<name>'"
# windows-terminal entry: "purged": {"defaults": {"previous": snapshot, "installed": str} | None,
#                                    "profiles": {guid: snapshot}, "schemes": [{"index": int, "value": dict}]}

# witchy/ritual/caret.py
NAME = "caret"
EVE_DAYS = 1
LINE: re.Pattern                                       # "<YYYY-MM-DD>" or "<YYYY-MM-DD> <HEX> <sabbat>"
def colour(day: date, tz: tzinfo | None) -> tuple[str, str] | None   # ("samhain", "FFB86B")
def line(day: date, tz: tzinfo | None) -> str
def text(day: date, tz: tzinfo | None) -> str          # today's line and tomorrow's
def write(path: Path, day: date, tz: tzinfo | None) -> None          # atomic; OSError
def read(path: Path) -> dict[str, tuple[str, str] | None]            # OSError without a file

# witchy/ritual/sky.py
def run(home: Path, now: datetime, move_sky: bool = True) -> int
# ritual CLI: --caret (exclusive with --full, --omen, --sky) runs sky.run(home, now, move_sky=False)

# witchy/components/fish.py
CARET = "tide_character_color"
def caret_check(ctx) -> Check

# witchy/preview.py
SAMPLES: tuple[Sample, ...]                            # home, git, unwritable, failed, jobs
def prompt(tide: Mapping[str, str], sample: Sample, now: datetime, columns: int) -> list[str]   # two lines
def render(variant: str = palette.DEFAULT_VARIANT, now: datetime | None = None, columns: int = 80) -> str
# CLI: python3 -m witchy preview [--variant NAME]; exit 0
```

---
### Task 1: Windows Terminal loses PastelOneDark, and uninstall gives it back

**Items:**
- Spec 8: `palette.PURGED_SCHEMES`; in the write the component already makes, `profiles.defaults.colorScheme` becomes "Moonlit Candle" when it names a purged scheme, every profile that names one loses its `colorScheme`, and the definitions are deleted. Each previous value is recorded first-install-wins and given back on uninstall, leaving alone what the user changed since.
- Spec 9.1: `windows-terminal` doctor ✗ while a purged scheme is still defined or referenced.

**Files:**
- Modify: `witchy/palette.py` (`PURGED_SCHEMES`, before `STATUSLINE`)
- Modify: `witchy/wt.py` (`Iterable` import; `_names`, `_defaults`, `purge_schemes`, `restore_purged`, `purged_uses` before `manual_snippet`)
- Modify: `witchy/components/windows_terminal.py` (`plan`'s `build`, `restore`'s `give_back`, `check`)
- Modify: `README.md` (one "It installs" line, one Troubleshooting row)
- Test: `tests/test_wt.py`, `tests/test_components_wt.py`, `tests/test_install.py`

**Interfaces:**
- Consumes: `wt._profiles`, `wt._profile`, `wt.profile`, `wt.apply_scheme`, `wt.restore_scheme`, `records.snapshot`, `records.put_back`, `palette.WT_SCHEME`, `palette.THEME_NAME`, `base.Check`, `base.fix_command`.
- Produces: `palette.PURGED_SCHEMES`; `wt.purge_schemes(data, names, replacement, recorded) -> (data, record)`; `wt.restore_purged(data, record | None) -> (data, warnings)`; `wt.purged_uses(data, name) -> list[str]`; the entry key `purged` (shape in "Interfaces produced"); the doctor line `✗ windows-terminal  PastelOneDark is still in settings.json: <places>` with fix `python3 -m witchy install --only windows-terminal`.

**Decisions:**
1. **Restore order:** `restore_purged` runs before `restore_scheme`. `restore_scheme` keeps the witchy scheme when `_scheme_in_use` finds it, and `profiles.defaults` names it until the purge is undone.
2. **First install wins, per item:** the defaults record is kept once set; a profile is recorded once per GUID (any case); a scheme definition once per name. A reinstall still purges whatever came back, and records what is new (a profile that took the scheme since).
3. **"Changed after install" for each kind:** the default no longer holds "Moonlit Candle"; a profile has any `colorScheme` again; a scheme of that name exists and is not the recorded one. Each leaves the value alone with one warning. A deleted profile is skipped silently; a deleted `schemes` list is created again.
4. **A light/dark pair** that names a purged scheme in either member is removed whole and given back whole; witchy does not write half a pair.
5. **The doctor line names the places** (`schemes`, `profiles.defaults`, `profile '<name>'`) so the user can see what came back, and has no ✓ twin: the existing ✓ lines already say the component is healthy.

- [ ] **Step 1: Write the failing tests**

In `tests/test_wt.py`, after `ApplyRestoreTest` (after `test_manual_snippet`, before the blank lines and `CANONICAL = …`), add:

```python
CMD = "{0caa0dad-35be-5f56-a8ff-afceeeaa6101}"
PASTEL = {"name": "PastelOneDark", "background": "#282C34", "foreground": "#F5C6E0"}
CAMPBELL = {"name": "Campbell", "background": "#0C0C0C", "foreground": "#CCCCCC"}


def pastel_settings():
    """This PC before the purge: PastelOneDark is the default scheme, set on PowerShell and cmd, and defined."""
    data = settings()
    data["profiles"]["defaults"] = {"colorScheme": "PastelOneDark", "font": {"face": "Cascadia Mono"}}
    for profile in data["profiles"]["list"][:2]:
        profile["colorScheme"] = "PastelOneDark"
    data["schemes"] = [copy.deepcopy(PASTEL), copy.deepcopy(CAMPBELL)]
    return data


def installed(data, recorded=None):
    """apply_scheme, then the purge, as the component does."""
    result, record = wt.apply_scheme(data, palette.WT_SCHEME, UBUNTU, recorded)
    result, record["purged"] = wt.purge_schemes(result, palette.PURGED_SCHEMES, palette.THEME_NAME,
                                                (recorded or {}).get("purged"))
    return result, record


def uninstalled(data, record):
    """restore_purged, then restore_scheme, as the component does."""
    result, warnings = wt.restore_purged(data, record["purged"])
    result, more = wt.restore_scheme(result, record)
    return result, warnings + more


class PurgeTest(unittest.TestCase):
    def test_the_default_profiles_and_definition_lose_the_purged_scheme(self):
        result, record = installed(pastel_settings())
        self.assertEqual(result["profiles"]["defaults"], {"colorScheme": "Moonlit Candle",
                                                          "font": {"face": "Cascadia Mono"}})
        profiles = {p["guid"]: p for p in result["profiles"]["list"]}
        self.assertNotIn("colorScheme", profiles[POWERSHELL])
        self.assertNotIn("colorScheme", profiles[CMD])
        self.assertEqual(result["schemes"], [CAMPBELL, palette.WT_SCHEME])
        self.assertEqual(record["purged"], {
            "defaults": {"previous": {"value": "PastelOneDark"}, "installed": "Moonlit Candle"},
            "profiles": {POWERSHELL: {"value": "PastelOneDark"}, CMD: {"value": "PastelOneDark"}},
            "schemes": [{"index": 0, "value": PASTEL}],
        })
        self.assertEqual([wt.purged_uses(result, name) for name in palette.PURGED_SCHEMES], [[]])

    def test_uninstall_gives_every_value_back_in_place(self):
        original = pastel_settings()
        restored, warnings = uninstalled(*installed(original))
        self.assertEqual((restored, warnings), (original, []))
        self.assertEqual(list(restored["profiles"]["list"][0]), ["guid", "name", "colorScheme"])

    def test_a_light_and_dark_pair_that_names_a_purged_scheme_is_purged_whole(self):
        data = pastel_settings()
        data["profiles"]["list"][0]["colorScheme"] = {"light": "Campbell", "dark": "PastelOneDark"}
        result, record = installed(data)
        self.assertNotIn("colorScheme", wt.profile(result, POWERSHELL))
        self.assertEqual(record["purged"]["profiles"][POWERSHELL],
                         {"value": {"light": "Campbell", "dark": "PastelOneDark"}})
        self.assertEqual(uninstalled(result, record), (data, []))

    def test_settings_without_the_purged_scheme_record_nothing(self):
        result, record = installed(settings())
        self.assertEqual(record["purged"], {"defaults": None, "profiles": {}, "schemes": []})
        self.assertEqual(result["profiles"]["defaults"], {})
        self.assertEqual(uninstalled(result, record), (settings(), []))

    def test_a_reinstall_keeps_the_first_record(self):
        first_data, first = installed(pastel_settings())
        again = copy.deepcopy(first_data)
        again["profiles"]["defaults"]["colorScheme"] = "PastelOneDark"  # put back by hand, then reinstalled
        again["schemes"].append({"name": "PastelOneDark", "background": "#000000"})
        second_data, second = installed(again, first)
        self.assertEqual(second["purged"], first["purged"])
        self.assertEqual(second_data, first_data)

    def test_a_reinstall_records_a_profile_that_took_the_scheme_since(self):
        first_data, first = installed(pastel_settings())
        again = copy.deepcopy(first_data)
        wt.profile(again, UBUNTU)["colorScheme"] = "Moonlit Candle"
        again["profiles"]["list"].append({"guid": "{22222222-2222-2222-2222-222222222222}", "name": "Azure",
                                          "colorScheme": "PastelOneDark"})
        _, second = installed(again, first)
        self.assertEqual(second["purged"]["profiles"]["{22222222-2222-2222-2222-222222222222}"],
                         {"value": "PastelOneDark"})
        self.assertEqual(second["purged"]["profiles"][POWERSHELL], {"value": "PastelOneDark"})

    def test_uninstall_leaves_what_the_user_changed_since(self):
        result, record = installed(pastel_settings())
        result["profiles"]["defaults"]["colorScheme"] = "Campbell"
        wt.profile(result, POWERSHELL)["colorScheme"] = "Campbell"
        result["schemes"].insert(0, {"name": "PastelOneDark", "background": "#111111"})
        restored, warnings = uninstalled(result, record)
        self.assertEqual(restored["profiles"]["defaults"]["colorScheme"], "Campbell")
        self.assertEqual(wt.profile(restored, POWERSHELL)["colorScheme"], "Campbell")
        self.assertEqual(wt.profile(restored, CMD)["colorScheme"], "PastelOneDark")
        self.assertEqual(restored["schemes"][0], {"name": "PastelOneDark", "background": "#111111"})
        self.assertEqual(len(warnings), 3)
        self.assertTrue(all("after install" in warning for warning in warnings), warnings)

    def test_uninstall_twice_is_silent_and_a_deleted_profile_is_skipped(self):
        original = pastel_settings()
        result, record = installed(original)
        once, _ = uninstalled(result, record)
        self.assertEqual(wt.restore_purged(once, record["purged"]), (original, []))
        result["profiles"]["list"] = [p for p in result["profiles"]["list"] if p["guid"] != CMD]
        restored, warnings = uninstalled(result, record)
        self.assertEqual((len(restored["profiles"]["list"]), warnings), (2, []))

    def test_uninstall_puts_back_a_schemes_list_the_user_deleted(self):
        result, record = installed(pastel_settings())
        del result["schemes"]
        restored, _ = wt.restore_purged(result, record["purged"])
        self.assertEqual(restored["schemes"], [PASTEL])

    def test_an_entry_from_before_the_purge_restores_as_before(self):
        result, _ = installed(pastel_settings())
        self.assertEqual(wt.restore_purged(result, None), (result, []))

    def test_the_witchy_scheme_is_never_purged(self):
        self.assertNotIn(palette.WT_SCHEME["name"], palette.PURGED_SCHEMES)

    def test_purged_uses_names_every_place(self):
        data = pastel_settings()
        self.assertEqual(wt.purged_uses(data, "PastelOneDark"),
                         ["schemes", "profiles.defaults", "profile 'Windows PowerShell'",
                          "profile 'Símbolo del sistema'"])
        self.assertEqual(wt.purged_uses(data, "Campbell"), ["schemes"])
        self.assertEqual(wt.purged_uses({"profiles": "odd", "schemes": {}}, "PastelOneDark"), [])

```

In `tests/test_components_wt.py`, in `WindowsTerminalComponentTest`, before `test_recorded_settings_path_is_reused_without_cmd_exe`, add:

```python
    def test_check_fails_while_a_purged_scheme_is_defined_or_used(self):
        ctx, entry = self.install()
        data = json.loads(self.wt.read_text(encoding="utf-8"))
        data["profiles"]["defaults"]["colorScheme"] = "PastelOneDark"
        data["schemes"].append({"name": "PastelOneDark", "background": "#282C34"})
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        fails = [(c.message, c.fix) for c in self.component.check(ctx, entry) if c.level == "fail"]
        self.assertEqual(fails, [("PastelOneDark is still in settings.json: schemes, profiles.defaults",
                                  "python3 -m witchy install --only windows-terminal")])

    def test_install_purges_pastel_one_dark_and_uninstall_gives_it_back(self):
        data = json.loads(json.dumps(WT))
        data["profiles"]["defaults"]["colorScheme"] = "PastelOneDark"
        data["schemes"] = [{"name": "PastelOneDark", "background": "#282C34"}]
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        ctx, entry = self.install()
        after = json.loads(self.wt.read_text(encoding="utf-8"))
        self.assertEqual(after["profiles"]["defaults"], {"colorScheme": "Moonlit Candle"})
        self.assertEqual([scheme["name"] for scheme in after["schemes"]], ["Moonlit Candle"])
        self.assertEqual(entry["purged"]["schemes"], [{"index": 0, "value": data["schemes"][0]}])
        self.assertEqual({c.level for c in self.component.check(ctx, entry)}, {"ok"})
        apply_changes(ctx, self.component.restore(self.ctx(stamp="20261002-130000"), entry).changes)
        self.assertEqual(json.loads(self.wt.read_text(encoding="utf-8")), data)

```

In `tests/test_install.py`, in `InstallTest`, before `test_install_twice_is_idempotent`, add:

```python
    def test_this_pcs_pastel_one_dark_is_purged_and_uninstall_gives_back_every_byte(self):
        data = json.loads(json.dumps(WT_ORIGINAL))
        data["profiles"]["defaults"]["colorScheme"] = "PastelOneDark"
        for profile in data["profiles"]["list"][:2]:
            profile["colorScheme"] = "PastelOneDark"
        data["schemes"] = [{"name": "PastelOneDark", "background": "#282C34", "foreground": "#F5C6E0"}]
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        before = self.snapshot()
        self.assertEqual(install.install(self.ctx()), 0)
        self.assertNotIn("PastelOneDark", self.wt.read_text(encoding="utf-8"))
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)

```

- [ ] **Step 2: Run the new tests and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_wt tests.test_components_wt tests.test_install`
Expected: `Ran 115 tests` and `FAILED (failures=3, errors=12)`. The twelve `PurgeTest` errors are `AttributeError: module 'witchy.wt' has no attribute 'purge_schemes'` (ten), `… 'purged_uses'` (one) and `module 'witchy.palette' has no attribute 'PURGED_SCHEMES'` (one). The three failures: `test_check_fails_while_a_purged_scheme_is_defined_or_used` (`Lists differ: [] != [('PastelOneDark is still in settings.json…`), `test_install_purges_pastel_one_dark_and_uninstall_gives_it_back` (`{'colorScheme': 'PastelOneDark'} != {'colorScheme': 'Moonlit Candle'}`) and `test_this_pcs_pastel_one_dark_is_purged_and_uninstall_gives_back_every_byte` (`'PastelOneDark' unexpectedly found in …`).

- [ ] **Step 3: Implement**

In `witchy/palette.py`, before:

```python
# Order matters: build.py writes this dict into statusline.py's PALETTE block verbatim.
STATUSLINE: dict[str, str] = {
```

add:

```python
# Windows Terminal schemes the windows-terminal component takes out of settings.json (spec 8): the default
# scheme becomes WT_SCHEME, profiles that name one inherit the default, and their definitions go.
PURGED_SCHEMES: tuple[str, ...] = ("PastelOneDark",)

```

In `witchy/wt.py`, replace:

```python
from typing import Any, Callable, Mapping
```

with:

```python
from typing import Any, Callable, Iterable, Mapping
```

and, before `def manual_snippet(scheme: dict, guid: str) -> str:`, add:

```python
def _names(value: Any, names: Iterable[str]) -> bool:
    """Whether a colorScheme value, a name or a {"light": …, "dark": …} pair, names one of ``names``."""
    names = tuple(names)
    if isinstance(value, dict):
        return any(isinstance(member, str) and member in names for member in value.values())
    return isinstance(value, str) and value in names


def _defaults(data: Any) -> dict | None:
    profiles = data.get("profiles") if isinstance(data, dict) else None
    defaults = profiles.get("defaults") if isinstance(profiles, dict) else None
    return defaults if isinstance(defaults, dict) else None


def purge_schemes(data: dict, names: Iterable[str], replacement: str, recorded: dict | None) -> tuple[dict, dict]:
    """Take the ``names`` schemes out of settings.json (spec 8).

    profiles.defaults gets ``replacement`` when it names one, a profile that names one loses its colorScheme so
    it inherits the default, and their definitions are deleted. What each held is recorded; a reinstall keeps
    the first record of each and adds the new ones.
    """
    names = tuple(names)
    result = copy.deepcopy(data)
    earlier = recorded or {}
    record = {"defaults": copy.deepcopy(earlier.get("defaults")),
              "profiles": copy.deepcopy(earlier.get("profiles", {})),
              "schemes": copy.deepcopy(earlier.get("schemes", []))}
    defaults = _defaults(result)
    if defaults is not None and _names(defaults.get("colorScheme"), names):
        if record["defaults"] is None:
            record["defaults"] = {"previous": snapshot(defaults, "colorScheme"), "installed": replacement}
        defaults["colorScheme"] = replacement
    for profile in _profiles(result) or []:
        if not (isinstance(profile, dict) and isinstance(profile.get("guid"), str)):
            continue  # a profile without a GUID could not be found again on uninstall
        if _names(profile.get("colorScheme"), names):
            if not any(guid.lower() == profile["guid"].lower() for guid in record["profiles"]):
                record["profiles"][profile["guid"]] = snapshot(profile, "colorScheme")
            del profile["colorScheme"]
    schemes = result.get("schemes")
    if isinstance(schemes, list):
        known = {item["value"].get("name") for item in record["schemes"]}
        purged = [index for index, scheme in enumerate(schemes)
                  if isinstance(scheme, dict) and scheme.get("name") in names]
        record["schemes"] += [{"index": index, "value": copy.deepcopy(schemes[index])} for index in purged
                              if schemes[index].get("name") not in known]
        result["schemes"] = [scheme for index, scheme in enumerate(schemes) if index not in purged]
    return result, record


def restore_purged(data: dict, record: dict | None) -> tuple[dict, list[str]]:
    """Undo purge_schemes, leaving alone whatever the user changed since. Runs before restore_scheme, so the
    witchy scheme is no longer the default when that one decides whether it is still in use."""
    result = copy.deepcopy(data)
    warnings: list[str] = []
    if not record:
        return result, warnings  # installed before the purge existed
    if record.get("schemes"):
        schemes = result.setdefault("schemes", [])
        if not isinstance(schemes, list):
            warnings.append("schemes in Windows Terminal settings is not a list; the purged schemes were not "
                            "given back.")
        else:
            given: list[dict] = []
            for item in sorted(record["schemes"], key=lambda item: item["index"]):
                name = item["value"].get("name")
                present = [scheme for scheme in schemes if isinstance(scheme, dict) and scheme.get("name") == name
                           and not any(scheme is mine for mine in given)]
                if item["value"] in present:
                    continue  # already given back
                if present:
                    warnings.append(f"The Windows Terminal scheme {name!r} was added again after install; "
                                    "leaving it as it is.")
                    continue
                scheme = copy.deepcopy(item["value"])
                schemes.insert(min(item["index"], len(schemes)), scheme)
                given.append(scheme)
    defaults_record = record.get("defaults")
    defaults = _defaults(result)
    if defaults_record and defaults is not None and snapshot(defaults, "colorScheme") != defaults_record["previous"]:
        if defaults.get("colorScheme") == defaults_record["installed"]:
            put_back(defaults, "colorScheme", defaults_record["previous"])
        else:
            warnings.append("The Windows Terminal default colour scheme was changed after install; "
                            "leaving it as it is.")
    for guid, previous in (record.get("profiles") or {}).items():
        profile = _profile(result, guid)
        if profile is None or snapshot(profile, "colorScheme") == previous:
            continue  # the profile was deleted, or this one was already given back
        if "colorScheme" in profile:
            warnings.append(f"The colour scheme of Windows Terminal profile {profile.get('name', guid)!r} was "
                            "changed after install; leaving it as it is.")
            continue
        put_back(profile, "colorScheme", previous)
    return result, warnings


def purged_uses(data: Any, name: str) -> list[str]:
    """Where settings.json still defines or uses the scheme ``name``: "schemes", "profiles.defaults", profiles."""
    places = []
    schemes = data.get("schemes") if isinstance(data, dict) else None
    if isinstance(schemes, list) and any(isinstance(s, dict) and s.get("name") == name for s in schemes):
        places.append("schemes")
    defaults = _defaults(data)
    if defaults is not None and _names(defaults.get("colorScheme"), (name,)):
        places.append("profiles.defaults")
    places += [f"profile {profile.get('name', profile.get('guid'))!r}" for profile in _profiles(data) or []
               if isinstance(profile, dict) and _names(profile.get("colorScheme"), (name,))]
    return places


```

In `witchy/components/windows_terminal.py`, in `plan`'s inner `build`, replace:

```python
            new_data, record = wt.apply_scheme(data, scheme, guid, entry)
            recorded = (entry or {}).get("profile_keys")
```

with:

```python
            new_data, record = wt.apply_scheme(data, scheme, guid, entry)
            new_data, record["purged"] = wt.purge_schemes(new_data, palette.PURGED_SCHEMES, scheme["name"],
                                                          (entry or {}).get("purged"))
            recorded = (entry or {}).get("profile_keys")
```

In `restore`'s inner `give_back`, replace:

```python
            restored, notes = wt.restore_scheme(data, entry)
            restored, more = wt.restore_profile_keys(restored, entry["profile_guid"], entry.get("profile_keys", {}))
            return restored, notes + more
```

with:

```python
            # The purge first: restore_scheme keeps the witchy scheme while profiles.defaults still names it.
            restored, purged = wt.restore_purged(data, entry.get("purged"))
            restored, notes = wt.restore_scheme(restored, entry)
            restored, more = wt.restore_profile_keys(restored, entry["profile_guid"], entry.get("profile_keys", {}))
            return restored, purged + notes + more
```

In `check`, replace:

```python
        records = entry.get("files") or []
        if records:
```

with:

```python
        for purged in palette.PURGED_SCHEMES:
            places = wt.purged_uses(data, purged)
            if places:
                checks.append(Check("fail", self.name, f"{purged} is still in {path.name}: " + ", ".join(places),
                                    fix))
        records = entry.get("files") or []
        if records:
```

- [ ] **Step 4: Document it in the README**

In `README.md`, after the "It installs" line that starts `- On your WSL profile in Windows Terminal:`, add:

```markdown
- Windows Terminal's default colour scheme becomes "Moonlit Candle" when it was `PastelOneDark`; that old scheme is removed from every profile and from `schemes` (uninstall gives it back)
```

In the Troubleshooting table, after the row that starts ``| `✗ windows-terminal  changed or missing: …` ``, add:

```markdown
| `✗ windows-terminal  PastelOneDark is still in settings.json: …` | an old scheme is still defined, the default, or set on a profile | `python3 -m witchy install --only windows-terminal` (uninstall gives it back) |
```

- [ ] **Step 5: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 781 tests … OK (skipped=2)` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 6: Dry-run against a fixture (read-only)**

Run:
```bash
H=$(mktemp -d)
cat > "$H/settings.json" <<'EOF'
{
    "profiles": {
        "defaults": {"colorScheme": "PastelOneDark"},
        "list": [
            {"guid": "{61c54bbd-c2c6-5271-96e7-009a87ff44bf}", "name": "Windows PowerShell", "colorScheme": "PastelOneDark"},
            {"guid": "{05f3f843-450a-55ad-a264-cacf368dafe5}", "name": "Ubuntu", "source": "Microsoft.WSL"}
        ]
    },
    "schemes": [{"name": "PastelOneDark", "background": "#282C34"}]
}
EOF
env HOME="$H" XDG_CONFIG_HOME="$H/.config" WT_PROFILE_ID="{05f3f843-450a-55ad-a264-cacf368dafe5}" PATH=/usr/bin:/bin \
    /usr/bin/python3 -m witchy install --dry-run --only windows-terminal --wt-settings "$H/settings.json" | grep PastelOneDark
ls -A "$H"
```
Expected: only `-` lines hold `PastelOneDark` (the defaults line, the PowerShell profile and the `schemes` line); the `+` side has `"colorScheme": "Moonlit Candle"` under `defaults` and no `colorScheme` on PowerShell. `ls` prints only `settings.json`: the dry run wrote nothing.

- [ ] **Step 7: Commit**

```bash
git add witchy/palette.py witchy/wt.py witchy/components/windows_terminal.py README.md tests/test_wt.py tests/test_components_wt.py tests/test_install.py
git commit -m "feat: Windows Terminal loses PastelOneDark: default, profiles and definition, all given back on uninstall" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 2: The sky job writes the caret cache

**Items:**
- Spec 15.3, first and third bullets: the sky job writes `~/.cache/witchy/caret`; colours from the sabbat colours of `palette.RITUAL`; a write failure goes to `ritual.log`.
- Decision 1 (Python side): `ritual --caret` writes the cache and leaves the sky alone; `ritual --sky` writes it, then moves the sky.
- Spec 12, seasonal caret: fixed dates for a sabbat day, the day before and an ordinary day; a damaged cache.

**Files:**
- Create: `witchy/ritual/caret.py`
- Modify: `witchy/ritual/sky.py` (docstring, import, `_failed`, `run`)
- Modify: `witchy/ritual/cli.py` (docstring, `--caret`, dispatch)
- Modify: `witchy/ritual/__main__.py` (usage docstring)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (15.3, first and third bullets)
- Test: `tests/test_caret.py` (new), `tests/test_sky_job.py`, `tests/test_ritual_cli.py`

**Interfaces:**
- Consumes: `wheel.upcoming(day, tz) -> (name, days) | None` (days 0–7, across New Year), `wheel.sabbat_dates`, `ritual.palette.PALETTE` (the variant's ritual colours; `build.ritual_package` rewrites the block, so the installed copy holds the installed variant's), `log.append`, `sky.CACHE`, `sky.FAIL`.
- Produces: `caret.NAME`, `caret.EVE_DAYS`, `caret.LINE`, `caret.colour`, `caret.line`, `caret.text`, `caret.write`, `caret.read` (signatures in "Interfaces produced"); `sky.run(home, now, move_sky=True)`; the `ritual --caret` mode; the log line `sky: could not write the caret cache (<error>)`.

**Decisions:**
1. **Two lines** (plan Decision 3). `caret.text(day)` is `line(day) + line(day + 1)`, each line ending in `\n`.
2. **The format fish can check without Python:** a date, then an upper-case six-digit hex colour without `#` (Tide's own colour format), then the sabbat's lower-case name. `caret.LINE` accepts exactly that or a date alone; `read` skips any other line.
3. **The module lives in the greeting package** (`witchy/ritual/`), which is installed to `~/.claude/witchy/ritual/`: the sky job runs from there with `python3 -I -B`, so it can import only the package's own modules. `build.ritual_package` copies every `*.py` of the folder, so `caret.py` ships without a build change.
4. **The caret step runs first and on its own:** a failure there logs and marks the day failed, then the sky step still runs, because a broken cache file must not leave the moon on last week's phase. The day check (`sky-fail` holds today) still stops both, as before.
5. **`--caret` ignores `--date`, like `--sky`:** the job always works on the real now, so a preview never writes tomorrow's cache.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_caret.py`:

```python
import tempfile
import unittest
from datetime import date, timedelta, timezone
from pathlib import Path

from witchy import palette as theme
from witchy.ritual import caret, palette, wheel

UTC = timezone.utc


class ColourTest(unittest.TestCase):
    def test_the_sabbat_and_its_eve_take_its_colour(self):
        self.assertEqual(caret.colour(date(2026, 10, 30), UTC), ("samhain", "FFB86B"))
        self.assertEqual(caret.colour(date(2026, 10, 31), UTC), ("samhain", "FFB86B"))

    def test_other_days_are_gold(self):
        for day in (date(2026, 10, 29), date(2026, 11, 1), date(2026, 10, 5)):
            with self.subTest(day=day):
                self.assertIsNone(caret.colour(day, UTC))

    def test_every_sabbat_wears_its_greeting_colour(self):
        for name, day in wheel.sabbat_dates(2027, UTC).items():
            with self.subTest(name=name):
                expected = (name.lower(), theme.RITUAL[name.lower()].lstrip("#"))
                self.assertEqual(caret.colour(day, UTC), expected)
                self.assertEqual(caret.colour(day - timedelta(days=1), UTC), expected)
                self.assertIsNone(caret.colour(day + timedelta(days=1), UTC))

    def test_a_time_zone_moves_a_season_date(self):
        # The 2026 December solstice is 2026-12-21 20:50 UTC, already 12-22 east of UTC+3:10.
        east = timezone(timedelta(hours=9))
        self.assertIsNone(caret.colour(date(2026, 12, 22), UTC))
        self.assertEqual(caret.colour(date(2026, 12, 22), east), ("yule", "E6DCEE"))

    def test_the_colours_come_from_the_installed_palette_block(self):
        self.assertEqual(palette.PALETTE["samhain"], "#FFB86B")


class TextTest(unittest.TestCase):
    def test_today_and_tomorrow(self):
        self.assertEqual(caret.text(date(2026, 10, 30), UTC), "2026-10-30 FFB86B samhain\n2026-10-31 FFB86B samhain\n")
        self.assertEqual(caret.text(date(2026, 10, 31), UTC), "2026-10-31 FFB86B samhain\n2026-11-01\n")
        self.assertEqual(caret.text(date(2026, 10, 5), UTC), "2026-10-05\n2026-10-06\n")

    def test_across_new_year_and_into_imbolc(self):
        self.assertEqual(caret.text(date(2026, 12, 31), UTC), "2026-12-31\n2027-01-01\n")
        self.assertEqual(caret.text(date(2027, 1, 30), UTC), "2027-01-30\n2027-01-31 F3EAF7 imbolc\n")


class FileTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "cache" / "witchy" / caret.NAME

    def test_write_creates_the_folder_and_replaces_the_file_whole(self):
        caret.write(self.path, date(2026, 10, 30), UTC)
        self.assertEqual(self.path.read_text(encoding="utf-8"),
                         "2026-10-30 FFB86B samhain\n2026-10-31 FFB86B samhain\n")
        caret.write(self.path, date(2026, 11, 1), UTC)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "2026-11-01\n2026-11-02\n")
        self.assertEqual([p.name for p in self.path.parent.iterdir()], [caret.NAME])

    def test_read_returns_each_well_formed_line(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("2026-10-31 FFB86B samhain\n2026-11-01\n", encoding="utf-8")
        self.assertEqual(caret.read(self.path), {"2026-10-31": ("samhain", "FFB86B"), "2026-11-01": None})

    def test_read_skips_damaged_lines(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"2026-10-31 #FFB86B samhain\n2026-10-31 ffb86b samhain\n\xff\xfe\n"
                              b"2026-11-01 FFB86B\n2026-11-02 FFB86B samhain; rm\n2026-11-03\n")
        self.assertEqual(caret.read(self.path), {"2026-11-03": None})

    def test_read_raises_when_there_is_no_file(self):
        with self.assertRaises(OSError):
            caret.read(self.path)


if __name__ == "__main__":
    unittest.main()
```

In `tests/test_sky_job.py`, replace:

```python
from witchy.ritual import log, moon, sky
```

with:

```python
from witchy.ritual import caret, log, moon, sky
```

and, in `SkyJobTest`, before `test_shares_names_with_the_installer`, add:

```python
    def test_writes_the_caret_cache_for_today_and_tomorrow(self):
        eve = datetime(2026, 10, 30, 8, 0, tzinfo=timezone(timedelta(hours=1)))
        self.run_job(eve)
        self.assertEqual((self.cache / caret.NAME).read_text(encoding="utf-8"),
                         "2026-10-30 FFB86B samhain\n2026-10-31 FFB86B samhain\n")
        self.assertEqual(self.background(), wt.SKY_VALUES[moon.phase_bin(eve)])

    def test_the_caret_alone_needs_no_config_and_leaves_the_sky(self):
        (self.home / sky.CONFIG).unlink()
        self.assertEqual(sky.run(self.home, FULL_MOON, move_sky=False), 0)
        self.assertEqual((self.cache / caret.NAME).read_text(encoding="utf-8"), "2026-10-26\n2026-10-27\n")
        self.assertEqual(self.background(), wt.SKY_VALUES[1])
        self.assertEqual(sorted(path.name for path in self.cache.iterdir()), [caret.NAME])

    def test_a_caret_that_cannot_be_written_is_logged_and_the_sky_still_moves(self):
        (self.cache / caret.NAME).mkdir(parents=True)
        self.run_job()
        self.assertEqual(self.background(), wt.SKY_VALUES[4])
        self.assertIn("sky: could not write the caret cache", log.last(self.cache / log.NAME))
        self.assertEqual((self.cache / sky.FAIL).read_text(encoding="utf-8"), "2026-10-26\n")

    def test_after_a_failure_today_the_caret_waits_for_tomorrow_too(self):
        self.cache.mkdir(parents=True)
        (self.cache / sky.FAIL).write_text("2026-10-26\n", encoding="utf-8")
        sky.run(self.home, FULL_MOON, move_sky=False)
        self.assertFalse((self.cache / caret.NAME).exists())

```

In `tests/test_ritual_cli.py`, in `SkyModeTest`, before `test_sky_and_another_mode_is_an_argument_error`, add:

```python
    def test_caret_runs_the_job_without_the_sky_on_now(self):
        with mock.patch.object(sky, "run", return_value=0) as run:
            self.assertEqual(self.run_cli(["--caret", "--date", "2026-12-24"]), "")
        run.assert_called_once_with(self.home, SAMHAIN_NIGHT, move_sky=False)
        self.assertFalse(self.stamp.exists())

```

and in `test_sky_and_another_mode_is_an_argument_error`, replace:

```python
        for mode in ("--full", "--omen"):
```

with:

```python
        for mode in ("--full", "--omen", "--caret"):
```

- [ ] **Step 2: Run the new tests and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_caret tests.test_sky_job tests.test_ritual_cli`
Expected: `Ran 34 tests` and `FAILED (failures=1, errors=3)`: `tests.test_caret` and `tests.test_sky_job` fail to import (`ImportError: cannot import name 'caret' from 'witchy.ritual'`), `test_caret_runs_the_job_without_the_sky_on_now` errors (argparse exits on `--caret`), and `test_sky_and_another_mode_is_an_argument_error [--caret]` fails with `ritual: error: unrecognized arguments: --caret`.

- [ ] **Step 3: Implement**

Create `witchy/ritual/caret.py`:

```python
"""~/.cache/witchy/caret: the prompt caret's colour on a sabbat and its eve (prompt takeover spec 15.3).

The sky job writes two lines, today's and tomorrow's: "<YYYY-MM-DD> <HEX> <sabbat>" when that day or the next
is a sabbat, else "<YYYY-MM-DD>". conf.d/witchy.fish reads the line for today with fish's read and sets a
global tide_character_color; tomorrow's line lets the first shell of a day show the right caret before the job
has run. doctor reads the file too.
"""
from __future__ import annotations

import os
import re
import tempfile
from datetime import date, timedelta, tzinfo
from pathlib import Path

from . import palette, wheel

NAME = "caret"
EVE_DAYS = 1  # the day before a sabbat wears its colour too
LINE = re.compile(r"(\d{4}-\d\d-\d\d)(?: ([0-9A-F]{6}) ([a-z]+))?")


def colour(day: date, tz: tzinfo | None) -> tuple[str, str] | None:
    """The sabbat on ``day`` or the day after, and its colour as Tide writes it (no "#"); None for gold."""
    found = wheel.upcoming(day, tz)
    if found is None or found[1] > EVE_DAYS:
        return None
    name = found[0].lower()
    return name, palette.PALETTE[name].lstrip("#").upper()


def line(day: date, tz: tzinfo | None) -> str:
    found = colour(day, tz)
    return day.isoformat() if found is None else f"{day.isoformat()} {found[1]} {found[0]}"


def text(day: date, tz: tzinfo | None) -> str:
    """The whole file: the line for ``day`` and the line for the day after."""
    return "".join(line(day + timedelta(days=offset), tz) + "\n" for offset in (0, 1))


def write(path: Path, day: date, tz: tzinfo | None) -> None:
    """Replace the file whole, so a shell never reads half of it. Raises OSError."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text(day, tz))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read(path: Path) -> dict[str, tuple[str, str] | None]:
    """Each well-formed line's date and its (sabbat, colour), or None for gold. Raises OSError without a file."""
    found = {}
    for entry in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LINE.fullmatch(entry)
        if match:
            found[match.group(1)] = (match.group(3), match.group(2)) if match.group(2) else None
    return found
```

In `witchy/ritual/sky.py`, replace:

```python
"""The sky job: point the Windows Terminal profile's backgroundImage at tonight's phase image (spec 4.5).
```

with:

```python
"""The sky job: point the Windows Terminal profile's backgroundImage at tonight's phase image (spec 4.5), and
write the caret cache for today (prompt takeover spec 15.3).
```

replace:

```python
from . import log, moon
```

with:

```python
from . import caret, log, moon
```

and replace the whole `run` function:

```python
def run(home: Path, now: datetime) -> int:
    """Move the sky to ``now``'s phase. Failures are logged and retried at most once a day; always exits 0."""
    cache = home / CACHE
    today = now.date().isoformat()
    fail = cache / FAIL
    try:
        if fail.read_text(encoding="utf-8").strip() == today:
            return 0
    except (OSError, ValueError):
        pass
    try:
        config = json.loads((home / CONFIG).read_text(encoding="utf-8"))
        update(config, cache / LOCK, cache / STAMP, moon.phase_bin(now))
    except Exception as exc:  # the job runs in the background: it must never surface a traceback
        try:
            cache.mkdir(parents=True, exist_ok=True)
            fail.write_text(today + "\n", encoding="utf-8")
        except OSError:
            pass
        log.append(cache / log.NAME, f"sky: {exc}", now)
    return 0
```

with:

```python
def _failed(cache: Path, now: datetime, message: str) -> None:
    """Log ``message`` and mark today as failed, so shells start no job again until tomorrow."""
    try:
        cache.mkdir(parents=True, exist_ok=True)
        (cache / FAIL).write_text(now.date().isoformat() + "\n", encoding="utf-8")
    except OSError:
        pass
    log.append(cache / log.NAME, f"sky: {message}", now)


def run(home: Path, now: datetime, move_sky: bool = True) -> int:
    """Write the caret cache for ``now``'s day, then move the sky to ``now``'s phase unless ``move_sky`` is
    False. Failures are logged and retried at most once a day; always exits 0."""
    cache = home / CACHE
    try:
        if (cache / FAIL).read_text(encoding="utf-8").strip() == now.date().isoformat():
            return 0
    except (OSError, ValueError):
        pass
    try:
        caret.write(cache / caret.NAME, now.date(), now.tzinfo)
    except Exception as exc:  # the job runs in the background: it must never surface a traceback
        _failed(cache, now, f"could not write the caret cache ({exc})")
    if not move_sky:
        return 0
    try:
        config = json.loads((home / CONFIG).read_text(encoding="utf-8"))
        update(config, cache / LOCK, cache / STAMP, moon.phase_bin(now))
    except Exception as exc:
        _failed(cache, now, str(exc))
    return 0
```

In `witchy/ritual/cli.py`, replace:

```python
"""The greeting: the full ritual, the one-line omen, or the sky job (spec 6)."""
```

with:

```python
"""The greeting: the full ritual, the one-line omen, or the sky job (spec 6) with or without the sky."""
```

replace:

```python
    mode.add_argument("--sky", action="store_true", help="move the Windows Terminal sky to tonight's phase")
```

with:

```python
    mode.add_argument("--sky", action="store_true",
                      help="move the Windows Terminal sky to tonight's phase and write the caret cache")
    mode.add_argument("--caret", action="store_true", help="write the caret cache only")
```

and replace:

```python
        if args.date and not args.sky:  # the sky job always works on the real now
            # the same wall time, with the local UTC offset of that day (it differs across a DST change)
            now = datetime.combine(args.date, now.time()).astimezone()
        if args.sky:
            return sky.run(home, now)
```

with:

```python
        if args.date and not (args.sky or args.caret):  # the sky job always works on the real now
            # the same wall time, with the local UTC offset of that day (it differs across a DST change)
            now = datetime.combine(args.date, now.time()).astimezone()
        if args.sky:
            return sky.run(home, now)
        if args.caret:
            return sky.run(home, now, move_sky=False)
```

In `witchy/ritual/__main__.py`, replace the first line:

```python
"""python3 -I -B ~/.claude/witchy/ritual [--full | --omen | --sky] [--debug] [--date YYYY-MM-DD]"""
```

with:

```python
"""python3 -I -B ~/.claude/witchy/ritual [--full | --omen | --sky | --caret] [--debug] [--date YYYY-MM-DD]"""
```

- [ ] **Step 4: Correct the spec**

In `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md`, section 15.3, replace the first bullet:

```markdown
- The daily sky job (ritual 4.5) also writes `~/.cache/witchy/caret`: `<YYYY-MM-DD> <HEX> <sabbat>` when today or tomorrow is a sabbat, else `<YYYY-MM-DD>` alone. Colours come from `palette.RITUAL` (the sabbat colours, already contrast-checked against the background).
```

with:

```markdown
- The sky job (ritual 4.5) also writes `~/.cache/witchy/caret`, two lines: one for today and one for tomorrow, each `<YYYY-MM-DD> <HEX> <sabbat>` when that day or the next is a sabbat, else `<YYYY-MM-DD>` alone (on 2026-10-31: `2026-10-31 FFB86B samhain`, then `2026-11-01`). Tomorrow's line lets the first shell of a day show the right caret before the job has run that day. Colours come from `palette.RITUAL` (the sabbat colours, already contrast-checked against the background), upper case and without `#`. `ritual --caret` writes the file and leaves the sky alone; `ritual --sky` writes it, then moves the sky.
```

and the third bullet:

```markdown
- A missing, stale or damaged file leaves the caret gold. A write failure goes to `ritual.log` like other sky-job errors.
```

with:

```markdown
- A missing, stale or damaged file leaves the caret gold. A write failure goes to `ritual.log` as a `sky:` line and marks the day failed (`sky-fail`), like other sky-job errors; the sky step still runs.
```

- [ ] **Step 5: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 797 tests … OK (skipped=2)` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 6: Commit**

```bash
git add witchy/ritual/caret.py witchy/ritual/sky.py witchy/ritual/cli.py witchy/ritual/__main__.py tests/test_caret.py tests/test_sky_job.py tests/test_ritual_cli.py docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: the sky job writes the caret cache: a sabbat's colour on the day and its eve" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 3: New shells take the caret colour from today's cache, and the job refreshes it daily

**Items:**
- Spec 15.3, second bullet: `conf.d/witchy.fish` reads the cache with `read` (no Python) and sets `set -g tide_character_color <HEX>` only from today's line; the universal value stays gold.
- Decision 1 (fish side): start `ritual --caret` once a day.
- Spec 12, seasonal caret: a fish integration test that `conf.d/witchy.fish` sets the global only from today's file; acceptance criterion 10.

**Files:**
- Modify: `content/fish/conf.d/witchy.fish` (whole file below)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (15.3, second bullet and a new daily-refresh bullet)
- Modify: `README.md` (the sky-job paragraph under "The greeting")
- Test: `tests/test_fish_files.py`

**Interfaces:**
- Consumes: Task 2's cache format and `caret.write` (the acceptance test writes the file the job would write), `ritual --caret`, `ritual --sky`; `_witchy_moon_bin`; the `@PYTHON@`, `@WITCHY_DIR@`, `@EZA_COLORS@` placeholders of `build.fish_files`.
- Produces: in every fish shell that reads `conf.d` (interactive or not, doctor's included) a global `tide_character_color` holding today's colour when the cache has one; on interactive shells that are not doctor's, at most one background job: `ritual --sky` (Windows Terminal, phase moved) or `ritual --caret` (cache not written today).

**Decisions:**
1. **Before `status is-interactive`** (plan Decision 4). The block uses only `test`, `read`, `string match` and one `date +%F`, and calls `date` only when the cache is readable.
2. **Only a six-digit upper-case hex colour is used** (`string match -qr '^[0-9A-F]{6}$'`). The value reaches `set -g` as a variable, never as code, so `FFB86B; echo hacked` or `(echo FFB86B)` in the file is only a colour that does not match.
3. **"Written today" is the first line's date.** The job writes today's line first; a file whose first line is yesterday's still has today's colour in its second line, but the job runs again to write tomorrow's.
4. **The job's preconditions change:** it needs an interactive shell that is not doctor's, an executable `@PYTHON@` and the greeting package (`ritual/__main__.py`), and no failure today. The sky step still needs `WT_SESSION` and `ritual-config.json`, as before; the caret step needs neither.
5. **Every shell test starts with today's cache** (`FishTestCase.setUp`), so the existing greeting and sky-job tests stay about what they test; the job-start helpers move to `JobStartTestCase`, shared by `SkyJobStartTest` and the new `CaretJobStartTest`.
6. **Acceptance 10 is tested with a stand-in `date`** that prints the day under test, placed first on `PATH`, reading the file `caret.write` produces for the day the job ran.

- [ ] **Step 1: Write the failing tests**

In `tests/test_fish_files.py`, replace:

```python
from witchy.ritual import moon
```

with:

```python
from witchy.ritual import caret, moon
```

In `FishTestCase.setUp`, replace:

```python
        self.witchy = self.home / ".claude" / "witchy"
        self.cache = self.home / ".cache" / "witchy"
        (self.witchy / "ritual").mkdir(parents=True)
```

with:

```python
        self.witchy = self.home / ".claude" / "witchy"
        self.cache = self.home / ".cache" / "witchy"
        (self.witchy / "ritual").mkdir(parents=True)
        # Today's caret cache, so no shell starts the caret job unless a test means it to.
        self.cache.mkdir(parents=True)
        self.write_caret(f"{date.today().isoformat()}\n")
```

and, before `def fish(self, script, *args, interactive=False, env=None):`, add:

```python
    def write_caret(self, text):
        (self.cache / "caret").write_text(text, encoding="utf-8")

```

Replace the head of `SkyJobStartTest` up to its first test:

```python
class SkyJobStartTest(FishTestCase):
    """Whether the job started is read from fish_trace, which prints every command before it runs. That is
    synchronous, so a job that was not started is a fact, not a timeout. The starting cases are the controls
    that prove the trace can see the job."""

    WT = {"WT_SESSION": "f00d"}

    def setUp(self):
        super().setUp()
        (self.witchy / "ritual-config.json").write_text("{}", encoding="utf-8")
        self.cache.mkdir(parents=True)
        self.bin = moon.phase_bin(datetime.now(timezone.utc))

    def start_shell(self, env=None, interactive=True, session=True):
        return self.fish("true", interactive=interactive, env={**(self.WT if session else {}), **(env or {})})

    def sky_job_started(self, interactive=True, session=True):
        """Starts a shell with tracing on and says whether it ran the --sky command. It also checks that the
        trace saw the file that decides, so that an empty trace cannot pass for "did not start"."""
        done = self.start_shell({"fish_trace": "1"}, interactive, session)
        lines = done.stderr.splitlines()
        self.assertTrue(any(re.search(r"source .*conf\.d/witchy\.fish$", line) for line in lines), done.stderr[-500:])
        return any(re.search(r"^-+> .*/ritual'? --sky$", line) for line in lines)

    def wait_for_python(self):
        deadline = time.monotonic() + 5
        while self.python_args() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        return self.python_args()

    def test_starts_the_job_when_the_phase_moved(self):
```

with:

```python
class JobStartTestCase(FishTestCase):
    """Whether the job started is read from fish_trace, which prints every command before it runs. That is
    synchronous, so a job that was not started is a fact, not a timeout. The starting cases are the controls
    that prove the trace can see the job."""

    WT = {"WT_SESSION": "f00d"}

    def setUp(self):
        super().setUp()
        (self.witchy / "ritual-config.json").write_text("{}", encoding="utf-8")
        self.bin = moon.phase_bin(datetime.now(timezone.utc))

    def start_shell(self, env=None, interactive=True, session=True):
        return self.fish("true", interactive=interactive, env={**(self.WT if session else {}), **(env or {})})

    def sky_job_started(self, interactive=True, session=True, mode="--sky", env=None):
        """Starts a shell with tracing on and says whether it ran the job with ``mode``. It also checks that the
        trace saw the file that decides, so that an empty trace cannot pass for "did not start"."""
        done = self.start_shell({"fish_trace": "1", **(env or {})}, interactive, session)
        lines = done.stderr.splitlines()
        self.assertTrue(any(re.search(r"source .*conf\.d/witchy\.fish$", line) for line in lines), done.stderr[-500:])
        return any(re.search(rf"^-+> .*/ritual'? {mode}$", line) for line in lines)

    def wait_for_python(self):
        deadline = time.monotonic() + 5
        while self.python_args() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        return self.python_args()


class SkyJobStartTest(JobStartTestCase):
    def test_starts_the_job_when_the_phase_moved(self):
```

After `SkyJobStartTest` (before `if __name__ == "__main__":`), add:

```python
class CaretJobStartTest(JobStartTestCase):
    """The same job, started once a day for the caret cache (prompt takeover spec 15.3)."""

    def setUp(self):
        super().setUp()
        (self.cache / "sky-bin").write_text(f"{self.bin}\n", encoding="utf-8")  # the sky is current
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        self.write_caret(f"{yesterday}\n{date.today().isoformat()}\n")

    def test_starts_the_caret_job_when_the_cache_is_not_from_today(self):
        self.assertTrue(self.sky_job_started(mode="--caret"))
        self.assertEqual(self.wait_for_python()[:4], ["-I", "-B", f"{self.witchy}/ritual", "--caret"])

    def test_starts_it_outside_windows_terminal_and_without_the_sky_config(self):
        (self.witchy / "ritual-config.json").unlink()
        self.assertTrue(self.sky_job_started(session=False, mode="--caret"))

    def test_starts_it_when_there_is_no_cache_yet(self):
        (self.cache / "caret").unlink()
        self.assertTrue(self.sky_job_started(mode="--caret"))

    def test_a_moved_phase_starts_only_the_sky_job_which_writes_the_caret_too(self):
        (self.cache / "sky-bin").write_text(f"{(self.bin + 1) % 8}\n", encoding="utf-8")
        self.assertTrue(self.sky_job_started())
        self.assertFalse(self.sky_job_started(mode="--caret"))

    def test_nothing_after_a_failure_today_in_the_doctors_shell_or_a_non_interactive_one(self):
        (self.cache / "sky-fail").write_text(date.today().isoformat() + "\n", encoding="utf-8")
        self.assertFalse(self.sky_job_started(mode="--caret"))
        (self.cache / "sky-fail").unlink()
        self.assertFalse(self.sky_job_started(mode="--caret", env={"WITCHY_DOCTOR": "1"}))
        self.assertFalse(self.sky_job_started(mode="--caret", interactive=False))
        self.assertIsNone(self.python_args())

    def test_nothing_without_python_or_the_greeting_package(self):
        (self.witchy / "ritual" / "__main__.py").unlink()
        self.assertFalse(self.sky_job_started(mode="--caret"))
        self.python.unlink()
        self.assertFalse(self.sky_job_started(mode="--caret"))


class CaretTest(FishTestCase):
    """conf.d/witchy.fish sets the caret colour from today's line of the cache, in every shell that reads conf.d."""

    def caret(self, interactive=False, env=None):
        done = self.fish("set -q -U tide_character_color; and echo universal; "
                         "set -q -g tide_character_color; and echo $tide_character_color; or echo gold",
                         interactive=interactive, env=env)
        self.assertEqual(done.stderr, "")
        return done.stdout.strip()

    def day(self, offset=0):
        return (date.today() + timedelta(days=offset)).isoformat()

    def test_todays_line_sets_a_global_in_tides_child_shell_and_in_a_new_tab(self):
        self.write_caret(f"{self.day()} FFB86B samhain\n{self.day(1)}\n")
        self.assertEqual(self.caret(), "FFB86B")  # Tide draws the prompt in a non-interactive fish -c
        self.assertEqual(self.caret(interactive=True), "FFB86B")
        self.assertEqual(self.caret(interactive=True, env={"WITCHY_DOCTOR": "1"}), "FFB86B")

    def test_yesterdays_second_line_covers_the_first_shell_of_today(self):
        self.write_caret(f"{self.day(-1)} FFB86B samhain\n{self.day()} FFB86B samhain\n")
        self.assertEqual(self.caret(), "FFB86B")

    def test_other_days_leave_it_gold(self):
        for text in (f"{self.day(-1)} FFB86B samhain\n{self.day()}\n", f"{self.day(-2)} FFB86B samhain\n",
                     f"{self.day(1)} FFB86B samhain\n", f"{self.day()}\n{self.day(1)} FFB86B samhain\n"):
            with self.subTest(text=text):
                self.write_caret(text)
                self.assertEqual(self.caret(), "gold")

    def test_a_damaged_cache_leaves_it_gold(self):
        for text in (f"{self.day()} #FFB86B samhain\n", f"{self.day()} ffb86b samhain\n",
                     f"{self.day()} FFB86B; echo hacked\n", f"{self.day()} (echo FFB86B)\n", "", "\n\n",
                     f"\xff\xfe {self.day()} FFB86B\n"):
            with self.subTest(text=text):
                self.write_caret(text)
                self.assertEqual(self.caret(), "gold")

    def test_samhain_eve_and_day_are_amber_and_the_day_after_gold(self):
        """Acceptance criterion 10: the cache the job wrote, read by a shell on a later day or the same one."""
        fake = Path(self.home.parent) / "fake-date"
        fake.mkdir()
        cases = (("2026-10-29", "2026-10-30", "FFB86B"), ("2026-10-30", "2026-10-30", "FFB86B"),
                 ("2026-10-31", "2026-10-31", "FFB86B"), ("2026-10-31", "2026-11-01", "gold"),
                 ("2026-11-01", "2026-11-01", "gold"))
        for written, today, expected in cases:
            with self.subTest(written=written, today=today):
                caret.write(self.cache / "caret", date.fromisoformat(written), None)
                (fake / "date").write_text(f"#!/bin/sh\necho {today}\n", encoding="utf-8")
                (fake / "date").chmod(0o755)
                self.assertEqual(self.caret(env={"PATH": f"{fake}:{self.env['PATH']}"}), expected)

    def test_a_missing_or_unreadable_cache_leaves_it_gold(self):
        (self.cache / "caret").unlink()
        self.assertEqual(self.caret(), "gold")
        (self.cache / "caret").mkdir()
        self.assertEqual(self.caret(), "gold")
        (self.cache / "caret").rmdir()
        self.write_caret(f"{self.day()} FFB86B samhain\n")
        (self.cache / "caret").chmod(0)
        self.addCleanup((self.cache / "caret").chmod, 0o644)
        self.assertEqual(self.caret(), "gold")


```

- [ ] **Step 2: Run the new tests and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_fish_files`
Expected: `Ran 36 tests` and `FAILED (failures=8)`: `test_starts_the_caret_job_when_the_cache_is_not_from_today`, `test_starts_it_outside_windows_terminal_and_without_the_sky_config`, `test_starts_it_when_there_is_no_cache_yet`, `test_todays_line_sets_a_global_in_tides_child_shell_and_in_a_new_tab`, `test_yesterdays_second_line_covers_the_first_shell_of_today`, and three subtests of `test_samhain_eve_and_day_are_amber_and_the_day_after_gold` (the three amber days). The other new tests are guards that hold on the old file too (nothing set, no job) and must keep holding.

- [ ] **Step 3: Implement**

Replace the whole of `content/fish/conf.d/witchy.fish` with:

```fish
# Moonlit Candle (witchy): eza colours, the seasonal caret, and the job that keeps the Windows Terminal moon on
# tonight's phase and the caret cache on today (spec 4.5, 7; prompt takeover spec 15.3). The job starts when
# the cache was not written today or the phase bin differs from the last one it set, and at most once a day
# after a failure.
set -gx EZA_COLORS @EZA_COLORS@

# Before the interactive check: Tide draws the prompt in a non-interactive `fish -c` child, which reads conf.d
# too. Only today's line counts (the job writes today's and tomorrow's); the universal value stays gold.
set -l caret_written
if test -r $HOME/.cache/witchy/caret
    set -l today (date +%F)
    while read -l day colour sabbat
        set -q caret_written[1]; or set caret_written $day
        if test "$day" = $today; and string match -qr '^[0-9A-F]{6}$' -- "$colour"
            set -g tide_character_color $colour
        end
    end <$HOME/.cache/witchy/caret
end

status is-interactive; or exit
set -q WITCHY_DOCTOR; and exit  # doctor's new shell reads the prompt variables and must start nothing
test -x @PYTHON@; and test -f @WITCHY_DIR@/ritual/__main__.py; or exit

set -l cache $HOME/.cache/witchy
set -l today (date +%F)
set -l failed
test -r $cache/sky-fail; and read failed <$cache/sky-fail
test "$failed" = $today; and exit
set -l job
if set -q WT_SESSION; and test -f @WITCHY_DIR@/ritual-config.json
    set -l stamp
    test -r $cache/sky-bin; and read stamp <$cache/sky-bin
    test "$stamp" = (_witchy_moon_bin); or set job --sky  # --sky writes the caret cache too
end
if not set -q job[1]; and test "$caret_written" != $today
    set job --caret
end
set -q job[1]; or exit
@PYTHON@ -I -B @WITCHY_DIR@/ritual $job >/dev/null 2>&1 &
builtin disown 2>/dev/null
```

- [ ] **Step 4: Correct the spec and the README**

In `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md`, section 15.3, replace the second bullet:

```markdown
- `conf.d/witchy.fish` reads that file with `read` (no Python) and, only if its date is today and it holds a colour, runs `set -g tide_character_color <HEX>`. The universal value stays gold. The failure colour is not changed.
```

with:

```markdown
- `conf.d/witchy.fish` reads that file with `read` (no Python) and, only from the line whose date is today and only for a six-digit upper-case hex colour, runs `set -g tide_character_color <HEX>`. It does so before its `status is-interactive` check: Tide draws the prompt in a non-interactive `fish -c` child, which reads conf.d too and would otherwise never see the global. The universal value stays gold. The failure colour is not changed.
- Daily refresh: the sky job used to start only when the moon-phase bin changed (ritual 4.5). `conf.d/witchy.fish` now also starts it as `ritual --caret` when the cache's first line is not today's date, on any interactive shell that is not doctor's (Windows Terminal or not, with or without `ritual-config.json`), unless the job failed today. A changed phase in Windows Terminal starts `ritual --sky`, which writes the cache as well, so a shell starts at most one job.
```

In `README.md`, under "The greeting", replace:

```markdown
The sky job runs in the background when a tab opens and moves the Windows Terminal moon to tonight's phase. Errors from the greeting and the sky job go to `~/.cache/witchy/ritual.log`; `doctor` shows the newest ones.
```

with:

```markdown
The sky job runs in the background when a tab opens and moves the Windows Terminal moon to tonight's phase. Once a day it also writes `~/.cache/witchy/caret`: on a sabbat and the day before, the prompt's `❯` takes the sabbat's colour (Samhain amber on 30 and 31 October), and it is candle gold on every other day. Errors from the greeting and the sky job go to `~/.cache/witchy/ritual.log`; `doctor` shows the newest ones.
```

- [ ] **Step 5: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 809 tests … OK (skipped=2)` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 6: Check the caret with Tide's own character item (temporary HOME)**

This needs Tide 6.1.1 installed for the user (read only: one file is copied out of `~/.config/fish/functions`). Run:
```bash
H=$(mktemp -d); mkdir -p "$H/cfg/fish/functions" "$H/home/.cache/witchy"
cp ~/.config/fish/functions/_tide_item_character.fish "$H/cfg/fish/functions/"
/usr/bin/python3 -c "
import sys; from pathlib import Path; from witchy import build
for name, data in build.fish_files('/usr/bin/python3', Path(sys.argv[1]) / 'home/.claude/witchy').items():
    path = Path(sys.argv[1]) / 'cfg/fish' / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
" "$H"
run() { env HOME="$H/home" XDG_CONFIG_HOME="$H/cfg" COLORTERM=truecolor fish -c "$1"; }
run 'set -U tide_character_color FFD477; set -U tide_character_color_failure FF6B9F; set -U tide_character_icon ❯'
printf '%s FFB86B samhain\n' "$(date +%F)" > "$H/home/.cache/witchy/caret"
run 'set _tide_status 0; set -g fish_key_bindings fish_default_key_bindings; _tide_item_character' | od -c | head -2
printf '2020-01-01 FFB86B samhain\n' > "$H/home/.cache/witchy/caret"
run 'set _tide_status 0; set -g fish_key_bindings fish_default_key_bindings; _tide_item_character' | od -c | head -2
```
Expected: the first `od` shows `033 [ 3 8 ; 2 ; 2 5 5 ; 1 8 4 ; 1 0 7 m` (`FFB86B`) before `❯`, the second `… 2 5 5 ; 2 1 2 ; 1 1 9 m` (`FFD477`). The universal variables live in `$H/cfg`, not in the real fish config.

- [ ] **Step 7: Commit**

```bash
git add content/fish/conf.d/witchy.fish tests/test_fish_files.py README.md docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: new shells take the caret colour from today's cache, and the job refreshes it daily" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 4: doctor shows today's caret and accepts the caret global only with today's colour

**Items:**
- Spec 15.3, doctor bullet: the global-shadow check (9.1) accepts `tide_character_color` when its global equals the colour in today's caret file; doctor prints `caret: gold` or `caret: samhain FFB86B (today's cache)`, ⚠ when the cache is older than today.

**Files:**
- Modify: `witchy/components/fish.py` (imports, `CARET`, `_today`, `_todays_caret`, `caret_check`, `_prompt_checks`, `check`)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (15.3, doctor bullet)
- Modify: `README.md` (two Troubleshooting rows)
- Test: `tests/test_components_fish.py`, `tests/test_fish_integration.py`

**Interfaces:**
- Consumes: Task 2's `caret.read`, `caret.NAME`; Task 3's global (doctor's `fish -i -c` with `WITCHY_DOCTOR=1` reads `conf.d/witchy.fish`, which sets the caret global before its `WITCHY_DOCTOR` exit); Plan F's `fish.shadows(ctx, names) -> dict[str, list[str]]` and `_prompt_checks`; Plan G's `info` check level (`runner.SYMBOLS["info"] == "·"`); `log.MAX_LINES`, `log.NAME`; `ctx.now`, `ctx.cache_dir`.
- Produces: `fish.CARET = "tide_character_color"`; `fish.caret_check(ctx) -> Check` (level `info` or `warn`); one more `fish` doctor line after the prompt checks.

**Decisions:**
1. **Today is the local day:** `ctx.now()`, converted to local time when it carries a zone, the day `date +%F` and the sky job use. The log checks already treat `now` that way.
2. **Accepted only when exact:** the global must be the one-element list `[today's colour]`. A two-element value, another name, a colour from another line or a gold day are not witchy's and stay ✗ with the `--only tide` fix.
3. **The caret line does not depend on Tide being ready:** it reads only the cache, so it shows even when the prompt checks are one ⚠.
4. **Levels:** `info` (`·`, Plan G's level for a line to read) with a line for today, gold or a sabbat's colour, since neither is a check that passed; ⚠ without one. A missing cache has no fix (a new tab writes it); a stale or damaged one points at the log, since the job writes its failures there.

- [ ] **Step 1: Write the failing tests**

In `tests/test_components_fish.py`, after `DoctorTest` (before `@unittest.skipUnless(FISH, "fish is not installed")` and `class RealFishBytesTest`), add:

```python
class CaretDoctorTest(FishTestCase):
    """doctor's caret line and the caret global (prompt takeover spec 15.3)."""

    NOW = datetime(2026, 10, 31, 21, 0)
    SAMHAIN = "2026-10-31 FFB86B samhain\n2026-11-01\n"

    def setUp(self):
        super().setUp()
        runner.install(self.ctx())

    def doctor(self, run=None):
        ctx = self.ctx(run=run)
        ctx.now = lambda: self.NOW
        code = runner.doctor(ctx, [fish.FishComponent()])
        return code, self.out.getvalue()

    def write_caret(self, text):
        path = self.home / ".cache" / "witchy" / "caret"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_a_sabbat_shows_its_colour(self):
        self.write_caret(self.SAMHAIN)
        self.assertIn("· fish              caret: samhain FFB86B (today's cache)\n", self.doctor()[1])

    def test_an_ordinary_day_is_gold(self):
        self.write_caret("2026-10-31\n2026-11-01\n")
        self.assertIn("· fish              caret: gold\n", self.doctor()[1])

    def test_yesterdays_cache_still_holds_a_line_for_today(self):
        self.write_caret("2026-10-30 FFB86B samhain\n2026-10-31 FFB86B samhain\n")
        self.assertIn("· fish              caret: samhain FFB86B (today's cache)\n", self.doctor()[1])

    def test_a_stale_cache_is_a_warning_with_the_log(self):
        self.write_caret("2026-10-28\n2026-10-29\n")
        code, output = self.doctor()
        self.assertEqual(code, 0)
        log = self.home / ".cache" / "witchy" / "ritual.log"
        self.assertIn("⚠ fish              caret: gold (the caret cache was written on 2026-10-28, not today)\n"
                      f"    fix: tail -n 20 {log}\n", output)

    def test_a_damaged_or_missing_cache_is_a_warning(self):
        self.write_caret("FFB86B\n")
        self.assertIn("⚠ fish              caret: gold (the caret cache is damaged)\n", self.doctor()[1])
        (self.home / ".cache" / "witchy" / "caret").unlink()
        output = self.doctor()[1]
        self.assertIn("⚠ fish              caret: gold (no caret cache yet; a new tab writes it)\n", output)
        self.assertNotIn("caret cache yet; a new tab writes it)\n    fix", output)

    def test_the_caret_global_is_accepted_only_with_todays_colour(self):
        run = fake_fish(self.variables, globals={"tide_character_color": ["FFB86B"]})
        self.write_caret(self.SAMHAIN)
        code, output = self.doctor(run=run)
        self.assertEqual(code, 0, output)
        self.assertNotIn("overridden", output)
        for text in ("2026-10-31\n2026-11-01\n", "2026-10-30 FFB86B samhain\n", "2026-10-31 FFD477 litha\n"):
            with self.subTest(text=text):
                self.write_caret(text)
                code, output = self.doctor(run=run)
                self.assertEqual(code, 1)
                self.assertIn("✗ fish              tide_character_color is overridden by a global in config.fish "
                              "or conf.d\n", output)

    def test_only_the_caret_colour_is_accepted(self):
        self.write_caret(self.SAMHAIN)
        for hidden in ({"tide_character_color": ["FFB86B", "FFB86B"]}, {"tide_character_color_failure": ["FFB86B"]}):
            with self.subTest(hidden=hidden):
                code, output = self.doctor(run=fake_fish(self.variables, globals=hidden))
                self.assertEqual(code, 1)
                self.assertIn(f"✗ fish              {next(iter(hidden))} is overridden", output)

    def test_an_aware_now_uses_the_local_day(self):
        self.write_caret(self.SAMHAIN)
        local = self.NOW.astimezone()  # 21:00 on the 31st in this machine's zone
        ctx = self.ctx()
        ctx.now = lambda: local.astimezone(timezone.utc)
        runner.doctor(ctx, [fish.FishComponent()])
        self.assertIn("caret: samhain FFB86B (today's cache)", self.out.getvalue())


```

In `tests/test_fish_integration.py`, replace:

```python
import unittest
from pathlib import Path
```

with:

```python
import unittest
from datetime import date
from pathlib import Path
```

and, in `RealFishRoundTripTest`, before `test_snapshot_reads_values_with_spaces_and_empty_lists`, add:

```python
    def test_doctor_accepts_the_caret_global_only_while_it_holds_todays_colour(self):
        self.assertEqual(runner.install(self.ctx("20261003-120000")), 0, self.out.getvalue())
        cache = self.home / ".cache" / "witchy"
        cache.mkdir(parents=True)
        (cache / "caret").write_text(f"{date.today().isoformat()} FFB86B samhain\n", encoding="utf-8")
        runner.doctor(self.ctx("20261003-130000"), [fish.FishComponent()])
        self.assertIn("· fish              caret: samhain FFB86B (today's cache)", self.out.getvalue())
        self.assertNotIn("tide_character_color is overridden", self.out.getvalue())
        with (self.config / "config.fish").open("a", encoding="utf-8") as config:
            config.write("set -g tide_character_color 123456\n")
        runner.doctor(self.ctx("20261003-140000"), [fish.FishComponent()])
        self.assertIn("✗ fish              tide_character_color is overridden by a global", self.out.getvalue())

```

- [ ] **Step 2: Run the new tests and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_fish tests.test_fish_integration`
Expected: `Ran 81 tests` and `FAILED (failures=8)`: seven `CaretDoctorTest` tests (no `caret:` line; the accepted global still reads `overridden`) and `test_doctor_accepts_the_caret_global_only_while_it_holds_todays_colour`. `test_only_the_caret_colour_is_accepted` is a guard that holds before and after.

- [ ] **Step 3: Implement**

In `witchy/components/fish.py`, replace:

```python
from datetime import datetime, timedelta
```

with:

```python
from datetime import date, datetime, timedelta
```

replace:

```python
from ..ritual import log, sky
```

with:

```python
from ..ritual import caret, log, sky
```

replace:

```python
LOG_LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d) (greeting|sky): (.*)$")
```

with:

```python
LOG_LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d) (greeting|sky): (.*)$")
CARET = "tide_character_color"  # conf.d/witchy.fish sets it as a global on a sabbat and its eve (spec 15.3)
```

Before `def log_checks(ctx: Any) -> list[Check]:`, add:

```python
def _today(ctx: Any) -> date:
    """The local day, as fish's `date +%F` and the sky job see it."""
    now = ctx.now()
    return (now.astimezone() if now.tzinfo is not None else now).date()


def _todays_caret(ctx: Any) -> str | None:
    """The colour today's line of the caret cache holds, or None (gold, or no usable cache)."""
    try:
        found = caret.read(ctx.cache_dir / caret.NAME).get(_today(ctx).isoformat())
    except OSError:
        return None
    return found[1] if found else None


def caret_check(ctx: Any) -> Check:
    """doctor's caret line (spec 15.3): today's colour from the cache, or gold, as a line to read; a warning when
    the cache holds no line for today, since then every new shell shows gold."""
    path = ctx.cache_dir / caret.NAME
    try:
        days = caret.read(path)
    except OSError:
        return Check("warn", "fish", "caret: gold (no caret cache yet; a new tab writes it)")
    today = _today(ctx).isoformat()
    if today not in days:
        written = next(iter(days), None)
        why = f"was written on {written}, not today" if written else "is damaged"
        return Check("warn", "fish", f"caret: gold (the caret cache {why})",
                     f"tail -n {log.MAX_LINES} {shlex.quote(str(ctx.cache_dir / log.NAME))}")
    found = days[today]
    return Check("info", "fish", f"caret: {found[0]} {found[1]} (today's cache)" if found else "caret: gold")


```

In `FishComponent._prompt_checks`, replace:

```python
        # The tide component disables `set -g tide_…` lines in config.fish and conf.d.
        checks += [Check("fail", self.name, f"{name} is overridden by a global in config.fish or conf.d",
                         fix_command("tide")) for name in sorted(hidden)]
```

with:

```python
        # conf.d/witchy.fish's own caret global holds today's colour from the cache; any other global is not ours.
        caret_colour = _todays_caret(ctx)
        if caret_colour is not None and hidden.get(CARET) == [caret_colour]:
            del hidden[CARET]
        # The tide component disables `set -g tide_…` lines in config.fish and conf.d.
        checks += [Check("fail", self.name, f"{name} is overridden by a global in config.fish or conf.d",
                         fix_command("tide")) for name in sorted(hidden)]
```

In `FishComponent.check`, replace:

```python
        checks += self._prompt_checks(ctx)
```

with:

```python
        checks += self._prompt_checks(ctx)
        checks.append(caret_check(ctx))
```

- [ ] **Step 4: Correct the spec and the README**

In `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md`, section 15.3, replace the doctor bullet:

```markdown
- doctor: the global-shadow check (9.1) accepts `tide_character_color` when its global equals the colour in today's caret file. doctor shows one line: `caret: gold` or `caret: samhain FFB86B (today's cache)`, and ⚠ when the cache is older than today.
```

with:

```markdown
- doctor: the global-shadow check (9.1) accepts `tide_character_color` when its global is exactly the colour on today's line of the caret file. doctor shows one info line (`·`, never a problem): `caret: gold` or `caret: samhain FFB86B (today's cache)`, and ⚠ when the cache holds no line for today (`caret: gold (the caret cache was written on <date>, not today)`, fix: show the log; `… is damaged`; `no caret cache yet; a new tab writes it`). A cache written yesterday still holds today's line and passes.
```

In `README.md`'s Troubleshooting table, before the row that starts ``| `⚠ fish  eza missing — sudo apt install eza` |``, add:

```markdown
| `⚠ fish  caret: gold (the caret cache was written on …, not today)` | the daily job did not refresh `~/.cache/witchy/caret`, so the prompt caret stays gold | `tail -n 20 ~/.cache/witchy/ritual.log`; a new tab retries |
| `⚠ fish  caret: gold (no caret cache yet; a new tab writes it)` | no shell has started the daily job since install | open a new tab, then run doctor again |
```

- [ ] **Step 5: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 818 tests … OK (skipped=2)` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 6: Commit**

```bash
git add witchy/components/fish.py tests/test_components_fish.py tests/test_fish_integration.py README.md docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: doctor shows today's caret and accepts the caret global only with today's colour" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 5: preview draws the prompt from the palette, with neither fish nor Tide

**Items:**
- Spec 15.2 (D16): `python3 -m witchy preview [--variant NAME]` prints the left and right prompt as fish would draw them, in 24-bit colour, from `build.tide(variant)`, for home, a project with dirty git, an unwritable directory, a failed command with duration, and background jobs; needs neither fish nor Tide, writes nothing, exits 0; lives in `witchy/preview.py`.
- Spec 12: `test_preview.py` with golden files `tests/golden/prompt-*.txt`.
- Acceptance criterion 9; a README entry.

**Files:**
- Create: `witchy/preview.py`
- Create: `tests/test_preview.py`, `tests/golden/prompt-home.txt`, `prompt-git.txt`, `prompt-unwritable.txt`, `prompt-failed.txt`, `prompt-jobs.txt`
- Modify: `witchy/__main__.py` (docstring, imports, the `preview` subparser and its dispatch)
- Modify: `README.md` (Usage line and one paragraph)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (15.2, one paragraph)

**Interfaces:**
- Consumes: Plan F's `build.tide(variant) -> dict[str, str | tuple[str, ...]]` (158 names, Tide's defaults merged with `palette.TIDE`); `palette.VARIANTS`, `palette.DEFAULT_VARIANT`, `palette.THEME_NAME`; `ritual.layout.cell_width` (emoji two cells, as `fish_emoji_width 2`); `ritual.moon.phase_bin`, `ritual.moon.GLYPHS`.
- Produces: `preview.Sample`, `preview.SAMPLES`, `preview.fg`, `preview.bg`, `preview.width`, `preview.Side`, `preview.pwd`, `preview.git`, `preview.duration`, `preview.prompt(tide, sample, now, columns) -> [top, bottom]`, `preview.render(variant, now=None, columns=80) -> str`; the CLI command `preview` (exit 0; an unknown `--variant` is argparse's exit 2).

**Decisions:**
1. **What is copied from Tide 6.1.1** (read from the installed source): `_tide_print_item` (prefix for the first item, the same-colour separator between items that share a background, the diff separator otherwise, the item's colour on its background, one pad space each side), `_tide_item_newline` (the left suffix), `_tide_pwd` for paths that need no truncation (the icon before the first part, the last part bold in the anchor colour), `_tide_item_git` for a branch with changed and new files (unstable background, `!n`, `?n`), `_tide_item_status` with `character` on the left, `_tide_item_cmd_duration` with 0 decimals (whole seconds, truncated like `math -s0`), `_tide_item_jobs` under the number threshold, `_tide_item_time` (`strftime` of `tide_time_format`), `_tide_item_character`, and `fish_prompt`'s two-line frame with the connection dots filling the top line to the terminal width.
2. **Escapes are fish's in effect** (plan Decision 9).
3. **Golden files are generated, then pinned by hash and by readable assertions:** `test_each_state_shows_its_items` and the other `PromptTest` tests say in plain text what each sample must show, and the golden files pin every escape. A change to the palette that moves a colour fails the golden test; regenerate with Step 4's command and review the diff with `cat -v`.
4. **The `__main__.py` change is one subparser and one dispatch block before the `Context`,** so it does not touch the install, doctor, `--fresh` or `--fix` paths Plan G built.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_preview.py`:

```python
import io
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from witchy import __main__ as cli
from witchy import build, palette, preview, validate

GOLDEN = Path(__file__).resolve().parent / "golden"
NOW = datetime(2026, 10, 31, 21, 13, tzinfo=timezone.utc)  # a waning moon, 🌗
TIDE = {name: value if isinstance(value, str) else " ".join(value) for name, value in build.tide().items()}
COLOUR = re.compile(r"\x1b\[[34]8;2;(\d+);(\d+);(\d+)m")


def plain(line):
    return preview.ESCAPE.sub("", line)


def colours(text):
    return {"%02X%02X%02X" % tuple(int(part) for part in match) for match in COLOUR.findall(text)}


def sample(name):
    return next(sample for sample in preview.SAMPLES if sample.name == name)


class GoldenTest(unittest.TestCase):
    def test_every_sample_matches_its_golden_file(self):
        self.assertEqual([s.name for s in preview.SAMPLES], ["home", "git", "unwritable", "failed", "jobs"])
        for found in preview.SAMPLES:
            with self.subTest(sample=found.name):
                expected = (GOLDEN / f"prompt-{found.name}.txt").read_text(encoding="utf-8").splitlines()
                self.assertEqual(preview.prompt(TIDE, found, NOW, 80), expected)


class PromptTest(unittest.TestCase):
    def lines(self, name, columns=80):
        return preview.prompt(TIDE, sample(name), NOW, columns)

    def test_each_state_shows_its_items(self):
        left = (TIDE["tide_left_prompt_prefix"], TIDE["tide_left_prompt_separator_diff_color"],
                TIDE["tide_left_prompt_suffix"])
        right = (TIDE["tide_right_prompt_prefix"], TIDE["tide_right_prompt_suffix"])
        expected = {
            "home": ["{} 🌗 {} 🔮 ~ {}".format(*left), "{} 21:13 🦉 {}".format(*right)],
            "git": ["🧹 ~/projects/witchyterm", "🌿 main !2 ?1"],
            "unwritable": ["🪦 /etc/ssl"],
            "failed": ["🌿 main", "💀 2", "🔥 4s", "21:13 🦉"],
            "jobs": ["🧹 ~/projects", " 🐈 ", "21:13 🦉"],
        }
        for name, parts in expected.items():
            with self.subTest(sample=name):
                top, bottom = (plain(line) for line in self.lines(name))
                self.assertTrue(top.startswith("╭─") and top.endswith("─╮"), top)
                self.assertTrue(bottom.startswith("╰─❯ ") and bottom.endswith("─╯"), bottom)
                for part in parts:
                    self.assertIn(part, top)

    def test_items_that_show_nothing_are_left_out(self):
        top = plain(self.lines("home")[0])
        for glyph in ("🌿", "💀", "🧪", "🔥", "🐈"):
            self.assertNotIn(glyph, top)

    def test_the_caret_is_gold_and_rose_red_after_a_failure(self):
        gold, red = preview.fg(TIDE["tide_character_color"]), preview.fg(TIDE["tide_character_color_failure"])
        self.assertIn(gold + "❯", self.lines("home")[1])
        self.assertIn(red + "❯", self.lines("failed")[1])

    def test_a_dirty_repository_takes_the_unstable_background(self):
        self.assertIn(preview.bg(TIDE["tide_git_bg_color_unstable"]), self.lines("git")[0])
        self.assertIn(preview.bg(TIDE["tide_git_bg_color"]), self.lines("failed")[0])

    def test_every_line_fills_the_terminal_exactly(self):
        for columns in (80, 120):
            for found in preview.SAMPLES:
                with self.subTest(columns=columns, sample=found.name):
                    self.assertEqual([preview.width(line) for line in self.lines(found.name, columns)],
                                     [columns, columns])

    def test_a_narrow_terminal_gets_no_connection_dots(self):
        top = plain(self.lines("git", 40)[0])
        self.assertNotIn(TIDE["tide_prompt_icon_connection"], top)

    def test_every_colour_comes_from_the_prompt_and_none_is_pastel(self):
        text = "".join(line for found in preview.SAMPLES for line in preview.prompt(TIDE, found, NOW, 80))
        values = {value for value in TIDE.values() if re.fullmatch(r"[0-9A-F]{6}", value)}
        self.assertLessEqual(colours(text), values)
        self.assertFalse([part for part in colours(text) | set(plain(text)) if validate.is_pastel(part)])

    def test_durations(self):
        self.assertEqual([preview.duration(ms) for ms in (4321, 65000, 3723000)], ["4s", "1m 5s", "1h 2m 3s"])


class CommandTest(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("subprocess.run", side_effect=AssertionError("preview runs nothing")), \
                mock.patch("pathlib.Path.home", return_value=Path(tmp)), \
                mock.patch("shutil.get_terminal_size", return_value=mock.Mock(columns=100)), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                code = cli.main(argv)
            except SystemExit as exc:
                code = exc.code
            self.assertEqual(list(Path(tmp).iterdir()), [])  # writes nothing
        return code, out.getvalue(), err.getvalue()

    def test_preview_prints_every_sample_and_exits_0(self):
        code, out, _ = self.run_cli(["preview"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], "Moonlit Candle prompt (midnight), drawn from the palette; a sketch, Tide itself "
                                   "does not run.")
        for found in preview.SAMPLES:
            self.assertIn(found.title, lines)
        self.assertEqual({preview.width(line) for line in lines if line.startswith("\x1b")}, {100})

    def test_a_variant_can_be_named(self):
        self.assertEqual(self.run_cli(["preview", "--variant", "midnight"])[0], 0)
        code, _, err = self.run_cli(["preview", "--variant", "noon"])
        self.assertEqual(code, 2)
        self.assertIn("invalid choice: 'noon'", err)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new tests and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_preview`
Expected: `Ran 1 test` and `FAILED (errors=1)`: `ImportError: cannot import name 'preview' from 'witchy'`.

- [ ] **Step 3: Implement**

Create `witchy/preview.py`:

```python
"""python3 -m witchy preview: the Tide prompt drawn from the palette, with neither fish nor Tide (spec 15.2).

A sketch. For its sample states it copies what Tide 6.1.1 does (fish_prompt's frame, _tide_2_line_prompt,
_tide_print_item, _tide_pwd and the moon, pwd, git, status, cmd_duration, jobs, time and character items);
nothing of Tide runs, and Tide's truncation of long paths is left out because no sample needs it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from . import build, palette
from .ritual import layout, moon

NORMAL = "\x1b[0m"
BOLD = "\x1b[1m"
DEFAULT_BG = "\x1b[49m"
ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
PWD_MARK = "@PWD@"  # Tide draws the items first and puts the path in last; the frame needs its width


@dataclass(frozen=True)
class Sample:
    """One prompt state. ``pwd`` is the path as Tide shows it (``~`` for HOME)."""

    name: str
    title: str
    pwd: str
    writable: bool = True
    branch: str | None = None
    dirty: int = 0
    untracked: int = 0
    status: int = 0
    duration_ms: int = 0
    jobs: int = 0


SAMPLES = (
    Sample("home", "home", "~"),
    Sample("git", "a project with changed and new files", "~/projects/witchyterm", branch="main", dirty=2,
           untracked=1),
    Sample("unwritable", "a folder you cannot write to", "/etc/ssl", writable=False),
    Sample("failed", "a command that failed with exit 2 after 4 s", "~/projects/witchyterm", branch="main",
           status=2, duration_ms=4321),
    Sample("jobs", "two jobs in the background", "~/projects", jobs=2),
)


def fg(colour: str) -> str:
    red, green, blue = (int(colour[i:i + 2], 16) for i in (0, 2, 4))
    return f"\x1b[38;2;{red};{green};{blue}m"


def bg(colour: str) -> str:
    red, green, blue = (int(colour[i:i + 2], 16) for i in (0, 2, 4))
    return f"\x1b[48;2;{red};{green};{blue}m"


def width(text: str) -> int:
    """Cells on screen, as `string length -V` counts them with fish_emoji_width 2."""
    return layout.cell_width(ESCAPE.sub("", text))


class Side:
    """One side of the prompt, item by item, the way _tide_print_item joins them."""

    def __init__(self, tide: Mapping[str, str], side: str) -> None:
        self.tide, self.side = tide, side
        self.text = ""
        self.previous: str | None = None
        self.add_prefix = True
        self.pad = " " if tide["tide_prompt_pad_items"] == "true" else ""

    def item(self, name: str, text: str, bg_colour: str | None = None, colour: str | None = None) -> None:
        tide, side = self.tide, self.side
        item_bg = bg_colour or tide[f"tide_{name}_bg_color"]
        if self.add_prefix:
            self.text += fg(item_bg) + DEFAULT_BG + tide[f"tide_{side}_prompt_prefix"]
            self.add_prefix = False
        elif item_bg == self.previous:
            separator = tide[f"tide_{side}_prompt_separator_same_color"]
            self.text += fg(tide["tide_prompt_color_separator_same_color"]) + separator
        elif side == "left":
            self.text += fg(self.previous) + bg(item_bg) + tide["tide_left_prompt_separator_diff_color"]
        else:
            self.text += fg(item_bg) + bg(self.previous) + tide["tide_right_prompt_separator_diff_color"]
        colour = colour or tide.get(f"tide_{name}_color")  # pwd has none: its text carries its own colours
        self.text += (fg(colour) if colour else "") + bg(item_bg) + self.pad + text + self.pad
        self.previous = item_bg

    def end(self) -> str:
        """The side's last cap; the side is done."""
        if not self.add_prefix:
            self.text += fg(self.previous) + DEFAULT_BG + self.tide[f"tide_{self.side}_prompt_suffix"]
            self.add_prefix = True
        return self.text


def pwd(tide: Mapping[str, str], sample: Sample) -> str:
    """_tide_pwd for a path short enough to need no truncation."""
    anchors = BOLD + fg(tide["tide_pwd_color_anchors"])
    dirs = NORMAL + bg(tide["tide_pwd_bg_color"]) + fg(tide["tide_pwd_color_dirs"])
    if sample.pwd == "~":
        return dirs + tide["tide_pwd_icon_home"] + " " + anchors + "~"
    parts = sample.pwd.split("/")
    icon = tide["tide_pwd_icon"] if sample.writable else tide["tide_pwd_icon_unwritable"]
    parts[0] = icon + " " + parts[0]
    parts[-1] = anchors + parts[-1] + dirs
    return dirs + "/".join(parts)


def git(tide: Mapping[str, str], sample: Sample) -> tuple[str, str]:
    """The git item's text and background."""
    branch = fg(tide["tide_git_color_branch"])
    text = branch + tide["tide_git_icon"] + " " + branch + sample.branch
    if sample.dirty:
        text += fg(tide["tide_git_color_dirty"]) + f" !{sample.dirty}"
    if sample.untracked:
        text += fg(tide["tide_git_color_untracked"]) + f" ?{sample.untracked}"
    unstable = sample.dirty or sample.untracked
    return text, tide["tide_git_bg_color_unstable"] if unstable else tide["tide_git_bg_color"]


def duration(milliseconds: int) -> str:
    """_tide_item_cmd_duration with tide_cmd_duration_decimals 0: whole seconds, then minutes and hours."""
    seconds = milliseconds // 1000
    hours, minutes, seconds = seconds // 3600, seconds // 60 % 60, seconds % 60
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s" if minutes else f"{seconds}s"


def prompt(tide: Mapping[str, str], sample: Sample, now: datetime, columns: int) -> list[str]:
    """The two lines a new prompt shows in ``sample``'s state."""
    left = Side(tide, "left")
    left.item("moon", moon.GLYPHS[moon.phase_bin(now)])
    left.item("pwd", PWD_MARK)
    if sample.branch is not None:
        text, git_bg = git(tide, sample)
        left.item("git", text, bg_colour=git_bg)
    top_left = left.end()  # the newline item
    bottom_left = fg(tide["tide_character_color"] if sample.status == 0 else tide["tide_character_color_failure"])
    bottom_left += tide["tide_character_icon"]

    right = Side(tide, "right")
    # With the character item on the left, Tide shows a status only for a code other than 1 (the caret turns
    # rose-red for any failure).
    if sample.status not in (0, 1):
        right.item("status", f"{tide['tide_status_icon_failure']} {sample.status}",
                   bg_colour=tide["tide_status_bg_color_failure"], colour=tide["tide_status_color_failure"])
    if sample.duration_ms > int(tide["tide_cmd_duration_threshold"]):
        right.item("cmd_duration", f"{tide['tide_cmd_duration_icon']} {duration(sample.duration_ms)}")
    if sample.jobs:
        number = f" {sample.jobs}" if sample.jobs >= int(tide["tide_jobs_number_threshold"]) else ""
        right.item("jobs", tide["tide_jobs_icon"] + number)
    right.item("time", now.strftime(tide["tide_time_format"]))
    top_right = right.end()

    frame = fg(tide["tide_prompt_color_frame_and_connection"]) + DEFAULT_BG
    top_left = top_left.replace(PWD_MARK, pwd(tide, sample))
    fill = max(0, columns - 4 - width(top_left) - width(top_right))
    top = (frame + "╭─" + top_left + frame + tide["tide_prompt_icon_connection"] * fill + top_right + frame + "─╮"
           + NORMAL)
    bottom_right = frame + "─╯" + NORMAL
    bottom = frame + "╰─" + bottom_left + NORMAL + " "
    bottom += " " * max(0, columns - width(bottom) - width(bottom_right)) + bottom_right
    return [top, bottom]


def render(variant: str = palette.DEFAULT_VARIANT, now: datetime | None = None, columns: int = 80) -> str:
    """Every sample, each under its title."""
    now = now or datetime.now().astimezone()
    tide = {name: value if isinstance(value, str) else " ".join(value) for name, value in build.tide(variant).items()}
    lines = [f"{palette.THEME_NAME} prompt ({variant}), drawn from the palette; a sketch, Tide itself does not run."]
    for sample in SAMPLES:
        lines += ["", sample.title, *prompt(tide, sample, now, columns)]
    return "\n".join(lines) + "\n"
```

In `witchy/__main__.py`, replace:

```python
"""python3 -m witchy validate | build | install | uninstall | doctor | mood"""
```

with:

```python
"""python3 -m witchy validate | build | install | uninstall | doctor | mood | preview"""
```

replace:

```python
import os
import sys
```

with:

```python
import os
import shutil
import sys
```

replace:

```python
from . import build, components, fresh, runner, validate
```

with:

```python
from . import build, components, fresh, palette, preview, runner, validate
```

and replace:

```python
    mood_parser.add_argument("variant", nargs="?", help="variant to switch to")
    args = parser.parse_args(argv)
```

with:

```python
    mood_parser.add_argument("variant", nargs="?", help="variant to switch to")
    preview_parser = commands.add_parser("preview", help="draw the prompt from the palette, without fish or Tide")
    preview_parser.add_argument("--variant", choices=sorted(palette.VARIANTS), default=palette.DEFAULT_VARIANT,
                                help="colour variant to draw")
    args = parser.parse_args(argv)

    if args.command == "preview":
        print(preview.render(args.variant, columns=shutil.get_terminal_size((80, 24)).columns), end="")
        return 0
```

- [ ] **Step 4: Generate the golden files and check them**

Run:
```bash
/usr/bin/python3 -c "
from pathlib import Path
from tests.test_preview import NOW, TIDE
from witchy import preview
for sample in preview.SAMPLES:
    Path(f'tests/golden/prompt-{sample.name}.txt').write_text('\n'.join(preview.prompt(TIDE, sample, NOW, 80)) + '\n', encoding='utf-8')
"
sha256sum tests/golden/prompt-*.txt
for name in home git unwritable failed jobs; do sed 's/\x1b\[[0-9;]*m//g' tests/golden/prompt-$name.txt; done
```
Expected:
```
feef13b1681b42ba86bd2f7f17cd16aa2442cd03cdfbccda8127ad0aab706010  tests/golden/prompt-failed.txt
a2946a19ba50efa61ada10f5cf7cc26b314d3440c1e34f7c4ae00731df797742  tests/golden/prompt-git.txt
e9bae63e1033b352fbecdf018e1d20d35e2410952fad0da5870fb68dcf5bd281  tests/golden/prompt-home.txt
9572fe5b66ef63df474f7b98d4236c6bd932db6a3c8847ce0c83168e0b9ed856  tests/golden/prompt-jobs.txt
3b4313ee2eb207b04a869970dfded30b8defae7bdeeba74cd82a996e8f16fa5e  tests/golden/prompt-unwritable.txt
╭─ 🌗  🔮 ~ ··················································· 21:13 🦉 ─╮
╰─❯                                                                           ─╯
╭─ 🌗  🧹 ~/projects/witchyterm  🌿 main !2 ?1 ··············· 21:13 🦉 ─╮
╰─❯                                                                           ─╯
╭─ 🌗  🪦 /etc/ssl ············································ 21:13 🦉 ─╮
╰─❯                                                                           ─╯
╭─ 🌗  🧹 ~/projects/witchyterm  🌿 main ······ 💀 2  🔥 4s  21:13 🦉 ─╮
╰─❯                                                                           ─╯
╭─ 🌗  🧹 ~/projects ····································· 🐈  21:13 🦉 ─╮
╰─❯                                                                           ─╯
```
The caps and separators are Nerd Font private-use glyphs (U+E0BA, U+E0BC, U+E0B3); without Maple Mono NF they may look like blanks above, and each is one cell. `cat tests/golden/prompt-git.txt` in Windows Terminal shows the coloured prompt.

- [ ] **Step 5: Document it**

In `README.md`'s Usage block, after the `mood` line, add:

```sh
/usr/bin/python3 -m witchy preview                       # draw the prompt from the palette, without fish or Tide
```

After the paragraph `Restart Claude Code and Windows Terminal after installing, and open a new tab for the new prompt and greeting.`, add:

```markdown

`preview` prints the prompt in 24-bit colour for five sample states (home, a project with changes, a folder you cannot write to, a failed command, background jobs), as Tide would draw it with witchy's values. It needs neither fish nor Tide and writes nothing, so it also shows the prompt on a PC before install; `--variant NAME` picks another colour variant. It is a sketch: Tide's own code does not run.
```

In `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md`, section 15.2, after its first paragraph (the one that ends "It lives in `witchy/preview.py`."), add:

```markdown

The lines fill the terminal's width, today's moon phase and time included. The failed command exits 2: with `character` on the left, Tide shows no status item for exit 1 and only turns the caret rose-red. The golden files hold each sample's two lines at 80 columns on 2026-10-31 21:13 UTC.
```

- [ ] **Step 6: Run the whole suite on both interpreters, and preview in a temporary HOME**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
H=$(mktemp -d); env HOME="$H" XDG_CONFIG_HOME="$H/.config" PATH=/usr/bin:/bin /usr/bin/python3 -m witchy preview; echo "exit=$?"; ls -A "$H"
```
Expected: `Ran 829 tests … OK (skipped=2)` on both, `Moonlit Candle: all checks passed`, the five samples under the line `Moonlit Candle prompt (midnight), drawn from the palette; a sketch, Tide itself does not run.`, `exit=0`, and `ls` prints nothing (acceptance criterion 9: no fish, no Tide, nothing written).

- [ ] **Step 7: Commit**

```bash
git add witchy/preview.py witchy/__main__.py tests/test_preview.py tests/golden/prompt-*.txt README.md docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: preview draws the prompt from the palette, with neither fish nor Tide" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 6: The shell-ritual spec no longer promises the pink prompt back

**Items:**
- Spec 13, docs part: `2026-10-02-shell-ritual-design.md` line 438 ("the pink 🌸 Tide prompt") becomes "the prompt that was there before install"; its section 2 "Out" drops "Installing fish, fisher, Tide" with a pointer to the takeover spec. Plans under `docs/superpowers/plans/` stay as written.

**Files:**
- Modify: `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (section 1 Success line, section 2 Out, acceptance criterion 9)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (section 13)

**Interfaces:**
- Consumes: none.
- Produces: none (documentation only).

**Decisions:**
1. **The section 1 Success line said "the pink Tide prompt" too;** it gets the same wording as criterion 9, and spec 13 says so (plan Decision 10).
2. **eza stays "Out" without `--fresh`:** spec 15.1 installs fish and eza only with `install --fresh`, and fisher and Tide are installed by the `tide` component. The Out line says that and points to sections 5 and 15.1.
3. **No test:** the change is prose. Step 2's `grep` is the check.

- [ ] **Step 1: Edit the shell-ritual spec**

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md`, replace (section 1, Success):

```markdown
**Success:** after `python3 -m witchy install` and a Windows Terminal restart, a new Ubuntu tab matches sections 4–7, `python3 -m witchy doctor` shows no `✗`, and `python3 -m witchy uninstall` gives back the pink Tide prompt, the previous profile settings and the default greeting, leaving only the Maple Mono font files installed.
```

with:

```markdown
**Success:** after `python3 -m witchy install` and a Windows Terminal restart, a new Ubuntu tab matches sections 4–7, `python3 -m witchy doctor` shows no `✗`, and `python3 -m witchy uninstall` gives back the prompt that was there before install, the previous profile settings and the default greeting, leaving only the Maple Mono font files installed.
```

replace (section 2, Out):

```markdown
- Installing fish, fisher, Tide or eza. Missing tools are skipped with a warning; doctor prints the install command.
```

with:

```markdown
- Installing eza without `install --fresh`. A missing eza is skipped with a warning; doctor prints the install command. (witchy installs fisher and Tide, and with `--fresh` fish and eza, since [the prompt takeover spec](2026-10-05-witchy-prompt-takeover-design.md), sections 5 and 15.1.)
```

and replace (acceptance criterion 9):

```markdown
9. `uninstall` brings back the pink 🌸 Tide prompt, the previous profile settings and the default greeting, and leaves Maple Mono installed; the user then reinstalls if they want.
```

with:

```markdown
9. `uninstall` brings back the prompt that was there before install, the previous profile settings and the default greeting, and leaves Maple Mono installed; the user then reinstalls if they want.
```

In `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md`, section 13, replace:

```markdown
- `2026-10-02-shell-ritual-design.md`: line 438 ("the pink 🌸 Tide prompt") becomes "the prompt that was there before install"; section 2 "Out" drops "Installing fish, fisher, Tide" with a pointer to this spec.
```

with:

```markdown
- `2026-10-02-shell-ritual-design.md`: line 438 ("the pink 🌸 Tide prompt") and the matching "pink Tide prompt" in its section 1 Success line become "the prompt that was there before install"; section 2 "Out" drops "Installing fish, fisher, Tide" with a pointer to this spec.
```

- [ ] **Step 2: Check what is left, and that no plan changed**

Run:
```bash
grep -n "pink\|🌸\|Installing" docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git diff --name-only -- docs/superpowers/plans
/usr/bin/python3 -m unittest discover -s tests -t .
```
Expected: three `grep` lines, none about the prompt: line 14 and line 432 (`pink box cursor`, witchy's own `#FF67B7` cursor) and line 36 (the new Out line). `git diff` prints nothing. `Ran 829 tests … OK (skipped=2)`.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-10-02-shell-ritual-design.md docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "docs: the shell-ritual spec no longer promises the pink prompt back and points to the takeover for installing Tide" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## After the last task

- [ ] **Run the whole suite once more and review the branch**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
git diff --stat <Plan G's last commit>..HEAD
```
Expected: `Ran 829 tests … OK (skipped=2)` on both, `Moonlit Candle: all checks passed`, and 29 files changed by this plan.

Acceptance criteria this plan closes, and where:

| Criterion | Proof |
|---|---|
| 2 (Windows Terminal part): no `PastelOneDark` after install | Task 1 `test_this_pcs_pastel_one_dark_is_purged_and_uninstall_gives_back_every_byte`; on the real PC, after Plan G's real install: `grep -c PastelOneDark <settings.json>` prints `0` and doctor has no `PastelOneDark is still in` line |
| 9: `preview` on a PC without Tide | Task 5 `CommandTest`, Step 6 in a temporary HOME |
| 10: amber on 2026-10-30 and 2026-10-31, gold on 2026-11-01 | Task 3 `test_samhain_eve_and_day_are_amber_and_the_day_after_gold`, Task 2 `TextTest`; Task 3 Step 6 with Tide's own character item |
