import os
import re
import struct
import subprocess
import sys

ADT_PATH = '/home/exerczz1/ios-agate/shim/out/agate.adt'
KERNEL_PATH = '/home/exerczz1/ios-agate/xnu/out/kernel.development.sweet'

sys.path.insert(0, '/home/exerczz1/ios-agate/tools')
import adt

def get_adt_root():
    assert os.path.exists(ADT_PATH), f'{ADT_PATH} missing'
    with open(ADT_PATH, 'rb') as f:
        data = f.read()
    root, _ = adt.parse(data)
    return root

def find_child(node, name):
    for c in node.children:
        if c.name == name:
            return c
    return None

def test_adt_gic_node():
    root = get_adt_root()
    arm_io = find_child(root, 'arm-io')
    assert arm_io is not None, 'arm-io node not found'
    gic = find_child(arm_io, 'gic')
    assert gic is not None, 'gic node not found under arm-io'

    comp = gic.prop('compatible')
    assert comp is not None, 'gic compatible prop missing'
    assert b'arm,gic-v3' in comp, f'unexpected compatible: {comp}'

    intid = gic.prop('virtual-timer-intid')
    assert intid is not None, 'virtual-timer-intid missing'
    assert len(intid) == 4, f'unexpected intid len: {len(intid)}'
    intid_val = struct.unpack('<I', intid)[0]
    assert intid_val == 27, f'expected intid 27, got {intid_val}'

    reg = gic.prop('reg')
    assert reg is not None, 'reg prop missing'
    assert len(reg) == 32, f'reg must be 32 bytes, got {len(reg)}'
    gicd_off, gicd_sz, gicr_off, gicr_sz = struct.unpack('<QQQQ', reg)
    assert gicd_off == 0x0b000000, f'gicd_off {hex(gicd_off)} != 0x0b000000'
    assert gicd_sz == 0x40000, f'gicd_sz {hex(gicd_sz)} != 0x40000'
    assert gicr_off == 0x0b040000, f'gicr_off {hex(gicr_off)} != 0x0b040000'
    assert gicr_sz == 0x200000, f'gicr_sz {hex(gicr_sz)} != 0x200000'
    print('PASS: test_adt_gic_node')

def test_adt_arm_io_ranges():
    root = get_adt_root()
    arm_io = find_child(root, 'arm-io')
    assert arm_io is not None

    addr_cells = arm_io.prop('#address-cells')
    size_cells = arm_io.prop('#size-cells')
    assert addr_cells is not None and struct.unpack('<I', addr_cells)[0] == 2
    assert size_cells is not None and struct.unpack('<I', size_cells)[0] == 2

    ranges = arm_io.prop('ranges')
    assert ranges is not None
    assert len(ranges) == 24, f'ranges len {len(ranges)} != 24'
    child_base, parent_base, size = struct.unpack('<QQQ', ranges)
    assert child_base == 0, f'child_base {hex(child_base)} != 0'
    assert parent_base == 0x01000000, f'parent_base {hex(parent_base)} != 0x01000000'
    assert size == 0xff000000, f'size {hex(size)} != 0xff000000'

    gic = find_child(arm_io, 'gic')
    reg = gic.prop('reg')
    gicd_off, gicd_sz, gicr_off, gicr_sz = struct.unpack('<QQQQ', reg)

    phys_gicd = parent_base + (gicd_off - child_base)
    phys_gicr = parent_base + (gicr_off - child_base)
    assert phys_gicd == 0x0c000000, f'phys_gicd {hex(phys_gicd)} != 0x0c000000'
    assert phys_gicr == 0x0c040000, f'phys_gicr {hex(phys_gicr)} != 0x0c040000'
    assert phys_gicd + gicd_sz <= phys_gicr, 'GICD and GICR overlap'
    print('PASS: test_adt_arm_io_ranges')

def test_adt_cpus_timebase():
    root = get_adt_root()
    cpus = find_child(root, 'cpus')
    assert cpus is not None
    assert len(cpus.children) == 8, f'expected 8 cores, got {len(cpus.children)}'

    for i in range(8):
        core = find_child(cpus, f'cpu{i}')
        assert core is not None, f'cpu{i} missing'
        tb = core.prop('timebase-frequency')
        assert tb is not None, f'cpu{i} timebase-frequency missing'
        assert struct.unpack('<I', tb)[0] == 13000000, f'cpu{i} bad timebase'

        fix = core.prop('fixed-frequency')
        assert fix is not None and struct.unpack('<I', fix)[0] == 13000000
        per = core.prop('peripheral-frequency')
        assert per is not None and struct.unpack('<I', per)[0] == 13000000
    print('PASS: test_adt_cpus_timebase')

def get_kernel_disassembly(start_addr, stop_addr):
    cmd = ['llvm-objdump', '-d', f'--start-address={start_addr}', f'--stop-address={stop_addr}', KERNEL_PATH]
    out = subprocess.check_output(cmd, text=True)
    return out

def test_kernel_pe_init_fiq():
    out = get_kernel_disassembly('0xfffffe0007a78d54', '0xfffffe0007a79020')

    assert 'SecureDTLookupEntry' in out
    assert 'SecureDTGetProperty' in out
    assert 'pe_arm_get_soc_base_phys' in out
    assert 'ml_io_map' in out

    assert 'MPIDR_EL1' in out
    assert '0x20000' in out

    assert 'nanoseconds_to_deadline' in out or 'mach_absolute_time' in out
    assert 'tbnz' in out or 'tbz' in out

    assert '0xa0a0' in out
    assert 'ICC_SRE_EL1' in out
    assert 'ICC_BPR1_EL1' in out
    assert 'ICC_PMR_EL1' in out
    assert '0xff' in out
    assert 'ICC_CTLR_EL1' in out
    assert 'ICC_IGRPEN1_EL1' in out

    assert 'fffffe0007a78f14:' in out
    assert 'fffffe0007a78fb8:' in out
    assert 'fffffe0007a78fec:' in out
    print('PASS: test_kernel_pe_init_fiq')

def test_kernel_sleh_irq():
    out = get_kernel_disassembly('0xfffffe000748a300', '0xfffffe000748a460')

    assert 'ICC_IAR1_EL1' in out
    assert '0x3fc' in out
    assert 'fffffe00072a6000' in out
    assert 'sleh_interrupt_handler_prologue' in out
    assert '<_rtclock_intr>' in out
    assert 'ICC_EOIR1_EL1' in out

    assert re.search(r'cmp\s+w\d+,\s+w\d+', out)
    assert re.search(r'bl\s+0x[0-9a-f]+\s+<_rtclock_intr>', out)
    print('PASS: test_kernel_sleh_irq')

def test_sweet_vtimer_intid_symbol_and_value():
    nm_cmd = ['llvm-nm', KERNEL_PATH]
    nm_out = subprocess.check_output(nm_cmd, text=True)
    assert '_sweet_vtimer_intid' in nm_out
    m = re.search(r'([0-9a-f]+)\s+[A-Za-z]\s+_sweet_vtimer_intid', nm_out)
    assert m is not None
    sym_addr = int(m.group(1), 16)
    assert sym_addr == 0xfffffe00072a6198

    dump_cmd = ['llvm-objdump', '-s', '-j', '__const', KERNEL_PATH]
    dump_out = subprocess.check_output(dump_cmd, text=True)
    line_match = re.search(r'fffffe00072a6190\s+([0-9a-f\s]{35,})', dump_out)
    assert line_match is not None
    hex_str = line_match.group(1).replace(' ', '')
    val_intid = int.from_bytes(bytes.fromhex(hex_str[16:24]), 'little')
    assert val_intid == 27, f'default sweet_vtimer_intid {val_intid} != 27'
    print('PASS: test_sweet_vtimer_intid_symbol_and_value')

def test_clean_constraints():
    with open('/home/exerczz1/ios-agate/tests/test_challenger_m3.py', 'r') as f:
        for idx, line in enumerate(f, 1):
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('/*'):
                raise AssertionError(f'Comment on line {idx}: {stripped}')
    print('PASS: test_clean_constraints')

if __name__ == '__main__':
    test_adt_gic_node()
    test_adt_arm_io_ranges()
    test_adt_cpus_timebase()
    test_kernel_pe_init_fiq()
    test_kernel_sleh_irq()
    test_sweet_vtimer_intid_symbol_and_value()
    test_clean_constraints()
    print('ALL MILESTONE 3 CHALLENGER TESTS PASSED')
