# Emu68 Driver Stack

AmigaOS drivers that let your Amiga use the hardware of the Raspberry Pi 4 or
Compute Module 4 it is running on. If you have a PiStorm with Emu68, this
package gives you USB, Gigabit Ethernet with a TCP/IP stack, and NVMe solid-state
storage — as ordinary Amiga libraries and devices, driven from AmigaOS 3.x.

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
- AmigaOS 3.x
- For USB: a Poseidon USB stack (not included — see *Choosing your drivers* below)
- For the SANA-II Ethernet option: a TCP/IP stack such as Roadshow, AmiTCP or Miami

## Download

Take the archive from the [Releases](https://github.com/rondoval/emu68-driver-stack/releases)
page. Four are published; pick one:

| Archive | When to use it |
|---|---|
| `emu68-drivers-<ver>.lha` | **Start here.** Works on every Emu68 version. |
| `emu68-drivers-<ver>-rangeops.lha` | Faster, but needs a custom Emu68 build (see *A note on speed*). |
| `...-serial.lha`, `...-rangeops-serial.lha` | Same drivers, but they print diagnostics to the serial port. Only for troubleshooting. |

If you install a `-rangeops` archive on an Emu68 that does not have the dcache
extensions, the installer says so and stops — nothing is broken, you just take
the other archive.

## Installing

1. Unpack the archive on your Amiga.
2. Run the `Install` script (double-click it, or run it from a Shell).
3. Answer the questions — see below — and reboot.

The installer only copies what you select, never downgrades a newer file without
asking, and pulls in the supporting libraries automatically, so you cannot end up
with a driver whose library is missing.

## Choosing your drivers

Two of the drivers come in **two versions each**, and only one of each can be
installed. The installer asks you which; pick by what you already run.

**USB — which Poseidon do you have?**

- *Poseidon for AmigaOS 6.x* → choose the **6.x** driver. Real USB 3.0 speeds and
  fast UAS mass storage.
- *Classic Poseidon 4.x* → choose the **5.x** driver. It also runs on Poseidon
  6.x, just more slowly, so choose 6.x if you can.

**Ethernet — which TCP/IP stack do you want?**

- *The bundled one* → choose **netdev + lwip-amiga**. This installs
  `bsdsocket.library` and replaces the one you have now (your old one is backed
  up first).
- *Roadshow, AmiTCP or Miami* → choose **SANA-II**. Your existing TCP/IP stack
  keeps working untouched.

## A note on speed

The drivers move a lot of data, and how fast they can do it depends on which
Emu68 you run. The *dcache extensions* make the memory housekeeping around every
transfer far cheaper — but they are **not part of official Emu68**. They are a
separate change to Emu68's JIT that has not been merged upstream, so you need a
custom Emu68 build to get them:
[Emu68 v1.1-alpha-with-rangeops](https://github.com/rondoval/Emu68/releases/tag/v1.1-alpha-with-rangeops).

The difference is large:

| Archive | Emu68 | Download speed | Upload speed |
|---|---|---|---|
| standard | official build | 104 Mb/s | 79 Mb/s |
| standard | custom build with the dcache extensions | 698 Mb/s | 477 Mb/s |
| `-rangeops` | custom build with the dcache extensions | near gigabit line rate | near gigabit line rate |

On an official Emu68 — which is what most people run — take the standard archive
and choose the **SANA-II** Ethernet option with a third-party TCP/IP stack: there
it is genuinely faster than the bundled stack, which is built around the cheap
housekeeping the extensions provide. If you do run a build that carries them,
install the `-rangeops` archive. The technical reason is in
[docs/BUILDING.md](docs/BUILDING.md#cache-op-routing).

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

- [docs/BUILDING.md](docs/BUILDING.md) — toolchain, build options, the debug
  backend and tiers, cache-op routing, packaging
- [docs/RELEASING.md](docs/RELEASING.md) — versioning and the release process
