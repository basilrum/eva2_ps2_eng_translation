# -*- coding: utf-8 -*-
"""Find {name string, function pointer} tables.

Dispatch and debug-menu tables pair a label with a handler. Where the label is
an identifier rather than prose, the table names the handler outright -- and
one table can name dozens of functions at once, which is far better yield than
picking them off individually.

The scan looks for a word pointing at an identifier-shaped string within a
short window of a word pointing at a known function entry, then requires the
same (name_slot, func_slot) stride to repeat at least three times. A single
coincidental pair proves nothing; a repeating stride is a table.

    python3 find_tables.py [--json symbols/tables.json]
"""
import json, os, re, struct, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
ID = re.compile(rb'[A-Za-z_][A-Za-z0-9_]{3,48}\x00')


def main():
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    out, total = {}, 0
    for rel, info in syms.items():
        blob = open(os.path.join(GAME, rel), 'rb').read()
        base = info['base']
        faddr = {f['addr'] for f in info['functions']}
        names = {}
        for m in ID.finditer(blob):
            s = m.start()
            if s and blob[s - 1] != 0:
                continue
            names[s + base] = m.group()[:-1].decode()

        words = [struct.unpack_from('<I', blob, i)[0] for i in range(0, (len(blob) & ~3), 4)]
        isname = [w in names for w in words]
        isfunc = [w in faddr for w in words]

        # for each stride, collect runs where slot i is a name and i+d a function
        found = []
        for stride in (2, 3, 4, 5, 6, 8):
            for d in range(1, stride):
                i = 0
                while i < len(words) - stride:
                    if isname[i] and isfunc[i + d]:
                        j, rows = i, []
                        while (j + d < len(words) and isname[j] and isfunc[j + d]):
                            rows.append((words[j], words[j + d]))
                            j += stride
                        if len(rows) >= 3:
                            found.append({'at': i * 4, 'stride': stride, 'delta': d,
                                          'rows': [(names[n], f) for n, f in rows]})
                            i = j
                            continue
                    i += 1
        # keep the largest non-overlapping tables
        found.sort(key=lambda t: -len(t['rows']))
        used, keep = set(), []
        for t in found:
            span = range(t['at'], t['at'] + len(t['rows']) * t['stride'] * 4, 4)
            if any(x in used for x in span):
                continue
            used.update(span)
            keep.append(t)
        n = sum(len(t['rows']) for t in keep)
        print(f'{rel}: {len(keep)} tables, {n} name->function pairs')
        for t in keep[:3]:
            print(f'    at 0x{t["at"]:06X} stride {t["stride"]} x{len(t["rows"])}: '
                  + ', '.join(r[0] for r in t['rows'][:4]) + ' ...')
        out[rel] = keep
        total += n
    print(f'\nTOTAL {total} name->function pairs from tables')
    if '--json' in sys.argv:
        p = os.path.join(ROOT, 'symbols', 'tables.json')
        json.dump(out, open(p, 'w'), indent=1)
        print(f'wrote {p}')


if __name__ == '__main__':
    main()
