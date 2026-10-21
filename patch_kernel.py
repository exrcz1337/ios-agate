import binascii

stage0 = binascii.unhexlify("e0ceaff2004082f201008092020480d2049581d2030380d2e50300aaa18400f8630400f1c1ffff540000048b420400f121ffff54")
mark = binascii.unhexlify("1f500071c80200540804000b0a408252eb1f8052eaceaf72086d1c530945288b08681b5329010a8b0a288152ec031faa2d010c8b8c0d00919f410271a8010039ab050039bf09003941ffff544a05009129a132915f8125f1a1feff54c0035fd6")
ret = b"\xc0\x03\x5f\xd6"

with open("/home/exerczz1/ios-agate/xnu/out/kernel.development.sweet", "r+b") as f:
    f.seek(0x489104)
    f.write(stage0)
    f.seek(0x480f24)
    f.write(mark)
    f.seek(0x480c68)
    f.write(ret)
    f.seek(0xa76f64)
    f.write(ret)
    f.seek(0xa77030)
    f.write(ret)

print("PATCH_APPLIED_SUCCESSFULLY")
