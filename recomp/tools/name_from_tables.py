# -*- coding: utf-8 -*-
"""Name debug handlers from the label->handler tables.

The debug menus are tables pairing a label with the function that runs it.
The labels are prose, and they are in ENGLISH because this project translated
them, so they read as descriptions rather than identifiers:

    'Emotion Control' -> 0x01F2C310      'Debug Camera'      -> 0x01F215B8
    'Set funds'       -> 0x01F26CE8      'Bardiel VS Unit-01'-> 0x01F18838

Filtering matters. A table of asset filenames all pointing at one shared
handler ('kaiwa_anm00.ifl', 'kaiwa_anm01.ifl' ... -> the same address) says
nothing about that function, so any handler claimed by more than one label is
dropped, as is any label claimed by more than one handler.

    python3 name_from_tables.py [--apply]
"""
import json, os, re, struct, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'


def ident(s):
    s = re.sub(r'^\d+\s*[:.]?\s*', '', s.strip())         # strip a leading index
    s = re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_')
    if not s or s[0].isdigit():
        s = 'm_' + s
    return s[:48]


def main():
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    pairs = []
    for rel, info in syms.items():
        b = open(os.path.join(GAME, rel), 'rb').read()
        base = info['base']
        faddr = {f['addr'] for f in info['functions'] if f.get('region') != 'sdk'}

        def isstr(v):
            o = v - base
            if not (0 <= o < len(b)):
                return None
            e = b.find(b'\x00', o)
            if e < 0 or e - o < 3 or e - o > 40:
                return None
            r = b[o:e]
            return r.decode() if all(32 <= c < 127 for c in r) else None

        words = [struct.unpack_from('<I', b, i)[0] for i in range(0, (len(b) & ~3), 4)]
        seen = set()
        for stride in (2, 3, 4):
            for d in range(1, stride):
                i = 0
                while i < len(words) - stride:
                    s = isstr(words[i])
                    if s and words[i + d] in faddr:
                        j, rows = i, []
                        while j + d < len(words):
                            s2 = isstr(words[j])
                            if not (s2 and words[j + d] in faddr):
                                break
                            rows.append((s2, words[j + d])); j += stride
                        if len(rows) >= 4:
                            key = (i, stride, d)
                            if key not in seen:
                                seen.add(key)
                                for s2, a in rows:
                                    pairs.append((rel, a, s2))
                            i = j; continue
                    i += 1

    byfunc = {}
    for rel, a, s in pairs:
        byfunc.setdefault((rel, a), set()).add(s)
    bylabel = Counter(s for _, _, s in pairs)
    good = {}
    for (rel, a), labels in byfunc.items():
        if len(labels) != 1:
            continue                       # a shared handler names nothing
        lab = next(iter(labels))
        if sum(1 for k, v in byfunc.items() if lab in v) != 1:
            continue                       # label claimed by several handlers
        good[(rel, a)] = lab
    print(f'{len(pairs)} label/handler pairs -> {len(good)} unambiguous')

    # sanity check: do the names land in plausible units?
    ok = tot = 0
    idx = {(r, f['addr']): f for r, v in syms.items() for f in v['functions']}
    for (rel, a), lab in sorted(good.items())[:14]:
        f = idx.get((rel, a))
        print(f"   {rel.split('/')[-1]:14} 0x{a:08X}  {ident(lab):34} "
              f"[{(f['unit'] if f else None) or '?'}]")
    if '--apply' in sys.argv:
        n = 0
        for (rel, a), lab in good.items():
            f = idx.get((rel, a))
            if not f or f.get('name_source') in ('recovered', 'manual'):
                continue
            f['name'] = ident(lab); f['name_source'] = 'menu_label'
            f['menu_label'] = lab
            n += 1
        json.dump(syms, open(os.path.join(ROOT, 'symbols', 'symbols.json'), 'w'), indent=1)
        print(f'\napplied {n} names from menu labels')


if __name__ == '__main__':
    main()
