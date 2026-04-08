# emu68-sdk

Top-level superbuild for the Emu68 AmigaOS driver stack.

This project always builds the full stack into one SDK prefix:

- `devicetree.resource`
- `emu68-common`
- `emu68-gic400-library`
- `emu68-pcie-library`
- `emu68-xhci-driver`
- `emu68-genet-driver`

By default the SDK build happens in a `build/` subdirectory and the installed SDK contents go into an `install/` subdirectory, so the generated files land under:

- `install/Developer/`
- `install/include/`
- `install/lib/`
- `install/LIBS/`
- `install/DEVS/`
- `install/C/`

## Assumptions

- all component repositories live next to this directory
- Bebbo's AmigaOS cross-toolchain is installed under `/opt/m68k-amigaos`

## Building

```sh
cmake -S . -B build
cmake --build build
```

That configures and installs every component into this SDK directory.

The component build trees are created under `build/` as part of the superbuild.

If you want the SDK output somewhere else:

```sh
cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/path/to/emu68-sdk
cmake --build build
```