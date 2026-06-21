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
- `emu68-nvme-driver`

## Output layout

| Path | Contents |
|---|---|
| `install/LIBS/` | `gic400.library`, `bcmpcie.library`, `openpci.library` |
| `install/DEVS/` | `nvme.device` |
| `install/DEVS/USBHardware/` | `xhci.device` |
| `install/DEVS/Networks/` | `genet.device` |
| `install/C/` | `lspci`, `nvmeadm`, `nvmeinfo`, `genet-stats` |
| `install/Developer/` | Public headers and SFD files |
| `install/include/`, `install/lib/` | Build-time headers and static libraries |

## Assumptions

- Bebbo's AmigaOS cross-toolchain is installed under `/opt/m68k-amigaos`
  — or use the Docker build below, which needs no local toolchain.

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

### Building with Docker (no local toolchain)

`scripts/docker-build.sh` runs the build inside the same cross-toolchain image CI
uses (`amigadev/crosstools:m68k-amigaos`), so no local `/opt/m68k-amigaos` install
is required. It also carries the `lha` archiver used by the `package` target.

```sh
git submodule update --init --recursive   # submodules are read from the host
./scripts/docker-build.sh                  # configure + build the whole stack
./scripts/docker-build.sh --target package # ...and create the .lha release archive
```

Build outputs land in `install/` and `build/` on the host, owned by your user (the
wrapper runs the container as your uid/gid). Pass extra configure-time options via
`EMU68_CONFIGURE_ARGS`, e.g. `EMU68_CONFIGURE_ARGS="-DEMU68_DEBUG_BACKEND=serial"`;
any positional arguments are forwarded to `cmake --build build`.

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

## Debug output backend

All components share one debug-output backend, selected at configure time with
the `EMU68_DEBUG_BACKEND` cache variable (default `pistorm`) and propagated to
every component so the whole image stays consistent:

| Value     | Debug output                                                          | ROM-able |
|-----------|-----------------------------------------------------------------------|----------|
| `pistorm` | `RawDoFmt` → magic address `0xdeadbeef`, trapped & printed by Emu68    | yes      |
| `serial`  | `debug.lib` `KPutChar` → Amiga serial port @ 9600 baud                | no¹      |
| `off`     | debug output compiled out                                             | yes      |

```sh
cmake -S . -B build -DEMU68_DEBUG_BACKEND=serial   # pistorm (default) | serial | off
cmake --build build
```

Switching the value reconfigures and rebuilds the affected components.  With
`serial`, debug output goes to the Amiga serial port (9600 baud) on real
hardware, or can be captured/redirected on a host with the Sashimi tool; use
`off` for the smallest binaries.

¹ The `serial` backend links `debug.lib`, which carries a 4-byte writable
`_SysBase`, so those binaries are intentionally **not** ROM-able and skip the ROM
check.  `pistorm` and `off` remain ROM-able.

### Verbose ("high") logging

The backend above selects *where* debug output goes; `EMU68_DEBUG_HIGH` selects
*how much*.  It enables the verbose `KprintfH` / `DEBUG_HIGH` tier (hot-path and
per-operation traces) on top of the normal `Kprintf` output, **per component**:

```sh
# verbose logging in just the PCIe library
cmake -S . -B build -DEMU68_DEBUG_HIGH=emu68-pcie-library

# verbose logging in several components (CMake list — semicolon-separated)
cmake -S . -B build "-DEMU68_DEBUG_HIGH=emu68-pcie-library;emu68-nvme-driver"

# verbose logging everywhere
cmake -S . -B build -DEMU68_DEBUG_HIGH=ALL
```

- Default is empty — verbose logging is **off** in every component.
- Value is a list of component target names, or `ALL` for every debug-emitting
  component.  Valid names: `emu68-common`, `emu68-gic400-library`,
  `emu68-pcie-library`, `emu68-xhci-driver`, `emu68-genet-driver`,
  `emu68-nvme-driver`.  An unknown name fails at configure time.
- Independent of the backend, but requires `EMU68_DEBUG_BACKEND != off` to emit
  anything — with the `off` backend there is no debug output to make verbose.

Scope it to the component you're debugging: `ALL` is noisy enough to swamp the
debug console (and slow the hot paths) across the whole stack.

## Versioning

Component submodule pointers in this repository always track a release tag of
each component.  To update a component to a new release:

```sh
git -C components/emu68-xhci-driver checkout v4.1.0
git add components/emu68-xhci-driver
git commit -m "Bump emu68-xhci-driver to v4.1.0"
```

## Creating a release package

```sh
cmake --build build --target package
# or, without a local toolchain:
./scripts/docker-build.sh --target package
```

This produces `build/package/emu68-drivers-<version>.lha`
containing the runtime binaries (`LIBS/`, `DEVS/`, `C/`) alongside the Installer script, so the installer can be run directly from the unpacked archive.
The package version is taken from the project version in `CMakeLists.txt` and stamped
into the installer's `Install` / `ReadMe` (generated from the `*.in` templates), so
there is a single version source.

Packaging needs the `lha` archiver. It ships in the toolchain image used by
`scripts/docker-build.sh`; for a native build, install an `lha` archiver yourself.

## Custom install prefix

```sh
cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/path/to/prefix
cmake --build build
```
