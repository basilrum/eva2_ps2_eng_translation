# -*- coding: utf-8 -*-
"""Name functions that reference exactly ONE identifier-shaped string.

Distinct from name_funcs.py, which required the name's prefix to match the
numbered filename it was attributed to. That rejected things like
`imLookDouble` sitting in `../im/im0501.c`: the family prefix agrees (`im`)
but the digits do not, and they were never going to.

What gets rejected here instead:
  * assert expressions        contain == < > && || !
  * asset paths               contain / or a known data extension
  * prose                     contains a space
  * anything already named
  * a string referenced by more than one function -- it cannot name both

    python3 name_solo_strings.py [--apply]
"""
import bisect, json, os, re, struct, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from addrloads import loads as _loads

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{4,46}$')
DATA_EXT = ('.har', '.hpt', '.pss', '.ifl', '.zpt', '.bin', '.dat', '.evs', '.c')


def family(name, unit):
    """Do the name and the file agree on their FAMILY prefix?

    Numbered files (im0501.c) never match a name's digits, so compare the
    leading alphabetic run instead: imLookDouble / im0501.c -> both 'im'.
    """
    if not unit:
        return False
    stem = os.path.basename(unit).rsplit('.', 1)[0].lower()
    n = name.lower().lstrip('_')
    fs = re.match(r'^[a-z]+', stem)
    fn = re.match(r'^[a-z]+', n)
    if not fs or not fn:
        return False
    a, b = fs.group(), fn.group()
    if n.startswith(stem) or stem.startswith(n[:6]):
        return True
    return len(a) >= 2 and len(b) >= 2 and (a.startswith(b[:2]) or b.startswith(a[:2])) \
        and abs(len(a) - len(b)) <= 8 and (a[:2] == b[:2])


def main():
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    picks = []
    for rel, info in syms.items():
        b = open(os.path.join(GAME, rel), 'rb').read()
        base = info['base']
        funcs = sorted(info['functions'], key=lambda f: f['addr'])
        starts = [f['addr'] for f in funcs]
        byaddr = {f['addr']: f for f in funcs}

        def cstr(o, lim=52):
            e = b.find(b'\x00', o)
            if e < 0 or e - o < 5 or e - o > lim:
                return None
            r = b[o:e]
            return r.decode() if all(32 <= c < 127 for c in r) else None

        refs, users = defaultdict(set), defaultdict(set)
        lo, hi = ((0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99')
                  else (0, len(b) & ~3))
        for i, a in _loads(b, lo, hi):
            o = a - base
            if not (0 <= o < len(b)):
                continue
            s = cstr(o)
            if not s or not IDENT.match(s):
                continue
            if s.lower().endswith(DATA_EXT) or '/' in s:
                continue
            k = bisect.bisect_right(starts, base + i) - 1
            if k >= 0:
                refs[starts[k]].add(s); users[s].add(starts[k])

        for a, v in refs.items():
            if len(v) != 1:
                continue
            s = next(iter(v))
            if len(users[s]) != 1:
                continue                     # names two functions -> names neither
            f = byaddr.get(a)
            if not f or f.get('name_source') or f.get('region') == 'sdk':
                continue
            if family(s, f['unit']):
                picks.append((rel, a, s, f['unit']))

    print(f'{len(picks)} functions named by a solo identifier string\n')
    for rel, a, s, u in sorted(picks)[:22]:
        print(f"   {rel.split('/')[-1]:14} 0x{a:08X}  {s:28} [{u}]")
    if len(picks) > 22:
        print(f'   ... and {len(picks)-22} more')
    if '--apply' in sys.argv:
        idx = {(r, f['addr']): f for r, v in syms.items() for f in v['functions']}
        for rel, a, s, u in picks:
            f = idx[(rel, a)]
            f['name'] = s; f['name_source'] = 'solo_string'
        json.dump(syms, open(os.path.join(ROOT, 'symbols', 'symbols.json'), 'w'), indent=1)
        print(f'\napplied {len(picks)} names')


if __name__ == '__main__':
    main()
