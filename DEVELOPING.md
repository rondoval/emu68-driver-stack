# Developing the Emu68 driver stack

This repository is a CMake superbuild. Every component is a git submodule under
`components/`, and the whole stack builds into one shared install prefix:

| Component | Ships as |
|---|---|
| `devicetree.resource` | build-only — parses Emu68's device tree, where hardware discovery starts |
| `mailbox.resource` | build-only — VideoCore mailbox, reloads the VL805 USB firmware |
| `emu68-common` | static library + the `emu68check` capability probe |
| `emu68-gic400-library` | `gic400.library` |
| `emu68-pcie-library` | `bcmpcie.library`, `openpci.library`, `lspci` |
| `emu68-xhci-driver-context` | `xhci.device` 6.x (context HCD ABI, Poseidon for AmigaOS 6.x) |
| `emu68-xhci-driver-legacy` | `xhci.device` 5.x (classic Poseidon HCD ABI) |
| `lwip-amiga` | `bsdsocket.library`, `netdev-stats`, `netinfo`, `mdns` — the TCP/IP stack, and the `netdev` NIC ABI it defines |
| `emu68-genet-driver-netdev` | `genet.device` 4.x (netdev) |
| `emu68-genet-driver-sana2` | `genet.device` 3.x (SANA-II), `genet-stats` |
| `emu68-nvme-driver` | `nvme.device`, `nvmeinfo`, `nvmeadm` |

`lwip-amiga` exports the `netdev` contract that `genet.device` 4.x implements,
so it builds before it. Two pairs above are two branches of one upstream repo:
`emu68-xhci-driver` (`context_release` / `main`) and `emu68-genet-driver`
(`netdev_release` / `main`).

## Quick start

**Build in the toolchain container** — no local m68k toolchain needed.
`scripts/docker-build.sh` runs the same image CI does, and carries the `lha`
archiver the `package` target needs.

```sh
git clone --recurse-submodules https://github.com/rondoval/emu68-driver-stack.git
cd emu68-driver-stack
./scripts/docker-build.sh                        # configure + build everything
./scripts/docker-build.sh --target lwip-amiga    # one component
./scripts/docker-build.sh --target package       # ...and make the .lha
```

Build outputs land in `build/` and `install/` on the host, owned by your user.
Positional arguments are forwarded to `cmake --build`; configure-time options go
through `EMU68_CONFIGURE_ARGS`.

The `build/` tree is configured at `/work` *inside* the container, so a
host-side `cmake -S . -B build` fails on a CMakeCache path mismatch and
reconfiguring on the host clobbers the container's cache. Always go through the
wrapper. (A native build against a local Bebbo toolchain at
`/opt/m68k-amigaos` does work, but only into its own separate build directory.)

Every build ends with `scripts/check-regargs.py`, which fails the build if a
function declaring `asm("aN")` parameters was emitted with the stack calling
convention — gcc 16.1 does that silently when a prototype sees a parameter's
struct as incomplete. `EMU68_SKIP_ABI_CHECK=1` skips it.

## Build options

All are configure-time CMake cache variables, passed via `EMU68_CONFIGURE_ARGS`:

```sh
EMU68_CONFIGURE_ARGS="-DEMU68_DEBUG_BACKEND=serial" ./scripts/docker-build.sh
```

| Variable | Default | Values / meaning |
|---|---|---|
| `EMU68_DEBUG_BACKEND` | `pistorm` | Where debug output goes, stack-wide. `pistorm` = `RawDoFmt` to magic address `0xdeadbeef`, trapped by Emu68. `serial` = `debug.lib` `KPutChar` to the Amiga serial port @ 9600. `off` = compiled out; nothing is emitted whatever the tiers say. |
| `EMU68_TIER` | `debug` | Stack-wide baseline for *what* is emitted. Cumulative ladder: `off` → `profile` (timing probes + `perf_report`) → `debug` (`+` asserts and logging) → `trace` (`+` verbose per-operation logging). |
| `EMU68_PROFILE`, `EMU68_DEBUG`, `EMU68_TRACE` | empty | Pin individual components to a rung above the baseline. Each takes a CMake list of component target names, or `ALL`. An unknown name, an unknown tier, or a component named in two lists fails at configure time. |
| `EMU68_FORCE_LVO_CACHE_OPS` | `OFF` | Cache-op flavor — see [below](#the-dcache-extensions). `OFF` emits the inline Emu68 range opcodes (the `-rangeops` archives); `ON` routes through exec's `CachePreDMA`/`CachePostDMA` (the standard archives). |
| `M68K_CPU` | `68040` | `68000` `68010` `68020` `68040` `68060` `68080` |
| `M68K_FPU` | `hard` | `hard` `soft` |
| `M68K_CRT` | `nix20` | `nix20` `nix13` `clib2` `ixemul` `newlib` |
| `<COMPONENT>_SOURCE_DIR` | the submodule | Point a component at your own checkout, e.g. `-DEMU68_XHCI_CONTEXT_SOURCE_DIR=/path/to/checkout`. Cached in `build/CMakeCache.txt` until cleared; the submodule is then ignored for that component. |

Valid component names for the three tier lists and the source-dir overrides:
`emu68-common`, `emu68-gic400-library`, `emu68-pcie-library`,
`emu68-xhci-driver-context`, `emu68-xhci-driver-legacy`,
`emu68-genet-driver-netdev`, `emu68-genet-driver-sana2`, `emu68-nvme-driver`,
`lwip-amiga`.

```sh
# silent stack except the network stack's timing numbers — the tier to profile on:
# no logging overhead, and lwIP's asserts are gone, so the numbers track release
EMU68_CONFIGURE_ARGS="-DEMU68_TIER=off -DEMU68_PROFILE=lwip-amiga" ./scripts/docker-build.sh
```

Profile-tier output is what `components/emu68-common/scripts/perf-report.py`
reduces; capture a run and pipe it through that. Scope `trace` to the component
you are debugging — stack-wide it swamps the debug console and slows the hot
paths.

Two things that bite:

- **`serial` binaries are not ROM-able.** `debug.lib` carries a 4-byte writable
  `_SysBase`, so those builds skip the ROM check. `pistorm` and `off` stay
  ROM-able, and the drivers must keep no other writable data.
- **Never put `-m68040` / `-mhard-float` / `-fomit-frame-pointer` in a
  component's `add_compile_options()`.** `cmake/toolchain.cmake` owns the
  code-generation flags for the whole stack, and target options are emitted
  *after* `CMAKE_C_FLAGS` — GCC takes the last `-m<cpu>`, so a hardcoded one
  silently overrides `M68K_CPU`. `68040` is the only combination built and
  tested for release.

## Developer loop — build and upload to a live Amiga

`./build.sh` wraps `scripts/docker-build.sh` and adds an upload of the freshly
built binaries to a running Amiga over Cloanto Amiga Explorer (`AE.exe`, driven
from WSL). With no flags it does build + upload.

```sh
./build.sh                       # build, then upload (the usual loop)
./build.sh --build               # build only
BACKEND=off ./build.sh --package # release build + build/package/emu68-drivers-<ver>.lha
./build.sh --upload --dry-run    # preview the LIBS:/DEVS:/C: copy plan, copy nothing
```

It exposes the options above as environment knobs — `BACKEND=`, `FLAVOR=`,
`TIER=`, `PROFILE=`/`DEBUG=`/`TRACE=`, `BUILD_DIR=`, `INSTALL_DIR=` — and passes
them on every configure, so a reused build directory cannot keep a stale cached
value. Run `./build.sh --help` for the full list. The upload copies the runtime
trees only (`install/{LIBS,DEVS,C}`); for a first-time or full install use the
`.lha` and the Installer.

## Output layout

| Path | Contents |
|---|---|
| `install/LIBS/` | `gic400.library`, `bcmpcie.library`, `openpci.library`, `bsdsocket.library` |
| `install/DEVS/` | `nvme.device` |
| `install/DEVS/USBHardware/` | `xhci.device` (the 6.x context line) |
| `install/DEVS/Networks/` | `genet.device` (the 4.x netdev line) |
| `install/C/` | `lspci`, `nvmeadm`, `nvmeinfo`, `netdev-stats`, `netinfo`, `mdns`, `emu68check` (installer support — run from the archive, never copied to `C:`) |
| `install/Storage/` | The alternate driver lines, parked for the Installer to choose: `DEVS/USBHardware/xhci.device` (5.x legacy) and `DEVS/Networks/genet.device` + `C/genet-stats` (SANA-II 3.x) |
| `install/ENVARC/` | `netstack.prefs.default` — the lwip-amiga config template the Installer copies to `ENVARC:` when no prefs exist |
| `install/Developer/` | Public headers and SFD files |
| `install/include/`, `install/lib/` | Build-time headers and static libraries, including the `netdev` ABI header and its CMake package |

`xhci.device` and `genet.device` each ship in two mutually exclusive lines: same
filename, same slot, so only one can be installed. The default line installs to
its real path and the alternate is parked under `Storage/`; the Installer asks
which. `sockbench` (the lwip-amiga throughput bench) and `diskbench` (the
xhci-context mass-storage bench) are built but deliberately not installed, so
they stay out of the shipped package.

## The dcache extensions

`emu68-common`'s `cache_ops.h` emits its `cache_pre_dma()` / `cache_post_dma()`
range operations inline, through a private LINE-F opcode that only a patched
Emu68 decodes. `EMU68_FORCE_LVO_CACHE_OPS=ON` routes them back through exec's
`CachePreDMA` / `CachePostDMA` instead, which runs on any Emu68 from 1.1
alpha.1 on. Both settings ship — every release publishes four archives:

| Archive | Flavor | Firmware |
|---|---|---|
| `emu68-drivers-<ver>.lha` | LVO (`ON`) | Emu68 1.1 alpha.1 or newer — slow without the dcache extensions, see below |
| `emu68-drivers-<ver>-rangeops.lha` | inline (`OFF`) | a custom Emu68 build with the dcache extensions |

…each also built with `EMU68_DEBUG_BACKEND=serial`, which appends `-serial` to
the name. That is the whole 4-leg matrix.

The extensions are **out of tree**: our own addition to Emu68's JIT, with no
upstream PR yet and no guarantee one would be accepted, so `-rangeops` binaries
need [a custom Emu68 build](https://github.com/rondoval/Emu68/releases/tag/v1.1-alpha-with-rangeops).
User-facing text must say "a custom Emu68 build", never "update Emu68".

**This is a throughput axis, not only a compatibility one.** The standard
archive runs on any supported Emu68, but "runs" is not "runs well" — measured
TCP throughput, netdev `genet.device` + `bsdsocket.library` on a gigabit LAN:

| Drivers | Emu68 | TCP RX | TCP TX |
|---|---|---|---|
| standard (LVO) | official build, **no** dcache extensions | 104 Mb/s | 79 Mb/s |
| standard (LVO) | custom build with the extensions | 698 Mb/s | 477 Mb/s |
| `-rangeops` | custom build with the extensions | near line rate | near line rate |

The LVO path calls exec's `CachePreDMA`/`CachePostDMA`, which the
`68040.library` embedded in the Emu68 image patches. Without the dcache
extensions that library walks the buffer in emulated 68k code, one
`cpushl dc,(An)` per 32-byte cache line — roughly 47 JIT-executed instructions
per 1500-byte frame, on every frame. With the extensions it emits a single range
opcode that the JIT expands into a native ARM loop, which is the ~6× jump in the
middle row; the `-rangeops` build then emits that same opcode inline at the call
site, dropping the exec LVO round-trip too.

**Consequence for the driver lines.** The stack's DMA paths are built around
cache maintenance being cheap and fine-grained. On an Emu68 without the
extensions that assumption inverts, and the netdev `genet.device` 4.x +
lwip-amiga stack ends up **slower than the SANA-II `genet.device` 3.x line**.
That is the situation on stock Emu68, so it is the default user-facing advice —
see [README.md](README.md#what-to-download-and-install).

Mechanics:

- An Emu68 with the extensions advertises the opcode as the `/emu68`
  device-tree property `dcache-range-ops`. Drivers built with the inline path
  check it at device init (`emu68_has_dcache_range_ops()`, `emu68_features.h`)
  and refuse to load — rather than Line-F trap — on firmware without it.
- The flag is forwarded only to the components that include `cache_ops.h`:
  `emu68-xhci-driver-context`, `emu68-genet-driver-netdev` and
  `emu68-nvme-driver`. It has no effect on the rest of the stack.
- **The archive suffix is inverted relative to the default.** CMake defaults to
  `OFF` and `build.sh` to `FLAVOR=rangeops`, so a plain local build produces a
  `-rangeops` archive — while the *unsuffixed* published archive is the LVO one,
  which keeps the historical name.
- CI (`build.yml`) and releases (`release.yml`) build both flavors across the
  `off` and `serial` backends — the full 4-leg matrix.

## Packaging

```sh
./scripts/docker-build.sh --target package
```

Produces `build/package/emu68-drivers-<version>.lha`, containing the runtime
binaries (`LIBS/`, `DEVS/`, `C/`, `Storage/`, `ENVARC/`) alongside the Installer
script, so the installer runs directly from the unpacked archive. It also
bundles, for licence completeness and self-documentation:

- `Documentation/<component>/` — each component's `README.md`, `LICENSE` and
  release notes;
- `Licenses` — a generated summary mapping every component and shipped binary to
  its licence;
- `RELEASE-NOTES.md` — the top-level changelog.

The package version comes from `project(emu68_driver_stack VERSION ...)` in
`CMakeLists.txt` and is stamped into the installer's `Install` and `ReadMe`,
generated from `installer/*.in`. **Edit the templates, never the generated
files** — the copies under `build/` are overwritten on every configure.

Packaging needs the `lha` archiver. It ships in the toolchain image; for a
native build, install one yourself.

## Versioning and releasing

Submodule pointers in this repository always track a component release tag:

```sh
git -C components/emu68-xhci-driver-context checkout v6.0
git add components/emu68-xhci-driver-context
git commit -m "Bump emu68-xhci-driver-context to v6.0"
```

**Every** pull request — in a component repo or this one — is gated by CI on
three checks: the CMake `project(... VERSION ...)` is bumped, `RELEASE-NOTES.md`
is updated, and the code compiles cleanly.

**Per component repo** (only those that changed): update its `RELEASE-NOTES.md`
(newest entry on top), bump its `project(... VERSION ...)`, and open a PR — CI
builds the stack with that component's source overridden
(`.github/workflows/component-versioning.yml`). Merging auto-creates the
`v<version>` tag. Component repos publish no GitHub Releases; the tag is the
stable point this repo's submodule pointer tracks. Note tags are cut on `main`,
`netdev_release` **and** `context_release` — which is how `genet.device` ships
3.x and 4.x, and `xhci.device` 5.x and 6.x, from one repo each.

**This (stack) repo — a single release PR:**

1. Bump each changed submodule pointer to its new component tag.
2. Bump the stack version in `CMakeLists.txt`.
3. Update [`RELEASE-NOTES.md`](RELEASE-NOTES.md): refresh the component-versions
   table and headlines, linking each component's tagged `RELEASE-NOTES.md`, and
   append the new stack version on top. It ships at the top of the archive —
   write it for the people installing the drivers, not for maintainers.
4. Update `installer/ReadMe.in` / `installer/Install.in` only if components were
   added or removed.
5. Open the PR (`build.yml` + `release-checks.yml` apply the same three gates),
   then merge.
6. **Tag the release manually** and push it:
   ```sh
   git tag v<stack-version> && git push origin v<stack-version>
   ```
   The tag triggers `.github/workflows/release.yml`, which builds the 4-leg
   matrix, runs the `package` target, and publishes the GitHub Release with all
   four `.lha` files — with `installer/VERSIONS.txt` as the release body.
