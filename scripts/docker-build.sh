#!/usr/bin/env bash
# Build the driver stack inside the Amiga cross-toolchain container.
#
# No local m68k-amigaos toolchain is required: this runs the same image CI uses,
# which ships the cross-compiler at /opt/m68k-amigaos and the `lha` archiver used
# by the `package` target.  The image tag lives here and nowhere else, so the
# wrapper and CI stay in lock-step.
#
# Usage:
#   scripts/docker-build.sh                 # configure + build the whole stack
#   scripts/docker-build.sh --target package  # ...and create the .lha release archive
#   EMU68_CONFIGURE_ARGS="-DEMU68_DEBUG_BACKEND=serial" scripts/docker-build.sh
#   # build two backends side by side (distinct dirs, no clobber):
#   EMU68_BUILD_DIR=build-off    EMU68_INSTALL_DIR=install-off \
#       EMU68_CONFIGURE_ARGS="-DEMU68_DEBUG_BACKEND=off"    scripts/docker-build.sh --target package
#   EMU68_BUILD_DIR=build-serial EMU68_INSTALL_DIR=install-serial \
#       EMU68_CONFIGURE_ARGS="-DEMU68_DEBUG_BACKEND=serial" scripts/docker-build.sh --target package
#
# Any arguments are forwarded to `cmake --build <build dir> <args>`.
# Environment overrides:
#   EMU68_BUILD_IMAGE     Toolchain image tag (default: amigadev/crosstools:m68k-amigaos)
#   EMU68_CONFIGURE_ARGS  Extra args appended to the `cmake -S . -B <build dir>` configure step
#   EMU68_BUILD_DIR       CMake build directory, relative to the workspace (default: build)
#   EMU68_INSTALL_DIR     Install prefix, relative to the workspace (default: install).
#                         The package's .lha lands in <EMU68_BUILD_DIR>/package/.
set -euo pipefail

IMAGE=${EMU68_BUILD_IMAGE:-"amigadev/crosstools:m68k-amigaos"}
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
STACK_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)

if ! command -v docker >/dev/null 2>&1; then
	echo "docker not found in PATH" >&2
	exit 1
fi

# Outputs are written back to the mounted workspace; -u keeps them host-owned
# (not root).  HOME=/tmp gives the arbitrary uid a writable home for tool caches.
# The explicit -DCMAKE_INSTALL_PREFIX=/work/install pins the install tree to the
# mounted workspace: the image's CMAKE_TOOLCHAIN_FILE env otherwise defaults the
# prefix into the root-owned toolchain sysroot, which a non-root build can't write.
# Note: a build/ tree is tied to its prefix path (/work here) — do not share one
# build directory between docker and a native /opt/m68k-amigaos build; rm -rf build
# when switching.
docker run --rm \
	-v "${STACK_ROOT}:/work" \
	-w /work \
	-u "$(id -u):$(id -g)" \
	-e HOME=/tmp \
	-e LC_ALL=C \
	-e EMU68_CONFIGURE_ARGS \
	-e EMU68_BUILD_DIR \
	-e EMU68_INSTALL_DIR \
	"${IMAGE}" \
	sh -c 'BD=${EMU68_BUILD_DIR:-build}; ID=/work/${EMU68_INSTALL_DIR:-install}; cmake -S . -B "$BD" -DCMAKE_INSTALL_PREFIX="$ID" ${EMU68_CONFIGURE_ARGS:-} && cmake --build "$BD" "$@"' \
	sh "$@"
