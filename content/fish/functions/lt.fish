# Moonlit Candle (witchy): a two-level tree through eza, or ls -R without it (spec 7).
function lt --description 'Tree of a folder, two levels deep (eza)'
    if command -q eza
        eza --tree --level=2 --icons $argv
    else
        ls -R $argv
    end
end
