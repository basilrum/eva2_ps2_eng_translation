# -*- coding: utf-8 -*-
"""Recover real function names from name-shaped strings the code references.

Some functions reference a string that is an identifier rather than a message
-- `hhMemFree`, `hhFileSearchFILEMEM`, `btMissionTest`. These are the names the
developers used, left behind in debug traces and dispatch tables.

A function referencing such a string is not proof the string is ITS name: it
could be naming a callee. So each candidate is checked against the unit the
function was independently attributed to -- `hhMemFree` should live in
`hhmem.c`, `btIm319Test` in a `bt*.c`. Agreement across an independent signal
is what promotes a candidate to a name.

Also mined: `assert(p && "func_name: message")`, which states the name outright.

    python3 name_funcs.py [--apply]
"""
import bisect, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
ID = re.compile(rb'[A-Za-z_][A-Za-z0-9_]{5,48}\x00')
ASSERT_NAME = re.compile(r'"\s*([A-Za-z_][A-Za-z0-9_]{3,60})\s*:')
import struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from addrloads import loads as _loads


def stem(u):
    return os.path.basename(u).replace('.c', '').replace('.cpp', '').lower()


def consistent(name, unit):
    """Does the name's prefix agree with the file it was attributed to?"""
    s = stem(unit)
    n = name.lower().lstrip('_')
    # Names carrying a number must match it: im0215_* belongs in im0215.c, not
    # im0096.c. A loose prefix test passed that and it was wrong.
    dn = re.findall(r'\d{3,4}', n)
    ds = re.findall(r'\d{3,4}', s)
    if dn and ds and dn[0] != ds[0]:
        return False
    if dn and not ds:
        return False
    if n.startswith(s) or s.startswith(n[:6]):
        return True
    for k in range(len(s), 2, -1):
        if n.startswith(s[:k]):
            return True
    return False


def main():
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    asr = json.load(open(os.path.join(ROOT, 'symbols', 'asserts.json')))
    applied = 0
    rows = []
    for rel, info in syms.items():
        blob = open(os.path.join(GAME, rel), 'rb').read()
        base = info['base']
        funcs = sorted(info['functions'], key=lambda f: f['addr'])
        starts = [f['addr'] for f in funcs]
        byaddr = {f['addr']: f for f in funcs}
        names = {}
        for m in ID.finditer(blob):
            s = m.start()
            if s and blob[s - 1] != 0:
                continue
            t = m.group()[:-1].decode()
            if '_' in t or re.match(r'^(hh|bt|fc|fm|fv|gm|cp|gs)[A-Z]', t):
                names[s + base] = t
        lo, hi = (0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99') else (0, len(blob) & ~3)
        hits = {}
        for i, a in _loads(blob, lo, hi):
            if a in names:
                k = bisect.bisect_right(starts, base + i) - 1
                if k >= 0:
                    hits.setdefault(starts[k], set()).add(names[a])
        # assert-embedded names are stated outright, so they win
        hard = {}
        for st in asr.get(rel, []):
            m = ASSERT_NAME.search(st['expr'] or '')
            if m and st['func'] is not None:
                hard[st['func']] = m.group(1)

        for a, cands in hits.items():
            if len(cands) != 1:
                continue
            n = next(iter(cands))
            f = byaddr.get(a)
            if not f:
                continue
            good = f['unit'] and consistent(n, f['unit'])
            rows.append((rel, a, n, f['unit'], 'assert' if a in hard else 'string',
                         bool(good)))
        for a, n in hard.items():
            f = byaddr.get(a)
            if f and not any(r[1] == a for r in rows):
                rows.append((rel, a, n, f['unit'],
                             'assert', bool(f['unit'] and consistent(n, f['unit']))))

    ok = [r for r in rows if r[5]]
    # A name referenced from two functions cannot name both; the reference is
    # ambiguous, so drop it rather than pick one.
    from collections import Counter
    dup = {n for n, c in Counter(r[2] for r in ok).items() if c > 1}
    if dup:
        print(f'dropping {len(dup)} name(s) claimed by more than one function: '
              f'{", ".join(sorted(dup))}\n')
    ok = [r for r in ok if r[2] not in dup]
    print(f'{len(rows)} name candidates, {len(ok)} consistent with the attributed '
          f'unit ({len(ok)/max(len(rows),1):.0%})\n')
    for rel, a, n, u, src, g in sorted(ok)[:30]:
        print(f'   0x{a:08X}  {n:34} {u or "?":24} [{src}]')
    if len(ok) > 30:
        print(f'   ... and {len(ok)-30} more')

    if '--apply' in sys.argv:
        idx = {(r[0], r[1]): r[2] for r in ok}
        for rel, info in syms.items():
            for f in info['functions']:
                nm = idx.get((rel, f['addr']))
                if nm:
                    f['name'] = nm
                    f['name_source'] = 'recovered'
                    applied += 1
        json.dump(syms, open(os.path.join(ROOT, 'symbols', 'symbols.json'), 'w'), indent=1)
        print(f'\napplied {applied} recovered names to symbols.json')


if __name__ == '__main__':
    main()
