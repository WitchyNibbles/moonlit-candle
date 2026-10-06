# Plan F: Prompt Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** witchy owns the whole Tide prompt: every one of the Tide 6.1.1 release's 156 universal variables plus the moon item's two and `fish_emoji_width` (159 in all), drawn from one glyph table shared with the status line and the greeting, held to new validation rules, and checked by doctor against the spec in a fresh interactive shell.

**Architecture:** Tide's own defaults become generated data (`scripts/tide_defaults.py` → `content/tide-6.1.1-defaults.json`); `palette.TIDE` keeps only witchy's overrides and `build.tide(variant)` merges the two (Tasks 2–3). `palette.GLYPHS` feeds the prompt and, through generated `# BEGIN GLYPHS` blocks, the status line and the greeting (Task 4). `validate.py` checks the merged prompt (Task 5). A new `witchy/fishprobe.py` asks fish once about fisher, Tide and the active `fish_prompt` (Task 6); the fish component uses it to decide whether Tide is ready, then sets every variable and erases unknown `tide_*` ones (Task 7), and doctor compares every variable with the spec and looks for globals in a new interactive shell (Task 8). Task 9 runs the result end to end against the Tide v6.1.1 release in a temporary HOME.

**Tech Stack:** Python 3.10+ standard library only (`subprocess`, `dataclasses`, `json`, `unicodedata`, `unittest`); fish 3.7; the Tide v6.1.1 release tarball (`https://codeload.github.com/IlanCosman/tide/tar.gz/refs/tags/v6.1.1`) for generating the defaults and for Task 9.

**Spec:** `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (revision 2), sections 6, 7, 9.1, the last paragraph of 9.2 (D19), 11 and the test-fixture part of 13. It builds on `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` ("ritual" below), sections 3, 5, 9 and 11. Tasks that change behaviour or correct the spec edit the spec in the same commit (6.1, 6.2, 6.3, 7, 9.1, 11; ritual 5.3). Plan F is one of three: Plan G (the `tide` component, bootstrap and install flow) and Plan H (Windows Terminal purge, seasonal caret, preview, docs purge) are written against the interfaces this plan produces. This plan is written against `feat/prompt-takeover` at `26dd3ec`.

## Global Constraints

- Python 3.10 or newer, standard library only. Every test passes on `/usr/bin/python3` (3.12) and `/home/eimi/.pyenv/versions/3.10.0/bin/python3`.
- Test command, from the repo root: `/usr/bin/python3 -m unittest discover -s tests -t .`, and the same with the 3.10 interpreter. `python3 -m witchy validate` must print `Moonlit Candle: all checks passed`.
- No test touches the real `~/.claude`, `~/.cache`, `~/.config/fish`, fish universal variables, Windows Terminal, `cmd.exe`, `reg.exe`, the registry or the network. Use `tests/fakes.py` and temporary folders. Tests that run real fish set `HOME` and `XDG_CONFIG_HOME` to a temporary folder and are skipped when fish is missing.
- **Every manual run of witchy code uses a temporary HOME and XDG_CONFIG_HOME** (`HOME=$(mktemp -d)`). The Tide source for Tasks 2 and 9 is the v6.1.1 release tarball, downloaded into a temporary folder (the only network use in this plan). The Tide installed in `~/.config/fish` on this PC is a development build and is not used, except for one read-only check that the generator refuses it (Task 2 Step 4). Never use `fish --no-config` for Tide work: it also turns off universal variables.
- Never run a real `install`, `uninstall`, `mood` or `doctor` against the real HOME in this plan.
- Exit codes do not change anywhere.
- Messages, docstrings and comments are English and neutral in tone. Plan prose and code comments never use the witchy voice.
- Lines stay within 120 characters (a few older lines in `validate.py`, `runner.py`, `wt.py` and `claude_settings.py` are longer; leave them).
- Prompt icons are one emoji code point each: no U+FE0F, no U+200D, no skin tone (spec D5). The candle `🕯️` stays out of the prompt.
- Commit messages end with the `Co-Authored-By:` trailer of the model that wrote the commit. The commit blocks below show the prototype's message; keep the subject and body, and put your own trailer.
- SDD workspaces go under `.superpowers/sdd/` (git-excluded).

## Decisions

Given with the task:

1. **The frame keeps `6E5A80` (spec deviation).** Spec 6.2 set `tide_prompt_color_frame_and_connection` to `38234D`, which is 1.42:1 on `#0D0916` and fails the existing 3:1 frame rule (`validate.TIDE_SECONDARY_PAIRS`, ritual 11.3). `6E5A80` is 3.22:1. Task 3 corrects spec 6.2 and 11.4 in the same commit.

Made while prototyping (each task's **Decisions** block has the details):

2. **Prototype first.** Every task was built and tested in a scratch clone (`proto/plan-f`), test-first, one commit per task. Every stage is green on both interpreters with `validate` clean; each task's new tests were run against the stage before it and fail there. Counts: 557 → 558 → 574 → 585 → 594 → 609 → 620 → 626 → 638.
3. **158 names = the release's 156 + the moon item's 2.** The Rainbow preset (`icons.fish` + `configs/rainbow.fish`) of the Tide v6.1.1 release defines 156 universal variables. The Tide on this PC is the development branch, which still prints `tide, version 6.1.1` but differs in 12 of the release's 83 installed files and adds the `bun` item (`tide_bun_bg_color`, `tide_bun_color`, `tide_bun_icon`); its 161 universal `tide_*` variables are those 159 plus witchy's moon two. Spec 6.4's `bun` icon is dropped (Task 3). The moon item's `tide_moon_bg_color` and `tide_moon_color` are named in `palette.TIDE_OWN`, so validation accepts them and the fish component never erases them. `fish_emoji_width` lives apart in `palette.FISH`: the fish component sets 159 variables. On this PC, the three `tide_bun_*` variables count as unknown, so install erases them and records them for uninstall.
4. **The defaults file is a flat JSON object, one variable per line, each value a list of strings** (a fish list; `[]` for an empty list, `[""]` for one empty string), non-ASCII as `\u` escapes so Nerd Font glyphs stay visible in review. The generator resolves Tide's own colour names (`$_tide_color_green` → `5FD700`) from `_tide_sub_configure.fish` and records Tide's generic Linux OS branding (Tux, `080808` on `CED7CF`): `tide configure` takes the branding from the machine, and witchy overrides all three `tide_os_*` anyway. It refuses anything that is not Tide 6.1.1 or uses fish syntax it cannot read exactly, and it tells the release from a development build by the SHA-256 of the two files it reads (`scripts/tide_defaults.RELEASE`), since both print `tide, version 6.1.1`.
5. **The greeting takes its glyphs through a `# BEGIN GLYPHS` block in `witchy/ritual/palette.py`, not through `ritual/data.json` (spec deviation).** The repository copy of the greeting reads `content/ritual.json` directly, with no build step, so glyphs carried in `data.json` would be missing there. The block is rewritten by `build.ritual_package` exactly like its PALETTE block and like the status line's new GLYPHS block. Task 4 corrects spec 7.
6. **Each GLYPHS block holds the whole table,** so one rule covers both files: the block equals `palette.GLYPHS`. The status line's branch glyph becomes 🌿.
7. **`layout.WIDE` lists the emoji explicitly** (moon phases plus every table emoji); validate rule 5 keeps it in step with `palette.GLYPHS`.
8. **What counts as an emoji (rules 11.1 and 11.5):** a character of category `So` that is East Asian Wide/Fullwidth or lies past U+1F000 (🕯 is narrow in Unicode). `❯`, `✦`, `⋆`, `·`, `▶` and Nerd Font private-use glyphs are text.
9. **`validate.PASTEL`** holds all 49 hex colours and the icons of `~/change_this_bitch.sh` (stored without U+FE0F), except the six icons witchy uses on purpose (🔮 🐍 💎 🦀 ☕ 🐳). The rule applies to the merged prompt and to `WT_SCHEME`.
10. **`jobs` wears the muted pair** (`A99AB9` on `1D1230`), like the unused items: spec 6.3 named no colour for it. Spec 6.3 says so (Task 3).
11. **Separator glyphs are not colours.** Tide names `tide_{left,right}_prompt_separator_{diff,same}_color` with the word "color", but they hold glyphs; `validate.TIDE_SEPARATOR_GLYPHS` excludes them from the colour rules.
12. **fisher's real names (verified on this PC, fisher 4.4.5):** the file list of `ilancosman/tide` is `_fisher_ilancosman_2F_tide_files` (upper-case `2F`, not the spec's `_2f_`); fisher derives it with `string escape --style=var`, so Tide installed from a tag (`ilancosman/tide@v6.1.1`, how Plan G installs it) is `_fisher_ilancosman_2F_tide_40_v6_2E_31_2E_31__files`. The probe computes the name in fish and `fishprobe.plugin_files` matches a plugin with or without `@ref`, in any case. fisher stores paths with `~` for HOME; the probe prints them expanded. `tide --version` prints `tide, version 6.1.1`, `fisher --version` prints `fisher, version 4.4.5`, and `functions --details` prints `n/a` for an undefined function.
13. **The snapshot still erases globals, inside its own `fish -c` process only** (the one exact way fish 3.7 offers to read a universal value that a global hides). What the spec wanted, "a global no longer passes as ✓", comes from doctor's second read in a fresh interactive shell. Task 8 rewords spec 9.1.
14. **doctor compares every variable with the spec, not with what an install recorded**, so an older install that set 31 variables shows ✗ until it is reinstalled. The ✗ line lists the first 10 drifted names, sorted, then `(and N more)`. When Tide is not ready, the three prompt checks become one ⚠ `Tide variables not checked: <reason>` with the fix `python3 -m witchy install --only tide` (Plan G's `tide` check carries the ✗). A global's fix is also `--only tide`, because Plan G's takeover disables `set -g tide_*` lines.
15. **`Command` also gains `env`** (added to `ctx.env`), so doctor's new shell gets `WITCHY_DOCTOR=1`; it also gets empty standard input, so `fish -i` never waits on the terminal. `fish_greeting` gains `WITCHY_DOCTOR` in its guard list as well, although `fish -i -c` never calls the greeting (checked on fish 3.7.0).
16. **doctor checks the installed variant:** `runner.doctor` sets `ctx.variant` from `state.json` when the CLI gave none.
17. **Uninstall after Tide was removed:** only the `tide_*` variables witchy set decide "Tide's variables are gone"; `fish_emoji_width` is still given back.

Made by the user after Plan G's prototype:

18. **The defaults come from the Tide v6.1.1 release, not from this PC's Tide.** Plan G found that the installed Tide is the development branch (Decision 3). The first prototype had generated 159 names from it; this plan regenerates 156 from the release tarball, drops `bun` from `palette.UNUSED_ICONS`, `validate.TIDE_ITEMS` and spec 6.4, removes the `tide_bun_*` names from `tests/test_prompt_palette.TIDE_6_1_1_VARIABLES`, and makes the generator refuse a development build (Decision 4). Task 9 runs against the release.

## Review Focus

1. **Upgrading this PC's real install,** whose fish entry recorded 32 variables with the pastel values as `previous`: a reinstall must keep those `previous` values, record the current values of the 127 new names, erase the three `tide_bun_*` variables of this PC's development build (recording them), and uninstall must give back the user's prompt (spec D4). Test: Task 7 `test_upgrading_an_install_that_set_fewer_variables_still_gives_back_the_users_prompt`.
2. **A universal `tide_*` variable Tide 6.1.1 does not define** (a leftover of an older Tide or a theme script) is erased, recorded, kept recorded across a reinstall, and given back by uninstall; Tide's private `_tide_*` variables are never read or written. Tests: Task 7 `test_a_tide_variable_tide_does_not_define_is_erased_and_recorded`, `test_a_reinstall_keeps_the_record_of_an_erased_variable`, `test_tides_private_variables_are_never_touched`, and the real-fish `test_snapshot_reads_values_with_spaces_and_empty_lists`.
3. **doctor's fresh interactive shell** must succeed when no global exists (the prototype's first script exited 1 there, which only real fish showed), see a global that only an interactive `conf.d` file sets, never wait on the terminal, start no sky job and no greeting, and have 15 s. Tests: Task 8 `test_doctor_sees_globals_that_only_a_new_interactive_shell_sets` (real fish), `test_the_new_shell_is_interactive_quiet_and_has_15_seconds`, `test_the_doctors_new_shell_never_starts_the_job`, `test_the_doctors_new_shell_never_greets`.
4. **Tide installed from a tag or listed in another case,** and a fisher plugin with an empty file list (where `string replace` with no value would read standard input and hang): readiness still holds and the probe returns. Tests: Task 6 `test_tide_installed_from_a_tag_or_in_another_case_counts`, real-fish `test_reads_versions_the_prompt_and_each_plugins_files`.
5. **The defaults generator run on the wrong Tide** (another version, a development build that also says 6.1.1, like the one on this PC, other OS branding, syntax it cannot read, a name set twice) must refuse instead of writing a wrong file, and the checked-in file must hold exactly the release's 156 names. Tests: Task 2 `test_refuses_a_tree_that_is_not_tide_6_1_1`, `test_refuses_a_development_build_that_also_says_6_1_1`, `test_the_release_pins_are_the_two_files_read`, `test_refuses_os_branding_it_does_not_know`, `test_refuses_fish_syntax_it_cannot_read_safely`, `test_refuses_a_name_set_twice`, `test_holds_every_tide_6_1_1_variable_once`.

## Scope → tasks

| Task | Spec |
|---|---|
| 1 | D20 (`Command.timeout`, interface for Plan G) · 13 (test fixtures) |
| 2 | 6.1 (defaults file, generator, `build.tide`, `TIDE_OWN`) |
| 3 | 6.2, 6.3, 6.4, 6.1 (`fish_emoji_width` value), 7 (`palette.GLYPHS`), 11.4 (new contrast pairs); frame deviation |
| 4 | 7 (status line and greeting GLYPHS blocks, ⎇ → 🌿, `layout.WIDE`) |
| 5 | 11.1, 11.2, 11.3, 11.5; 11.4 on the merged prompt |
| 6 | 9.2 last paragraph and D19 (the probe and `tide_ready`); `fake_fish` probe answers |
| 7 | 6.1 (every variable, `fish_emoji_width`, unknown `tide_*` erased), D19 (fish skips unless Tide is ready) |
| 8 | 9.1 fish checks (drift over every name, stray `tide_*`, globals in a fresh interactive shell, `WITCHY_DOCTOR`, 15 s) |
| 9 | End-to-end check with the Tide v6.1.1 release in a temporary HOME |

## File structure

| Task | Source | Tests | Data and docs |
|---|---|---|---|
| 1 | `witchy/components/base.py` | `tests/test_base.py`, `tests/test_components_fish.py`, `tests/test_fish_integration.py`, `tests/test_install.py`, `tests/fixtures/state-v1.json` | n/a |
| 2 | `scripts/tide_defaults.py` (new), `witchy/content.py`, `witchy/build.py`, `witchy/palette.py` | `tests/test_tide_defaults.py` (new), `tests/test_prompt_palette.py` | `content/tide-6.1.1-defaults.json` (new), spec 1, 6.1 |
| 3 | `witchy/palette.py`, `witchy/validate.py` | `tests/test_prompt_palette.py` | spec 6.2, 6.3, 6.4, 11.4 |
| 4 | `witchy/build.py`, `witchy/statusline.py`, `witchy/ritual/palette.py`, `witchy/ritual/cli.py`, `witchy/ritual/layout.py` | `tests/test_build.py`, `tests/test_statusline.py`, `tests/test_ritual_cli.py`, `tests/test_ritual_content.py`, `tests/test_ritual_package.py`, `tests/test_layout.py` | spec 7 |
| 5 | `witchy/validate.py` | `tests/test_prompt_palette.py` | spec 11.1, 11.3 |
| 6 | `witchy/fishprobe.py` (new) | `tests/fakes.py`, `tests/test_fishprobe.py` (new) | n/a |
| 7 | `witchy/components/fish.py` | `tests/fakes.py`, `tests/test_components_fish.py`, `tests/test_fish_integration.py` | n/a |
| 8 | `witchy/components/base.py`, `witchy/components/fish.py`, `witchy/runner.py`, `content/fish/conf.d/witchy.fish`, `content/fish/functions/fish_greeting.fish` | `tests/fakes.py`, `tests/test_base.py`, `tests/test_components_fish.py`, `tests/test_fish_files.py`, `tests/test_fish_integration.py` | spec 9.1, ritual 5.3 |
| 9 | none | none | none |

Order: each task needs the ones before it (Task 3 needs `build.tide` and `content.load_tide_defaults` from Task 2; Task 5 needs Task 4's `layout.WIDE`; Tasks 7 and 8 need Task 6's probe). Test counts in each step assume this order.

## Interfaces for Plans G and H

As built (Plan G and Plan H are written against these names):

```python
# witchy/components/base.py
COMMAND_TIMEOUT = 5
@dataclass(frozen=True)
class Command:
    args: tuple[str, ...]
    label: str
    input: str | None = None
    exact: bool = False
    timeout: float = COMMAND_TIMEOUT
    env: dict[str, str] = field(default_factory=dict)  # added to ctx.env
def run_command(ctx, command: Command, check: bool = True) -> subprocess.CompletedProcess
#   timeout message: "could not <label> (timed out after <timeout:g> s)"

# witchy/fishprobe.py
FISH = "fish"
SENTINEL = "witchy-fish"
TIDE_VERSION = "6.1.1"
TIDE_PLUGIN = "ilancosman/tide"
FISHER_PLUGIN = "jorgebucaran/fisher"
PROBE_SCRIPT: str
@dataclass(frozen=True)
class Probe:
    fisher: str | None             # fisher's version, None when `fisher` is not a function
    tide: str | None               # version printed by `tide --version`, None when missing
    prompt_path: str | None        # `functions --details fish_prompt`, None when undefined
    plugins: dict[str, list[str]]  # each fisher plugin (from _fisher_plugins, as installed) -> its files, HOME expanded
def fields(stdout: str) -> list[str]                          # NUL-terminated fields after the sentinel
def probe(ctx) -> Probe                                      # one fish call; ComponentFailed (cause FileNotFoundError when fish is missing)
def plugin_files(found: Probe, plugin: str) -> list[str] | None  # "owner/repo", any case, with or without "@ref"
def tide_ready(found: Probe) -> str | None
#   None, "Tide not found", "Tide is 6.0.0, not 6.1.1", "Tide is of an unknown version, not 6.1.1",
#   "fish_prompt is not Tide's (<path>)", "fish_prompt is not Tide's (no fish_prompt)"

# scripts/tide_defaults.py (run by hand; not imported by witchy)
SOURCES = (Path("functions/tide/configure/icons.fish"), Path("functions/tide/configure/configs/rainbow.fish"))
RELEASE: dict[Path, str]                                       # SHA-256 of SOURCES in the v6.1.1 release
def defaults(root: Path, release: dict[Path, str] = RELEASE) -> dict[str, list[str]]   # 156 names for the release

# witchy/content.py and witchy/build.py
content.TIDE_DEFAULTS = "tide-6.1.1-defaults.json"
def content.load_tide_defaults(content_dir=CONTENT_DIR) -> dict[str, str | tuple[str, ...]]
build.TIDE_DEFAULTS = content.CONTENT_DIR / content.TIDE_DEFAULTS
def build.tide(variant: str = palette.DEFAULT_VARIANT, content_dir: Path = content.CONTENT_DIR) -> dict[str, str | tuple[str, ...]]
def build.dict_block(name: str, values: dict[str, str]) -> str
def build.with_blocks(source: Path, blocks: dict[str, dict[str, str]]) -> str
def build.statusline_source(colours=palette.STATUSLINE, source=STATUSLINE_SOURCE, glyphs=palette.GLYPHS) -> str

# witchy/palette.py
GLYPHS: dict[str, str]             # candle scroll branch dirty separator cwd home unwritable ok fail duration jobs time caret
UNUSED_ICONS: dict[str, str]       # the 23 unused items of spec 6.4 -> icon (no bun)
VI_MODES = ("default", "insert", "replace", "visual")
TIDE: dict[str, str | tuple[str, ...]]   # overrides only
TIDE_OWN: tuple[str, ...] = ("tide_moon_bg_color", "tide_moon_color")
FISH: dict[str, str] = {"fish_emoji_width": "2"}

# witchy/validate.py
PASTEL: frozenset[str]
TIDE_SEPARATOR_GLYPHS: frozenset[str]
def is_emoji(char: str) -> bool
def is_pastel(value: str) -> bool
def validate_tide(overrides, background=palette.BACKGROUND, defaults=None) -> list[Failure]
def validate_glyphs(glyphs) -> list[Failure]

# witchy/components/fish.py
NOT_READY = "skipped: Tide not ready (run: python3 -m witchy install --only tide)"
SHELL_TIMEOUT = 15
SNAPSHOT_SCRIPT, GLOBALS_SCRIPT, SET_SCRIPT, REFRESH_SCRIPT: str
def desired(variant: str) -> dict[str, list[str]]           # build.tide + palette.FISH as fish lists (159 names)
def snapshot(ctx, names: list[str]) -> dict[str, dict]      # names asked for, then every other universal tide_*
def shadows(ctx, names: list[str]) -> dict[str, list[str]]  # globals a fresh `fish -i -c` holds (WITCHY_DOCTOR=1, 15 s)
# fish entry "variables": name -> {"previous": snapshot, "installed": [values] | None (None = erased)}

# tests/fakes.py
FAKE_FUNCTIONS = "/home/user/.config/fish/functions"
FAKE_PROMPT = f"{FAKE_FUNCTIONS}/fish_prompt.fish"
FAKE_TIDE_FILES = [FAKE_PROMPT, f"{FAKE_FUNCTIONS}/tide.fish", f"{FAKE_FUNCTIONS}/_tide_item_git.fish"]
def fake_fish(variables=None, tide="6.1.1", fail_at=None, missing=False, noise="", calls=None, fisher="4.4.5",
              prompt=FAKE_PROMPT, plugins=None, globals=None)
def fake_tide(fish_config: Path, env: dict) -> None   # real fish: a stand-in Tide 6.1.1 installed by fisher
```

Two things Plan G must know:

- **The fish component checks Tide while it plans** (D19). The runner plans every component before it applies any (ritual 3.2), so on a PC without Tide the fish plan says `skipped: Tide not ready` even when the `tide` component installs Tide in the same run. Plan G has to plan `fish` after `tide` applied (or re-plan it) for acceptance criterion 1 to hold.
- **Until Plan G adds the `tide` component, `python3 -m witchy install --only tide` (the fix this plan prints) is not a valid command.**

---
### Task 1: Commands carry their own timeout; test fixtures lose the pastel values

**Items:**
- Spec D20 / 5.1: `Command` gains `timeout` (default 5 s, as today). Plan G uses 120 s for downloads and `fisher install`; Task 8 uses 15 s.
- Spec 13 (test part): `FFB7C5` becomes Tide 6.1.1's default pwd background `3465A4` in the fish and install tests; `tests/fixtures/state-v1.json` names `Campbell` instead of `PastelOneDark`.

**Files:**
- Modify: `witchy/components/base.py` (`COMMAND_TIMEOUT` comment, `Command`, `run_command`)
- Modify: `tests/fixtures/state-v1.json:124`
- Test: `tests/test_base.py`, `tests/test_components_fish.py`, `tests/test_fish_integration.py`, `tests/test_install.py`

**Interfaces:**
- Consumes: `base.COMMAND_TIMEOUT`, `base.Command`, `base.run_command`.
- Produces: `Command(args, label, input=None, exact=False, timeout=COMMAND_TIMEOUT)`; `run_command` passes `command.timeout` to `ctx.run` and a timeout reads `could not <label> (timed out after <timeout:g> s)` (`5` and `15`, never `5.0`).

**Decisions:**
1. **The fixture purge needs no RED:** it changes only test data. `3465A4` is what Tide 6.1.1's Rainbow preset sets for `tide_pwd_bg_color` (Task 2's defaults file holds it too).

- [ ] **Step 1: Write the failing test and purge the fixtures**

In `tests/test_base.py`, in `RunCommandTest`, before `test_an_exact_command_sends_and_reads_every_byte_unchanged`, add:

```python
    def test_a_command_can_carry_its_own_timeout(self):
        seen = {}

        def run(args, **kwargs):
            seen.update(kwargs)
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])

        with self.assertRaises(ComponentFailed) as caught:
            run_command(self.ctx(run), Command(("fish", "-i", "-c", "x"), "read the shell", timeout=15))
        self.assertEqual(seen["timeout"], 15)
        self.assertEqual(str(caught.exception), "could not read the shell (timed out after 15 s)")
        self.assertEqual(Command(("x",), "do x").timeout, 5)

```

Then replace the pastel values in the test data:

```bash
sed -i 's/FFB7C5/3465A4/g' tests/test_components_fish.py tests/test_fish_integration.py tests/test_install.py
sed -i 's/"PastelOneDark"/"Campbell"/' tests/fixtures/state-v1.json
grep -rn "FFB7C5\|PastelOneDark" tests/ witchy/ --include='*.py' --include='*.json'
```

Expected: the `grep` prints nothing. Six lines change in `tests/test_components_fish.py`, one each in `tests/test_fish_integration.py`, `tests/test_install.py` and `tests/fixtures/state-v1.json`.

- [ ] **Step 2: Run the new test and watch it fail**

Run: `/usr/bin/python3 -m unittest tests.test_base.RunCommandTest.test_a_command_can_carry_its_own_timeout`
Expected:
```
ERROR: test_a_command_can_carry_its_own_timeout (...)
TypeError: Command.__init__() got an unexpected keyword argument 'timeout'
FAILED (errors=1)
```

- [ ] **Step 3: Implement**

In `witchy/components/base.py`, replace:

```python
COMMAND_TIMEOUT = 5  # seconds for every fish call (spec 5.3)
```

with:

```python
COMMAND_TIMEOUT = 5  # seconds, unless a command carries its own timeout (spec 5.3)
```

In `class Command`, replace:

```python
    An ``exact`` command's input and output travel as UTF-8 bytes with surrogate escapes and no newline
    translation, so every byte comes back as it was (a fish value can hold any byte but NUL).
    """

    args: tuple[str, ...]
    label: str
    input: str | None = None
    exact: bool = False
```

with:

```python
    An ``exact`` command's input and output travel as UTF-8 bytes with surrogate escapes and no newline
    translation, so every byte comes back as it was (a fish value can hold any byte but NUL). ``timeout`` is in
    seconds.
    """

    args: tuple[str, ...]
    label: str
    input: str | None = None
    exact: bool = False
    timeout: float = COMMAND_TIMEOUT
```

In `run_command`, replace:

```python
    """Run ``command`` through ``ctx.run`` with ``ctx.env`` and a timeout.
```

with:

```python
    """Run ``command`` through ``ctx.run`` with ``ctx.env`` and the command's timeout.
```

and replace:

```python
        done = ctx.run(list(command.args), input=data, capture_output=True, timeout=COMMAND_TIMEOUT,
                       env=dict(ctx.env), **text)
    except subprocess.TimeoutExpired as exc:  # its text would hold the whole argument list
        raise ComponentFailed(f"could not {command.label} (timed out after {COMMAND_TIMEOUT} s)") from exc
```

with:

```python
        done = ctx.run(list(command.args), input=data, capture_output=True, timeout=command.timeout,
                       env=dict(ctx.env), **text)
    except subprocess.TimeoutExpired as exc:  # its text would hold the whole argument list
        raise ComponentFailed(f"could not {command.label} (timed out after {command.timeout:g} s)") from exc
```

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 558 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/components/base.py tests/test_base.py tests/test_components_fish.py tests/test_fish_integration.py tests/test_install.py tests/fixtures/state-v1.json
git commit -m "feat: commands carry their own timeout; test fixtures drop the pastel values" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Tide 6.1.1's defaults as generated data, merged with the overrides

**Items:** spec 6.1 and D23: `content/tide-6.1.1-defaults.json` generated by `scripts/tide_defaults.py` from the source of Tide's v6.1.1 release and checked in; `build.tide(variant)` merges it with `palette.TIDE`; a test checks the merge has exactly the defaults' names plus the moon item's and that every override names one of them.

**Files:**
- Create: `scripts/tide_defaults.py`
- Create: `content/tide-6.1.1-defaults.json` (the script's output, 158 lines)
- Modify: `witchy/content.py` (`TIDE_DEFAULTS`, `load_tide_defaults`)
- Modify: `witchy/build.py` (`TIDE_DEFAULTS`, `tide`)
- Modify: `witchy/palette.py` (`TIDE_OWN`)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (sections 1 and 6.1)
- Test: `tests/test_tide_defaults.py` (new), `tests/test_prompt_palette.py` (`TIDE_6_1_1_VARIABLES`, `TIDE_6_1_1_ITEMS`)

**Interfaces:**
- Consumes: `content.CONTENT_DIR`, `palette.VARIANTS`, `palette.DEFAULT_VARIANT`, `palette.TIDE`; `tests.test_prompt_palette.TIDE_6_1_1_VARIABLES` (already in the repo, but taken from this PC's development build: this task removes the three `tide_bun_*` names, leaving the release's 156).
- Produces:
  - `scripts/tide_defaults.py`: `SOURCES`, `RELEASE: dict[Path, str]` (SHA-256 of both source files in the release), `words(line, variables) -> list[str]`, `defaults(root: Path, release: dict[Path, str] = RELEASE) -> dict[str, list[str]]`, `to_json(found) -> str`, `main(argv) -> int` (0 written, 1 refused, 2 usage). Usage: `python3 scripts/tide_defaults.py <tide source folder> [<output file>]`, where the folder holds Tide's `functions/` (the unpacked v6.1.1 release tarball).
  - `content.TIDE_DEFAULTS = "tide-6.1.1-defaults.json"`; `content.load_tide_defaults(content_dir=CONTENT_DIR) -> dict[str, str | tuple[str, ...]]` (one element → `str`, any other count → `tuple`; raises `ValueError` for anything but an object of string lists, `OSError` when missing).
  - `build.TIDE_DEFAULTS: Path`; `build.tide(variant=palette.DEFAULT_VARIANT, content_dir=content.CONTENT_DIR) -> dict[str, str | tuple[str, ...]]` (158 names today).
  - `palette.TIDE_OWN = ("tide_moon_bg_color", "tide_moon_color")`.

**Decisions:**
1. **The file holds Tide's Rainbow preset as `tide configure` loads it:** `icons.fish`, then `configs/rainbow.fish` (Tide's `style.fish` sources them in that order). In the v6.1.1 release that gives 156 names, exactly `TIDE_6_1_1_VARIABLES` once the three `tide_bun_*` names are removed from it.
2. **Only the release counts** (plan Decision 4). The Tide on this PC is the development branch: it prints `tide, version 6.1.1` too, but 12 of the release's 83 installed files differ and it adds the `bun` item (`tide_bun_bg_color`, `tide_bun_color`, `tide_bun_icon`, plus `bun` in `tide_right_prompt_items` and `bun.lockb` in `tide_pwd_markers`). The version string cannot tell them apart, so `RELEASE` pins the SHA-256 of the two files the generator reads (`icons.fish` `a800efbf…`, `configs/rainbow.fish` `01b12b0e…`), and any other tree is refused with `<file> is not the one in the Tide 6.1.1 release (a development build of Tide?)`. Hashing the two files is cheaper and more exact than counting names. Tests pass their own pins (`release=`) for the cut-down tree.
3. **`$_tide_color_*` are read from `_tide_sub_configure.fish`** (`set -g _tide_color_gold D7AF00`, `_tide_color_green 5FD700`, …). **`$os_branding_*` are fixed to Tide's generic Linux branding** (U+F17C Tux, `080808`, `CED7CF`), and the script checks `_tide_detect_os.fish` still holds `set -lx defaultColor 080808 CED7CF`. On this PC `tide configure` would pick Ubuntu's colours; witchy overrides all three `tide_os_*` (Task 3), so the choice never shows.
4. **The tokenizer reads only what these two files use** (bare words, single quotes with `\'` and `\\`, a whole-word `$name`, `#` comments) and raises on anything else: a wrong default is worse than a refused one.
5. **Values stay lists in the file; `load_tide_defaults` gives them `palette.TIDE`'s shapes,** so `{**defaults, **overrides}` is a plain merge and a one-element default (`"3465A4"`) compares equal to an override string. `tide_git_truncation_strategy` is the empty list `()`.
6. **The loader lives in `content.py`, not `build.py`:** `build` imports `validate`, and Task 5's `validate_all` needs the defaults too.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tide_defaults.py`:

```python
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import build, content, palette

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "tide_defaults.py"
_spec = importlib.util.spec_from_file_location("tide_defaults", SCRIPT)
tide_defaults = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tide_defaults)

# A Tide 6.1.1 tree cut down to the lines the generator must understand.
TIDE_FISH = "function tide\n    if set -q _flag_version\n        echo 'tide, version 6.1.1'\n    end\nend\n"
SUB_CONFIGURE = "set -g _tide_color_gold D7AF00\nset -g _tide_color_green 5FD700\n\nfunction _tide_sub_configure\nend\n"
DETECT_OS = "function _tide_detect_os\n    set -lx defaultColor 080808 CED7CF\nend\n"
ICONS = ("tide_aws_icon \uf270 # Actual aws glyph is harder to see\n"
         "tide_os_icon $os_branding_icon\n"
         "tide_prompt_icon_connection ' '\n"
         "tide_status_icon \u2714\n")
RAINBOW = ("tide_character_color $_tide_color_green\n"
           "tide_context_color_root $_tide_color_gold\n"
           "tide_git_truncation_strategy\n"
           "tide_left_prompt_prefix ''\n"
           "tide_os_bg_color $os_branding_bg_color\n"
           "tide_pwd_bg_color 3465A4\n"
           "tide_pwd_markers .bzr .git build.zig\n"
           "tide_right_prompt_suffix 'it\\'s'\n")


class TreeTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.write("functions/tide.fish", TIDE_FISH)
        self.write("functions/_tide_sub_configure.fish", SUB_CONFIGURE)
        self.write("functions/_tide_detect_os.fish", DETECT_OS)
        self.write("functions/tide/configure/icons.fish", ICONS)
        self.write("functions/tide/configure/configs/rainbow.fish", RAINBOW)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def release(self):
        """Pins that make this tree count as the release, as it is now."""
        return {source: hashlib.sha256((self.root / source).read_bytes()).hexdigest()
                for source in tide_defaults.SOURCES}

    def defaults(self):
        return tide_defaults.defaults(self.root, self.release())


class GeneratorTest(TreeTestCase):
    def test_reads_the_rainbow_preset_with_tides_own_colours_and_generic_os_branding(self):
        self.assertEqual(self.defaults(), {
            "tide_aws_icon": ["\uf270"],
            "tide_character_color": ["5FD700"],
            "tide_context_color_root": ["D7AF00"],
            "tide_git_truncation_strategy": [],
            "tide_left_prompt_prefix": [""],
            "tide_os_bg_color": ["CED7CF"],
            "tide_os_icon": ["\uf17c"],
            "tide_prompt_icon_connection": [" "],
            "tide_pwd_bg_color": ["3465A4"],
            "tide_pwd_markers": [".bzr", ".git", "build.zig"],
            "tide_right_prompt_suffix": ["it's"],
            "tide_status_icon": ["\u2714"],
        })

    def test_refuses_a_tree_that_is_not_tide_6_1_1(self):
        self.write("functions/tide.fish", TIDE_FISH.replace("6.1.1", "6.0.0"))
        with self.assertRaisesRegex(ValueError, r"is not Tide 6\.1\.1"):
            self.defaults()

    def test_refuses_a_development_build_that_also_says_6_1_1(self):
        with self.assertRaisesRegex(ValueError, r"icons\.fish is not the one in the Tide 6\.1\.1 release "
                                                r"\(a development build of Tide\?\)"):
            tide_defaults.defaults(self.root)

    def test_the_release_pins_are_the_two_files_read(self):
        self.assertEqual(set(tide_defaults.RELEASE), set(tide_defaults.SOURCES))

    def test_refuses_os_branding_it_does_not_know(self):
        self.write("functions/_tide_detect_os.fish", DETECT_OS.replace("CED7CF", "FFFFFF"))
        with self.assertRaisesRegex(ValueError, r"generic Linux branding"):
            self.defaults()

    def test_refuses_fish_syntax_it_cannot_read_safely(self):
        for line in ('tide_a "double"\n', "tide_a (command)\n", "tide_a x$y\n", "tide_a $unknown\n",
                     "tide_a 'open\n", "tide_a back\\slash\n"):
            with self.subTest(line=line):
                self.write("functions/tide/configure/configs/rainbow.fish", RAINBOW + line)
                with self.assertRaises(ValueError):
                    self.defaults()

    def test_refuses_a_name_set_twice(self):
        self.write("functions/tide/configure/configs/rainbow.fish", RAINBOW + "tide_status_icon x\n")
        with self.assertRaisesRegex(ValueError, r"tide_status_icon is set twice"):
            self.defaults()

    def test_main_writes_sorted_ascii_json_and_reports_errors(self):
        out = self.root / "out.json"
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr), \
                mock.patch.dict(tide_defaults.RELEASE, self.release()):
            self.assertEqual(tide_defaults.main([str(self.root), str(out)]), 0)
            self.assertEqual(tide_defaults.main([str(self.root / "missing"), str(out)]), 1)
        text = out.read_text(encoding="ascii")
        self.assertEqual(json.loads(text), self.defaults())
        self.assertEqual(list(json.loads(text)), sorted(json.loads(text)))
        self.assertTrue(text.endswith("}\n"))
        self.assertIn(f"wrote 12 Tide variables to {out}", stdout.getvalue())
        self.assertIn("tide_defaults: ", stderr.getvalue())


class CheckedInDefaultsTest(unittest.TestCase):
    def test_holds_every_tide_6_1_1_variable_once(self):
        from tests.test_prompt_palette import TIDE_6_1_1_VARIABLES
        raw = json.loads((content.CONTENT_DIR / content.TIDE_DEFAULTS).read_text(encoding="utf-8"))
        self.assertEqual(set(raw), TIDE_6_1_1_VARIABLES)
        self.assertEqual(len(raw), 156)

    def test_holds_tides_rainbow_values(self):
        defaults = content.load_tide_defaults()
        self.assertEqual(defaults["tide_pwd_bg_color"], "3465A4")
        self.assertEqual(defaults["tide_character_color"], "5FD700")
        self.assertEqual(defaults["tide_left_prompt_separator_diff_color"], "\ue0b0")
        self.assertEqual(defaults["tide_time_format"], "%T")
        self.assertEqual(defaults["tide_git_truncation_strategy"], ())
        self.assertEqual(defaults["tide_left_prompt_items"], ("pwd", "git", "newline"))
        self.assertEqual(defaults["tide_os_icon"], "\uf17c")

    def test_a_file_that_is_not_names_and_lists_of_strings_is_refused(self):
        for text in ("[]", '{"tide_a": "x"}', '{"tide_a": [1]}', '{"": ["x"]}', "not json"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / content.TIDE_DEFAULTS).write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    content.load_tide_defaults(Path(tmp))


class MergeTest(unittest.TestCase):
    def test_every_default_plus_witchys_own_items(self):
        defaults = content.load_tide_defaults()
        merged = build.tide()
        self.assertEqual(set(merged), set(defaults) | set(palette.TIDE_OWN))
        self.assertEqual(len(merged), 158)

    def test_every_override_names_a_tide_variable_or_witchys_own(self):
        defaults = content.load_tide_defaults()
        self.assertEqual(set(palette.TIDE) - set(defaults) - set(palette.TIDE_OWN), set())

    def test_overrides_win_and_the_rest_keeps_tides_default(self):
        merged = build.tide()
        self.assertEqual(merged["tide_pwd_bg_color"], palette.TIDE["tide_pwd_bg_color"])
        self.assertEqual(merged["tide_pwd_markers"], content.load_tide_defaults()["tide_pwd_markers"])
        self.assertEqual(merged["tide_prompt_min_cols"], "34")

    def test_the_variant_supplies_the_overrides(self):
        midnight = palette.VARIANTS["midnight"]
        dawn = palette.Variant(**{**midnight.__dict__, "name": "dawn",
                                  "tide": dict(midnight.tide, tide_pwd_bg_color="D0B8FF")})
        with mock.patch.dict(palette.VARIANTS, {"dawn": dawn}):
            self.assertEqual(build.tide("dawn")["tide_pwd_bg_color"], "D0B8FF")
        self.assertEqual(build.tide(), build.tide(palette.DEFAULT_VARIANT))

    def test_the_path_constant_points_at_the_checked_in_file(self):
        self.assertEqual(build.TIDE_DEFAULTS, content.CONTENT_DIR / "tide-6.1.1-defaults.json")
        self.assertTrue(build.TIDE_DEFAULTS.is_file())


if __name__ == "__main__":
    unittest.main()
```

In `tests/test_prompt_palette.py`, the two lists of Tide 6.1.1 names were taken from this PC's development build. Replace:

```python
# `fish -c 'set -U | string match -r "^tide_\S+"'` on Tide 6.1.1 (2026-10-03), the version the spec targets.
TIDE_6_1_1_VARIABLES = frozenset("""
tide_aws_bg_color tide_aws_color tide_aws_icon tide_bun_bg_color tide_bun_color tide_bun_icon tide_character_color
```

with:

```python
# The 156 names of Tide's v6.1.1 release tag (its icons.fish and configs/rainbow.fish), the version the spec
# targets. Tide's development branch, which also calls itself 6.1.1, adds tide_bun_bg_color, _color and _icon.
TIDE_6_1_1_VARIABLES = frozenset("""
tide_aws_bg_color tide_aws_color tide_aws_icon tide_character_color
```

and replace:

```python
# Tide 6.1.1's prompt items: its _tide_item_* functions, plus pwd and newline from _tide_2_line_prompt.
TIDE_6_1_1_ITEMS = frozenset("""
aws bun character cmd_duration context crystal direnv distrobox docker elixir gcloud git go java jobs kubectl
```

with:

```python
# The release's prompt items: its _tide_item_* functions, plus pwd and newline from _tide_2_line_prompt.
TIDE_6_1_1_ITEMS = frozenset("""
aws character cmd_duration context crystal direnv distrobox docker elixir gcloud git go java jobs kubectl
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_tide_defaults`
Expected:
```
ERROR: test_tide_defaults (unittest.loader._FailedTest.test_tide_defaults)
FileNotFoundError: [Errno 2] No such file or directory: '…/scripts/tide_defaults.py'
FAILED (errors=1)
```

- [ ] **Step 3: Write the generator**

Create `scripts/tide_defaults.py`:

```python
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
```

- [ ] **Step 4: Generate the defaults from the Tide v6.1.1 release**

Download and unpack the release (network allowed for this step only), then generate:

```bash
TIDE_SRC=$(mktemp -d)
curl -sSfL https://codeload.github.com/IlanCosman/tide/tar.gz/refs/tags/v6.1.1 | tar xz -C "$TIDE_SRC"
python3 scripts/tide_defaults.py "$TIDE_SRC/tide-6.1.1"
```

Expected: `wrote 156 Tide variables to <repo>/content/tide-6.1.1-defaults.json`, where `<repo>` is the checkout the script sits in. Keep `$TIDE_SRC` for Task 9.

The installed Tide on this PC is refused (read only, nothing is written):

Run: `python3 scripts/tide_defaults.py ~/.config/fish /dev/null; echo "exit=$?"`
Expected: `tide_defaults: /home/eimi/.config/fish/functions/tide/configure/icons.fish is not the one in the Tide 6.1.1 release (a development build of Tide?)`, then `exit=1`.

Check the file is the prototype's, byte for byte:

Run: `sha256sum content/tide-6.1.1-defaults.json`
Expected: `1fcdc5cfee7c3312505f30d2e70c72356a5da8986fdee1c89f2d0f9743b86f62  content/tide-6.1.1-defaults.json`

Without network, write the file by hand with exactly this content (158 lines, ending in a newline):

```json
{
  "tide_aws_bg_color": ["FF9900"],
  "tide_aws_color": ["232F3E"],
  "tide_aws_icon": ["\uf270"],
  "tide_character_color": ["5FD700"],
  "tide_character_color_failure": ["FF0000"],
  "tide_character_icon": ["\u276f"],
  "tide_character_vi_icon_default": ["\u276e"],
  "tide_character_vi_icon_replace": ["\u25b6"],
  "tide_character_vi_icon_visual": ["V"],
  "tide_cmd_duration_bg_color": ["C4A000"],
  "tide_cmd_duration_color": ["000000"],
  "tide_cmd_duration_decimals": ["0"],
  "tide_cmd_duration_icon": [],
  "tide_cmd_duration_threshold": ["3000"],
  "tide_context_always_display": ["false"],
  "tide_context_bg_color": ["444444"],
  "tide_context_color_default": ["D7AF87"],
  "tide_context_color_root": ["D7AF00"],
  "tide_context_color_ssh": ["D7AF87"],
  "tide_context_hostname_parts": ["1"],
  "tide_crystal_bg_color": ["FFFFFF"],
  "tide_crystal_color": ["000000"],
  "tide_crystal_icon": ["\ue62f"],
  "tide_direnv_bg_color": ["D7AF00"],
  "tide_direnv_bg_color_denied": ["FF0000"],
  "tide_direnv_color": ["000000"],
  "tide_direnv_color_denied": ["000000"],
  "tide_direnv_icon": ["\u25bc"],
  "tide_distrobox_bg_color": ["FF00FF"],
  "tide_distrobox_color": ["000000"],
  "tide_distrobox_icon": ["\udb80\udda7"],
  "tide_docker_bg_color": ["2496ED"],
  "tide_docker_color": ["000000"],
  "tide_docker_default_contexts": ["default", "colima"],
  "tide_docker_icon": ["\uf308"],
  "tide_elixir_bg_color": ["4E2A8E"],
  "tide_elixir_color": ["000000"],
  "tide_elixir_icon": ["\ue62d"],
  "tide_gcloud_bg_color": ["4285F4"],
  "tide_gcloud_color": ["000000"],
  "tide_gcloud_icon": ["\udb80\udead"],
  "tide_git_bg_color": ["4E9A06"],
  "tide_git_bg_color_unstable": ["C4A000"],
  "tide_git_bg_color_urgent": ["CC0000"],
  "tide_git_color_branch": ["000000"],
  "tide_git_color_conflicted": ["000000"],
  "tide_git_color_dirty": ["000000"],
  "tide_git_color_operation": ["000000"],
  "tide_git_color_staged": ["000000"],
  "tide_git_color_stash": ["000000"],
  "tide_git_color_untracked": ["000000"],
  "tide_git_color_upstream": ["000000"],
  "tide_git_icon": [],
  "tide_git_truncation_length": ["24"],
  "tide_git_truncation_strategy": [],
  "tide_go_bg_color": ["00ACD7"],
  "tide_go_color": ["000000"],
  "tide_go_icon": ["\ue627"],
  "tide_java_bg_color": ["ED8B00"],
  "tide_java_color": ["000000"],
  "tide_java_icon": ["\ue256"],
  "tide_jobs_bg_color": ["444444"],
  "tide_jobs_color": ["4E9A06"],
  "tide_jobs_icon": ["\uf013"],
  "tide_jobs_number_threshold": ["1000"],
  "tide_kubectl_bg_color": ["326CE5"],
  "tide_kubectl_color": ["000000"],
  "tide_kubectl_icon": ["\udb84\udcfe"],
  "tide_left_prompt_frame_enabled": ["true"],
  "tide_left_prompt_items": ["pwd", "git", "newline"],
  "tide_left_prompt_prefix": [""],
  "tide_left_prompt_separator_diff_color": ["\ue0b0"],
  "tide_left_prompt_separator_same_color": ["\ue0b1"],
  "tide_left_prompt_suffix": ["\ue0b0"],
  "tide_nix_shell_bg_color": ["7EBAE4"],
  "tide_nix_shell_color": ["000000"],
  "tide_nix_shell_icon": ["\uf313"],
  "tide_node_bg_color": ["44883E"],
  "tide_node_color": ["000000"],
  "tide_node_icon": ["\ue24f"],
  "tide_os_bg_color": ["CED7CF"],
  "tide_os_color": ["080808"],
  "tide_os_icon": ["\uf17c"],
  "tide_php_bg_color": ["617CBE"],
  "tide_php_color": ["000000"],
  "tide_php_icon": ["\ue608"],
  "tide_private_mode_bg_color": ["F1F3F4"],
  "tide_private_mode_color": ["000000"],
  "tide_private_mode_icon": ["\udb81\uddf9"],
  "tide_prompt_add_newline_before": ["true"],
  "tide_prompt_color_frame_and_connection": ["6C6C6C"],
  "tide_prompt_color_separator_same_color": ["949494"],
  "tide_prompt_icon_connection": [" "],
  "tide_prompt_min_cols": ["34"],
  "tide_prompt_pad_items": ["true"],
  "tide_prompt_transient_enabled": ["false"],
  "tide_pulumi_bg_color": ["F7BF2A"],
  "tide_pulumi_color": ["000000"],
  "tide_pulumi_icon": ["\uf1b2"],
  "tide_pwd_bg_color": ["3465A4"],
  "tide_pwd_color_anchors": ["E4E4E4"],
  "tide_pwd_color_dirs": ["E4E4E4"],
  "tide_pwd_color_truncated_dirs": ["BCBCBC"],
  "tide_pwd_icon": [],
  "tide_pwd_icon_home": [],
  "tide_pwd_icon_unwritable": ["\uf023"],
  "tide_pwd_markers": [".bzr", ".citc", ".git", ".hg", ".node-version", ".python-version", ".ruby-version", ".shorten_folder_marker", ".svn", ".terraform", "Cargo.toml", "composer.json", "CVS", "go.mod", "package.json", "build.zig"],
  "tide_python_bg_color": ["444444"],
  "tide_python_color": ["00AFAF"],
  "tide_python_icon": ["\udb80\udf20"],
  "tide_right_prompt_frame_enabled": ["true"],
  "tide_right_prompt_items": ["status", "cmd_duration", "context", "jobs", "direnv", "node", "python", "rustc", "java", "php", "pulumi", "ruby", "go", "gcloud", "kubectl", "distrobox", "toolbox", "terraform", "aws", "nix_shell", "crystal", "elixir", "zig"],
  "tide_right_prompt_prefix": ["\ue0b2"],
  "tide_right_prompt_separator_diff_color": ["\ue0b2"],
  "tide_right_prompt_separator_same_color": ["\ue0b3"],
  "tide_right_prompt_suffix": [""],
  "tide_ruby_bg_color": ["B31209"],
  "tide_ruby_color": ["000000"],
  "tide_ruby_icon": ["\ue23e"],
  "tide_rustc_bg_color": ["F74C00"],
  "tide_rustc_color": ["000000"],
  "tide_rustc_icon": ["\ue7a8"],
  "tide_shlvl_bg_color": ["808000"],
  "tide_shlvl_color": ["000000"],
  "tide_shlvl_icon": ["\uf120"],
  "tide_shlvl_threshold": ["1"],
  "tide_status_bg_color": ["2E3436"],
  "tide_status_bg_color_failure": ["CC0000"],
  "tide_status_color": ["4E9A06"],
  "tide_status_color_failure": ["FFFF00"],
  "tide_status_icon": ["\u2714"],
  "tide_status_icon_failure": ["\u2718"],
  "tide_terraform_bg_color": ["800080"],
  "tide_terraform_color": ["000000"],
  "tide_terraform_icon": ["\udb84\udc62"],
  "tide_time_bg_color": ["D3D7CF"],
  "tide_time_color": ["000000"],
  "tide_time_format": ["%T"],
  "tide_toolbox_bg_color": ["613583"],
  "tide_toolbox_color": ["000000"],
  "tide_toolbox_icon": ["\ue24f"],
  "tide_vi_mode_bg_color_default": ["949494"],
  "tide_vi_mode_bg_color_insert": ["87AFAF"],
  "tide_vi_mode_bg_color_replace": ["87AF87"],
  "tide_vi_mode_bg_color_visual": ["FF8700"],
  "tide_vi_mode_color_default": ["000000"],
  "tide_vi_mode_color_insert": ["000000"],
  "tide_vi_mode_color_replace": ["000000"],
  "tide_vi_mode_color_visual": ["000000"],
  "tide_vi_mode_icon_default": ["D"],
  "tide_vi_mode_icon_insert": ["I"],
  "tide_vi_mode_icon_replace": ["R"],
  "tide_vi_mode_icon_visual": ["V"],
  "tide_zig_bg_color": ["F7A41D"],
  "tide_zig_color": ["000000"],
  "tide_zig_icon": ["\ue6a9"]
}
```

- [ ] **Step 5: Load and merge**

In `witchy/content.py`, replace:

```python
RITUAL = "ritual.json"
```

with:

```python
RITUAL = "ritual.json"
TIDE_DEFAULTS = "tide-6.1.1-defaults.json"  # written by scripts/tide_defaults.py (spec 6.1)
```

and before `def read_output_style(`, add:

```python
def load_tide_defaults(content_dir: Path = CONTENT_DIR) -> dict[str, str | tuple[str, ...]]:
    """Tide 6.1.1's own value for each of its variables, in palette.TIDE's shapes: one element as a string,
    any other count as a tuple."""
    data = json.loads((content_dir / TIDE_DEFAULTS).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(
            isinstance(name, str) and name and isinstance(values, list) and all(isinstance(v, str) for v in values)
            for name, values in data.items()):
        raise ValueError(f"{TIDE_DEFAULTS} must map each variable name to a list of strings")
    return {name: values[0] if len(values) == 1 else tuple(values) for name, values in data.items()}


```

In `witchy/build.py`, replace:

```python
FISH_SOURCE = content.CONTENT_DIR / "fish"
```

with:

```python
FISH_SOURCE = content.CONTENT_DIR / "fish"
TIDE_DEFAULTS = content.CONTENT_DIR / content.TIDE_DEFAULTS
```

and before `def fish_quote(`, add:

```python
def tide(variant: str = palette.DEFAULT_VARIANT,
         content_dir: Path = content.CONTENT_DIR) -> dict[str, str | tuple[str, ...]]:
    """Every Tide variable witchy sets: Tide 6.1.1's defaults with the variant's overrides on top (spec 6.1)."""
    return {**content.load_tide_defaults(content_dir), **palette.VARIANTS[variant].tide}


```

In `witchy/palette.py`, after the closing `}` of `TIDE` and before `# eza (spec 7)`, add:

```python
# Variables of witchy's own prompt items, which Tide does not define: the moon item's colours (spec 5.1).
TIDE_OWN: tuple[str, ...] = ("tide_moon_bg_color", "tide_moon_color")

```

In `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md`, section 1, replace:

```
2. witchy sets only Tide's colours and item lists (`palette.TIDE`, 31 variables). Tide has 161 universal variables.
```

with:

```
2. witchy sets only Tide's colours and item lists (`palette.TIDE`, 31 variables). This PC has 161 universal `tide_*` variables (its Tide is a development build that still calls itself 6.1.1; the 6.1.1 release defines 156, and witchy's moon item adds 2).
```

(the rest of that line stays). Section 6.1, replace:

```
witchy now sets every universal variable Tide 6.1.1 defines (161 names on this PC). Defaults and taste are kept apart (D23):

- `content/tide-6.1.1-defaults.json` holds Tide 6.1.1's Rainbow-preset values, generated once by `scripts/tide_defaults.py` from Tide's `functions/tide/configure/configs/rainbow.fish` and `icons.fish`, and checked in.
```

with:

```
witchy now sets every universal variable the Tide 6.1.1 release defines (156 names) and the moon item's two (`tide_moon_bg_color`, `tide_moon_color`): 158 names. Defaults and taste are kept apart (D23):

- `content/tide-6.1.1-defaults.json` holds Tide 6.1.1's Rainbow-preset values, generated once by `scripts/tide_defaults.py` from Tide's `functions/tide/configure/configs/rainbow.fish` and `icons.fish` in the v6.1.1 release tag, and checked in. The generator refuses any other tree, including a development build that also prints `tide, version 6.1.1` (it pins the SHA-256 of both files). Tide's own colour names (`$_tide_color_green`, …) are resolved from `_tide_sub_configure.fish`. The OS branding differs per machine, so the file records Tide's generic Linux branding; witchy overrides all three `tide_os_*` anyway.
```

and replace:

```
- `build.tide(variant)` merges them. A test checks the merge has exactly the names in the defaults file and every override names one of them.
```

with:

```
- `build.tide(variant)` merges them. A test checks the merge has exactly the names in the defaults file plus the moon item's (`palette.TIDE_OWN`), and every override names one of those.
```

- [ ] **Step 6: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 574 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 7: Commit**

```bash
git add scripts/tide_defaults.py content/tide-6.1.1-defaults.json witchy/content.py witchy/build.py witchy/palette.py tests/test_tide_defaults.py tests/test_prompt_palette.py docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: Tide 6.1.1's defaults as generated data, merged with witchy's overrides" -m "scripts/tide_defaults.py reads the Rainbow preset of Tide's v6.1.1 release (both source files pinned by SHA-256, so a development build is refused); content/tide-6.1.1-defaults.json is its output. build.tide(variant) puts the variant's overrides on top." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The witchy prompt: glyph table, Slanted shape, icons and colours for every Tide item

**Items:** spec 6.2 (shape), 6.3 (glyph map and caret colours), 6.4 (unused items), 6.1 (`fish_emoji_width` = `2`), 7 (`palette.GLYPHS`), 11.4 (the new contrast pairs). Frame deviation (Decision 1).

**Files:**
- Modify: `witchy/palette.py` (`GLYPHS`, `UNUSED_ICONS`, `VI_MODES`, `TIDE`, `FISH`)
- Modify: `witchy/validate.py` (`TIDE_ITEMS`, `VI_MODES`, `TIDE_ITEM_PAIRS`, `TIDE_SEPARATOR_GLYPHS`, `is_tide_colour`, the pair loop in `validate_tide`)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (sections 6.2, 6.3, 6.4, 11.4)
- Test: `tests/test_prompt_palette.py`

**Interfaces:**
- Consumes: `build.tide()`, `content.load_tide_defaults()`, `palette.TIDE_OWN` (Task 2).
- Produces:
  - `palette.GLYPHS: dict[str, str]` with keys `candle scroll branch dirty separator cwd home unwritable ok fail duration jobs time caret` (Task 4 writes it into two files).
  - `palette.UNUSED_ICONS: dict[str, str]` (23 items → icon; no `bun`, which only Tide's development branch has), `palette.VI_MODES`, `palette.FISH = {"fish_emoji_width": "2"}` (Task 7 sets it).
  - `palette.TIDE`: witchy's overrides of spec 6.2–6.4 (141 names; every colour Tide defines is overridden).
  - `validate.TIDE_ITEM_PAIRS`, `validate.TIDE_SEPARATOR_GLYPHS`; `validate.is_tide_colour(key)` is false for the four separator-glyph names.

**Decisions:**
1. **The frame keeps `6E5A80`** (plan Decision 1); spec 6.2 and 11.4 say so.
2. **`jobs` joins the muted pair** (plan Decision 10). Every other new visible colour is a pair validate already knows (`A99AB9` and `FF6B9F` on `1D1230`: 6.78:1 and 6.65:1; the caret `FFD477` on `0D0916`: 13.99:1).
3. **No `bun` item.** Spec 6.4 gave `bun` 🥟, but the Tide 6.1.1 release has no bun item or `tide_bun_*` variable (only the development branch on this PC does); an override for it would fail Task 2's `test_every_override_names_a_tide_variable_or_witchys_own` and, later, validation rule 11.2. Spec 6.4 drops it.
4. **The unused items are generated from `UNUSED_ICONS`** in one comprehension (icon, `1D1230`, `A99AB9` each), so adding an item cannot miss a colour. `context` and `vi_mode` keep Tide's text (no icon override); their colours and the denied direnv are listed by hand.
5. **`tide_left_prompt_separator_same_color` and `tide_right_prompt_separator_same_color` are not overridden** (spec 6.2: Tide's Rainbow defaults `\ue0b1` and `\ue0b3`).
6. **Separator glyphs are not colours** (plan Decision 11). Without this the merged prompt would fail the colour format check in Task 5.
7. **`validate_all` still validates the overrides only in this task;** Task 5 switches it to the merged prompt. Every colour Tide defines is already overridden (`test_every_colour_tide_defines_is_a_palette_colour`), so the contrast rules see the same colours either way.

- [ ] **Step 1: Write the failing tests**

In `tests/test_prompt_palette.py`, replace:

```python
from witchy import build, palette, validate
```

with:

```python
from witchy import build, content, palette, validate
```

In `TideNamesTest`, delete the whole `test_the_spec_variables_are_all_there` method (it pinned 32 variables).

In `TideNamesTest.test_every_tide_colour_is_validated_for_contrast_or_exempt`, replace:

```python
        checked = {name for pair in validate.TIDE_TEXT_PAIRS + validate.TIDE_SECONDARY_PAIRS for name in pair if name}
```

with:

```python
        checked = {name for pair in validate.TIDE_TEXT_PAIRS + validate.TIDE_ITEM_PAIRS + validate.TIDE_SECONDARY_PAIRS
                   for name in pair if name}
```

Replace the whole `TideNamesTest.test_colour_keys_are_the_ones_with_a_colour_word` method (up to the two blank lines before `class TideValidateTest`) with:

```python
    def test_colour_keys_are_the_ones_with_a_colour_word(self):
        for key in ("tide_pwd_bg_color", "tide_git_color_branch", "tide_context_color_default",
                    "tide_prompt_color_separator_same_color"):
            self.assertTrue(validate.is_tide_colour(key), key)
        for key in ("tide_left_prompt_items", "tide_cmd_duration_threshold", "tide_colorful_icon", "tide_pwd_decolor"):
            self.assertFalse(validate.is_tide_colour(key), key)

    def test_the_separator_glyphs_are_not_colours(self):
        # Tide names them with "color", but they hold the glyph drawn between two segments.
        for key in ("tide_left_prompt_separator_diff_color", "tide_left_prompt_separator_same_color",
                    "tide_right_prompt_separator_diff_color", "tide_right_prompt_separator_same_color"):
            self.assertFalse(validate.is_tide_colour(key), key)
        self.assertEqual(validate.validate_tide(dict(palette.TIDE, tide_left_prompt_separator_diff_color="\ue0bc")),
                         [])


# The unused items of spec 6.4 and their icons.
UNUSED_ICONS = {
    "aws": "🏺", "crystal": "💠", "direnv": "🍃", "distrobox": "📦", "docker": "🐳", "elixir": "💧",
    "gcloud": "⛅", "go": "🐹", "java": "☕", "kubectl": "🎡", "nix_shell": "🧊", "node": "🍄", "os": "🐧",
    "php": "🐘", "private_mode": "🎭", "pulumi": "🧬", "python": "🐍", "ruby": "💎", "rustc": "🦀", "shlvl": "🌀",
    "terraform": "🧱", "toolbox": "🧰", "zig": "⚡",
}


class TideLookTest(unittest.TestCase):
    """The prompt the spec draws (spec 6.2-6.4)."""

    def test_two_framed_lines_with_slanted_caps(self):
        expected = {
            "tide_left_prompt_items": ("moon", "pwd", "git", "newline", "character"),
            "tide_right_prompt_items": ("status", "cmd_duration", "jobs", "time"),
            "tide_left_prompt_prefix": "\ue0ba", "tide_left_prompt_suffix": "\ue0bc",
            "tide_right_prompt_prefix": "\ue0ba", "tide_right_prompt_suffix": "\ue0bc",
            "tide_left_prompt_separator_diff_color": "\ue0bc", "tide_right_prompt_separator_diff_color": "\ue0ba",
            "tide_left_prompt_frame_enabled": "true", "tide_right_prompt_frame_enabled": "true",
            "tide_prompt_transient_enabled": "true", "tide_prompt_add_newline_before": "true",
            "tide_prompt_icon_connection": "·", "tide_prompt_color_frame_and_connection": "6E5A80",
            "tide_cmd_duration_threshold": "3000",
        }
        self.assertEqual({name: palette.TIDE[name] for name in expected}, expected)

    def test_same_colour_separators_keep_tides_rainbow_default(self):
        defaults = content.load_tide_defaults()
        for name in ("tide_left_prompt_separator_same_color", "tide_right_prompt_separator_same_color"):
            self.assertNotIn(name, palette.TIDE)
            self.assertEqual(build.tide()[name], defaults[name])

    def test_the_glyph_map(self):
        expected = {
            "tide_pwd_icon": "🧹", "tide_pwd_icon_home": "🔮", "tide_pwd_icon_unwritable": "🪦", "tide_git_icon": "🌿",
            "tide_status_icon": "🧪", "tide_status_icon_failure": "💀", "tide_cmd_duration_icon": "🔥",
            "tide_jobs_icon": "🐈", "tide_time_format": "%H:%M 🦉", "tide_character_icon": "❯",
            "tide_character_vi_icon_default": "❮", "tide_character_vi_icon_replace": "▶",
            "tide_character_vi_icon_visual": "V",
        }
        self.assertEqual({name: palette.TIDE[name] for name in expected}, expected)

    def test_prompt_icons_come_from_the_shared_table(self):
        uses = {"tide_pwd_icon": "cwd", "tide_pwd_icon_home": "home", "tide_pwd_icon_unwritable": "unwritable",
                "tide_git_icon": "branch", "tide_status_icon": "ok", "tide_status_icon_failure": "fail",
                "tide_cmd_duration_icon": "duration", "tide_jobs_icon": "jobs", "tide_character_icon": "caret"}
        for name, key in uses.items():
            self.assertEqual(palette.TIDE[name], palette.GLYPHS[key], name)
        self.assertEqual(palette.TIDE["tide_time_format"], "%H:%M " + palette.GLYPHS["time"])

    def test_the_caret_is_candle_gold_and_rose_red_on_failure(self):
        self.assertEqual((palette.TIDE["tide_character_color"], palette.TIDE["tide_character_color_failure"]),
                         ("FFD477", "FF6B9F"))

    def test_jobs_and_unused_items_wear_witchy_icons_on_the_muted_pair(self):
        self.assertEqual((palette.TIDE["tide_jobs_bg_color"], palette.TIDE["tide_jobs_color"]), ("1D1230", "A99AB9"))
        for item, icon in UNUSED_ICONS.items():
            with self.subTest(item=item):
                self.assertEqual((palette.TIDE[f"tide_{item}_icon"], palette.TIDE[f"tide_{item}_bg_color"],
                                  palette.TIDE[f"tide_{item}_color"]), (icon, "1D1230", "A99AB9"))

    def test_context_and_vi_mode_keep_tides_text_in_palette_colours(self):
        self.assertNotIn("tide_vi_mode_icon_default", palette.TIDE)
        expected = {
            "tide_context_bg_color": "1D1230", "tide_context_color_default": "A99AB9",
            "tide_context_color_root": "FF6B9F", "tide_context_color_ssh": "FF6B9F",
            "tide_direnv_bg_color_denied": "1D1230", "tide_direnv_color_denied": "FF6B9F",
            **{f"tide_vi_mode_bg_color_{mode}": "1D1230" for mode in ("default", "insert", "replace", "visual")},
            **{f"tide_vi_mode_color_{mode}": "A99AB9" for mode in ("default", "insert", "replace", "visual")},
        }
        self.assertEqual({name: palette.TIDE[name] for name in expected}, expected)

    def test_every_colour_tide_defines_is_a_palette_colour(self):
        colours = {name for name in content.load_tide_defaults() if validate.is_tide_colour(name)}
        self.assertEqual(colours - set(palette.TIDE), set())


class SharedTablesTest(unittest.TestCase):
    def test_the_glyph_table(self):
        self.assertEqual(palette.GLYPHS, {
            "candle": "\U0001F56F\uFE0F", "scroll": "📜", "branch": "🌿", "dirty": "✦", "separator": "⋆",
            "cwd": "🧹", "home": "🔮", "unwritable": "🪦", "ok": "🧪", "fail": "💀", "duration": "🔥", "jobs": "🐈",
            "time": "🦉", "caret": "❯",
        })

    def test_fish_draws_emoji_two_cells_wide(self):
        self.assertEqual(palette.FISH, {"fish_emoji_width": "2"})
```

In `TideValidateTest`, before `test_a_missing_variable_is_reported`, add:

```python
    def test_unused_items_and_jobs_read_on_their_background(self):
        dark = "2A1F3D"
        tide = dict(palette.TIDE, tide_aws_color=dark, tide_jobs_color=dark, tide_direnv_color_denied=dark,
                    tide_context_color_root=dark, tide_vi_mode_color_insert=dark)
        self.assertLessEqual({("text-contrast", "tide.tide_aws_color on tide_aws_bg_color"),
                              ("text-contrast", "tide.tide_jobs_color on tide_jobs_bg_color"),
                              ("text-contrast", "tide.tide_direnv_color_denied on tide_direnv_bg_color_denied"),
                              ("text-contrast", "tide.tide_context_color_root on tide_context_bg_color"),
                              ("text-contrast", "tide.tide_vi_mode_color_insert on tide_vi_mode_bg_color_insert")},
                             pairs(validate.validate_tide(tide)))

```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_prompt_palette`
Expected (real output from the prototype, abridged):
```
ERROR: test_the_glyph_table (...)              AttributeError: module 'witchy.palette' has no attribute 'GLYPHS'
ERROR: test_fish_draws_emoji_two_cells_wide (...)  AttributeError: module 'witchy.palette' has no attribute 'FISH'
ERROR: test_two_framed_lines_with_slanted_caps (...)  KeyError: 'tide_left_prompt_prefix'
ERROR: test_the_glyph_map / test_prompt_icons_come_from_the_shared_table  KeyError: 'tide_pwd_icon'
ERROR: test_jobs_and_unused_items_wear_witchy_icons_on_the_muted_pair  KeyError: 'tide_jobs_bg_color'
ERROR: test_context_and_vi_mode_keep_tides_text_in_palette_colours  KeyError: 'tide_context_bg_color'
FAIL: test_the_caret_is_candle_gold_and_rose_red_on_failure  ('FF67B7', 'FF6B9F') != ('FFD477', 'FF6B9F')
FAIL: test_the_separator_glyphs_are_not_colours  True is not false : tide_left_prompt_separator_diff_color
FAIL: test_unused_items_and_jobs_read_on_their_background
FAIL: test_every_colour_tide_defines_is_a_palette_colour
FAILED (failures=4, errors=8)
```
(`test_every_tide_colour_is_validated_for_contrast_or_exempt` errors too, with `AttributeError: … 'TIDE_ITEM_PAIRS'`.)

- [ ] **Step 3: Implement the look**

In `witchy/palette.py`, replace the whole block from `# The Tide prompt (spec 5.2): fish universal variables.` down to and including the closing `}` of `TIDE`, which today reads:

```python
# The Tide prompt (spec 5.2): fish universal variables. Colours are written without "#"; item lists are tuples
# (fish lists). Text on each segment reads at 4.5:1 on its background (spec 11.3).
TIDE: dict[str, str | tuple[str, ...]] = {
    "tide_left_prompt_items": ("moon", "pwd", "git", "newline", "character"),
    "tide_right_prompt_items": ("status", "cmd_duration", "time"),
    "tide_moon_bg_color": "1D1230",
    "tide_moon_color": "FFD477",
    "tide_pwd_bg_color": "B99AFF",
    "tide_pwd_color_anchors": "0D0916",
    "tide_pwd_color_dirs": "1D1230",
    "tide_pwd_color_truncated_dirs": "38234D",
    "tide_git_bg_color": "FFD477",
    "tide_git_bg_color_unstable": "FFB86B",
    "tide_git_bg_color_urgent": "FF6B9F",
    "tide_git_color_branch": "0D0916",
    "tide_git_color_conflicted": "0D0916",
    "tide_git_color_dirty": "0D0916",
    "tide_git_color_operation": "0D0916",
    "tide_git_color_staged": "0D0916",
    "tide_git_color_stash": "0D0916",
    "tide_git_color_untracked": "0D0916",
    "tide_git_color_upstream": "0D0916",
    "tide_character_color": "FF67B7",
    "tide_character_color_failure": "FF6B9F",
    "tide_prompt_color_frame_and_connection": "6E5A80",
    # Drawn between segments that share a background, so no single background exists to test it on: it is
    # in no contrast pair in validate.py, only format-checked.
    "tide_prompt_color_separator_same_color": "A99AB9",
    "tide_status_bg_color": "1D1230",
    "tide_status_color": "74E8B8",
    "tide_status_bg_color_failure": "1D1230",
    "tide_status_color_failure": "FF6B9F",
    "tide_cmd_duration_bg_color": "1D1230",
    "tide_cmd_duration_color": "A99AB9",
    "tide_cmd_duration_threshold": "3000",
    "tide_time_bg_color": "1D1230",
    "tide_time_color": "A99AB9",
}
```

with:

```python
# Every icon witchy draws, defined once (spec 7). The prompt takes its icons from here; build.py writes the
# table into the status line's and the greeting's GLYPHS blocks. Prompt icons are one emoji code point each,
# with no variation selector (spec D5), so the candle stays out of the prompt.
GLYPHS: dict[str, str] = {
    "candle": "\U0001F56F\uFE0F",  # status line model, greeting sabbat day; never in the prompt
    "scroll": "📜",  # status line repo
    "branch": "🌿",  # status line branch, Tide git icon
    "dirty": "✦",
    "separator": "⋆",
    "cwd": "🧹",
    "home": "🔮",
    "unwritable": "🪦",
    "ok": "🧪",
    "fail": "💀",
    "duration": "🔥",
    "jobs": "🐈",
    "time": "🦉",
    "caret": "❯",
}

# Items the prompt does not show (spec 6.4), with their icons. Turned on, they still look witchy: each wears the
# muted pair, A99AB9 on 1D1230.
UNUSED_ICONS: dict[str, str] = {
    "aws": "🏺", "crystal": "💠", "direnv": "🍃", "distrobox": "📦", "docker": "🐳", "elixir": "💧",
    "gcloud": "⛅", "go": "🐹", "java": "☕", "kubectl": "🎡", "nix_shell": "🧊", "node": "🍄", "os": "🐧",
    "php": "🐘", "private_mode": "🎭", "pulumi": "🧬", "python": "🐍", "ruby": "💎", "rustc": "🦀", "shlvl": "🌀",
    "terraform": "🧱", "toolbox": "🧰", "zig": "⚡",
}
VI_MODES = ("default", "insert", "replace", "visual")

# The Tide prompt (spec 5.2, 6): witchy's overrides of Tide 6.1.1's defaults; build.tide merges the two, and
# every other Tide variable keeps its default. fish universal variables: colours are written without "#", lists
# are tuples. Text on each segment reads at 4.5:1 on its background (spec 11.3).
TIDE: dict[str, str | tuple[str, ...]] = {
    # Shape (spec 6.2): two lines in a frame, Tide's Slanted caps and separators, a transient prompt.
    "tide_left_prompt_items": ("moon", "pwd", "git", "newline", "character"),
    "tide_right_prompt_items": ("status", "cmd_duration", "jobs", "time"),
    "tide_left_prompt_prefix": "\ue0ba",  # Slanted tail
    "tide_left_prompt_suffix": "\ue0bc",  # Slanted head
    "tide_right_prompt_prefix": "\ue0ba",  # Slanted head
    "tide_right_prompt_suffix": "\ue0bc",  # Slanted tail
    "tide_left_prompt_separator_diff_color": "\ue0bc",
    "tide_right_prompt_separator_diff_color": "\ue0ba",
    "tide_left_prompt_frame_enabled": "true",
    "tide_right_prompt_frame_enabled": "true",
    "tide_prompt_transient_enabled": "true",
    "tide_prompt_add_newline_before": "true",
    "tide_prompt_icon_connection": "·",
    "tide_prompt_color_frame_and_connection": "6E5A80",
    # Drawn between segments that share a background, so no single background exists to test it on: it is
    # in no contrast pair in validate.py, only format-checked.
    "tide_prompt_color_separator_same_color": "A99AB9",
    # The visible items (spec 6.3)
    "tide_moon_bg_color": "1D1230",
    "tide_moon_color": "FFD477",
    "tide_pwd_icon": GLYPHS["cwd"],
    "tide_pwd_icon_home": GLYPHS["home"],
    "tide_pwd_icon_unwritable": GLYPHS["unwritable"],
    "tide_pwd_bg_color": "B99AFF",
    "tide_pwd_color_anchors": "0D0916",
    "tide_pwd_color_dirs": "1D1230",
    "tide_pwd_color_truncated_dirs": "38234D",
    "tide_git_icon": GLYPHS["branch"],
    "tide_git_bg_color": "FFD477",
    "tide_git_bg_color_unstable": "FFB86B",
    "tide_git_bg_color_urgent": "FF6B9F",
    "tide_git_color_branch": "0D0916",
    "tide_git_color_conflicted": "0D0916",
    "tide_git_color_dirty": "0D0916",
    "tide_git_color_operation": "0D0916",
    "tide_git_color_staged": "0D0916",
    "tide_git_color_stash": "0D0916",
    "tide_git_color_untracked": "0D0916",
    "tide_git_color_upstream": "0D0916",
    "tide_character_icon": GLYPHS["caret"],
    "tide_character_vi_icon_default": "❮",
    "tide_character_vi_icon_replace": "▶",
    "tide_character_vi_icon_visual": "V",
    "tide_character_color": "FFD477",
    "tide_character_color_failure": "FF6B9F",
    "tide_status_icon": GLYPHS["ok"],
    "tide_status_icon_failure": GLYPHS["fail"],
    "tide_status_bg_color": "1D1230",
    "tide_status_color": "74E8B8",
    "tide_status_bg_color_failure": "1D1230",
    "tide_status_color_failure": "FF6B9F",
    "tide_cmd_duration_icon": GLYPHS["duration"],
    "tide_cmd_duration_bg_color": "1D1230",
    "tide_cmd_duration_color": "A99AB9",
    "tide_cmd_duration_threshold": "3000",
    "tide_jobs_icon": GLYPHS["jobs"],
    "tide_jobs_bg_color": "1D1230",
    "tide_jobs_color": "A99AB9",
    "tide_time_format": "%H:%M " + GLYPHS["time"],
    "tide_time_bg_color": "1D1230",
    "tide_time_color": "A99AB9",
    # The items witchy does not show (spec 6.4). context and vi_mode keep Tide's text; a denied direnv and a
    # root or ssh context are rose-red.
    **{f"tide_{item}_{key}": value for item, icon in UNUSED_ICONS.items()
       for key, value in (("icon", icon), ("bg_color", "1D1230"), ("color", "A99AB9"))},
    "tide_direnv_bg_color_denied": "1D1230",
    "tide_direnv_color_denied": "FF6B9F",
    "tide_context_bg_color": "1D1230",
    "tide_context_color_default": "A99AB9",
    "tide_context_color_root": "FF6B9F",
    "tide_context_color_ssh": "FF6B9F",
    **{f"tide_vi_mode_bg_color_{mode}": "1D1230" for mode in VI_MODES},
    **{f"tide_vi_mode_color_{mode}": "A99AB9" for mode in VI_MODES},
}

# fish's own universal variables that witchy sets and records like Tide's (spec 6.1): emoji are two cells wide,
# as Windows Terminal draws them.
FISH: dict[str, str] = {"fish_emoji_width": "2"}
```

followed by one blank line, so `# Variables of witchy's own prompt items` (Task 2) follows `FISH`. `EZA` below keeps reading `TIDE["tide_git_bg_color"]` and the two other git backgrounds, which did not change.

In `witchy/validate.py`, after the closing `)` of `TIDE_TEXT_PAIRS`, add:

```python
# The items witchy does not show (spec 6.4) and jobs: each one's text on its own background.
TIDE_ITEMS = ("aws", "crystal", "direnv", "distrobox", "docker", "elixir", "gcloud", "go", "java", "jobs",
              "kubectl", "nix_shell", "node", "os", "php", "private_mode", "pulumi", "python", "ruby", "rustc",
              "shlvl", "terraform", "toolbox", "zig")
VI_MODES = ("default", "insert", "replace", "visual")
TIDE_ITEM_PAIRS: tuple[tuple[str, str | None], ...] = (
    *((f"tide_{item}_color", f"tide_{item}_bg_color") for item in TIDE_ITEMS),
    ("tide_direnv_color_denied", "tide_direnv_bg_color_denied"),
    *((f"tide_context_color_{kind}", "tide_context_bg_color") for kind in ("default", "root", "ssh")),
    *((f"tide_vi_mode_color_{mode}", f"tide_vi_mode_bg_color_{mode}") for mode in VI_MODES),
)
```

Replace:

```python
def is_tide_colour(key: str) -> bool:
    """Tide names a colour variable with the word ``color``: ``tide_pwd_bg_color``, ``tide_git_color_branch``."""
    return "color" in key.split("_")
```

with:

```python
# Tide names these with the word "color", but they hold the glyph drawn between two segments (spec 6.2).
TIDE_SEPARATOR_GLYPHS = frozenset({"tide_left_prompt_separator_diff_color", "tide_left_prompt_separator_same_color",
                                   "tide_right_prompt_separator_diff_color", "tide_right_prompt_separator_same_color"})


def is_tide_colour(key: str) -> bool:
    """Tide names a colour variable with the word ``color``: ``tide_pwd_bg_color``, ``tide_git_color_branch``."""
    return "color" in key.split("_") and key not in TIDE_SEPARATOR_GLYPHS
```

In `validate_tide`, replace:

```python
    for pairs, rule, minimum in ((TIDE_TEXT_PAIRS, "text-contrast", TEXT_MIN),
```

with:

```python
    for pairs, rule, minimum in ((TIDE_TEXT_PAIRS + TIDE_ITEM_PAIRS, "text-contrast", TEXT_MIN),
```

- [ ] **Step 4: Correct the spec**

In `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md`:

Section 6.2, replace:

```
| `tide_prompt_color_frame_and_connection` | `38234D` (deep violet) |
```

with:

```
| `tide_prompt_color_frame_and_connection` | `6E5A80` (unchanged: the deep violet `38234D` is 1.42:1 on `#0D0916`, below the 3:1 rule for the frame in ritual 11.3) |
```

Section 6.3, replace:

```
Caret colours: `tide_character_color` `FFD477`, `tide_character_color_failure` `FF6B9F`. The other visible colours stay as in ritual 5.2.
```

with:

```
Caret colours: `tide_character_color` `FFD477`, `tide_character_color_failure` `FF6B9F`. `jobs` wears the muted pair of section 6.4 (`A99AB9` on `1D1230`). The other visible colours stay as in ritual 5.2.
```

Section 6.4, replace the icon table:

```
| aws | 🏺 | gcloud | ⛅ | private_mode | 🎭 |
| bun | 🥟 | go | 🐹 | pulumi | 🧬 |
| crystal | 💠 | java | ☕ | python | 🐍 |
| direnv | 🍃 | kubectl | 🎡 | ruby | 💎 |
| distrobox | 📦 | nix_shell | 🧊 | rustc | 🦀 |
| docker | 🐳 | node | 🍄 | shlvl | 🌀 |
| elixir | 💧 | os | 🐧 | terraform | 🧱 |
| php | 🐘 | toolbox | 🧰 | zig | ⚡ |
```

with:

```
| aws | 🏺 | gcloud | ⛅ | private_mode | 🎭 |
| crystal | 💠 | go | 🐹 | pulumi | 🧬 |
| direnv | 🍃 | java | ☕ | python | 🐍 |
| distrobox | 📦 | kubectl | 🎡 | ruby | 💎 |
| docker | 🐳 | nix_shell | 🧊 | rustc | 🦀 |
| elixir | 💧 | node | 🍄 | shlvl | 🌀 |
| php | 🐘 | os | 🐧 | terraform | 🧱 |
| | | toolbox | 🧰 | zig | ⚡ |

The Tide 6.1.1 release has no `bun` item (only Tide's development branch does), so witchy sets no `tide_bun_*` variable.
```

Section 11, replace item 4:

```
4. **Contrast:** each new visible pair (caret on the terminal background, muted on `1D1230` for unused items, frame `38234D` against `0D0916` as non-text ≥ 1.5:1) joins the existing pairs.
```

with:

```
4. **Contrast:** each new visible pair (caret on the terminal background, muted on `1D1230` for `jobs` and the unused items, rose-red on `1D1230` for the denied direnv and the root and ssh context) joins the existing pairs. The frame keeps its 3:1 rule on `0D0916` (ritual 11.3).
```

- [ ] **Step 5: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 585 tests … OK` on both, and `Moonlit Candle: all checks passed`. The fish component tests still pass: they read `palette.TIDE` (now 141 names) through the variant, which Task 7 replaces with `build.tide`.

- [ ] **Step 6: Commit**

```bash
git add witchy/palette.py witchy/validate.py tests/test_prompt_palette.py docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: the witchy prompt: glyph table, Slanted shape, icons and colours for every Tide item" -m "palette.TIDE now holds every override of spec 6.2-6.4 and takes its icons from palette.GLYPHS; palette.FISH sets fish_emoji_width. The frame keeps 6E5A80: the spec's 38234D fails the 3:1 frame rule, so spec 6.2 and 11.4 say so." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The status line and the greeting take their glyphs from the shared table

**Items:** spec 7: `statusline.py` gets a `# BEGIN GLYPHS` / `# END GLYPHS` block rewritten by `build.py`; the branch glyph `⎇` becomes 🌿; the greeting takes `candle`, `dirty` and `separator` from the table; `ritual/layout.WIDE` covers every table emoji. Deviation: the greeting reads the table from a GLYPHS block, not from `data.json` (plan Decision 5).

**Files:**
- Modify: `witchy/build.py` (`dict_block`, `with_blocks`, `statusline_source`, `ritual_package`; `PALETTE_BLOCK` and `with_palette` go)
- Modify: `witchy/statusline.py` (GLYPHS block replaces the five glyph constants)
- Modify: `witchy/ritual/palette.py` (GLYPHS block), `witchy/ritual/cli.py`, `witchy/ritual/layout.py` (`WIDE`)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (section 7)
- Test: `tests/test_build.py`, `tests/test_statusline.py`, `tests/test_ritual_cli.py`, `tests/test_ritual_content.py`, `tests/test_ritual_package.py`, `tests/test_layout.py`

**Interfaces:**
- Consumes: `palette.GLYPHS` (Task 3).
- Produces:
  - `build.dict_block(name: str, values: dict[str, str]) -> str`: `NAME = {` + one `    "key": "value",` line per entry (`json.dumps`, `ensure_ascii=False`) + `}` + newline. `build.palette_block(colours)` stays and equals `dict_block("PALETTE", colours)`.
  - `build.with_blocks(source: Path, blocks: dict[str, dict[str, str]]) -> str`: rewrites each `# BEGIN NAME` … `# END NAME` block; `ValueError("<source> must contain exactly one NAME block, found N")` otherwise.
  - `build.statusline_source(colours=palette.STATUSLINE, source=STATUSLINE_SOURCE, glyphs=palette.GLYPHS) -> str`.
  - `statusline.GLYPHS` and `witchy.ritual.palette.GLYPHS`: copies of `palette.GLYPHS` (a test pins each).
  - `layout.WIDE = frozenset("🌑🌒🌓🌔🌕🌖🌗🌘🕯📜🌿🧹🔮🪦🧪💀🔥🐈🦉")`.

**Decisions:**
1. **One generic block writer.** `with_palette` and `PALETTE_BLOCK` had a single caller each (`statusline_source`, `ritual_package`); both now call `with_blocks` with two blocks. `palette_block` stays because `tests/test_ritual_content.py` uses it.
2. **The art's star glyphs (`art.STAR_GLYPHS`) stay as they are:** they are moon-art decoration, not the icons spec 7 names.
3. **`layout.WIDE` lists the emoji in a string** rather than deriving them from `GLYPHS`: the greeting must not need to know which table entries are emoji, and Task 5's rule 11.5 fails validation when the two drift apart.

- [ ] **Step 1: Write the failing tests**

In `tests/test_statusline.py`, replace every `⎇` with `🌿` (six places in `GitSegmentTest`: `test_clean_repo`, `test_dirty_repo_counts_changes`, `test_long_branch_is_cut_to_28`, `test_detached_head_shows_the_short_hash`, `test_git_segment_colours` and `assert_git_segment_hidden`):

```bash
sed -i 's/⎇/🌿/g' tests/test_statusline.py
```

Then, in `GitSegmentTest`, before `test_git_segment_colours`, add:

```python
    def test_the_branch_glyph_is_the_herb(self):
        self.assertIn("📜 spellbook 🌿 main", self.line())

```

In `tests/test_build.py`, in `BuildTest`, before `test_missing_palette_block_raises`, add:

```python
    def test_source_glyph_block_matches_the_table(self):
        source = build.STATUSLINE_SOURCE.read_text(encoding="utf-8")
        self.assertIn(build.dict_block("GLYPHS", palette.GLYPHS), source)

    def test_glyph_block_is_rewritten(self):
        source = build.statusline_source(glyphs=dict(palette.GLYPHS, branch="Y"))
        self.assertIn('    "branch": "Y",\n', source)
        self.assertIn('    "model": "#FFD477",\n', source)

    def test_generated_statusline_draws_the_table_glyphs(self):
        namespace = {}
        exec(compile(build.statusline_source(glyphs=dict(palette.GLYPHS, candle="C")), "statusline.py", "exec"),
             namespace)
        self.assertTrue(namespace["render"]({}).startswith(" \x1b[1m\x1b[38;2;255;212;119mC --"))

    def test_missing_glyph_block_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "statusline.py"
            source.write_text("# BEGIN PALETTE\nPALETTE = {}\n# END PALETTE\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly one GLYPHS block, found 0"):
                build.statusline_source(source=source)

```

In `tests/test_ritual_content.py`, in `RitualPaletteTest`, before `test_real_palette_passes`, add:

```python
    def test_the_package_glyph_block_matches_the_table(self):
        self.assertIn(build.dict_block("GLYPHS", palette.GLYPHS), RITUAL_PALETTE_SOURCE.read_text(encoding="utf-8"))

```

In `tests/test_ritual_package.py`, in `PackageTest`, before `test_imports_nothing_from_witchy`, add:

```python
    def test_glyphs_come_from_the_table(self):
        with mock.patch.dict(palette.GLYPHS, {"candle": "C"}):
            text = build.ritual_package()["palette.py"].decode("utf-8")
        self.assertIn('    "candle": "C",\n', text)

```

In `tests/test_ritual_cli.py`, replace:

```python
from witchy.ritual import cli, layout, sky, wheel
```

with:

```python
from witchy.ritual import cli, layout, palette, sky, wheel
```

and at the top of `class OmenTest(CliTestCase):`, before `test_one_line`, add:

```python
    def test_candle_dirty_and_separator_come_from_the_glyph_table(self):
        with mock.patch.dict(palette.GLYPHS, {"candle": "C", "dirty": "D", "separator": "S"}):
            self.assertEqual(self.run_cli(["--omen"]), "🌗 Last Quarter 67% · D The Star · C Samhain\n\n")
            text = self.run_cli(["--full"], now=datetime(2026, 10, 26, 8, 0, tzinfo=CET))
        self.assertIn("S Samhain in 5 days", text)
        self.assertIn("S Full  100%", text)
        self.assertIn("D XV · The Devil", text)

```

In `tests/test_layout.py`, in `WidthTest`, before `test_fit_cuts_with_an_ellipsis`, add:

```python
    def test_every_emoji_of_the_glyph_table_is_two_cells(self):
        self.assertLessEqual(set("🕯📜🌿🧹🔮🪦🧪💀🔥🐈🦉"), layout.WIDE)
        self.assertEqual(layout.cell_width("🪦 🦉"), 5)

```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_build tests.test_layout tests.test_ritual_cli tests.test_ritual_content tests.test_ritual_package tests.test_statusline`
Expected (real output from the prototype, abridged):
```
ERROR: test_generated_statusline_draws_the_table_glyphs / test_glyph_block_is_rewritten
  TypeError: statusline_source() got an unexpected keyword argument 'glyphs'
ERROR: test_source_glyph_block_matches_the_table / test_the_package_glyph_block_matches_the_table
  AttributeError: module 'witchy.build' has no attribute 'dict_block'
ERROR: test_candle_dirty_and_separator_come_from_the_glyph_table
  AttributeError: module 'witchy.ritual.palette' has no attribute 'GLYPHS'
FAIL: test_clean_repo  … ⋆ 📜 spellbook ⎇ main
FAIL: test_the_branch_glyph_is_the_herb, test_dirty_repo_counts_changes, test_long_branch_is_cut_to_28,
      test_detached_head_shows_the_short_hash, test_git_segment_colours
FAIL: test_missing_glyph_block_raises  ValueError not raised
FAIL: test_glyphs_come_from_the_table
FAIL: test_every_emoji_of_the_glyph_table_is_two_cells
FAILED (failures=9, errors=5)
```

- [ ] **Step 3: Generic blocks in build.py**

In `witchy/build.py`, delete the line:

```python
PALETTE_BLOCK = re.compile(r"(# BEGIN PALETTE\n)(.*?)(# END PALETTE\n)", re.DOTALL)
```

Replace:

```python
def palette_block(colours: dict[str, str]) -> str:
    lines = ["PALETTE = {", *(f'    "{key}": "{value}",' for key, value in colours.items()), "}"]
    return "\n".join(lines) + "\n"


def statusline_source(colours: dict[str, str] = palette.STATUSLINE, source: Path = STATUSLINE_SOURCE) -> str:
    """The status line script with its PALETTE block rewritten from ``colours``."""
    return with_palette(source, colours)


def with_palette(source: Path, colours: dict[str, str]) -> str:
    """``source`` with its one ``# BEGIN PALETTE`` block rewritten from ``colours``."""
    text = source.read_text(encoding="utf-8")
    rewritten, count = PALETTE_BLOCK.subn(lambda m: m.group(1) + palette_block(colours) + m.group(3), text)
    if count != 1:
        raise ValueError(f"{source} must contain exactly one PALETTE block, found {count}")
    return rewritten
```

with:

```python
def dict_block(name: str, values: dict[str, str]) -> str:
    """``NAME = {...}``, one ``"key": "value",`` line per entry, as the generated blocks hold it."""
    lines = [f"{name} = {{", *(f"    {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)},"
                               for key, value in values.items()), "}"]
    return "\n".join(lines) + "\n"


def palette_block(colours: dict[str, str]) -> str:
    return dict_block("PALETTE", colours)


def with_blocks(source: Path, blocks: dict[str, dict[str, str]]) -> str:
    """``source`` with each ``# BEGIN NAME`` / ``# END NAME`` block rewritten; each must appear exactly once."""
    text = source.read_text(encoding="utf-8")
    for name, values in blocks.items():
        pattern = re.compile(rf"(# BEGIN {name}\n)(.*?)(# END {name}\n)", re.DOTALL)
        text, count = pattern.subn(lambda m: m.group(1) + dict_block(name, values) + m.group(3), text)
        if count != 1:
            raise ValueError(f"{source} must contain exactly one {name} block, found {count}")
    return text


def statusline_source(colours: dict[str, str] = palette.STATUSLINE, source: Path = STATUSLINE_SOURCE,
                      glyphs: dict[str, str] = palette.GLYPHS) -> str:
    """The status line script with its PALETTE and GLYPHS blocks rewritten."""
    return with_blocks(source, {"PALETTE": colours, "GLYPHS": glyphs})
```

In `ritual_package`, replace:

```python
    """The greeting package as installed: its modules, palette.py from ``variant``, and data.json from content/."""
    files = {}
    for module in sorted(source.glob("*.py")):
        text = (with_palette(module, palette.VARIANTS[variant].ritual) if module.name == "palette.py"
                else module.read_text(encoding="utf-8"))
```

with:

```python
    """The greeting package as installed: its modules, palette.py from ``variant`` and the glyph table, and
    data.json from content/."""
    files = {}
    for module in sorted(source.glob("*.py")):
        text = (with_blocks(module, {"PALETTE": palette.VARIANTS[variant].ritual, "GLYPHS": palette.GLYPHS})
                if module.name == "palette.py" else module.read_text(encoding="utf-8"))
```

- [ ] **Step 4: The status line**

In `witchy/statusline.py`, replace:

```python
the witchy package; build.py rewrites the PALETTE block from palette.py. Like
```

with:

```python
the witchy package; build.py rewrites the PALETTE and GLYPHS blocks from palette.py. Like
```

Delete:

```python
CANDLE = "🕯️"
SCROLL = "📜"
BRANCH = "⎇"
DIRTY = "✦"
SEPARATOR = "⋆"
```

After the line `# END PALETTE` add (one blank line before, one after; the candle is U+1F56F U+FE0F):

```python

# BEGIN GLYPHS
GLYPHS = {
    "candle": "🕯️",
    "scroll": "📜",
    "branch": "🌿",
    "dirty": "✦",
    "separator": "⋆",
    "cwd": "🧹",
    "home": "🔮",
    "unwritable": "🪦",
    "ok": "🧪",
    "fail": "💀",
    "duration": "🔥",
    "jobs": "🐈",
    "time": "🦉",
    "caret": "❯",
}
# END GLYPHS
```

In `_model`, replace:

```python
    return _paint(f"{CANDLE} {name or DASH}", "model", bold=True) + effort
```

with:

```python
    return _paint(f"{GLYPHS['candle']} {name or DASH}", "model", bold=True) + effort
```

In `_repo`, replace:

```python
    segment = _paint(f"{SCROLL} {os.path.basename(top)}", "repo") + " " + _paint(f"{BRANCH} {branch}", "branch")
    return segment + (_paint(f"{DIRTY}{dirty}", "dirty") if dirty else "")
```

with:

```python
    segment = (_paint(f"{GLYPHS['scroll']} {os.path.basename(top)}", "repo") + " "
               + _paint(f"{GLYPHS['branch']} {branch}", "branch"))
    return segment + (_paint(f"{GLYPHS['dirty']}{dirty}", "dirty") if dirty else "")
```

In `render`, replace:

```python
    return " " + _paint(f" {SEPARATOR} ", "divider").join(parts) + " "
```

with:

```python
    return " " + _paint(f" {GLYPHS['separator']} ", "divider").join(parts) + " "
```

To be sure the block is byte-exact (the candle's U+FE0F is invisible), regenerate the file from the table once and check nothing else moved:

```bash
python3 -c "from witchy import build; build.STATUSLINE_SOURCE.write_text(build.statusline_source(), encoding='utf-8')"
git diff --stat witchy/statusline.py
```

- [ ] **Step 5: The greeting**

In `witchy/ritual/palette.py`, replace the docstring:

```python
"""The greeting's colours. build.py rewrites the PALETTE block from the active variant."""
```

with:

```python
"""The greeting's colours and glyphs. build.py rewrites the PALETTE block from the active variant and the GLYPHS
block from the shared glyph table (spec 7)."""
```

and after `# END PALETTE` (the last line) append one blank line and the same GLYPHS block as in Step 4 (from `# BEGIN GLYPHS` to `# END GLYPHS`). Then make it byte-exact:

```bash
python3 -c "
from witchy import build, palette
path = build.RITUAL_SOURCE / 'palette.py'
path.write_text(build.with_blocks(path, {'PALETTE': palette.RITUAL, 'GLYPHS': palette.GLYPHS}), encoding='utf-8')"
```

In `witchy/ritual/cli.py`, replace:

```python
def _countdown(name: str, days: int) -> str:
    return f"⋆ {name} tomorrow" if days == 1 else f"⋆ {name} in {days} days"
```

with:

```python
def _countdown(name: str, days: int) -> str:
    star = palette.GLYPHS["separator"]
    return f"{star} {name} tomorrow" if days == 1 else f"{star} {name} in {days} days"
```

In `info_lines`, replace:

```python
        text = f"🕯️ {name} — {data['sabbats'][name]}" if days == 0 else _countdown(name, days)
```

with:

```python
        text = f"{palette.GLYPHS['candle']} {name} — {data['sabbats'][name]}" if days == 0 else _countdown(name, days)
```

replace:

```python
    lines.append([(f"⋆ {moon.NAMES[phase]}  {moon.illumination(now)}%", "moon", False)])
```

with:

```python
    lines.append([(f"{palette.GLYPHS['separator']} {moon.NAMES[phase]}  {moon.illumination(now)}%", "moon", False)])
```

and replace:

```python
    title = [(f"✦ {tarot.NUMERALS[card['number']]} · {card['name']}", "tarot", False)]
```

with:

```python
    title = [(f"{palette.GLYPHS['dirty']} {tarot.NUMERALS[card['number']]} · {card['name']}", "tarot", False)]
```

In `omen_line`, replace:

```python
            (f"✦ {card['name']}", "tarot", False)]
```

with:

```python
            (f"{palette.GLYPHS['dirty']} {card['name']}", "tarot", False)]
```

and replace:

```python
        line += [SEPARATOR, (f"🕯️ {name}" if days == 0 else _countdown(name, days), name.lower(), False)]
```

with:

```python
        candle = f"{palette.GLYPHS['candle']} {name}"
        line += [SEPARATOR, (candle if days == 0 else _countdown(name, days), name.lower(), False)]
```

In `witchy/ritual/layout.py`, replace:

```python
# Emoji we print, drawn two cells wide. 🕯 is narrow in Unicode but terminals draw it wide with its VS16.
WIDE = frozenset("🌑🌒🌓🌔🌕🌖🌗🌘🕯")
```

with:

```python
# Emoji we print, drawn two cells wide: the moon phases and every emoji of the glyph table (validate.py checks
# the table). 🕯 is narrow in Unicode but terminals draw it wide with its VS16.
WIDE = frozenset("🌑🌒🌓🌔🌕🌖🌗🌘🕯📜🌿🧹🔮🪦🧪💀🔥🐈🦉")
```

In `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md`, section 7, replace:

```
- The ritual takes `candle`, `dirty` and `separator` from the table through `ritual/data.json`. `ritual/layout.WIDE` becomes the moon phases plus every table emoji, so width stays right.
```

with:

```
- The ritual takes `candle`, `dirty` and `separator` from the table through a `# BEGIN GLYPHS` block in `witchy/ritual/palette.py`, which `build.py` rewrites like its PALETTE block. (`ritual/data.json` would not do: the repository copy reads `content/ritual.json`, which no build step touches.) `ritual/layout.WIDE` becomes the moon phases plus every table emoji, so width stays right.
```

- [ ] **Step 6: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 594 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 7: Commit**

```bash
git add witchy/build.py witchy/statusline.py witchy/ritual/palette.py witchy/ritual/cli.py witchy/ritual/layout.py tests/test_build.py tests/test_statusline.py tests/test_ritual_cli.py tests/test_ritual_content.py tests/test_ritual_package.py tests/test_layout.py docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: the status line and the greeting take their glyphs from the shared table" -m "build.py rewrites a GLYPHS block in statusline.py and in the greeting's palette.py from palette.GLYPHS; the status line's branch glyph is now the herb. layout.WIDE covers every emoji of the table." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Validate the whole prompt (rules 11.1–11.5)

**Items:** spec 11: (1) every `*_icon` value and `tide_time_format` holds at most one emoji and no U+FE0F, U+200D or skin tone; (2) every key of `palette.TIDE` is a Tide 6.1.1 name (or one of witchy's own); (3) no prompt or terminal value comes from the pastel theme, listed in `validate.PASTEL`; (4) the contrast rules run on the merged prompt; (5) every emoji of `GLYPHS` is in `ritual/layout.WIDE` or East Asian Wide.

**Files:**
- Modify: `witchy/validate.py` (`PASTEL`, `PROMPT_GLYPH_MARKS`, `is_emoji`, `is_pastel`, `_prompt_glyph`, `validate_glyphs`, `validate_tide`, `validate_palette`, `validate_all`)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (section 11, items 1 and 3)
- Test: `tests/test_prompt_palette.py`

**Interfaces:**
- Consumes: `content.load_tide_defaults`, `content.TIDE_DEFAULTS` (Task 2); `palette.GLYPHS`, `palette.UNUSED_ICONS`, `palette.TIDE_OWN` (Tasks 2–3); `layout.WIDE` (Task 4).
- Produces:
  - `validate.PASTEL: frozenset[str]` (49 hex colours, upper case without `#`, and 24 single-code-point icons).
  - `validate.is_emoji(char) -> bool`, `validate.is_pastel(value) -> bool`.
  - `validate.validate_tide(overrides, background=palette.BACKGROUND, defaults=None) -> list[Failure]`; `defaults=None` loads the checked-in file. New rules: `unknown-variable`, `prompt-glyph`, `pastel`.
  - `validate.validate_glyphs(glyphs) -> list[Failure]` (rule `width`).
  - `validate_palette` adds rule `pastel` for `wt.*` values. `validate_all` reports an unreadable defaults file as one `content` failure (item = the file's path) and checks the merged prompt and the glyph table.

**Decisions:**
1. **Emoji** = category `So` and (East Asian Wide/Fullwidth or past U+1F000) (plan Decision 8). Rule 1 counts emoji in the joined values; rule 5 needs the "past U+1F000" half for 🕯, which Unicode calls narrow.
2. **The rules run on `{**defaults, **overrides}`,** so a Tide default that slipped through (say a two-emoji icon in a future Tide) fails as well (`test_tides_own_icons_are_checked_too`).
3. **`PASTEL` is the whole old theme** (plan Decision 9). `test_no_witchy_glyph_is_on_the_list` keeps the overlap empty.
4. **`validate_tide(..., defaults=None)` loads the file itself,** so the existing one-argument calls in the tests keep working; `validate_all` passes the defaults it already read from `content_dir`.
5. **An unreadable defaults file is a `content` failure and skips only the Tide rules**, like the existing handling of `spinner.json` (the other variant rules still run).

- [ ] **Step 1: Write the failing tests**

In `tests/test_prompt_palette.py`, replace:

```python
import unittest
from unittest import mock

from witchy import build, content, palette, validate
```

with:

```python
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import build, content, palette, validate
from witchy.ritual import layout
```

In `TideNamesTest.test_every_tide_colour_is_validated_for_contrast_or_exempt`, replace:

```python
        colours = {key for key in palette.TIDE if validate.is_tide_colour(key)}
```

with:

```python
        colours = {key for key in build.tide() if validate.is_tide_colour(key)}
```

In `TideValidateTest.test_a_name_that_only_contains_color_is_not_a_colour`, replace:

```python
        self.assertEqual(found, set())
```

with:

```python
        self.assertEqual(found, {("unknown-variable", "tide.tide_colorful_icon")})
```

Before `class VariantPromptTest(unittest.TestCase):`, add:

```python
class PromptGlyphRuleTest(unittest.TestCase):
    """Spec 11.1: a prompt icon is at most one emoji, one code point, no selector, joiner or skin tone."""

    def test_a_variation_selector_a_joiner_or_a_skin_tone_fails(self):
        for bad in ("\U0001F56F\uFE0F", "\U0001F9D9\u200D\u2640", "\U0001F44D\U0001F3FD"):
            with self.subTest(bad=bad):
                found = pairs(validate.validate_tide(dict(palette.TIDE, tide_pwd_icon=bad)))
                self.assertIn(("prompt-glyph", "tide.tide_pwd_icon"), found)

    def test_two_emoji_fail_and_text_glyphs_pass(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_time_format="%H:%M 🦉🦉")))
        self.assertIn(("prompt-glyph", "tide.tide_time_format"), found)
        fine = dict(palette.TIDE, tide_character_icon="❯", tide_prompt_icon_connection="·", tide_pwd_icon="\uf07c")
        self.assertEqual(validate.validate_tide(fine), [])

    def test_tides_own_icons_are_checked_too(self):
        defaults = dict(content.load_tide_defaults(), tide_vi_mode_icon_insert="🐍🐍")
        found = pairs(validate.validate_tide(palette.TIDE, defaults=defaults))
        self.assertIn(("prompt-glyph", "tide.tide_vi_mode_icon_insert"), found)


class CompletenessRuleTest(unittest.TestCase):
    """Spec 11.2: every override names a Tide 6.1.1 variable or one of witchy's own."""

    def test_a_typo_is_an_unknown_variable(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_pwd_bg_colour="B99AFF")))
        self.assertIn(("unknown-variable", "tide.tide_pwd_bg_colour"), found)

    def test_the_moon_items_variables_are_witchys_own(self):
        self.assertEqual(validate.validate_tide({**palette.TIDE, "tide_moon_color": "FFD477"}), [])


class PastelRuleTest(unittest.TestCase):
    """Spec 11.3: no value of the old pastel prompt comes back."""

    def test_the_list_holds_the_recorded_values(self):
        self.assertLessEqual({"FFB7C5", "F8A4C9", "FF6EC7", "FBAED2", "F5C6E0", "FFC8DD",
                              "🎀", "🏰", "🌷", "💖", "💔", "✨", "🍰", "🌸"}, validate.PASTEL)

    def test_no_witchy_glyph_is_on_the_list(self):
        used = set("".join(palette.GLYPHS.values())) | set("".join(palette.UNUSED_ICONS.values()))
        self.assertEqual(used & validate.PASTEL, set())

    def test_a_pastel_colour_or_icon_in_the_prompt_fails(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_pwd_bg_color="FFB7C5", tide_git_icon="🌷",
                                                  tide_time_format="%H:%M 🍰")))
        self.assertLessEqual({("pastel", "tide.tide_pwd_bg_color"), ("pastel", "tide.tide_git_icon"),
                              ("pastel", "tide.tide_time_format")}, found)

    def test_a_pastel_tide_default_fails(self):
        defaults = dict(content.load_tide_defaults(), tide_vi_mode_icon_insert="🎀")
        found = pairs(validate.validate_tide(palette.TIDE, defaults=defaults))
        self.assertIn(("pastel", "tide.tide_vi_mode_icon_insert"), found)

    def test_a_pastel_terminal_colour_fails(self):
        found = pairs(validate.validate_palette(scheme=dict(palette.WT_SCHEME, brightPurple="#FBAED2")))
        self.assertIn(("pastel", "wt.brightPurple"), found)


class WidthRuleTest(unittest.TestCase):
    """Spec 11.5: the greeting measures every emoji of the glyph table two cells wide."""

    def test_the_real_table_passes(self):
        self.assertEqual(validate.validate_glyphs(palette.GLYPHS), [])

    def test_an_emoji_unicode_calls_narrow_must_be_in_wide(self):
        with mock.patch.object(layout, "WIDE", frozenset()):
            found = pairs(validate.validate_glyphs(palette.GLYPHS))
        # 🕯 is narrow in Unicode; every other emoji of the table is East Asian Wide.
        self.assertEqual(found, {("width", "glyphs.candle")})

    def test_text_glyphs_are_not_emoji(self):
        self.assertEqual(validate.validate_glyphs({"dirty": "✦", "caret": "❯", "separator": "⋆"}), [])


```

At the end of `VariantPromptTest` (after `test_validate_all_checks_every_variant_prompt_and_eza`), add:

```python

    def test_validate_all_checks_the_merged_prompt_and_the_glyph_table(self):
        midnight = palette.VARIANTS["midnight"]
        broken = palette.Variant(**{**midnight.__dict__, "name": "broken",
                                    "tide": dict(midnight.tide, tide_pwd_bg_colour="B99AFF")})
        with mock.patch.dict(palette.VARIANTS, {"broken": broken}), mock.patch.object(layout, "WIDE", frozenset()):
            found = pairs(validate.validate_all())
        self.assertIn(("unknown-variable", "tide.tide_pwd_bg_colour"), found)
        self.assertIn(("width", "glyphs.candle"), found)

    def test_validate_all_reports_defaults_it_cannot_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in (content.SPINNER, content.OUTPUT_STYLE, content.RITUAL):
                (Path(tmp) / name).write_bytes((content.CONTENT_DIR / name).read_bytes())
            failures = validate.validate_all(Path(tmp))
        self.assertEqual([(f.rule, f.item) for f in failures],
                         [("content", str(Path(tmp) / content.TIDE_DEFAULTS))])
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_prompt_palette`
Expected (real output from the prototype, abridged):
```
ERROR: test_a_pastel_tide_default_fails / test_tides_own_icons_are_checked_too
  TypeError: validate_tide() got an unexpected keyword argument 'defaults'
ERROR: test_no_witchy_glyph_is_on_the_list / test_the_list_holds_the_recorded_values
  AttributeError: module 'witchy.validate' has no attribute 'PASTEL'
ERROR: test_the_real_table_passes / test_an_emoji_unicode_calls_narrow_must_be_in_wide / test_text_glyphs_are_not_emoji
  AttributeError: module 'witchy.validate' has no attribute 'validate_glyphs'
FAIL: test_a_typo_is_an_unknown_variable, test_a_pastel_colour_or_icon_in_the_prompt_fails,
      test_a_pastel_terminal_colour_fails, test_a_variation_selector_a_joiner_or_a_skin_tone_fails (3 subtests),
      test_two_emoji_fail_and_text_glyphs_pass, test_a_name_that_only_contains_color_is_not_a_colour,
      test_validate_all_checks_the_merged_prompt_and_the_glyph_table,
      test_validate_all_reports_defaults_it_cannot_read
FAILED (failures=10, errors=7)
```

- [ ] **Step 3: Implement the rules**

In `witchy/validate.py`, replace:

```python
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import content, palette, sky_render, tokens
from .contrast import contrast_ratio
```

with:

```python
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import content, palette, sky_render, tokens
from .contrast import contrast_ratio
from .ritual import layout
```

Before `@dataclass(frozen=True)` / `class Failure:`, add:

```python
# Every colour and icon of the old "pastel princess" prompt (~/change_this_bitch.sh), so none comes back
# (spec 11.3). Icons witchy uses on purpose (🔮 🐍 💎 🦀 ☕ 🐳) are left off; icons are stored without U+FE0F.
PASTEL = frozenset({
    "012A4A", "034078", "05386B", "1C0035", "1F0322", "280659", "2B061E", "2D132C", "371B58", "3A0F29", "3E005D",
    "490B3D", "4B1139", "52052E", "541C1D", "5A4500", "5C3A21", "5D1E41", "780116", "A2D2FF", "BDE0FE", "BEE3DB",
    "CBC3E3", "D4E6FB", "D8B4FE", "E0AAFF", "E2CFEA", "E7C6FF", "E8CFF8", "F4978E", "F4ACB7", "F5C6E0", "F8A4C9",
    "FBAED2", "FCD5CE", "FDE68A", "FF3E96", "FF6B6B", "FF6EC7", "FFAAA5", "FFAFCC", "FFB7C5", "FFC8DD", "FFD1DC",
    "FFD6E0", "FFDAC1", "FFDFD3", "FFE5B4", "FFF5C2",
    "🎀", "🏰", "🌷", "💖", "💔", "✨", "🍰", "🌸", "🔒", "⏳", "🪡", "🍬", "🐬", "🦄", "☸", "☁", "🍯", "🌼",
    "🕶", "🧁", "🖋", "🎨", "🩹", "👑",
})
# Spec 11.1 (D5): a prompt icon is one code point. These would join or restyle the emoji before them.
PROMPT_GLYPH_MARKS = frozenset({"\uFE0F", "\u200D", *map(chr, range(0x1F3FB, 0x1F400))})


```

In `validate_palette`, replace:

```python
    for key in WT_TEXT:
        if usable("wt", scheme, key):
            _contrast(failures, "text-contrast", f"wt.{key}", scheme[key], background, TEXT_MIN, scheme[key])
```

with:

```python
    for key, value in scheme.items():
        if key != "name" and isinstance(value, str) and is_pastel(value):
            failures.append(Failure("pastel", f"wt.{key}", value, "is a colour of the old pastel theme"))
    for key in WT_TEXT:
        if usable("wt", scheme, key):
            _contrast(failures, "text-contrast", f"wt.{key}", scheme[key], background, TEXT_MIN, scheme[key])
```

Before `def validate_sky(`, add:

```python
def is_emoji(char: str) -> bool:
    """A pictograph a terminal draws as an emoji: a symbol that is East Asian Wide, or one past U+1F000 (🕯 is
    narrow in Unicode). Text symbols such as ❯, ✦ or Nerd Font glyphs are not emoji."""
    return unicodedata.category(char) == "So" and (unicodedata.east_asian_width(char) in ("W", "F")
                                                    or ord(char) >= 0x1F000)


def is_pastel(value: str) -> bool:
    """``value`` is a colour of the old pastel theme (with or without "#"), or holds one of its icons."""
    return value.lstrip("#").upper() in PASTEL or any(char in PASTEL for char in value)


def _prompt_glyph(failures: list[Failure], key: str, text: str) -> None:
    if any(char in PROMPT_GLYPH_MARKS for char in text):
        failures.append(Failure("prompt-glyph", f"tide.{key}", text,
                                "holds a variation selector, a joiner or a skin tone; use one plain code point"))
    elif sum(map(is_emoji, text)) > 1:
        failures.append(Failure("prompt-glyph", f"tide.{key}", text, "holds more than one emoji"))


def validate_glyphs(glyphs: Mapping[str, str]) -> list[Failure]:
    """Spec 11.5: the greeting measures every emoji of the glyph table two cells wide."""
    failures: list[Failure] = []
    for key, glyph in glyphs.items():
        narrow = [char for char in glyph if is_emoji(char) and char not in layout.WIDE
                  and unicodedata.east_asian_width(char) not in ("W", "F")]
        if narrow:
            failures.append(Failure("width", f"glyphs.{key}", glyph,
                                    "is an emoji the greeting would measure one cell wide; add it to ritual/layout.WIDE"))
    return failures


```

In `validate_tide`, replace the signature, the docstring and the opening checks:

```python
def validate_tide(tide: Mapping[str, Any], background: str = palette.BACKGROUND) -> list[Failure]:
    """Every Tide variable is present; colours are RRGGBB without "#"; segment text reads on its background."""
    failures: list[Failure] = []
    for key in palette.TIDE:
        if key not in tide:
            failures.append(Failure("missing-token", f"tide.{key}", "-", "is missing from the Tide variables"))
    bad = set()
    for key, value in tide.items():
        colour = is_tide_colour(key)
```

with:

```python
def validate_tide(overrides: Mapping[str, Any], background: str = palette.BACKGROUND,
                  defaults: Mapping[str, Any] | None = None) -> list[Failure]:
    """A variant's Tide overrides, and the whole prompt they make with Tide's ``defaults`` (spec 11).

    Every override of palette.TIDE is present and names a Tide 6.1.1 variable or one of witchy's own; in the
    merged prompt, colours are RRGGBB without "#", segment text reads on its background, each icon is one plain
    emoji at most, and no value comes from the old pastel theme.
    """
    if defaults is None:
        defaults = content.load_tide_defaults()
    failures: list[Failure] = []
    for key in palette.TIDE:
        if key not in overrides:
            failures.append(Failure("missing-token", f"tide.{key}", "-", "is missing from the Tide variables"))
    for key, value in overrides.items():
        if key not in defaults and key not in palette.TIDE_OWN:
            failures.append(Failure("unknown-variable", f"tide.{key}", str(value), "is not a Tide 6.1.1 variable"))
    tide = {**defaults, **overrides}
    bad = set()
    for key, value in tide.items():
        texts = [value] if isinstance(value, str) else list(value) if isinstance(value, tuple) else []
        if "icon" in key.split("_") or key == "tide_time_format":
            _prompt_glyph(failures, key, "".join(text for text in texts if isinstance(text, str)))
        if any(isinstance(text, str) and is_pastel(text) for text in texts):
            failures.append(Failure("pastel", f"tide.{key}", str(value), "comes from the old pastel theme"))
        colour = is_tide_colour(key)
```

(The rest of `validate_tide` keeps using `tide`, which is now the merged prompt.)

In `validate_all`, replace:

```python
def validate_all(content_dir: Path = content.CONTENT_DIR) -> list[Failure]:
    failures: list[Failure] = []
    for variant in palette.VARIANTS.values():
        failures += validate_palette(variant.claude_overrides, variant.wt_scheme, variant.statusline,
                                     variant.background, variant.foreground)
        failures += validate_sky(variant.sky)
        failures += validate_ritual_palette(variant.ritual, variant.background)
        failures += validate_tide(variant.tide, variant.background)
        failures += validate_eza(variant.eza, variant.background)
```

with:

```python
def validate_all(content_dir: Path = content.CONTENT_DIR) -> list[Failure]:
    failures: list[Failure] = []
    try:
        defaults = content.load_tide_defaults(content_dir)
    except (OSError, ValueError) as exc:
        defaults = None
        failures.append(Failure("content", str(content_dir / content.TIDE_DEFAULTS), "-", f"cannot be read: {exc}"))
    for variant in palette.VARIANTS.values():
        failures += validate_palette(variant.claude_overrides, variant.wt_scheme, variant.statusline,
                                     variant.background, variant.foreground)
        failures += validate_sky(variant.sky)
        failures += validate_ritual_palette(variant.ritual, variant.background)
        if defaults is not None:
            failures += validate_tide(variant.tide, variant.background, defaults)
        failures += validate_eza(variant.eza, variant.background)
    failures += validate_glyphs(palette.GLYPHS)
```

In `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md`, section 11, replace item 1:

```
1. **Prompt glyphs:** every `*_icon` value and `tide_time_format` in TIDE holds at most one emoji; none contains U+FE0F, U+200D or U+1F3FB–U+1F3FF. Text glyphs (`❯`, `·`, Nerd Font private-use caps) are allowed.
```

with:

```
1. **Prompt glyphs:** every `*_icon` value and `tide_time_format` in the merged prompt (`build.tide`) holds at most one emoji; none contains U+FE0F, U+200D or U+1F3FB–U+1F3FF. Text glyphs (`❯`, `·`, Nerd Font private-use caps) are allowed. An emoji is a symbol (category So) that is East Asian Wide or lies past U+1F000.
```

and item 3:

```
3. **No pastel:** no TIDE value and no `WT_SCHEME` value is one of the recorded pastel hex values (`FFB7C5`, `F8A4C9`, `FF6EC7`, `FBAED2`, `F5C6E0`, `FFC8DD`, …) or one of the pastel icons (🎀 🏰 🌷 💖 💔 ✨ 🍰 🌸). The list lives in `validate.py` as `PASTEL`.
```

with:

```
3. **No pastel:** no value of the merged prompt and no `WT_SCHEME` value is one of the recorded pastel hex values (`FFB7C5`, `F8A4C9`, `FF6EC7`, `FBAED2`, `F5C6E0`, `FFC8DD`, …) or holds one of the pastel icons (🎀 🏰 🌷 💖 💔 ✨ 🍰 🌸, …). The list lives in `validate.py` as `PASTEL`: every colour and icon of `~/change_this_bitch.sh`, except the icons witchy uses on purpose (🔮 🐍 💎 🦀 ☕ 🐳).
```

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 609 tests … OK` on both, and `Moonlit Candle: all checks passed`. `tests/test_validate.py::ValidateAllTest.test_unreadable_content_is_a_failure` still sees only `content` failures for an empty folder.

- [ ] **Step 5: Commit**

```bash
git add witchy/validate.py tests/test_prompt_palette.py docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: validate the whole prompt: one plain emoji per icon, known names, no pastel, wide glyphs" -m "validate_tide checks Tide's defaults merged with the overrides; PASTEL lists the old theme's colours and icons; validate_glyphs keeps layout.WIDE in step with the glyph table." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: One fish call reports fisher, Tide, the active fish_prompt and fisher's plugin files

**Items:** spec 9.2 (last paragraph) and D19: fish decides itself whether Tide is ready: Tide installed, `tide --version` is `6.1.1`, and the active `fish_prompt` is one of the files fisher installed for Tide. Plan G's `tide` component reads the same probe for its bootstrap table (spec 5.1).

**Files:**
- Create: `witchy/fishprobe.py`
- Modify: `tests/fakes.py` (`FAKE_FUNCTIONS`, `FAKE_PROMPT`, `FAKE_TIDE_FILES`; `fake_fish` answers the probe)
- Test: `tests/test_fishprobe.py` (new)

**Interfaces:**
- Consumes: `base.Command`, `base.run_command`, `base.ComponentFailed`.
- Produces (exact names Plans G and H use):
  - `fishprobe.FISH = "fish"`, `SENTINEL = "witchy-fish"`, `TIDE_VERSION = "6.1.1"`, `TIDE_PLUGIN = "ilancosman/tide"`, `FISHER_PLUGIN = "jorgebucaran/fisher"`, `PROBE_SCRIPT: str`.
  - `@dataclass(frozen=True) class Probe: fisher: str | None; tide: str | None; prompt_path: str | None; plugins: dict[str, list[str]]`.
  - `fishprobe.fields(stdout: str) -> list[str]` (raises `ValueError("fish printed no answer")` without the sentinel).
  - `fishprobe.probe(ctx) -> Probe`: one `fish -c PROBE_SCRIPT` call, label `read fisher and Tide`, `exact=True`, default 5 s. Raises `ComponentFailed` (cause `FileNotFoundError` when fish is missing; `could not read fisher and Tide (<why>)` for an answer it cannot parse).
  - `fishprobe.plugin_files(found: Probe, plugin: str) -> list[str] | None`.
  - `fishprobe.tide_ready(found: Probe) -> str | None`: `None`, `"Tide not found"`, `"Tide is <v>, not 6.1.1"`, `"Tide is of an unknown version, not 6.1.1"`, `"fish_prompt is not Tide's (<path>)"`, `"fish_prompt is not Tide's (no fish_prompt)"`.
  - `tests/fakes.py`: `FAKE_FUNCTIONS`, `FAKE_PROMPT`, `FAKE_TIDE_FILES`; `fake_fish(variables=None, tide="6.1.1", fail_at=None, missing=False, noise="", calls=None, fisher="4.4.5", prompt=FAKE_PROMPT, plugins=None)`. `tide` is the version `tide --version` reports, or `None`/`False` for no Tide (existing `tide=False` callers keep working); `fisher` likewise; `prompt` is `functions --details fish_prompt` (`None` → `n/a`); `plugins` defaults to fisher's and Tide's own files when they are installed.

**Decisions:**
1. **Names verified on this PC** (plan Decision 12): fisher 4.4.5 keeps `_fisher_plugins` and one `_fisher_<escaped plugin>_files` list per plugin, named with `string escape --style=var` (upper-case `_2F_`; `ilancosman/tide@v6.1.1` becomes `ilancosman_2F_tide_40_v6_2E_31_2E_31_`), each path with `~` for HOME. The script computes the name in fish rather than in Python.
2. **A plugin's files are expanded one at a time.** `string replace -- \~ ~ $$files` with an empty list would read standard input (and hang under a terminal); the real-fish test includes an empty plugin.
3. **Versions are parsed leniently:** `fisher, version 4.4.5` → `4.4.5`; text in any other shape is kept as printed, so `tide_ready` can say what it found.
4. **The probe imports `components.base` at module level; `components/fish.py` (Task 7) imports it as `from .. import fishprobe`** and uses `fishprobe.X` at call time. `witchy.components` imports `fish.py` on package import, so `from ..fishprobe import probe` would fail when `witchy.fishprobe` is the first module imported.
5. **`SENTINEL` and `fields` move here;** Task 7 removes the copies from `components/fish.py`. `fake_fish` already prints `fishprobe.SENTINEL` (the same string).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fishprobe.py`:

```python
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.fakes import FAKE_PROMPT, FAKE_TIDE_FILES, fake_fish
from witchy import fishprobe
from witchy.components.base import ComponentFailed
from witchy.context import Context

FISH = shutil.which("fish")
TOOL_DIRS = list(dict.fromkeys([str(Path(FISH).parent) if FISH else "/usr/bin", "/usr/bin", "/bin"]))


def ctx(run, home=Path("/home/user"), env=None):
    return Context(home=home, env=env or {"PATH": "/nowhere"}, out=io.StringIO(), run=run)


class ProbeTest(unittest.TestCase):
    def test_a_machine_with_fisher_and_tide(self):
        calls = []
        found = fishprobe.probe(ctx(fake_fish(calls=calls)))
        self.assertEqual(found, fishprobe.Probe(
            fisher="4.4.5", tide="6.1.1", prompt_path=FAKE_PROMPT,
            plugins={"jorgebucaran/fisher": ["/home/user/.config/fish/functions/fisher.fish"],
                     "ilancosman/tide": FAKE_TIDE_FILES}))
        self.assertEqual([args for args, _ in calls], [["fish", "-c", fishprobe.PROBE_SCRIPT]])
        self.assertIsNone(fishprobe.tide_ready(found))

    def test_nothing_installed(self):
        found = fishprobe.probe(ctx(fake_fish(fisher=None, tide=None, prompt=None)))
        self.assertEqual(found, fishprobe.Probe(fisher=None, tide=None, prompt_path=None, plugins={}))
        self.assertEqual(fishprobe.tide_ready(found), "Tide not found")

    def test_what_config_fish_prints_is_ignored(self):
        found = fishprobe.probe(ctx(fake_fish(noise="Welcome!\n\0stray\0")))
        self.assertEqual((found.fisher, found.tide), ("4.4.5", "6.1.1"))

    def test_a_version_in_another_format_is_kept_as_printed(self):
        def run(args, **kwargs):
            out = "\0".join(["witchy-fish", "no-fisher", "tide", "tide 5.6.0 (dev)", "n/a", ""])
            return subprocess.CompletedProcess(args, 0, stdout=out.encode(), stderr=b"")

        self.assertEqual(fishprobe.probe(ctx(run)).tide, "tide 5.6.0 (dev)")

    def test_missing_fish_keeps_the_cause(self):
        with self.assertRaises(ComponentFailed) as caught:
            fishprobe.probe(ctx(fake_fish(missing=True)))
        self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

    def test_an_answer_without_the_marker_or_cut_short_fails(self):
        for stdout in (b"garbage", b"witchy-fish\0fisher\0"):
            def run(args, **kwargs):
                return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr=b"")

            with self.subTest(stdout=stdout), self.assertRaisesRegex(ComponentFailed,
                                                                     r"^could not read fisher and Tide \("):
                fishprobe.probe(ctx(run))


class TideReadyTest(unittest.TestCase):
    def probe(self, **changes):
        healthy = dict(fisher="4.4.5", tide="6.1.1", prompt_path=FAKE_PROMPT,
                       plugins={"ilancosman/tide": FAKE_TIDE_FILES})
        return fishprobe.Probe(**{**healthy, **changes})

    def test_ready(self):
        self.assertIsNone(fishprobe.tide_ready(self.probe()))

    def test_the_reasons(self):
        cases = (
            ({"tide": None}, "Tide not found"),
            ({"tide": "6.0.0"}, "Tide is 6.0.0, not 6.1.1"),
            ({"tide": ""}, "Tide is of an unknown version, not 6.1.1"),
            ({"prompt_path": "/home/user/.config/fish/functions/fish_prompt.fish.mine"},
             "fish_prompt is not Tide's (/home/user/.config/fish/functions/fish_prompt.fish.mine)"),
            ({"prompt_path": None}, "fish_prompt is not Tide's (no fish_prompt)"),
            ({"plugins": {}}, f"fish_prompt is not Tide's ({FAKE_PROMPT})"),
        )
        for changes, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(fishprobe.tide_ready(self.probe(**changes)), reason)

    def test_tide_installed_from_a_tag_or_in_another_case_counts(self):
        for name in ("ilancosman/tide@v6.1.1", "IlanCosman/tide"):
            with self.subTest(name=name):
                self.assertIsNone(fishprobe.tide_ready(self.probe(plugins={name: FAKE_TIDE_FILES})))
        self.assertEqual(fishprobe.plugin_files(self.probe(plugins={"ilancosman/tide-fork": FAKE_TIDE_FILES}),
                                                fishprobe.TIDE_PLUGIN), None)


@unittest.skipUnless(FISH, "fish is not installed")
class RealFishProbeTest(unittest.TestCase):
    """Real fish with a temporary HOME holding a stand-in fisher and Tide."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.functions = self.home / ".config" / "fish" / "functions"
        self.functions.mkdir(parents=True)
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"),
                    "PATH": ":".join(TOOL_DIRS)}

    def function(self, name, body):
        (self.functions / f"{name}.fish").write_text(f"function {name}\n    {body}\nend\n", encoding="utf-8")

    def fish(self, script, *args):
        subprocess.run([FISH, "-c", script, "--", *args], env=self.env, check=True, timeout=20, capture_output=True)

    def test_reads_versions_the_prompt_and_each_plugins_files(self):
        self.function("fisher", "echo 'fisher, version 4.4.5'")
        self.function("tide", "echo 'tide, version 6.1.1'")
        self.function("fish_prompt", "echo '> '")
        # As fisher records them: ~ for HOME, one list per plugin, named after the plugin as it was installed.
        self.fish("set -U _fisher_plugins jorgebucaran/fisher ilancosman/tide@v6.1.1 empty/plugin; "
                  "set -U _fisher_jorgebucaran_2F_fisher_files $argv[1]; "
                  "set -U _fisher_(string escape --style=var -- ilancosman/tide@v6.1.1)_files $argv[2..]; "
                  "set -U _fisher_empty_2F_plugin_files",
                  "~/.config/fish/functions/fisher.fish", "~/.config/fish/functions/fish_prompt.fish",
                  "~/.config/fish/functions/tide.fish")
        found = fishprobe.probe(ctx(subprocess.run, home=self.home, env=self.env))
        self.assertEqual(found, fishprobe.Probe(
            fisher="4.4.5", tide="6.1.1", prompt_path=str(self.functions / "fish_prompt.fish"),
            plugins={"jorgebucaran/fisher": [str(self.functions / "fisher.fish")],
                     "ilancosman/tide@v6.1.1": [str(self.functions / "fish_prompt.fish"),
                                                str(self.functions / "tide.fish")],
                     "empty/plugin": []}))
        self.assertIsNone(fishprobe.tide_ready(found))

    def test_without_fisher_or_tide_fish_keeps_its_own_prompt(self):
        found = fishprobe.probe(ctx(subprocess.run, home=self.home, env=self.env))
        self.assertEqual((found.fisher, found.tide, found.plugins), (None, None, {}))
        self.assertEqual(fishprobe.tide_ready(found), "Tide not found")
        self.assertTrue(found.prompt_path.endswith("/functions/fish_prompt.fish"), found.prompt_path)


if __name__ == "__main__":
    unittest.main()
```

In `tests/fakes.py`, replace:

```python
def fake_fish(variables=None, tide=True, fail_at=None, missing=False, noise="", calls=None):
```

with:

```python
# The machine fake_fish stands for: fisher 4.4.5 and Tide 6.1.1 installed by fisher in /home/user.
FAKE_FUNCTIONS = "/home/user/.config/fish/functions"
FAKE_PROMPT = f"{FAKE_FUNCTIONS}/fish_prompt.fish"
FAKE_TIDE_FILES = [FAKE_PROMPT, f"{FAKE_FUNCTIONS}/tide.fish", f"{FAKE_FUNCTIONS}/_tide_item_git.fish"]


def fake_fish(variables=None, tide="6.1.1", fail_at=None, missing=False, noise="", calls=None, fisher="4.4.5",
              prompt=FAKE_PROMPT, plugins=None):
```

In its docstring, replace:

```python
    call is appended to ``calls``, with its input as a string.
    """
    from witchy.components import fish

    store = {} if variables is None else variables

    def answer(args, received):
```

with:

```python
    call is appended to ``calls``, with its input as a string.

    The fisher and Tide probe (witchy.fishprobe) sees: ``fisher``, the version ``fisher --version`` reports (None:
    fisher is not installed); ``tide``, the version ``tide --version`` reports (None or False: Tide is not
    installed); ``prompt``, the file fish_prompt comes from (None: not defined); and ``plugins``, fisher's plugins
    and their files. By default ``plugins`` lists fisher and Tide (``FAKE_TIDE_FILES``) when they are installed.
    """
    from witchy import fishprobe
    from witchy.components import fish

    store = {} if variables is None else variables
    if plugins is None:
        plugins = {}
        if fisher is not None:
            plugins["jorgebucaran/fisher"] = [f"{FAKE_FUNCTIONS}/fisher.fish"]
        if tide:
            plugins["ilancosman/tide"] = list(FAKE_TIDE_FILES)

    def answer(args, received):
        if args == ["fish", "-c", fishprobe.PROBE_SCRIPT]:
            fields = ["fisher", f"fisher, version {fisher}"] if fisher is not None else ["no-fisher"]
            fields += ["tide", f"tide, version {tide}"] if tide else ["no-tide"]
            fields.append(prompt if prompt is not None else "n/a")
            for name, files in plugins.items():
                fields += [name, str(len(files)), *files]
            return 0, fields
```

and in `run`, replace:

```python
        printed = noise + ("" if fields is None else "".join(f"{field}\0" for field in [fish.SENTINEL, *fields]))
```

with:

```python
        printed = noise + ("" if fields is None else "".join(f"{field}\0" for field in [fishprobe.SENTINEL, *fields]))
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_fishprobe`
Expected:
```
ERROR: test_fishprobe (unittest.loader._FailedTest.test_fishprobe)
ImportError: Failed to import test module: test_fishprobe
…
ImportError: cannot import name 'fishprobe' from 'witchy' (…/witchy/__init__.py)
FAILED (errors=1)
```

- [ ] **Step 3: Write the probe**

Create `witchy/fishprobe.py`:

```python
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
```

- [ ] **Step 4: Check the import order works both ways**

Run: `python3 -c "import witchy.fishprobe" && python3 -c "import witchy.components, witchy.fishprobe" && echo ok`
Expected: `ok`

- [ ] **Step 5: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 620 tests … OK` on both, and `Moonlit Candle: all checks passed`. The real-fish probe tests run in about a tenth of a second each; a hang there means a `string replace` is reading standard input.

- [ ] **Step 6: Commit**

```bash
git add witchy/fishprobe.py tests/fakes.py tests/test_fishprobe.py
git commit -m "feat: one fish call reports fisher, Tide, the active fish_prompt and fisher's plugin files" -m "witchy.fishprobe.probe and tide_ready: Tide is ready when it is 6.1.1 and fish_prompt is one of the files fisher installed for it. fake_fish answers the probe." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: fish sets every Tide variable and fish_emoji_width, erases unknown tide_ ones, and checks Tide itself

**Items:**
- Spec 6.1: the fish component uses the merged set (`build.tide(variant)`) plus `fish_emoji_width` = `2`, recorded and restored like a Tide variable. A universal `tide_*` variable that is not in Tide 6.1.1's list (and not the moon item's) is erased and recorded, so uninstall gives it back; `_tide_*` is never touched.
- Spec 9.2 last paragraph and D19: fish asks fish (Task 6's probe), not the `tide` component's result. When Tide is not ready it plans `skipped: Tide not ready (run: python3 -m witchy install --only tide)` and sets no variable; the fish files and the greeting still install.

**Files:**
- Modify: `witchy/components/fish.py`
- Modify: `tests/fakes.py` (`fake_fish` snapshot answer; new `fake_tide`)
- Test: `tests/test_components_fish.py`, `tests/test_fish_integration.py`

**Interfaces:**
- Consumes: `fishprobe.probe`, `fishprobe.tide_ready`, `fishprobe.fields`, `fishprobe.SENTINEL`, `fishprobe.PROBE_SCRIPT` (Task 6); `build.tide` (Task 2); `palette.FISH` (Task 3).
- Produces:
  - `fish.desired(variant: str) -> dict[str, list[str]]`: every variable the component sets (159 today: 156 Tide names, the moon item's 2 and `fish_emoji_width`), as fish lists.
  - `fish.snapshot(ctx, names) -> dict[str, dict]`: each name asked for, then every other universal `tide_*` variable that exists (the "strays"). The old `(tide, found)` tuple is gone.
  - `fish.NOT_READY = "skipped: Tide not ready (run: python3 -m witchy install --only tide)"`.
  - The fish entry's `variables[name]` is `{"previous": <snapshot>, "installed": [values]}`, or `"installed": None` for an erased stray.
  - Plan action for a stray: `fish: set -e -U <name> (now: <value>)`. Message when Tide is not ready: `fish: <tide_ready reason>; prompt not recoloured. Run: python3 -m witchy install --only tide`.
  - `fish.SENTINEL` and `fish._fields` are removed (use `fishprobe.SENTINEL` and `fishprobe.fields`).
  - `tests/fakes.py`: `fake_tide(fish_config: Path, env: dict) -> None` for real-fish tests.

**Decisions:**
1. **Probe first, then snapshot:** two fish calls when Tide is ready, one when it is not (`test_a_tide_that_is_not_ready_gets_no_variable` pins that only the probe runs). Merging the probe into the snapshot script would save about 0.4 s but tie Plan G's bootstrap to the variable reader.
2. **The snapshot lists strays itself** (`set -U --names | string match 'tide_*'`, which matches whole names, so `_tide_*` never comes back). A regex form (`string match -r '^tide_'`) prints only the matched part; the real-fish round trip caught that in the prototype.
3. **An erased stray is recorded with `"installed": None`.** Restore needs no special case: `current.get("value")` of an absent variable is `None`, so a stray that is still gone counts as "still holds what install left" and gets its previous value back, and one the user re-created counts as changed and is left with a warning. A reinstall keeps the first record, because `apply` starts from the recorded variables.
4. **Drift order:** desired names come in `build.tide` order (Tide's names sorted, then the moon item's), then `fish_emoji_width`, then strays sorted. That is why `test_a_failed_set_stops_and_records_only_what_was_set` now uses `tide_aws_icon` as "set before the failure" and `tide_moon_color` as "never reached".
5. **Uninstall after Tide was removed** (plan Decision 17): only the `tide_*` names witchy set decide "gone"; `fish_emoji_width` is still erased or restored.
6. **`from .. import fishprobe`, not `from ..fishprobe import …`** (Task 6 Decision 4).

- [ ] **Step 1: Write the failing tests**

In `tests/fakes.py`, replace the module docstring and imports:

```python
"""Stand-ins for the Windows side, so no test runs cmd.exe or reg.exe."""
import io
import struct
```

with:

```python
"""Stand-ins for the Windows side and for fish, so no test runs cmd.exe or reg.exe or needs a real Tide."""
import io
import shutil
import struct
```

In `fake_fish`'s `answer`, replace:

```python
        if args[:3] == ["fish", "-c", fish.SNAPSHOT_SCRIPT] and args[3] == "--":
            fields = ["tide" if tide else "no-tide"]
            for name in args[4:]:
```

with:

```python
        if args[:3] == ["fish", "-c", fish.SNAPSHOT_SCRIPT] and args[3] == "--":
            # The names asked for, then every other universal tide_ variable (never Tide's private _tide_ ones).
            fields = []
            for name in args[4:] + sorted(name for name in store if name.startswith("tide_") and name not in args[4:]):
```

At the end of `tests/fakes.py`, add:

```python


def fake_tide(fish_config, env):
    """Make the real fish behind ``env`` see Tide 6.1.1 installed by fisher in the folder ``fish_config``.

    It writes a ``tide`` function that reports version 6.1.1 and a stand-in for Tide's fish_prompt, and sets the
    universal variables fisher keeps for an installed plugin. ``env`` must point HOME and XDG_CONFIG_HOME at
    temporary folders.
    """
    functions = fish_config / "functions"
    functions.mkdir(parents=True, exist_ok=True)
    (functions / "tide.fish").write_text("function tide\n    echo 'tide, version 6.1.1'\nend\n", encoding="utf-8")
    (functions / "fish_prompt.fish").write_text("function fish_prompt\n    echo '> '\nend\n", encoding="utf-8")
    subprocess.run([shutil.which("fish"), "-c", "set -U _fisher_plugins ilancosman/tide; "
                    "set -U _fisher_ilancosman_2F_tide_files $argv", "--",
                    str(functions / "tide.fish"), str(functions / "fish_prompt.fish")],
                   env=env, check=True, timeout=20, capture_output=True)
```

In `tests/test_components_fish.py`, replace:

```python
from tests.fakes import fake_fish
from witchy import build, components, jsonio, palette, runner
```

with:

```python
from tests.fakes import fake_fish, fake_tide
from witchy import build, components, fishprobe, jsonio, palette, runner
```

After the closing `}` of `USER_TIDE`, add:

```python
# Every variable witchy sets: Tide's, the moon item's and fish_emoji_width.
DESIRED = {name: [value] if isinstance(value, str) else list(value)
           for name, value in {**build.tide(), **palette.FISH}.items()}
NOT_READY = "skipped: Tide not ready (run: python3 -m witchy install --only tide)"
```

In `InstallTest`, after `test_installs_the_files_and_recolours_tide`, add:

```python
    def test_sets_every_tide_variable_and_the_emoji_width(self):
        self.assertEqual(runner.install(self.ctx()), 0)
        self.assertEqual({name: self.value(name) for name in DESIRED}, DESIRED)
        self.assertEqual(len(DESIRED), 159)
        self.assertEqual(self.value("fish_emoji_width"), ["2"])
        self.assertEqual(self.value("tide_left_prompt_prefix"), ["\ue0ba"])
        self.assertEqual(self.value("tide_pwd_markers"), list(build.tide()["tide_pwd_markers"]))

    def test_a_tide_variable_tide_does_not_define_is_erased_and_recorded(self):
        self.variables["tide_sparkle_icon"] = {"value": ["✨"], "exported": False}
        self.assertEqual(runner.install(self.ctx(dry_run=True)), 0)
        self.assertIn("fish: set -e -U tide_sparkle_icon (now: ✨)", self.out.getvalue())
        self.assertEqual(runner.install(self.ctx()), 0)
        self.assertNotIn("tide_sparkle_icon", self.variables)
        self.assertEqual(self.entry()["variables"]["tide_sparkle_icon"],
                         {"previous": {"value": ["✨"], "exported": False}, "installed": None})
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.variables["tide_sparkle_icon"], {"value": ["✨"], "exported": False})

    def test_a_reinstall_keeps_the_record_of_an_erased_variable(self):
        self.variables["tide_sparkle_icon"] = {"value": ["✨"], "exported": False}
        self.variables["tide_old_icon"] = {"value": ["🎀"], "exported": False}
        self.assertEqual(runner.install(self.ctx()), 0)
        self.assertEqual(runner.install(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.entry()["variables"]["tide_sparkle_icon"],
                         {"previous": {"value": ["✨"], "exported": False}, "installed": None})
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-140000")), 0)
        self.assertEqual(self.variables["tide_sparkle_icon"], {"value": ["✨"], "exported": False})
        self.assertEqual(self.variables["tide_old_icon"], {"value": ["🎀"], "exported": False})

    def test_tides_private_variables_are_never_touched(self):
        self.variables["_tide_left_items"] = {"value": ["pwd"], "exported": False}
        self.assertEqual(runner.install(self.ctx()), 0)
        self.assertEqual(self.variables["_tide_left_items"], {"value": ["pwd"], "exported": False})
        self.assertNotIn("_tide_left_items", self.entry()["variables"])

    def test_upgrading_an_install_that_set_fewer_variables_still_gives_back_the_users_prompt(self):
        older = {name: DESIRED[name] for name in USER_TIDE}  # an older witchy set only these
        with mock.patch.object(fish, "desired", return_value=older):
            self.assertEqual(runner.install(self.ctx()), 0)
        self.assertEqual(runner.install(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.entry()["variables"]["tide_pwd_bg_color"]["previous"],
                         {"value": ["3465A4"], "exported": False})
        self.assertEqual(set(self.entry()["variables"]), set(DESIRED))
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-140000")), 0)
        self.assertEqual(self.variables, USER_TIDE)

    def test_a_tide_that_is_not_ready_gets_no_variable(self):
        cases = ((fake_fish(self.variables, tide=None, calls=self.calls), "Tide not found"),
                 (fake_fish(self.variables, tide="6.0.0", calls=self.calls), "Tide is 6.0.0, not 6.1.1"),
                 (fake_fish(self.variables, prompt="/usr/share/fish/functions/fish_prompt.fish", calls=self.calls),
                  "fish_prompt is not Tide's (/usr/share/fish/functions/fish_prompt.fish)"))
        for run, reason in cases:
            with self.subTest(reason=reason):
                self.calls.clear()
                self.assertEqual(runner.install(self.ctx(run=run)), 2)
                self.assertEqual(self.state()["last_install"]["results"], {"fish": NOT_READY})
                self.assertIn(f"fish: {reason}; prompt not recoloured. Run: python3 -m witchy install --only tide",
                              self.out.getvalue())
                self.assertEqual([args for args, _ in self.calls], [["fish", "-c", fishprobe.PROBE_SCRIPT]])
                self.assertEqual(self.variables, USER_TIDE)

```

Then adapt the existing tests to the new set of names:

- In `test_records_what_each_variable_held_before`, `test_a_fish_that_times_out_while_setting_keeps_the_files_recorded` and `unknown_outcome`, replace `set(palette.TIDE)` with `set(DESIRED)` (three places):

```bash
sed -i 's/set(palette.TIDE)/set(DESIRED)/' tests/test_components_fish.py
```

- In `test_without_tide_the_files_still_install`, replace:

```python
        self.assertEqual(self.state()["last_install"]["results"], {"fish": "skipped: Tide not found"})
```

with:

```python
        self.assertEqual(self.state()["last_install"]["results"], {"fish": NOT_READY})
```

(The message line `fish: Tide not found; prompt not recoloured.` it also checks is still a prefix of the new message.)

- In `test_a_failed_set_stops_and_records_only_what_was_set`, replace:

```python
        self.assertIn("tide_moon_color", variables)  # set before the failure
        self.assertNotIn("tide_pwd_bg_color", variables)
        self.assertNotIn("tide_time_color", variables)  # never reached
```

with:

```python
        self.assertIn("tide_aws_icon", variables)  # set before the failure
        self.assertNotIn("tide_pwd_bg_color", variables)
        self.assertNotIn("tide_time_color", variables)  # never reached
        self.assertNotIn("tide_moon_color", variables)
```

- In `test_a_set_call_killed_by_a_signal_is_an_unknown_outcome`, replace:

```python
        name = next(iter(palette.TIDE))
        self.unknown_outcome(lambda args: subprocess.CompletedProcess(
            args, -9, stdout=f"{fish.SENTINEL}\0{name}\0".encode(), stderr=b""))
```

with:

```python
        name = next(iter(DESIRED))
        self.unknown_outcome(lambda args: subprocess.CompletedProcess(
            args, -9, stdout=f"{fishprobe.SENTINEL}\0{name}\0".encode(), stderr=b""))
```

- In `test_dry_run_reads_but_never_writes`, after the `tide_moon_color` line, add:

```python
        self.assertIn("fish: set -U fish_emoji_width 2 (now: unset)", self.out.getvalue())
```

- In `UninstallTest.test_tide_removed_before_uninstall_gives_one_warning`, replace:

```python
        self.variables.clear()  # Tide's own uninstall erases every tide_ variable
```

with:

```python
        for name in [name for name in self.variables if name.startswith("tide_")]:
            del self.variables[name]  # Tide's own uninstall erases every tide_ variable
```

and replace:

```python
        self.assertEqual(self.set_calls(), [])
        self.assertFalse((self.home / ".claude" / "witchy").exists())
```

(the one in that test) with:

```python
        self.assertEqual(self.set_calls(), ["fish_emoji_width\0erase\0" "0\0"])  # fish's own goes back
        self.assertEqual(self.variables, {})
        self.assertFalse((self.home / ".claude" / "witchy").exists())
```

- In `UninstallTest.test_dry_run_lists_the_restore_and_changes_nothing`, replace:

```python
        self.assertIn(f"fish: restore {len(palette.TIDE) - 1} Tide variables", self.out.getvalue())
```

with:

```python
        self.assertIn(f"fish: restore {len(DESIRED) - 1} Tide variables", self.out.getvalue())
```

- In `DoctorTest.test_a_healthy_install`, replace:

```python
        self.assertIn(f"✓ fish              {len(palette.TIDE)} Tide variables match", output)
```

with:

```python
        self.assertIn(f"✓ fish              {len(DESIRED)} Tide variables match", output)
```

- In `RealFishBytesTest.setUp`, replace:

```python
        config = self.root / "config"
        (config / "fish" / "functions").mkdir(parents=True)
        (config / "fish" / "functions" / "tide.fish").write_text("function tide\nend\n", encoding="utf-8")
        tools = dict.fromkeys([str(Path(FISH).parent), "/usr/bin", "/bin"])
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(config), "PATH": os.pathsep.join(tools)}
```

with:

```python
        config = self.root / "config"
        tools = dict.fromkeys([str(Path(FISH).parent), "/usr/bin", "/bin"])
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(config), "PATH": os.pathsep.join(tools)}
        fake_tide(config / "fish", self.env)
```

In `tests/test_fish_integration.py`, replace:

```python
from witchy import palette, runner
```

with:

```python
from tests.fakes import fake_tide
from witchy import build, fishprobe, palette, runner
```

In `RealFishRoundTripTest.setUp`, replace:

```python
        self.config = self.root / "config" / "fish"
        (self.config / "functions").mkdir(parents=True)
        (self.config / "functions" / "tide.fish").write_text("function tide\nend\n", encoding="utf-8")
```

with:

```python
        self.config = self.root / "config" / "fish"
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config.parent), "PATH": ":".join(TOOL_DIRS)}
        fake_tide(self.config, self.env)
```

and delete the later line (now a duplicate):

```python
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config.parent), "PATH": ":".join(TOOL_DIRS)}
```

that sits between the `_tide_remove_unusable_items.fish` write and `self.fish(BEFORE)`.

In `test_install_recolours_tide_and_uninstall_gives_every_variable_back`, after the `tide_moon_bg_color` assertion, add:

```python
        self.assertEqual(self.fish("printf '%s\\n' $tide_pwd_icon $fish_emoji_width"), "🧹\n2\n")
        self.assertEqual(self.fish("set -U --names | string match 'tide_*'").split(), sorted(build.tide()))
```

and replace:

```python
                         ["_tide_remove_unusable_items.fish", "tide.fish"])
```

with:

```python
                         ["_tide_remove_unusable_items.fish", "fish_prompt.fish", "tide.fish"])
```

Replace the whole `test_snapshot_reads_values_with_spaces_and_empty_lists` with:

```python
    def test_snapshot_reads_values_with_spaces_and_empty_lists(self):
        self.fish("set -U tide_a 'two words' ''; set -U tide_b; set -Ux tide_c x; set -U _tide_private x")
        asked = ["tide_a", "tide_b", "tide_c", "tide_none"]
        found = fish.snapshot(self.ctx("20261003-120000"), asked)
        self.assertEqual({name: found[name] for name in asked},
                         {"tide_a": {"value": ["two words", ""], "exported": False},
                          "tide_b": {"value": [], "exported": False},
                          "tide_c": {"value": ["x"], "exported": True},
                          "tide_none": {"absent": True}})
        # Every other universal tide_ variable comes too, so install can erase it; Tide's private ones never do.
        self.assertEqual(set(found) - set(asked), {"tide_left_prompt_items", "tide_pwd_bg_color", "tide_time_color",
                                                   "tide_cmd_duration_threshold"})
```

In `test_the_set_script_sets_exports_and_erases`, replace:

```python
        _, found = fish.snapshot(ctx, ["tide_a", "tide_c", "tide_pwd_bg_color"])
        self.assertEqual(found, {"tide_a": {"value": ["a b", ""], "exported": False},
                                 "tide_c": {"value": ["x"], "exported": True},
                                 "tide_pwd_bg_color": {"absent": True}})
```

with:

```python
        found = fish.snapshot(ctx, ["tide_a", "tide_c", "tide_pwd_bg_color"])
        self.assertEqual({name: found[name] for name in ("tide_a", "tide_c", "tide_pwd_bg_color")},
                         {"tide_a": {"value": ["a b", ""], "exported": False},
                          "tide_c": {"value": ["x"], "exported": True},
                          "tide_pwd_bg_color": {"absent": True}})
```

In `test_the_set_script_stops_at_the_first_failure`, replace:

```python
        self.assertEqual(fish._fields(done.stdout), ["tide_a"])
        self.assertEqual(fish.snapshot(ctx, ["tide_b"])[1], {"tide_b": {"absent": True}})
```

with:

```python
        self.assertEqual(fishprobe.fields(done.stdout), ["tide_a"])
        self.assertEqual(fish.snapshot(ctx, ["tide_b"])["tide_b"], {"absent": True})
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_fish tests.test_fish_integration`
Expected: `Ran 63 tests` and `FAILED (failures=35, errors=7)`. The snapshot answer no longer starts with `tide`/`no-tide`, so most installs read `skipped: could not read the Tide variables (…)` (`AssertionError: 2 != 0`); the new tests fail on `fish.desired` (`AttributeError`), on the missing `NOT_READY` outcome and on the old `(tide, found)` tuple (`TypeError: tuple indices must be integers or slices, not str`).

- [ ] **Step 3: Implement**

In `witchy/components/fish.py`, replace the module docstring:

```python
"""fish: the greeting package, the fish functions and conf.d snippet, and the Tide prompt colours (spec 5, 6, 7)."""
```

with:

```python
"""fish: the greeting package, the fish functions and conf.d snippet, and every Tide variable (spec 5, 6, 7)."""
```

Replace:

```python
from .. import build, palette
```

with:

```python
from .. import build, fishprobe, palette
```

Delete the line:

```python
SENTINEL = "witchy-fish"  # whatever config.fish prints comes before it
```

Replace:

```python
PROMPT_ITEMS = ("tide_left_prompt_items", "tide_right_prompt_items")
```

with:

```python
PROMPT_ITEMS = ("tide_left_prompt_items", "tide_right_prompt_items")
NOT_READY = "skipped: Tide not ready (run: python3 -m witchy install --only tide)"
```

Replace the comment and the first lines of `SNAPSHOT_SCRIPT`:

```python
# Prints the sentinel, whether Tide is installed, then each name's universal value: the name, "absent" or
# "exported"/"unexported", the element count and the elements. Every field ends in NUL, which no fish
# value can hold.
SNAPSHOT_SCRIPT = """\
printf '%s\\0' witchy-fish
functions -q tide; and printf 'tide\\0'; or printf 'no-tide\\0'
for name in $argv
    set -e -g $name  # a global set by config.fish would hide the universal value
```

with:

```python
# Prints the sentinel, then the universal value of each name asked for and of every other universal tide_
# variable (Tide's private _tide_ ones are not listed): the name, "absent" or "exported"/"unexported", the
# element count and the elements. Every field ends in NUL, which no fish value can hold.
SNAPSHOT_SCRIPT = """\
printf '%s\\0' witchy-fish
set -l names $argv
for name in (set -U --names | string match 'tide_*')
    contains -- $name $argv; or set -a names $name
end
for name in $names
    set -e -g $name  # a global set by config.fish would hide the universal value here (doctor reports it)
```

Replace `_fields` and the head of `snapshot`:

```python
def _fields(stdout: str) -> list[str]:
    head, found, rest = stdout.partition(SENTINEL + "\0")
    if not found:
        raise ValueError("fish printed no answer")
    return rest.split("\0")[:-1]


def snapshot(ctx: Any, names: list[str]) -> tuple[bool, dict[str, dict]]:
    """Whether Tide is installed, and each variable as ``{"absent": True}`` or ``{"value": [...], "exported": bool}``."""
    done = run_command(ctx, Command((FISH, "-c", SNAPSHOT_SCRIPT, "--", *names), "read the Tide variables",
                                    exact=True))
    try:
        fields = _fields(done.stdout)
        tide, index, found = fields[0] == "tide", 1, {}
```

with:

```python
def snapshot(ctx: Any, names: list[str]) -> dict[str, dict]:
    """Each of ``names``, then every other universal ``tide_`` variable, as ``{"absent": True}`` or
    ``{"value": [...], "exported": bool}``."""
    done = run_command(ctx, Command((FISH, "-c", SNAPSHOT_SCRIPT, "--", *names), "read the Tide variables",
                                    exact=True))
    try:
        fields = fishprobe.fields(done.stdout)
        index, found = 0, {}
```

and, at its end, replace:

```python
        return tide, {name: found[name] for name in names}
```

with:

```python
        return {**{name: found[name] for name in names}, **found}
```

After `_values`, add:

```python
def desired(variant: str) -> dict[str, list[str]]:
    """Every variable witchy sets, as fish lists: all of Tide's, the moon item's and fish's own (spec 6.1)."""
    return {name: _values(value) for name, value in {**build.tide(variant), **palette.FISH}.items()}


def _action(name: str, mode: str, values: list[str], current: dict) -> str:
    now = _shown(current["value"]) if "value" in current else "unset"
    if mode == "erase":
        return f"fish: set -e -U {name} (now: {now})"
    return f"fish: set -U{'x' if mode == 'exported' else ''} {name} {' '.join(values)} (now: {now})"
```

In `FishComponent.plan`, replace:

```python
        desired = {name: _values(value) for name, value in palette.VARIANTS[variant].tide.items()}
        try:
            tide, current = snapshot(ctx, list(desired))
        except ComponentFailed as exc:
```

with:

```python
        wanted = desired(variant)
        try:
            # Tide's readiness comes from fish itself, never from how the tide component ended (spec D19).
            reason = fishprobe.tide_ready(fishprobe.probe(ctx))
            current = None if reason else snapshot(ctx, list(wanted))
        except ComponentFailed as exc:
```

and replace:

```python
        if not tide:
            plan.notes.insert(0, GREETING_NOTE)
            plan.outcome = "skipped: Tide not found"
            ctx.say("fish: Tide not found; prompt not recoloured.")
            return plan
        records, updates = {}, []
        for name, values in desired.items():
            # A reinstall keeps the value from before the first install, not witchy's own.
            previous = recorded[name]["previous"] if name in recorded else current[name]
            records[name] = {"previous": previous, "installed": values}
            if current[name].get("value") != values:
                updates.append((name, "exported" if previous.get("exported") else "set", values))
        plan.data.update(records=records, updates=updates)
        plan.notes.insert(0, NEW_TAB_NOTE)
        plan.actions = [f"fish: set -U{'x' if mode == 'exported' else ''} {name} {' '.join(values)} "
                        f"(now: {_shown(current[name]['value']) if 'value' in current[name] else 'unset'})"
                        for name, mode, values in updates]
        return plan
```

with:

```python
        if current is None:
            plan.notes.insert(0, GREETING_NOTE)
            plan.outcome = NOT_READY
            ctx.say(f"fish: {reason}; prompt not recoloured. Run: {fix_command('tide')}")
            return plan
        records, updates = {}, []
        for name, values in wanted.items():
            # A reinstall keeps the value from before the first install, not witchy's own.
            previous = recorded[name]["previous"] if name in recorded else current[name]
            records[name] = {"previous": previous, "installed": values}
            if current[name].get("value") != values:
                updates.append((name, "exported" if previous.get("exported") else "set", values))
        for name in sorted(current.keys() - wanted.keys()):
            # A tide_ variable Tide 6.1.1 does not define is erased; uninstall gives it back (spec 6.1).
            previous = recorded[name]["previous"] if name in recorded else current[name]
            records[name] = {"previous": previous, "installed": None}
            if "value" in current[name]:
                updates.append((name, "erase", []))
        plan.data.update(records=records, updates=updates)
        plan.notes.insert(0, NEW_TAB_NOTE)
        plan.actions = [_action(name, mode, values, current[name]) for name, mode, values in updates]
        return plan
```

In `apply`, replace:

```python
                done = set(_fields(result.stdout))
```

with:

```python
                done = set(fishprobe.fields(result.stdout))
```

In `restore`, replace:

```python
                _, current = snapshot(ctx, list(variables))
            except ComponentFailed as exc:
                if not isinstance(exc.__cause__, FileNotFoundError):
```

with:

```python
                current = snapshot(ctx, list(variables))
            except ComponentFailed as exc:
                if not isinstance(exc.__cause__, FileNotFoundError):
```

and replace:

```python
            if current and all(found.get("absent") for found in current.values()):
                warnings.append("fish: Tide's variables are gone (was Tide removed?); nothing to restore.")
                current = {}
```

with:

```python
            # The tide_ variables witchy set; fish's own (fish_emoji_width) and the erased ones do not go with Tide.
            ours = [name for name, record in variables.items()
                    if name.startswith("tide_") and record["installed"] is not None]
            if current and ours and all(current[name].get("absent") for name in ours):
                warnings.append("fish: Tide's variables are gone (was Tide removed?); nothing to restore.")
                current = {name: found for name, found in current.items() if name not in ours}
```

In `check`, replace:

```python
                _, current = snapshot(ctx, list(variables))
            except ComponentFailed as exc:
                checks.append(Check("warn", self.name, f"cannot check the Tide variables: {exc}"))
```

with:

```python
                current = snapshot(ctx, list(variables))
            except ComponentFailed as exc:
                checks.append(Check("warn", self.name, f"cannot check the Tide variables: {exc}"))
```

(Task 8 rewrites `check`.)

- [ ] **Step 4: Check the import order still works both ways**

Run: `python3 -c "import witchy.fishprobe" && python3 -c "import witchy.components, witchy.fishprobe" && echo ok`
Expected: `ok`

- [ ] **Step 5: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 626 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 6: Commit**

```bash
git add witchy/components/fish.py tests/fakes.py tests/test_components_fish.py tests/test_fish_integration.py
git commit -m "feat: fish sets every Tide variable and fish_emoji_width, erases unknown tide_ ones, and checks Tide itself" -m "The fish component installs build.tide plus palette.FISH, records and erases universal tide_ variables Tide 6.1.1 does not define (never _tide_ ones), and skips the variables unless fishprobe says Tide 6.1.1 owns fish_prompt." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: doctor checks every prompt variable, unknown tide_ ones and the globals a new shell sets

**Items:** spec 9.1, fish part:
- A global hiding a universal no longer passes as ✓: doctor reads each name a second time in a fresh interactive shell (`fish -i -c` with `WITCHY_DOCTOR=1`), and ✗ `tide_X is overridden by a global in config.fish or conf.d`.
- `conf.d/witchy.fish` skips the sky job when `WITCHY_DOCTOR` is set, and `fish_greeting` stays quiet.
- ✓/✗ every variable matches the spec (all 158 and `fish_emoji_width`, not only what an install recorded); ✗ lists the drifted names, fix `python3 -m witchy install --only fish`.
- ✗ any universal `tide_*` not in Tide 6.1.1's list.
- doctor's interactive read gets a 15 s timeout.

**Files:**
- Modify: `witchy/components/base.py` (`Command.env`, `run_command`)
- Modify: `witchy/components/fish.py` (`SHOWN_MAX`, `SHELL_TIMEOUT`, `GLOBALS_SCRIPT`, `shadows`, `_prompt_checks`, `check`)
- Modify: `witchy/runner.py` (`doctor` takes the variant from state)
- Modify: `content/fish/conf.d/witchy.fish`, `content/fish/functions/fish_greeting.fish`
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (9.1), `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (5.3)
- Test: `tests/fakes.py` (`globals`), `tests/test_base.py`, `tests/test_components_fish.py`, `tests/test_fish_files.py`, `tests/test_fish_integration.py`

**Interfaces:**
- Consumes: `fish.desired`, `fish.snapshot` (Task 7); `fishprobe.probe`, `fishprobe.tide_ready`, `fishprobe.fields` (Task 6); `Command.timeout` (Task 1).
- Produces:
  - `Command(..., env: dict[str, str] = {})`, added to `ctx.env` by `run_command`.
  - `fish.SHELL_TIMEOUT = 15`, `fish.SHOWN_MAX = 10`, `fish.GLOBALS_SCRIPT: str`.
  - `fish.shadows(ctx, names) -> dict[str, list[str]]`: the globals a fresh `fish -i -c` holds, with their values (Plan H compares `tide_character_color`'s global with today's caret file). Label `read the prompt variables a new shell sees`, empty standard input, `exact=True`, 15 s, env `WITCHY_DOCTOR=1`.
  - doctor lines for fish: `✓ <N> prompt variables match` | `✗ prompt variables changed: <first 10, sorted> (and N more)`; `✗ not Tide 6.1.1 variables: <names>`; `✗ <name> is overridden by a global in config.fish or conf.d` (fix `python3 -m witchy install --only tide`); `⚠ Tide variables not checked: <tide_ready reason>` (fix `--only tide`); `⚠ cannot check the Tide variables: <why>`.
  - `runner.doctor` sets `ctx.variant` from state when the CLI gave none.
  - `fake_fish(..., globals=None)`: answers the `fish -i -c GLOBALS_SCRIPT` call with these names and values.

**Decisions:**
1. **Compare with the spec, not the record** (plan Decision 14). An install recorded by an older witchy (31 or 32 names) now shows ✗ until reinstalled, which is what spec 9.1 asks (every name, "not 31").
2. **The snapshot keeps erasing globals in its own process** (plan Decision 13): it is the exact way to read the universal value; the interactive read is what catches globals. Spec 9.1 is reworded.
3. **`GLOBALS_SCRIPT` uses `if … end`, not `set -q -g $name; and printf …`:** with the short form the script's status is that of the last `set -q`, so fish exits 1 whenever the last name has no global. The fake could not show this; the real-fish test `test_doctor_sees_globals_that_only_a_new_interactive_shell_sets` did.
4. **Standard input is an empty pipe** (`input=""`): `fish -i` never reads the user's terminal, so a doctor run cannot hang on it.
5. **Tide not ready is one ⚠, not three ✗** (plan Decision 14). doctor still probes before reading variables; three fish calls in all (probe, snapshot, interactive read).
6. **A global's fix is `--only tide`,** because Plan G's takeover comments out `set -g tide_*` lines. `doctor --fix` (Plan H) will run it.
7. **`fish_greeting` gets `WITCHY_DOCTOR` in its guard list** although `fish -i -c` never calls the greeting on fish 3.7.0 (checked); `test_the_doctors_new_shell_never_greets` pins the silence either way.

- [ ] **Step 1: Write the failing tests**

In `tests/fakes.py`, replace:

```python
def fake_fish(variables=None, tide="6.1.1", fail_at=None, missing=False, noise="", calls=None, fisher="4.4.5",
              prompt=FAKE_PROMPT, plugins=None):
```

with:

```python
def fake_fish(variables=None, tide="6.1.1", fail_at=None, missing=False, noise="", calls=None, fisher="4.4.5",
              prompt=FAKE_PROMPT, plugins=None, globals=None):
```

At the end of its docstring, replace:

```python
    and their files. By default ``plugins`` lists fisher and Tide (``FAKE_TIDE_FILES``) when they are installed.
    """
```

with:

```python
    and their files. By default ``plugins`` lists fisher and Tide (``FAKE_TIDE_FILES``) when they are installed.

    A new interactive shell (doctor's read) sees ``globals``: names set with ``set -g`` by config.fish or conf.d,
    each with its value.
    """
```

In `answer`, before `if args == ["fish", "-c", fish.SET_SCRIPT]:`, add:

```python
        if args[:4] == ["fish", "-i", "-c", fish.GLOBALS_SCRIPT] and args[4] == "--":
            fields = []
            for name in args[5:]:
                if name in (globals or {}):
                    fields += [name, str(len(globals[name])), *globals[name]]
            return 0, fields
```

In `tests/test_base.py`, in `RunCommandTest`, before `test_an_exact_command_sends_and_reads_every_byte_unchanged`, add:

```python
    def test_a_command_can_add_environment_variables(self):
        seen = {}

        def run(args, **kwargs):
            seen.update(kwargs)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        run_command(self.ctx(run), Command(("fish",), "ask fish", env={"WITCHY_DOCTOR": "1"}))
        self.assertEqual(seen["env"], {"HOME": "/tmp/h", "WITCHY_DOCTOR": "1"})

```

In `tests/test_components_fish.py`, in `DoctorTest.test_a_healthy_install`, replace:

```python
        self.assertIn(f"✓ fish              {len(DESIRED)} Tide variables match", output)
        self.assertIn("✓ fish              no greeting or sky errors in the last 7 days", output)
```

with:

```python
        self.assertIn(f"✓ fish              {len(DESIRED)} prompt variables match", output)
        self.assertIn("✓ fish              no greeting or sky errors in the last 7 days", output)
        self.assertNotIn("overridden", output)
```

In `test_a_changed_file_and_a_changed_variable_fail`, replace:

```python
        self.assertIn("✗ fish              Tide variables changed: tide_pwd_bg_color", output)
```

with:

```python
        self.assertIn("✗ fish              prompt variables changed: tide_pwd_bg_color", output)
```

Replace the whole `test_fish_that_does_not_answer_is_a_warning` with it and the new doctor tests:

```python
    def test_fish_that_does_not_answer_is_a_warning(self):
        runner.install(self.ctx())
        code, output = self.doctor(run=fake_fish(missing=True))
        self.assertEqual(code, 0)
        self.assertIn("⚠ fish              cannot check the Tide variables: could not read fisher and Tide", output)

    def test_every_variable_is_checked_not_only_the_recorded_ones(self):
        older = {name: DESIRED[name] for name in USER_TIDE}  # an older witchy recorded only these
        with mock.patch.object(fish, "desired", return_value=older):
            runner.install(self.ctx())
        code, output = self.doctor()
        self.assertEqual(code, 1)
        self.assertIn("✗ fish              prompt variables changed: fish_emoji_width, tide_aws_bg_color, "
                      "tide_aws_color, tide_aws_icon, tide_character_color, tide_character_color_failure, "
                      "tide_character_icon, tide_character_vi_icon_default, tide_character_vi_icon_replace, "
                      "tide_character_vi_icon_visual (and 145 more)\n", output)

    def test_tide_configure_afterwards_is_drift(self):
        runner.install(self.ctx())
        for name, value in (("tide_pwd_icon", [""]), ("tide_left_prompt_items", ["pwd", "git", "newline"]),
                            ("tide_prompt_transient_enabled", ["false"])):
            self.variables[name]["value"] = value
        code, output = self.doctor()
        self.assertEqual(code, 1)
        self.assertIn("✗ fish              prompt variables changed: tide_left_prompt_items, "
                      "tide_prompt_transient_enabled, tide_pwd_icon\n", output)

    def test_a_tide_variable_tide_does_not_define_fails(self):
        runner.install(self.ctx())
        self.variables["tide_sparkle_icon"] = {"value": ["✨"], "exported": False}
        self.variables["_tide_private"] = {"value": ["x"], "exported": False}
        code, output = self.doctor()
        self.assertEqual(code, 1)
        self.assertIn("✗ fish              not Tide 6.1.1 variables: tide_sparkle_icon\n"
                      "    fix: python3 -m witchy install --only fish", output)
        self.assertNotIn("_tide_private", output)

    def test_a_global_hiding_a_universal_fails(self):
        runner.install(self.ctx())
        run = fake_fish(self.variables, globals={"tide_pwd_bg_color": ["000000"], "fish_emoji_width": ["1"]})
        code, output = self.doctor(run=run)
        self.assertEqual(code, 1)
        self.assertIn("✗ fish              fish_emoji_width is overridden by a global in config.fish or conf.d\n"
                      "    fix: python3 -m witchy install --only tide\n"
                      "✗ fish              tide_pwd_bg_color is overridden by a global in config.fish or conf.d\n",
                      output)
        self.assertIn(f"✓ fish              {len(DESIRED)} prompt variables match", output)

    def test_the_new_shell_is_interactive_quiet_and_has_15_seconds(self):
        runner.install(self.ctx())
        seen = []
        answers = fake_fish(self.variables)

        def run(args, **kwargs):
            seen.append((args, kwargs["env"].get("WITCHY_DOCTOR"), kwargs["timeout"], kwargs["input"]))
            return answers(args, **kwargs)

        self.doctor(run=run)
        self.assertIn((["fish", "-i", "-c", fish.GLOBALS_SCRIPT, "--", *DESIRED], "1", 15, b""), seen)

    def test_a_new_shell_that_does_not_answer_is_a_warning(self):
        runner.install(self.ctx())
        answers = fake_fish(self.variables)

        def run(args, **kwargs):
            if args[:2] == ["fish", "-i"]:
                raise subprocess.TimeoutExpired(args, kwargs["timeout"])
            return answers(args, **kwargs)

        code, output = self.doctor(run=run)
        self.assertEqual(code, 0)
        self.assertIn("⚠ fish              cannot check the Tide variables: could not read the prompt variables a "
                      "new shell sees (timed out after 15 s)", output)

    def test_tide_not_ready_is_one_warning(self):
        runner.install(self.ctx())
        code, output = self.doctor(run=fake_fish(self.variables, tide="6.0.0"))
        self.assertEqual(code, 0)
        self.assertIn("⚠ fish              Tide variables not checked: Tide is 6.0.0, not 6.1.1\n"
                      "    fix: python3 -m witchy install --only tide", output)
        self.assertNotIn("prompt variables", output)

    def test_the_installed_variant_is_the_one_checked(self):
        midnight = palette.VARIANTS["midnight"]
        dawn = palette.Variant(**{**midnight.__dict__, "name": "dawn",
                                  "tide": dict(midnight.tide, tide_pwd_bg_color="D0B8FF")})
        with mock.patch.dict(palette.VARIANTS, {"dawn": dawn}):
            ctx = self.ctx()
            ctx.variant = "dawn"
            self.assertEqual(runner.install(ctx), 0)
            code, output = self.doctor()
        self.assertEqual(code, 0, output)
        self.assertIn(f"✓ fish              {len(DESIRED)} prompt variables match", output)
```

In `tests/test_fish_files.py`, in `GreetingTest.test_quiet_unless_every_condition_holds`, replace:

```python
                 "VS Code": ({**self.WT, "TERM_PROGRAM": "vscode"}, True)}
```

with:

```python
                 "VS Code": ({**self.WT, "TERM_PROGRAM": "vscode"}, True),
                 "doctor's shell": ({**self.WT, "WITCHY_DOCTOR": "1"}, True)}
```

After that test, add:

```python
    def test_the_doctors_new_shell_never_greets(self):
        # doctor reads the prompt variables with `fish -i -c`, which must stay silent (spec 9.1).
        done = self.fish("true", interactive=True, env={**self.WT, "WITCHY_DOCTOR": "1"})
        self.assertEqual((done.stdout, done.stderr), ("", ""))
        self.assertIsNone(self.python_args())

```

In `SkyJobStartTest`, before `test_needs_an_interactive_windows_terminal_shell_and_the_config`, add:

```python
    def test_the_doctors_new_shell_never_starts_the_job(self):
        self.assertTrue(self.sky_job_started())  # the control: a normal shell starts it
        self.wait_for_python()
        done = self.start_shell({"fish_trace": "1", "WITCHY_DOCTOR": "1"})
        self.assertTrue(any(re.search(r"source .*conf\.d/witchy\.fish$", line) for line in done.stderr.splitlines()))
        self.assertFalse(any(re.search(r"^-+> .*/ritual'? --sky$", line) for line in done.stderr.splitlines()))

```

In `tests/test_fish_integration.py`, before `test_snapshot_reads_values_with_spaces_and_empty_lists`, add (its `config.fish` already sets `set -g tide_pwd_bg_color 000000` outside any interactive guard; the new `conf.d` file sets a global only in interactive shells):

```python
    def test_doctor_sees_globals_that_only_a_new_interactive_shell_sets(self):
        self.assertEqual(runner.install(self.ctx("20261003-120000")), 0, self.out.getvalue())
        (self.config / "conf.d").mkdir(exist_ok=True)
        (self.config / "conf.d" / "mine.fish").write_text(
            "status is-interactive; or exit\nset -g tide_time_color 5F8787\n", encoding="utf-8")
        ctx = self.ctx("20261003-130000")
        self.assertEqual(runner.doctor(ctx, [fish.FishComponent()]), 1)
        output = self.out.getvalue()
        self.assertIn(f"✓ fish              {len(build.tide()) + 1} prompt variables match", output)
        self.assertIn("✗ fish              tide_pwd_bg_color is overridden by a global in config.fish or conf.d", output)
        self.assertIn("✗ fish              tide_time_color is overridden by a global in config.fish or conf.d", output)
        self.assertNotIn("hello from config.fish", output)

```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_base tests.test_components_fish tests.test_fish_files tests.test_fish_integration`
Expected: `Ran 118 tests` and `FAILED (failures=3, errors=53)`. `fake_fish` now refers to `fish.GLOBALS_SCRIPT` on every call, so almost every fake-fish test errors with `AttributeError: module 'witchy.components.fish' has no attribute 'GLOBALS_SCRIPT'`; also `TypeError: Command.__init__() got an unexpected keyword argument 'env'`, the greeting runs for `doctor's shell` (`('python ran\n', '') != ('', '')`), the doctor's shell starts the sky job (`True is not false`), and the real-fish doctor exits 0 (`0 != 1`).

- [ ] **Step 3: Commands can add environment variables**

In `witchy/components/base.py`, in `class Command`, replace:

```python
    translation, so every byte comes back as it was (a fish value can hold any byte but NUL). ``timeout`` is in
    seconds.
    """

    args: tuple[str, ...]
    label: str
    input: str | None = None
    exact: bool = False
    timeout: float = COMMAND_TIMEOUT
```

with:

```python
    translation, so every byte comes back as it was (a fish value can hold any byte but NUL). ``timeout`` is in
    seconds; ``env`` is added to ``ctx.env``.
    """

    args: tuple[str, ...]
    label: str
    input: str | None = None
    exact: bool = False
    timeout: float = COMMAND_TIMEOUT
    env: dict[str, str] = field(default_factory=dict)
```

In `run_command`, replace:

```python
                       env=dict(ctx.env), **text)
```

with:

```python
                       env={**ctx.env, **command.env}, **text)
```

- [ ] **Step 4: The new shell stays quiet**

In `content/fish/conf.d/witchy.fish`, replace:

```fish
status is-interactive; or exit
```

with:

```fish
status is-interactive; or exit
set -q WITCHY_DOCTOR; and exit  # doctor's new shell reads the prompt variables and must start nothing
```

In `content/fish/functions/fish_greeting.fish`, replace:

```fish
    for name in TMUX CLAUDECODE WITCHY_RITUAL_SHOWN
```

with:

```fish
    for name in TMUX CLAUDECODE WITCHY_RITUAL_SHOWN WITCHY_DOCTOR
```

- [ ] **Step 5: doctor reads the new shell and compares every variable**

In `witchy/components/fish.py`, replace:

```python
MESSAGE_MAX = 100
```

with:

```python
MESSAGE_MAX = 100
SHOWN_MAX = 10  # drifted names listed by doctor
SHELL_TIMEOUT = 15  # seconds for doctor's new interactive shell, which runs the user's whole config (spec 9.1)
```

Before the comment `# Reads records from standard input (name, mode, element count, elements; …` (above `SET_SCRIPT`), add:

```python
# Run by a new interactive shell, the way a new tab starts one: prints each name that has a global value (set
# by config.fish or conf.d, so it hides the universal one), its element count and its elements.
GLOBALS_SCRIPT = """\
printf '%s\\0' witchy-fish
for name in $argv
    if set -q -g $name
        printf '%s\\0' $name (count $$name) $$name
    end
end
"""

```

Before `def set_command(`, add:

```python
def shadows(ctx: Any, names: list[str]) -> dict[str, list[str]]:
    """The ``names`` a new interactive shell holds as globals, with their values.

    WITCHY_DOCTOR makes conf.d/witchy.fish skip the sky job and fish_greeting stay quiet; standard input is
    empty, so nothing waits for a key.
    """
    done = run_command(ctx, Command((FISH, "-i", "-c", GLOBALS_SCRIPT, "--", *names),
                                    "read the prompt variables a new shell sees", "", exact=True,
                                    timeout=SHELL_TIMEOUT, env={"WITCHY_DOCTOR": "1"}))
    try:
        fields = fishprobe.fields(done.stdout)
        found, index = {}, 0
        while index < len(fields):
            count = int(fields[index + 1])
            found[fields[index]] = fields[index + 2:index + 2 + count]
            index += 2 + count
        return found
    except (ValueError, IndexError) as exc:
        raise ComponentFailed(f"could not read the prompt variables a new shell sees ({exc})") from exc


```

In `FishComponent`, before `def check(`, add:

```python
    def _prompt_checks(self, ctx: Any) -> list[Check]:
        """Every variable against the spec, not only the recorded ones (spec 9.1): drift, tide_ variables Tide
        does not define, and globals that hide a universal value in a new shell."""
        fix = fix_command(self.name)
        wanted = desired(ctx.variant or palette.DEFAULT_VARIANT)
        try:
            reason = fishprobe.tide_ready(fishprobe.probe(ctx))
            if reason:
                return [Check("warn", self.name, f"Tide variables not checked: {reason}", fix_command("tide"))]
            current = snapshot(ctx, list(wanted))
            hidden = shadows(ctx, list(wanted))
        except ComponentFailed as exc:
            return [Check("warn", self.name, f"cannot check the Tide variables: {exc}")]
        drift = sorted(name for name, values in wanted.items() if current[name].get("value") != values)
        more = f" (and {len(drift) - SHOWN_MAX} more)" if len(drift) > SHOWN_MAX else ""
        checks = [Check("fail", self.name, "prompt variables changed: " + ", ".join(drift[:SHOWN_MAX]) + more, fix)
                  if drift else Check("ok", self.name, f"{len(wanted)} prompt variables match")]
        strays = sorted(current.keys() - wanted.keys())
        if strays:
            checks.append(Check("fail", self.name, "not Tide 6.1.1 variables: " + ", ".join(strays), fix))
        # The tide component disables `set -g tide_…` lines in config.fish and conf.d.
        checks += [Check("fail", self.name, f"{name} is overridden by a global in config.fish or conf.d",
                         fix_command("tide")) for name in sorted(hidden)]
        return checks

```

In `check`, replace:

```python
        variables = entry.get("variables") or {}
        if variables:
            try:
                current = snapshot(ctx, list(variables))
            except ComponentFailed as exc:
                checks.append(Check("warn", self.name, f"cannot check the Tide variables: {exc}"))
            else:
                drift = [name for name, record in variables.items() if current[name].get("value") != record["installed"]]
                checks.append(Check("fail", self.name, "Tide variables changed: " + ", ".join(drift), fix) if drift
                              else Check("ok", self.name, f"{len(variables)} Tide variables match"))
```

with:

```python
        checks += self._prompt_checks(ctx)
```

In `witchy/runner.py`, in `doctor`, replace:

```python
    entries = (state or {}).get("components", {})
    checks: list[Check] = []
```

with:

```python
    entries = (state or {}).get("components", {})
    ctx.variant = ctx.variant or (state or {}).get("variant")  # fish compares the prompt with this variant's
    checks: list[Check] = []
```

- [ ] **Step 6: The specs**

In `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md`, section 9.1, replace:

```
- The snapshot no longer erases globals. It reads each name twice: the universal value and the value a fresh interactive shell sees (`fish -i -c` with `WITCHY_DOCTOR=1` set, which makes `conf.d/witchy.fish` skip the greeting and the sky job). A global hiding a universal is ✗ `tide_X is overridden by a global in config.fish or conf.d`.
- ✓/✗ every `tide_*` in the spec matches (all 161, not 31); ✗ lists the names that drifted, fix `python3 -m witchy install --only fish`.
- ✗ any universal `tide_*` not in Tide 6.1.1's list.
```

with:

```
- A global no longer passes as ✓. The snapshot still reads the universal value by erasing globals inside its own `fish -c` process (the one exact way fish 3.7 offers), and doctor reads each name a second time in a fresh interactive shell (`fish -i -c` with `WITCHY_DOCTOR=1` set, which makes `conf.d/witchy.fish` skip the sky job and `fish_greeting` stay quiet; empty standard input, 15 s timeout). A global hiding a universal is ✗ `tide_X is overridden by a global in config.fish or conf.d`, fix `python3 -m witchy install --only tide`.
- ✓/✗ every variable in the spec matches (all 158 and `fish_emoji_width`, not 31), whatever an older install recorded; ✗ lists the names that drifted (the first 10, then a count), fix `python3 -m witchy install --only fish`.
- ✗ any universal `tide_*` not in Tide 6.1.1's list.
- When Tide is not ready, these three are replaced by one ⚠ `Tide variables not checked: <reason>`, fix `python3 -m witchy install --only tide` (the `tide` check carries the ✗).
```

Section 12, replace:

```
- `test_components_fish.py`: the global-shadow check, the 161-name drift check, skip when `tide` did not end `ok`.
```

with:

```
- `test_components_fish.py`: the global-shadow check, the drift check over all 158 names and `fish_emoji_width`, skip when `tide` did not end `ok`.
```

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md`, section 5.3, replace:

```
- Every `fish` call uses list arguments and a 5 s timeout through the injectable `ctx.run`.
```

with:

```
- Every `fish` call uses list arguments and a 5 s timeout through the injectable `ctx.run` (doctor's read in a new interactive shell gets 15 s; prompt-takeover spec 9.1).
```

- [ ] **Step 7: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 638 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 8: Commit**

```bash
git add witchy/components/base.py witchy/components/fish.py witchy/runner.py content/fish/conf.d/witchy.fish content/fish/functions/fish_greeting.fish tests/fakes.py tests/test_base.py tests/test_components_fish.py tests/test_fish_files.py tests/test_fish_integration.py docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "feat: doctor checks every prompt variable, unknown tide_ ones and globals a new shell sets" -m "The fish check compares all of build.tide and fish_emoji_width with the spec, fails on tide_ variables Tide 6.1.1 does not define, and reads globals in a fresh interactive shell (WITCHY_DOCTOR=1, 15 s, empty stdin) that starts no sky job and no greeting. Commands can add environment variables; doctor checks the installed variant." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: End-to-end check with the Tide v6.1.1 release in a temporary HOME

**Items:** the whole plan, against the real Tide 6.1.1 release (its `functions/`, `conf.d/` and `completions/`, the files fisher installs), copied into a throwaway HOME the way fisher lays them out. Nothing under the real `~/.config/fish`, `~/.claude` or `~/.cache` is read or written, and no real universal variable changes.

**Files:** none changed.

**Interfaces:**
- Consumes: the whole branch; the release tree unpacked in Task 2 Step 4 (`$TIDE_SRC/tide-6.1.1`).
- Produces: nothing new.

- [ ] **Step 1: Build a throwaway HOME with the release, recorded as fisher records a tagged install**

```bash
R=$TIDE_SRC/tide-6.1.1   # or unpack it again as in Task 2 Step 4
T=$(mktemp -d)
mkdir -p $T/.config/fish
cp -r $R/functions $R/conf.d $R/completions $T/.config/fish/
E="env -i HOME=$T XDG_CONFIG_HOME=$T/.config PATH=/usr/bin:/bin TERM=xterm-256color LANG=C.UTF-8"
$E fish -c 'set -U _fisher_plugins ilancosman/tide@v6.1.1
set -U _fisher_(string escape --style=var -- ilancosman/tide@v6.1.1)_files (string replace -- $HOME \~ $HOME/.config/fish/{functions,conf.d,completions}/**.fish)
set -U tide_pwd_bg_color FFB7C5
set -U tide_sparkle_icon ✨'
```

- [ ] **Step 2: Dry run, install, doctor**

```bash
$E python3 -m witchy install --only fish --dry-run | tail -4
$E python3 -m witchy install --only fish | tail -4; echo "exit=$?"
$E python3 -m witchy doctor | grep fish
```

Expected (seen on the prototype):
```
fish: set -U tide_moon_color FFD477 (now: unset)
fish: set -U fish_emoji_width 2 (now: unset)
fish: set -e -U tide_sparkle_icon (now: ✨)
Dry run: nothing was written.
1/1 components installed
Moonlit Candle installed. Undo with: python3 -m witchy uninstall
Open a new terminal tab to see the new prompt and greeting; open shells keep the old ones.
The output style applies from your next message; restart Claude Code if the theme or status line do not update.
exit=0
✓ fish              20 files match
✓ fish              159 prompt variables match
✓ fish              eza found          (⚠ eza missing … when eza is not installed)
✓ fish              no greeting or sky errors in the last 7 days
```

- [ ] **Step 3: Drift, a stray and a global show up**

```bash
echo "set -g tide_time_color 5F8787" >> $T/.config/fish/config.fish
$E fish -c 'set -U tide_pwd_icon ""; set -U tide_bogus x'
$E python3 -m witchy doctor | grep -A1 "✗"; echo "exit=${PIPESTATUS[0]}"
```

Expected:
```
✗ fish              prompt variables changed: tide_pwd_icon
    fix: python3 -m witchy install --only fish
✗ fish              not Tide 6.1.1 variables: tide_bogus
    fix: python3 -m witchy install --only fish
✗ fish              tide_time_color is overridden by a global in config.fish or conf.d
    fix: python3 -m witchy install --only tide
exit=1
```

- [ ] **Step 4: Tide draws the slanted prompt with the moon**

```bash
sed -i '$d' $T/.config/fish/config.fish
$E COLUMNS=100 fish -i -c 'set -U tide_pwd_icon 🧹; set -e -U tide_bogus; _tide_remove_unusable_items; _tide_cache_variables; set -g _tide_side left; _tide_2_line_prompt' </dev/null 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | head -1 | cat -A
```

Expected (run from the repo, so the git item shows): a line like
```
^[(B^[(BM-nM-^BM-: M-pM-^_M-^LM-^X M-nM-^BM-< @PWD@ M-nM-^BM-< M-pM-^_M-^LM-? <branch> ^[(B^[(BM-nM-^BM-<$
```
that is U+E0BA (Slanted tail), the moon of the day (🌘 here), U+E0BC (Slanted separator), Tide's pwd placeholder, U+E0BC, 🌿 and the branch, U+E0BC. (Errors from the character item about `$_tide_status` go to the discarded stderr: there is no real prompt.)

- [ ] **Step 5: Uninstall gives the user's values back, then clean up**

```bash
$E python3 -m witchy uninstall | tail -2; echo "exit=$?"
$E fish -c 'printf "%s\n" $tide_pwd_bg_color $tide_sparkle_icon; set -q fish_emoji_width; or echo "no emoji width"'
rm -rf $T "$TIDE_SRC"
```

Expected: `Moonlit Candle uninstalled.`, `exit=0`, then `FFB7C5`, `✨`, `no emoji width`.

No commit: this task changes no files.
