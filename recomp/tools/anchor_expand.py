# -*- coding: utf-8 -*-
"""Anchor functions by their .rodata references, then re-window everything.

Measured on the ELF's pinned functions: a function's rodata reference falls
inside its OWN unit's literal block 97.7% of the time (341/349), and within one
unit of it 98.6%. So a rodata reference identifies the unit nearly as reliably
as a __FILE__ reference does -- and unlike __FILE__ references, they also land
in the blocks of the 69 units that no address load ever names, which is exactly
what was missing.

Each function votes with all of its references and takes the majority; ties and
single-reference disagreements are the expected ~2% error, so a function is
only anchored when its references agree.

    python3 anchor_expand.py [--json symbols/unit_windows.json]
"""
import bisect, json, os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from addrloads import loads as _loads
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
SRC = re.compile(rb'(?:\.\./)?[\w/]*[\w-]+\.(?:c|cpp)\x00')


def literals(blob):
    out = []
    for m in SRC.finditer(blob):
        s = m.start()
        if s == 0 or blob[s - 1] == 0:
            out.append((s, m.group()[:-1].decode('latin-1')))
    out.sort()
    return out


def main():
    fns = json.load(open(os.path.join(ROOT, 'symbols', 'functions.json')))
    result = {}
    for rel, info in fns.items():
        base = info['base']
        blob = open(os.path.join(GAME, rel), 'rb').read()
        lits = literals(blob)
        if len(lits) < 2:
            continue
        lit_off = [o for o, _ in lits]
        order = [nm for _, nm in lits]
        funcs = sorted(info['functions'], key=lambda f: f['addr'])
        starts = [f['addr'] for f in funcs]
        # the literal block region -- for the overlays there are no section
        # headers, so bound it by where the literals actually live
        r0, r1 = lit_off[0], lit_off[-1] + 64
        lo, hi = (0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99') else (0, len(blob) & ~3)

        # Use the liveness-aware extractor: pairing lui only with an addiu at
        # +4/+8 was missing ~45% of all address loads, which is the evidence
        # this whole pass runs on.
        refs = defaultdict(list)
        for i, a in _loads(blob, lo, hi):
            off = a - base
            if r0 <= off < r1:
                k = bisect.bisect_right(starts, base + i) - 1
                if k >= 0:
                    kk = bisect.bisect_right(lit_off, off) - 1
                    if kk >= 0:
                        refs[starts[k]].append(order[kk])

        anchored = {}
        for f in funcs:
            if f['certain']:
                anchored[f['addr']] = f['unit']
        added = 0
        for a, votes in refs.items():
            if a in anchored:
                continue
            c = Counter(votes).most_common()
            if len(c) == 1 or c[0][1] > c[1][1]:        # a clear majority only
                anchored[a] = c[0][0]; added += 1

        # Units are contiguous and ordered, so anchors MUST be non-decreasing
        # in unit index as address increases. Anything that violates that is a
        # bad anchor -- a function referencing a string in another unit's
        # block. Keep the longest non-decreasing subsequence and drop the rest.
        # (The 100% hold-out did not catch these: it only sampled functions
        # pinned by __FILE__, which cluster where literals are referenced.)
        idx = {nm: i for i, nm in enumerate(order)}
        cand = sorted((a, u) for a, u in anchored.items() if u in idx)
        seq = [idx[u] for _, u in cand]
        import bisect as _bi
        tails, prev = [], [-1] * len(seq)
        pos = []
        for i, v in enumerate(seq):
            j = _bi.bisect_right(tails, v)
            if j == len(tails):
                tails.append(v); pos.append(j)
            else:
                tails[j] = v; pos.append(j)
        best, keepset = len(tails) - 1, set()
        for i in range(len(seq) - 1, -1, -1):
            if pos[i] == best:
                keepset.add(i); best -= 1
                if best < 0:
                    break
        dropped_anchor = len(cand) - len(keepset)
        aa = [cand[i] for i in sorted(keepset)]
        anchored = {a: u for a, u in aa}
        alo = [a for a, _ in aa]
        wins = []
        for f in funcs:
            a = f['addr']
            if a in anchored:
                wins.append({'addr': a, 'candidates': [anchored[a]], 'src': 'anchor'})
                continue
            k = bisect.bisect_right(alo, a) - 1
            # Outside the anchored range the window is unbounded on one side.
            # Collapsing it to the first/last unit in link order is WRONG: the
            # head and tail almost certainly contain units that have no
            # __FILE__ literal at all, which this method cannot see. Before
            # this guard, 1,296 functions across 256KB of tail were all
            # attributed to chara.c, and 150 across 420KB of head to im/test.c.
            if k < 0 or k + 1 >= len(aa):
                wins.append({'addr': a, 'candidates': [], 'src': 'outside'})
                continue
            lo_i, hi_i = idx[aa[k][1]], idx[aa[k + 1][1]]
            if hi_i < lo_i:
                lo_i, hi_i = hi_i, lo_i
            wins.append({'addr': a, 'candidates': order[lo_i:hi_i + 1], 'src': 'window'})
        sizes = [len(w['candidates']) for w in wins]
        one = sum(1 for s in sizes if s == 1)
        import statistics
        print(f'{rel}')
        print(f'   anchors: {len(anchored)} kept '
              f'({dropped_anchor} dropped as out of link order)')
        print(f'   {len(wins)} functions: {one} narrowed to ONE unit '
              f'({one/len(wins):.0%}), median window '
              f'{statistics.median(sizes):.0f}, max {max(sizes)}')
        result[rel] = {'base': base, 'order': order, 'windows': wins}
    tot = sum(len(v['windows']) for v in result.values())
    one = sum(1 for v in result.values() for w in v['windows'] if len(w['candidates']) == 1)
    print(f'\nTOTAL {one}/{tot} functions narrowed to exactly one .c file ({one/tot:.0%})')
    if '--json' in sys.argv:
        d = os.path.join(ROOT, 'symbols', 'unit_windows.json')
        json.dump(result, open(d, 'w'), indent=1)
        print(f'wrote {d}')


if __name__ == '__main__':
    main()
