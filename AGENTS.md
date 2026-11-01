# emu68-driver-stack — Agent Notes

Top-level superbuild of an AmigaOS 3.x driver stack for a classic Amiga with a **PiStorm + Raspberry Pi 4 / CM4** running the **Emu68** m68k JIT. Code is cross-compiled to 68040 with `-ffreestanding -nostdlib -nostartfiles`; Emu68 exposes the Pi's peripherals (GIC-400, GENET, BCM2711 PCIe, VL805 xHCI, NVMe, VideoCore) through a device tree. Options, layout, packaging and the release steps: [DEVELOPING.md](DEVELOPING.md).

## Components

Git submodules under `components/`, mostly with notes of their own. `add_stack_project()` in `CMakeLists.txt` holds the build order.

| Component | What it is |
|---|---|
| `emu68-common` | Shared utilities: debug output, DMA memory, iomem, devicetree wrappers, the `emu68check` probe |
| `emu68-gic400-library` | Library over the ARM GIC-400: MSI and all hardware interrupts |
| `emu68-pcie-library` | BCM2711 PCIe bring-up, BAR assignment, MSI, the openpci API |
| `emu68-xhci-driver-context` | `xhci.device` 6.x (branch `context_release`): Neptune's context HCD ABI only, a **matched pair** with the Neptune repo (`rondoval/neptune-usb-stack`, local checkout `neptune`), whose `docs/neptune-context-hcd-abi.md` and `docs/implementation-plan.md` govern the ABI |
| `emu68-xhci-driver-legacy` | `xhci-legacy.device` 5.x (branch `main`, same repo): classic V1/V2 HCD ABI, for Poseidon 4.x; also runs on Neptune, without real USB 3.0 or streams |
| `emu68-genet-driver-netdev` | `genet.device` 4.x: the netdev ABI, for `lwip-amiga`, not SANA-II |
| `emu68-genet-driver-sana2` | `genet.device` 3.x (branch `main`, same repo): SANA-II |
| `emu68-nvme-driver` | `nvme.device`: the Linux NVMe core adapted to AmigaOS |
| `lwip-amiga` | lwIP plus `bsdsocket.library`; drives NICs over the netdev ABI |
| `emu68-vchiq-library` | VideoCore: `vchiq.device`, `videocodec.library`, `videocore.audio`, `vcjpeg.datatype`, `VCGrab`; experimental, unticked in the Install script |

## Build

**Build only through `./scripts/docker-build.sh`: never `cmake` on the host, never a component from its own directory.** `build/` is configured at `/work` inside the container, so a host-side build fails on a CMakeCache path mismatch and a host reconfigure clobbers the cache. CI runs this same wrapper.

```sh
./scripts/docker-build.sh                        # configure + build everything
./scripts/docker-build.sh --target lwip-amiga    # one component (superbuild target name)
./scripts/docker-build.sh --target package       # + build/package/emu68-drivers-<version>.lha
```

Arguments go to `cmake --build`; configure-time options go through `EMU68_CONFIGURE_ARGS`.

- **`./build.sh` with no flags builds and uploads to a live Amiga.** Use `--build` for a build alone; `./build.sh --help` has the knobs.
- The wrapper never pulls: `proto/devicetree.h: No such file` means a stale image, so `docker pull ghcr.io/rondoval/amiga-build-container:gcc-v16.2` once. The `devicetree.resource`, `mailbox.resource`, `cma.resource` and Picasso96 headers come with that image.
- Edit `installer/*.in`, never the generated `Install` and `ReadMe`.
- After editing a C file, build the affected target and confirm zero errors and zero warnings before reporting done.

### Debug output and cache-op flavor

- `EMU68_DEBUG_BACKEND` (`pistorm`, `serial`, `off`) applies stack-wide; `emu68-common` owns the mechanism. `Kprintf` formats with `fmt_vformat`: C argument rules, so `%d` is 32-bit and needs no `l`.
- `EMU68_FORCE_LVO_CACHE_OPS` (`FLAVOR=lvo|rangeops` in `build.sh`) picks exec's cache calls or the inline Emu68 range opcodes; releases ship both. It decides throughput as well as compatibility: read [*The dcache extensions*](DEVELOPING.md#the-dcache-extensions) before advising on driver lines or reading benchmark numbers.
- Official Emu68 releases up to 1.1.0-beta.1 lack the extensions. User-facing text names a newer Emu68 or the custom build, never just "update Emu68".

## Driver source rules

### SysBase

Never read the Exec base from address 4: on PiStorm that is an Amiga-bus cycle (~1.5 µs) per call. Every driver `.c` file opens, before any include, with:

```c
#define __NOLIBBASE__
#define EXEC_BASE_NAME SysBase /* a local in every function, from its context's sysBase */
```

Every function that calls Exec, `pool_*`, `cache_pre_dma`/`cache_post_dma` and other emu68-common macros included, starts with `struct ExecBase *SysBase = p->sysBase;`, `p` being one of its parameters. The init function stores the base from a6 in the device or library base, and each context struct gets a copy when created. Interrupt servers and init functions name their a6 parameter `SysBase`; a header `static inline` binds it from its own context parameter.

`__NOLIBBASE__` comes first: without it a missing local compiles silently against a global `SysBase` and fails only at link time. No build check enforces this rule. Only the serial debug sink and the nvme mounter's boot point may read address 4.

### Warnings

All components build with `-Wall -Wconversion -Wsign-conversion -Wshadow -Wmissing-prototypes -Wstrict-prototypes`:

- Size and count arithmetic uses `ULONG`; don't mix `s32` `min()`/`max()` with unsigned operands, use a ternary.
- Every non-`static` function has a visible prototype at its definition; a function with no parameters is `f(void)`.

`cmake/toolchain.cmake` owns the code-generation flags: never put `-m68040`, `-mhard-float` or `-fomit-frame-pointer` in a component.

### Memory

Only Emu68 Fast RAM (the Pi's DRAM, the device tree's `/memory`) is DMA-reachable; Chip RAM and Zorro III or accelerator Fast RAM are not. Use `pool_alloc` for non-DMA structs, `dma_alloc` for DMA buffers and `slab_alloc` for hot-path fixed-size DMA objects. Free `dma_alloc` memory only with `dma_free`, never `dma_pool_region_free` or `FreePooled`. Signatures are in `emu68-common`'s README.

### Module layout and LTO

The reasons are in `emu68-common/cmake/` (`Emu68CommonModuleLayout.cmake`, `Emu68CommonLto.cmake`, `Emu68CommonIsrCheck.cmake`).

- **`emu68_module_layout(<target> [WRITABLE])`** links through `ldscripts/module.lds`, the module contract. Pin the entry stub and the romtag with `__attribute__((used, section(".text.entry")))` and `(".text.modhdr")`. `used` is load-bearing and `ENTRY()` is no substitute: without it LTO discards the module and still emits a valid, empty HUNK file. The stub must start with `moveq #-1,d0; rts`, with no waiver. Pass `WRITABLE` only for a module that never goes in ROM.
- **`emu68_enable_lto(<target>)`** is the only way in; never write `-flto`. `EMU68_LTO` defaults to ON. The native toolchain cannot do LTO, and the build warns rather than fails.
- **A TU whose payload is file-scope `asm()`** opts out with `emu68_lto_keep_real_objects(<t> <src>…)`, or its symbols vanish and the link fails. First ask whether it should be a `.S`: it needs C only for `offsetof()` through `"i"` operands. Then keep the block in a TU of its own, since opting out takes the whole TU. An interrupt server is no reason to opt out.
- **`emu68-common`'s `memory.c` stays a real object.** GCC synthesises `memcpy`, `memset`, `memmove` and `memcmp` calls at ltrans, when only a real archive member can satisfy them, and `__attribute__((used))` does not help.
- **An Exec interrupt server** is marked `EMU68_INTSERVER(<name>)` (`<intserver.h>`) and named in `emu68_isr_z_check(<t> SERVERS <name>…)`, which fails the build on the linked module if an exit leaves Z from anything but D0, a server tail-calls out, or a server ships undeclared. A server in file-scope `asm()` says `.section .text.isr.<name>,"ax"` itself and hands `.text` back at the end, or the rest of the TU lands in its section.

## Output layout

[*Output layout*](DEVELOPING.md#output-layout) is the single source. When touching install rules: `genet.device` ships in two lines with one filename, the alternate parked under `install/Storage/` for the Installer to choose, and `emu68check` ships in `C/` but is never copied to `C:`.

## Installer

- A new or renamed shipped file touches every list of them: `installer/Install.in` (the copy and its `getsize` line, and the summary and closing screens for a new topic), `installer/ReadMe.in`, the `package` target and `Licenses` map in `CMakeLists.txt`, the *Output layout* table and, for a new top-level drawer, `build.sh`'s `TREES`.
- `Install.in` opens with its text budget: a screen is at most ten lines of 50 columns, a choice label at most 40. The closing screen is already at ten lines.
- `AND` and `OR` take two operands: nest them.
- Every question comes before the summary screen, and nothing is written before it, except the newer-file question and the Installer's own `startup` confirmation, which need the copy phase.
- A query that must run in Pretend mode needs `(safe)`, or it returns 0 there.
- `emu68check`'s file queries look for a string only our build of that file carries; the string's first character must not recur in it.

## Validation

- Validate stack-wide from this repo when a change touches exported headers, generated SFD headers or CMake package config.
- If a downstream component stops configuring, check that the upstream one was rebuilt **and installed** into the shared prefix first.
- A missing component-local `build/` is no failure: the superbuild creates build trees lazily.
- No automated tests at this level; correctness is verified on-device. `emu68-vchiq-library` has an on-device suite in its `tests/`.
