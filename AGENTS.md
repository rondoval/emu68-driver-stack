# emu68-driver-stack — Agent Notes

Guidance for AI coding agents working in this repository (the top-level superbuild).

## Platform

AmigaOS 3.x driver stack for a classic Amiga with a **PiStorm accelerator + Raspberry Pi 4 / CM4** running the **Emu68** m68k JIT emulator. All code is cross-compiled to 68040 (`/opt/m68k-amigaos` toolchain) with `-ffreestanding -nostdlib -nostartfiles`. Emu68 exposes RPi4 peripherals (GIC-400, BCM GENET, BCM2711 PCIe, VL805 xHCI, NVMe) via a device tree.

Components are git submodules under `components/`: `devicetree.resource`, `mailbox.resource`, `emu68-common`, `emu68-gic400-library`, `emu68-pcie-library`, `emu68-xhci-driver-context`, `emu68-xhci-driver-legacy`, `emu68-genet-driver-netdev`, `emu68-genet-driver-sana2`, `emu68-nvme-driver`, `lwip-amiga`.

## Build

**All builds run inside the toolchain container via `./scripts/docker-build.sh` —
never invoke `cmake` on the host, and never build a component standalone from its
own directory.** The shared `build/` tree is configured at `/work` inside the
container image (`ghcr.io/rondoval/amiga-build-container:latest`, NDK 3.2, ships
`lha`), so a host-side `cmake --build build` fails with a CMakeCache path
mismatch, and reconfiguring on the host would clobber the container cache.

```sh
./scripts/docker-build.sh                        # configure + build everything
./scripts/docker-build.sh --target lwip-amiga    # one component (superbuild target name)
./scripts/docker-build.sh --target package       # build + package build/package/emu68-drivers-<version>.lha
```

Arguments are forwarded to `cmake --build`; configure-time knobs go through the
environment, e.g. `EMU68_CONFIGURE_ARGS="-DEMU68_DEBUG_BACKEND=serial"
./scripts/docker-build.sh` (see the script header for `EMU68_BUILD_DIR` /
`EMU68_INSTALL_DIR` side-by-side builds). To override one component's source
during a superbuild:
`EMU68_CONFIGURE_ARGS="-DEMU68_XHCI_CONTEXT_SOURCE_DIR=/path/to/checkout" ./scripts/docker-build.sh`.

CI (`.github/workflows/`) runs this exact wrapper, so a green local
`docker-build.sh` matches CI.

Every build ends with `scripts/check-regargs.py`, which fails the build if a
function declaring `asm("aN")` parameters was emitted with the stack calling
convention. gcc 16.1 does that **silently** when a prototype sees a parameter's
struct as incomplete and the definition later sees it complete, so keep such a
struct complete before any prototype that names it. `EMU68_SKIP_ABI_CHECK=1`
skips the check.

For the edit-build-test loop, `./build.sh` (repo root) wraps `docker-build.sh`
and adds an upload to a live Amiga over `AE.exe`: no flags = build + upload;
`--build`, `--package`, `--upload`, `--dry-run`; knobs `BACKEND=`, `FLAVOR=`,
`TIER=`, and the per-component `PROFILE=`/`DEBUG=`/`TRACE=` lists. See
`./build.sh --help`.

The package version comes from `CMakeLists.txt` `project(... VERSION)` and is
stamped into `installer/Install`/`ReadMe`, generated from the `*.in` templates
(`@PACKAGE_VERSION@`, ...) — edit the templates, not the generated files.

After editing a C file, build the affected target to confirm zero errors and
zero warnings before reporting the task done.

### Debug output backend

`EMU68_DEBUG_BACKEND` (default `pistorm`) selects the debug sink for the whole
stack, propagated to every component:

- `pistorm` — `RawDoFmt` → magic `0xdeadbeef` (Emu68 trap). ROM-able.
- `serial`  — `debug.lib` `KPutChar` → AmigaOS serial console @ 9600. **Not**
  ROM-able (links a 4-byte `_SysBase` `.bss`).
- `off`     — debug compiled out (smallest binaries).

Mechanism lives in `emu68-common` (`include/debug.h` + the shared
`cmake/Emu68CommonDebug.cmake` module) — see that component's own docs.

### Cache-op flavor

`EMU68_FORCE_LVO_CACHE_OPS` (`FLAVOR=lvo|rangeops` via `build.sh`) picks
between exec `CachePreDMA`/`CachePostDMA` and the inline Emu68 range opcodes;
releases ship both. Note this is a throughput axis, not only a compatibility
one: on an Emu68 *without* the dcache extensions every cache-maintenance call
degrades to a per-32-byte-line `cpushl` loop in emulated 68k code, which drops
netdev `genet.device` TCP from 698/477 to 104/79 Mb/s and makes it slower than
the SANA-II line. The extensions are **out of tree** — our own Emu68 change,
no upstream PR — so rangeops needs
[a custom Emu68 build](https://github.com/rondoval/Emu68/releases/tag/v1.1-alpha-with-rangeops);
never write "update Emu68" in user-facing text. Read
[*The dcache extensions*](DEVELOPING.md#the-dcache-extensions) before advising
on driver lines or reading benchmark numbers.

## Dependency Order

When rebuilding manually after API or layout changes:

1. `devicetree.resource`
2. `mailbox.resource`
3. `emu68-common`
4. `emu68-gic400-library`, `lwip-amiga`
5. `emu68-pcie-library`
6. `emu68-xhci-driver-context`, `emu68-xhci-driver-legacy`, `emu68-nvme-driver`, `emu68-genet-driver-netdev`, `emu68-genet-driver-sana2` (parallel)

## Component Summary

| Component | What it is |
|---|---|
| `devicetree.resource` | Parses Emu68's device tree; all hardware discovery starts here |
| `mailbox.resource` | VideoCore mailbox; needed to reload VL805 USB firmware via the GPU |
| `emu68-common` | Shared utilities: debug output, DMA-aligned memory, iomem helpers, devicetree wrappers, the `emu68check` capability-probe tool |
| `emu68-gic400-library` | AmigaOS library wrapping the ARM GIC-400; drives MSI and all hardware interrupts |
| `emu68-pcie-library` | BCM2711 STB PCIe controller bring-up, BAR assignment, MSI, openpci API |
| `emu68-xhci-driver-context` | USB xHCI device driver, 6.x line — speaks the context HCD ABI only, a **matched pair** with the `poseidon-backport` repo (ABI evolution governed by that repo's `docs/poseidon-context-hcd-abi.md` + `docs/implementation-plan.md`). Branch `context_release`. |
| `emu68-xhci-driver-legacy` | The same repo's 5.x line (branch `main`), speaking the classic Poseidon HCD ABI. Required on Poseidon 4.x; also runs on 6.x (dual-ABI) but without real USB 3.0 or streams. Installs under `Storage/` so its `xhci.device` does not collide with the context line's. |
| `lwip-amiga` | TCP/IP stack — lwIP core plus `bsdsocket.library`; drives NICs over the netdev ABI |
| `emu68-genet-driver-netdev` | Ethernet driver for BCM GENET v5; speaks the netdev ABI (`lwip-amiga`), not SANA-II. Its SANA-II sibling `emu68-genet-driver-sana2` (branch `main`) tracks the same repo for the 3.x line. |
| `emu68-nvme-driver` | NVMe device driver; Linux kernel NVMe core adapted to AmigaOS |

## Memory Allocation

Only Emu68 Fast RAM (the Pi's own DRAM, advertised in the device-tree `/memory`
node and added to Exec by `devicetree.resource` as high-priority "expansion
memory") is DMA-reachable; Chip RAM and Zorro III / accelerator Fast RAM are
not. Three allocation layers live in `emu68-common`:

| API | Header | Use for |
|---|---|---|
| `pool_alloc` / `pool_free` (and `pool_zalloc`) | `memory.h` | Non-DMA structs from the driver's Exec pool |
| `dma_alloc` / `dma_free` (and `dma_zalloc`) | `dma_mem.h` | One-off DMA buffers from a region pool |
| `slab_alloc` / `slab_free` | `slab.h` | Hot-path fixed-size DMA objects; `slab_cache` is embedded in the device struct, init'd once, destroyed on teardown |

`dma_mem.h` is the DMA-reachability layer: `dma_addr_reachable()` is the
transport-agnostic bounce-buffer predicate, and a `struct dma_pool *` from
`dma_pool_create()` is guaranteed to allocate inside Emu68 RAM even under memory
pressure. `dma_alloc` stores bookkeeping just before the returned aligned
address, so free it only with `dma_free` — never `dma_pool_region_free` or
`FreePooled`. See `emu68-common`'s own README for the full signatures.

## Driver Source Conventions

### Mandatory include pattern for every driver `.c` file

Every `.c` file that uses Exec or the `memory.h` inline functions must open with:

```c
#ifdef __INTELLISENSE__
#include <clib/exec_protos.h>
#else
#define __NOLIBBASE__
#define EXEC_BASE_NAME (*(struct ExecBase **)4UL)
#include <proto/exec.h>
#endif
```

The `__INTELLISENSE__` guard lets IDEs resolve symbols without the
Bebbo-specific `proto/exec.h` magic. Omitting `proto/exec.h` causes
`AllocPooled`/`FreePooled` implicit-declaration warnings when `memory.h` is included.

### Compiler warning flags

All components are built with `-Wall -Wconversion -Wsign-conversion -Wshadow
-Wmissing-prototypes -Wstrict-prototypes`. Compliance rules:

- All size/count arithmetic must use `ULONG` — avoid mixing `s32` `min()`/`max()` with unsigned operands; use the ternary operator instead.
- Every non-`static` function needs a visible prototype at its definition site (include the relevant header in the `.c` file).
- Functions with no parameters must be declared `f(void)`.

## Output Layout

See [*Output layout*](DEVELOPING.md#output-layout) — the single source. Two
things to keep in mind when touching install rules: `xhci.device` and
`genet.device` each ship in two mutually exclusive lines with the same
filename, the alternate parked under `install/Storage/` for the Installer to
choose; and `emu68check` ships in `C/` but is never copied to `C:`.

## Validation

- Prefer validating stack-wide from this repo when changes touch exported headers, generated SFD headers, or CMake package config files.
- If a downstream component stops configuring, verify the upstream component was rebuilt **and installed** into the shared prefix before investigating further.
- Do not treat a missing component-local `build/` directory as a failure; the superbuild is allowed to create build trees lazily.
- There is no automated test suite; correctness is verified on-device.
