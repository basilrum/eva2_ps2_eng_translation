# -*- coding: utf-8 -*-
"""Recover the full link order of translation units, including unlocated ones.

69 of the 248 source files have __FILE__ literals that no address load ever
references, so `tu_map.py` cannot place them -- they sit inside the gaps, which
is why treating a gap as "unit A or unit B" scored barely above chance in the
hold-out test.

But the compiler emits each unit's .rodata in the same order it emits its
.text, and that holds here EXACTLY: ranking the located units by literal offset
against their code address gives Spearman rho = +1.000 with zero inversions
(2,415 + 1,891 + 990 pairwise comparisons in the ELF, BATTLE and FREE).

So literal order IS link order. Every file can be put in sequence, and a
function narrows to the ordered window of units between the nearest located
anchors either side of it -- correct by construction, no guessing.

    python3 unit_order.py [--json symbols/unit_order.json]
"""
import bisect, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
SRC = re.compile(rb'(?:\.\./)?[\w/]*[\w-]+\.(?:c|cpp)\x00')


def main():
    tu = json.load(open(os.path.join(ROOT, 'symbols', 'tu_map.json')))
    fns = json.load(open(os.path.join(ROOT, 'symbols', 'functions.json')))
    out = {}
    for rel, info in tu.items():
        blob = open(os.path.join(GAME, rel), 'rb').read()
        lits = []
        for m in SRC.finditer(blob):
            s = m.start()
            if s == 0 or blob[s - 1] == 0:
                lits.append((s, m.group()[:-1].decode('latin-1')))
        lits.sort()
        order = [nm for _, nm in lits]                    # link order
        idx = {nm: i for i, nm in enumerate(order)}
        anchors = sorted(((idx[u['file']], u['lo'], u['hi'], u['file'])
                          for u in info['units'] if u['file'] in idx))
        if not anchors:
            continue
        # sanity: anchors must be ascending in BOTH order index and address
        assert all(anchors[i][1] < anchors[i + 1][1] for i in range(len(anchors) - 1))
        alo = [a[1] for a in anchors]
        funcs = sorted(fns[rel]['functions'], key=lambda f: f['addr'])
        wins = []
        for f in funcs:
            a = f['addr']
            k = bisect.bisect_right(alo, a) - 1
            if 0 <= k < len(anchors) and anchors[k][1] <= a <= anchors[k][2]:
                cand = [anchors[k][3]]                    # inside a pinned span
            else:
                lo_i = anchors[k][0] if k >= 0 else -1
                hi_i = anchors[k + 1][0] if k + 1 < len(anchors) else len(order)
                cand = order[max(lo_i, 0):hi_i + 1] if k >= 0 else order[:hi_i + 1]
            wins.append({'addr': a, 'candidates': cand})
        sizes = [len(w['candidates']) for w in wins]
        exact = sum(1 for s in sizes if s == 1)
        import statistics
        print(f'{rel}: {len(order)} units in link order, {len(anchors)} anchored')
        print(f'   {len(wins)} functions: {exact} narrowed to ONE unit '
              f'({exact/len(wins):.0%}), median window {statistics.median(sizes):.0f}, '
              f'max {max(sizes)}')
        out[rel] = {'order': order, 'windows': wins}
    if '--json' in sys.argv:
        d = os.path.join(ROOT, 'symbols', 'unit_order.json')
        json.dump(out, open(d, 'w'), indent=1)
        print(f'\nwrote {d}')


if __name__ == '__main__':
    main()
