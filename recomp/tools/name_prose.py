# -*- coding: utf-8 -*-
"""Name functions from a solo PROSE string (a label, not an identifier).

name_from_tables.py only caught labels sitting in a label/handler table, and
name_solo_strings.py only accepted identifier-shaped strings. That leaves the
many functions that reference one descriptive label directly -- most of them
debug-menu handlers whose labels this project already translated into English.

Rejected: assert expressions, printf formats, asset paths, anything a second
function also references, and strings too short or too generic to mean
anything.

    python3 name_prose.py [--apply]
"""
import bisect, json, os, re, struct, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from addrloads import loads as _loads

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
BAD_CHARS = set('=<>!&|%\\/')
DATA_EXT = ('.har', '.hpt', '.pss', '.ifl', '.zpt', '.bin', '.dat', '.evs',
            '.c', '.h', '.img', '.irx')
GENERIC = {'none', 'normal', 'test', 'debug', 'exit', 'start', 'end', 'on', 'off',
           'yes', 'no', 'error', 'ok', 'dummy', 'sample', 'not implemented yet.'}


def ident(s):
    s = re.sub(r'^\d+\s*[:.]?\s*', '', s.strip())
    s = re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_')
    if not s or s[0].isdigit():
        s = 'm_' + s
    return s[:44]


def usable(s):
    if len(s) < 6 or len(s) > 40:
        return False
    if any(c in BAD_CHARS for c in s):
        return False
    if s.lower().endswith(DATA_EXT):
        return False
    if s.strip().lower() in GENERIC:
        return False
    if not re.search(r'[A-Za-z]{3}', s):
        return False
    # a label reads like words; reject things that are mostly punctuation/digits
    letters = sum(c.isalpha() or c == ' ' for c in s)
    return letters / len(s) > 0.75


def main():
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    picks = []
    for rel, info in syms.items():
        b = open(os.path.join(GAME, rel), 'rb').read()
        base = info['base']
        funcs = sorted(info['functions'], key=lambda f: f['addr'])
        starts = [f['addr'] for f in funcs]
        byaddr = {f['addr']: f for f in funcs}

        def cstr(o):
            e = b.find(b'\x00', o)
            if e < 0 or e - o < 4 or e - o > 44:
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
            if not s or not usable(s):
                continue
            k = bisect.bisect_right(starts, base + i) - 1
            if k >= 0:
                refs[starts[k]].add(s); users[s].add(starts[k])

        for a, v in refs.items():
            if len(v) != 1:
                continue
            s = next(iter(v))
            if len(users[s]) != 1:
                continue
            f = byaddr.get(a)
            if not f or f.get('name_source') or f.get('region') == 'sdk':
                continue
            picks.append((rel, a, s, f['unit']))

    print(f'{len(picks)} functions named by a solo prose label\n')
    for rel, a, s, u in sorted(picks)[:20]:
        print(f"   {rel.split('/')[-1]:14} 0x{a:08X}  {ident(s):36} [{u or '?'}]")
    if len(picks) > 20:
        print(f'   ... and {len(picks)-20} more')
    if '--apply' in sys.argv:
        idx = {(r, f['addr']): f for r, v in syms.items() for f in v['functions']}
        for rel, a, s, u in picks:
            f = idx[(rel, a)]
            f['name'] = ident(s); f['name_source'] = 'prose_label'; f['menu_label'] = s
        json.dump(syms, open(os.path.join(ROOT, 'symbols', 'symbols.json'), 'w'), indent=1)
        print(f'\napplied {len(picks)} names')


if __name__ == '__main__':
    main()
