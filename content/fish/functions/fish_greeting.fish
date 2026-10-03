# Moonlit Candle (witchy): the greeting, on top-level Windows Terminal shells only (spec 6.2).
function fish_greeting --description 'Moonlit Candle greeting'
    status is-interactive; or return
    set -q WT_SESSION; or return
    for name in TMUX CLAUDECODE WITCHY_RITUAL_SHOWN
        set -q $name; and return
    end
    test "$TERM_PROGRAM" = vscode; and return
    # Exported, so nested shells and everything they start stay quiet.
    set -gx WITCHY_RITUAL_SHOWN 1
    test -x @PYTHON@; and test -f @WITCHY_DIR@/ritual/__main__.py; or return
    env FISH_VERSION=$FISH_VERSION @PYTHON@ -I -B @WITCHY_DIR@/ritual 2>/dev/null
end
