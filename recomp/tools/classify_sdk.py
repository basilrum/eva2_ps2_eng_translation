# -*- coding: utf-8 -*-
"""Mark which functions are Sony SDK / libc rather than game code.

The 256KB after the last game translation unit references sceSifMCallRpc,
'libpad: Module version mismatch', DMA register names (D1_TADR, D2_MADR),
MPEG decoder messages ('slice_start_code(0x%08x) out of range', and Sony's own
typos 'skiped macroblock in I picure') and libc float formatting ('Inf',
'e+%d', '0123456789abcdef'). That is the linked runtime, not the game.

This matters for two reasons: it explains why the attribution can never reach
those functions (they have no game __FILE__ literals), and in a decomp you
would LINK the real library rather than decompile any of it. The game itself
is ~1,400 functions smaller than the raw count suggests.

Libraries link contiguously, so each function is labelled by the nearest
identifying string evidence either side of it.

    python3 classify_sdk.py [--apply]
"""
import bisect, json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from addrloads import loads as _loads

MARKERS = [
    ('libmpeg', ('slice_start_code', 'macroblock', 'picture', 'Extension',
                 'the second field is missing', 'Skip to the next picture')),
    ('libsif',  ('sceSifMCallRpc', 'send buffer addr', 'receive buffer addr')),
    ('libpad',  ('libpad:',)),
    ('libdma',  ('D1_TADR', 'D1_MADR', 'D2_TADR', 'D2_MADR')),
    ('kernel',  ('TLB over flow', 'TTY: receive error')),
    ('libc',    ('0123456789abcdef', 'Inf', 'e+%d')),
]


def cstr(b, off, lim=90):
    e = b.find(b'\x00', off)
    if e < 0 or e - off > lim or e == off:
        return None
    r = b[off:e]
    return r.decode() if all(32 <= c < 127 for c in r) else None


def main():
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    wins = json.load(open(os.path.join(ROOT, 'symbols', 'unit_windows2.json')))
    rel = 'SLPS_252.99'
    base = syms[rel]['base']
    b = open(os.path.join(GAME, rel), 'rb').read()
    funcs = sorted(syms[rel]['functions'], key=lambda f: f['addr'])
    starts = [f['addr'] for f in funcs]
    anch = [w['addr'] for w in wins[rel]['windows'] if w['src'] != 'outside']
    hi_a = max(anch)
    tail = [f for f in funcs if f['addr'] > hi_a]
    lo, hi = min(f['addr'] for f in tail), max(f['addr'] for f in tail)

    ev = {}
    for i, addr in _loads(b, lo - base, hi - base):
        off = addr - base
        if not (0 <= off < len(b)):
            continue
        s = cstr(b, off)
        if not s:
            continue
        for lib, keys in MARKERS:
            if any(k in s for k in keys):
                k2 = bisect.bisect_right(starts, base + i) - 1
                if k2 >= 0:
                    ev[starts[k2]] = lib
                break

    pts = sorted(ev)
    def nearest(a):
        if not pts:
            return 'sdk'
        i = bisect.bisect_left(pts, a)
        cand = [p for p in (pts[i-1] if i else None, pts[i] if i < len(pts) else None)
                if p is not None]
        return ev[min(cand, key=lambda p: abs(p - a))]

    from collections import Counter
    lab = Counter()
    for f in tail:
        f['region'] = 'sdk'
        f['library'] = nearest(f['addr'])
        lab[f['library']] += 1
    for f in funcs:
        f.setdefault('region', 'game')

    print(f'tail 0x{lo:08X}..0x{hi:08X}  {len(tail)} functions marked as SDK/library')
    print(f'   {len(ev)} of them carry direct string evidence; the rest labelled '
          f'by nearest neighbour (libraries link contiguously)')
    for k, v in lab.most_common():
        print(f'      {v:5}  {k}')
    game = sum(1 for f in funcs if f['region'] == 'game')
    print(f'\ngame code in this binary: {game} functions '
          f'(was reporting {len(funcs)} including the runtime)')
    if '--apply' in sys.argv:
        json.dump(syms, open(os.path.join(ROOT, 'symbols', 'symbols.json'), 'w'), indent=1)
        print('applied')


if __name__ == '__main__':
    main()
