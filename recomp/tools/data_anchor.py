# -*- coding: utf-8 -*-
"""Extend attribution using .data / .bss references.

.rodata worked because the __FILE__ literals sit inside it and label the
blocks directly. .data has no such labels -- but a unit's statics are emitted
in link order too, so the blocks are there, they just need naming.

Bootstrap: functions already anchored (by __FILE__ or by rodata) tell us which
.data offsets belong to which unit. That gives a .data offset -> unit map,
which then anchors further functions that touch the same statics.

The map is built ONLY from anchored functions, and it is hold-out tested the
same way as before: hide a function's anchor, see whether its .data references
alone recover the right unit.

    python3 data_anchor.py [--json symbols/unit_windows2.json]
"""
import bisect, json, os, re, struct, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from addrloads import loads as _loads

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'


def refs_in(blob, base, starts, lo, hi, rlo, rhi):
    """function addr -> list of referenced offsets inside [rlo,rhi)."""
    out = defaultdict(list)
    for i, a in _loads(blob, lo, hi):
        off = a - base
        if rlo <= off < rhi:
            k = bisect.bisect_right(starts, base + i) - 1
            if k >= 0:
                out[starts[k]].append(off)
    return out


def main():
    win = json.load(open(os.path.join(ROOT, 'symbols', 'unit_windows.json')))
    fns = json.load(open(os.path.join(ROOT, 'symbols', 'functions.json')))
    out = {}
    G_ok = G_n = 0
    for rel, info in win.items():
        base = info['base']
        blob = open(os.path.join(GAME, rel), 'rb').read()
        funcs = sorted(fns[rel]['functions'], key=lambda f: f['addr'])
        starts = [f['addr'] for f in funcs]
        anchored = {w['addr']: w['candidates'][0]
                    for w in info['windows'] if w['src'] == 'anchor'}
        # .data is everything addressable that is NOT the literal region; for
        # the ELF use the real section bounds, for overlays take the whole file
        if rel.endswith('.99'):
            rlo, rhi = 0xD3780, 0xD3780 + 0x23B5C
            lo, hi = 0x1000, 0x1000 + 0xC4AB8
        else:
            rlo, rhi = 0, len(blob)
            lo, hi = 0, len(blob) & ~3
        dref = refs_in(blob, base, starts, lo, hi, rlo, rhi)

        # build offset -> unit from anchored functions only
        owner = defaultdict(Counter)
        for a, offs in dref.items():
            u = anchored.get(a)
            if u:
                for o in offs:
                    owner[o][u] += 1
        omap = {}
        for o, c in owner.items():
            m = c.most_common()
            if len(m) == 1 or m[0][1] > m[1][1]:
                omap[o] = m[0][0]

        # hold-out: hide each anchored function's label, recover from .data
        ok = n = 0
        for a, u in anchored.items():
            offs = dref.get(a)
            if not offs:
                continue
            votes = Counter()
            for o in offs:
                c = owner.get(o)
                if not c:
                    continue
                c2 = Counter(c); c2[u] -= 1               # remove own vote
                c2 = +c2
                if c2:
                    votes[c2.most_common(1)[0][0]] += 1
            if not votes:
                continue
            m = votes.most_common()
            if len(m) > 1 and m[0][1] == m[1][1]:
                continue
            n += 1; ok += (m[0][0] == u)
        G_ok += ok; G_n += n
        print(f'{rel}: .data offsets mapped {len(omap)}, '
              f'hold-out {ok}/{n} = {ok/max(n,1):.1%}')

        # apply to unanchored functions
        added = 0
        newwin = []
        for w in info['windows']:
            if w['src'] == 'anchor' or len(w['candidates']) == 1:
                newwin.append(w); continue
            offs = dref.get(w['addr'])
            pick = None
            if offs:
                votes = Counter(omap[o] for o in offs if o in omap)
                if votes:
                    m = votes.most_common()
                    if len(m) == 1 or m[0][1] > m[1][1]:
                        if m[0][0] in w['candidates']:     # must stay in-window
                            pick = m[0][0]
            if pick:
                newwin.append({'addr': w['addr'], 'candidates': [pick], 'src': 'data'})
                added += 1
            else:
                newwin.append(w)
        one = sum(1 for w in newwin if len(w['candidates']) == 1)
        print(f'   +{added} functions resolved by .data -> '
              f'{one}/{len(newwin)} on one unit ({one/len(newwin):.0%})')
        out[rel] = {'base': base, 'order': info['order'], 'windows': newwin}
    print(f'\n.data hold-out overall: {G_ok}/{G_n} = {G_ok/max(G_n,1):.1%}')
    tot = sum(len(v['windows']) for v in out.values())
    one = sum(1 for v in out.values() for w in v['windows'] if len(w['candidates']) == 1)
    print(f'TOTAL {one}/{tot} functions on exactly one .c file ({one/tot:.0%})')
    if '--json' in sys.argv:
        d = os.path.join(ROOT, 'symbols', 'unit_windows2.json')
        json.dump(out, open(d, 'w'), indent=1)
        print(f'wrote {d}')


if __name__ == '__main__':
    main()
