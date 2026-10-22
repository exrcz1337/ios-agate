#pragma once
#include <stdint.h>

#define FB_BASE		0x7E020000UL
#define FB_W		1080
#define FB_H		2400
#define FB_STRIDE	(FB_W * 3)

#define RED	0xffff0000U
#define BLUE	0xff0000a0U
#define WHITE	0xffffffffU
#define YELLOW	0xffffff00U
#define GREEN	0xff00ff00U

extern volatile void *con_fb;
extern uint32_t con_stride;
extern uint32_t con_w;
extern uint32_t con_h;
extern uint32_t con_bpp;
extern uint32_t con_bswap;

void con_init(void);
void con_clear(uint32_t bg);
void con_flush(void);
void con_flush_force(void);
void con_skip(void);
void con_str(const char *label, const char *s);
void con_hex(const char *label, uint64_t v);
void con_hex2(const char *label, const char *a, uint32_t va, const char *b, uint32_t vb);
