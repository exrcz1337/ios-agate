#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

if command -v aarch64-linux-gnu-gcc >/dev/null 2>&1; then
	CC=aarch64-linux-gnu-gcc
	OBJCOPY=aarch64-linux-gnu-objcopy
	READELF=aarch64-linux-gnu-readelf
	NM=aarch64-linux-gnu-nm
	LD=aarch64-linux-gnu-gcc
	LDFLAGS="-static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N"
	PIC_FLAG="-fno-pic"
else
	CC="clang --target=aarch64-linux-gnu"
	OBJCOPY=llvm-objcopy
	READELF=llvm-readelf
	NM=llvm-nm
	LD=ld.lld
	LDFLAGS="-T shim.ld --build-id=none -N"
	PIC_FLAG="-fpie"
fi

if command -v mkbootimg >/dev/null 2>&1; then
	MKBOOTIMG=mkbootimg
else
	MKBOOTIMG="python3 ../tools/mkbootimg.py"
fi

CFLAGS="-O2 -ffreestanding -nostdlib $PIC_FLAG -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"
mkdir -p out

for f in start.S shim.c console.c mmu.c fdt.c loader.c ufs.c; do
	$CC $CFLAGS -c $f -o out/${f%.*}.o
done

abs=$($READELF -r out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations in C objects" >&2; exit 1; }

if [ "$LD" = "ld.lld" ]; then
	$LD $LDFLAGS out/start.o out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o -o out/shim.elf
else
	$LD $CFLAGS $LDFLAGS out/start.o out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o -o out/shim.elf
fi

$OBJCOPY -O binary out/shim.elf out/Image
size=$($NM out/shim.elf | awk '$3=="_end"{print strtonum("0x"$1)}')
truncate -s "$size" out/Image
gzip -n -9 -c out/Image > out/Image.gz

if [ -n "${1:-}" ]; then
	cp "$1" out/ramdisk.bin
else
	(cd out && rm -rf rd && mkdir rd && cd rd && find . | cpio -o -H newc --quiet | gzip -9 > ../ramdisk.bin)
fi

DTB=""
if [ -f ../agate_analysis/boot_unpacked/dtb ]; then
	DTB=../agate_analysis/boot_unpacked/dtb
elif [ -f ../dtb/boot_unpacked/dtb ]; then
	DTB=../dtb/boot_unpacked/dtb
fi

DTB_ARG=""
if [ -n "$DTB" ]; then
	DTB_ARG="--dtb $DTB"
fi

$MKBOOTIMG --header_version 2 --kernel out/Image.gz --ramdisk out/ramdisk.bin \
	$DTB_ARG --base 0x40000000 --kernel_offset 0x80000 --ramdisk_offset 0x11100000 \
	--tags_offset 0x07c80000 --dtb_offset 0x07c80000 --pagesize 2048 \
	--os_version 0x18000197 \
	--cmdline "bootopt=64S3,32N2,64N2 buildvariant=user" -o out/shim-boot.img

gcc -O1 -Wall -o out/host_test console.c host_test.c && ./out/host_test
ls -l out/Image out/Image.gz out/shim-boot.img
