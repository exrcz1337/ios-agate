/* Render the console layout on the host: ./out/host_test && view out/host.ppm */
#include <stdio.h>
#include "console.h"

static uint8_t host_fb[FB_H * FB_STRIDE];

int main(void)
{
	con_fb = host_fb;
	con_clear(RED);
	con_str("SHIM", "agate milestone 2");
	con_hex("MMFR0", 0x0000000000101122ULL);
	con_hex2("PSCI", "ver=", 0x10001, "smccc=", 0x10002);
	con_hex2("CPU7", "ret=", 0, "mpidr=", 0x81000700);
	con_clear(BLUE);
	con_str("PANIC", "sync exception");
	con_hex("ESR", 0x96000010);
	FILE *f = fopen("out/host.ppm", "wb");
	fprintf(f, "P6 %d %d 255\n", FB_W, FB_H);
	fwrite(host_fb, 1, FB_H * FB_STRIDE, f);
	fclose(f);
	return 0;
}
