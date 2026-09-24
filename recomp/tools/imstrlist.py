# -*- coding: utf-8 -*-
"""Dump imstrlist -- the game's own names for all 956 IM actions.

Found from the assert in btim319.c:652, `imid>0 && imid<Arraysize(imstrlist)`,
whose function indexes a table at 0x01F5B278 by IM id and sprintf's the two
strings it holds as "%s\\n%s". So each entry is a two-line label, and the whole
table is already translated to English.

This matters for reading the map: the free-roam and battle overlays hold units
named after IM ids (../im/im0423.c, btim319.c), and the table says what each
one IS -- im0423.c is "NPC Asuka Only / Close to Hikari 1". That is a real
description of the scene, not a guess.

    python3 imstrlist.py            print the table
    python3 imstrlist.py 423        one entry
    from imstrlist import lookup    {id: 'text'} for other tools
"""
import os, struct, sys

GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
BASE = 0x01F00000
TBL  = 0x01F5B278
COUNT = 956


def _blob():
    return open(os.path.join(GAME, 'prog/BATTLE.BIN'), 'rb').read()


def _cstr(blob, va, limit=90):
    o = va - BASE
    if not (0 <= o < len(blob)):
        return None
    e = blob.find(b'\x00', o)
    raw = blob[o:min(e if e > 0 else o + limit, o + limit)]
    try:
        return raw.decode('shift_jis')
    except UnicodeDecodeError:
        return None


def lookup():
    """{imid: 'line1 / line2'}"""
    blob = _blob()
    out = {}
    for i in range(COUNT):
        a, b = struct.unpack_from('<II', blob, TBL - BASE + i * 8)
        x, y = _cstr(blob, a), _cstr(blob, b)
        if x is None:
            continue
        out[i] = f'{x} / {y}' if y else x
    return out


if __name__ == '__main__':
    t = lookup()
    if len(sys.argv) > 1:
        i = int(sys.argv[1])
        print(f'[{i}] {t.get(i, "<out of range>")}')
    else:
        for i in sorted(t):
            print(f'{i:4}  {t[i]}')
