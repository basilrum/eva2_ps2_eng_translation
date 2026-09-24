# -*- coding: utf-8 -*-
"""Recover function boundaries, and attribute each function to its .c file.

Two independent sources of truth, which is the point -- where they agree, a
function entry is certain:

  jal targets      a `jal` names its callee outright. Definite entry points,
                   but only for functions that are actually called directly;
                   anything reached solely through a pointer is invisible here.

  return boundaries  the word after a `jr $ra` and its delay slot starts the
                   next function, once any `nop` alignment padding is stepped
                   over. Catches pointer-only functions, but over-fires on
                   functions with several `return`s, where an interior `jr $ra`
                   is followed by more of the same function.

So: take jal targets as certain, use return boundaries to fill the gaps, and
report how much the two agree as a confidence measure.

Attribution comes from tu_map.json -- a function belongs to the unit whose
__FILE__ reference span contains it. Units only pin the range they are
referenced from, so functions before the first reference or after the last in
a unit fall in the gaps between units and are left unattributed rather than
guessed at.

    python3 func_scan.py [--json symbols/functions.json]
"""
import json, os, struct, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
JR_RA, NOP = 0x03E00008, 0x00000000


def scan(blob, base, lo, hi):
    """lo..hi are file offsets bounding the executable region."""
    jal, rets = set(), []
    for i in range(lo, hi - 4, 4):
        w = struct.unpack_from('<I', blob, i)[0]
        op = w >> 26
        if op == 3:                                  # jal
            tgt = ((base + i) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
            jal.add(tgt)
        elif w == JR_RA:
            j = i + 8                                # skip the delay slot
            while j < hi and struct.unpack_from('<I', blob, j)[0] == NOP:
                j += 4                               # step over alignment padding
            if j < hi:
                rets.append(base + j)
        elif op == 2:
            # A TAIL CALL ends a function just as a `jr $ra` does: the compiler
            # drops the epilogue's jump-to-register and emits a plain `j` to
            # the callee instead. Scanning only for `jr $ra` therefore glues
            # the next function onto this one -- it merged four functions at
            # 0x00172538, one of which was the event-script interpreter.
            #
            # Requiring the `j` target to be a known jal target does NOT work:
            # tail calls into pointer-only helpers are exactly the case that
            # goes wrong, and that filter misses all of them. What identifies
            # a boundary is the other side -- the next instruction being a
            # stack-allocating prologue. An intra-function `j` lands on more
            # of the same function, and an early exit lands on an epilogue,
            # which adds to $sp rather than subtracting from it.
            j = i + 8
            while j < hi and struct.unpack_from('<I', blob, j)[0] == NOP:
                j += 4
            if j < hi:
                nxt = struct.unpack_from('<I', blob, j)[0]
                if (nxt >> 16) == 0x27BD and (nxt & 0x8000):   # addiu $sp,$sp,-N
                    rets.append(base + j)
    return jal, set(rets)


def main():
    tu = json.load(open(os.path.join(ROOT, 'symbols', 'tu_map.json')))
    out, totals = {}, [0, 0, 0, 0]
    for rel, info in tu.items():
        p = os.path.join(GAME, rel)
        blob = open(p, 'rb').read()
        base = info['base']
        lo, hi = (0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99') else (0, len(blob) & ~3)
        jal, rets = scan(blob, base, lo, hi)
        # The ELF entry point is a function by definition, but nothing `jal`s
        # it and no `jr $ra` precedes it, so neither source can see it. It was
        # genuinely missing from the map until this was added -- and it is the
        # root of the whole call graph, so everything reachability-related
        # started from the wrong place.
        if blob[:4] == b'\x7fELF':
            jal.add(struct.unpack_from('<I', blob, 0x18)[0])
        else:
            # An overlay is a raw image loaded at `base`, and the main ELF
            # enters it by `jal 0x01F00000` -- overlayEnter @0x00140990 does
            # exactly that, so the load base IS the entry point. All five
            # overlays have a real prologue there and none of them had it in
            # the map: nothing inside an overlay calls its own entry, and no
            # `jr $ra` precedes offset 0.
            jal.add(base)
        # A function reached ONLY through a pointer in a table is invisible to
        # both sources. Take a data word that points at a stack-allocating
        # prologue as an entry: the prologue test is what keeps this from
        # firing on arbitrary integers that happen to land in .text. It finds
        # just 5 in the whole game -- e.g. entry 4 of the boot-mode table at
        # 0x001D2780 -- so the map was already close to complete here, but a
        # missing function is a missing function.
        for k in range(0, (len(blob) & ~3) - 4, 4):
            if lo <= k < hi:
                continue
            w = struct.unpack_from('<I', blob, k)[0]
            if (w & 3) or not (base + lo <= w < base + hi):
                continue
            o = w - base
            if o + 4 > len(blob):
                continue
            nxt = struct.unpack_from('<I', blob, o)[0]
            if (nxt >> 16) == 0x27BD and (nxt & 0x8000):
                jal.add(w)
        inrange = lambda a: base + lo <= a < base + hi
        jal = {a for a in jal if inrange(a)}
        rets = {a for a in rets if inrange(a)}
        starts = sorted(jal | rets)
        agree = len(jal & rets)
        units = sorted(info['units'], key=lambda u: u['lo'])

        # A unit's __FILE__ references only pin the span between the first and
        # last of them, which is a slice of the unit -- so a plain containment
        # test leaves most functions unattributed. But the linker emits units
        # contiguously, so a function in the gap between unit i and unit i+1
        # must belong to one or the other. Report that honestly as a pair
        # rather than either dropping it or guessing one.
        def unit_of(a):
            for u in units:
                if u['lo'] <= a <= u['hi']:
                    return u['file'], True
            for i in range(len(units) - 1):
                if units[i]['hi'] < a < units[i + 1]['lo']:
                    return f"{units[i]['file']}|{units[i + 1]['file']}", False
            return None, False

        funcs, by_unit = [], defaultdict(int)
        narrowed = 0
        for k, a in enumerate(starts):
            end = starts[k + 1] if k + 1 < len(starts) else base + hi
            f, certain = unit_of(a)
            funcs.append({'addr': a, 'size': end - a, 'unit': f,
                          'certain': certain, 'called': a in jal})
            if certain:
                by_unit[f] += 1
            elif f:
                narrowed += 1
        named = sum(1 for f in funcs if f['certain'])
        out[rel] = {'base': base, 'functions': funcs}
        totals[0] += len(funcs); totals[1] += named; totals[2] += len(jal)
        totals.append(narrowed) if len(totals) < 4 else totals.__setitem__(3, totals[3] + narrowed)
        print(f'{rel}')
        print(f'   {len(jal):5} jal targets, {len(rets):5} return boundaries, '
              f'{agree:5} agree ({agree/max(len(jal),1):.0%} of jal targets)')
        print(f'   {len(funcs):5} functions: {named} pinned to one unit '
              f'({named/max(len(funcs),1):.0%}), {narrowed} narrowed to two '
              f'({(named+narrowed)/max(len(funcs),1):.0%} placed)')
        top = sorted(((v, k) for k, v in by_unit.items() if k), reverse=True)[:5]
        print('   biggest units: ' + ', '.join(f'{k} {v}' for v, k in top))
    print(f'\nTOTAL  {totals[0]} function candidates')
    print(f'       {totals[1]} pinned to one .c file, {totals[3]} narrowed to two '
          f'-> {totals[1]+totals[3]} placed ({(totals[1]+totals[3])/totals[0]:.0%})')
    print(f'       {totals[2]} are directly called (jal), which is the firm '
          f'lower bound on the real function count')
    if '--json' in sys.argv:
        d = os.path.join(ROOT, 'symbols', 'functions.json')
        json.dump(out, open(d, 'w'), indent=1)
        print(f'wrote {d}')


if __name__ == '__main__':
    main()
