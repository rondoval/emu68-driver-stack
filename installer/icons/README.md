# installer/icons — Workbench icon assets

Source art and generator for the installer's `.info` icon. The produced
`.info` is committed as a **static binary asset** next to the script it
belongs to, so building the stack needs no Python, pypng or icontool — the
files here only matter when *regenerating* it. The `package` target
explicitly excludes this drawer from the archive.

| Output (committed) | From | Kind |
|---|---|---|
| `installer/Install.info` | `Install.png` + `Install.info.src` | project (`DefaultTool = SYS:Utilities/Installer`), ColorIcon + classic fallback |

`make_icons.py` drives the icontool fork, one invocation per icon — `--create`
synthesises the DiskObject, the imports supply the art, and the tooltype
options are applied in the order given. Descriptor keys are `TYPE`, `STACK`,
`DEFAULTTOOL`, `TOOLTYPES` (boolean) and a repeatable `TOOLTYPE = KEY=VALUE`
for value tooltypes. Same format as
[`components/lwip-amiga/dist/icons/`](../../components/lwip-amiga/dist/icons/).

`Install.info` must be a **project** icon carrying a DefaultTool: that is what
lets a user double-click `Install` and have Workbench start the Commodore
Installer on it. 

## Regenerating

Host-side only. Needs python3 with **pypng** (a venv is fine) and the
[icontool fork](https://github.com/rondoval/icontool) (branch `set-defaulttool`,
which adds `--create`, the ColorIcon writer, DefaultTool set/clear and
repeatable tooltype options):

```sh
python3 -m venv .venv && .venv/bin/pip install pypng
ICONTOOL=/path/to/icontool/icontool .venv/bin/python make_icons.py
```

Without pypng, icontool still writes a DiskObject but silently imports no
artwork — check the output for `imported main icon` and `attached ColorIcon`
before committing. Reducing the full-colour PNG to the 4-bitplane classic
fallback reports a colour-error warning; that is expected, and the ColorIcon
carries the faithful image for OS3.5+ and Emu68 setups that render it.

## Licensing

`Install.png` is original art for this project, under the repository's licence.
Nothing here is taken from AmigaOS or third-party icon sets.
