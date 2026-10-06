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
