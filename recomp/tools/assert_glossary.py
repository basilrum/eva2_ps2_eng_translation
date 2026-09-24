# -*- coding: utf-8 -*-
"""Recover identifiers from assert expressions.

The asserts are live (684 call sites) and their expression text survives in
full, so every one is a fragment of real source. That makes them the only
place in the binary that names things a disassembler cannot infer:

    self->objtype == HHCA_OBJTYPE      a struct FIELD and a constant
    cid >= PID_BEGIN && cid < PID_MAX  an enum range
    vmode>=0 && vmode<Arraysize(viewparam)   a global ARRAY
    info->mPix!=NULL                   a field on a texture info struct

A recomp has to declare all of these, and guessing names for them is exactly
the kind of invention that makes decompiled source hard to trust. Here they
are, with the unit each was seen in.

    python3 assert_glossary.py
"""
import collections, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIELD = re.compile(r'\b([A-Za-z_]\w*)\s*(->|\.)\s*([A-Za-z_]\w*)')
CONST = re.compile(r'\b([A-Z][A-Z0-9_]{2,})\b')
ARRSZ = re.compile(r'\bArraysize\s*\(\s*([A-Za-z_]\w*)\s*\)')
CALL  = re.compile(r'\b([A-Za-z_]\w*)\s*\(\s*\)')
# words that are C keywords or appear as bare operands, not identifiers we want
SKIP = {'NULL', 'TRUE', 'FALSE', 'sizeof'}


def main():
    asr = json.load(open(os.path.join(ROOT, 'symbols', 'asserts.json')))
    fields = collections.defaultdict(set)   # struct var -> {field}
    consts = collections.defaultdict(set)   # const -> {unit}
    arrays = collections.defaultdict(set)
    calls  = collections.defaultdict(set)
    for rel, sites in asr.items():
        for s in sites:
            e = s.get('expr')
            if not e:
                continue
            u = s.get('unit') or s.get('file') or '?'
            for var, op, fld in FIELD.findall(e):
                fields[var].add(fld)
            for c in CONST.findall(e):
                if c not in SKIP:
                    consts[c].add(u)
            for a in ARRSZ.findall(e):
                arrays[a].add(u)
            for c in CALL.findall(e):
                if c not in SKIP:
                    calls[c].add(u)

    print(f'STRUCT FIELDS  ({sum(len(v) for v in fields.values())} '
          f'across {len(fields)} variables)')
    for var in sorted(fields, key=lambda k: -len(fields[k])):
        print(f'  {var:14} {", ".join(sorted(fields[var]))}')
    print(f'\nCONSTANTS  ({len(consts)})')
    for c in sorted(consts):
        print(f'  {c:34} {", ".join(sorted(consts[c])[:3])}')
    print(f'\nARRAYS named by Arraysize()  ({len(arrays)})')
    for a in sorted(arrays):
        print(f'  {a:24} {", ".join(sorted(arrays[a]))}')
    print(f'\nFUNCTIONS called in assertions  ({len(calls)})')
    for c in sorted(calls):
        print(f'  {c:24} {", ".join(sorted(calls[c])[:3])}')


main()
