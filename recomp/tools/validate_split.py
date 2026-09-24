# -*- coding: utf-8 -*-
"""Hold-out test for the call-graph splitter.

There is no ground truth for a gap by construction, so the splitter cannot be
checked against one directly. But there IS ground truth either side of a gap:
functions pinned by a __FILE__ reference.

So: manufacture synthetic gaps out of pinned data. Take two adjacent units A
and B that both have pinned functions, blank the labels on A's last few and
B's first few, run the same scoring the splitter uses, and see whether it puts
the split back where it belongs. Everything else stays pinned, exactly as in
the real run.

Reported as accuracy per function, plus how often the split lands exactly right.
"""
import json, os, struct, sys, bisect
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
HOLD = 6                      # functions blanked either side of each seam


def call_edges(rel, base, starts):
    blob = open(os.path.join(GAME, rel), 'rb').read()
    lo, hi = (0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99') else (0, len(blob) & ~3)
    fset, edges = set(starts), []
    for i in range(lo, hi - 4, 4):
        w = struct.unpack_from('<I', blob, i)[0]
        if (w >> 26) != 3:
            continue
        tgt = ((base + i) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
        if tgt in fset:
            k = bisect.bisect_right(starts, base + i) - 1
            if k >= 0:
                edges.append((starts[k], tgt))
    return edges


def main():
    fns = json.load(open(os.path.join(ROOT, 'symbols', 'functions.json')))
    gt_ok = gt_n = seams = exact = 0
    for rel, info in fns.items():
        funcs = sorted(info['functions'], key=lambda f: f['addr'])
        starts = [f['addr'] for f in funcs]
        pinned = [f for f in funcs if f['certain']]
        if len(pinned) < 20:
            continue
        nbr = defaultdict(list)
        for a, b in call_edges(rel, info['base'], starts):
            nbr[a].append(b); nbr[b].append(a)
        truth = {f['addr']: (f['unit'] if f['certain'] else None) for f in funcs}

        # every adjacent pair of DIFFERENT units among the pinned functions
        for i in range(len(pinned) - 1):
            A, B = pinned[i]['unit'], pinned[i + 1]['unit']
            if A == B:
                continue
            lo_i = max(0, i - HOLD + 1)
            hi_i = min(len(pinned) - 1, i + HOLD)
            held = pinned[lo_i:hi_i + 1]
            if len(held) < 4:
                continue
            unit = dict(truth)
            for f in held:
                unit[f['addr']] = None            # blank them
            addrs = [f['addr'] for f in held]
            def aff(a, U):
                return sum(1 for n in nbr.get(a, []) if unit.get(n) == U)
            n = len(addrs)
            pre = [0] * (n + 1)
            for k, a in enumerate(addrs):
                pre[k + 1] = pre[k] + aff(a, A)
            suf = [0] * (n + 2)
            for k in range(n - 1, -1, -1):
                suf[k] = suf[k + 1] + aff(addrs[k], B)
            best_k, best_s = None, -1
            for k in range(n + 1):
                s = pre[k] + suf[k]
                if s > best_s:
                    best_s, best_k = s, k
            if best_s <= 0:
                continue
            seams += 1
            true_k = sum(1 for f in held if truth[f['addr']] == A)
            exact += (best_k == true_k)
            for k, f in enumerate(held):
                pred = A if k < best_k else B
                gt_n += 1
                gt_ok += (pred == truth[f['addr']])
        print(f'{rel}: tested so far -> {seams} seams')
    print(f'\nHOLD-OUT RESULT over {seams} synthetic seams:')
    print(f'   per-function accuracy : {gt_ok}/{gt_n} = {gt_ok/max(gt_n,1):.1%}')
    print(f'   split placed exactly  : {exact}/{seams} = {exact/max(seams,1):.1%}')
    print(f'   (a coin flip would be ~50% per function)')


if __name__ == '__main__':
    main()
