#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+
"""Build the committed installer .info icon from its PNG + .info.src descriptor.

Each icon gets a faithful OS3.5 ColorIcon (full colour + transparency)
plus a planar fallback, honouring TYPE/STACK/DEFAULTTOOL/TOOLTYPES/TOOLTYPE
from its .info.src. One icontool invocation builds each icon: --create
synthesises the DiskObject, the imports supply the art, and the tooltype
options are applied in the order given.

The PNGs are committed source art; this script only matters when
regenerating the .info files (themselves committed static assets, so
building the stack needs nothing here). Same pipeline and descriptor format
as components/lwip-amiga/dist/icons/.

Descriptor keys:
    TYPE        = TOOL | PROJECT | ...      (default TOOL)
    STACK       = <bytes>                   (default 4096)
    DEFAULTTOOL = <tool>                    (projects)
    TOOLTYPES   = FLAG[, FLAG...]           boolean tooltypes (--set-flag)
    TOOLTYPE    = KEY=VALUE                 one value tooltype, repeatable (--set)

Requirements (host-side only):
    * python3 with pypng
    * icontool with --create / --import-coloricon / --set-defaulttool
      (https://github.com/rondoval/icontool, branch set-defaulttool)

Usage:   ICONTOOL=/path/to/icontool/icontool python3 make_icons.py [name...]
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ICONTOOL = os.environ.get("ICONTOOL",
                          os.path.normpath(os.path.join(ROOT, "..", "icontool", "icontool")))

# (source PNG, .info.src, output .info) — paths relative to the repo root
ICONS = [
    ("installer/icons/Install.png", "installer/icons/Install.info.src", "installer/Install.info"),
]


def parse_info_src(path):
    """KEY = VALUE lines; TOOLTYPE is repeatable and collected as a list."""
    meta = {"TOOLTYPE": []}
    if path and os.path.exists(path):
        with open(path, encoding="latin-1") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip().upper()
                v = v.strip()
                if k == "TOOLTYPE":
                    meta["TOOLTYPE"].append(v)
                else:
                    meta[k] = v
    return meta


def convert(png_rel, src_rel, out_rel):
    png = os.path.join(ROOT, png_rel)
    out = os.path.join(ROOT, out_rel)
    meta = parse_info_src(os.path.join(ROOT, src_rel))
    itype = meta.get("TYPE", "TOOL")
    stack = int(meta.get("STACK", "4096"))
    deftool = meta.get("DEFAULTTOOL")
    # boolean tooltypes, comma-separated (e.g. TOOLTYPES = DONOTWAIT)
    flags = [t.strip() for t in meta.get("TOOLTYPES", "").split(",") if t.strip()]
    values = meta["TOOLTYPE"]

    cmd = [sys.executable, ICONTOOL,
           "--create", itype,                       # synthesise the DiskObject
           "--edit", f"DiskObject:StackSize={stack}",
           "--import-icon", png,                    # classic planar fallback
           "--import-coloricon", png]               # OS3.5 ColorIcon (full colour)
    if deftool:
        cmd += ["--set-defaulttool", deftool]
    # flags before values: tooltypes land in the order given
    for tt in flags:
        cmd += ["--set-flag", tt]
    for tt in values:
        cmd += ["--set", tt]
    cmd += [out]
    subprocess.run(cmd, check=True)
    print(f"wrote {out_rel}  (type={itype} stack={stack}"
          + (f" defaulttool={deftool}" if deftool else "")
          + (f" flags={','.join(flags)}" if flags else "")
          + (f" tooltypes={','.join(values)}" if values else "") + ")")


def main():
    if not os.path.exists(ICONTOOL):
        sys.exit(f"icontool not found at {ICONTOOL} (set $ICONTOOL)")
    # optional argv filter: regenerate only the named outputs (base name)
    only = {a.removesuffix(".info") for a in sys.argv[1:]}
    for png_rel, src_rel, out_rel in ICONS:
        if only and os.path.basename(out_rel).removesuffix(".info") not in only:
            continue
        convert(png_rel, src_rel, out_rel)


if __name__ == "__main__":
    main()
