#!/usr/bin/env python3
"""Verify that every asm("aN"/"dN") register-argument function was actually
emitted with the register calling convention.

Why this exists
---------------
bebbo's gcc 16.1 SILENTLY drops the AmigaOS register-parameter annotations when
a prototype sees a parameter as pointer-to-*incomplete* struct and the
definition later sees the completed struct:

    struct Map;                                   /* tag only, e.g. via a member decl */
    LONG hook(struct Hook *h asm("a0"), struct Map *m asm("a1"));
    struct Map { ... };                           /* completed AFTER the prototype */
    LONG hook(struct Hook *h asm("a0"), struct Map *m asm("a1")) { ... }

The definition is then compiled with the plain stack calling convention.  No
diagnostic is emitted at any -W level.  Callers (Exec/MUI hook dispatch, library
LVO stubs, interrupt servers) still pass in a0/a1/..., so the callee reads
garbage off the stack: wild reads, wild writes, guru.  Found the hard way in
hid.class's USBKeyListDisplayHook.

What it does
------------
Collects the names of all functions carrying register parameters from the
sources, then walks the disassembly of every object in the build tree.  A
function is reported when it reads an *incoming argument off the stack*, which a
register-argument function never does.  Incoming argument K sits at
`depth + 4*K` from sp, where `depth` is how far sp has moved below the entry
point, so the prologue (pushes, movem, link, sp arithmetic) is modelled rather
than merely skipped -- a stack-convention function that saves registers first
would otherwise slip through.

Usage:  scripts/check-regargs.py [build-dir] [--src ROOT] [--objdump PATH] [-v]
Exit status is 1 when something was miscompiled.
"""

import argparse
import os
import re
import subprocess
import sys

SYM_RE = re.compile(r"^[0-9a-f]+ [0-9a-f]+ _([A-Za-z_][A-Za-z0-9_]*):")
# an offset that is not negative and not part of a larger token
SP_RE = re.compile(r"(?<![-\w.])(\d+)\(sp\)")
FP_RE = re.compile(r"(?<![-\w.])(\d+)\(a5\)")
REGARG_RE = re.compile(r'asm\s*\(\s*"[ad][0-7]"\s*\)')
MOVEM_REGS_RE = re.compile(r"\b([ad][0-7])(?:-([ad][0-7]))?")
END_RE = re.compile(r"^(rts|rte|rtd|rtr|\.short|\.long|\.byte|Address )")

SRC_EXTS = ("*.c", "*.h", "*.cpp", "*.hpp")
SKIP_DIRS = ("/build", "/install", "/.git", "/node_modules")


# --------------------------------------------------------------------------
# source side: which functions are supposed to take register arguments
# --------------------------------------------------------------------------
def enclosing_declarator(src, pos):
    """Given the offset of an asm("aN") inside a parameter list, return the name
    of the function it belongs to, or None."""
    depth = 0
    i = pos - 1
    while i >= 0:
        c = src[i]
        if c == ")":
            depth += 1
        elif c == "(":
            if depth == 0:
                break
            depth -= 1
        i -= 1
    if i < 0:
        return None

    j = i - 1
    while j >= 0 and src[j].isspace():
        j -= 1
    # `TYPE (name)(args ...)` -- the declarator is parenthesised
    if j >= 0 and src[j] == ")":
        depth = 0
        while j >= 0:
            if src[j] == ")":
                depth += 1
            elif src[j] == "(":
                depth -= 1
                if depth == 0:
                    break
            j -= 1
        name = src[j + 1 : i - 1].strip().lstrip("*").strip()
        return name if name.isidentifier() else None

    end = j + 1
    while j >= 0 and (src[j].isalnum() or src[j] == "_"):
        j -= 1
    name = src[j + 1 : end]
    return name if name and not name[0].isdigit() else None


def collect_regarg_functions(root):
    names = set()
    for dirpath, dirnames, filenames in os.walk(root):
        if any(s in dirpath for s in SKIP_DIRS):
            dirnames[:] = []
            continue
        for fn in filenames:
            if not fn.endswith((".c", ".h", ".cpp", ".hpp")):
                continue
            path = os.path.join(dirpath, fn)
            try:
                src = open(path, encoding="latin-1").read()
            except OSError:
                continue
            if "asm" not in src:
                continue
            for m in REGARG_RE.finditer(src):
                name = enclosing_declarator(src, m.start())
                if name:
                    names.add(name)
    return names


# --------------------------------------------------------------------------
# object side: model the prologue and catch incoming-argument stack reads
# --------------------------------------------------------------------------
def count_movem_regs(operand):
    n = 0
    for lo, hi in MOVEM_REGS_RE.findall(operand):
        if hi:
            # a2-a6 style range; both ends are in the same bank
            n += ord(hi[1]) - ord(lo[1]) + 1
        else:
            n += 1
    return n


def sp_delta(insn):
    """How much this instruction pushes (positive) or pops (negative)."""
    mnem = insn.split()[0] if insn.split() else ""
    operand = insn[len(mnem) :].strip()

    if mnem.startswith("movem"):
        if operand.endswith("-(sp)"):
            return 4 * count_movem_regs(operand.split(",")[0])
        if operand.startswith("(sp)+"):
            return -4 * count_movem_regs(operand.split(",", 1)[1])
        return 0
    if mnem.startswith("link"):
        # pushes the frame pointer, then carves out the local frame
        m = re.search(r"#-?(\d+)", operand)
        return 4 + (int(m.group(1)) if m else 0)
    if mnem.startswith("unlk"):
        return None  # frame torn down; depth is meaningless past here
    if mnem.startswith("pea"):
        return 4
    if mnem.startswith(("move", "clr", "tst")) and operand.endswith("-(sp)"):
        return 4
    if "(sp)+" in operand and mnem.startswith("move"):
        return -4
    # explicit stack arithmetic
    m = re.match(r"^(?:add|sub)[qi]?\.[bwl] #(-?\d+),sp$", insn)
    if m:
        v = int(m.group(1))
        return -v if mnem.startswith("add") else v
    m = re.match(r"^adda\.[wl] #(-?\d+),sp$", insn)
    if m:
        return -int(m.group(1))
    m = re.match(r"^lea (-?\d+)\(sp\),sp$", insn)
    if m:
        return -int(m.group(1))
    return 0


def scan_object(objdump, obj, regargs):
    try:
        dis = subprocess.run(
            [objdump, "-d", "--no-show-raw-insn", obj],
            capture_output=True, text=True, timeout=180,
        ).stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"warning: cannot disassemble {obj}: {e}", file=sys.stderr)
        return []

    hits, cur, depth, fp_depth, n = [], None, 0, None, 0
    for line in dis.splitlines():
        m = SYM_RE.match(line)
        if m:
            cur, depth, fp_depth, n = m.group(1), 0, None, 0
            continue
        if cur is None:
            continue
        parts = line.split("\t", 1)
        if len(parts) < 2:
            continue
        insn = parts[1].strip()
        # stop at the end of the function so we never disassemble into the
        # string/table data that follows short stubs like `clr.l d0; rts`
        if END_RE.match(insn):
            cur = None
            continue
        n += 1
        if n > 80 or cur not in regargs:
            if cur not in regargs:
                cur = None
            continue

        # an access above our own frame is the caller's argument block
        for m2 in SP_RE.finditer(insn):
            if int(m2.group(1)) >= depth + 4:
                hits.append((cur, insn))
                cur = None
                break
        if cur is None:
            continue
        # ...same thing addressed through the frame pointer: a5 holds sp as it
        # was fp_depth bytes into the frame, so N(a5) is arg1 at N - fp_depth == 4
        if fp_depth is not None:
            for m2 in FP_RE.finditer(insn):
                if int(m2.group(1)) - fp_depth >= 4:
                    hits.append((cur, insn))
                    cur = None
                    break
        if cur is None:
            continue

        d = sp_delta(insn)
        if d is None:
            cur = None
            continue
        if insn.startswith("link"):
            depth += 4              # the pushed frame pointer...
            fp_depth = depth        # ...is what a5 now points at
            depth += d - 4          # then the local frame
            continue
        depth += d
        if re.match(r"^movea?\.l sp,a5$", insn):
            fp_depth = depth        # frame pointer set up without link
    return hits


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("build", nargs="?", default=os.path.join(root, "build"),
                    help="build tree to scan (default: <repo>/build)")
    ap.add_argument("--src", default=root, help="source root (default: repo root)")
    ap.add_argument("--objdump", default=os.environ.get("OBJDUMP"),
                    help="m68k objdump (default: first one found)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    objdump = args.objdump
    if not objdump:
        for cand in ("/opt/m68k-amigaos/bin/m68k-amigaos-objdump",
                     "/opt/amiga/bin/m68k-amigaos-objdump",
                     "m68k-amigaos-objdump"):
            if os.path.exists(cand) or subprocess.run(
                    ["sh", "-c", f"command -v {cand}"],
                    capture_output=True).returncode == 0:
                objdump = cand
                break
    if not objdump:
        print("check-regargs: no m68k-amigaos-objdump found, skipping", file=sys.stderr)
        return 0

    objs = []
    for dirpath, _, filenames in os.walk(args.build):
        for fn in filenames:
            if fn.endswith((".obj", ".o")):
                objs.append(os.path.join(dirpath, fn))
    if not objs:
        if args.verbose:
            print(f"check-regargs: no objects under {args.build}, nothing to check")
        return 0

    regargs = collect_regarg_functions(args.src)
    hits = []
    for obj in sorted(objs):
        for fn, insn in scan_object(objdump, obj, regargs):
            hits.append((fn, insn, os.path.relpath(obj, root)))

    if args.verbose:
        print(f"check-regargs: {len(regargs)} register-argument functions, "
              f"{len(objs)} objects")
    if not hits:
        return 0

    print("", file=sys.stderr)
    print("check-regargs: FAILED -- register arguments were dropped by the compiler",
          file=sys.stderr)
    for fn, insn, obj in sorted(set(hits)):
        print(f"  {fn}(): reads an incoming argument off the stack "
              f"({insn})\n      in {obj}", file=sys.stderr)
    print("", file=sys.stderr)
    print("These functions declare asm(\"aN\")/asm(\"dN\") parameters but were emitted",
          file=sys.stderr)
    print("with the stack calling convention, so every call passes garbage.  The usual",
          file=sys.stderr)
    print("cause is a prototype that sees a parameter's struct as an incomplete type",
          file=sys.stderr)
    print("while the definition sees it complete -- make the struct complete before",
          file=sys.stderr)
    print("the prototype (move it into a header included earlier).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
