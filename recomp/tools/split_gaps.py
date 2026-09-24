# -*- coding: utf-8 -*-
"""Resolve the `a.c|b.c` functions using the call graph.

A function in the gap between unit A and unit B could belong to either. But
the linker emits translation units CONTIGUOUSLY, so the gap is not a free-for-
all: there is a single split point, and every function before it belongs to A,
every function after it to B. That turns thousands of independent guesses into
one choice per gap, which is a far easier thing to get right.

The choice is scored on the call graph, because functions call within their own
translation unit much more than across one. For each candidate split k:

    score(k) = calls between f[0..k]   and functions already pinned to A
             + calls between f[k+1..]  and functions already pinned to B

and the best-scoring k wins. Gaps where no call evidence exists either way are
left unresolved and reported as such rather than silently assigned.

Two passes: functions resolved in pass 1 become anchors for pass 2.

    python3 split_gaps.py [--json symbols/functions_split.json]
"""
import json, os, struct, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'


def call_edges(rel, base, funcs):
    """(caller_addr, callee_addr) for every jal whose target is a function."""
    blob = open(os.path.join(GAME, rel), 'rb').read()
    lo, hi = (0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99') else (0, len(blob) & ~3)
    starts = [f['addr'] for f in funcs]
    import bisect
    edges = []
    fset = set(starts)
    for i in range(lo, hi - 4, 4):
        w = struct.unpack_from('<I', blob, i)[0]
        if (w >> 26) != 3:
            continue
        tgt = ((base + i) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
        if tgt not in fset:
            continue
        k = bisect.bisect_right(starts, base + i) - 1
        if k >= 0:
            edges.append((starts[k], tgt))
    return edges


def main():
    tu = json.load(open(os.path.join(ROOT, 'symbols', 'tu_map.json')))
    fns = json.load(open(os.path.join(ROOT, 'symbols', 'functions.json')))
    out = {}
    tot_res = tot_amb = tot_unres = 0
    for rel, info in fns.items():
        funcs = info['functions']
        base = info['base']
        if not any('|' in (f['unit'] or '') for f in funcs):
            out[rel] = info
            continue
        edges = call_edges(rel, base, funcs)
        nbr = defaultdict(list)
        for a, b in edges:
            nbr[a].append(b); nbr[b].append(a)
        unit = {f['addr']: (f['unit'] if f['certain'] else None) for f in funcs}
        byaddr = {f['addr']: f for f in funcs}

        # group the ambiguous ones by which gap they sit in
        gaps = defaultdict(list)
        for f in funcs:
            if f['unit'] and '|' in f['unit']:
                gaps[f['unit']].append(f['addr'])
        for g in gaps:
            gaps[g].sort()

        resolved = unresolved = 0
        for _pass in range(2):
            for pair, addrs in gaps.items():
                A, B = pair.split('|')
                def aff(a, U):
                    return sum(1 for n in nbr.get(a, []) if unit.get(n) == U)
                n = len(addrs)
                pre = [0] * (n + 1)
                for i, a in enumerate(addrs):
                    pre[i + 1] = pre[i] + aff(a, A)
                suf = [0] * (n + 2)
                for i in range(n - 1, -1, -1):
                    suf[i] = suf[i + 1] + aff(addrs[i], B)
                best_k, best_s = None, -1
                for k in range(n + 1):
                    s = pre[k] + suf[k]
                    if s > best_s:
                        best_s, best_k = s, k
                if best_s <= 0:
                    continue                      # no evidence -- leave it alone
                for i, a in enumerate(addrs):
                    unit[a] = A if i < best_k else B

        for f in funcs:
            if f['unit'] and '|' in f['unit']:
                u = unit.get(f['addr'])
                if u and '|' not in u:
                    f['unit'] = u; f['certain'] = False; f['resolved'] = True
                    resolved += 1
                else:
                    unresolved += 1
        amb = sum(1 for f in funcs if f.get('resolved') or (f['unit'] and '|' in f['unit']))
        print(f'{rel}: {resolved} of {amb} ambiguous functions resolved '
              f'({resolved/max(amb,1):.0%}), {unresolved} left with no call evidence')
        tot_res += resolved; tot_amb += amb; tot_unres += unresolved
        out[rel] = info
    print(f'\nTOTAL {tot_res} of {tot_amb} resolved ({tot_res/max(tot_amb,1):.0%}), '
          f'{tot_unres} still ambiguous')
    pinned = sum(1 for v in out.values() for f in v['functions'] if f['certain'])
    single = sum(1 for v in out.values() for f in v['functions']
                 if f['unit'] and '|' not in f['unit'])
    total = sum(len(v['functions']) for v in out.values())
    print(f'functions attributed to exactly one .c file: {single}/{total} '
          f'({single/total:.0%})   [{pinned} of them pinned by a __FILE__ ref]')
    if '--json' in sys.argv:
        d = os.path.join(ROOT, 'symbols', 'functions_split.json')
        json.dump(out, open(d, 'w'), indent=1)
        print(f'wrote {d}')


if __name__ == '__main__':
    main()
