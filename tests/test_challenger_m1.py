import os
import struct
import sys

def verify_adt_binary():
    adt_path = '/home/exerczz1/ios-agate/shim/out/agate.adt'
    if not os.path.exists(adt_path):
        adt_path = os.path.abspath('shim/out/agate.adt')
    with open(adt_path, 'rb') as f:
        buf = f.read()

    assert len(buf) > 0

    fbcon_tag = b'sweet-fbcon\0'
    fbcon_idx = buf.find(fbcon_tag)
    assert fbcon_idx != -1
    node_start = fbcon_idx - 36 - 8

    def find_prop(start_off, name):
        target = name.encode().ljust(32, b'\0')[:32]
        idx = buf.find(target, start_off)
        if idx == -1:
            return None
        size_field, = struct.unpack_from('<I', buf, idx + 32)
        flags = size_field >> 31
        length = size_field & 0x7fffffff
        val = buf[idx + 36: idx + 36 + length]
        return idx, flags, length, val

    w = find_prop(node_start, 'width')
    assert w is not None
    w_idx, w_flags, w_len, w_val = w
    assert w_len == 4
    assert w_val == b'\x38\x04\x00\x00'
    assert struct.unpack('<I', w_val)[0] == 1080

    h = find_prop(node_start, 'height')
    assert h is not None
    h_idx, h_flags, h_len, h_val = h
    assert h_len == 4
    assert h_val == b'\x60\x09\x00\x00'
    assert struct.unpack('<I', h_val)[0] == 2400

    s = find_prop(node_start, 'stride')
    assert s is not None
    s_idx, s_flags, s_len, s_val = s
    assert s_len == 4
    assert s_val == b'\xa8\x0c\x00\x00'
    assert struct.unpack('<I', s_val)[0] == 3240

    rb = find_prop(node_start, 'row-bytes')
    assert rb is not None
    rb_idx, rb_flags, rb_len, rb_val = rb
    assert rb_len == 4
    assert rb_val == b'\xa8\x0c\x00\x00'
    assert struct.unpack('<I', rb_val)[0] == 3240

    d = find_prop(node_start, 'depth')
    assert d is not None
    d_idx, d_flags, d_len, d_val = d
    assert d_len == 4
    assert d_val == b'\x18\x00\x00\x00'
    assert struct.unpack('<I', d_val)[0] == 24

    reg = find_prop(node_start, 'reg')
    assert reg is not None
    reg_idx, reg_flags, reg_len, reg_val = reg
    assert reg_len == 16
    base, sz = struct.unpack('<QQ', reg_val)
    assert base == 0x7e020000
    assert sz == 0x1be0000

    fb_mem = find_prop(0, 'Framebuffer')
    assert fb_mem is not None
    fb_idx, fb_flags, fb_len, fb_val = fb_mem
    assert fb_len == 16
    fb_base, fb_sz = struct.unpack('<QQ', fb_val)
    assert fb_base == 0x7e020000
    assert fb_sz == 0x1be0000

def verify_host_ppm():
    ppm_path = '/home/exerczz1/ios-agate/shim/out/host.ppm'
    if not os.path.exists(ppm_path):
        ppm_path = os.path.abspath('shim/out/host.ppm')
    file_size = os.path.getsize(ppm_path)
    assert file_size == 7776017

    with open(ppm_path, 'rb') as f:
        header = f.read(17)
        assert header == b'P6 1080 2400 255\n'
        payload = f.read()

    assert len(payload) == 1080 * 2400 * 3

    colors = {}
    for i in range(0, len(payload), 3):
        c = (payload[i], payload[i+1], payload[i+2])
        colors[c] = colors.get(c, 0) + 1

    assert len(colors) == 3
    assert colors.get((0, 0, 160)) == 2580462
    assert colors.get((255, 255, 255)) == 8874
    assert colors.get((255, 255, 0)) == 2664

def test_corner_cases():
    FB_W = 1080
    FB_H = 2400
    FB_BPP = 3
    FB_STRIDE = FB_W * FB_BPP
    FB_SIZE = FB_H * FB_STRIDE

    EARLY_SCALE = 2
    EARLY_CELL_W = 8 * EARLY_SCALE
    EARLY_CELL_H = 16 * EARLY_SCALE
    EARLY_ROWS = int((FB_H - 32) / EARLY_CELL_H)
    EARLY_COLS = int(FB_W / EARLY_CELL_W)

    assert EARLY_COLS == 67
    assert EARLY_ROWS == 74

    fb = bytearray(FB_SIZE)
    state = {'row': 0, 'col': 0, 'started': False, 'disabled': False}

    def clear_row():
        y0 = state['row'] * EARLY_CELL_H
        for y in range(y0, y0 + EARLY_CELL_H):
            assert y < FB_H - 32
            line_start = y * FB_STRIDE
            fb[line_start:line_start + FB_STRIDE] = b'\0' * FB_STRIDE

    def early_putc(c):
        if state['disabled']:
            return
        if not state['started']:
            state['started'] = True
            clear_row()
        if c == '\r':
            state['col'] = 0
            return
        if c == '\n' or state['col'] == EARLY_COLS:
            state['col'] = 0
            state['row'] = (state['row'] + 1) % EARLY_ROWS
            clear_row()
            if c == '\n':
                return
        y0 = state['row'] * EARLY_CELL_H
        x0 = state['col'] * EARLY_CELL_W * FB_BPP
        for gy in range(16):
            for sy in range(EARLY_SCALE):
                y = y0 + gy * EARLY_SCALE + sy
                assert y < 2368
                line_off = y * FB_STRIDE + x0
                for gx in range(8):
                    for sx in range(EARLY_SCALE):
                        px = (gx * EARLY_SCALE + sx) * FB_BPP
                        total_off = line_off + px
                        assert total_off + 2 < (y + 1) * FB_STRIDE
                        assert total_off + 2 < FB_SIZE
                        fb[total_off] = 0xFF
                        fb[total_off + 1] = 0xFF
                        fb[total_off + 2] = 0xFF
        state['col'] += 1

    def early_str(s):
        for ch in s:
            early_putc(ch)

    def early_mark(stage, label):
        if state['disabled'] or stage > 20:
            return
        r = (stage & 7) * 32
        g = 0xFF
        b = 0x00
        for y in range(FB_H - 32, FB_H):
            line_off = y * FB_STRIDE
            for x in range(stage * 48, (stage + 1) * 48):
                off = line_off + x * 3
                assert off + 2 < (y + 1) * FB_STRIDE
                assert off + 2 < FB_SIZE
                fb[off] = r
                fb[off + 1] = g
                fb[off + 2] = b
        early_str(f"SWEET EARLY {stage}: {label}\n")

    early_str("")
    early_mark(0, "")
    assert state['col'] == 0
    assert state['row'] == 1

    early_str("A" * (EARLY_COLS - 1))
    assert state['col'] == EARLY_COLS - 1
    early_putc("B")
    assert state['col'] == EARLY_COLS
    early_putc("C")
    assert state['col'] == 1

    for i in range(300):
        early_str(f"line_{i}\n")

    assert state['row'] < EARLY_ROWS

    for stage in range(21):
        early_mark(stage, f"stage_{stage}")

    reloc_fb = bytearray(fb)
    fb = reloc_fb
    early_str("post_relocation_text\n")
    early_mark(9, "kernel framebuffer VA live")

    FBCON_SCALE = 2
    FBCON_COLS = int(FB_W / (8 * FBCON_SCALE))
    FBCON_ROWS = int(FB_H / (16 * FBCON_SCALE))
    assert FBCON_COLS == 67
    assert FBCON_ROWS == 75

    fbcon_state = {'row': 0, 'col': 0}

    def fbcon_clear_row(row):
        for y in range(row * 16 * FBCON_SCALE, (row + 1) * 16 * FBCON_SCALE):
            assert y < FB_H
            fb[y * FB_STRIDE : (y + 1) * FB_STRIDE] = b'\0' * FB_STRIDE

    def fbcon_newline():
        fbcon_state['col'] = 0
        fbcon_state['row'] = (fbcon_state['row'] + 1) % FBCON_ROWS
        fbcon_clear_row(fbcon_state['row'])
        fbcon_clear_row((fbcon_state['row'] + 1) % FBCON_ROWS)

    def fbcon_putc(c):
        if c == '\r':
            fbcon_state['col'] = 0
            return
        if c == '\n':
            fbcon_newline()
            return
        if fbcon_state['col'] >= FBCON_COLS:
            fbcon_newline()
        y0 = fbcon_state['row'] * 16 * FBCON_SCALE
        x0 = fbcon_state['col'] * 8 * FBCON_SCALE
        for gy in range(16):
            for sy in range(FBCON_SCALE):
                y = y0 + gy * FBCON_SCALE + sy
                assert y < FB_H
                line_off = y * FB_STRIDE + x0 * 3
                for gx in range(8):
                    for sx in range(FBCON_SCALE):
                        off = (gx * FBCON_SCALE + sx) * 3
                        tot = line_off + off
                        assert tot + 2 < (y + 1) * FB_STRIDE
                        assert tot + 2 < FB_SIZE
                        fb[tot] = 0xFF
                        fb[tot + 1] = 0xFF
                        fb[tot + 2] = 0xFF
        fbcon_state['col'] += 1

    for _ in range(500):
        for ch in "XNU kprintf test string line with wrap\n":
            fbcon_putc(ch)

    assert fbcon_state['row'] < FBCON_ROWS

if __name__ == '__main__':
    verify_adt_binary()
    print('PASS: verify_adt_binary')
    verify_host_ppm()
    print('PASS: verify_host_ppm')
    test_corner_cases()
    print('PASS: test_corner_cases')
    print('ALL CHALLENGER TESTS PASSED')
