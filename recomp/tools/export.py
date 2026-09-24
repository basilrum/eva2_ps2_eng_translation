# -*- coding: utf-8 -*-
"""Export the map into formats other tools consume.

Everything so far lives in bespoke JSON. This turns it into:

  export/symbol_addrs.txt   splat / spimdisasm style, one symbol per line
  export/ghidra_import.py   a Ghidra script that applies the names AND attaches
                            the evidence as a plate comment on each function,
                            so the asserts and strings are visible while
                            reading the disassembly
  export/<binary>.csv       flat table for anything else

Names that were RECOVERED from the binary are marked; generated ones are
`unit_ADDR` so they stay greppable without pretending to be real.

    python3 export.py
"""
import json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'export')


def main():
    os.makedirs(OUT, exist_ok=True)
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    asr = json.load(open(os.path.join(ROOT, 'symbols', 'asserts.json')))
    amap = defaultdict(lambda: defaultdict(list))
    for rel, sites in asr.items():
        for s in sites:
            if s['func'] is not None:
                amap[rel][s['func']].append(s)

    lines, ghidra, ncsv = [], [], 0
    for rel, info in syms.items():
        base = info['base']
        lines.append(f'// {rel}  base 0x{base:08X}')
        rows = []
        for f in sorted(info['functions'], key=lambda x: x['addr']):
            src = f.get('name_source', 'generated')
            tag = {'recovered': ' RECOVERED', 'manual': ' HAND-DERIVED',
                   'menu_label': ' MENU-LABEL', 'solo_string': ' RECOVERED',
                   'prose_label': ' DESCRIPTIVE-ONLY'}.get(src, '')
            if f.get('region') == 'sdk':
                tag += ' [SDK]'
            lines.append(f"{f['name']} = 0x{f['addr']:08X}; // "
                         f"size:0x{f['size'] or 0:X} {f['unit'] or '?'} "
                         f"{f['confidence']}{tag}")
            ev = []
            if f['unit']:
                ev.append(f"unit: {f['unit']}")
            elif f.get('candidates'):
                ev.append("unit: one of " + ' | '.join(f['candidates']))
            for s in amap[rel].get(f['addr'], [])[:6]:
                ev.append(f"assert {s['file']}:{s['line']}  {s['expr']}")
            ev.append(f"reach: {f['confidence']}"
                      + (' (jal)' if f['called'] else '')
                      + (' (ptr)' if f.get('ptr_ref') else '')
                      + (' (addr-taken)' if f.get('addr_taken') else ''))
            if f.get('menu_label'):
                lbl = ('debug menu label' if src == 'menu_label'
                       else 'the ONE string this function references (a hint, '
                            'not necessarily its name)')
                ev.insert(0, f"{lbl}: {f['menu_label']}")
            if f.get('why'):
                ev.insert(0, f['why'])
            if f.get('region') == 'sdk':
                ev.append('Sony SDK / libc -- link, do not decompile')
            ghidra.append({'addr': f['addr'], 'name': f['name'],
                           'recovered': src in ('recovered', 'manual', 'menu_label'),
                           'ev': ev})
            rows.append((f['addr'], f['name'], f['unit'] or '', f['confidence'], src))
        with open(os.path.join(OUT, rel.replace('/', '_') + '.csv'), 'w') as fh:
            fh.write('addr,name,unit,confidence,name_source\n')
            for a, n, u, c, s in rows:
                fh.write(f'0x{a:08X},{n},{u},{c},{s}\n')
            ncsv += len(rows)

    open(os.path.join(OUT, 'symbol_addrs.txt'), 'w').write('\n'.join(lines) + '\n')

    # Ghidra script with the payload inlined, so it needs no other file
    payload = json.dumps(ghidra)
    script = '''# Ghidra script -- apply the NGE2 symbol map.
# Run with the SLPS_252.99 ELF (or an overlay) loaded. Addresses are the
# vaddrs from the map; entries outside the current image are skipped, so the
# same script works for the ELF and for each overlay.
# @category NGE2
import json
DATA = json.loads(r"""%s""")
fm = currentProgram.getFunctionManager()
st = currentProgram.getSymbolTable()
af = currentProgram.getAddressFactory().getDefaultAddressSpace()
from ghidra.program.model.symbol import SourceType
made = named = 0
for e in DATA:
    a = af.getAddress(e["addr"])
    if not currentProgram.getMemory().contains(a):
        continue
    f = fm.getFunctionAt(a)
    if f is None:
        f = createFunction(a, e["name"])
        if f is None:
            continue
        made += 1
    try:
        f.setName(e["name"], SourceType.IMPORTED if e["recovered"]
                  else SourceType.ANALYSIS)
        named += 1
    except Exception:
        pass
    if e["ev"]:
        f.setComment("\\n".join(e["ev"]))
print("created %%d functions, named %%d" %% (made, named))
''' % payload
    open(os.path.join(OUT, 'ghidra_import.py'), 'w').write(script)

    n = sum(len(v['functions']) for v in syms.values())
    from collections import Counter
    c = Counter(f.get('name_source', 'generated')
                for v in syms.values() for f in v['functions'])
    named = n - c['generated']
    print(f'{n} symbols exported, {named} with a real name: ' +
          ', '.join(f'{k} {v}' for k, v in c.most_common() if k != 'generated'))
    for f in sorted(os.listdir(OUT)):
        print(f'   export/{f}  {os.path.getsize(os.path.join(OUT,f)):,} bytes')


if __name__ == '__main__':
    main()
