import sys

def test_bounds_safety():
    base = 0x7E020000
    width = 1080
    height = 2400
    bpp = 3
    stride = width * bpp
    dram_active_start = base
    dram_active_size = height * stride
    dram_active_end = dram_active_start + dram_active_size

    assert stride == 3240
    assert dram_active_size == 7776000
    assert dram_active_end == 0x7E78A700

    stage0_start_row = 2368
    stage0_num_rows = 32
    stage0_quadwords_per_row = 24
    stage0_bytes_per_row = stage0_quadwords_per_row * 8

    assert stage0_bytes_per_row == 192
    assert stage0_bytes_per_row % bpp == 0
    assert stage0_bytes_per_row // bpp == 64

    stage0_start_addr = base + stage0_start_row * stride
    assert stage0_start_addr == 0x7E771200
    assert stage0_start_addr % 8 == 0
    assert stride % 8 == 0

    first_row_end_addr = stage0_start_addr + stage0_bytes_per_row
    assert first_row_end_addr == 0x7E7712C0
    assert first_row_end_addr <= dram_active_end

    for r in range(stage0_num_rows):
        row_idx = stage0_start_row + r
        assert row_idx < height
        row_addr = base + row_idx * stride
        row_end = row_addr + stage0_bytes_per_row
        assert row_addr >= dram_active_start
        assert row_end <= row_addr + stride
        assert row_end <= dram_active_end

    last_row_idx = stage0_start_row + stage0_num_rows - 1
    assert last_row_idx == 2399
    last_row_addr = base + last_row_idx * stride
    assert last_row_addr == 0x7E789A58
    last_row_end = last_row_addr + stage0_bytes_per_row
    assert last_row_end == 0x7E789B18
    assert last_row_end <= dram_active_end
    margin_to_dram_end = dram_active_end - last_row_end
    assert margin_to_dram_end == 3048
    assert margin_to_dram_end == stride - stage0_bytes_per_row

def test_font_rendering_bounds():
    width = 1080
    height = 2400
    bpp = 3
    stride = width * bpp
    scale = 2
    cell_w = 8 * scale
    cell_h = 16 * scale
    early_rows = (height - 32) // cell_h
    early_cols = width // cell_w

    assert early_rows == 74
    assert early_cols == 67

    max_offset_seen = 0
    for r in range(early_rows):
        for c in range(early_cols):
            x0 = c * cell_w
            y0 = r * cell_h
            for gy in range(16):
                for sy in range(scale):
                    y = y0 + gy * scale + sy
                    assert 0 <= y < 2368
                    for gx in range(8):
                        for sx in range(scale):
                            x = x0 + gx * scale + sx
                            assert 0 <= x < width
                            px_off = (gx * scale + sx) * bpp
                            line_byte = c * cell_w * bpp + px_off
                            assert line_byte + 2 < stride
                            total_byte = y * stride + line_byte + 2
                            if total_byte > max_offset_seen:
                                max_offset_seen = total_byte

    assert max_offset_seen == (2367 * stride + 1071 * bpp + 2)
    assert max_offset_seen < (2368 * stride)
    assert max_offset_seen < (height * stride)

    c_overflow = 67
    x0_overflow = c_overflow * cell_w
    assert x0_overflow == 1072
    max_x_overflow = x0_overflow + 7 * scale + 1
    assert max_x_overflow == 1087
    max_byte_overflow = max_x_overflow * bpp + 2
    assert max_byte_overflow == 3263
    assert max_byte_overflow >= stride

    fbcon_cols = width // (8 * scale)
    fbcon_rows = height // (16 * scale)
    assert fbcon_cols == 67
    assert fbcon_rows == 75

    max_fbcon_offset = 0
    for r in range(fbcon_rows):
        for c in range(fbcon_cols):
            x0 = c * 8 * scale
            y0 = r * 16 * scale
            for gy in range(16):
                for sy in range(scale):
                    y = y0 + gy * scale + sy
                    assert 0 <= y < height
                    for gx in range(8):
                        for sx in range(scale):
                            x = x0 + gx * scale + sx
                            assert 0 <= x < width
                            byte_in_line = x * bpp
                            assert byte_in_line + 2 < stride
                            total_byte = y * stride + byte_in_line + 2
                            if total_byte > max_fbcon_offset:
                                max_fbcon_offset = total_byte

    assert max_fbcon_offset == (2399 * stride + 1071 * bpp + 2)
    assert max_fbcon_offset < (height * stride)

    for stage in range(21):
        x_start = stage * 48
        x_end = (stage + 1) * 48
        assert x_start >= 0
        assert x_end <= width
        for y in range(height - 32, height):
            byte_start = y * stride + x_start * 3
            byte_end = y * stride + (x_end - 1) * 3 + 2
            assert byte_start >= 0
            assert byte_end < height * stride

def test_color_packing():
    buffer = bytearray(3240)
    colors = [
        (0x00FF0000, 0xFF, 0x00, 0x00),
        (0x0000FF00, 0x00, 0xFF, 0x00),
        (0x000000FF, 0x00, 0x00, 0xFF),
        (0x00123456, 0x12, 0x34, 0x56),
        (0x00FFFFFF, 0xFF, 0xFF, 0xFF),
        (0x00000000, 0x00, 0x00, 0x00),
    ]

    for i, (c, expected_r, expected_g, expected_b) in enumerate(colors):
        r = (c >> 16) & 0xff
        g = (c >> 8) & 0xff
        b = c & 0xff
        assert r == expected_r
        assert g == expected_g
        assert b == expected_b
        buffer[i * 3 + 0] = r
        buffer[i * 3 + 1] = g
        buffer[i * 3 + 2] = b

    for i, (c, expected_r, expected_g, expected_b) in enumerate(colors):
        assert buffer[i * 3 + 0] == expected_r
        assert buffer[i * 3 + 1] == expected_g
        assert buffer[i * 3 + 2] == expected_b

    for stage in range(21):
        r = (stage & 7) * 32
        g = 0xff
        b = 0x00
        assert 0 <= r <= 224
        assert g == 255
        assert b == 0

    assert 3240 % 3 == 0

if __name__ == '__main__':
    test_bounds_safety()
    print('PASS: test_bounds_safety')
    test_font_rendering_bounds()
    print('PASS: test_font_rendering_bounds')
    test_color_packing()
    print('PASS: test_color_packing')
    print('ALL VERIFICATION SUITES PASSED')
