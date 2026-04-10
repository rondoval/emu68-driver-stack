# emu68-driver-stack Agent Notes

These instructions are specific to the top-level superbuild repo.

## Role

- This repo is the preferred validation point when a change touches installed headers, exported CMake packages, or more than one component.
- The superbuild assumes sibling repositories for `devicetree.resource`, `mailbox.resource`, `emu68-common`, `emu68-gic400-library`, `emu68-pcie-library`, `emu68-xhci-driver`, and `emu68-genet-driver`.
- Default driver-stack output goes under `install/`, including `install/Developer`, `install/include`, `install/lib`, `install/LIBS`, `install/DEVS`, and `install/C`.

## Build Flow

- Preferred rebuild commands:
  - `cmake -S . -B build`
  - `cmake --build build`
- The toolchain is expected under `/opt/m68k-amigaos`.
- The superbuild creates per-component build directories under `emu68-driver-stack/build/`; prefer this over ad hoc downstream rebuilds when interface changes are involved.

## Dependency Order

When rebuilding components manually after API or install-layout changes, use this order:

1. `devicetree.resource`
2. `mailbox.resource`
3. `emu68-common`
4. `emu68-gic400-library`
5. `emu68-pcie-library`
6. `emu68-xhci-driver`
7. `emu68-genet-driver`

## Validation

- If a downstream package stops configuring, check whether an upstream package was rebuilt and installed into the same prefix.
- Prefer validating stack-wide from here when changes affect exported headers, generated SFD headers, or package config files.
- Do not treat a missing component-local `build/` directory as a failure in this repo; the superbuild is allowed to create build trees lazily.

