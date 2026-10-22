#include <stdint.h>
#include "console.h"
#include "fdt.h"
#include "loader.h"
#include "/home/exerczz1/hackios/hackios-xnu-kernel/xnuloader/efi.h"

#define PSCI_CPU_ON 0xc4000003UL
#define PSCI_SYSTEM_RESET 0x84000009UL
#define PAYLOAD_BASE 0xF0000000ULL
#define PAYLOAD_MAGIC 0x50554E58u

extern char dsi_flush_loop[];
extern efi_status EFIAPI efi_main(efi_handle image, efi_system_table *st);
char __ImageBase = 0;

static uint64_t smc(uint64_t fn, uint64_t a1, uint64_t a2, uint64_t a3)
{
	register uint64_t x0 __asm__("x0") = fn;
	register uint64_t x1 __asm__("x1") = a1;
	register uint64_t x2 __asm__("x2") = a2;
	register uint64_t x3 __asm__("x3") = a3;

	__asm__ volatile("smc #0"
			 : "+r"(x0), "+r"(x1), "+r"(x2), "+r"(x3)
			 :
			 : "x4", "x5", "x6", "x7", "x8", "x9", "x10", "x11",
			   "x12", "x13", "x14", "x15", "x16", "x17", "memory");
	return x0;
}

static void copy64(uintptr_t dst, uintptr_t src, uint64_t n)
{
	volatile uint64_t *d = (volatile uint64_t *)dst;
	volatile const uint64_t *s = (volatile const uint64_t *)src;
	for (uint64_t i = 0; i < (n + 7) / 8; i++)
		d[i] = s[i];
}

static efi_gop_mode_info gop_info;
static efi_gop_mode gop_mode;
static efi_gop gop;
static efi_text_output text_out;
static efi_boot_services boot_services;
static efi_runtime_services runtime_services;
static efi_system_table system_table;

static uintptr_t bump_mem = 0x60000000ULL;

static efi_status EFIAPI efi_set_watchdog_timer(uint64_t timeout, uint64_t code, uint64_t size, char16 *data)
{
	(void)timeout;
	(void)code;
	(void)size;
	(void)data;
	return 0;
}

static efi_status EFIAPI efi_locate_protocol(const efi_guid *guid, void *reg, void **iface)
{
	static const efi_guid gop_guid = EFI_GOP_GUID;
	(void)reg;
	if (guid && iface) {
		const uint8_t *g1 = (const uint8_t *)guid;
		const uint8_t *g2 = (const uint8_t *)&gop_guid;
		int match = 1;
		for (int i = 0; i < 16; i++) {
			if (g1[i] != g2[i]) {
				match = 0;
				break;
			}
		}
		if (match) {
			*iface = &gop;
			return 0;
		}
	}
	return 0x800000000000000eULL;
}

static efi_status EFIAPI efi_get_memory_map(uint64_t *size, void *map, uint64_t *key, uint64_t *desc_size, uint32_t *desc_ver)
{
	if (!size || !map || !key || !desc_size || !desc_ver)
		return 0x8000000000000002ULL;
	*desc_size = sizeof(efi_memory_descriptor);
	*desc_ver = 1;
	*key = 1;
	if (*size < sizeof(efi_memory_descriptor)) {
		*size = sizeof(efi_memory_descriptor);
		return 0x8000000000000005ULL;
	}
	*size = sizeof(efi_memory_descriptor);
	efi_memory_descriptor *d = (efi_memory_descriptor *)map;
	d[0].type = EfiConventionalMemory;
	d[0].pad = 0;
	d[0].phys_start = 0x80000000ULL;
	d[0].virt_start = 0;
	d[0].pages = 0x60000000ULL >> 12;
	d[0].attribute = 0;
	return 0;
}

static efi_status EFIAPI efi_allocate_pages(int type, int mem_type, uint64_t pages, uint64_t *addr)
{
	(void)type;
	(void)mem_type;
	if (!addr)
		return 0x8000000000000002ULL;
	*addr = bump_mem;
	bump_mem += pages << 12;
	return 0;
}

static efi_status EFIAPI efi_stall(uint64_t us)
{
	con_flush_force();
	uint64_t start = 0;
	__asm__ volatile("mrs %0, cntvct_el0" : "=r"(start));
	uint64_t ticks = us * 13;
	uint64_t cur = 0;
	uint64_t last_pet = start;
	*(volatile uint32_t *)0x10007008 = 0x1971;
	do {
		__asm__ volatile("mrs %0, cntvct_el0" : "=r"(cur));
		if (cur - last_pet >= 13000000) {
			*(volatile uint32_t *)0x10007008 = 0x1971;
			last_pet = cur;
		}
	} while (cur - start < ticks);
	*(volatile uint32_t *)0x10007008 = 0x1971;
	return 0;
}

static efi_status EFIAPI efi_locate_handle_buffer(int type, const efi_guid *guid, void *key, uint64_t *count, efi_handle **buf)
{
	(void)type;
	(void)guid;
	(void)key;
	if (count)
		*count = 0;
	if (buf)
		*buf = 0;
	return 0x800000000000000eULL;
}

static efi_status EFIAPI efi_handle_protocol(efi_handle h, const efi_guid *guid, void **iface)
{
	(void)h;
	return efi_locate_protocol(guid, 0, iface);
}

static void EFIAPI efi_reset_system(int type, efi_status status, uint64_t size, void *data)
{
	(void)type;
	(void)status;
	(void)size;
	(void)data;
	smc(PSCI_SYSTEM_RESET, 0, 0, 0);
	for (;;) {}
}

static efi_status EFIAPI con_out_string(struct efi_text_output *self, const char16 *str)
{
	(void)self;
	if (!str)
		return 0;
	static char buf[128];
	static int len = 0;
	while (*str) {
		char c = (char)(*str++);
		if (c == '\r')
			continue;
		if (c == '\f') {
			con_clear(0);
			len = 0;
			continue;
		}
		if (c == '\v') {
			if (len > 0) {
				buf[len] = 0;
				con_str("", buf);
				len = 0;
			}
			con_flush_force();
			continue;
		}
		if (c == '\n') {
			buf[len] = 0;
			con_str("", buf);
			len = 0;
		} else if (len < 120) {
			buf[len++] = c;
		}
	}
	return 0;
}

const char *loader_boot(uintptr_t dtb)
{
	uint64_t rd_start, rd_end;

	if (!fdt_chosen_u64(dtb, "linux,initrd-start", &rd_start) ||
	    !fdt_chosen_u64(dtb, "linux,initrd-end", &rd_end))
		return "no initrd in /chosen";
	con_hex2("INITRD", "lo=", rd_start, "hi=", rd_end);

	volatile uint32_t *p_magic = (volatile uint32_t *)rd_start;
	if (*p_magic != PAYLOAD_MAGIC)
		return "no XNUP payload";

	con_str("LOADER", "copying payload to PAYLOAD_BASE");
	copy64(PAYLOAD_BASE, rd_start, rd_end - rd_start);

	gop_info.version = 0;
	gop_info.width = con_w;
	gop_info.height = con_h;
	gop_info.pixel_format = 1;
	gop_info.pixels_per_scanline = con_w;

	gop_mode.max_mode = 1;
	gop_mode.mode = 0;
	gop_mode.info = &gop_info;
	gop_mode.info_size = sizeof(gop_info);
	gop_mode.fb_base = (uint64_t)(uintptr_t)con_fb;
	gop_mode.fb_size = (uint64_t)con_stride * con_h;

	gop.mode = &gop_mode;

	text_out.output_string = con_out_string;

	boot_services.set_watchdog_timer = efi_set_watchdog_timer;
	boot_services.locate_protocol = efi_locate_protocol;
	boot_services.locate_handle_buffer = efi_locate_handle_buffer;
	boot_services.handle_protocol = efi_handle_protocol;
	boot_services.get_memory_map = efi_get_memory_map;
	boot_services.allocate_pages = efi_allocate_pages;
	boot_services.stall = efi_stall;

	runtime_services.reset_system = efi_reset_system;

	system_table.bs = &boot_services;
	system_table.rt = &runtime_services;
	system_table.con_out = &text_out;

	con_str("LOADER", "entering efi_main");
	efi_main(0, &system_table);

	return "efi_main returned";
}
