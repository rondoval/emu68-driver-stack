#!/usr/bin/env bash
#
# build.sh — build the emu68 driver stack (in the shared GHCR toolchain container),
# package it as an installable .lha, and/or push the built binaries to a live Amiga
# over Cloanto Amiga Explorer (AE.exe).
#
# Pick any combination of --build / --package / --upload; with none of them given it
# does --build --upload (the usual edit-build-test loop).
#
# The build/package half delegates to scripts/docker-build.sh (the CI-coupled wrapper
# that owns the docker invocation and image tag); this script adds the backend knobs
# and the upload.  The upload pushes the freshly built binaries into the same LIBS:/
# DEVS:/C: locations the Installer uses; it does NOT run the Installer's extra steps
# (docs, icons, S:User-Startup).  For a first-time/full install use the .lha
# (--package) + Installer.
#
# Prerequisites
#   * --build / --package: docker (the toolchain image is public and auto-pulled).
#   * --upload: Amiga Explorer running on the Amiga (serial or TCP) with the matching
#     connection configured on the Windows side (this script drives AE.exe via WSL).
#
# Usage
#   ./build.sh [--build] [--package] [--upload] [--dry-run]
#     --build     build the stack in the toolchain container (debug backend below)
#     --package   build, then create build/package/emu68-drivers-<ver>.lha
#                 (use BACKEND=off for a release)
#     --upload    push the built binaries (install/LIBS, DEVS, C) to the Amiga
#     (none of --build/--package/--upload => --build --upload)
#     --dry-run   upload: show what would be copied; copy nothing
#     -h, --help  this help
#
# Env overrides:
#     BACKEND=<pistorm|serial|off>  debug sink (default pistorm; use off for a release)
#     DEBUG_HIGH=<components|ALL>    verbose per-component logging (CMake list; default off)
#     BUILD_DIR=<rel path>          build dir under the repo (default build)
#     INSTALL_DIR=<rel path>        install prefix under the repo, and the upload source
#                                   (default install)
#     BUILD_IMAGE=<image>           override the toolchain image (default lives in
#                                   scripts/docker-build.sh)
#     AE=<path to AE.exe>
set -euo pipefail

# --- config ------------------------------------------------------------------
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${BUILD_DIR:-build}"        # relative to the repo (scripts/docker-build.sh contract)
INSTALL_DIR="${INSTALL_DIR:-install}"  # relative to the repo
AE="${AE:-/mnt/c/Program Files/Cloanto/Amiga Explorer/Windows/AE.exe}"
DEBUG_BACKEND="${BACKEND:-pistorm}"
DEBUG_HIGH="${DEBUG_HIGH:-}"
ABS_INSTALL="$ROOT/$INSTALL_DIR"

DO_BUILD=0 DO_PACKAGE=0 DO_UPLOAD=0 DRY=0 EXPLICIT=0
for a in "$@"; do
    case "$a" in
        --build)   DO_BUILD=1;   EXPLICIT=1 ;;
        --package) DO_PACKAGE=1; EXPLICIT=1 ;;
        --upload)  DO_UPLOAD=1;  EXPLICIT=1 ;;
        --dry-run) DRY=1 ;;
        -h|--help) sed -n '2,/^[^#]/{/^#/p}' "$0"; exit 0 ;;   # the leading comment block
        *) echo "unknown option: $a (try --help)" >&2; exit 2 ;;
    esac
done
# No action chosen => the usual build + upload loop.
if (( ! EXPLICIT )); then DO_BUILD=1; DO_UPLOAD=1; fi
# Packaging stages from a complete build, so it implies a build.
if (( DO_PACKAGE )); then DO_BUILD=1; fi

# Runtime trees the Installer/upload ship: install/<src> -> <Amiga:> (recursive).
# (Developer/, include/ and lib/ are the SDK/build-time outputs and are not deployed.)
TREES=(
    "LIBS|LIBS:"
    "DEVS|DEVS:"
    "C|C:"
)

# --- helpers -----------------------------------------------------------------
ae() { "$AE" "$@"; }                       # AE.exe always exits 0 — parse its output, not $?

# Create an Amiga dir if missing (MakeDir errors harmlessly when it already exists).
ensure_dir() { ae MakeDir "$1" >/dev/null 2>&1 || true; }

# Create every ancestor dir of <amiga-root><relative-file> on the Amiga (MakeDir does
# not create intermediates).  e.g. DEVS: + Networks/genet.device -> MakeDir DEVS:Networks.
ensure_parents() {                         # ensure_parents <amiga-root-colon> <relative/path>
    local amiga="$1" rel="$2" dir acc part
    dir="${rel%/*}"
    [[ "$dir" == "$rel" ]] && return       # no subdirectory component
    acc="$amiga"
    local IFS=/
    for part in $dir; do
        acc="${acc}${part}"
        ensure_dir "$acc"
        acc="${acc}/"
    done
}

ok=0 fail=0
copy_one() {                               # copy_one <abs-src> <amiga-dest> <label>
    local src="$1" dest="$2" label="$3" win out
    if [[ ! -f "$src" ]]; then
        printf '  \e[31mMISS\e[0m %-42s (not built — run --build?)\n' "$label" >&2
        fail=$((fail + 1)); return
    fi
    if (( DRY )); then
        printf '  would copy %-42s -> %s\n' "$label" "$dest"; return
    fi
    win="$(wslpath -w "$src")"
    out="$(ae Copy "$win" "$dest" /Y 2>&1 || true)"
    if printf '%s' "$out" | grep -qiE 'error|cannot|fail' || ! printf '%s' "$out" | grep -q '100%'; then
        printf '  \e[31mFAIL\e[0m %-42s -> %s\n' "$label" "$dest" >&2
        printf '       %s\n' "$(printf '%s' "$out" | tr -d '\r' | grep -iE 'error|cannot' | head -1)" >&2
        fail=$((fail + 1))
    else
        printf '  \e[32m OK \e[0m %-42s -> %s\n' "$label" "$dest"
        ok=$((ok + 1))
    fi
}

# Recursively copy install/<src-root> -> <amiga-root>, preserving the subtree (covers
# the nested DEVS:Networks / DEVS:USBHardware device dirs).
deploy_tree() {                            # deploy_tree <src-under-install> <amiga-root-colon>
    local root="$ABS_INSTALL/$1" amiga="$2"
    if [[ ! -d "$root" ]]; then
        printf '  \e[31mMISS\e[0m %-42s (not built — run --build?)\n' "$INSTALL_DIR/$1" >&2
        fail=$((fail + 1)); return
    fi
    local -a files; mapfile -t files < <(find "$root" -type f | sort)
    local f rel
    for f in "${files[@]}"; do
        rel="${f#"$root"/}"
        (( DRY )) || ensure_parents "$amiga" "$rel"
        copy_one "$f" "${amiga}${rel}" "$1/$rel"
    done
}

# --- build / package (delegated to the CI-coupled container wrapper) ----------
if (( DO_BUILD )); then
    # Translate the backend knobs into configure args, appending any the caller set.
    configure_args="-DEMU68_DEBUG_BACKEND=$DEBUG_BACKEND"
    [[ -n "$DEBUG_HIGH" ]] && configure_args+=" -DEMU68_DEBUG_HIGH=$DEBUG_HIGH"
    [[ -n "${EMU68_CONFIGURE_ARGS:-}" ]] && configure_args+=" $EMU68_CONFIGURE_ARGS"
    export EMU68_CONFIGURE_ARGS="$configure_args"
    export EMU68_BUILD_DIR="$BUILD_DIR"
    export EMU68_INSTALL_DIR="$INSTALL_DIR"
    # Forward an image override only if the caller set one; otherwise let
    # docker-build.sh own the default tag (single source of truth).
    [[ -n "${BUILD_IMAGE:-}" ]] && export EMU68_BUILD_IMAGE="$BUILD_IMAGE"

    what="building"; (( DO_PACKAGE )) && what="building + packaging"
    echo ">> $what via scripts/docker-build.sh (debug backend=$DEBUG_BACKEND${DEBUG_HIGH:+, high=$DEBUG_HIGH}) ..."
    if (( DO_PACKAGE )); then
        # The `package` target DEPENDS on the full `stack`, so this builds then archives.
        "$ROOT/scripts/docker-build.sh" --target package
        lha="$(ls -t "$ROOT/$BUILD_DIR"/package/emu68-drivers-*.lha 2>/dev/null | head -1 || true)"
        [[ -n "$lha" ]] && echo ">> package: $lha"
    else
        "$ROOT/scripts/docker-build.sh"
    fi
fi

# --- upload ------------------------------------------------------------------
if (( DO_UPLOAD )); then
    # --dry-run touches nothing, so it does not need AE.exe — it just previews the plan.
    if (( ! DRY )); then
        [[ -x "$AE" || -f "$AE" ]] || { echo "AE.exe not found at: $AE  (set AE=...)" >&2; exit 1; }

        # preflight: is the Amiga reachable? (retry — AE drops the odd request)
        echo ">> checking Amiga Explorer connection ..."
        # NB: do NOT wrap AE.exe in `timeout` — under WSL Win32 interop that severs its
        # connection and it reports no volumes. AE has its own serial/TCP timeout anyway.
        connected=0
        for attempt in 1 2 3; do
            if ae Info 2>/dev/null | grep -q 'Volume:'; then connected=1; break; fi
            sleep 2
        done
        if (( ! connected )); then
            echo "No Amiga connection (AE Info returned no volumes after 3 tries)." >&2
            echo "Start Amiga Explorer on the Amiga and check the Windows-side connection." >&2
            exit 1
        fi
    fi

    echo ">> deploying install/{LIBS,DEVS,C} to LIBS: / DEVS: / C: ..."
    for t in "${TREES[@]}"; do
        deploy_tree "${t%%|*}" "${t#*|}"
    done
fi

# --- summary -----------------------------------------------------------------
if (( DO_UPLOAD )); then
    echo
    if (( DRY )); then
        echo "dry run — nothing copied."
    else
        echo "done: $ok copied, $fail failed."
        echo "Note: the *.device drivers and *.library are bound at boot — reboot the"
        echo "      Amiga (or unload/reload the affected driver) to pick up the new binaries."
    fi
fi
(( fail == 0 ))
