# -*- coding: utf-8 -*-
"""Assemble the naming evidence for each function.

Names are not guessed here. What is collected is everything the binary itself
says about a function, so a name can be justified rather than invented:

  unit       which .c file, and how that was established
  asserts    the failed-expression text, which names variables, constants and
             struct fields, and states the function's contract
  strings    literals the function references -- the debug menu labels are a
             particularly good signal since they are already translated
  callers /
  callees    who uses it and what it uses

    python3 dossier.py UNIT_SUBSTRING          e.g. hhcamera
    python3 dossier.py hhcamera --disasm
"""
import bisect, json, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'

sys.path.insert(0, HERE)
from addrloads import loads


def cstr(blob, off, limit=120):
    e = blob.find(b'\x00', off)
    if e < 0 or e - off > limit or e == off:
        return None
    raw = blob[off:e]
    if not all(32 <= c < 127 or c in (9, 10) for c in raw):
        return None
    return raw.decode('ascii')


def main():
    want = sys.argv[1]
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    asr = json.load(open(os.path.join(ROOT, 'symbols', 'asserts.json')))
    for rel, info in syms.items():
        funcs = sorted(info['functions'], key=lambda f: f['addr'])
        hits = [f for f in funcs if f['unit'] and want in f['unit']]
        if not hits:
            continue
        base = info['base']
        blob = open(os.path.join(GAME, rel), 'rb').read()
        starts = [f['addr'] for f in funcs]
        lo, hi = (0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99') else (0, len(blob) & ~3)

        calls, srefs = {}, {}
        for i in range(lo, hi - 8, 4):
            w = struct.unpack_from('<I', blob, i)[0]
            k = bisect.bisect_right(starts, base + i) - 1
            if k < 0:
                continue
            src = starts[k]
            if (w >> 26) == 3:
                t = ((base + i) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
                calls.setdefault(src, set()).add(t)
        # string references, via the liveness-aware scanner -- the old inline
        # lui/addiu pairing at +4/+8 only saw about half of them
        for i, a in loads(blob, lo, hi):
            k = bisect.bisect_right(starts, base + i) - 1
            if k < 0:
                continue
            off = a - base
            if 0 <= off < len(blob):
                s = cstr(blob, off)
                if s and len(s) > 2:
                    srefs.setdefault(starts[k], set()).add(s)
        callers = {}
        for a, ts in calls.items():
            for t in ts:
                callers.setdefault(t, set()).add(a)
        byaddr = {f['addr']: f for f in funcs}
        amap = {}
        for st in asr.get(rel, []):
            if st['func'] is not None:
                amap.setdefault(st['func'], []).append(st)

        print(f'=== {rel} :: units matching "{want}" -- {len(hits)} functions ===\n')
        for f in hits:
            print(f"0x{f['addr']:08X}  {f['name']}   size {f['size'] or '?'}  "
                  f"[{f['confidence']}]")
            print(f"    unit     {f['unit']}")
            for st in amap.get(f['addr'], [])[:4]:
                print(f"    assert   {st['file']}:{st['line']}   {st['expr']!r}")
            ss = sorted(srefs.get(f['addr'], []))[:4]
            for s in ss:
                print(f"    string   {s!r}")
            cs = sorted(callers.get(f['addr'], []))
            cl = sorted(calls.get(f['addr'], set()))
            if cs:
                print(f"    callers  " + ', '.join(
                    (byaddr[c]['name'] if c in byaddr else f'0x{c:08X}') for c in cs[:5]))
            if cl:
                print(f"    calls    " + ', '.join(
                    (byaddr[c]['name'] if c in byaddr else f'0x{c:08X}') for c in cl[:5]))
            print()
        return
    print(f'no unit matching "{want}"')


if __name__ == '__main__':
    main()
