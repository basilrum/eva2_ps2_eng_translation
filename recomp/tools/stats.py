# -*- coding: utf-8 -*-
"""Print the map's size honestly, splitting game code from the SDK.

Attribution means "which game .c file is this in", so Sony SDK and libc
functions can never be attributed and must not sit in the denominator. They
are 1,308 of the main ELF's functions -- big enough that including them turned
a real 80.6% into a reported 70.9%.

The other trap is the numerator's history: `func_scan` used to miss tail-call
boundaries, so an older "77%" was measured against a function list missing
about a tenth of the program. Always print total, SDK, game and named
together; a percentage on its own has been misleading twice.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))

T = G = A = N = R = 0
rows = []
for rel, info in syms.items():
    f = info['functions']
    t = len(f)
    lib = sum(1 for x in f if x.get('library'))
    g = t - lib
    a = sum(1 for x in f if x.get('unit'))
    n = sum(1 for x in f if x.get('name_source'))
    r = sum(1 for x in f if x.get('confidence') == 'reached')
    rows.append((rel, t, lib, g, a, n, r))
    T += t; G += g; A += a; N += n; R += r

units = sum(len(i['units']) for i in
            json.load(open(os.path.join(ROOT, 'symbols', 'tu_map.json'))).values())

print(f'   {"binary":18} {"total":>6} {"SDK":>6} {"game":>6} {"attributed":>14} '
      f'{"named":>6} {"reached":>8}')
for rel, t, lib, g, a, n, r in rows:
    pct = f'({100*a/g:5.1f}%)' if g else '( n/a )'
    print(f'   {rel:18} {t:6} {lib:6} {g:6} {a:6} {pct} {n:6} {r:8}')
print(f'   {"TOTAL":18} {T:6} {T-G:6} {G:6} {A:6} ({100*A/G:5.1f}%) {N:6} {R:8}')
print(f'   {units} translation units bounded')
