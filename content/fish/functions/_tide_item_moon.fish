# Moonlit Candle (witchy): the Tide prompt item "moon", today's phase. Tide renders items asynchronously,
# so working it out on every prompt costs nothing visible and a shell left open for days stays right.
function _tide_item_moon
    set -l glyphs 🌑 🌒 🌓 🌔 🌕 🌖 🌗 🌘
    _tide_print_item moon $glyphs[(math (_witchy_moon_bin) + 1)]
end
