# Moonlit Candle (witchy): eza colours, and the sky job that keeps the Windows Terminal moon on tonight's
# phase (spec 4.5, 7). The job starts only when the phase bin differs from the last one it set, and at
# most once a day after a failure.
set -gx EZA_COLORS @EZA_COLORS@

status is-interactive; or exit
set -q WT_SESSION; or exit
test -f @WITCHY_DIR@/ritual-config.json; and test -x @PYTHON@; or exit

set -l cache $HOME/.cache/witchy
set -l stamp
test -r $cache/sky-bin; and read stamp <$cache/sky-bin
test "$stamp" = (_witchy_moon_bin); and exit
set -l failed
test -r $cache/sky-fail; and read failed <$cache/sky-fail
test "$failed" = (date +%F); and exit
@PYTHON@ -I -B @WITCHY_DIR@/ritual --sky >/dev/null 2>&1 &
disown
