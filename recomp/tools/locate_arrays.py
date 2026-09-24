# -*- coding: utf-8 -*-
"""Locate the global arrays that assert text names.

31 asserts read `... < Arraysize(<name>)`, which gives the array's real
identifier but not where it lives. The function holding such an assert has to
bounds-check the index and then index the array, so the code supplies what the
text does not:

    sltiu $t, $idx, N          <- N is the element count
    ...
    sll   $x, $idx, S          <- S is log2(element size)
    addu  $y, <base>, $x       <- base comes from a lui/addiu pair

What is TRUSTWORTHY from this:

  base      good -- confirmed independently for imstrlist, datainitalfunclist
            and equipdata (whose first words are "Smash Hawk", "(none)",
            "Sonic Glaive", unmistakably the Eva weapon table)
  count     good -- it is the literal the code bounds-checks against

What is NOT:

  elem size WEAK. It is taken from the first plausible `sll` in the function,
            which is often scaling a different index entirely. equipdata is
            reported as 4B when its entries are plainly much wider. Treat the
            element size as a hint and confirm it by reading the data.

    python3 locate_arrays.py
"""
import json, os, re, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
ARRSZ = re.compile(r'\bArraysize\s*\(\s*([A-Za-z_]\w*)\s*\)')


def analyse(blob, base, faddr, size):
    """-> (count, table_va, elem_size) or None."""
    o = faddr - base
    if o < 0 or o + size > len(blob):
        return None
    words = [struct.unpack_from('<I', blob, o + i)[0] for i in range(0, size, 4)]
    count = None
    for w in words:
        op = w >> 26
        if op == 0x0B:                       # sltiu rt, rs, imm
            imm = w & 0xFFFF
            if 1 < imm < 4096:
                count = imm
                break
    if count is None:
        return None
    # log2(element size) from the shift that scales the index
    shift = None
    for w in words:
        if (w >> 26) == 0 and (w & 0x3F) == 0:          # sll
            s = (w >> 6) & 0x1F
            if 1 <= s <= 6:
                shift = s
                break
    # table base: the lui/addiu pair whose result is in .data, not .text
    hi = {}
    cand = []
    for i, w in enumerate(words):
        op = w >> 26
        if op == 0x0F:                                   # lui
            hi[(w >> 16) & 0x1F] = (w & 0xFFFF) << 16
        elif op == 0x09:                                 # addiu
            rs = (w >> 21) & 0x1F
            if rs in hi:
                lo = w & 0xFFFF
                va = (hi[rs] + (lo - 0x10000 if lo & 0x8000 else lo)) & 0xFFFFFFFF
                cand.append(va)
    if not cand:
        return None
    return count, cand, (1 << shift if shift else None)


def is_cstring(blob, base, va, limit=80):
    """A lui/addiu pair that resolves onto a C string is an assert argument
    (the file name or the expression text), not the table we are after."""
    o = va - base
    if not (0 <= o < len(blob) - 1):
        return False
    e = blob.find(b'\x00', o)
    if e < 0 or e - o < 3 or e - o > limit:
        return False
    return all(32 <= c < 127 for c in blob[o:e])


def plausible(blob, base, va, count, esz):
    """Does `count` elements of `esz` bytes at va look like a table?

    Checked two ways, because the tables are of two kinds: arrays of pointers
    (every word lands in the image) and arrays of small structs (mostly small
    integers). Either is fine; random code or padding is not.
    """
    o = va - base
    if esz is None or not (0 <= o < len(blob) - count * esz):
        return False
    n = min(count, 32)
    words = [struct.unpack_from('<I', blob, o + i * 4)[0]
             for i in range(min(n * max(esz // 4, 1), (len(blob) - o) // 4))]
    if not words:
        return False
    inimg = sum(1 for w in words if base <= w < base + len(blob))
    small = sum(1 for w in words if w < 0x10000)
    return (inimg + small) >= len(words) * 0.7


def main():
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    asr = json.load(open(os.path.join(ROOT, 'symbols', 'asserts.json')))
    found, missing = [], []
    for rel, sites in asr.items():
        blob = open(os.path.join(GAME, rel), 'rb').read()
        base = syms[rel]['base']
        by = {f['addr']: f for f in syms[rel]['functions']}
        seen = set()
        for s in sites:
            e = s.get('expr') or ''
            m = ARRSZ.search(e)
            if not m or s.get('func') is None:
                continue
            name = m.group(1)
            if (rel, name) in seen:
                continue
            seen.add((rel, name))
            f = by.get(s['func'])
            if not f:
                missing.append((rel, name, 'containing function unknown'))
                continue
            r = analyse(blob, base, f['addr'], f.get('size') or 0)
            if not r:
                missing.append((rel, name, 'no bounds-check/base pattern'))
                continue
            count, cands, esz = r
            keep = [c for c in cands if not is_cstring(blob, base, c)]
            good = [c for c in keep if plausible(blob, base, c, count, esz)]
            found.append((rel, name, count, esz, good or keep, bool(good),
                          s['file'], s['line']))
    print(f'{len(found)} arrays located, {len(missing)} not\n')
    for rel, name, count, esz, cands, solid, f, l in sorted(found, key=lambda t: t[1]):
        mark = 'at' if (solid and len(cands) == 1) else 'candidates'
        cs = ' '.join(f'0x{c:08X}' for c in cands[:3])
        print(f'  {name:26} {count:5} x {str(esz):>4}B  {mark:10} {cs}'
              f'   [{rel.replace("prog/","")} {f}:{l}]')
    if missing:
        print('\nnot located:')
        for rel, name, why in missing:
            print(f'  {name:26} {why}')


main()
