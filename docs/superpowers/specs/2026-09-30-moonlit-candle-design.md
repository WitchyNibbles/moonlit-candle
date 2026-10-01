# Moonlit Candle: tema brujil para Claude Code

- **Fecha:** 2026-09-30
- **Estado:** diseño aprobado en conversación, pendiente de revisar esta spec
- **Uso:** personal (Manuel, WSL Ubuntu dentro de Windows Terminal, Claude Code 2.1.285)
- **Inspiración:** repos de [WitchyNibbles](https://github.com/WitchyNibbles), sobre todo `Spellbound-Themes` (paleta Moonlit) y `devgod`/`archon` (vela, luna dorada, "keep the receipts")

## 1. Objetivo

Conseguir que Claude Code, en el terminal del usuario, tenga la estética "Moonlit con llama de vela":

- la noche berenjena de Spellbound Moonlit,
- el oro de vela como acento principal de Claude,
- el rosa neón reservado a permisos y "accept edits",
- la lavanda para plan mode y memoria.

El mismo tema cubre colores, fondo del terminal, spinner, status line y la voz con la que Claude responde en el chat.

**Criterio de éxito:** tras `python3 -m witchy install` y un reinicio de Claude Code, la sesión se ve como la maqueta aprobada (sección 4) y `python3 -m witchy uninstall` deja todo exactamente como estaba.

## 2. Alcance

Dentro:

1. Tema de Claude Code `moonlit-candle` (una sola variante oscura).
2. Esquema de color "Moonlit Candle" para Windows Terminal, aplicado **solo** al perfil desde el que se ejecuta el instalador (Ubuntu/WSL).
3. Verbos del spinner (`spinnerVerbs`, en inglés, modo `replace`).
4. Tips del spinner (`spinnerTipsOverride`, en inglés, etiqueta `Grimoire`, junto a los tips normales).
5. Output style "WitchyNibbles": voz nivel B, **solo en lo que Claude escribe en el chat**.
6. Status line propio con fases lunares y git; sustituye al de `archon` y se restaura al desinstalar.
7. Instalador y desinstalador idempotentes, con copias de seguridad.

Fuera:

- Variantes clara y de alto contraste.
- Empaquetar como plugin de Claude Code. Los plugins no pueden instalar `settings.json` ni el esquema de Windows Terminal, y los temas en plugins son `experimental`.
- Tocar el paquete `archon` instalado.
- Windows Terminal Preview o instalaciones sin paquete: solo se admite la ruta estándar o la que se pase por `--wt-settings`.
- Una vista previa HTML generada.

## 3. Arquitectura

Una sola paleta en Python genera todo. Solo se usa la librería estándar, sin dependencias, y el código debe funcionar con **Python 3.10** o superior (el `/usr/bin/python3` del sistema es 3.12.3 y también existe `/usr/bin/python3.10`; los tests se pasan con los dos).

```
~/proyectos/witchy-claude-theme/
├── witchy/
│   ├── __init__.py
│   ├── __main__.py        CLI (argparse): build | validate | install [--dry-run] [--wt-settings PATH] | uninstall [--dry-run]
│   ├── palette.py         colores base, mapa token→color de Claude Code y esquema ANSI de Windows Terminal
│   ├── tokens.py          lista cerrada de tokens válidos según la documentación oficial
│   ├── contrast.py        luminancia y ratio de contraste WCAG 2.x
│   ├── validate.py        reglas de la sección 6; devuelve la lista de fallos
│   ├── build.py           genera dist/ a partir de palette.py y content/
│   ├── jsonio.py          leer JSON estricto, copia con fecha, escritura atómica (temporal + os.replace)
│   ├── claude_settings.py fusiona y restaura las claves de ~/.claude/settings.json
│   ├── wt.py              localiza, parchea y restaura el settings.json de Windows Terminal
│   ├── install.py         orquesta install y uninstall, y mantiene state.json
│   └── statusline.py      status line autónomo (solo stdlib, no importa witchy); build sustituye su bloque de paleta
├── content/
│   ├── spinner.json       {"verbs": [...], "tips": [{"id": ..., "text": ...}, ...]}
│   └── output-style.md    output style "WitchyNibbles" (texto de la sección 8.3)
├── tests/                 unittest
├── dist/                  (gitignored) salida de build
├── docs/superpowers/specs/
└── README.md
```

### 3.1 Salida de `build` (`dist/`)

| Fichero | Destino al instalar |
| :- | :- |
| `dist/claude/themes/moonlit-candle.json` | `~/.claude/themes/moonlit-candle.json` |
| `dist/claude/output-styles/witchynibbles.md` | `~/.claude/output-styles/witchynibbles.md` |
| `dist/claude/witchy/statusline.py` | `~/.claude/witchy/statusline.py` |
| `dist/claude/witchy/tips.json` | `~/.claude/witchy/tips.json` |
| `dist/windows-terminal/moonlit-candle.scheme.json` | se inserta en `schemes` del `settings.json` de Windows Terminal |

**Status line.** `witchy/statusline.py` contiene un bloque delimitado por `# BEGIN PALETTE` y `# END PALETTE` con un dict literal de colores. `build` lo reescribe con los valores de `palette.py`. Los valores por defecto de ese bloque en el código fuente deben coincidir con `palette.py`; hay un test que lo comprueba, así que el fichero funciona igual sin pasar por `build`.

**Tema JSON.** Formato oficial (`name`, `base`, `overrides`):

```json
{ "name": "Moonlit Candle", "base": "dark", "overrides": { "claude": "#FFD477", "...": "..." } }
```

## 4. Paleta

Fondo del terminal `#0D0916`, texto `#F3EAF7`. Todos los valores van en `#RRGGBB` en mayúsculas.

### 4.1 Tokens de Claude Code

**Acentos y texto**

| Token | Color | | Token | Color |
| :- | :- | :- | :- | :- |
| `claude` | `#FFD477` (vela) | | `claudeShimmer` | `#FFF1C9` |
| `text` | `#F3EAF7` (marfil) | | `inverseText` | `#0D0916` |
| `inactive` | `#A99AB9` | | `inactiveShimmer` | `#CFC3DB` |
| `subtle` | `#6E5A80` | | `suggestion` | `#B99AFF` (lavanda) |
| `permission` | `#FF67B7` (rosa) | | `permissionShimmer` | `#FFB3DA` |
| `remember` | `#B99AFF` | | | |

**Estados y modos**

| Token | Color | | Token | Color |
| :- | :- | :- | :- | :- |
| `success` | `#74E8B8` (menta) | | `error` | `#FF6B9F` |
| `warning` | `#FFB86B` (ámbar) | | `warningShimmer` | `#FFD6A3` |
| `merged` | `#B99AFF` | | `promptBorder` | `#6E5A80` ⚠️ ver nota |
| `promptBorderShimmer` | `#9A82B0` | | `planMode` | `#B99AFF` |
| `autoAccept` | `#FF67B7` | | `bashBorder` | `#77D9FF` (cian) |
| `ide` | `#77D9FF` | | `fastMode` | `#FF9BD7` |
| `fastModeShimmer` | `#FFC8E9` | | `effortUltra` | `#FFD477` |

> ⚠️ **Cambio respecto a la maqueta.** La maqueta aprobada tenía `promptBorder` en `#503762`, que da 1.93:1 sobre el fondo y no cumple la regla de 3:1 para bordes, también aprobada. Se sube a `#6E5A80` (3.22:1), el mismo tono que `subtle`.

**Diffs y fondos** (opacos)

| Token | Color | | Token | Color |
| :- | :- | :- | :- | :- |
| `diffAdded` | `#153042` | | `diffAddedWord` | `#1C4F65` |
| `diffRemoved` | `#441632` | | `diffRemovedWord` | `#712049` |
| `diffAddedDimmed` | `#111D2A` | | `diffRemovedDimmed` | `#2A1022` |
| `userMessageBackground` | `#1D1230` | | `userMessageBackgroundHover` | `#271A3D` |
| `memoryBackgroundColor` | `#1A1433` | | `bashMessageBackgroundColor` | `#0F1E28` |
| `selectionBg` | `#633B79` | | | |

**Medidor de uso y etiquetas**

| Token | Color | | Token | Color |
| :- | :- | :- | :- | :- |
| `rate_limit_fill` | `#FFD477` | | `rate_limit_empty` | `#38234D` (decorativo) |
| `briefLabelYou` | `#77D9FF` | | `briefLabelClaude` | `#FFD477` |

**Subagentes** (`<color>_FOR_SUBAGENTS_ONLY`)

| red | blue | green | yellow | purple | orange | pink | cyan |
| :- | :- | :- | :- | :- | :- | :- | :- |
| `#FF6B9F` | `#7FA6FF` | `#74E8B8` | `#FFD477` | `#B99AFF` | `#FFB86B` | `#FF67B7` | `#74E0E8` |

**Arcoíris de `ultrathink`** (`rainbow_<color>` / `rainbow_<color>_shimmer`)

| | red | orange | yellow | green | blue | indigo | violet |
| :- | :- | :- | :- | :- | :- | :- | :- |
| base | `#FF6B9F` | `#FFB86B` | `#FFD477` | `#74E8B8` | `#77D9FF` | `#9C8CFF` | `#D59BFF` |
| shimmer | `#FFA3C2` | `#FFD3A3` | `#FFE7B3` | `#A8F2D4` | `#B0E9FF` | `#C4BAFF` | `#E8C7FF` |

### 4.2 Esquema de Windows Terminal "Moonlit Candle"

```json
{
  "name": "Moonlit Candle",
  "background": "#0D0916", "foreground": "#F3EAF7",
  "cursorColor": "#FF67B7", "selectionBackground": "#633B79",
  "black": "#1D1230",  "red": "#FF6B9F",  "green": "#74E8B8",  "yellow": "#FFD477",
  "blue": "#77D9FF",   "purple": "#B99AFF", "cyan": "#74D7E8", "white": "#E6DCEE",
  "brightBlack": "#6E5A80", "brightRed": "#FF8FB5", "brightGreen": "#9DF2CE", "brightYellow": "#FFE3A3",
  "brightBlue": "#A3E6FF",  "brightPurple": "#D0B8FF", "brightCyan": "#A0E9F2", "brightWhite": "#FFFFFF"
}
```

### 4.3 Colores del status line

| Uso | Color |
| :- | :- |
| modelo (negrita) | `#FFD477` |
| effort, etiquetas `5h`/`7d` | `#A99AB9` |
| separador `⋆` (decorativo) | `#503762` |
| repo `📜 nombre` | `#B99AFF` |
| rama `⎇ nombre` | `#77D9FF` |
| `✦N` sin commitear | `#FF67B7` |
| % de contexto < 50 / 50–79 / ≥ 80 (negrita) | `#FFD477` / `#FF67B7` / `#FF6B9F` |
| % restante > 50 / 21–50 / ≤ 20 (negrita) | `#FFD477` / `#B99AFF` / `#FF67B7` |

## 5. Status line

Formato (una sola línea, con un espacio al principio y otro al final, como archon):

```
 🕯️ Opus 5.5·xhigh ⋆ 🌓 48% ⋆ 5h 71% ⋆ 7d 88% ⋆ 📜 GII_claude_2 ⎇ bugfix/INC-98560✦2
```

Datos de entrada (campos del JSON que Claude Code envía por stdin, según la [documentación oficial](https://code.claude.com/docs/en/statusline)):

| Segmento | Campo | Regla |
| :- | :- | :- |
| Modelo | `model.display_name` | Se quita el sufijo entre paréntesis (`Opus 5.5 (1M context)` → `Opus 5.5`). Si falta: `--` |
| Effort | `effort.level` | `·<level>` si existe; si no, se omite |
| Luna | `context_window.used_percentage` | 🌑 0–12, 🌒 13–37, 🌓 38–62, 🌔 63–87, 🌕 88–100 (se redondea antes de clasificar). `null` o sin datos: `🌑 --` |
| 5h / 7d | `rate_limits.five_hour.used_percentage`, `rate_limits.seven_day.used_percentage` | Muestra el **restante**: `round(100 - used)`. Si falta (por ejemplo con API key, sin suscripción): `--` en `#A99AB9` |
| Repo | `git rev-parse --show-toplevel` en `workspace.current_dir` (si no, `cwd`) | Nombre de la carpeta raíz del repo |
| Rama | `git branch --show-current` | Si pasa de 28 caracteres, se corta a 27 y se añade `…`. Con HEAD separado: hash corto `git rev-parse --short HEAD` |
| `✦N` | `git status --porcelain` | N = número de líneas; se omite si N = 0 |

Reglas:

- **Nunca falla.** Un JSON inválido, campos que faltan o de tipo incorrecto, o valores `NaN`/`bool` dan `--` en ese segmento. Siempre termina con código 0 y escribe una línea. La lectura de stdin está limitada a 1 MiB.
- **Git**: cada llamada con `timeout=1`, `stderr` descartado y `GIT_OPTIONAL_LOCKS=0` para no bloquear otros procesos git. Fuera de un repo, si no hay git o si se agota el tiempo, el segmento repo/rama desaparece junto con su separador.
- Los colores van en truecolor ANSI (`\x1b[38;2;R;G;Bm`) y cada segmento termina con `\x1b[0m`.
- Comando instalado: `"/usr/bin/python3 -I <HOME>/.claude/witchy/statusline.py"` con la ruta absoluta; `padding: 0`, sin `refreshInterval`. Si `/usr/bin/python3` no existe, se usa el `sys.executable` del instalador. No se usan los shims de pyenv, porque dependen del `.python-version` de cada proyecto.

## 6. Validación (`python3 -m witchy validate`)

`build` e `install` validan primero y abortan sin escribir nada si hay algún fallo. Reglas:

1. **Texto ≥ 4.5:1** sobre `#0D0916`: todos los tokens de color de texto de Claude Code (acentos, estados, modos, subagentes, arcoíris base, etiquetas), los 14 colores ANSI del esquema de Windows Terminal salvo `black` y `brightBlack`, más `foreground` y los colores de texto del status line.
2. **Secundario y bordes ≥ 3:1** sobre `#0D0916`: `subtle`, `promptBorder` y `brightBlack`.
3. **Fondos**: `text` (`#F3EAF7`) ≥ 4.5:1 sobre cada fondo (`diff*`, `*Background*`, `selectionBg`).
4. **Exentos** (decorativos o por convención), con la lista cerrada en `validate.py` y el motivo comentado: `rate_limit_empty`, el separador `⋆` del status line, los shimmer (son brillos animados de su token base) y `black` de Windows Terminal (por convención va cerca del fondo).
5. **Tokens**: todas las claves de `overrides` están en `tokens.py`, la lista oficial. Una clave desconocida es un fallo, no se ignora en silencio.
6. **Formato**: todos los colores cumplen `^#[0-9A-F]{6}$`.
7. **Contenido**: `spinner.json` tiene entre 36 y 48 verbos y entre 18 y 24 tips, sin duplicados, con los límites de la sección 8. El output style tiene frontmatter válido con `keep-coding-instructions: true`.

Cada fallo se imprime como `<regla>: <elemento> <valor> <ratio o motivo>`, y el comando termina con código 1.

## 7. Instalación y desinstalación

### 7.1 `install [--dry-run] [--wt-settings PATH]`

1. `build` y `validate`. Si falla, sale con código 1 sin tocar nada.
2. Copia los ficheros de `dist/claude/` a `~/.claude/` (sección 3.1), creando las carpetas que falten. Si `~/.claude/themes/` no existía, avisa: *"Restart Claude Code once so it starts watching ~/.claude/themes/"*.
3. Fusiona en `~/.claude/settings.json` estas **cinco claves**, sin tocar ninguna otra:
   ```json
   {
     "theme": "custom:moonlit-candle",
     "statusLine": { "type": "command", "command": "/usr/bin/python3 -I /home/<user>/.claude/witchy/statusline.py", "padding": 0 },
     "spinnerVerbs": { "mode": "replace", "verbs": ["..."] },
     "spinnerTipsOverride": { "label": "Grimoire", "tipsFile": "~/.claude/witchy/tips.json", "excludeDefault": false },
     "outputStyle": "WitchyNibbles"
   }
   ```
4. Windows Terminal (sección 7.3).
5. Escribe `~/.claude/witchy/state.json` y muestra un resumen de lo que ha cambiado.

`--dry-run` hace build y validate, calcula todos los cambios y muestra el diff unificado de cada fichero, **sin escribir nada**, ni siquiera `dist/`, que se genera en un directorio temporal.

### 7.2 Salvaguardas

- **Copia con fecha** antes de modificar cualquier fichero que ya existe: `<fichero>.bak-witchy-YYYYMMDD-HHMMSS`, en la misma carpeta.
- **Escritura atómica**: se escribe en un temporal de la misma carpeta y después `os.replace`.
- **JSON estricto**: si un `settings.json` no se puede leer con `json.loads` (comentarios, comas finales), **no se toca**. En el caso de Windows Terminal se muestra el fragmento para pegar a mano y el resto de la instalación sigue. En el caso de `~/.claude/settings.json`, se aborta.
- **state.json** guarda, para cada clave, su valor anterior o la marca `{"absent": true}`. Guarda también el valor que instaló, la lista de ficheros copiados, la ruta del `settings.json` de Windows Terminal, el GUID del perfil, su `colorScheme` anterior (o ausente) y si el esquema "Moonlit Candle" ya existía.
- **Idempotencia**: si `state.json` ya existe, `install` vuelve a aplicar los cambios pero **conserva** los valores anteriores guardados, así no se pierde el valor original de verdad. Dos instalaciones seguidas dan el mismo resultado que una.
- Los mensajes del instalador van en inglés y en tono neutro (el output style no aplica aquí).

### 7.3 Windows Terminal

- **Ruta**: `--wt-settings PATH` si se indica. Si no, `/mnt/c/Users/<U>/AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json`, donde `<U>` es la salida de `cmd.exe /c echo %USERNAME%` sin `\r`. **No se usa glob**: en esta máquina existen los usuarios `admin` y `mmarenas`, y hay que tocar solo el del usuario actual. Si no se encuentra, se muestra un aviso, se omite Windows Terminal y la instalación sigue.
- **Perfil**: el GUID de la variable de entorno `WT_PROFILE_ID` (ahora es `{05f3f843-450a-55ad-a264-cacf368dafe5}`, "Ubuntu"). Si no está, el único perfil con `source == "Microsoft.WSL"` cuyo `name` coincida con `$WSL_DISTRO_NAME`. Si hay cero o varios, se muestra un aviso y se omite Windows Terminal.
- **Cambios**: se añade el esquema a `schemes` (si ya existe uno con ese `name`, se reemplaza) y se pone `"colorScheme": "Moonlit Candle"` **solo** en ese perfil. El valor anterior ahora es `"One Half Dark"`.
- Windows Terminal recarga su `settings.json` en caliente; no hace falta reiniciarlo.

### 7.4 `uninstall [--dry-run]`

Lee `state.json`; si no existe, avisa de que no hay nada que desinstalar y sale con código 0.

- **Claves de Claude**: por cada clave, **solo si su valor actual sigue siendo el que instaló witchy**, se restaura el valor anterior o se borra la clave si antes no existía. Si el usuario la cambió después, se deja como está y se avisa.
- **Windows Terminal**: se restaura el `colorScheme` anterior del perfil con la misma regla. Se borra el esquema "Moonlit Candle" solo si no existía antes y ningún perfil lo usa.
- Se borran los ficheros copiados: tema, output style, `statusline.py` y `tips.json`. Después se borra `state.json` y la carpeta `~/.claude/witchy/` si queda vacía. Antes de modificar se hacen copias, igual que al instalar.

## 8. Contenido

### 8.1 Verbos del spinner (`content/spinner.json` → `verbs`)

Entre 36 y 48 verbos en inglés, con temática de brujería o hechicería, en forma *-ing* o con frase corta que empiece por *-ing*, de 28 caracteres como máximo y **sin** puntos suspensivos (Claude Code ya los añade). Estos 16 son obligatorios; el resto, del mismo estilo, los elige quien lo implemente:

`Brewing`, `Conjuring`, `Scrying`, `Hexing`, `Divining`, `Transmuting`, `Warding`, `Exorcising`, `Summoning`, `Enchanting`, `Incanting`, `Stirring the cauldron`, `Consulting the grimoire`, `Reading the runes`, `Lighting candles`, `Scrying the query plan`.

### 8.2 Tips (`content/spinner.json` → `tips`)

Entre 18 y 24 objetos `{"id", "text"}`: `id` en kebab-case (máximo 64 caracteres) y `text` en inglés, de 120 caracteres como máximo. Estos, tal cual, son obligatorios:

- `haunted-houses`: *Legacy systems are just haunted houses with uptime requirements.*
- `love-letters`: *Tests are love letters to your future self.*
- `ghost-in-query-plan`: *Measure before you optimise — the ghost is usually in the query plan.*
- `boring-code`: *Boring code is good code.*
- `remembers-everything`: *Be kind to your code — it remembers everything.*
- `keep-the-receipts`: *Keep the receipts.*
- `hold-the-thread`: *Hold the thread.*
- `through-the-fog`: *Exorcising legacy systems. Shipping code through the fog.*

El resto, del mismo tono (consejos de desarrollo backend con imaginería brujil y sin crueldad), los elige quien lo implemente. `build` genera `dist/claude/witchy/tips.json` como `{"tips": [...]}`.

### 8.3 Output style (`content/output-style.md`, texto final)

```markdown
---
name: WitchyNibbles
description: A backend witch's voice in chat replies only — files, code, commits and docs stay plain
keep-coding-instructions: true
---

# WitchyNibbles voice

Speak to the user in the voice of a backend witch: someone who exorcises legacy systems, keeps a grimoire of runbooks, and ships code through the fog. Precision comes first; the voice is seasoning, never a substitute for facts.

## Where the voice applies

Only in the prose you write directly to the user in this conversation.

## Where the voice never applies

Write exactly as you would without this style in:

- files you create or edit — code, comments, docstrings, configs, tests, docs, READMEs, specs, plans
- commit messages, branch names, PR titles and descriptions, issue and review comments
- tool arguments, shell commands, and anything sent to an external service or another agent
- prompts you write for subagents

## Always neutral

Drop the voice entirely, for the whole message, when reporting:

- errors, failing tests, or broken builds
- security findings or warnings
- confirmations before destructive, irreversible, or outward-facing actions
- production incidents

## How the voice sounds

- Light, dry, and competent. Vocabulary such as conjure, summon, ward, hex, exorcise, grimoire, ritual, familiar, candle, fog, haunted, ghost — at most one or two touches per message, where they fit naturally.
- "Receipts" means verification evidence: the command you ran and what it showed. When you claim something works, show the receipts.
- Keep the user's language: if they write in Spanish, answer in Spanish with the same voice.
- Never let a metaphor hide what actually happened. If a sentence would be clearer plain, write it plain.
- No emoji beyond an occasional 🕯️.
```

## 9. Pruebas

`python3 -m unittest discover -s tests -t .`, con `/usr/bin/python3` (3.12) y `/usr/bin/python3.10`. Cobertura mínima:

- **Paleta**: todas las claves de `overrides` están en `tokens.py`; cada regla de la sección 6 detecta un fallo inyectado; la paleta real pasa sin fallos.
- **Contraste**: valores conocidos (`#FFFFFF`/`#000000` = 21:1; `#6E5A80` sobre `#0D0916` ≈ 3.22).
- **Build**: el tema generado tiene `name`, `base: "dark"` y los `overrides` esperados; el bloque de paleta del `statusline.py` generado coincide con `palette.py`; el del fuente también.
- **Status line** (pasándole JSON por stdin a `main` y leyendo la salida):
  - payload completo;
  - payload vacío, `null` y JSON inválido;
  - sin `rate_limits`, `used_percentage: null` o de tipo incorrecto;
  - bordes de fase lunar (12/13, 37/38, 62/63, 87/88);
  - umbrales de color (49/50, 79/80 para contexto; 50/51, 20/21 para restante);
  - fuera de un repo, repo limpio, repo con cambios, rama larga y HEAD separado (con repos git temporales).

  En todos los casos termina con código 0.
- **Instalador**, con un `HOME` temporal y un `settings.json` de Windows Terminal falso, pasando `--wt-settings` y `WT_PROFILE_ID` por entorno:
  - install y después uninstall deja los ficheros byte a byte iguales, sin contar las copias `.bak-witchy-*`;
  - dos installs seguidos dan el mismo resultado que uno y `state.json` conserva el valor original;
  - uninstall no restaura una clave que el usuario cambió después;
  - un Windows Terminal con comentarios no se toca y se muestra el fragmento;
  - `--dry-run` no escribe nada;
  - las claves ajenas de `settings.json` siguen intactas.

Ningún test toca el `~/.claude` ni el Windows Terminal reales.

## 10. Criterios de aceptación

1. `python3 -m witchy validate` termina con código 0 y todos los tests pasan con `/usr/bin/python3` (3.12) y con `/usr/bin/python3.10`.
2. `python3 -m witchy install --dry-run` sobre la máquina real muestra solo los cambios de las secciones 7.1 y 7.3.
3. Tras `install` real y un reinicio de Claude Code:
   - `/theme` muestra "Moonlit Candle" seleccionado;
   - el fondo del perfil Ubuntu es berenjena;
   - el spinner usa los verbos y los tips `Grimoire:`;
   - el status line tiene fases lunares y git;
   - las respuestas en el chat tienen la voz B y los ficheros no.
4. El usuario lo revisa visualmente y lo aprueba.
5. `uninstall` real devuelve `theme: "dark"`, el status line de archon y "One Half Dark". Esto se comprueba y después se vuelve a instalar si el usuario quiere.
