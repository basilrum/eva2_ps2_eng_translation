# -*- coding: utf-8 -*-
"""Test whether a function's rodata references identify its translation unit.

A unit's .rodata is emitted as one contiguous block, and those blocks come out
in link order (proven: literal order vs code order is rho=+1.000). The
__FILE__ literals sit inside those blocks and mark them.

So the hypothesis is: if a function references a rodata address, that address
falls in its OWN unit's block -- i.e. between its unit's __FILE__ literal and
the next unit's. If that holds, every string reference becomes an anchor, and
the 69 unlocated units stop being invisible.

This does not assume the hypothesis, it MEASURES it, using the functions
already pinned by a __FILE__ reference as ground truth.

    python3 rodata_anchor.py
"""
import bisect, json, os, re, struct, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
SRC = re.compile(rb'(?:\.\./)?[\w/]*[\w-]+\.(?:c|cpp)\x00')

sys.path.insert(0, HERE)
from addrloads import loads
# ELF section ranges (file offsets) from readelf
RODATA = (0xF7300, 0xF7300 + 0x1F468)
DATA = (0xD3780, 0xD3780 + 0x23B5C)


def main():
    rel = 'SLPS_252.99'
    base = 0xFF000
    blob = open(os.path.join(GAME, rel), 'rb').read()
    fns = json.load(open(os.path.join(ROOT, 'symbols', 'functions.json')))[rel]
    funcs = sorted(fns['functions'], key=lambda f: f['addr'])
    starts = [f['addr'] for f in funcs]

    # __FILE__ literals, in link order, with the unit each marks
    lits = []
    for m in SRC.finditer(blob):
        s = m.start()
        if s == 0 or blob[s - 1] == 0:
            lits.append((s, m.group()[:-1].decode('latin-1')))
    lits.sort()
    lit_off = [o for o, _ in lits]

    # every address load that resolves into .rodata or .data
    hits = defaultdict(list)
    lo, hi = 0x1000, 0x1000 + 0xC4AB8
    for i, a in loads(blob, lo, hi):
        off = a - base
        if RODATA[0] <= off < RODATA[1]:
            k = bisect.bisect_right(starts, base + i) - 1
            if k >= 0:
                hits[starts[k]].append(off)

    pinned = {f['addr']: f['unit'] for f in funcs if f['certain']}
    print(f'{len(hits)} functions make a .rodata reference; '
          f'{sum(1 for a in hits if a in pinned)} of them are pinned\n')

    ok = near = tot = 0
    dist = []
    for a, offs in hits.items():
        u = pinned.get(a)
        if not u:
            continue
        # which literal block does each referenced offset fall in?
        for off in offs:
            k = bisect.bisect_right(lit_off, off) - 1
            tot += 1
            if k < 0:
                continue
            owner = lits[k][1]
            if owner == u:
                ok += 1
            # how many units away is it, in link order?
            try:
                iu = [nm for _, nm in lits].index(u)
                dist.append(abs(k - iu))
                near += (abs(k - iu) <= 1)
            except ValueError:
                pass
    print(f'HYPOTHESIS TEST on {tot} references from pinned functions:')
    print(f'   reference lands in its own unit\'s literal block : '
          f'{ok}/{tot} = {ok/max(tot,1):.1%}')
    print(f'   lands within ONE unit of it                     : '
          f'{near}/{tot} = {near/max(tot,1):.1%}')
    if dist:
        import statistics
        print(f'   median distance in units: {statistics.median(dist):.0f}, '
              f'mean {statistics.mean(dist):.1f}')


if __name__ == '__main__':
    main()
