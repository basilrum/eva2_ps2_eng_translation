# -*- coding: utf-8 -*-
"""Look an address up in the map: which function, which .c file, who calls it.

    python3 whatis.py 0x1511F0
    python3 whatis.py 0x1511F0 --disasm
"""
import json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'


def callers(rel, base, target):
    blob = open(os.path.join(GAME, rel), 'rb').read()
    lo, hi = (0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99') else (0, len(blob) & ~3)
    out = []
    for i in range(lo, hi - 4, 4):
        w = struct.unpack_from('<I', blob, i)[0]
        if (w >> 26) != 3:
            continue
        if (((base + i) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)) == target:
            out.append(base + i)
    return out


def main():
    addr = int(sys.argv[1], 0)
    fns = json.load(open(os.path.join(ROOT, 'symbols', 'functions.json')))
    for rel, info in fns.items():
        for f in info['functions']:
            if not (f['addr'] <= addr < f['addr'] + f['size']):
                continue
            print(f"{rel}  base 0x{info['base']:08X}")
            print(f"  function 0x{f['addr']:08X}  size {f['size']} bytes "
                  f"({f['size']//4} instructions)")
            print(f"  unit     {f['unit'] or 'unknown'}"
                  f"   [{'pinned' if f['certain'] else 'narrowed to two'}]")
            print(f"  offset   +0x{addr - f['addr']:X} into it")
            c = callers(rel, info['base'], f['addr'])
            print(f"  callers  {len(c)}" + (': ' + ', '.join(f'0x{a:08X}' for a in c[:8])
                                            + (' ...' if len(c) > 8 else '') if c else
                                            '  (pointer-only or an entry point)'))
            if '--disasm' in sys.argv:
                from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_LITTLE_ENDIAN
                md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 + CS_MODE_LITTLE_ENDIAN)
                md.skipdata = True            # R5900 ops abort the sweep otherwise
                blob = open(os.path.join(GAME, rel), 'rb').read()
                off = f['addr'] - info['base']
                print()
                for x in md.disasm(blob[off:off + f['size']], f['addr']):
                    mark = '  <<<' if x.address == addr else ''
                    print(f"    0x{x.address:08X}  {x.mnemonic:9} {x.op_str}{mark}")
            return
    print(f'0x{addr:08X} is not inside any mapped function')


if __name__ == '__main__':
    main()
