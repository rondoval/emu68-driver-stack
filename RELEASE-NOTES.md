# Release notes — Emu68 driver stack 1.0.6

Changes since 1.0.5. A build-system update only — the drivers themselves are
unchanged from 1.0.5 (every component keeps its 1.0.5 version, see the table
below). The stack ships as a single `emu68-drivers-1.0.6.lha` archive with the
Commodore Installer script.

---

## Build & tooling

The cross-toolchain build image moved to `ghcr.io/rondoval/amiga-build-container`,
and a single top-level `build.sh` now drives the whole edit-build-test loop —
container build, `.lha` packaging, and upload to a live Amiga over Amiga Explorer
— behind `--build` / `--package` / `--upload` / `--dry-run` (on top of
`scripts/docker-build.sh`, which CI shares).

---


# Release notes — Emu68 driver stack 1.0.5

First public release of the full driver stack for PiStorm/Emu68 on the Raspberry
Pi 4B / CM4. The stack is built and distributed as a single
`emu68-drivers-1.0.5.lha` archive with a Commodore Installer script.

This document is the top-level summary; each component ships its own detailed
release notes (linked below).

---

## Component versions in this release

| Component | Version | Detailed notes |
|---|---|---|
| `emu68-common` (support library) | 1.6.0 | [RELEASE-NOTES.md](components/emu68-common/RELEASE-NOTES.md) |
| `gic400.library` | 1.5 | [RELEASE-NOTES.md](components/emu68-gic400-library/RELEASE-NOTES.md) |
| `bcmpcie.library` | 2.0 | [RELEASE-NOTES.md](components/emu68-pcie-library/RELEASE-NOTES.md) |
| `openpci.library` | 45.12 | bundled with `bcmpcie.library` |
| `xhci.device` | 5.1 | [RELEASE-NOTES.md](components/emu68-xhci-driver/RELEASE-NOTES.md) |
| `genet.device` | 3.11 | [RELEASE-NOTES.md](components/emu68-genet-driver/RELEASE-NOTES.md) |
| `nvme.device` | 1.1 | [RELEASE-NOTES.md](components/emu68-nvme-driver/RELEASE-NOTES.md) |

---

## What the stack delivers

- **PCIe storage — `nvme.device`.** A PCIe NVMe block-storage driver with native
  Write Zeroes / TRIM, a full `nvmeadm` admin and diagnostics tool (SMART,
  self-test, format, sanitize, firmware update, logs) and an `nvmeinfo` helper.
  Units map 1:1 to namespaces. Installs to `DEVS:` with `nvmeadm` / `nvmeinfo`
  in `C:`.
- **USB 3.0 — `xhci.device`.** A SuperSpeed xHCI host driver for the onboard OTG
  controller and PCIe controllers (VL805), with USB 3.0 hubs, SuperSpeed
  devices, real-time isochronous audio, USB power management (U1/U2 LPM,
  USB 2.0 L1/BESL, LTM) and Multi-TT hub support.
- **Gigabit Ethernet — `genet.device`.** A SANA-II driver for the Pi's onboard
  Broadcom GENET MAC, with hardware statistics and the `genet-stats` viewer.
- **PCIe services — `bcmpcie.library`.** A BCM2711 root-complex driver exposing
  a typed, multi-vector interrupt API with MSI-X, alongside the
  `openpci.library` compatibility API and `lspci`.
- **Interrupt routing — `gic400.library`.** GIC-400 SPI routing that the PCIe and
  GENET paths build on.
- **Shared foundation — `emu68-common`.** DMA-reachable memory pools, a reset
  guard, a slab allocator, freestanding C runtime primitives, and a stack-wide
  debug backend used by every component.

---

## Stack-wide design

Themes that run through the whole stack:

- **Region-restricted DMA memory pools.** The `dma_mem` facility in
  `emu68-common` allocates DMA buffers only from Emu68 (Pi-DRAM) RAM that the
  Pi's PCIe / on-SoC DMA engines can actually reach, with a transport-agnostic
  reachability predicate driving bounce-buffer decisions. Chip RAM and
  Zorro/accelerator Fast RAM are correctly excluded. Used by `bcmpcie.library`,
  `genet.device`, and `nvme.device`.
- **Typed, multi-vector interrupts with MSI-X.** `bcmpcie.library` exposes a
  typed interrupt API (`AllocIntVectors` and friends) covering INTx, MSI and
  multi-vector MSI-X, with per-vector masking and typed error codes.
  `xhci.device` and `nvme.device` pick the best available type
  (MSI-X → MSI → INTx); MSI-X rescues drives whose single-message MSI is broken
  (for example the Micron 2300).
- **Reset guard.** DMA-capable drivers register a "prepare for reset" hook
  covering both the Ctrl-Amiga-Amiga keyboard reset-warning protocol and
  `ColdReboot()` (`C:Reboot`, Installer, …), quiescing their DMA engines before
  the Amiga resets.
- **ROM-ability.** A shared `emu68_rom_check` build step fails the build if any
  module carries writable `.data`/`.bss`, so every library and device in the
  stack is verified ROM-able.
- **Stack-wide debug backend.** A single `EMU68_DEBUG_BACKEND` build option
  (`pistorm` | `serial` | `off`) selects debug output for the whole stack;
  release builds compile diagnostics out entirely.
- **Toolchain portability.** The stack builds against NDK 3.2 (the target)and
  older pre-3.2 NDKs, at `-O3`, with `emu68-common` supplying
  the freestanding `memset`/`memcpy`/`memmove`/`memcmp` the
  `-ffreestanding -nostdlib` drivers need.

---

## Per-component summary

### `nvme.device` 1.1 — PCIe NVMe block storage
NVMe over the Emu68 PCIe path; units map 1:1 to namespaces. Standard block I/O
(`CMD_READ`/`CMD_WRITE`, TD64, newstyle 64-bit) with Fast-RAM bounce-buffering;
native `NSCMD_NVME_WRITE_ZEROES` / `NSCMD_NVME_TRIM`; `NSCMD_NVME_UNIT_INFO`
topology query; admin passthrough with per-device quirks and Host Memory Buffer.
Interrupts via MSI-X / MSI / INTx; region-restricted DMA pools; reset guard;
synchronous Flush on last unit close; asynchronous I/O-queue rebuild so
controller reset and recovery complete without deadlocking. Ships the `nvmeadm`
admin/diagnostics tool and the `nvmeinfo` helper. Requires `bcmpcie.library` 2.0
and `gic400.library`. Still a young storage driver — keep current backups.

### `xhci.device` 5.1 — USB 3.0 host
SuperSpeed xHCI host for the onboard OTG controller (unit 0) and PCIe
controllers such as the VL805 (units 1+). Handles USB 3.0 hubs and SuperSpeed
devices, USB 2.0/1.x devices, and real-time isochronous audio with slab-allocated
hot-path objects and a growing transfer ring. Power management covers USB 3.0
U1/U2 LPM, USB 2.0 hardware LPM (L1/BESL), Latency Tolerance Messaging and
Multi-TT hubs. Interrupts via MSI-X / MSI / INTx; a reset guard halts every
controller before a machine reset; SuperSpeed root ports are brought up with warm
resets; VL805 quirks are applied per controller; transaction errors are reported
with USB-correct codes for Poseidon. Poseidon-compatible HCD interface. Units 1+
require `bcmpcie.library` 2.0 in `LIBS:`; unit 0 does not.

### `genet.device` 3.11 — Gigabit Ethernet
SANA-II driver for the Raspberry Pi's onboard Broadcom GENET Gigabit MAC.
Interrupt-driven RX with a region-restricted DMA pool kept separate from
CPU-only metadata, an explicit DMA-reachability check on opener buffers, and a
reset guard that quiesces the GENET DMA engine before reset — so a soft reboot
while online no longer hangs the Amiga. Hardware MIB statistics, extended/special
stats and throughput sampling are exposed through SANA-II and the bundled
`genet-stats` viewer. Configurable through `ENV:genet.prefs`. Requires
`gic400.library`.

### `bcmpcie.library` 2.0 — PCIe root-complex services
Driver for the BCM2711 PCIe root complex used by Emu68/PiStorm. Provides a typed,
multi-vector interrupt-allocation API (`AllocIntVectors` / `AddIntVectorServer` /
`MaskIntVector` / …, LVOs -342…-378) covering INTx, MSI and multi-vector MSI-X,
with per-vector masking and typed error codes (`<libraries/bcmpcie_errors.h>`).
DMA buffers are served from region-restricted pools that only return
PCIe-reachable RAM, and the library refuses to initialise when no reachable
region exists. ROM-able. Ships alongside the `openpci.library` 45.12 compatibility
API and the `lspci` tool. The legacy single-vector `EnableMSI` / `pci_add_intserver`
calls remain for source compatibility but never select MSI-X.

### `emu68-common` 1.6.0 — shared support library
The foundation linked into every component. Supplies the `dma_mem`
DMA-reachability predicate and region pools, cache-line-aligned `dma_alloc`, an
O(1) slab allocator, the `reset_guard` facility, string/bit/timing helpers, and
the freestanding C runtime primitives (`memset`/`memcpy`/`memmove`/`memcmp`) the
`-nostdlib` drivers depend on. It also ships the CMake building blocks the rest of
the stack shares: the `emu68_rom_check` ROM-ability guard, the
`EMU68_DEBUG_BACKEND` debug selector, and the reusable component-versioning
workflow. Builds against NDK 3.2 and 3.9.

### `gic400.library` 1.5 — GIC-400 interrupt routing
Routes GIC-400 SPIs on the BCM2711, underpinning both the PCIe MSI/MSI-X
aggregation interrupt and per-device INTx lines, as well as the GENET interrupt.
Opened on demand by the drivers that need it (`bcmpcie.library`, `genet.device`).
ROM-able.

---

## Requirements & dependencies

- `xhci.device` units 1+ (PCIe controllers, e.g. the VL805) require
  `bcmpcie.library` 2.0 in `LIBS:`. Unit 0 (onboard OTG) does not.
- `nvme.device` requires `bcmpcie.library` 2.0 and `gic400.library`.
- `genet.device` requires `gic400.library`.
- The bundled archive ships mutually compatible versions of all of these, so a
  clean install of the whole stack satisfies every dependency. `xhci.device` and
  `nvme.device` open `bcmpcie.library` requesting version 2 and decline to start
  against an older 1.x library rather than misbehaving.
- Developers building against `emu68-common` should read its release notes for
  the current DMA-pool / slab / debug-backend API surface.

---

## Installation

Build and install the whole stack, then package it:

```sh
cmake -S . -B build
cmake --build build
cmake --build build --target package   # -> build/package/emu68-drivers-1.0.5.lha
```

No local toolchain? Use `./scripts/docker-build.sh --target package` instead, which
builds inside the cross-toolchain container (and provides the `lha` archiver).

Unpack the archive on the Amiga and run the bundled Commodore Installer script.
See [README.md](README.md) for build details and per-component requirements.
