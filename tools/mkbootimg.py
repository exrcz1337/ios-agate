#!/usr/bin/env python3
import argparse, hashlib, struct

def parse_int(x):
    return int(x, 0) if x else 0

def pad(data, page_size):
    r = len(data) % page_size
    return data + (b'\0' * (page_size - r) if r else b'')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--kernel', required=True)
    p.add_argument('--ramdisk', required=True)
    p.add_argument('--dtb')
    p.add_argument('--cmdline', default='')
    p.add_argument('--base', type=parse_int, default=0)
    p.add_argument('--kernel_offset', type=parse_int, default=0x8000)
    p.add_argument('--ramdisk_offset', type=parse_int, default=0x1000000)
    p.add_argument('--second_offset', type=parse_int, default=0)
    p.add_argument('--tags_offset', type=parse_int, default=0x100)
    p.add_argument('--dtb_offset', type=parse_int, default=0)
    p.add_argument('--pagesize', type=parse_int, default=2048)
    p.add_argument('--header_version', type=parse_int, default=2)
    p.add_argument('--os_version', type=parse_int, default=0x18000197)
    p.add_argument('--os_patch_level', default='')
    p.add_argument('-o', '--output', required=True)
    a = p.parse_args()

    k_data = open(a.kernel, 'rb').read()
    r_data = open(a.ramdisk, 'rb').read()
    d_data = open(a.dtb, 'rb').read() if a.dtb else b''

    k_addr = a.base + a.kernel_offset
    r_addr = a.base + a.ramdisk_offset
    t_addr = a.base + a.tags_offset
    d_addr = a.base + a.dtb_offset

    hdr = bytearray(a.pagesize)
    hdr[0:8] = b'ANDROID!'
    struct.pack_into('<10I', hdr, 8,
                     len(k_data), k_addr,
                     len(r_data), r_addr,
                     0, 0,
                     t_addr, a.pagesize,
                     a.header_version, a.os_version)
    cmd = a.cmdline.encode()
    hdr[64:64+min(len(cmd), 512)] = cmd[:512]
    if len(cmd) > 512:
        hdr[608:608+min(len(cmd)-512, 1024)] = cmd[512:1536]

    h = hashlib.sha1()
    h.update(k_data)
    h.update(struct.pack('<I', len(k_data)))
    h.update(r_data)
    h.update(struct.pack('<I', len(r_data)))
    h.update(b'')
    h.update(struct.pack('<I', 0))
    if a.header_version >= 1:
        h.update(b'')
        h.update(struct.pack('<I', 0))
    if a.header_version >= 2:
        h.update(d_data)
        h.update(struct.pack('<I', len(d_data)))
    hdr[576:576+20] = h.digest()

    if a.header_version >= 1:
        struct.pack_into('<IQI', hdr, 1632, 0, 0, 1660)
    if a.header_version >= 2:
        struct.pack_into('<IQ', hdr, 1648, len(d_data), d_addr)

    out = open(a.output, 'wb')
    out.write(hdr)
    out.write(pad(k_data, a.pagesize))
    out.write(pad(r_data, a.pagesize))
    if d_data:
        out.write(pad(d_data, a.pagesize))
    out.close()

if __name__ == '__main__':
    main()
