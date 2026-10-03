# Moonlit Candle (witchy): the moon phase bin, 0 (new) to 7 (waning crescent), as ritual/moon.py computes it:
# days since the new moon of 2000-01-06 18:14 UTC (Unix time 947182440), modulo 29.530588853, in eighths
# centred on each phase. An optional argument gives the time in Unix seconds instead of now.
function _witchy_moon_bin --description 'Moon phase bin, 0-7'
    set -l now $argv[1]
    set -q now[1]; or set now (date +%s)
    math "floor(((($now - 947182440) / 86400) % 29.530588853) / 29.530588853 * 8 + 0.5) % 8"
end
