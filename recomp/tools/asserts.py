# -*- coding: utf-8 -*-
"""Extract every assert site: source file, line number, and the expression.

The asserts were compiled out of the *messages* but not out of the *calls*.
Each site looks like:

    lui   $a0, hi(__FILE__)     ; the source file
    lui   $a2, hi(expr)         ; the failed expression, as text
    addiu $a0, ...
    addiu $a2, ...
    jal   panic
    addiu $a1, $zero, LINE      ; the line number

so every site yields (file, line, expression) plus the function it sits in.
That is three useful things at once:

  * the expression names variables and states the function's contract, which
    is the best naming evidence in the binary
  * the line number orders functions WITHIN a file, independently of address
  * a file+line pair confirms the unit attribution for that function

    python3 asserts.py [--json symbols/asserts.json]
"""
import bisect, json, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = '/home/vasilije/Downloads/nge_2_re-master/tools/everything'
SRC = re.compile(rb'(?:\.\./)?[\w/]*[\w-]+\.(?:c|cpp)\x00')


def cstr(blob, off, limit=200):
    e = blob.find(b'\x00', off)
    if e < 0 or e - off > limit:
        return None
    try:
        return blob[off:e].decode('ascii')
    except UnicodeDecodeError:
        return None


def main():
    fns = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    out, total = {}, 0
    for rel, info in fns.items():
        base = info['base']
        blob = open(os.path.join(GAME, rel), 'rb').read()
        files = {}
        for m in SRC.finditer(blob):
            s = m.start()
            if s == 0 or blob[s - 1] == 0:
                files[s + base] = m.group()[:-1].decode('latin-1')
        funcs = sorted(info['functions'], key=lambda f: f['addr'])
        starts = [f['addr'] for f in funcs]
        lo, hi = (0x1000, 0x1000 + 0xC4AB8) if rel.endswith('.99') else (0, len(blob) & ~3)

        # gather register-forming pairs in a small window, then read them off
        sites = []
        for i in range(lo, hi - 4, 4):
            w = struct.unpack_from('<I', blob, i)[0]
            if (w >> 26) != 3:                      # jal
                continue
            # Track only what we can model, and INVALIDATE a register written
            # by anything else -- otherwise a stale constant from further back
            # is read as the line number. That mistake showed up as assert line
            # numbers going out of order within a file.
            RT_WRITERS = {0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x18,
                          0x19, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
                          0x2E, 0x31, 0x35}
            regs, line = {}, None
            for j in range(max(lo, i - 128), i + 8, 4):
                v = struct.unpack_from('<I', blob, j)[0]
                op = v >> 26
                if op == 0:                      # SPECIAL: writes rd
                    rd = (v >> 11) & 0x1F
                    regs.pop(rd, None)
                elif op in RT_WRITERS and op not in (0x0F, 0x09, 0x0D):
                    regs.pop((v >> 16) & 0x1F, None)
                if op == 0x0F:                      # lui
                    regs[(v >> 16) & 0x1F] = (v & 0xFFFF) << 16
                elif op == 0x0D:                    # ori
                    rs, rt = (v >> 21) & 0x1F, (v >> 16) & 0x1F
                    im = v & 0xFFFF
                    if rs == 0:
                        regs[rt] = im
                    elif rs in regs:
                        regs[rt] = regs[rs] | im
                elif op == 0x09:                    # addiu
                    rs, rt = (v >> 21) & 0x1F, (v >> 16) & 0x1F
                    im = v & 0xFFFF
                    im = im - 0x10000 if im & 0x8000 else im
                    if rs == 0:
                        regs[rt] = im
                    elif rs in regs:
                        regs[rt] = regs[rs] + im
            a0, a1, a2 = regs.get(4), regs.get(5), regs.get(6)
            if a0 not in files:
                continue
            expr = cstr(blob, a2 - base) if a2 and 0 <= a2 - base < len(blob) else None
            k = bisect.bisect_right(starts, base + i) - 1
            fn = funcs[k] if k >= 0 else None
            sites.append({'site': base + i, 'file': files[a0], 'line': a1,
                          'expr': expr, 'func': fn['addr'] if fn else None,
                          'unit': fn['unit'] if fn else None})
        out[rel] = sites
        total += len(sites)
        withexpr = sum(1 for s in sites if s['expr'])
        print(f'{rel}: {len(sites)} assert sites, {withexpr} with an expression string')
    print(f'\nTOTAL {total} assert sites')
    if '--json' in sys.argv:
        p = os.path.join(ROOT, 'symbols', 'asserts.json')
        json.dump(out, open(p, 'w'), indent=1)
        print(f'wrote {p}')


if __name__ == '__main__':
    main()
