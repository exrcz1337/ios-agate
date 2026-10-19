# ios-agate

**Apple's iOS 16 running on a Xiaomi 11T.**

Fork of [ios-sweet](https://github.com/nickcyber9/ios-sweet) adapted for the Xiaomi 11T (`agate`, MediaTek MT6893 / Dimensity 1200). Ports Apple's open-source XNU kernel (xnu-8796, the iOS 16 generation) to a MediaTek SoC. On top of it runs the **unmodified iOS 16.7.16 (20H392) userland of the iPhone X**: launchd, the system daemons, backboardd, SpringBoard and the stock apps.

> Experimental bring-up, not a usable phone OS. Many things are missing or stubbed (see below), and Apple's security model is mostly switched off. It installs into the `userdata` partition and so **erases Android's user data**.

## Status

Work in progress. The upstream project (`ios-sweet`) boots to the iOS home screen on a Redmi Note 10 Pro (Qualcomm SM7150). This fork adapts it to the MediaTek Dimensity 1200 platform.

## What works (upstream, on sweet)

| Area | State |
| --- | --- |
| Boot | Stock Xiaomi bootloader → `fastboot boot` of our shim → XNU |
| CPU | Cortex-A55 cores via PSCI, 16K pages, GICv3 interrupts, timers |
| Storage | Own UFS host driver; the iOS root is a journaled HFS+ volume in `userdata`, read/write |
| iOS userland | Real iPhone X 16.7.16 root filesystem and shared cache; launchd and the system daemons run |
| Display | Kernel IOSurface + IOMobileFramebuffer services; CoreAnimation renders in software; frames are copied into the bootloader's framebuffer. Presented to iOS as an iPhone X panel (1125×2436) |
| GUI | backboardd, SpringBoard, lock screen, home screen, Control Center, notification center, Settings |
| Touch | HID digitizer events from touch controller |
| Buttons | Power, volume up/down as HID consumer keys; lock/wake works |
| Device identity | iPhone X (`iPhone10,3` / `D22AP`): no Home button, gesture UI |

## What changes for agate (MT6893)

The SoC vendor changes from Qualcomm to MediaTek. The core architecture (ARMv8, GICv3, PSCI, UFSHCI) is the same, but every bus-level peripheral driver is different:

| Component | sweet (SM7150) | agate (MT6893) |
| --- | --- | --- |
| GIC | GICD `0x17a00000`, GICR `0x17a60000` | GICD `0x0c000000`, GICR `0x0c040000` |
| Timer | 19.2 MHz, VTIMER INTID 19 | 13.0 MHz, VTIMER INTID 27 |
| UFS | `0x01d84000` | `0x11270000` |
| RAM base | `0x80000000` | `0x40000000` |
| Framebuffer | `0x9c000000` (fixed) | `0x7E020000` (from LK) |
| Touch | Goodix GT9896, Qualcomm GENI I²C | ST FTS (SPI) / Goodix GT9886 (MTK I²C) |
| Buttons | Qualcomm SPMI + PM6150 | MTK KPD `0x10010000` + MT6359 pwrap |
| Power rails | Qualcomm RPMh | MT6359/MT6360 via pwrap/I²C |
| USB | Synopsys DWC3 | MediaTek MTU3 |
| Debug UART | None (SPI-mode) | UART0 `0x11002000` (921600 baud) |

~55 of the 81 XNU kernel patches are hardware-independent and carry over directly. About 10 need address/name changes. The Qualcomm SPMI/GENI/RPMh input drivers (~8 patches) must be rewritten for MediaTek buses.

## How it boots

```
LK (stock Xiaomi bootloader, unlocked)
  -> fastboot boot shim-boot.img              (temporary; nothing is flashed to boot)
     -> shim: own MMU setup, reads the live FDT, loads the payload from the ramdisk
        -> XNU Mach-O + generated Apple Device Tree (ADT) + boot-args
           -> XNU -> UFS driver -> HFS+ root in the userdata partition
              -> dyld + shared cache -> launchd -> daemons -> backboardd + SpringBoard
```

Unlike sweet, agate has a hardware UART at `0x11002000` (921600 baud) for debug output. The kernel also draws its console into the framebuffer that LK leaves at `0x7E020000`, and keeps a persistent 4 MiB log ring at the end of `userdata`.

## How to do it yourself

You need a Xiaomi 11T (`agate`, global variant, MT6893) with an **unlocked bootloader**, a Linux PC, and a GitHub account for the kernel build. **Everything on `userdata` is lost.** Bootloaders, recovery, nvram and persist partitions are never touched.

### 0. Back up the phone

Boot OrangeFox (or any recovery with adb root) temporarily and pull at least `persist`, `nvram`, `nvdata`, `nvcfg`, `boot`, `dtbo`, `vbmeta`, `lk`, `lk2`, `preloader_raw`. Keep them off git; `.gitignore` already excludes `backup/`, `dtb/` and `recovery/`.

The shim needs the stock DTB. Unpack your phone's stock `boot.img`:

```sh
python3 tools/unpack_bootv2.py backup/boot.img dtb/boot_unpacked   # -> dtb/boot_unpacked/dtb
```

### 1. Build the kernel

The kernel builds on GitHub's macOS runners with [blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build). The workflow fetches xnu-8796, applies `xnu/patches/` in order, and also stages the pinned open-source libpthread, HFS and BearSSL sources it needs. Fork the repo (public repos get free macOS minutes) and run:

```sh
gh workflow run xnu.yml -R YOU/ios-agate
gh run download RUN_ID -R YOU/ios-agate -n xnu-kernel -D xnu/out
```

To check a patch locally before spending a CI run, `tools/xnu-cc.py` replays the compile commands of a previous CI log for single files.

### 2. Build the iOS root image

Download the iPhone X (iPhone10,3) iOS 16.7.16 (20H392) IPSW from Apple. Then, on Linux, with `apfs-fuse`, `hfsprogs` and sudo:

```sh
tools/mkiosroot.sh OS.dmg SystemOS.dmg AppOS.dmg ios16-root.img 16G
sudo fsck.hfsplus -fy ios16-root.img
sudo mount -t hfsplus -o loop,force ios16-root.img /mnt/iosroot
sudo python3 tools/sweet-root-tweaks.py /mnt/iosroot
sudo umount /mnt/iosroot
img2simg ios16-root.img ios16-root.simg
```

The device tree builder copies `/product` from the real iPhone X device tree, which MobileGestalt needs. Extract it once:

```sh
python3 tools/remotezip.py IPSW_URL DeviceTree.d22ap.im4p research/ipsw-x/dt
ipsw img4 im4p extract research/ipsw-x/dt/Firmware/all_flash/DeviceTree.d22ap.im4p -o research/ipsw-x/d22ap.adt
```

### 3. Build the boot image

Needs `aarch64-linux-gnu-gcc` and `mkbootimg`.

```sh
python3 tools/mkadt.py shim/out/agate.adt --highmem
python3 tools/mkpayload.py xnu/out/kernel.development.agate shim/out/agate.adt shim/out/payload.bin \
    --cmdline 'debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 agatefb_noconsole=1 agatefb_hz=30'
shim/build.sh ../shim/out/payload.bin      # -> shim/out/shim-boot.img
```

What the less obvious boot-args do:

| Boot-arg | Effect |
| --- | --- |
| `rd=ufsroot0 ufsrw=1 rootrw=1` | Root on the `userdata` partition, writable |
| `cpus=1` | Start one A55 core only; increase after bring-up is stable |
| `launchd_unsecure_cache=1` | launchd accepts its job cache without AMFI |
| `wdt=-1 wdt_test=no_user_checkin` | No hardware watchdog |
| `agatefb_noconsole=1` | Stop drawing kernel text over the GUI |
| `agatefb_hz=30` | Panel refresh rate of the CPU copy |

### 4. Flash the root and boot

```sh
fastboot -S 512M flash userdata ios16-root.simg
fastboot boot shim/out/shim-boot.img
```

To get back to fastboot, hold Power + Volume down.

### 5. Read the kernel log

```sh
fastboot boot recovery/recovery.img        # OrangeFox, temporary
tools/sweet-log-pull.sh logs/boot.txt      # 4 MiB console ring from the end of userdata
adb reboot bootloader
```

### QEMU

`tools/qemu-sweet.py` boots the same kernel on QEMU `virt` with a test RAM-disk root. It is useful for kernel-only changes; see `NOTES.md`.

## Repository layout

| Path | What |
| --- | --- |
| `shim/` | Bare-metal boot shim (C + asm) packed as an Android boot.img v2 |
| `xnu/patches/` | The XNU patch series (applied in order by CI), plus staging scripts for libpthread, HFS and BearSSL |
| `.github/workflows/xnu.yml` | Kernel CI build |
| `tools/mkadt.py` | Generates the Apple Device Tree from agate's MMIO layout and the iPhone X identity |
| `tools/mkpayload.py` | Packs kernel + ADT + boot-args into the shim payload |
| `tools/mkiosroot.sh` | Builds the HFS+ iOS root from the IPSW images |
| `tools/sweet-root-tweaks.py` | Bring-up changes to the root (Setup skip, activation, daemons) |
| `tools/sweet-log-pull.sh`, `sweet-log.py` | Read the persistent kernel log from recovery |
| `tools/sweet-crash.py` | Symbolicate console crash reports |
| `tools/xnu-cc.py` | Local single-file compile check from a CI log |
| `tools/qemu-sweet.py` | QEMU test boots with framebuffer text decoding |
| `tools/adt.py`, `remotezip.py`, `unpack_bootv2.py`, `sparsediff.py` | Helpers |
| `NOTES.md` | Detailed engineering log: every boot, crash and decision, plus hardware facts |

Not in git: partition backups, live device trees, recovery images, Apple firmware and root images, and downloaded or generated build trees. They contain device serials and calibration data, or Apple's copyrighted files.

## Kernel patches

| # | What |
| --- | --- |
| 0001–0009 | Toolchain compatibility, AGATE machine config, non-PAC arm64, stubs for Apple-internal pieces |
| 0010–0018 | Early framebuffer console, physmap fix, PRNG without corecrypto, device-tree platform expert, timer PPI, boot CPU driver |
| 0019–0020 | Apple open-source libpthread kernel provider; BearSSL AES |
| 0021–0027 | RAM-disk root, mockfs, SHA-256, minimal AMFI, Apple open-source HFS+, MD5 |
| 0028–0034 | UFS host driver and root device, read/write root, DMA above 4 GiB |
| 0035–0045 | Entitlements, bindfs, AppleKeyStore stub, IOWatchdog, console crash reports |
| 0046 | IOSurface (IOCoreSurfaceRoot) and IOMobileFramebuffer (AppleCLCD) services |
| 0047–0055 | Diagnostics: persistent log, /dev/null tee, IOKit trace, heap strings and user stack sampler on crash; permissive Sandbox policy; HFS rename-swap; AppleKeyStore selectors |
| 0056–0057 | Throttled panel copy; no external identity resolver |
| 0058 | HID event services. Apple's IOHIDFamily-1915.140.3 user client and event queue, matching the iOS 16.7 userland |
| 0059 | iPhone X identity (`hw.product` / `hw.target` from the device tree) |
| 0060 | Power and volume keys over MTK KPD / pwrap; touch over MTK I²C |
| 0061 | Present the display as 1125×2436 |
| 0062 | Touch rail power; battery power source |
| 0063 | Touch controller I²C protocol (Goodix GT9886 or ST FTS) |
| 0064 | Grant PRIV_WORK_INTERVAL (UIKit's CoreAnimation work interval) |
| 0065 | SMP: secondary cores via PSCI CPU_ON |
| 0066–0067 | Fault-region crash info; console mute |
| 0068 | IOSurface lookup semantics for already-mapped surfaces |
| 0069 | Batched persistent-log flushes |

## Key hardware facts (MT6893)

- RAM: DRAM starts at `0x40000000`. Upper bank at `0x100000000` (8 GiB+ models). MediaTek reserved carve-outs are all below `0xD0000000`.
- GICv3: GICD `0x0c000000`, GICR `0x0c040000`. Virtual timer INTID 27 (standard ARM), not 19 like Qualcomm.
- PSCI through `smc`, 13.0 MHz timer, ARMv8.2 without pointer authentication. MPIDR uses Aff1 for the core number (`0x000`–`0x700`).
- CPUs: 4× Cortex-A55 (2.0 GHz) + 3× Cortex-A78 (2.6 GHz) + 1× Cortex-A78 Ultra (3.0 GHz).
- Panel: 1080×2400 AMOLED, DSC command mode, 60/120 Hz. Continuous splash from LK at `0x7E020000`.
- UFS: JEDEC UFSHCI at `0x11270000` (standard register interface, same protocol as sweet).
- Touch: ST FTS (SPI6) or Goodix GT9886 (I²C0 `0x11015000` slave `0x5D`) or Goodix GT9896S (SPI4). IRQ GPIO 21, Reset GPIO 20.
- Buttons: Volume up/down on MTK KPD (`0x10010000`), power on PMIC MT6359 via pwrap (`0x10026000`).
- PMIC: MT6359 (main, via pwrap) + MT6360 (charger/LDO, I²C5 `0x11F00000` slave `0x34`).
- UART: debug UART0 at `0x11002000`, 921600 baud (usable for kernel log).

More in [`NOTES.md`](NOTES.md).

## Credits

Built on Apple's open-source releases (xnu, IOHIDFamily, libpthread, hfs), [BearSSL](https://bearssl.org), [blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build), [ipsw](https://github.com/blacktop/ipsw), the upstream [ios-sweet](https://github.com/nickcyber9/ios-sweet) project, MediaTek/Xiaomi's published Linux kernel sources for the hardware details, and [OrangeFox Recovery](https://orangefox.download). iOS itself is Apple's and is not distributed here.
