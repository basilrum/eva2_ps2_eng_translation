# -*- coding: utf-8 -*-
"""Prune the function list by REACHABILITY, not by shape.

`func_scan.py` unions two sources: `jal` targets (certain) and the word after
each `jr $ra` (over-fires, because a function with several returns produces an
interior boundary that is really just more of the same function).

The obvious filter -- "a real entry starts with a stack adjust" -- was measured
and does NOT work: 74-85% of known-good `jal` targets start with `addiu`, but so
do 58-72% of the questionable ones. The base rates are too close to separate
them, so filtering on shape would discard real functions.

Reachability does separate them. A real function is reached either by a `jal`,
or through a pointer -- a jump table, a callback table, a vtable. So this scans
the whole image for stored words that equal a candidate address and keeps
anything referenced either way. A boundary-only candidate that nothing in the
binary ever refers to is almost certainly the tail of the function above it.

    python3 prune_funcs.py [--json symbols/functions_pruned.json]
"""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from addrloads import loads as _loads

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'


def main():
    fns = json.load(open(os.path.join(ROOT, 'symbols', 'functions.json')))
    out, tot_before, tot_after = {}, 0, 0
    for rel, info in fns.items():
        base = info['base']
        blob = open(os.path.join(GAME, rel), 'rb').read()
        funcs = sorted(info['functions'], key=lambda f: f['addr'])
        addrs = {f['addr'] for f in funcs}

        lo, hi = ((0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99')
                  else (0, len(blob) & ~3))

        # (a) a stored word equal to a candidate entry -- jump/callback tables
        ptr = set()
        for i in range(0, len(blob) - 3, 4):
            v = struct.unpack_from('<I', blob, i)[0]
            if v in addrs:
                ptr.add(v)

        # (b) an address BUILT by lui/addiu -- these get called through jalr,
        # so neither the jal scan nor the stored-word scan sees them. 240 of
        # them were wrongly dropped before this class was added.
        taken = set()
        for _i, a in _loads(blob, lo, hi):
            if a in addrs:
                taken.add(a)

        # (c) branched to from inside the function above -> a continuation,
        # positively NOT a function start
        BR = {1, 4, 5, 6, 7, 20, 21, 22, 23}
        btgt = {}
        for i in range(lo, hi - 4, 4):
            w = struct.unpack_from('<I', blob, i)[0]
            op = w >> 26
            a = None
            if op in BR:
                o = w & 0xFFFF
                a = base + i + 4 + ((o - 0x10000 if o & 0x8000 else o) << 2)
            elif op == 2:
                a = ((base + i) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
            if a is not None:
                btgt.setdefault(a, []).append(base + i)

        keep, cont, unsure = [], 0, 0
        srt = sorted(addrs)
        import bisect as _b
        confirmed = {f['addr'] for f in funcs if f['called']} | ptr | taken
        for f in funcs:
            f = dict(f)
            f['ptr_ref'] = f['addr'] in ptr
            f['addr_taken'] = f['addr'] in taken
            if f['called'] or f['ptr_ref'] or f['addr_taken']:
                f['confidence'] = 'reached'
                keep.append(f); continue
            # not reached: is it provably a continuation?
            k = _b.bisect_right(sorted(confirmed), f['addr']) - 1
            owner = sorted(confirmed)[k] if k >= 0 else None
            srcs = btgt.get(f['addr'], [])
            if owner is not None and any(owner <= s < f['addr'] for s in srcs):
                cont += 1                     # dropped, provably a continuation
            elif any(not (owner is not None and owner <= s < f['addr'])
                     for s in srcs if (struct.unpack_from('<I', blob, s - base)[0] >> 26) == 2):
                # A `j` from OUTSIDE the function above is a TAIL CALL, which
                # is a real reference -- the callee simply never appears as a
                # jal target. Before this, such functions were filed as
                # "unreferenced" despite being called: `j` was only ever read
                # as continuation evidence, which was correct until the
                # tail-call boundary fix proved tail calls are everywhere.
                f['confidence'] = 'reached'
                f['tail_called'] = True
                keep.append(f)
            else:
                unsure += 1
                f['confidence'] = 'unreferenced'
                keep.append(f)
        # recompute sizes over the kept set
        for i, f in enumerate(keep):
            end = keep[i + 1]['addr'] if i + 1 < len(keep) else None
            if end:
                f['size'] = end - f['addr']
        reached = sum(1 for f in keep if f['confidence'] == 'reached')
        print(f'{rel}: {len(funcs)} candidates -> {len(keep)} kept, {cont} dropped')
        print(f'   {reached} REACHED (jal / stored pointer / address taken)')
        print(f'   {unsure} kept but unreferenced -- flagged, not trusted')
        print(f'   {cont} dropped: provably branched into from the function above')
        tot_before += len(funcs); tot_after += len(keep)
        out[rel] = {'base': base, 'functions': keep}
    R = sum(1 for v in out.values() for f in v['functions'] if f['confidence'] == 'reached')
    print(f'\nTOTAL {tot_before} candidates -> {tot_after} kept '
          f'({tot_before-tot_after} dropped as provable continuations)')
    print(f'      {R} of those are REACHED and can be trusted as real functions')
    if '--json' in sys.argv:
        d = os.path.join(ROOT, 'symbols', 'functions_pruned.json')
        json.dump(out, open(d, 'w'), indent=1)
        print(f'wrote {d}')


if __name__ == '__main__':
    main()
