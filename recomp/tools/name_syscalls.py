# -*- coding: utf-8 -*-
"""Name the PS2 EE kernel syscall stubs.

The main ELF links the standard stub table, where every entry is exactly four
instructions and does nothing but issue one numbered syscall:

    addiu $v1, $zero, N
    syscall
    jr    $ra
    nop

Matching that exact shape identifies them with no guesswork, and the number N
comes straight out of the instruction.

The name is `eeSyscall_<N>` and nothing more. Sony's own names for these
(CreateThread, SignalSema, ...) live in a documented external table; they are
NOT written here, because inventing a plausible-looking wrong name for a
kernel call is worse than leaving a number the reader can look up. Negative N
appears for the interrupt-context variants and is kept verbatim as `neg<N>`.

Naming them matters mainly because it marks ~170 functions as definitively not
game code.
"""
import json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
SYSCALL, JR_RA, NOP = 0x0000000C, 0x03E00008, 0x00000000


def main():
    apply = '--apply' in sys.argv
    p = os.path.join(ROOT, 'symbols', 'symbols.json')
    syms = json.load(open(p))
    total = 0
    for rel, info in syms.items():
        blob = open(os.path.join(GAME, rel), 'rb').read()
        base = info['base']
        for f in info['functions']:
            off = f['addr'] - base
            if off < 0 or off + 16 > len(blob):
                continue
            w = struct.unpack_from('<4I', blob, off)
            if w[1] != SYSCALL or w[2] != JR_RA or w[3] != NOP:
                continue
            if (w[0] >> 26) != 0x09 or ((w[0] >> 16) & 0x1F) != 3:  # addiu $v1
                continue
            if ((w[0] >> 21) & 0x1F) != 0:                          # from $zero
                continue
            imm = w[0] & 0xFFFF
            n = imm - 0x10000 if imm & 0x8000 else imm
            if f.get('name_source'):
                continue
            total += 1
            if apply:
                f['name'] = f'eeSyscall_neg{-n}' if n < 0 else f'eeSyscall_{n}'
                f['name_source'] = 'syscall_stub'
                f['name_why'] = f'four-instruction stub whose only body is syscall {n}'
    print(f'{total} EE kernel syscall stubs named')
    if apply:
        json.dump(syms, open(p, 'w'), indent=1)
        print('applied')


main()
