# -*- coding: utf-8 -*-
"""Validate the map using assert LINE NUMBERS.

The compiler emits a file's functions in source order, so within one .c file
the assert line numbers must rise with the address. That is a constraint the
attribution never used, which makes it a genuine test rather than a restatement.

A function whose line number breaks the sequence is either misattributed, or
its assert was mis-associated by the register-window heuristic in asserts.py.
Either way it is worth flagging.

    python3 check_lines.py
"""
import json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    asr = json.load(open(os.path.join(ROOT, 'symbols', 'asserts.json')))
    tot_pairs = tot_ok = 0
    bad_units = []
    for rel, sites in asr.items():
        byfile = defaultdict(dict)                 # file -> {func_addr: min line}
        for s in sites:
            if s['func'] is None or s['line'] is None:
                continue
            d = byfile[s['file']]
            d[s['func']] = min(d.get(s['func'], 1 << 30), s['line'])
        for fl, d in byfile.items():
            if len(d) < 3:
                continue
            seq = [ln for _, ln in sorted(d.items())]     # ordered by address
            pairs = ok = 0
            for i in range(len(seq)):
                for j in range(i + 1, len(seq)):
                    pairs += 1
                    ok += seq[i] <= seq[j]
            tot_pairs += pairs; tot_ok += ok
            if ok < pairs:
                bad_units.append((pairs - ok, pairs, fl, rel, len(d)))
    print(f'assert line order vs address order, within each .c file:')
    print(f'   {tot_ok}/{tot_pairs} ordered pairs agree = {tot_ok/tot_pairs:.1%}')
    print(f'   (random ordering would be ~50%)\n')
    bad_units.sort(reverse=True)
    print(f'{len(bad_units)} files show at least one inversion:')
    for inv, pairs, fl, rel, n in bad_units[:12]:
        print(f'   {inv:4}/{pairs:4} inversions  {fl:26} {rel:16} ({n} functions)')


if __name__ == '__main__':
    main()
