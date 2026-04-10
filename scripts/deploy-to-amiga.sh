#!/usr/bin/env bash
set -euo pipefail

AE_EXE=${AE_EXE:-"/mnt/c/Program Files/Cloanto/Amiga Explorer/Windows/ae.exe"}
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
STACK_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
INSTALL_DIR=${INSTALL_DIR:-"${STACK_ROOT}/install"}

usage() {
	cat <<'EOF'
Usage: deploy-to-amiga.sh [--install-dir PATH] [--dry-run]

Copies installed driver-stack runtime binaries to the Amiga using ae.exe.

Source directories mapped automatically:
  install/LIBS -> LIBS:
  install/DEVS -> DEVS:
  install/C    -> C:

Environment overrides:
  AE_EXE       Path to ae.exe
	INSTALL_DIR  Driver-stack install directory
EOF
}

DRY_RUN=0
while [[ $# -gt 0 ]]; do
	case "$1" in
		--install-dir)
			INSTALL_DIR=$2
			shift 2
			;;
		--dry-run)
			DRY_RUN=1
			shift
			;;
		-h|--help)
			usage
			exit 0
			;;
		*)
			echo "Unknown argument: $1" >&2
			usage >&2
			exit 2
			;;
	esac
done

if [[ ! -x "$AE_EXE" ]]; then
	echo "ae.exe not found or not executable: $AE_EXE" >&2
	exit 1
fi

if [[ ! -d "$INSTALL_DIR" ]]; then
	echo "Install directory not found: $INSTALL_DIR" >&2
	exit 1
fi

run_ae() {
	if [[ $DRY_RUN -eq 1 ]]; then
		printf 'DRY RUN: %q' "$AE_EXE"
		shift 0
		for arg in "$@"; do
			printf ' %q' "$arg"
		done
		printf '\n'
	else
		"$AE_EXE" "$@"
	fi
}

copy_tree() {
	local src_root=$1
	local amiga_root=$2

	[[ -d "$src_root" ]] || return 0

	while IFS= read -r -d '' file; do
		local rel_path=${file#"$src_root/"}
		run_ae Copy "$file" "${amiga_root}${rel_path}" /Y
	done < <(find "$src_root" -type f -print0 | sort -z)
}

copy_tree "$INSTALL_DIR/LIBS" "LIBS:"
copy_tree "$INSTALL_DIR/DEVS" "DEVS:"
copy_tree "$INSTALL_DIR/C" "C:"

echo "Transfer complete."