# -*- coding: utf-8 -*-
"""Extract address loads properly, with register liveness.

Every earlier pass paired a `lui` only with an `addiu` at +4 or +8. Compilers
routinely separate the two halves much further, and the narrow window was
finding 4,696 loads in the ELF where a correct scan finds ~8,400 -- so roughly
45% of all address references were invisible to the anchoring, which is the
evidence attribution runs on.

Done properly: after `lui rt, hi`, walk forward until either
  * an instruction reads rt as its base/source and supplies the low half
    (addiu / ori / any load or store) -> that is the pair, or
  * an instruction WRITES rt without reading it -> the register was reused for
    something else, so give up.

Shared by the anchoring passes via `loads(blob, lo, hi)`.
"""
import struct

# opcodes that combine with a lui: addiu, ori, and the load/store family
LOW_OPS = {0x09, 0x0D, 0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B,
           0x31, 0x39, 0x37, 0x3F, 0x26, 0x2E, 0x22, 0x2A}
# opcodes whose destination is the rt field
RT_DEST = {0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x18, 0x19,
           0x20, 0x21, 0x23, 0x24, 0x25, 0x26, 0x27, 0x22, 0x2E, 0x31, 0x35}


def loads(blob, lo, hi, window=48):
    """Yield (site_offset, resolved_address)."""
    out = []
    for i in range(lo, hi - 4, 4):
        w = struct.unpack_from('<I', blob, i)[0]
        if (w >> 26) != 0x0F:                       # lui
            continue
        rt, high = (w >> 16) & 0x1F, (w & 0xFFFF) << 16
        if rt == 0:
            continue
        for j in range(i + 4, min(i + 4 + window, hi), 4):
            w2 = struct.unpack_from('<I', blob, j)[0]
            op = w2 >> 26
            rs2, rt2 = (w2 >> 21) & 0x1F, (w2 >> 16) & 0x1F
            if op in LOW_OPS and rs2 == rt:
                l = w2 & 0xFFFF
                out.append((i, (high + (l - 0x10000 if l & 0x8000 else l)) & 0xFFFFFFFF))
                break
            # register clobbered without being used -> not a pair
            if op == 0 and ((w2 >> 11) & 0x1F) == rt:
                break
            if op in RT_DEST and rt2 == rt and rs2 != rt:
                break
        # a lui with no partner is a bare upper half; ignore it
    return out


if __name__ == '__main__':
    import json, os
    S = json.load(open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'symbols', 'symbols.json')))
    GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
    for rel, info in S.items():
        b = open(os.path.join(GAME, rel), 'rb').read()
        lo, hi = ((0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99')
                  else (0, len(b) & ~3))
        print(f'{rel}: {len(loads(b, lo, hi))} address loads')
