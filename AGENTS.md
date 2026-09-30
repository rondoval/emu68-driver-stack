# emu68-driver-stack — Agent Notes

Guidance for AI coding agents working in this repository (the top-level superbuild).

## Platform

AmigaOS 3.x driver stack for a classic Amiga with a **PiStorm accelerator + Raspberry Pi 4 / CM4** running the **Emu68** m68k JIT emulator. All code is cross-compiled to 68040 (`/opt/m68k-amigaos` toolchain) with `-ffreestanding -nostdlib -nostartfiles`. Emu68 exposes RPi4 peripherals (GIC-400, BCM GENET, BCM2711 PCIe, VL805 xHCI, NVMe) via a device tree.

Components are git submodules under `components/`: `devicetree.resource`, `mailbox.resource`, `emu68-common`, `emu68-gic400-library`, `emu68-pcie-library`, `emu68-xhci-driver-context`, `emu68-xhci-driver-legacy`, `emu68-genet-driver-netdev`, `emu68-genet-driver-sana2`, `emu68-nvme-driver`, `lwip-amiga`.

## Build

**All builds run inside the toolchain container via `./scripts/docker-build.sh` —
never invoke `cmake` on the host, and never build a component standalone from its
own directory.** The shared `build/` tree is configured at `/work` inside the
container image (`ghcr.io/rondoval/amiga-build-container:gcc-v16.2`, NDK 3.2, ships
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

- `pistorm` — magic `0xdeadbeef` (Emu68 trap). ROM-able.
- `serial`  — Exec `RawPutChar`, the `kprintf` path: serial port, or whatever
  redirects it (Sashimi). ROM-able.
- `off`     — debug compiled out (smallest binaries).

Both sinks format with emu68-common's `fmt_vformat` (C argument rules — `%d` is
32-bit, no `l` needed — and no Exec call). The serial sink is the one place that
takes `SysBase` from address 4 — debug printing has no context to carry it.

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

Never read the Exec base from address 4: on PiStorm that is an Amiga-bus cycle
(~1.5 µs) per Exec call. Every `.c` file opens, before any include, with:

```c
#define __NOLIBBASE__
#define EXEC_BASE_NAME SysBase /* a local in every function, from its context's sysBase */
```

and every function that calls Exec — `pool_*`, `cache_pre_dma`/`cache_post_dma`
and other emu68-common macros included — starts with
`struct ExecBase *SysBase = p->sysBase;`, where `p` is one of its own
parameters. The base is stored once, from the init function's a6, in the device
or library base, and copied into each context struct when it is created (unit,
controller, ring, request, …), so reaching it is always one hop. Interrupt
servers and init functions name their a6 parameter `SysBase`. A header
`static inline` that calls Exec does the same from its own context parameter
(an inline body sees no caller locals, but every includer binds `SysBase`).

`__NOLIBBASE__` must come first: without it `proto/exec.h` declares a global
`SysBase`, and a missing local compiles silently against it (it then fails only
at link time, as these targets have no such symbol).

The rule is a review rule, not a build-enforced one. Only a handful of places
may read address 4, each for a stated reason: the serial debug sink and the
nvme mounter's boot point.

### Compiler warning flags

All components are built with `-Wall -Wconversion -Wsign-conversion -Wshadow
-Wmissing-prototypes -Wstrict-prototypes`. Compliance rules:

- All size/count arithmetic must use `ULONG` — avoid mixing `s32` `min()`/`max()` with unsigned operands; use the ternary operator instead.
- Every non-`static` function needs a visible prototype at its definition site (include the relevant header in the `.c` file).
- Functions with no parameters must be declared `f(void)`.

### Module layout and LTO

Two per-target calls that look like flags but are not, so they do not break the "state a flag at
exactly one level" rule:

- `emu68_module_layout(<target> [WRITABLE])` links the module through
  `components/emu68-common/ldscripts/module.lds`. That script is the module contract:
  `.text.entry` (the `doNotExecute` stub, which `LoadSeg()` runs at offset 0) and `.text.modhdr`
  (the romtag) are placed first, `_endOfCode` is defined at the true end of `.text` so
  `RT_ENDSKIP` bounds the whole module, and a link-time `ASSERT` rejects any writable section.
  Pin the stub and the romtag with `__attribute__((used, section(".text.entry")))` /
  `(".text.modhdr")`. The stub is checked to be `moveq #-1,d0; rts` and there is no way to
  waive that, so a stub that wants to do more must still start with the `moveq`. `used` is load-bearing and `ENTRY()` is **not** a substitute: it is not an
  LTO root, and without it the plugin discards the whole module and still emits a valid, empty
  HUNK file. Pass `WRITABLE` only for a module that is never placed in ROM.
- `emu68_enable_lto(<target>)` sets CMake's `INTERPROCEDURAL_OPTIMIZATION` property. **Never write
  `-flto` by hand.** A TU whose payload is file-scope `asm()` must opt out with
  `emu68_lto_keep_real_objects(<t> <src>…)`: LTO's symbol table cannot see a symbol defined only
  inside an asm string, so the definition is silently dropped and the link fails with an undefined
  reference (verified, not assumed), and which partition it would land in is unspecified.
  Two rules before reaching for it:
  **(1) Should it be a `.c` at all?** Only if the asm needs the C compiler — `offsetof()` fed
  through `"i"` operands. Without those, write it as `.S`: assembly never enters LTO, so there is
  no exception to state. `gic400_dispatch.c` and genet-sana2's `bcmgenet-isr.c` need C;
  `mounter/bootpoint.S` did not, and converting it removed poseidon's last exception outright.
  **(2) Is the file the asm block and nothing else?** A TU that opts out takes everything in it
  out, so split the block off rather than excluding the file it grew up in.
  (`emu68-common`'s `memory.c` opts out for its own reason; see its `CMakeLists.txt`.) An
  interrupt server is **not** a reason to opt out.
- An Exec interrupt server is marked `EMU68_INTSERVER(<name>)` (`<intserver.h>`), which gives it a
  `.text.isr.<name>` section of its own, and named in `emu68_isr_z_check(<t> SERVERS <name>…)`.
  The check slices the server out of the **linked** module — the map gives a section's address and
  size whatever the symbol's linkage, where HUNK has no symbols and most servers are `static` — and
  fails the build if any exit path leaves Z from something other than D0, if the server tail-calls
  out of itself, or if a server ships undeclared. It therefore checks the bytes that ship, with LTO
  on or off. A server written in file-scope `asm()` says `.section .text.isr.<name>,"ax"` itself,
  and must hand `.text` back at the end: GCC emits a top-level `asm()` before any function body and
  tracks the current section itself, so without that the rest of the TU lands in the server's
  section.
- **GCC synthesises `memcpy`/`memset`/`memmove`/`memcmp` calls during *ltrans* codegen**, after
  the IR phase has ended. `ld` can still satisfy such a late reference out of `libcommon.a` — the
  bsdsocket map shows all three pulled by an `ltransN.ltrans.o`, not by anything in the IR — but
  only when the archive member is a **real object**, because an IR member can no longer be
  compiled by then. That is the whole reason `emu68-common/src/memory.c` is `-fno-lto` and why its
  assembly siblings `memcpy_movem.S`/`memset_movem.S` never needed anything: tested both ways on
  gcc 16.2, LTO'ing `memory.c` ends in `undefined reference to memcmp`, and
  `__attribute__((used))` does **not** fix it — the body is not being dropped, the member cannot
  be codegen'd.

`EMU68_LTO` defaults to ON and is forwarded to every component. A native `/opt/m68k-amigaos` build
cannot do LTO — its binutils was configured `--disable-plugins`, so any LTO object inside a `.a`
becomes an undefined reference; `check_ipo_supported()` detects that and warns rather than failing.

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
