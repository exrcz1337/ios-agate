import os
import re
import struct
import subprocess
import sys

def test_race_condition_elimination():
    elf = "/home/exerczz1/ios-agate/shim/out/shim.elf"
    assert os.path.exists(elf), "shim.elf missing"
    out = subprocess.check_output(["llvm-objdump", "-d", elf], text=True)

    match = re.search(r"<loader_boot>:(.*?)(?:\n\n[0-9a-f]+ <|\Z)", out, re.DOTALL)
    assert match, "loader_boot not found"
    lines = [l.strip() for l in match.group(1).split("\n") if l.strip()]

    smc_idx = -1
    blr_idx = -1
    con_str_indices = []
    adr_dsi_idx = -1

    for idx, line in enumerate(lines):
        if "smc\t#0" in line:
            smc_idx = idx
        elif "blr\tx20" in line:
            blr_idx = idx
        elif "<con_str>" in line or "<con_hex>" in line or "<con_hex2>" in line:
            con_str_indices.append(idx)
        elif "<dsi_flush_loop>" in line and "adr" in line:
            adr_dsi_idx = idx

    assert smc_idx != -1, "smc #0 not found"
    assert blr_idx != -1, "blr x20 not found"
    assert adr_dsi_idx != -1, "adr dsi_flush_loop not found"
    assert len(con_str_indices) > 0, "No console prints found"

    assert max(con_str_indices) < smc_idx, "All console prints must complete before smc"
    assert adr_dsi_idx < smc_idx, "dsi_flush_loop address must be set before smc"
    assert smc_idx < blr_idx, "smc must precede blr"

    critical_section = lines[smc_idx + 1:blr_idx]
    allowed_mnemonics = ("dsb", "ic", "isb", "mov", "nop")
    for instr in critical_section:
        parts = [p.strip() for p in instr.split("\t") if p.strip()]
        assert len(parts) >= 2, f"Malformed instruction line: {instr}"
        op = parts[1]
        assert op in allowed_mnemonics, f"Unexpected instruction in critical section: {instr}"
        assert not op.startswith("st"), f"Store instruction detected: {instr}"
        assert op != "bl", f"Function call detected: {instr}"

    print("PASS: test_race_condition_elimination")

def test_pacing_loop_and_rollover():
    elf = "/home/exerczz1/ios-agate/shim/out/shim.elf"
    out = subprocess.check_output(["llvm-objdump", "-d", elf], text=True)
    match = re.search(r"<dsi_flush_loop>:(.*?)(?:\n\n[0-9a-f]+ <|\Z)", out, re.DOTALL)
    assert match, "dsi_flush_loop not found"
    body = match.group(1)

    assert "0x7020" in body and "0x1411" in body, "MUTEX register 0x14117020 not targeted"
    assert "0xe000" in body and "0x1400" in body, "DSI register 0x1400e000 not targeted"
    assert "cntpct_el0" in body.lower(), "CNTPCT_EL0 register not read"
    assert "0x100000" in body or "1048576" in body, "0x100000 ticks missing"

    freq = 13000000
    ticks = 0x100000
    delay_sec = ticks / freq
    delay_ms = delay_sec * 1000.0
    hz = 1.0 / delay_sec

    assert 80.65 < delay_ms < 80.67, f"Unexpected delay ms: {delay_ms}"
    assert 12.39 < hz < 12.41, f"Unexpected hz: {hz}"
    assert 12.0 <= hz <= 30.0, f"Hz out of target 12-30 range: {hz}"

    mask64 = (1 << 64) - 1
    cnt = (1 << 64) - 0x80000
    target = (cnt + ticks) & mask64
    assert target == 0x80000

    def blo(curr, tgt):
        return curr < tgt

    assert not blo(cnt, target), "Rollover boundary must not branch backward into infinite loop"

    next_cnt = target + 1
    next_target = (next_cnt + ticks) & mask64
    assert blo(next_cnt, next_target), "Normal loop iteration after rollover must branch correctly"

    years = ((1 << 64) / freq) / (86400 * 365.25)
    assert 44900 < years < 45000, f"Rollover years calculation mismatch: {years}"

    print("PASS: test_pacing_loop_and_rollover")

def test_memory_boundary_arithmetic():
    sys.path.insert(0, "/home/exerczz1/ios-agate/tools")
    import mkadt

    phys_base = mkadt.PHYS_BASE
    mem_size = mkadt.MEM_SIZE
    fb_base = mkadt.FB
    fb_size = mkadt.FB_SIZE

    assert phys_base == 0x40000000
    assert mem_size == 0x3E000000
    assert fb_base == 0x7E020000
    assert fb_size == 0x1BE0000

    kernel_mem_end = phys_base + mem_size
    assert kernel_mem_end == 0x7E000000
    assert kernel_mem_end < fb_base

    guard_hole = fb_base - kernel_mem_end
    assert guard_hole == 0x20000
    assert guard_hole == 128 * 1024

    k_start, k_end = phys_base, kernel_mem_end
    f_start, f_end = fb_base, fb_base + fb_size
    overlap = max(0, min(k_end, f_end) - max(k_start, f_start))
    assert overlap == 0

    adt_path = "/home/exerczz1/ios-agate/shim/out/adt.bin"
    subprocess.check_call(["python3", "/home/exerczz1/ios-agate/tools/mkadt.py", adt_path])
    with open(adt_path, "rb") as f:
        buf = f.read()

    def find_val(name):
        target = name.encode().ljust(32, b"\0")[:32]
        idx = buf.find(target)
        assert idx != -1, f"Property {name} not found"
        sz, = struct.unpack_from("<I", buf, idx + 32)
        length = sz & 0x7fffffff
        return buf[idx + 36:idx + 36 + length]

    dram_base = struct.unpack("<Q", find_val("dram-base"))[0]
    dram_size = struct.unpack("<Q", find_val("dram-size"))[0]
    fb_val = find_val("Framebuffer")
    adt_fb_base, adt_fb_size = struct.unpack("<QQ", fb_val)

    assert dram_base == 0x40000000
    assert dram_size == 0x3E000000
    assert adt_fb_base == 0x7E020000
    assert adt_fb_size == 0x1BE0000

    print("PASS: test_memory_boundary_arithmetic")

def test_zero_comments_in_diff():
    for f in ["shim/loader.c", "tools/mkadt.py"]:
        cmd = ["git", "-C", "/home/exerczz1/ios-agate", "diff", "origin/main..HEAD", "--", f]
        out = subprocess.check_output(cmd, text=True)
        for line in out.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                code = line[1:].strip()
                assert not code.startswith("//"), f"Comment found: {code}"
                assert "/*" not in code, f"Comment found: {code}"
                assert "*/" not in code, f"Comment found: {code}"
    print("PASS: test_zero_comments_in_diff")

if __name__ == "__main__":
    test_race_condition_elimination()
    test_pacing_loop_and_rollover()
    test_memory_boundary_arithmetic()
    test_zero_comments_in_diff()
    print("ALL CHALLENGER M2 EMPIRICAL TESTS PASSED")
