#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <assert.h>

#define CANARY_SIZE 65536
#define FB_WIDTH 1080u
#define FB_HEIGHT 2400u
#define FB_BPP 3u
#define FB_STRIDE (FB_WIDTH * FB_BPP)
#define FB_TOTAL_SIZE (FB_HEIGHT * FB_STRIDE)

#define EARLY_SCALE 2u
#define EARLY_CELL_W (8u * EARLY_SCALE)
#define EARLY_CELL_H (16u * EARLY_SCALE)
#define EARLY_ROWS ((FB_HEIGHT - 32u) / EARLY_CELL_H)
#define EARLY_COLS (FB_WIDTH / EARLY_CELL_W)

#define FBCON_SCALE 2u
#define FBCON_COLS (FB_WIDTH / (8u * FBCON_SCALE))
#define FBCON_ROWS (FB_HEIGHT / (16u * FBCON_SCALE))

static uint8_t simulated_iso_font[256 * 16];

static uint8_t canary_pre[CANARY_SIZE];
static uint8_t fb_mem[FB_TOTAL_SIZE];
static uint8_t canary_post[CANARY_SIZE];

static volatile uint8_t *early_fb = fb_mem;
static unsigned int early_row, early_col;
static unsigned int early_started, early_disabled;

static void sweet_early_clear_row(void)
{
	for (unsigned int y = 0; y < EARLY_CELL_H; y++) {
		volatile uint8_t *line = early_fb + (early_row * EARLY_CELL_H + y) * FB_STRIDE;
		for (unsigned int b = 0; b < FB_STRIDE; b++) {
			line[b] = 0;
		}
	}
}

static void sweet_early_putc(char c)
{
	if (early_disabled) {
		return;
	}
	if (!early_started) {
		early_started = 1;
		sweet_early_clear_row();
	}
	if (c == '\r') {
		early_col = 0;
		return;
	}
	if (c == '\n' || early_col == EARLY_COLS) {
		early_col = 0;
		early_row = (early_row + 1) % EARLY_ROWS;
		sweet_early_clear_row();
		if (c == '\n') {
			return;
		}
	}
	const unsigned char *glyph = simulated_iso_font + (unsigned char)c * 16;
	for (unsigned int gy = 0; gy < 16; gy++) {
		for (unsigned int sy = 0; sy < EARLY_SCALE; sy++) {
			volatile uint8_t *line = early_fb +
			    (early_row * EARLY_CELL_H + gy * EARLY_SCALE + sy) * FB_STRIDE +
			    early_col * EARLY_CELL_W * FB_BPP;
			for (unsigned int gx = 0; gx < 8; gx++) {
				uint8_t val = (glyph[gy] & (1u << gx)) ? 0xff : 0x00;
				for (unsigned int sx = 0; sx < EARLY_SCALE; sx++) {
					unsigned int px = (gx * EARLY_SCALE + sx) * FB_BPP;
					line[px + 0] = val;
					line[px + 1] = val;
					line[px + 2] = val;
				}
			}
		}
	}
	early_col++;
}

static void sweet_early_mark(unsigned int stage)
{
	if (early_disabled || stage > 20) {
		return;
	}
	uint8_t r = (uint8_t)((stage & 7u) * 32u);
	uint8_t g = 0xff;
	uint8_t b = 0x00;
	for (unsigned int y = FB_HEIGHT - 32; y < FB_HEIGHT; y++) {
		volatile uint8_t *line = early_fb + y * FB_STRIDE;
		for (unsigned int x = stage * 48; x < (stage + 1) * 48; x++) {
			line[x * 3 + 0] = r;
			line[x * 3 + 1] = g;
			line[x * 3 + 2] = b;
		}
	}
}

static volatile uint8_t *fbcon_base = fb_mem;
static uint32_t fbcon_width = FB_WIDTH;
static uint32_t fbcon_height = FB_HEIGHT;
static uint32_t fbcon_stride = FB_STRIDE;
static uint32_t fbcon_cols = FBCON_COLS;
static uint32_t fbcon_rows = FBCON_ROWS;
static uint32_t fbcon_col, fbcon_row;

static void fbcon_clear_row(uint32_t row)
{
	for (uint32_t y = row * 16 * FBCON_SCALE; y < (row + 1) * 16 * FBCON_SCALE; y++) {
		volatile uint8_t *line = fbcon_base + y * fbcon_stride;
		for (uint32_t b = 0; b < fbcon_stride; b++) {
			line[b] = 0;
		}
	}
}

static void fbcon_newline(void)
{
	fbcon_col = 0;
	fbcon_row = (fbcon_row + 1) % fbcon_rows;
	fbcon_clear_row(fbcon_row);
	fbcon_clear_row((fbcon_row + 1) % fbcon_rows);
}

static void fbcon_init(void)
{
	fbcon_cols = fbcon_width / (8 * FBCON_SCALE);
	fbcon_rows = fbcon_height / (16 * FBCON_SCALE);
	fbcon_col = fbcon_row = 0;
	for (uint32_t r = 0; r < fbcon_rows; r++) {
		fbcon_clear_row(r);
	}
}

static void fbcon_transmit_data(uint8_t c)
{
	if (c == '\r') {
		fbcon_col = 0;
		return;
	}
	if (c == '\n') {
		fbcon_newline();
		return;
	}
	if (fbcon_col >= fbcon_cols) {
		fbcon_newline();
	}
	const unsigned char *glyph = simulated_iso_font + c * 16;
	uint32_t x0 = fbcon_col * 8 * FBCON_SCALE, y0 = fbcon_row * 16 * FBCON_SCALE;
	for (uint32_t gy = 0; gy < 16; gy++) {
		for (uint32_t sy = 0; sy < FBCON_SCALE; sy++) {
			volatile uint8_t *line = fbcon_base + (y0 + gy * FBCON_SCALE + sy) * fbcon_stride + x0 * 3;
			for (uint32_t gx = 0; gx < 8; gx++) {
				uint8_t px = (glyph[gy] & (1u << gx)) ? 0xff : 0x00;
				for (uint32_t sx = 0; sx < FBCON_SCALE; sx++) {
					uint32_t off = (gx * FBCON_SCALE + sx) * 3;
					line[off + 0] = px;
					line[off + 1] = px;
					line[off + 2] = px;
				}
			}
		}
	}
	fbcon_col++;
}

static void test_stage0_asm_simulation(void)
{
	uint64_t x0 = 2368u * FB_STRIDE;
	uint64_t x1 = 0xffffffffffffffffULL;
	uint32_t x2 = 32;
	uint32_t x4 = FB_STRIDE;
	while (x2 > 0) {
		uint32_t x3 = 24;
		uint8_t *x5 = fb_mem + x0;
		while (x3 > 0) {
			*(uint64_t *)x5 = x1;
			x5 += 8;
			x3--;
		}
		x0 += x4;
		x2--;
	}

	for (size_t i = 0; i < 2368u * FB_STRIDE; i++) {
		assert(fb_mem[i] == 0);
	}
	for (uint32_t r = 0; r < 32; r++) {
		size_t offset = (2368u + r) * FB_STRIDE;
		for (size_t b = 0; b < 192; b++) {
			assert(fb_mem[offset + b] == 0xff);
		}
		for (size_t b = 192; b < FB_STRIDE; b++) {
			assert(fb_mem[offset + b] == 0);
		}
	}
}

static void verify_canaries(void)
{
	for (size_t i = 0; i < CANARY_SIZE; i++) {
		assert(canary_pre[i] == 0x5a);
		assert(canary_post[i] == 0xa5);
	}
}

int main(void)
{
	memset(canary_pre, 0x5a, sizeof(canary_pre));
	memset(fb_mem, 0, sizeof(fb_mem));
	memset(canary_post, 0xa5, sizeof(canary_post));
	memset(simulated_iso_font, 0xaa, sizeof(simulated_iso_font));

	verify_canaries();
	test_stage0_asm_simulation();
	verify_canaries();
	printf("PASS: Stage 0 marker memory bounds and canary check\n");

	memset(fb_mem, 0, sizeof(fb_mem));
	early_row = 0;
	early_col = 0;
	early_started = 0;
	early_disabled = 0;

	for (int i = 0; i < 10000; i++) {
		sweet_early_putc((char)('A' + (i % 26)));
		if (i % 67 == 66) {
			sweet_early_putc('\n');
		}
	}
	for (int stage = 0; stage <= 20; stage++) {
		sweet_early_mark((unsigned int)stage);
	}
	verify_canaries();
	printf("PASS: sweet_early_putc and sweet_early_mark canary check\n");

	memset(fb_mem, 0, sizeof(fb_mem));
	fbcon_init();
	verify_canaries();

	for (int i = 0; i < 20000; i++) {
		fbcon_transmit_data((uint8_t)('0' + (i % 10)));
		if (i % 68 == 67) {
			fbcon_transmit_data('\n');
		}
	}
	verify_canaries();
	printf("PASS: fbcon_transmit_data canary check\n");

	uint32_t colors[] = {0x00ff0000, 0x0000ff00, 0x000000ff, 0x00123456};
	for (int i = 0; i < 4; i++) {
		uint8_t *p = fb_mem + i * 3;
		uint32_t c = colors[i];
		p[0] = (c >> 16) & 0xff;
		p[1] = (c >> 8) & 0xff;
		p[2] = c & 0xff;
	}
	assert(fb_mem[0] == 0xff && fb_mem[1] == 0x00 && fb_mem[2] == 0x00);
	assert(fb_mem[3] == 0x00 && fb_mem[4] == 0xff && fb_mem[5] == 0x00);
	assert(fb_mem[6] == 0x00 && fb_mem[7] == 0x00 && fb_mem[8] == 0xff);
	assert(fb_mem[9] == 0x12 && fb_mem[10] == 0x34 && fb_mem[11] == 0x56);
	verify_canaries();
	printf("PASS: 24-bit RGB888 color packing verified\n");

	printf("ALL EMPIRICAL C TESTS PASSED WITH 0 ERRORS\n");
	return 0;
}
