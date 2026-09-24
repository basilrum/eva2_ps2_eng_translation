# -*- coding: utf-8 -*-
"""Apply manual_names.json to symbols.json.

Kept separate from the recovered names: those are literal developer names
lifted out of the binary, these are descriptive and were chosen here after
reading the disassembly. Each carries its justification so a later reader can
disagree with it.
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
man = json.load(open(os.path.join(ROOT, 'symbols', 'manual_names.json')))
syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
n = 0
for rel, entries in man.items():
    if rel.startswith('_') or rel not in syms:
        continue
    idx = {f['addr']: f for f in syms[rel]['functions']}
    for a, e in entries.items():
        f = idx.get(int(a, 16))
        if f is None:
            print(f'   {a} not a known function start -- skipped ({e["name"]})')
            continue
        f['name'] = e['name']; f['name_source'] = 'manual'; f['why'] = e['why']
        n += 1
        print(f'   {a}  {e["name"]}')
json.dump(syms, open(os.path.join(ROOT, 'symbols', 'symbols.json'), 'w'), indent=1)
print(f'applied {n} manual names')
