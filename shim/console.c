#include "console.h"
#include "font.h"

#define SCALE		3
#define CH_W		(8 * SCALE)
#define CH_H		(16 * SCALE)
#define MARGIN		24
#define LABEL_COLS	8

volatile void *con_fb = (volatile void *)FB_BASE;
uint32_t con_stride = FB_STRIDE;
uint32_t con_w = FB_W;
uint32_t con_h = FB_H;
uint32_t con_bpp = 4;
uint32_t con_bswap = 0;

static uint32_t con_bg;
static int row;

void con_flush(void)
{
#ifndef __x86_64__
	__asm__ volatile("dsb sy" ::: "memory");
	*(volatile uint32_t *)0x14117020 = 1;
	*(volatile uint32_t *)0x1400e000 = 0;
	*(volatile uint32_t *)0x1400e000 = 1;
#endif
}

void con_init(void)
{
#ifndef __x86_64__
	uint32_t src_on = *(volatile uint32_t *)0x1400002c;
	int layer = 0;
	if (src_on & 1)
		layer = 0;
	else if (src_on & 2)
		layer = 1;
	else if (src_on & 4)
		layer = 2;
	else if (src_on & 8)
		layer = 3;

	uint32_t l_size = *(volatile uint32_t *)(0x14000038UL + (uintptr_t)layer * 0x20UL);
	uint32_t l_addr = *(volatile uint32_t *)(0x14000f40UL + (uintptr_t)layer * 0x20UL);

	uint32_t w = l_size & 0xfff;
	uint32_t h = (l_size >> 16) & 0xfff;
	if (w >= 320 && w <= 4096)
		con_w = w;
	else
		con_w = FB_W;

	if (h >= 480 && h <= 4096)
		con_h = h;
	else
		con_h = FB_H;

	con_bpp = 4;
	con_stride = con_w * 4;
	con_bswap = 1;

	uint32_t rdma_fb = *(volatile uint32_t *)0x14004f00;
	if (l_addr >= 0x40000000 && l_addr < 0xc0000000)
		con_fb = (volatile void *)(uintptr_t)l_addr;
	else if (rdma_fb >= 0x40000000 && rdma_fb < 0xc0000000)
		con_fb = (volatile void *)(uintptr_t)rdma_fb;
	else
		con_fb = (volatile void *)FB_BASE;

	volatile uint32_t *p_con = (volatile uint32_t *)(0x14000030UL + (uintptr_t)layer * 0x20UL);
	volatile uint32_t *p_pitch = (volatile uint32_t *)(0x14000044UL + (uintptr_t)layer * 0x20UL);
	uint32_t val = *p_con;
	*p_con = (val & ~((0xf << 12) | (1 << 24) | (1 << 25))) | (3 << 12) | (1 << 24);
	*p_pitch = con_stride | (1 << 28);
	con_flush();
#endif
}

static inline void put_pixel(int x, int y, uint32_t c)
{
	if ((unsigned)x >= con_w || (unsigned)y >= con_h)
		return;
	uint8_t *p = (uint8_t *)con_fb + y * con_stride + x * con_bpp;
	uint8_t r = (c >> 16) & 0xff;
	uint8_t g = (c >> 8) & 0xff;
	uint8_t b = c & 0xff;
	if (con_bswap) {
		uint8_t t = r;
		r = b;
		b = t;
	}
	if (con_bpp == 3) {
		p[0] = r;
		p[1] = g;
		p[2] = b;
	} else if (con_bpp == 4) {
		p[0] = r;
		p[1] = g;
		p[2] = b;
		p[3] = 0xff;
	} else if (con_bpp == 2) {
		uint16_t v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
		*(uint16_t *)p = v;
	}
}

void con_clear(uint32_t bg)
{
	con_bg = bg;
	row = 0;
	uint8_t r = (bg >> 16) & 0xff;
	uint8_t g = (bg >> 8) & 0xff;
	uint8_t b = bg & 0xff;
	if (con_bswap) {
		uint8_t t = r;
		r = b;
		b = t;
	}
	if (con_bpp == 3) {
		for (int y = 0; y < (int)con_h; y++) {
			uint8_t *line = (uint8_t *)con_fb + y * con_stride;
			for (int x = 0; x < (int)con_w; x++) {
				line[x * 3 + 0] = r;
				line[x * 3 + 1] = g;
				line[x * 3 + 2] = b;
			}
		}
	} else if (con_bpp == 4) {
		for (int y = 0; y < (int)con_h; y++) {
			uint8_t *line = (uint8_t *)con_fb + y * con_stride;
			for (int x = 0; x < (int)con_w; x++) {
				line[x * 4 + 0] = r;
				line[x * 4 + 1] = g;
				line[x * 4 + 2] = b;
				line[x * 4 + 3] = 0xff;
			}
		}
	} else if (con_bpp == 2) {
		uint16_t v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
		for (int y = 0; y < (int)con_h; y++) {
			uint16_t *line = (uint16_t *)((uint8_t *)con_fb + y * con_stride);
			for (int x = 0; x < (int)con_w; x++)
				line[x] = v;
		}
	}
	con_flush();
}

static void put_char(int col, char ch, uint32_t fg)
{
	if (ch < 0x20 || ch > 0x7e)
		ch = '?';
	const unsigned char *g = font8x16[ch - 0x20];
	int x0 = MARGIN + col * CH_W, y0 = MARGIN + row * CH_H;
	if (x0 + CH_W > (int)con_w || y0 + CH_H > (int)con_h)
		return;
	for (int gy = 0; gy < 16; gy++)
		for (int gx = 0; gx < 8; gx++) {
			uint32_t c = (g[gy] & (0x80 >> gx)) ? fg : con_bg;
			for (int sy = 0; sy < SCALE; sy++)
				for (int sx = 0; sx < SCALE; sx++)
					put_pixel(x0 + gx * SCALE + sx, y0 + gy * SCALE + sy, c);
		}
}

static int put_str(int col, const char *s, uint32_t fg)
{
	while (*s)
		put_char(col++, *s++, fg);
	return col;
}

static void fmt_hex(char *buf, uint64_t v, int digits)
{
	static const char hex[] = "0123456789ABCDEF";
	for (int i = 0; i < digits; i++)
		buf[i] = hex[(v >> (4 * (digits - 1 - i))) & 0xf];
	buf[digits] = 0;
}

void con_skip(void)
{
	row++;
}

void con_str(const char *label, const char *s)
{
	put_str(0, label, YELLOW);
	put_str(LABEL_COLS, s, WHITE);
	row++;
	con_flush();
}

void con_hex(const char *label, uint64_t v)
{
	char buf[17];
	fmt_hex(buf, v, 16);
	con_str(label, buf);
}

void con_hex2(const char *label, const char *a, uint32_t va, const char *b, uint32_t vb)
{
	char buf[9];
	int col = put_str(0, label, YELLOW);
	col = col < LABEL_COLS ? LABEL_COLS : col + 1;
	col = put_str(col, a, YELLOW);
	fmt_hex(buf, va, 8);
	col = put_str(col, buf, WHITE);
	if (b) {
		col = put_str(col + 1, b, YELLOW);
		fmt_hex(buf, vb, 8);
		put_str(col, buf, WHITE);
	}
	row++;
	con_flush();
}
