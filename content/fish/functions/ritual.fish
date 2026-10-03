# Moonlit Candle (witchy): the full ritual on demand, anywhere; `ritual --date 2026-10-31` previews a day.
function ritual --description 'Moonlit Candle: show the full ritual'
    env FISH_VERSION=$FISH_VERSION @PYTHON@ -I -B @WITCHY_DIR@/ritual --full $argv
end
