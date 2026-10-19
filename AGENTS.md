# Working on ios-agate

Adaptation of the ios-sweet project (XNU on Qualcomm SM7150) to Xiaomi 11T
(`agate`, MediaTek MT6893 / Dimensity 1200).

- Read `NOTES.md` before starting; it contains the project goal, hardware facts,
  current blocker, local artifact locations and the next concrete action.
- The user switches agents frequently. Update the active handoff in `NOTES.md`
  after each milestone and before stopping. Record commits, CI run IDs, exact
  build/boot results and unfinished work. Distinguish observations from guesses.
- Commit completed changes with `git commit -s -S`. Use `gh` for GitHub Actions
  kernel builds and logs. Local single-file cross-compiles are useful before
  spending a CI run.
- Device bring-up uses temporary `fastboot boot` images. Preserve the Android
  installation and partition backups. The iOS root goes into the existing
  `userdata` partition (no GPT changes). Keep bootloaders (preloader, lk, lk2),
  recovery, nvram, nvdata, nvcfg, persist and the backups intact, and confirm
  each destructive step with the user before running it.
- Keep device dumps, serial numbers and downloaded Apple artifacts out of git.

## Target device: Xiaomi 11T (agate)

- SoC: MediaTek MT6893 (Dimensity 1200), 4×A55 + 3×A78 + 1×A78 Ultra
- RAM base: `0x40000000` (not `0x80000000` like sweet)
- GICv3: GICD `0x0c000000`, GICR `0x0c040000`
- Timer: 13.0 MHz (not 19.2), virtual timer INTID 27 (not 19)
- UFS: `0x11270000` (JEDEC UFSHCI, standard registers)
- Framebuffer: `0x7E020000` (from LK, confirm on live device)
- UART: `0x11002000` (921600 baud) — available for debug, unlike sweet
- Touch: ST FTS (SPI6) or Goodix GT9886 (I2C0 `0x11015000` slave `0x5D`)
- Buttons: MTK KPD `0x10010000` (vol) + PMIC MT6359 pwrap (power)
- No SPMI, no GENI, no RPMh — all Qualcomm bus code must be replaced
- PSCI `smc`, CPU_ON `0xC4000003`, MPIDR `core << 8` (`0x000`–`0x700`)

## Stock firmware location

```
~/idktool/work/stock_extracted/miui_AGATEGlobal_OS1.0.17.0.UKWMIXM_2deb69168e_14.0/partitions/
```

Extracted DTB and DTS are in `agate_analysis/boot_unpacked/`.
