import os
import re
import subprocess
import sys

def test_disassembly_loader_boot():
    elf = "/home/exerczz1/ios-agate/shim/out/shim.elf"
    assert os.path.exists(elf), "shim.elf not found"
    
    cmd = ["llvm-objdump", "-d", elf]
    out = subprocess.check_output(cmd, text=True)
    
    loader_boot_match = re.search(r"<loader_boot>:(.*?)(?:\n\n[0-9a-f]+ <|\Z)", out, re.DOTALL)
    assert loader_boot_match, "loader_boot not found in disassembly"
    body = loader_boot_match.group(1)
    
    lines = [line.strip() for line in body.strip().split("\n") if line.strip()]
    
    smc_idx = -1
    blr_idx = -1
    con_str_indices = []
    adr_dsi_idx = -1
    
    for idx, line in enumerate(lines):
        if "smc\t#0" in line:
            smc_idx = idx
        elif "blr\tx20" in line or "blr" in line:
            blr_idx = idx
        elif "<con_str>" in line or "<con_hex>" in line or "<con_hex2>" in line:
            con_str_indices.append(idx)
        elif "<dsi_flush_loop>" in line and "adr" in line:
            adr_dsi_idx = idx

    assert smc_idx != -1, "smc #0 not found in loader_boot"
    assert blr_idx != -1, "blr not found in loader_boot"
    assert adr_dsi_idx != -1, "adr dsi_flush_loop not found"
    
    assert smc_idx > max(con_str_indices), f"smc at {smc_idx} must be after all console prints (max {max(con_str_indices)})"
    assert adr_dsi_idx < smc_idx, "adr dsi_flush_loop must precede smc"
    assert smc_idx < blr_idx, f"smc at {smc_idx} must precede blr at {blr_idx}"
    
    between = lines[smc_idx + 1:blr_idx]
    for b in between:
        assert "bl\t" not in b, f"Unexpected branch in handoff critical section: {b}"
        assert "str" not in b, f"Unexpected store in handoff critical section: {b}"
    print("PASS: test_disassembly_loader_boot")

def test_dsi_flush_loop_pacing():
    elf = "/home/exerczz1/ios-agate/shim/out/shim.elf"
    cmd = ["llvm-objdump", "-d", elf]
    out = subprocess.check_output(cmd, text=True)
    
    flush_match = re.search(r"<dsi_flush_loop>:(.*?)(?:\n\n[0-9a-f]+ <|\Z)", out, re.DOTALL)
    assert flush_match, "dsi_flush_loop not found"
    body = flush_match.group(1)
    
    assert "CNTPCT_EL0" in body.upper() or "cntpct_el0" in body.lower(), "Timer register not polled"
    assert "0x100000" in body or "1048576" in body, "0x100000 tick delay missing"
    print("PASS: test_dsi_flush_loop_pacing")

def test_mkadt_carveout():
    sys.path.insert(0, "/home/exerczz1/ios-agate/tools")
    import mkadt
    assert mkadt.PHYS_BASE == 0x40000000
    assert mkadt.MEM_SIZE == 0x3e000000
    assert mkadt.FB == 0x7E020000
    assert mkadt.PHYS_BASE + mkadt.MEM_SIZE == 0x7E000000
    assert mkadt.PHYS_BASE + mkadt.MEM_SIZE <= mkadt.FB
    print("PASS: test_mkadt_carveout")

def test_zero_comments_in_diff():
    cmd = ["git", "-C", "/home/exerczz1/ios-agate", "diff", "shim/loader.c"]
    out = subprocess.check_output(cmd, text=True)
    for line in out.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            code = line[1:].strip()
            assert "//" not in code, f"Comment found: {code}"
            assert "/*" not in code, f"Comment found: {code}"
            assert "*/" not in code, f"Comment found: {code}"
    print("PASS: test_zero_comments_in_diff")

if __name__ == "__main__":
    test_disassembly_loader_boot()
    test_dsi_flush_loop_pacing()
    test_mkadt_carveout()
    test_zero_comments_in_diff()
    print("ALL MILESTONE 2 TESTS PASSED")
