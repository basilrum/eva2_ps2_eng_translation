# -*- coding: utf-8 -*-
"""Bound every translation unit in the NGE2 executables.

The game shipped with asserts compiled out but their __FILE__ literals still
in .rodata, and the code that would have passed them still loads their
addresses. A MIPS address load is a lui/addiu pair carrying the halves of a
32-bit vaddr, so scanning .text for pairs that resolve to a known __FILE__
literal tells you which code belongs to which .c file.

That is the whole trick: 187 source filenames survive, so the original
translation-unit layout is recoverable without a symbol table (the ELF has
none -- 0 symbols).

Each binary needs its load address to turn a file offset into a vaddr. The
main ELF's is known from its program headers; for the overlays it is solved
for here, by taking the most common (referenced_vaddr - literal_file_offset)
across every candidate pair. A single consistent answer across dozens of
independent pairs is the confirmation that it is right.

    python3 tu_map.py [--json symbols/tu_map.json]
"""
import json, os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from addrloads import loads as _loads
from collections import Counter, defaultdict

GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
# All five overlays load into the SAME slot at 0x01F00000 -- BATTLE and FREE
# each solve to it independently (167 and 95 exact literal hits, next best 90
# and 42), and under it every unit range lands inside its image with zero
# overlaps, in ascending order, which is what a linker produces. TITLE/ENDING/
# MINIGAME carry too few literals to solve alone but agree with it (70/88/54%
# of their address loads point inside the image).
OVERLAY_BASE = 0x01F00000
BINS = [('SLPS_252.99', 0xFF000), ('prog/BATTLE.BIN', OVERLAY_BASE),
        ('prog/FREE.BIN', OVERLAY_BASE), ('prog/TITLE.BIN', OVERLAY_BASE),
        ('prog/ENDING.BIN', OVERLAY_BASE), ('prog/MINIGAME.BIN', OVERLAY_BASE)]
SRC = re.compile(rb'(?:\.\./)?[\w/]*[\w-]+\.(?:c|cpp)\x00')


def literals(blob):
    """file offset -> source filename, for NUL-delimited *.c strings."""
    out = {}
    for m in SRC.finditer(blob):
        s = m.start()
        if s and blob[s - 1] != 0:
            continue
        out[s] = m.group()[:-1].decode('latin-1')
    return out


def addr_loads(blob, lo=None, hi=None):
    """Every address load, as (site_file_offset, resolved_address).

    Uses the shared liveness-aware extractor: pairing lui only with an addiu
    at +4/+8 missed about half of all address loads, and this function is what
    every unit boundary is derived from.
    """
    if lo is None:
        lo, hi = 0, len(blob) & ~3
    return _loads(blob, lo, hi)


def solve_base(lits, loads):
    """base = referenced_vaddr - literal_file_offset, by majority vote."""
    votes = Counter()
    off = set(lits)
    for _, a in loads:
        for o in off:
            d = a - o
            if 0 < d < 0x40000000:
                votes[d] += 1
    if not votes:
        return None, 0, 0
    base, n = votes.most_common(1)[0]
    return base, n, votes.most_common(2)[1][1] if len(votes) > 1 else 0


def main():
    report = {}
    for rel, base in BINS:
        p = os.path.join(GAME, rel)
        if not os.path.isfile(p):
            continue
        blob = open(p, 'rb').read()
        lits = literals(blob)
        loads = addr_loads(blob)
        runner_up = 0
        if base is None:
            base, hits, runner_up = solve_base(lits, loads)
            if base is None:
                print(f'{rel}: no load address could be solved'); continue
            note = f'solved 0x{base:08X} ({hits} pairs agree, next best {runner_up})'
        else:
            note = f'base 0x{base:08X}'
        by_addr = {o + base: nm for o, nm in lits.items()}
        units = defaultdict(list)
        for site, a in loads:
            nm = by_addr.get(a)
            if nm:
                units[nm].append(site + base)
        print(f'\n{rel}  --  {note}')
        print(f'   {len(lits)} source literals, {len(loads)} address loads, '
              f'{len(units)} units located')
        rows = sorted((min(v), max(v), k, len(v)) for k, v in units.items())
        report[rel] = {'base': base, 'units': [
            {'file': k, 'lo': lo, 'hi': hi, 'refs': n} for lo, hi, k, n in rows]}
        for lo, hi, k, n in rows:
            print(f'     {k:16} 0x{lo:08X}..0x{hi:08X}  ({n} ref{"s" if n > 1 else ""})')
    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
        json.dump(report, open(out, 'w'), indent=1)
        print(f'\nwrote {out}')


if __name__ == '__main__':
    main()
