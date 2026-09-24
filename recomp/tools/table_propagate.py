# -*- coding: utf-8 -*-
"""Attribute functions via dispatch-table membership.

A table of function pointers is a dispatch table, and its handlers are written
together in one source file -- every table inspected by hand had all of its
targets in a single unit. So if most entries of a table are attributed to unit
U, the unattributed ones are almost certainly U as well.

Runs of >=6 consecutive pointers are treated as a table. A table only votes if
at least 4 of its targets are already attributed and at least 80% of those
agree, and a target is only assigned if the ordered window allows it.

Hold-out: hide each attributed target's own label and see whether its table
mates recover it.

    python3 table_propagate.py [--json symbols/unit_windows5.json]
"""
import json, os, struct, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'


def tables(blob, faddr):
    words = [struct.unpack_from('<I', blob, i)[0] for i in range(0, (len(blob) & ~3), 4)]
    isf = [w in faddr for w in words]
    out, i = [], 0
    while i < len(isf):
        if isf[i]:
            j = i
            while j < len(isf) and isf[j]:
                j += 1
            if j - i >= 6:
                out.append(words[i:j])
            i = j
        else:
            i += 1
    return out


def main():
    win = json.load(open(os.path.join(ROOT, 'symbols', 'unit_windows3.json')))
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    out, G_ok, G_n, G_add = {}, 0, 0, 0
    for rel, info in win.items():
        blob = open(os.path.join(GAME, rel), 'rb').read()
        faddr = {f['addr'] for f in syms[rel]['functions']}
        known = {w['addr']: w['candidates'][0]
                 for w in info['windows'] if len(w['candidates']) == 1}
        tabs = tables(blob, faddr)

        # hold-out
        ok = n = 0
        for t in tabs:
            for a in set(t):
                if a not in known:
                    continue
                mates = [known.get(x) for x in t if x != a and x in known]
                mates = [m for m in mates if m]
                if len(mates) < 4:
                    continue
                c = Counter(mates).most_common()
                if c[0][1] / len(mates) < 0.8:
                    continue
                n += 1; ok += (c[0][0] == known[a])

        vote = {}
        for t in tabs:
            mates = [known.get(x) for x in t if x in known]
            mates = [m for m in mates if m]
            if len(mates) < 4:
                continue
            c = Counter(mates).most_common()
            if c[0][1] / len(mates) < 0.8:
                continue
            for x in set(t):
                if x not in known:
                    vote.setdefault(x, Counter())[c[0][0]] += 1

        added, neww = 0, []
        for w in info['windows']:
            if len(w['candidates']) == 1:
                neww.append(w); continue
            v = vote.get(w['addr'])
            if v:
                pick = v.most_common(1)[0][0]
                if not w['candidates'] or pick in w['candidates']:
                    neww.append({'addr': w['addr'], 'candidates': [pick], 'src': 'table'})
                    added += 1; continue
            neww.append(w)
        one = sum(1 for x in neww if len(x['candidates']) == 1)
        print(f'{rel}: {len(tabs)} tables  hold-out {ok}/{n} = {ok/max(n,1):.1%}  '
              f'+{added} -> {one}/{len(neww)} ({one/len(neww):.0%})')
        G_ok += ok; G_n += n; G_add += added
        out[rel] = {'base': info['base'], 'order': info['order'], 'windows': neww}
    print(f'\ndispatch-table hold-out: {G_ok}/{G_n} = {G_ok/max(G_n,1):.1%}   +{G_add} resolved')
    tot = sum(len(v['windows']) for v in out.values())
    one = sum(1 for v in out.values() for w in v['windows'] if len(w['candidates']) == 1)
    print(f'TOTAL {one}/{tot} ({one/tot:.0%})')
    if '--json' in sys.argv:
        p = os.path.join(ROOT, 'symbols', 'unit_windows5.json')
        json.dump(out, open(p, 'w'), indent=1)
        print(f'wrote {p}')


if __name__ == '__main__':
    main()
