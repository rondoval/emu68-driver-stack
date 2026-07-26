# emu68-driver-stack Agent Notes

These instructions are specific to the top-level superbuild repo.

## Role

- This repo is the preferred validation point when a change touches installed headers, exported CMake packages, or more than one component.
- Components are git submodules under `components/`: `devicetree.resource`, `mailbox.resource`, `emu68-common`, `emu68-gic400-library`, `emu68-pcie-library`, `emu68-xhci-driver-context`, `emu68-xhci-driver-legacy`, `emu68-genet-driver-netdev`, `emu68-genet-driver-sana2`, `emu68-nvme-driver`, `lwip-amiga`.
- Default driver-stack output goes under `install/`, including `install/Developer`, `install/include`, `install/lib`, `install/LIBS`, `install/DEVS`, and `install/C`.

## Build Flow

- **All builds go through `./scripts/docker-build.sh` (container build). Never run
  `cmake` on the host**: the shared `build/` cache is configured at `/work` inside
  the container image (`ghcr.io/rondoval/amiga-build-container:latest`), so host-side
  `cmake --build build` fails with a CMakeCache path mismatch, and a host reconfigure
  would clobber the container cache.
- Rebuild commands:
  - `./scripts/docker-build.sh` (full stack)
  - `./scripts/docker-build.sh --target <name>` (single superbuild target)
- `--target package` produces `build/package/emu68-drivers-<version>.lha` (`lha` ships
  in the image). The version comes from `CMakeLists.txt` and is stamped into
  `installer/Install`/`ReadMe`, generated from the `*.in` templates.
- The superbuild creates per-component build directories under `emu68-driver-stack/build/`; prefer this over ad hoc downstream rebuilds when interface changes are involved.
- Debug output backend is stack-wide via `EMU68_DEBUG_BACKEND` (default `pistorm`),
  propagated to all components:
  `EMU68_CONFIGURE_ARGS="-DEMU68_DEBUG_BACKEND=serial" ./scripts/docker-build.sh`
  (`pistorm` → `0xdeadbeef` trap, ROM-able | `serial` → `debug.lib` serial @ 9600,
  not ROM-able | `off` → compiled out). See `components/emu68-common`.

## Dependency Order

When rebuilding components manually after API or install-layout changes, use this order:

1. `devicetree.resource`
2. `mailbox.resource`
3. `emu68-common`
4. `emu68-gic400-library`, `lwip-amiga`
5. `emu68-pcie-library`
6. `emu68-xhci-driver-context`, `emu68-xhci-driver-legacy`, `emu68-nvme-driver`, `emu68-genet-driver-netdev`, `emu68-genet-driver-sana2` (parallel)

## Related Repositories

- `emu68-xhci-driver-context` is a **matched pair** with the Poseidon USB stack backport
  (the `poseidon-backport` repo): the context HCD ABI is specified in that repo's
  `docs/poseidon-context-hcd-abi.md` + `docs/implementation-plan.md`. Cross-repo ABI changes must
  land in both.

## Validation

- If a downstream package stops configuring, check whether an upstream package was rebuilt and installed into the same prefix.
- Prefer validating stack-wide from here when changes affect exported headers, generated SFD headers, or package config files.
- Do not treat a missing component-local `build/` directory as a failure in this repo; the superbuild is allowed to create build trees lazily.

