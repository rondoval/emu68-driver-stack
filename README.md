# Emu68 Driver Stack

AmigaOS drivers that let your Amiga use the hardware of the Raspberry Pi 4 or
Compute Module 4 it is running on. If you have a PiStorm with Emu68, this
package gives you USB, Gigabit Ethernet with a TCP/IP stack, and NVMe solid-state
storage — as ordinary Amiga libraries and devices, driven from AmigaOS 3.x.

> **2.0.0 is a big release — treat it as beta.** Nearly everything in the
> networking path is new: a TCP/IP stack, a new driver ABI, a rewritten Ethernet
> driver, and a second USB driver line. Keep a bootable backup of your current
> `LIBS:` and `DEVS:` before installing, and please report what breaks.

## What you get

- **USB** — `xhci.device` drives the USB controllers on the Pi 4 / CM4. Each one
  is a separate unit that has to be added to your USB stack on its own; the
  driver's own documentation lists which units your board has. Needs a Poseidon
  USB stack, which is distributed separately.
- **Ethernet** — `genet.device` drives the Pi 4's built-in gigabit port.
- **TCP/IP** — `bsdsocket.library`, a modern TCP/IP stack (lwip-amiga) that
  configures itself over DHCP. Comes with the `netinfo`, `netdev-stats` and
  `mdns` tools.
- **Storage** — `nvme.device` drives an NVMe SSD attached to the PCIe slot, with
  the `nvmeinfo` and `nvmeadm` tools for health and SMART data.
- **Supporting libraries** — `gic400.library` and `bcmpcie.library`, which the
  drivers need, plus optional `openpci.library` and the `lspci` tool.

## Requirements

- A Raspberry Pi 4 or CM4 running [Emu68](https://github.com/michalsc/Emu68)
  **1.1 alpha.1 or newer**
- AmigaOS 3.x
- For USB: a Poseidon USB stack (not included — see *What to download and
  install* below)
- For the SANA-II Ethernet option: a TCP/IP stack such as Roadshow, AmiTCP or Miami

## What to download and install

**The one thing that decides everything: does your Emu68 have the dcache
extensions?**

They are not part of official Emu68 — they are a separate change to its JIT that
has not been merged upstream, so having them means running
[a custom Emu68 build](https://github.com/rondoval/Emu68/releases/tag/v1.1-alpha-with-rangeops).
Without them the drivers still work, but the cache housekeeping around every
transfer has to be done the slow way — and the bundled TCP/IP stack, which is
built around that housekeeping being cheap, ends up *slower* than the plain old
SANA-II driver. So on official Emu68 there is no point installing the netdev
Ethernet driver at all: take the standard archive and pair the SANA-II driver
with Roadshow, AmiTCP or Miami. On
[a custom build with the extensions](https://github.com/rondoval/Emu68/releases/tag/v1.1-alpha-with-rangeops),
take the `-rangeops` archive and the netdev driver with the bundled
`bsdsocket.library`, which gets you close to gigabit line rate. USB is a
separate, independent question: it depends only on which Poseidon you run.

Archives are on the [Releases](https://github.com/rondoval/emu68-driver-stack/releases)
page. **Find your row.**

| Your Emu68 | Your Poseidon | Download | Ethernet | USB |
|---|---|---|---|---|
| Official, 1.1 alpha.1 or newer | classic 4.x | `emu68-drivers-<ver>.lha` | **SANA-II** 3.x + Roadshow / AmiTCP / Miami | `xhci.device` **5.x** |
| Official, 1.1 alpha.1 or newer | for AmigaOS 6.x | `emu68-drivers-<ver>.lha` | **SANA-II** 3.x + Roadshow / AmiTCP / Miami | `xhci.device` **6.x** |
| Custom build with the dcache extensions | classic 4.x | `emu68-drivers-<ver>-rangeops.lha` | **netdev** 4.x + the bundled `bsdsocket.library` | `xhci.device` **5.x** |
| Custom build with the dcache extensions | for AmigaOS 6.x | `emu68-drivers-<ver>-rangeops.lha` | **netdev** 4.x + the bundled `bsdsocket.library` | `xhci.device` **6.x** |

**Choosing netdev turns off every other network interface you have.** The
bundled `bsdsocket.library` is not a SANA-II stack: it drives network hardware
over the new *netdev* interface, and `genet.device` 4.x is the only driver in
existence that speaks it. Anything else you connect through — a Zorro or PCMCIA
Ethernet card, a USB Ethernet adapter, a PPP or SLIP dial-up link — has a
SANA-II driver only, and will stop working once the bundled stack replaces your
`bsdsocket.library`. If you need any of them, take the SANA-II row.

The bundled `bsdsocket.library` replaces yours (the old one is kept as
`bsdsocket.library.orig`); the SANA-II driver leaves your TCP/IP stack alone.
`xhci.device` 5.x also runs on Poseidon for AmigaOS 6.x, just without real USB
3.0 or fast UAS storage — so it is the safe answer if you are unsure.

The two `-serial` archives are the same drivers with serial-port diagnostics —
take one only when chasing a problem. Installing a `-rangeops` archive on an
Emu68 without the extensions is safe: the installer checks, says so, and stops
without changing anything.

Where the advice comes from — measured TCP throughput, netdev `genet.device` +
the bundled stack, on a gigabit LAN:

| Archive | Emu68 | Download | Upload |
|---|---|---|---|
| standard | official build | 104 Mb/s | 79 Mb/s |
| standard | custom build with the extensions | 698 Mb/s | 477 Mb/s |
| `-rangeops` | custom build with the extensions | near line rate | near line rate |

Why the extensions make that much difference is explained in
[DEVELOPING.md](DEVELOPING.md#the-dcache-extensions).

## Installing

1. Unpack the archive on your Amiga.
2. Run the `Install` script (double-click it, or run it from a Shell).
3. Answer the questions — the table above tells you which to pick — and reboot.

The installer only copies what you select, never downgrades a newer file without
asking, and pulls in the supporting libraries automatically, so you cannot end up
with a driver whose library is missing.

## Documentation and licences

The archive contains a `ReadMe` covering every component and the post-install
steps, a `Licenses` summary, and a `Documentation` drawer with each component's
own documentation. [`RELEASE-NOTES.md`](RELEASE-NOTES.md) lists what changed in
each version.

Each component is covered by its own licence: GPL-2.0, MPL-2.0/GPL-2.0+, and
BSD-3-Clause for `lwip-amiga` — the TCP/IP stack, `bsdsocket.library` and the
networking tools. The per-file SPDX headers in the sources are authoritative,
and the `Licenses` file in the archive maps every shipped binary to its licence.

## For developers

This repository is a CMake superbuild; every component is a git submodule under
`components/`.

```sh
git clone --recurse-submodules https://github.com/rondoval/emu68-driver-stack.git
cd emu68-driver-stack
./scripts/docker-build.sh                   # build in the toolchain container
./scripts/docker-build.sh --target package  # ...and make the .lha
```

[DEVELOPING.md](DEVELOPING.md) covers the toolchain, the build options, the
debug backend and tiers, the cache-op flavors, packaging and the release
process.
