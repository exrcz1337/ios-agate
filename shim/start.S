/*
 * sweet boot shim entry: arm64 Linux Image header so Qualcomm ABL treats
 * us like a kernel. ABL enters at EL1, MMU/D-cache off, x0 = DTB pointer.
 */
	.section .text.head, "ax"
	.globl _head
_head:
	b	_start			/* code0 */
	.long	0			/* code1 */
	.quad	0x80000
	.quad	_end			/* image_size (linked at 0) */
	.quad	0xa			/* flags: LE, 4K pages, place anywhere */
	.quad	0			/* res2 */
	.quad	0			/* res3 */
	.quad	0			/* res4 */
	.ascii	"ARM\x64"		/* magic */
	.long	0			/* res5 (PE offset) */

	.text
	.globl _start
_start:
	msr	daifset, #0xf
	mrs	x1, CurrentEL
	cmp	x1, #0x8
	b.ne	1f
	mov	x1, #(1 << 31)
	msr	hcr_el2, x1
	mrs	x1, cnthctl_el2
	orr	x1, x1, #3
	msr	cnthctl_el2, x1
	msr	cntvoff_el2, xzr
	msr	cptr_el2, xzr
	mov	x1, #0x3c5
	msr	spsr_el2, x1
	adr	x1, 1f
	msr	elr_el2, x1
	eret
1:	mov	x19, x0
	msr	spsel, #1
	adrp	x1, _stack_top
	add	x1, x1, :lo12:_stack_top
	mov	sp, x1
	adrp	x1, vectors
	add	x1, x1, :lo12:vectors
	msr	vbar_el1, x1
	isb
	adrp	x1, _bss_start
	add	x1, x1, :lo12:_bss_start
	adrp	x2, _bss_end
	add	x2, x2, :lo12:_bss_end
2:	cmp	x1, x2
	b.hs	3f
	str	xzr, [x1], #8
	b	2b
3:	mov	x0, x19
	bl	shim_main
4:	wfe
	b	4b

	.globl secondary_entry
secondary_entry:
	msr	daifset, #0xf
	mrs	x1, CurrentEL
	cmp	x1, #0x8
	b.ne	1f
	mov	x1, #(1 << 31)
	msr	hcr_el2, x1
	mrs	x1, cnthctl_el2
	orr	x1, x1, #3
	msr	cnthctl_el2, x1
	msr	cntvoff_el2, xzr
	msr	cptr_el2, xzr
	mov	x1, #0x3c5
	msr	spsr_el2, x1
	adr	x1, 1f
	msr	elr_el2, x1
	eret
1:	msr	spsel, #1
	adrp	x1, _sec_stacks
	add	x1, x1, :lo12:_sec_stacks
	add	x1, x1, x0, lsl #12
	add	x1, x1, #0x1000
	mov	sp, x1
	adrp	x1, vectors
	add	x1, x1, :lo12:vectors
	msr	vbar_el1, x1
	isb
	bl	secondary_main
2:	wfe
	b	2b

	.globl dsi_flush_loop
dsi_flush_loop:
	msr	daifset, #0xf
	mrs	x1, CurrentEL
	cmp	x1, #0x8
	b.ne	1f
	mov	x1, #(1 << 31)
	msr	hcr_el2, x1
	mrs	x1, cnthctl_el2
	orr	x1, x1, #3
	msr	cnthctl_el2, x1
	msr	cntvoff_el2, xzr
	msr	cptr_el2, xzr
	mov	x1, #0x3c5
	msr	spsr_el2, x1
	adr	x1, 1f
	msr	elr_el2, x1
	eret
1:	movz	x3, #0x7020
	movk	x3, #0x1411, lsl #16
	movz	x4, #0xe000
	movk	x4, #0x1400, lsl #16
2:	dsb	sy
	mov	w1, #1
	str	w1, [x3]
	str	wzr, [x4]
	str	w1, [x4]
	dsb	sy
	mrs	x0, cntpct_el0
	mov	x2, #0x100000
	add	x0, x0, x2
3:	mrs	x1, cntpct_el0
	cmp	x1, x0
	b.lo	3b
	b	2b

/*
 * Exception vectors. Each slot stashes x29/x30, loads its slot number
 * and jumps to the common path, which saves x0-x28 and calls
 * exc_handler(slot, regs). IRQs return; everything else ends in the
 * on-screen panic.
 */
.macro vent slot
	.balign	0x80
	stp	x29, x30, [sp, #-16]!
	mov	x29, #\slot
	b	exc_common
.endm

	.balign	0x800
	.globl vectors
vectors:
	vent 0
	vent 1
	vent 2
	vent 3
	vent 4
	vent 5
	vent 6
	vent 7
	vent 8
	vent 9
	vent 10
	vent 11
	vent 12
	vent 13
	vent 14
	vent 15

exc_common:
	sub	sp, sp, #(30 * 8)
	stp	x0, x1, [sp, #0]
	stp	x2, x3, [sp, #16]
	stp	x4, x5, [sp, #32]
	stp	x6, x7, [sp, #48]
	stp	x8, x9, [sp, #64]
	stp	x10, x11, [sp, #80]
	stp	x12, x13, [sp, #96]
	stp	x14, x15, [sp, #112]
	stp	x16, x17, [sp, #128]
	stp	x18, x19, [sp, #144]
	stp	x20, x21, [sp, #160]
	stp	x22, x23, [sp, #176]
	stp	x24, x25, [sp, #192]
	stp	x26, x27, [sp, #208]
	str	x28, [sp, #224]
	mov	x0, x29
	mov	x1, sp
	bl	exc_handler
	ldp	x0, x1, [sp, #0]
	ldp	x2, x3, [sp, #16]
	ldp	x4, x5, [sp, #32]
	ldp	x6, x7, [sp, #48]
	ldp	x8, x9, [sp, #64]
	ldp	x10, x11, [sp, #80]
	ldp	x12, x13, [sp, #96]
	ldp	x14, x15, [sp, #112]
	ldp	x16, x17, [sp, #128]
	ldp	x18, x19, [sp, #144]
	ldp	x20, x21, [sp, #160]
	ldp	x22, x23, [sp, #176]
	ldp	x24, x25, [sp, #192]
	ldp	x26, x27, [sp, #208]
	ldr	x28, [sp, #224]
	add	sp, sp, #(30 * 8)
	ldp	x29, x30, [sp], #16
	eret
