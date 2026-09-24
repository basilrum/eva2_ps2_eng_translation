# -*- coding: utf-8 -*-
"""Merge the passes into one symbol map, plus a plain-text export.

Combines:
  functions_pruned.json   reachability tiers
  unit_windows2.json      which .c file each function belongs to

Names are auto-generated as <unit>_<addr> where the unit is known, so they are
stable and greppable without pretending to be real names. Anything still
ambiguous keeps the candidate list rather than picking one.

    python3 build_symbols.py
"""
import json, os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def stem(u):
    return os.path.basename(u).replace('.c', '').replace('.cpp', '').replace('-', '_')


# every source that a naming pass in rebuild.sh produces from scratch
REGENERATED = {'manual', 'recovered', 'trace_string', 'menu_label',
               'solo_string', 'prose_label', 'syscall_stub'}


def main():
    dropped = {}
    pruned = json.load(open(os.path.join(ROOT, 'symbols', 'functions_pruned.json')))
    wf = 'unit_windows5.json'
    if not os.path.exists(os.path.join(ROOT, 'symbols', wf)):
        wf = 'unit_windows2.json'
    wins = json.load(open(os.path.join(ROOT, 'symbols', wf)))
    # keep names and regions already established -- rebuilding the map must not
    # silently discard recovered/manual names or the SDK classification
    prev = {}
    pp = os.path.join(ROOT, 'symbols', 'symbols.json')
    if os.path.exists(pp):
        for r, v in json.load(open(pp)).items():
            for f in v['functions']:
                prev[(r, f['addr'])] = f
    out, lines = {}, []
    tot = named = reached = 0
    for rel, info in pruned.items():
        w = {x['addr']: x for x in wins.get(rel, {}).get('windows', [])}
        rows = []
        for f in sorted(info['functions'], key=lambda f: f['addr']):
            win = w.get(f['addr'])
            cand = win['candidates'] if win else []
            unit = cand[0] if len(cand) == 1 else None
            name = f'{stem(unit)}_{f["addr"]:08X}' if unit else f'func_{f["addr"]:08X}'
            row = {'addr': f['addr'], 'size': f.get('size'), 'name': name,
                   'unit': unit, 'candidates': None if unit else cand,
                   'confidence': f['confidence'],
                   'called': f['called'], 'ptr_ref': f.get('ptr_ref', False),
                   'addr_taken': f.get('addr_taken', False)}
            old = prev.get((rel, f['addr']))
            if old:
                # Names from the passes rebuild.sh runs are DROPPED here and
                # regenerated below, in strength order. Carrying them over
                # instead would freeze whatever pass happened to get there
                # first: a stronger pass added later could never take a name
                # off a weaker one, and 4 prose_label names did exactly that
                # to name_trace_strings. Anything from a source rebuild.sh
                # does NOT regenerate is still preserved, so hand work made
                # outside the pipeline is not lost.
                src = old.get('name_source')
                if src and src not in REGENERATED:
                    row['name'] = old['name']
                    row['name_source'] = src
                    if 'why' in old:
                        row['why'] = old['why']
                elif src:
                    dropped[src] = dropped.get(src, 0) + 1
                for k in ('region', 'library', 'menu_label', 'unit_source'):
                    if k in old:
                        row[k] = old[k]
            rows.append(row)
            tot += 1; named += bool(unit); reached += f['confidence'] == 'reached'
            lines.append(f"{f['addr']:08X} {name} {rel} "
                         f"{unit or '|'.join(cand) or '?'} {f['confidence']}")
        out[rel] = {'base': info['base'], 'functions': rows}
    p = os.path.join(ROOT, 'symbols', 'symbols.json')
    json.dump(out, open(p, 'w'), indent=1)
    t = os.path.join(ROOT, 'symbols', 'symbols.txt')
    open(t, 'w').write('\n'.join(lines) + '\n')
    print(f'{tot} functions')
    print(f'   {reached} reached (trustworthy), {tot-reached} unreferenced (flagged)')
    print(f'   {named} assigned to exactly one .c file ({named/tot:.0%})')
    per = Counter(r['unit'] for v in out.values() for r in v['functions'] if r['unit'])
    print(f'   {len(per)} distinct units represented; biggest: '
          + ', '.join(f'{stem(k)} {v}' for k, v in per.most_common(6)))
    if dropped:
        print('dropped for regeneration: ' +
              ', '.join(f'{k} {v}' for k, v in sorted(dropped.items())))
    print(f'wrote {p}\nwrote {t}')


if __name__ == '__main__':
    main()
