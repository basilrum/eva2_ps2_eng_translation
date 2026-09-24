# -*- coding: utf-8 -*-
"""Attribute functions whose callers all live in ONE unit.

A `static` function in C can only be called from inside its own translation
unit, and even non-static helpers are usually only used by their own file. So
if every caller of a function is attributed to unit U, the function is very
likely in U too.

This is NOT the call-graph splitter that failed earlier. That one assumed a gap
contained exactly two units and searched for a split point; this makes no
assumption about gaps at all, only asks whether the callers agree, and is
constrained to candidates the ordered window already allows.

Hold-out tested by hiding each anchored function's own label and asking whether
its callers alone recover it.

    python3 caller_locality.py [--json symbols/unit_windows4.json]
"""
import bisect, json, os, struct, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'


def main():
    win = json.load(open(os.path.join(ROOT, 'symbols', 'unit_windows3.json')))
    fns = json.load(open(os.path.join(ROOT, 'symbols', 'functions.json')))
    out, G_ok, G_n, G_add = {}, 0, 0, 0
    for rel, info in win.items():
        base = info['base']
        blob = open(os.path.join(GAME, rel), 'rb').read()
        funcs = sorted(fns[rel]['functions'], key=lambda f: f['addr'])
        starts = [f['addr'] for f in funcs]
        known = {w['addr']: w['candidates'][0]
                 for w in info['windows'] if len(w['candidates']) == 1}
        lo, hi = ((0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99')
                  else (0, len(blob) & ~3))
        callers = defaultdict(list)
        for i in range(lo, hi - 4, 4):
            w = struct.unpack_from('<I', blob, i)[0]
            if (w >> 26) != 3:
                continue
            t = ((base + i) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
            k = bisect.bisect_right(starts, base + i) - 1
            if k >= 0 and starts[k] != t:
                callers[t].append(starts[k])

        # hold-out: hide a known function's label, recover from its callers
        ok = n = 0
        for a, u in known.items():
            cs = [known.get(c) for c in callers.get(a, [])]
            cs = [c for c in cs if c and c != u or c and c != u]
            allc = [known.get(c) for c in callers.get(a, []) if known.get(c)]
            if not allc:
                continue
            uniq = set(allc)
            if len(uniq) != 1:
                continue                       # callers disagree -> no claim
            n += 1; ok += (next(iter(uniq)) == u)

        added, neww = 0, []
        for w in info['windows']:
            if len(w['candidates']) == 1:
                neww.append(w); continue
            allc = [known.get(c) for c in callers.get(w['addr'], []) if known.get(c)]
            uniq = set(allc)
            if len(uniq) == 1:
                pick = next(iter(uniq))
                if not w['candidates'] or pick in w['candidates']:
                    neww.append({'addr': w['addr'], 'candidates': [pick],
                                 'src': 'callers'})
                    added += 1
                    continue
            neww.append(w)
        one = sum(1 for x in neww if len(x['candidates']) == 1)
        print(f'{rel}: hold-out {ok}/{n} = {ok/max(n,1):.1%}   +{added} resolved '
              f'-> {one}/{len(neww)} ({one/len(neww):.0%})')
        G_ok += ok; G_n += n; G_add += added
        out[rel] = {'base': base, 'order': info['order'], 'windows': neww}
    print(f'\ncaller-locality hold-out: {G_ok}/{G_n} = {G_ok/max(G_n,1):.1%}')
    print(f'newly resolved: +{G_add}')
    tot = sum(len(v['windows']) for v in out.values())
    one = sum(1 for v in out.values() for w in v['windows'] if len(w['candidates']) == 1)
    print(f'TOTAL {one}/{tot} ({one/tot:.0%})')
    if '--json' in sys.argv:
        p = os.path.join(ROOT, 'symbols', 'unit_windows4.json')
        json.dump(out, open(p, 'w'), indent=1)
        print(f'wrote {p}')


if __name__ == '__main__':
    main()
