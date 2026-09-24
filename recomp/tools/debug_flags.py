# -*- coding: utf-8 -*-
"""Map every test of the debug-flags word at 0x001D3910.

One word in .data gates every developer feature left in the retail build, and
it ships as zero. This finds each test by resolving address loads to the word,
following the `lw`, and collecting the `andi` masks applied to the loaded
register.

The scan window matters: the first version looked only 24 bytes past the `lw`
and MISSED bit 0x2000, which `cdGetMediaType` @0x00106DA8 tests 28 bytes after
its load -- the function tests three bits in a row off one load. The window is
64 bytes now, and the register is tracked so an unrelated `andi` cannot be
picked up.
"""
import bisect, collections, json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
sys.path.insert(0, HERE)
from addrloads import loads

FLAGS = 0x001D3910


def main():
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    agg = collections.defaultdict(set)
    seen = set()
    for rel, info in syms.items():
        blob = open(os.path.join(GAME, rel), 'rb').read()
        base = info['base']
        fs = sorted(info['functions'], key=lambda f: f['addr'])
        starts = [f['addr'] for f in fs]
        by = {f['addr']: f for f in fs}
        lo, hi = (0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99') else (0, len(blob) & ~3)
        for i, a in loads(blob, lo, hi):
            for j in range(i, min(i + 48, hi), 4):
                w = struct.unpack_from('<I', blob, j)[0]
                if (w >> 26) != 0x23:                     # lw
                    continue
                off = w & 0xFFFF
                off = off - 0x10000 if off & 0x8000 else off
                if a + off != FLAGS and a != FLAGS:
                    continue
                rt = (w >> 16) & 0x1F
                for k in range(j + 4, min(j + 64, hi), 4):
                    w2 = struct.unpack_from('<I', blob, k)[0]
                    if (w2 >> 26) == 0x0C and ((w2 >> 21) & 0x1F) == rt:
                        if (rel, base + k) in seen:
                            continue
                        seen.add((rel, base + k))
                        kk = bisect.bisect_right(starts, base + k) - 1
                        fn = by[starts[kk]] if kk >= 0 else None
                        agg[w2 & 0xFFFF].add(
                            (rel.replace('prog/', ''), fn['name'] if fn else '?'))
                    # the register is reloaded or overwritten -> stop
                    elif (w2 >> 26) in (0x23, 0x09, 0x0F) and ((w2 >> 16) & 0x1F) == rt:
                        break
                break
    print(f'{len(seen)} tests of the debug-flags word 0x{FLAGS:08X}, '
          f'{len(agg)} distinct bit masks\n')
    for mask in sorted(agg):
        who = sorted(agg[mask])
        print(f'  0x{mask:04X}   {len(who)} sites')
        for r, n in who:
            print(f'           {r:14} {n}')


main()
