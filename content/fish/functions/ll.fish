# Moonlit Candle (witchy): a long listing through eza, or ls without it (spec 7).
function ll --description 'List all files in long format (eza)'
    if command -q eza
        eza -la --icons --group-directories-first --git $argv
    else
        ls -la $argv
    end
end
