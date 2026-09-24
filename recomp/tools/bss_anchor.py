# -*- coding: utf-8 -*-
"""Extend attribution using .bss / .sbss references.

.bss holds file-scope statics, and like everything else it is laid out in link
order -- but it lives past the end of the file image, so it has no literals in
it to anchor against and the earlier passes discarded every reference to it.
There are 938 such references in the ELF, more than twice the .data count.

Same bootstrap as data_anchor.py: functions already anchored tell us which
.bss offsets belong to which unit, and those offsets then anchor further
functions. Hold-out tested by hiding each anchored function's label and seeing
whether its .bss references alone recover it.

    python3 bss_anchor.py [--json symbols/unit_windows3.json]
"""
import bisect, json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from addrloads import loads as _loads
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'


def main():
    win = json.load(open(os.path.join(ROOT, 'symbols', 'unit_windows2.json')))
    fns = json.load(open(os.path.join(ROOT, 'symbols', 'functions.json')))
    out, G_ok, G_n, G_add = {}, 0, 0, 0
    for rel, info in win.items():
        base = info['base']
        blob = open(os.path.join(GAME, rel), 'rb').read()
        funcs = sorted(fns[rel]['functions'], key=lambda f: f['addr'])
        starts = [f['addr'] for f in funcs]
        anchored = {w['addr']: w['candidates'][0]
                    for w in info['windows'] if w['src'] in ('anchor', 'data')}
        lo, hi = ((0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99')
                  else (0, len(blob) & ~3))
        # references PAST the end of the image are .bss/.sbss
        end = base + len(blob)
        refs = defaultdict(list)
        for i, a in _loads(blob, lo, hi):
            if end <= a < end + 0x400000:
                k = bisect.bisect_right(starts, base + i) - 1
                if k >= 0:
                    refs[starts[k]].append(a)

        owner = defaultdict(Counter)
        for a, offs in refs.items():
            u = anchored.get(a)
            if u:
                for o in offs:
                    owner[o][u] += 1
        omap = {}
        for o, c in owner.items():
            m = c.most_common()
            if len(m) == 1 or m[0][1] > m[1][1]:
                omap[o] = m[0][0]

        ok = n = 0
        for a, u in anchored.items():
            offs = refs.get(a)
            if not offs:
                continue
            votes = Counter()
            for o in offs:
                c = Counter(owner.get(o, {})); c[u] -= 1; c = +c
                if c:
                    votes[c.most_common(1)[0][0]] += 1
            if not votes:
                continue
            m = votes.most_common()
            if len(m) > 1 and m[0][1] == m[1][1]:
                continue
            n += 1; ok += (m[0][0] == u)

        added, neww = 0, []
        for w in info['windows']:
            if len(w['candidates']) == 1:
                neww.append(w); continue
            offs = refs.get(w['addr'])
            pick = None
            if offs:
                votes = Counter(omap[o] for o in offs if o in omap)
                if votes:
                    m = votes.most_common()
                    if (len(m) == 1 or m[0][1] > m[1][1]) and m[0][0] in w['candidates']:
                        pick = m[0][0]
            if pick:
                neww.append({'addr': w['addr'], 'candidates': [pick], 'src': 'bss'})
                added += 1
            else:
                neww.append(w)
        one = sum(1 for w in neww if len(w['candidates']) == 1)
        print(f'{rel}: {len(refs)} functions touch .bss, {len(omap)} offsets mapped')
        print(f'   hold-out {ok}/{n} = {ok/max(n,1):.1%}   +{added} newly resolved '
              f'-> {one}/{len(neww)} on one unit ({one/len(neww):.0%})')
        G_ok += ok; G_n += n; G_add += added
        out[rel] = {'base': base, 'order': info['order'], 'windows': neww}
    print(f'\n.bss hold-out overall: {G_ok}/{G_n} = {G_ok/max(G_n,1):.1%}')
    print(f'newly resolved: +{G_add}')
    tot = sum(len(v['windows']) for v in out.values())
    one = sum(1 for v in out.values() for w in v['windows'] if len(w['candidates']) == 1)
    print(f'TOTAL {one}/{tot} on exactly one .c file ({one/tot:.0%})')
    if '--json' in sys.argv:
        p = os.path.join(ROOT, 'symbols', 'unit_windows3.json')
        json.dump(out, open(p, 'w'), indent=1)
        print(f'wrote {p}')


if __name__ == '__main__':
    main()
