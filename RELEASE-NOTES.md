# Release notes — Emu68 driver stack 1.0.0

First packaged release of the full driver stack for PiStorm/Emu68 on the Raspberry Pi 4B / CM4.
The stack is built and distributed as a single `emu68-drivers-1.0.0.lha` archive with an
Installer script.

This document is the top-level summary; each component ships its own detailed
release notes (linked below).

---

## Component versions in this release

| Component | Version | Detailed notes |
|---|---|---|
| `emu68-common` (support library) | 1.5.0 | [RELEASE-NOTES-1.5.0.md](components/emu68-common/RELEASE-NOTES-1.5.0.md) |
| `gic400.library` | 1.4.0 | [RELEASE-NOTES-1.4.0.md](components/emu68-gic400-library/RELEASE-NOTES-1.4.0.md) |
| `bcmpcie.library` | 1.1 | [RELEASE-NOTES-1.1.md](components/emu68-pcie-library/RELEASE-NOTES-1.1.md) |
| `xhci.device` | 5.0 | [RELEASE-NOTES-5.0.md](components/emu68-xhci-driver/RELEASE-NOTES-5.0.md) |
| `genet.device` | 3.10 | [RELEASE-NOTES-3.10.md](components/emu68-genet-driver/RELEASE-NOTES-3.10.md) |
| `nvme.device` | 1.0 | [RELEASE-NOTES-1.0.md](components/emu68-nvme-driver/RELEASE-NOTES-1.0.md) |

---

## Headlines

- **`nvme.device` joins the stack.** A new PCIe NVMe block-storage driver with
  native Write Zeroes / TRIM, a full `nvmeadm` admin and diagnostics tool
  (SMART, self-test, format, sanitize, firmware update, logs) and an `nvmeinfo`
  helper. Installs to `DEVS:` with `nvmeadm` / `nvmeinfo` in `C:`.
- **USB power management in `xhci.device` 5.0.** USB 3.0 Link Power Management
  (U1/U2), USB 2.0 hardware LPM (L1/BESL), Latency Tolerance Messaging, and
  Multi-TT hub support, plus more reliable SuperSpeed bring-up.
- **Safer resets across the whole stack.** `emu68-common` gains a shared *reset
  guard*; `xhci.device`, `genet.device`, and `nvme.device` now quiesce their DMA
  engines before the Amiga resets.

## Cross-cutting changes

These themes run through several components this release:

- **Region-restricted DMA memory pools.** A new `dma_mem` facility in
  `emu68-common` allocates DMA buffers only from Emu68 (Pi-DRAM) RAM that the
  Pi's PCIe / on-SoC DMA engines can actually reach, with a transport-agnostic
  reachability predicate driving bounce-buffer decisions. Adopted by
  `bcmpcie.library`, `genet.device`, and `nvme.device`.
- **Reset guard.** Drivers register a "prepare for reset" hook covering both the
  Ctrl-Amiga-Amiga keyboard reset-warning protocol and `ColdReboot()`
  (`C:Reboot`, Installer, …).
- **ROM-ability.** A shared `emu68_rom_check` build step fails the build if any
  module carries writable `.data`/`.bss`, so every library and device in the
  stack is verified ROM-able.
- **Millisecond delay helpers.** Bring-up/reset timing switched from
  microsecond arithmetic to `delay_ms()` for clarity (no timing change).

---

## Per-component summary

### `nvme.device` 1.0 — new
First release. NVMe over the Emu68 PCIe path; units map 1:1 to namespaces;
standard block I/O with Fast-RAM bounce-buffering; native
`NSCMD_NVME_WRITE_ZEROES` / `NSCMD_NVME_TRIM`; `NSCMD_NVME_UNIT_INFO` topology
query; admin passthrough with per-device quirks and HMB. Reliability: DMA-pool
memory management, reset guard, synchronous Flush on last unit close, I/O
back-pressure handling, direction-aware cache maintenance.

### `xhci.device` 5.0
New: USB 3.0 U1/U2 LPM, USB 2.0 L1/BESL, LTM, Multi-TT hub support. Fixes:
timed-out command retirement on command-ring stop, USB-correct error
classification. Reliability: reset guard, always-warm-reset of SuperSpeed root
ports, VL805 quirks, endpoint-ring stop before U3 suspend, DMA memory rework.
No breaking changes.

### `genet.device` 3.10
Reset guard for GENET DMA quiesce — fixes the boot hang after a soft reboot while
online. Separate region-restricted DMA pool vs. CPU-only metadata pool, explicit
DMA-reachability check, `CachePreDMA()` on the RX buffer. No breaking changes.

### `bcmpcie.library` 1.1
Region-restricted DMA pools (refuses to init when no reachable region exists),
correct `dma-ranges` parsing and full `MemList` walk, ROM-able. ABI and client
DMA contract unchanged — `xhci.device` works without recompilation.

### `emu68-common` 1.5.0
New shared APIs: `dma_mem` facility (reachability predicate + region pool),
cache-line-aligned `dma_alloc`, `reset_guard`, `_Strncmp`, and the
`emu68_rom_check` CMake helper. **Breaking (consumers must update):** the
`dma_alloc` family moved to `dma_mem.h` and now takes a `struct dma_pool *`, and
`slab_cache_init()` gained a `dma_pool` parameter. Consumed components in this
release are already updated.

### `gic400.library` 1.4.0
Verified ROM-able via `emu68_rom_check`; Resident priority raised to 126
(init-ordering only, no user-visible effect). No breaking changes.

---

## Breaking changes

- **End users / installers:** none. Existing AmigaOS configurations continue to
  work; install the new `nvme.device` only if you want NVMe storage.
- **Developers building against `emu68-common`:** the `dma_alloc` family and
  `slab_cache_init()` signatures changed (see the `emu68-common` notes). This is
  internal to the stack; all bundled components are already migrated.

---

## Installation

Build and install the whole stack, then package it:

```sh
cmake -S . -B build
cmake --build build
cmake --build build --target package   # -> build/package/emu68-drivers-1.0.0.lha
```

No local toolchain? Use `./scripts/docker-build.sh --target package` instead, which
builds inside the cross-toolchain container (and provides the `lha` archiver).

Unpack the archive on the Amiga and run the bundled Commodore Installer script.
See [README.md](README.md) for build details and per-component requirements
(`xhci.device` units 1+ require `bcmpcie.library` in `LIBS:`; `genet.device` and
`nvme.device` require `gic400.library`).
