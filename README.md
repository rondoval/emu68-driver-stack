# Emu68 Driver Stack

AmigaOS drivers that let your Amiga use the hardware of the Raspberry Pi 4 or
Compute Module 4 it is running on. If you have a PiStorm with Emu68, this
package gives you USB, Gigabit Ethernet with a TCP/IP stack, and NVMe solid-state
storage — as ordinary Amiga libraries and devices, driven from AmigaOS 3.x — and,
as an experiment, hardware video, JPEG pictures and sound on the Pi's VideoCore.

> **Upgrading from 2.0?** Two things can change how your machine comes up.
> Network interfaces are no longer configured in `ENVARC:netstack.prefs` — each
> one now has its own file in `DEVS:NetInterfaces/` — so a fixed address set up
> under 2.0 comes back up on DHCP until you re-enter it there (the installer
> warns you). And NVMe partition numbering can shift, because exFAT partitions
> now mount too.

## What you get

- **USB** — `xhci.device` (for Neptune) or `xhci-legacy.device` (for classic Poseidon 4.x) drives the USB controllers on the Pi 4 / CM4. Each one
  is a separate unit that has to be added to your USB stack on its own; the
  driver's own documentation lists which units your board has. Needs a USB
  stack — [Neptune](https://github.com/rondoval/neptune-usb-stack) or classic Poseidon 4.x -
  which is distributed separately.
- **Ethernet** — `genet.device` drives the Pi 4's built-in gigabit port, in two
  versions you choose between: the fast zero-copy `netdev` driver for the
  bundled TCP/IP stack, or the classic SANA-II driver that any stack can use.
- **TCP/IP** — lwip-amiga, a modern TCP/IP stack that configures itself over
  DHCP. It provides the standard AmigaOS networking API, so it installs under
  the usual name `bsdsocket.library`. It also drives classic Ethernet-type
  SANA-II hardware — a Zorro or PCMCIA card, a USB Ethernet adapter — so it is
  not tied to the Pi's own port; one interface at a time. Comes with `netinfo`,
  `netdev-stats`, `mdns`, `ping`, `traceroute`, `arp`, the Roadshow-style
  `AddNetInterface` / `RemoveNetInterface` / `NetShutdown` commands, the
  `NetLogViewer` commodity and the `NetSpeed` throughput monitor.
- **Storage** — `nvme.device` drives an NVMe SSD attached to the PCIe slot, with
  the `nvmeinfo` and `nvmeadm` tools for health and SMART data.
- **VideoCore (experimental)** — `videocodec.library` decodes H.264 and MJPEG
  video and pictures and encodes H.264 and JPEG while the 68k stays almost idle,
  `vcjpeg.datatype` speeds up JPEG pictures in every program, `videocore.audio`
  plays AHI sound to HDMI or the headphone jack, and `VCGrab` records an RTG screen
  to an MKV file. `VCInfo` checks the setup. The installer leaves these unticked.
- **Supporting libraries** — `gic400.library` and `bcmpcie.library`, which the
  drivers need and the installer brings along, with the `lspci` tool, and
  `openpci.library` for programs such as `identify.library`.

## Requirements

- A Raspberry Pi 4 or CM4 running [Emu68](https://github.com/michalsc/Emu68)
  **1.1 alpha.1 or newer**
- AmigaOS 3.x
- For USB: a USB stack, Neptune or classic Poseidon 4.x (not included — see
  *What to download and install* below)
- For networking: either the bundled lwip-amiga stack or a third-party one such
  as Roadshow, AmiTCP or Miami. The `netdev` `genet.device` needs lwip-amiga;
  the SANA-II `genet.device` works with either
- For the VideoCore parts: an Emu68 newer than 1.1.0-beta.1 with the `cma` overlay;
  `vcjpeg.datatype` needs AmigaOS 3.2 and `videocore.audio` needs AHI. The archive's
  `ReadMe` has the settings

## What to download and install

**The one thing that decides everything: does your Emu68 have the dcache
extensions?**

Official Emu68 releases up to 1.1.0-beta.1 do not have them — they came to its
JIT later, so having them means running a newer Emu68 or
[a custom Emu68 build](https://github.com/rondoval/Emu68/releases/tag/v1.1-alpha-with-rangeops).
Without them the drivers still work, but the cache housekeeping around every
transfer has to be done the slow way — and the bundled TCP/IP stack, which is
built around that housekeeping being cheap, ends up *slower* than the plain old
SANA-II driver. So on those releases there is no point installing the netdev
Ethernet driver at all: take the standard archive and pair the SANA-II driver
with Roadshow, AmiTCP or Miami. With the extensions, take the `-rangeops`
archive and the netdev driver with the bundled lwip-amiga stack, which gets you
close to gigabit line rate. USB is a separate, independent question: it depends
only on which USB stack you run.

The VideoCore parts (video, JPEG pictures, sound) need an Emu68 newer than
1.1.0-beta.1, which has the extensions too, so for those take the `-rangeops`
archive.

Archives are on the [Releases](https://github.com/rondoval/emu68-driver-stack/releases)
page. **Find your row.**

The installer asks for the Ethernet driver and the TCP/IP stack separately —
they are independent choices, because the bundled stack drives SANA-II
hardware too.

| Your Emu68 | Your USB stack | Download | Ethernet driver | TCP/IP | USB |
|---|---|---|---|---|---|
| Official release, 1.1 alpha.1 to 1.1.0-beta.1 | classic Poseidon 4.x | `emu68-drivers-<ver>.lha` | **SANA-II** 3.x | Roadshow / AmiTCP / Miami, or the bundled stack | `xhci-legacy.device` **5.x** |
| Official release, 1.1 alpha.1 to 1.1.0-beta.1 | Neptune 6.x | `emu68-drivers-<ver>.lha` | **SANA-II** 3.x | Roadshow / AmiTCP / Miami, or the bundled stack | `xhci.device` **6.x** |
| Newer, or a custom build with the dcache extensions | classic Poseidon 4.x | `emu68-drivers-<ver>-rangeops.lha` | **netdev** 4.x | bundled lwip-amiga | `xhci-legacy.device` **5.x** |
| Newer, or a custom build with the dcache extensions | Neptune 6.x | `emu68-drivers-<ver>-rangeops.lha` | **netdev** 4.x | bundled lwip-amiga | `xhci.device` **6.x** |

**Installing the bundled stack replaces your `bsdsocket.library`**, so
Roadshow, AmiTCP and Miami stop working — and it installs its own `ping`,
`traceroute`, `arp`, `AddNetInterface`, `RemoveNetInterface`, `NetShutdown`,
`GetNetStatus` and `ShowNetStatus` into `C:`, over the Roadshow commands of
those names.
Your SANA-II Ethernet *hardware* keeps working, though: since lwip-amiga 1.5 the
bundled stack drives Ethernet-type SANA-II drivers itself, so a Zorro or PCMCIA
card or a USB Ethernet adapter just gets described in a `DEVS:NetInterfaces/`
file — and Roadshow's interface files are read as they are (a fixed address needs
`GATEWAY=` added, since Roadshow keeps the router in `DEVS:Internet/routes`). What it
cannot drive is non-Ethernet SANA-II — PPP and SLIP dial-up,
Token Ring, ArcNet. And it carries **one interface at a time** besides
loopback, so it is the Pi's port or your card, not both.

Neptune is an incompatible fork of the Poseidon USB stack; its 6.0–6.2 releases were
published as "Poseidon for AmigaOS". `xhci.device` (6.x) speaks only Neptune's own
context interface, so it does not work with Poseidon. `xhci-legacy.device` (5.x) speaks
the classic interface and runs on both, on Neptune just without real USB 3.0 or fast UAS
storage — so it is the safe answer if you are unsure. The two have different names and
can both be installed; up to 5.5 the 5.x driver was `xhci.device` too.

The two `-serial` archives are the same drivers with serial-port diagnostics —
take one only when chasing a problem. Installing a `-rangeops` archive on an
Emu68 without the extensions is safe: the installer checks, says so, and stops
without changing anything.

Where the advice comes from — measured TCP throughput, netdev `genet.device` +
the bundled stack, on a gigabit LAN:

| Archive | Emu68 | Download | Upload |
|---|---|---|---|
| standard | without the extensions | 104 Mb/s | 79 Mb/s |
| standard | with the extensions | 698 Mb/s | 477 Mb/s |
| `-rangeops` | with the extensions | near line rate | near line rate |

Over the SANA-II backend the same stack measures about 290 Mb/s down and
300 Mb/s up: SANA-II copies every packet and cannot offload checksums.

Why the extensions make that much difference is explained in
[DEVELOPING.md](DEVELOPING.md#the-dcache-extensions).

## Installing

1. Unpack the archive on your Amiga.
2. Run the `Install` script (double-click it, or run it from a Shell).
3. Answer the questions — which USB driver, which Ethernet driver, and which
   TCP/IP stack (the table above tells you which to pick) — then tick the other
   components you want. The first screen names your archive, and the answers start
   at what you have installed.
4. Check the list on the last screen before anything is copied, and reboot.

The installer only copies what you select, never downgrades a newer file without
asking, asks before replacing another TCP/IP stack, `openpci.library` or `lspci`, and
pulls in the supporting libraries automatically, so you cannot end up with a driver
whose library is missing.

## Documentation and licences

The archive contains a `ReadMe` covering every component and the post-install
steps, a `Licenses` summary, and a `Documentation` drawer with each component's
own documentation. [`RELEASE-NOTES.md`](RELEASE-NOTES.md) lists what changed in
each version.

Each component is covered by its own licence: GPL-2.0, MPL-2.0/GPL-2.0+, and
BSD-3-Clause for `lwip-amiga` (the TCP/IP stack, `bsdsocket.library` and the
networking tools) and `emu68-vchiq-library` (the VideoCore parts). The per-file
SPDX headers in the sources are authoritative, and the `Licenses` file in the archive maps every shipped binary to its licence.

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
