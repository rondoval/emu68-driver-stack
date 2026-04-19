# emu68-driver-stack

Top-level superbuild for the Emu68 AmigaOS driver stack.

This project builds the full stack into one driver-stack prefix.  All component
repositories are included as git submodules under `components/`.

## Components

- `devicetree.resource`
- `mailbox.resource`
- `emu68-common`
- `emu68-gic400-library`
- `emu68-pcie-library`
- `emu68-xhci-driver`
- `emu68-genet-driver`

## Output layout

| Path | Contents |
|---|---|
| `install/LIBS/` | `gic400.library`, `bcmpcie.library`, `openpci.library` |
| `install/DEVS/USBHardware/` | `xhci.device` |
| `install/DEVS/Networks/` | `genet.device` |
| `install/C/` | `lspci` |
| `install/Developer/` | Public headers and SFD files |
| `install/include/`, `install/lib/` | Build-time headers and static libraries |

## Assumptions

- Bebbo's AmigaOS cross-toolchain is installed under `/opt/m68k-amigaos`

## Building

### Fresh clone

```sh
git clone --recurse-submodules https://github.com/rondoval/emu68-driver-stack.git
cd emu68-driver-stack
cmake -S . -B build
cmake --build build
```

### Existing clone without submodules

```sh
git submodule update --init --recursive
cmake -S . -B build
cmake --build build
```

## Local development — working on an individual component

Override any component's source directory to point to your own checkout:

```sh
cmake -S . -B build -D EMU68_XHCI_SOURCE_DIR=/home/user/emu68-xhci-driver
cmake --build build
```

The override is cached in `build/CMakeCache.txt` and applies to all subsequent
builds until cleared.  The submodule under `components/` is ignored for any
overridden component.  All other overridable variables follow the same
`<COMPONENT>_SOURCE_DIR` naming pattern (see `CMakeLists.txt`).

## Versioning

Component submodule pointers in this repository always track a release tag of
each component.  To update a component to a new release:

```sh
git -C components/emu68-xhci-driver checkout v4.1.0
git add components/emu68-xhci-driver
git commit -m "Bump emu68-xhci-driver to v4.1.0"
```

## Creating a release package

Requires `lhasa` (`apt install lhasa` or equivalent):

```sh
cmake --build build --target package
```

This produces `build/package/emu68-drivers-<version>.lha` containing the
runtime binaries and the Commodore Installer script.

## Custom install prefix

```sh
cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/path/to/prefix
cmake --build build
```
