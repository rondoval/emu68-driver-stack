# Release notes — Emu68 driver stack 2.1.0

Changes since 2.0.0. The TCP/IP stack stops being tied to the Pi's own Ethernet
port — it now drives ordinary SANA-II network hardware as well — network
control grows the Roadshow-style commands it was missing, and every driver in
the stack can be built into a custom Kickstart ROM, so a machine can boot from
USB or NVMe.

- **Your existing network card works with the bundled stack.** A Zorro or
  PCMCIA Ethernet card, or a USB Ethernet adapter, no longer rules out
  lwip-amiga: the stack drives Ethernet-type SANA-II drivers itself now, and
  detects which kind of driver it is talking to.
- **Roadshow-style network control.** `AddNetInterface`,
  `RemoveNetInterface`, `NetShutdown`, `arp`, `ping`, `traceroute`,
  `GetNetStatus`/`ShowNetStatus`, and a `NetLogViewer` commodity that shows
  what the stack is doing. The conformance score reaches a clean 142/142.
- **Boot from USB or NVMe in a custom Kickstart ROM.** Nothing changes for a
  normal `DEVS:`/`LIBS:` install.
- **exFAT partitions mount** on NVMe — which can renumber `NVME<n>:`, see
  below.

Two things can leave a working machine behaving differently, so read *Before
you upgrade* first. Which archive to take, and what the installer asks, are in
the [README](https://github.com/rondoval/emu68-driver-stack/blob/main/README.md)
and in the `ReadMe` beside this file in the archive.

---

## Before you upgrade

**Network configuration moved out of `ENVARC:netstack.prefs`.** Interface
settings — `DEVICE`, `UNIT`, `MODE`, `ADDRESS`, `NETMASK`, `GATEWAY`, `VLAN` —
are no longer read from it. Each interface now has its own file in
`DEVS:NetInterfaces/`, added at boot by `AddNetInterface` from
`S:Network-Startup`, which the installer sets up for you. `netstack.prefs`
keeps the stack-wide keys (`HOSTNAME`, `DOMAIN`, `DNS1`/`DNS2`, `MDNS*`,
`NETWORK`) and those still work. **A fixed address configured under 2.0 must be
re-entered** in `DEVS:NetInterfaces/genet` — otherwise the machine comes up on
DHCP. The installer shows a screen when it finds a 2.0-era prefs file, and
changes nothing itself; the archive `ReadMe` lists which key moves where.

**`NVME<n>:` numbering can shift.** exFAT partitions mount now, and each takes
the next free `NVME<n>:`, so a partition that follows an exFAT one may come up
under a different number than in 2.0. RDB partitions keep the names their RDB
carries and are unaffected.

---

## Component versions in this release

| Component | Version | Detailed notes |
|---|---|---|
| `emu68-common` (support library) | **1.9.1** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-common/blob/v1.9.1/RELEASE-NOTES.md) |
| `gic400.library` | **1.8** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-gic400-library/blob/v1.8/RELEASE-NOTES.md) |
| `bcmpcie.library` | **2.4** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-pcie-library/blob/v2.4/RELEASE-NOTES.md) |
| `openpci.library` | 45.12 | bundled with `bcmpcie.library` |
| `xhci.device` (6.x) | **6.2** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-xhci-driver/blob/v6.2/RELEASE-NOTES.md) |
| `xhci.device` (5.x) | **5.4** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-xhci-driver/blob/v5.4/RELEASE-NOTES.md) |
| `genet.device` (4.x, netdev) | **4.2** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-genet-driver/blob/v4.2/RELEASE-NOTES.md) |
| `genet.device` (3.x, SANA-II) | **3.15** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-genet-driver/blob/v3.15/RELEASE-NOTES.md) |
| `nvme.device` | **1.5** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-nvme-driver/blob/v1.5/RELEASE-NOTES.md) |
| lwip-amiga (TCP/IP stack) | **1.4** — ships `bsdsocket.library` **4.104** | [RELEASE-NOTES.md](https://github.com/rondoval/lwip-amiga/blob/v1.4/RELEASE-NOTES.md) |

---

## What changed

### Networking — the stack drives your existing hardware

lwip-amiga gains a **SANA-II backend**. Besides its native `netdev`
interface it now drives classic Ethernet-type SANA-II drivers — Poseidon USB
Ethernet adapters, Zorro and PCMCIA cards, and the SANA-II `genet.device` —
detecting which kind a device speaks when the interface is added; the new
`TYPE` option in the interface file forces `NETDEV` or `SANA2` when the probe
needs overriding. Non-Ethernet SANA-II (Token Ring, ArcNet, serial-line
drivers) is not supported. SANA-II is copy-based and offload-blind, so expect
roughly 290/300 Mb/s against it rather than the netdev numbers.

Network control is now Roadshow-shaped. `AddNetInterface` brings interfaces up
from `DEVS:NetInterfaces/` files and blocks until they are actually usable —
link up, DHCP lease bound; `RemoveNetInterface` takes one down again; and
`NetShutdown` stops the whole stack, waits for network programs to quit, and
unloads the library. `arp` displays, sets and deletes ARP entries, with the
classic `SIOCSARP`/`SIOCGARP`/`SIOCDARP` `IoctlSocket()` requests behind it.
`ping` and `traceroute` arrive with Roadshow-compatible templates, and
`setsockopt(IP_HDRINCL)` now works for raw sockets. `GetNetStatus` and
`ShowNetStatus` answer the Roadshow status query.

The stack also **logs in every build**, not just debug ones: interface
bring-up and removal, driver selection, link changes, DHCP leases, DNS and
mDNS, mistakes in `netstack.prefs`, and shutdown. The log is delivered over the
public `SBTC_LOG_HOOK` tag so any program can subscribe, application `syslog()`
output joins it, and the new `NetLogViewer` commodity (Shift-Alt-F8, or
Exchange) shows it in a window and saves it to a file. A short boot backlog is
replayed to a viewer that starts late.

TCP **out-of-band data** works end to end — `MSG_OOB`, `SO_OOBINLINE`,
`SIOCATMARK`, `WaitSelect()` exception sets and the `SetSocketSignals()` urgent
signal — which takes the bsdsocktest conformance score from 138/142 to a clean
**142/142**. `FIOASYNC` became a real per-socket SIGIO toggle, and
`SBTC_ERRNOSTRPTR`/`SBTC_HERRNOSTRPTR` return BSD error text. One fix worth
naming: UDP `connect()` now commits the local address the BSD way, so
`getsockname()` reports the real source address instead of `0.0.0.0`, and
connecting toward a destination with no route fails with `ENETUNREACH` instead
of appearing to succeed.

See the [component notes](https://github.com/rondoval/lwip-amiga/blob/v1.4/RELEASE-NOTES.md)
for the full list, including the interface-file format.

### Boot from USB or NVMe in a custom Kickstart ROM

This one spans the whole stack. `bcmpcie.library` 2.4 initialises early enough
in the Kickstart boot sequence to serve drivers before DOS exists;
`gic400.library` 1.8 works when embedded in a ROM image, which it previously
did not; both `xhci.device` lines come up during that sequence, so USB
keyboard, mouse and drives are live in the early boot menu; and `nvme.device`
1.5 moves its romtag into the coldstart window so its namespaces are probed
after Emu68's own modules exist — at its old priority it ran before
`devicetree.resource` and `gic400.library`, and NVMe never came up at all.

Together that makes a Kickstart image that can boot the machine from a USB or
NVMe drive. **Nothing changes for a normal `DEVS:`/`LIBS:` installation** —
this is only about ROM images, which are built separately.

### Storage — exFAT automount

`nvme.device` 1.5 mounts **exFAT** filesystems on MBR, GPT and superfloppy
disks through `L:exFATFileSystem` (dostype `FATX`), alongside FAT (`fat95`) and
NTFS (`NTFileSystem3G`). These are the same three recipes `massstorage.class`
uses, so a drive behaves the same whether it is in a USB enclosure or an NVMe
slot. A filesystem whose handler is not installed is skipped rather than
mounted dead. This is what can renumber `NVME<n>:` — see *Before you upgrade*.
See the [component notes](https://github.com/rondoval/emu68-nvme-driver/blob/v1.5/RELEASE-NOTES.md).

### Ethernet — the SANA-II line joins the `-rangeops` archives

`genet.device` 3.15 moves its datapath onto the stack's shared cache
operations, so a `-rangeops` build uses Emu68's fast inline cache instructions
like the rest of the stack. In 2.0 only the netdev line benefited, so a
Roadshow, AmiTCP or Miami user on a custom Emu68 now has a reason to take the
`-rangeops` archive. Those builds also check the `/emu68` device tree's
`dcache-range-ops` capability at init and refuse to load on firmware that would
Line-F trap, instead of crashing. One reliability fix: a malformed receive
descriptor could make the driver invalidate cache lines past the end of the
receive buffer, and the invalidate now happens only after the descriptor passes
its checks. See the
[component notes](https://github.com/rondoval/emu68-genet-driver/blob/v3.15/RELEASE-NOTES.md).

### Installing

The installer now asks for the Ethernet driver and the TCP/IP stack as **two
separate questions**, because the bundled stack no longer implies the netdev
driver. Picking netdev still answers both, since nothing else can open it.
Choosing the SANA-II driver leaves the stack question open — pair it with
Roadshow as before, or with the bundled stack. The bundled stack can also be
installed with no `genet.device` at all, which is the right answer when you
connect through a card or USB adapter.

It also warns when it finds a 2.0-era `ENVARC:netstack.prefs` whose interface
keys it knows are now ignored, installs the commented interface-file sample to
`SYS:Storage/NetInterfaces/` as a template for describing other hardware.
`nvmeinfo` and `nvmeadm` are now installed when missing even if you keep an
existing `nvme.device`.

## Known limitations

- **One network interface at a time.** Besides loopback the bundled stack
  carries a single interface; a second `AddNetInterface` is refused. If
  `DEVS:NetInterfaces/` holds more than one file, the boot line adds the one
  with the highest `PRI=` icon tooltype and silently skips the rest — keep the
  spares in `SYS:Storage/NetInterfaces/`. Swap interfaces with
  `RemoveNetInterface` followed by `AddNetInterface`.
- Non-Ethernet SANA-II drivers (PPP, SLIP, Token Ring, ArcNet) are not
  supported by the bundled stack.
- `ping RECORDROUTE`, published/proxy `arp` entries, and Roadshow's
  `SBTC_LOG_FILE_NAME` log file are not implemented.

## Build & tooling

A hardcoded `-m68040` was removed across the whole stack. It overrode the
toolchain's `M68K_CPU`, so a build targeting anything other than a 68040
silently produced 68040 code anyway; every component picks up the fix, which is
the only change in `emu68-common` 1.9.1 and `genet.device` 4.2.
`scripts/check-regargs.py` is gone — gcc 16.2 made the register-argument ABI
check it performed unnecessary.

---

# Release notes — Emu68 driver stack 2.0.0

> **2.0.0 is a big release — treat it as beta.** Nearly everything in the
> networking path is new: a TCP/IP stack, a new driver ABI, a rewritten Ethernet
> driver, and a second USB driver line. Keep a bootable backup of your current
> `LIBS:` and `DEVS:` before installing, and please report what breaks.

The big one: your Amiga gets a TCP/IP stack of its own, USB 3.0 works properly
on the new Poseidon, and the installer now asks which Ethernet and USB driver
you want instead of deciding for you.

- **A TCP/IP stack is included.** `bsdsocket.library` (lwip-amiga) is a modern
  networking stack that configures itself over DHCP the first time a program
  uses it — no third-party stack needed. The `netinfo`, `netdev-stats` and
  `mdns` tools come with it.
- **Ethernet got much faster.** `genet.device` was rewritten (4.x) to work with
  that stack: packets move without being copied, and the Pi's hardware does the
  checksums.
- **Real USB 3.0.** A new `xhci.device` (6.x) for Poseidon for AmigaOS 6.x
  presents USB 3.0 devices as what they are instead of disguising them as USB
  2.0, and adds the fast transfer mode that UAS mass storage uses.
- **Four archives instead of one** — see *Which archive to install* below.

Every other component moves forward too: `emu68-common` 1.9.0, `gic400.library`
1.7, `bcmpcie.library` 2.3, `nvme.device` 1.4.

---

## Before you upgrade

Three things can leave you without a working device if you answer the installer
wrongly. It asks about all of them, so read these first.

**The bundled stack drops every SANA-II interface you have.** The new
`bsdsocket.library` is not a SANA-II stack: it drives network hardware over the
new *netdev* interface, and `genet.device` 4.1 is the only driver in existence
that speaks it. A Zorro or PCMCIA Ethernet card, a USB Ethernet adapter, a PPP
or SLIP dial-up link — all of those have SANA-II drivers only, and none of them
will work once the bundled stack is installed. If you use any of them, choose
the **SANA-II** `genet.device` (3.14) instead.

**Ethernet.** The default `genet.device` (4.1) works only with the bundled
`bsdsocket.library`. Roadshow, AmiTCP and Miami cannot use it. To keep your
existing TCP/IP stack, choose the **SANA-II** `genet.device` (3.14) when the
installer asks. Choosing the bundled stack replaces your current
`bsdsocket.library` — the old one is kept as `bsdsocket.library.orig`.

**USB.** The default `xhci.device` (6.1) works only with Poseidon for AmigaOS
6.x; on classic Poseidon 4.x it does nothing at all. On 4.x, choose the **5.x**
driver when the installer asks. The 5.x driver also runs on Poseidon 6.x, only
more slowly, so picking it is safe if you are unsure. Poseidon itself is
distributed separately, so the installer cannot detect which one you have.

---

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

**Find your row.**

| Your Emu68 | Your Poseidon | Download | Ethernet | USB |
|---|---|---|---|---|
| Official, 1.1 alpha.1 or newer | classic 4.x | `emu68-drivers-2.0.0.lha` | **SANA-II** 3.14 + Roadshow / AmiTCP / Miami | `xhci.device` **5.3** |
| Official, 1.1 alpha.1 or newer | for AmigaOS 6.x | `emu68-drivers-2.0.0.lha` | **SANA-II** 3.14 + Roadshow / AmiTCP / Miami | `xhci.device` **6.1** |
| Custom build with the dcache extensions | classic 4.x | `emu68-drivers-2.0.0-rangeops.lha` | **netdev** 4.1 + the bundled `bsdsocket.library` | `xhci.device` **5.3** |
| Custom build with the dcache extensions | for AmigaOS 6.x | `emu68-drivers-2.0.0-rangeops.lha` | **netdev** 4.1 + the bundled `bsdsocket.library` | `xhci.device` **6.1** |

The two `-serial` archives are the same drivers with serial-port diagnostics —
take one only when chasing a problem. Installing a `-rangeops` archive on an
Emu68 without the extensions is safe: the installer checks, says so, and stops
without changing anything.

What the extensions are worth — measured TCP throughput over gigabit Ethernet
with the bundled stack:

| Archive | Emu68 | Download | Upload |
|---|---|---|---|
| standard | official build | 104 Mb/s | 79 Mb/s |
| standard | custom build with the extensions | 698 Mb/s | 477 Mb/s |
| `-rangeops` | custom build with the extensions | near line rate | near line rate |

Why the extensions make that much difference is explained in
[DEVELOPING.md](https://github.com/rondoval/emu68-driver-stack/blob/main/DEVELOPING.md#the-dcache-extensions).

---

## Component versions in this release

| Component | Version | Detailed notes |
|---|---|---|
| `emu68-common` (support library) | **1.9.0** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-common/blob/v1.9.0/RELEASE-NOTES.md) |
| `gic400.library` | **1.7** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-gic400-library/blob/v1.7/RELEASE-NOTES.md) |
| `bcmpcie.library` | **2.3** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-pcie-library/blob/v2.3/RELEASE-NOTES.md) |
| `openpci.library` | 45.12 | bundled with `bcmpcie.library` |
| `xhci.device` (6.x) | **6.1** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-xhci-driver/blob/v6.1/RELEASE-NOTES.md) |
| `xhci.device` (5.x) | **5.3** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-xhci-driver/blob/v5.3/RELEASE-NOTES.md) |
| `genet.device` (4.x, bundled stack) | **4.1** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-genet-driver/blob/v4.1/RELEASE-NOTES.md) |
| `genet.device` (3.x, SANA-II) | **3.14** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-genet-driver/blob/v3.14/RELEASE-NOTES.md) |
| `nvme.device` | **1.4** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-nvme-driver/blob/v1.4/RELEASE-NOTES.md) |
| `bsdsocket.library` (lwip-amiga) | **4.103** (lwip-amiga 1.3) | [RELEASE-NOTES.md](https://github.com/rondoval/lwip-amiga/blob/v1.3/RELEASE-NOTES.md) |

---

## What changed

### Networking — a TCP/IP stack of your own

`bsdsocket.library` joins the archive: a modern stack built on lwIP, installed
together with the 4.x Ethernet driver. It configures itself over DHCP the first
time an application opens it; a fixed address, the hostname and the driver to
use live in `ENVARC:netstack.prefs`, and `netinfo` shows what it settled on.
`mdns` looks up and announces `.local` names. Like lwIP itself, lwip-amiga is
BSD-3-Clause licensed — the rest of the stack is GPL-2.0 or MPL-2.0/GPL-2.0+.

The 4.x `genet.device` was rewritten for it. Packets are handed straight between
the stack and the Ethernet hardware with no copying in between, the Pi computes
and checks the TCP/IP checksums itself, and interrupts are batched — which is
where the speeds in the table above come from. The SANA-II driver (3.14) stays
in the archive for anyone using Roadshow, AmiTCP or Miami.

### USB — real USB 3.0 on Poseidon 6.x

The 6.x `xhci.device` line drops the translation the 5.x line has to do: a
SuperSpeed device now reaches the USB stack as a SuperSpeed device, on a real
SuperSpeed hub, because Poseidon for AmigaOS 6.x understands USB 3.0 itself. It
also supports the fast parallel transfer mode that UAS mass storage uses, so
USB 3.0 drives are noticeably quicker. The 5.x line (5.3) is unchanged apart
from being rebuilt.

### Installing

The `-rangeops` archives now ask Emu68 up front whether it supports the newer
cache instructions and stop if it does not, so you cannot end up with drivers
that refuse to start after a reboot. `gic400.library` is installed like every
other library now; previously it was skipped whenever a copy was already in
memory, which could quietly leave an old version in place. If your Emu68 carries
its own `gic400.library`, the copy in `LIBS:` is simply never used — the
installer says so on the final screen. All the installer's screens were also
reflowed to fit the Installer window, and the ReadMe gained an *After
installation* section listing what to do once you reboot.

Every other component brings its own fixes — follow the links in the table above.

---

# Release notes — Emu68 driver stack 1.2.3

Changes since 1.1.0. `nvme.device` advances to 1.2 (automount rework, SCSI and
partition reliability fixes, batched DMA cache maintenance), `bcmpcie.library`
advances to 2.1 (no longer crashes when opened on a system without
PiStorm/Emu68), and the shared `emu68-common` support library advances to
1.7.0; every other component keeps its 1.1.0 version. The stack ships as a
single `emu68-drivers-1.2.3.lha` archive with the Commodore Installer script.

---

## Breaking changes

`nvme.device` 1.2 renames automounted MBR/GPT partitions from `MS<n>:` to
`NVME<n>:`. See the [component notes](https://github.com/rondoval/emu68-nvme-driver/blob/v1.2/RELEASE-NOTES.md#breaking-changes)
for what needs updating.

---

## Component versions in this release

| Component | Version | Detailed notes |
|---|---|---|
| `emu68-common` (support library) | **1.7.0** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-common/blob/v1.7.0/RELEASE-NOTES.md) |
| `gic400.library` | 1.5 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-gic400-library/blob/v1.5/RELEASE-NOTES.md) |
| `bcmpcie.library` | **2.1** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-pcie-library/blob/v2.1/RELEASE-NOTES.md) |
| `openpci.library` | 45.12 | bundled with `bcmpcie.library` |
| `xhci.device` | 5.2 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-xhci-driver/blob/v5.2/RELEASE-NOTES.md) |
| `genet.device` | 3.11 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-genet-driver/blob/v3.11/RELEASE-NOTES.md) |
| `nvme.device` | **1.2** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-nvme-driver/blob/v1.2/RELEASE-NOTES.md) |

---

## What changed

### `nvme.device` 1.2 — automount rework and reliability fixes

The driver drops its vendored A4091 mounter for the shared `rondoval/mounter`
fork, mounting FAT and NTFS partitions on MBR, GPT and superfloppy disks from a
per-filesystem recipe instead of hardcoded policy. `HD_SCSICMD` responses (INQUIRY,
MODE SENSE, REQUEST SENSE, READ CAPACITY, VPD, READ/WRITE) no longer overrun the
caller's buffer, legacy MBR/GPT partition extents are now exact instead of
CHS-rounded, and partition-table parsing past 4 GB and of malformed structures is
hardened. DMA cache maintenance moves onto `emu68-common` 1.7.0's `cache_ops.h`,
batched and emitted inline. See the
[component notes](https://github.com/rondoval/emu68-nvme-driver/blob/v1.2/RELEASE-NOTES.md) for full detail,
including the breaking automount rename above.

### `bcmpcie.library` 2.1 — crash fix for non-Emu68 systems

Opening the library on an Amiga without PiStorm/Emu68 used to crash the machine.
It now fails cleanly instead: `OpenLibrary` returns `NULL`, so software that
needs PCIe can handle its absence gracefully. See the
[component notes](https://github.com/rondoval/emu68-pcie-library/blob/v2.1/RELEASE-NOTES.md) for detail.

---

## Build & tooling

### `emu68-common` 1.7.0

The shared support library gains the `barrier.h` and `cache_ops.h` headers and a
standard `strncmp`, and goes back to targeting NDK 3.2 only. `nvme.device` 1.2 is
the first driver to consume `cache_ops.h`, for its batched, inlined DMA cache
maintenance (see above); `xhci.device` and `genet.device` are otherwise
unchanged from 1.1.0.

### Cache-op routing selectable at configure time

`cache_ops.h` emits its DMA cache range operations inline, through a private
LINE-F opcode that only a patched Emu68 decodes. The new
`EMU68_FORCE_LVO_CACHE_OPS` option (default `OFF`) routes `cache_pre_dma()` /
`cache_post_dma()` back through exec's `CachePreDMA` / `CachePostDMA` for an Emu68
that doesn't carry the opcode, and is forwarded to the components that consume
`cache_ops.h` — `xhci.device`, `genet.device` and `nvme.device`. CI builds set it
`ON`, so released binaries keep the LVO path. See
[DEVELOPING.md](https://github.com/rondoval/emu68-driver-stack/blob/main/DEVELOPING.md#the-dcache-extensions).

---


# Release notes — Emu68 driver stack 1.1.0

Changes since 1.0.6. `xhci.device` advances to 5.2; every other component is
unchanged. The stack ships as a single `emu68-drivers-1.1.0.lha` archive with the
Commodore Installer script.

---

## Component versions in this release

| Component | Version | Detailed notes |
|---|---|---|
| `emu68-common` (support library) | 1.6.0 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-common/blob/v1.6.0/RELEASE-NOTES.md) |
| `gic400.library` | 1.5 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-gic400-library/blob/v1.5/RELEASE-NOTES.md) |
| `bcmpcie.library` | 2.0 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-pcie-library/blob/v2.0/RELEASE-NOTES.md) |
| `openpci.library` | 45.12 | bundled with `bcmpcie.library` |
| `xhci.device` | **5.2** | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-xhci-driver/blob/v5.2/RELEASE-NOTES.md) |
| `genet.device` | 3.11 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-genet-driver/blob/v3.11/RELEASE-NOTES.md) |
| `nvme.device` | 1.1 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-nvme-driver/blob/v1.1/RELEASE-NOTES.md) |

---

## What changed

### `xhci.device` 5.2 — USB 3.0-aware stack compatibility

`xhci.device` presents SuperSpeed devices to the USB stack as high-speed through
its USB 3.0 ↔ USB 2.0 translation layer. The device descriptor returned to the
stack now clamps `bcdUSB` to `0x0210` for devices reporting USB 3.0 or later, so
the advertised USB revision matches that high-speed presentation. This keeps a
USB 3.0-aware stack — one that reads `bcdUSB` — from seeing a SuperSpeed revision
that contradicts the device it is handed. See the
[component notes](https://github.com/rondoval/emu68-xhci-driver/blob/v5.2/RELEASE-NOTES.md) for details.


# Release notes — Emu68 driver stack 1.0.6

Changes since 1.0.5. A build-system update only — the drivers themselves are
unchanged from 1.0.5 (every component keeps its 1.0.5 version). Not tagged as a
release; superseded by 1.1.0.

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
| `emu68-common` (support library) | 1.6.0 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-common/blob/v1.6.0/RELEASE-NOTES.md) |
| `gic400.library` | 1.5 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-gic400-library/blob/v1.5/RELEASE-NOTES.md) |
| `bcmpcie.library` | 2.0 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-pcie-library/blob/v2.0/RELEASE-NOTES.md) |
| `openpci.library` | 45.12 | bundled with `bcmpcie.library` |
| `xhci.device` | 5.1 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-xhci-driver/blob/v5.1/RELEASE-NOTES.md) |
| `genet.device` | 3.11 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-genet-driver/blob/v3.11/RELEASE-NOTES.md) |
| `nvme.device` | 1.1 | [RELEASE-NOTES.md](https://github.com/rondoval/emu68-nvme-driver/blob/v1.1/RELEASE-NOTES.md) |

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
See the [project README](https://github.com/rondoval/emu68-driver-stack/blob/main/README.md)
for build details and per-component requirements.
