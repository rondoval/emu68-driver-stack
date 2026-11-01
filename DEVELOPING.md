# Developing the Emu68 driver stack

This repository is a CMake superbuild: every component is a git submodule under
`components/`, and they all build into one shared install prefix. Each component
has its own README and release notes; this guide covers the stack as a whole.

| Component | Ships as |
|---|---|
| `emu68-common` | Support library, and the `emu68check` probe the installer runs |
| `emu68-gic400-library` | `gic400.library` |
| `emu68-pcie-library` | `bcmpcie.library`, `openpci.library`, `lspci` |
| `emu68-xhci-driver-context` | `xhci.device` 6.x, for Neptune |
| `emu68-xhci-driver-legacy` | `xhci-legacy.device` 5.x, for classic Poseidon 4.x; also runs on Neptune |
| `emu68-genet-driver-netdev` | `genet.device` 4.x, for the bundled stack |
| `emu68-genet-driver-sana2` | `genet.device` 3.x, for any SANA-II stack, and `genet-stats` |
| `emu68-nvme-driver` | `nvme.device`, `nvmeinfo`, `nvmeadm` |
| `lwip-amiga` | `bsdsocket.library`, the network tools, and the `netdev` interface `genet.device` 4.x implements |
| `emu68-vchiq-library` | The experimental VideoCore parts: `vchiq.device`, `videocodec.library`, `videocore.audio`, `vcjpeg.datatype`, `VCInfo`, `VCGrab` |

The two xhci components are branches of one repo, `emu68-xhci-driver`
(`context_release` and `main`), and the two genet ones of `emu68-genet-driver`
(`netdev_release` and `main`).

## Building

You need Docker and no local toolchain. `scripts/docker-build.sh` runs the image
CI uses, which carries the m68k compiler, the `lha` archiver, and the headers of
the Emu68 resources and Picasso96.

```sh
git clone --recurse-submodules https://github.com/rondoval/emu68-driver-stack.git
cd emu68-driver-stack
./scripts/docker-build.sh                        # build everything
./scripts/docker-build.sh --target lwip-amiga    # one component
./scripts/docker-build.sh --target package       # build, and make the .lha
```

The results land in `build/` and `install/`, owned by your user. Arguments are
passed on to `cmake --build`.

Always build through the wrapper. `build/` is configured at `/work` inside the
container, so `cmake` on the host fails on a path mismatch, and reconfiguring there
spoils the cache. A native build against a toolchain in `/opt/m68k-amigaos` needs a
build directory of its own, and has no link-time optimization.

If a build stops at `proto/devicetree.h: No such file`, your image is too old. The
wrapper never pulls, so run this once:

```sh
docker pull ghcr.io/rondoval/amiga-build-container:gcc-v16.2
```

### Trying a build on an Amiga

`./build.sh` wraps the same build and uploads the result to a running Amiga over
Cloanto Amiga Explorer (`AE.exe`, driven from WSL). With no flags it does both.

```sh
./build.sh                       # build, then upload: the usual loop
./build.sh --build               # build only
./build.sh --upload --dry-run    # show what would be copied, copy nothing
BACKEND=off ./build.sh --package # a silent build, and its .lha
```

It takes the options below as environment variables (`BACKEND=`, `FLAVOR=`, `TIER=`,
`PROFILE=`, `DEBUG=`, `TRACE=`, `LTO=` and more: see `./build.sh --help`), and passes
them on every configure, so a reused build directory cannot keep an old value.

The upload copies `install/{LIBS,DEVS,C,Tools,ENVARC}` and nothing else: it edits no
`S:User-Startup` and skips `Classes/` and `Storage/`. For a first or full install use
the `.lha` and the Installer.

Everything built here is marked as local: a `dev-<date>-<time>-g<hash>[-dirty]` stamp
ends up in each binary's `$VER`, the `.lha` name, the ReadMe and the Installer's first
screen. Releases come from CI and carry no stamp.

## Build options

These are CMake cache variables, set through `EMU68_CONFIGURE_ARGS`:

```sh
EMU68_CONFIGURE_ARGS="-DEMU68_DEBUG_BACKEND=serial" ./scripts/docker-build.sh
```

| Variable | Default | Meaning |
|---|---|---|
| `EMU68_DEBUG_BACKEND` | `pistorm` | Where debug output goes: see [below](#debug-output) |
| `EMU68_TIER` | `debug` | How much is emitted: see [below](#debug-output) |
| `EMU68_PROFILE`, `EMU68_DEBUG`, `EMU68_TRACE` | empty | Components to pin to a tier |
| `EMU68_FORCE_LVO_CACHE_OPS` | `OFF` | `ON` builds the standard archives, `OFF` the `-rangeops` ones: see [The dcache extensions](#the-dcache-extensions) |
| `EMU68_LTO` | `ON` | Link-time optimization |
| `EMU68_VCHIQ_TEST_HOOKS` | `OFF` | Test-only commands in `vchiq.device`, for `emu68-vchiq-library`'s test suite. Never for a release |
| `M68K_CPU` | `68040` | `68000` `68010` `68020` `68040` `68060` `68080` |
| `M68K_FPU` | `hard` | `hard` `soft` |
| `M68K_CRT` | `nix20` | `nix20` `nix13` `clib2` `ixemul` `newlib` |
| `EMU68_COMMON_SOURCE_DIR`, `EMU68_XHCI_CONTEXT_SOURCE_DIR`, ... | the submodule | Build a component from your own checkout instead. There is one per component (`LWIP_AMIGA_SOURCE_DIR` for the stack); it stays in `build/CMakeCache.txt` until you clear it |

Only 68040 with a hard FPU is built and tested for release. `cmake/toolchain.cmake`
owns the code-generation flags, so keep `-m68040`, `-mhard-float` and
`-fomit-frame-pointer` out of a component's own options: target options come last, and
GCC takes the last `-m<cpu>`, so a hardcoded one silently overrides `M68K_CPU`.

## Debug output

`EMU68_DEBUG_BACKEND` says where the output goes:

| Backend | Output |
|---|---|
| `pistorm` | The Emu68 debug console, through the magic address `0xdeadbeef` |
| `serial` | Exec's `RawPutChar`, the `kprintf` path: the Amiga serial port, or whatever redirects it (Sashimi) |
| `off` | Nothing, whatever the tiers say |

`EMU68_TIER` says how much. Each tier adds to the one before it:

| Tier | Adds |
|---|---|
| `off` | Nothing |
| `profile` | Timing probes and `perf_report` |
| `debug` | Asserts and logging |
| `trace` | Verbose logging of every operation |

`EMU68_PROFILE`, `EMU68_DEBUG` and `EMU68_TRACE` raise single components above that
baseline. Each takes a CMake list of the component names in the table at the top, or
`ALL`. An unknown name, or a component in two lists, fails at configure time.

The usual setup for measuring is a silent stack with one component's timing, since
there is no logging overhead and lwIP's asserts are gone:

```sh
EMU68_CONFIGURE_ARGS="-DEMU68_TIER=off -DEMU68_PROFILE=lwip-amiga" ./scripts/docker-build.sh
```

Capture the run and pipe it through `components/emu68-common/scripts/perf-report.py`.
Keep `trace` to the component you are debugging: across the stack it swamps the
console and slows the hot paths.

All three backends build modules that can go in ROM. The link fails on a writable
section, unless a module is declared never to go there.

## Output layout

| Path | Contents |
|---|---|
| `install/LIBS/` | `gic400.library`, `bcmpcie.library`, `openpci.library`, `bsdsocket.library`, `videocodec.library`, `videocodec/videocore.codec` |
| `install/DEVS/` | `nvme.device`, `vchiq.device`, `AHI/videocore.audio`, `AudioModes/VIDEOCORE` |
| `install/DEVS/USBHardware/` | `xhci.device` (6.x), `xhci-legacy.device` (5.x) |
| `install/DEVS/Networks/` | `genet.device` (4.x, netdev) |
| `install/C/` | `lspci`, `nvmeadm`, `nvmeinfo`, `netdev-stats`, `VCInfo`, `emu68check`, and the network tools: `netinfo`, `mdns`, `GetNetStatus`, `ShowNetStatus`, `AddNetInterface`, `RemoveNetInterface`, `NetShutdown`, `arp`, `ping`, `traceroute`, `NetLogViewer` and `NetSpeed`, these two with icons |
| `install/Classes/DataTypes/` | `vcjpeg.datatype` |
| `install/Tools/Commodities/` | `VCGrab` and its icon |
| `install/Storage/` | What the Installer places on request: `DEVS/Networks/genet.device` and `C/genet-stats` (the SANA-II 3.x line), `NetInterfaces/genet` (the interface sample), `DataTypes/VCJPEG` (`vcjpeg.datatype`'s descriptor) |
| `install/ENVARC/` | `netstack.prefs.default`, which the Installer copies to `ENVARC:` when there are no prefs yet |
| `install/Developer/` | In the archive only: `Tools/` (`VCTest`, `VPUPlay`), `Examples/videocodec/`, `Autodocs/`, `FD/`. The `package` target adds `include/`, the public headers |
| `install/include/`, `install/lib/` | Build-time headers and static libraries, including the `netdev` header and its CMake package |

The two `genet.device` lines share a filename, so only one can be installed: the 4.x
one sits at its real path and the 3.x one under `Storage/`, and the Installer asks
which. The xhci lines have their own names and can sit side by side. `emu68check` is
run from the archive and never copied to `C:`.

## The dcache extensions

Keeping the cache right around DMA is what the drivers do most, and there are two ways
to do it. That is why a release has two kinds of archive:

| Archive | `EMU68_FORCE_LVO_CACHE_OPS` | How | Runs on |
|---|---|---|---|
| `emu68-drivers-<ver>.lha` | `ON` | Calls exec's `CachePreDMA` and `CachePostDMA` | Any Emu68 from 1.1 alpha.1 on |
| `emu68-drivers-<ver>-rangeops.lha` | `OFF` | `cache_ops.h` emits a private LINE-F opcode inline | An Emu68 with the dcache extensions |

Each also comes with `EMU68_DEBUG_BACKEND=serial`, which adds `-serial` to its name, so
a release has four archives. The suffix runs against the default: a plain local build
makes a `-rangeops` archive, while the unsuffixed published one is the standard build
and keeps its historical name.

The extensions are in Emu68's `1_1_wip` but in no official release: 1.1.0-beta.1 lacksnoe 

The DMA paths assume this cache work is cheap. Without the extensions that fails, and
the netdev driver with lwip-amiga ends up slower than the SANA-II driver, which is why
[the README](README.md#what-to-download-and-install) steers those users to the SANA-II
line.

An Emu68 with the extensions advertises them as the `/emu68` device-tree property
`dcache-range-ops`. Drivers built with the inline path check it
(`emu68_has_dcache_range_ops()` in `emu68_features.h`) and refuse to load on firmware
without it, rather than take a Line-F trap. The option reaches only the components that
use `cache_ops.h`: `emu68-xhci-driver-context`, both genet lines, `emu68-nvme-driver`
and `emu68-vchiq-library`.

## Packaging

```sh
./scripts/docker-build.sh --target package
```

This makes `build/package/emu68-drivers-<version>[-<variant>].lha`. The archive holds
the runtime files (`LIBS/`, `DEVS/`, `C/`, `Classes/`, `Tools/`, `Storage/`, `ENVARC/`)
beside the Install script, which runs from the unpacked archive, and also:

- `Developer/`: the public headers, autodocs, FD files, examples and test tools;
- `Documentation/<component>/`: each component's README, licence and release notes;
- `Licenses`: a generated map of every component and shipped binary to its licence;
- `RELEASE-NOTES.md`: the stack's release notes.

The version comes from `project(emu68_driver_stack VERSION ...)` in `CMakeLists.txt`
and is stamped into `Install` and `ReadMe`. Those two are generated from `installer/*.in`
on every configure, so edit the templates.

## Testing

Testing happens on real hardware: there is no automated suite at this level.
`emu68-vchiq-library` has an on-device suite, described in its developer guide.
`sockbench` (lwip-amiga's throughput bench) and `diskbench` (the mass-storage bench in
`emu68-xhci-driver-context`) are built but not installed, so they stay out of the
archive.

To try the Installer, unpack the archive on an Amiga, run `Install` at Average or Expert
level, and pick *Pretend to Install* with a log file. It asks every question, runs the
`emu68check` probes and copies nothing, and the log says what it would have copied.

## Releasing

Every pull request, in a component or here, has to pass three CI checks: the
`project(... VERSION ...)` is bumped, `RELEASE-NOTES.md` is updated, and the code
compiles cleanly.

**For each component that changed:**

1. Update its `RELEASE-NOTES.md`, newest entry on top, and bump its version.
2. Open a PR. CI builds the whole stack with that component's source
   (`.github/workflows/component-versioning.yml`).
3. Merging creates the `v<version>` tag. Component repos publish no GitHub Releases: the
   tag is what this repo's submodule pointer tracks. Tags are cut on `main`,
   `netdev_release` and `context_release`, which is how one repo ships two lines.

**Then one release PR here:**

1. Point each changed submodule at its new tag; the pointers always track a tag:
   ```sh
   git -C components/emu68-xhci-driver-context checkout v6.4
   git add components/emu68-xhci-driver-context
   ```
2. Bump the stack version in `CMakeLists.txt`.
3. Put the new version on top of [`RELEASE-NOTES.md`](RELEASE-NOTES.md), with its
   headlines and a component-versions table linking each component's tagged notes. It
   ships in the archive, so write it for the people installing the drivers, and credit
   outside contributors.
4. Update `installer/ReadMe.in` and `installer/Install.in` if a component or a shipped
   file was added, removed or renamed. Check that the docs' Emu68 requirement, "newer
   than 1.1.0-beta.1", still names the newest official release.
5. Open the PR and merge it.
6. Tag the release by hand:
   ```sh
   git tag v<stack-version> && git push origin v<stack-version>
   ```
   The tag starts `.github/workflows/release.yml`, which builds all four archives and
   publishes them as a GitHub Release, with the `VERSIONS.txt` CMake generates as its
   text.
