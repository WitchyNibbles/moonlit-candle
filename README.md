# Moonlit Candle

Tema para Claude Code inspirado en [WitchyNibbles/Spellbound-Themes](https://github.com/WitchyNibbles/Spellbound-Themes): fondo berenjena de Moonlit, acento oro de vela y rosa para los permisos.

Incluye:

- Tema `moonlit-candle` para Claude Code (`~/.claude/themes/`)
- Esquema "Moonlit Candle" para el perfil WSL de Windows Terminal
- Verbos y tips del spinner (`spinnerVerbs`, `spinnerTipsOverride`)
- Output style "WitchyNibbles", que solo cambia el tono de las respuestas en el chat
- Status line con fases lunares según el contexto usado, límites de 5 h / 7 d y git

## Uso

```sh
/usr/bin/python3 -m witchy validate           # contraste, tokens y contenido
/usr/bin/python3 -m witchy install --dry-run  # muestra los cambios sin escribir
/usr/bin/python3 -m witchy install
/usr/bin/python3 -m witchy uninstall
```

`install` hace una copia `*.bak-witchy-<fecha>` de cada fichero que modifica y guarda los valores anteriores en `~/.claude/witchy/state.json`. `uninstall` los restaura. Un `settings.json` que no sea JSON estricto (comentarios, comas finales) nunca se reescribe. En el de Windows Terminal se muestra el fragmento para añadirlo a mano y el resto de la instalación sigue; en `~/.claude/settings.json` la instalación se aborta sin cambiar nada.

Después de instalar, reinicia Claude Code.

## Desarrollo

```sh
/usr/bin/python3 -m unittest discover -s tests -t . -v
/usr/bin/python3.10 -m unittest discover -s tests -t .
```

Los colores están en `witchy/palette.py`. El diseño está en `docs/superpowers/specs/2026-09-30-moonlit-candle-design.md`.
