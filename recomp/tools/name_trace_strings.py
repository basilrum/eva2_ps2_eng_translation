# -*- coding: utf-8 -*-
"""Name functions from trace strings that contain the function's own name.

Debug builds are full of printf calls that identify their caller:

    _SidToSeAngel(%d) index error\n
    OnAlert()alertparm:%p,hsprite[0]:%d,hsprite[1]:%d\n
    AlertFree(%p,%p)time:%d\n
    gmVoicePlay(nid:%d)\n

Each is a literal C identifier immediately followed by '(' -- the programmer
writing out the call they are tracing. That is a NAME, not a description, and
it is the strongest evidence in the binary short of an assert.

Only accept a function when the identifiers found in its strings agree, so a
function that traces something else does not steal that name. Anything printed
by more than one function is dropped as well -- a shared format string says
nothing about which of them owns the name.

Run AFTER the stronger passes; it skips anything already named.
"""
import json, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
sys.path.insert(0, HERE)
from addrloads import loads
import bisect, struct

# an identifier glued to an open paren, at the very start of the string
CALL = re.compile(r'^_?([A-Za-z][A-Za-z0-9_]{2,63})\(')
# reject C library calls and control keywords that show up in traces
REJECT = {'if', 'for', 'while', 'switch', 'return', 'sizeof', 'printf',
          'sprintf', 'malloc', 'free', 'memset', 'memcpy', 'strcpy', 'assert'}


def cstr(blob, off, limit=200):
    e = blob.find(b'\x00', off)
    if e < 0 or e - off > limit or e == off:
        return None
    raw = blob[off:e]
    if not all(32 <= c < 127 or c in (9, 10, 13) for c in raw):
        return None
    return raw.decode('ascii')


def main():
    apply = '--apply' in sys.argv
    path = os.path.join(ROOT, 'symbols', 'symbols.json')
    syms = json.load(open(path))
    total = skipped = 0
    agree = disagree = 0

    for rel, info in syms.items():
        funcs = sorted(info['functions'], key=lambda f: f['addr'])
        base = info['base']
        blob = open(os.path.join(GAME, rel), 'rb').read()
        starts = [f['addr'] for f in funcs]
        byaddr = {f['addr']: f for f in funcs}
        lo, hi = (0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99') else (0, len(blob) & ~3)

        cand = collections.defaultdict(set)   # func -> {identifier}
        owners = collections.defaultdict(set)  # identifier -> {func}
        for i, a in loads(blob, lo, hi):
            k = bisect.bisect_right(starts, base + i) - 1
            if k < 0:
                continue
            off = a - base
            if not (0 <= off < len(blob)):
                continue
            s = cstr(blob, off)
            if not s:
                continue
            m = CALL.match(s)
            if not m:
                continue
            ident = m.group(1)
            if ident in REJECT or ident.lower() == ident and '_' not in ident and len(ident) < 6:
                continue
            cand[starts[k]].add(ident)
            owners[ident].add(starts[k])

        for addr, idents in sorted(cand.items()):
            idents = {i for i in idents if len(owners[i]) == 1}
            if len(idents) != 1:
                skipped += 1
                continue
            name = idents.pop()
            f = byaddr[addr]
            if f.get('name_source'):
                # hold-out: does this agree with what a stronger pass decided?
                if f.get('name', '').lower() == name.lower():
                    agree += 1
                else:
                    disagree += 1
                    print(f'   differs {addr:08X} {rel:14} had {f["name"]!r} '
                          f'trace says {name!r}')
                continue
            total += 1
            if apply:
                f['name'] = name
                f['name_source'] = 'trace_string'
                f['name_why'] = 'the function prints its own name in a trace string'

    print(f'\n{total} functions named from trace strings, {skipped} ambiguous')
    print(f'hold-out against already-named functions: {agree} agree, {disagree} differ')
    if apply:
        json.dump(syms, open(path, 'w'), indent=1)
        print('applied')


main()
