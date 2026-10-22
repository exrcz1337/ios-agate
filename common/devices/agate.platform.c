static const struct platform platform_agate = {
	.name = "agate",
	.io_base = 0x0c000000,
	.io_size = 0x14000000,
	.gic_dist = 0x0c000000,
	.gic_redist = 0x0c040000,
	.uart = 0,
	.log_other_cpu = 1,
	.cores = 8,
	.core_shift = 8,
	.small_cores = 0x0f,
	.fb_base = 0x7e020000,
};
