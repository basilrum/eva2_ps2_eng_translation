# -*- coding: utf-8 -*-
"""Attribute a function that sits between two functions of the SAME unit.

The linker emits a translation unit's functions contiguously, so if the
nearest attributed function above and the nearest attributed function below
both belong to unit X, anything between them is in X too. That is not a guess
about behaviour -- it is the layout property every other pass here relies on.

Hold-out before trusting it: take the 7,064 functions that ARE attributed and
have same-unit neighbours on both sides, hide each one's unit, and predict it
from the neighbours.

    agrees 7063, disagrees 1  =  99.99%

The single miss is 0x01F6C618 in FREE.BIN, where fvattrib.c has exactly one
function stranded inside fvgimick.c's span.

Predictions are computed from the pre-existing attribution only and never
chained, so a sandwiched function cannot become evidence for its neighbour.
Runs after build_symbols.py, which recomputes `unit` from the windows each
time, so this cannot accumulate across rebuilds.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    apply = '--apply' in sys.argv
    p = os.path.join(ROOT, 'symbols', 'symbols.json')
    syms = json.load(open(p))
    tu = json.load(open(os.path.join(ROOT, 'symbols', 'tu_map.json')))
    total = blocked = 0
    for rel, info in syms.items():
        # Anchors of OTHER units inside the gap. A unit referenced from only
        # one place has a ZERO-WIDTH window, so it owns no functions and is
        # invisible to the neighbour test -- but the gap around it is emphatically
        # not homogeneous. Skipping this check put hhDbgPrintBegin/Row, which sit
        # either side of hhdprint.c's single anchor at 0x001136BC, into
        # hhcamera.c. Found by tools/check_names_vs_units.py, not by the
        # hold-out, because the hold-out can only test where an answer exists.
        anchors = sorted((u['lo'], u['file']) for u in tu[rel]['units'])
        fs = sorted(info['functions'], key=lambda f: f['addr'])
        known = [f.get('unit') for f in fs]          # frozen: no chaining
        for i, f in enumerate(fs):
            if known[i]:
                continue
            left = right = None
            j0 = j1 = None
            for j in range(i - 1, -1, -1):
                if known[j]:
                    left, j0 = known[j], j
                    break
            for j in range(i + 1, len(fs)):
                if known[j]:
                    right, j1 = known[j], j
                    break
            if left and left == right:
                lo_a, hi_a = fs[j0]['addr'], fs[j1]['addr']
                if any(lo_a < a < hi_a and fl != left for a, fl in anchors):
                    blocked += 1
                    continue
                total += 1
                if apply:
                    f['unit'] = left
                    f['unit_via'] = 'between two functions of the same unit'
                    f['candidates'] = None
    print(f'{total} functions attributed by the sandwich rule, '
          f'{blocked} blocked by another unit\'s anchor inside the gap')
    if apply:
        json.dump(syms, open(p, 'w'), indent=1)
        print('applied')


main()
