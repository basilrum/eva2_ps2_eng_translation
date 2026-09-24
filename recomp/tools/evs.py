# -*- coding: utf-8 -*-
"""Parse the game's .EVS event scripts.

NOTE ON OVERLAP: the translation repo already has an EVS parser at
`nge_2_re-master/tools/evs.py`, carried over from the PSP port, with a full
per-opcode parameter table. Use THAT one for anything touching dialogue. This
file exists because its format was recovered independently from the PS2 binary
-- which is what makes it useful as a cross-check, not as a replacement. The
two agree exactly on the container format, and the check in notes/evseq.md
found no opcode that carries text but is missing from its
HAS_CONTENT_SECTION.

Format recovered from evseq.c, not guessed. The two functions that prove it:

  evsStep @ 0x0016DAA8   return ctx->buffer + ctx->body[ctx->pc];
  a predicate @ 0x0016DBA8   return *(u16 *)evsStep() == 1;

So ctx->body (= buffer+8) is an ARRAY OF u32 OFFSETS indexed by the program
counter, each relative to the start of the buffer, and every record it points
at begins with a u16 opcode. That is why no opcode table exists in the binary:
the sequencer tests the opcode with a chain of predicate functions instead.

    file
      +0x00  char  magic[4]  ".EVS"      (memcmp'd by evseqCreate)
      +0x04  u32   count                 (-> ctx->0x14)
      +0x08  u32   offset[count]         (-> ctx->0x18, indexed by the PC)
      ...    records, each starting u16 opcode

Usage
    python3 evs.py <FILE.HAR> [...]      dump the script
    python3 evs.py --stats <dir>         opcode histogram over a whole tree
"""
import collections, glob, os, struct, sys

# opcode -> the predicate function in the ELF that recognises it
KNOWN = {1: 'evsIsOp1 @0x0016DBA8', 140: 'evsIsOp140 @0x0016DBD0',
         141: 'evsIsOp141 @0x0016DBF8', 144: 'evsIsOp144 @0x0016DC70',
         145: 'evsIsOp145 @0x0016DC48', 146: 'evsIsOp146 @0x0016DC20'}


def extract(path):
    """Pull the .evs member out of an HGAR archive (or read a bare .evs)."""
    b = open(path, 'rb').read()
    if b[:4] == b'.EVS':
        return b
    i = b.find(b'.EVS')
    if i < 0:
        return None
    return b[i:i + struct.unpack_from('<I', b, i - 4)[0]]


def steps(d):
    """Yield (index, offset, opcode, payload) for every step."""
    count = struct.unpack_from('<I', d, 4)[0]
    offs = [struct.unpack_from('<I', d, 8 + 4 * i)[0] for i in range(count)]
    for i, off in enumerate(offs):
        end = min((o for o in offs if o > off), default=len(d))
        yield i, off, struct.unpack_from('<H', d, off)[0], d[off + 2:end]


def dump(path):
    d = extract(path)
    if d is None:
        print(f'{path}: no .evs member')
        return
    count = struct.unpack_from('<I', d, 4)[0]
    print(f'\n=== {os.path.basename(path)}  {len(d)} bytes, {count} steps ===')
    for i, off, op, pay in steps(d):
        note = f'  <- {KNOWN[op]}' if op in KNOWN else ''
        body = pay[:24].hex(' ')
        print(f'  {i:4}  @0x{off:05X}  op {op:3}  {body}{note}')


def stats(root):
    ops = collections.Counter()
    files = empty = 0
    for p in sorted(glob.glob(os.path.join(root, '*.HAR'))):
        d = extract(p)
        if d is None:
            continue
        files += 1
        if struct.unpack_from('<I', d, 4)[0] == 0:
            empty += 1
            continue
        for _, _, op, _ in steps(d):
            ops[op] += 1
    print(f'{files} archives, {empty} with an empty script')
    print(f'{sum(ops.values())} steps, {len(ops)} opcodes, range '
          f'{min(ops)}..{max(ops)}\n')
    for op, c in ops.most_common():
        print(f'  op {op:3}  {c:6}   {KNOWN.get(op, "")}')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['--stats']:
        stats(a[1])
    else:
        for p in a:
            dump(p)
