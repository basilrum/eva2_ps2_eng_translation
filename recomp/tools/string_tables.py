# -*- coding: utf-8 -*-
"""Find the game's own English name tables.

A run of consecutive words that all resolve to short C strings is a name
table, and this game is full of them -- scenario lists, location names,
animation names, IM action labels. They are all already translated, so they
are the best available documentation of what the code is talking about.

Found by scanning every 4-byte-aligned word outside the code region, keeping
runs of >=12 consecutive valid string pointers. The run-length floor is what
keeps it from firing on incidental integers.

    python3 string_tables.py             summary of every table
    python3 string_tables.py 0x01F7F264  dump one table
"""
import json, os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
MIN_RUN = 12


def cstr(blob, base, va, limit=100):
    o = va - base
    if not (0 <= o < len(blob) - 1):
        return None
    e = blob.find(b'\x00', o)
    if e < 0 or e - o > limit:
        return None
    raw = blob[o:e]
    if len(raw) < 2 or not all(32 <= c < 127 or c >= 0x81 for c in raw):
        return None
    try:
        return raw.decode('shift_jis')
    except UnicodeDecodeError:
        return None


def tables(rel, info):
    blob = open(os.path.join(GAME, rel), 'rb').read()
    base = info['base']
    out, cur, start = [], 0, 0
    for i in range(0, (len(blob) & ~3) - 4, 4):
        w = struct.unpack_from('<I', blob, i)[0]
        if cstr(blob, base, w) is not None:
            if cur == 0:
                start = i
            cur += 1
        else:
            if cur >= MIN_RUN:
                out.append((base + start, cur))
            cur = 0
    if cur >= MIN_RUN:
        out.append((base + start, cur))
    return blob, base, out


def main():
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    want = int(sys.argv[1], 16) if len(sys.argv) > 1 else None
    total = 0
    for rel, info in syms.items():
        blob, base, tabs = tables(rel, info)
        if not tabs:
            continue
        if want is None:
            print(f'\n=== {rel}  ({len(tabs)} tables)')
        for va, n in sorted(tabs, key=lambda t: -t[1]):
            total += 1
            if want is not None:
                if va != want:
                    continue
                print(f'{rel}  0x{va:08X}  {n} entries')
                for k in range(n):
                    w = struct.unpack_from('<I', blob, va - base + k * 4)[0]
                    print(f'  [{k:4}] {cstr(blob, base, w)}')
                return
            head = []
            for k in range(min(n, 3)):
                w = struct.unpack_from('<I', blob, va - base + k * 4)[0]
                head.append(cstr(blob, base, w)[:22])
            print(f'  0x{va:08X}  {n:4}  {head}')
    if want is None:
        print(f'\n{total} tables total')


main()
