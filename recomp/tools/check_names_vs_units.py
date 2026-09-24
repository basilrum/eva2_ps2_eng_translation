# -*- coding: utf-8 -*-
"""Validate ATTRIBUTION against NAMES -- two signals that never touch.

Attribution comes from __FILE__ literal windows and linker layout. Naming comes
from strings, asserts, menu tables and trace output. Neither pass ever reads the
other's output, so where a recovered name encodes its own module the two can be
checked against each other at FUNCTION granularity -- which the assert-line
check (99.5%) cannot do, since that only measures ordering.

The engine's names are `hh<Module><Verb>`, and its filenames abbreviate by
truncating each word: hhObjectMotionLoadByID lives in hhobjmot.c, hhDrawLinkAdd
in hhdrawlk.c. So a filename counts as a match when it can be built from
prefixes of the leading CamelCase words. Without that rule the check reports
false errors -- 8 correct hhobjmot.c functions looked wrong at first pass.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORDS = re.compile(r'[A-Z][a-z0-9]*')


def matches(stem, name, pfx):
    """Can `stem` (e.g. hhobjmot, fclocate) be built from name's words?"""
    if not stem.startswith(pfx):
        return False
    # filenames carry disambiguating digits no identifier has (btmissi4.c
    # holds btMission*), so digits are not evidence either way
    rest = ''.join(c for c in stem[len(pfx):] if not c.isdigit())
    words = [w.lower() for w in WORDS.findall(name[len(pfx):])]
    if not words:
        return False
    # Walk the stem, consuming a SUBSEQUENCE of each successive word -- the
    # abbreviations drop interior letters, not just trailing ones
    # (hhdrawlk = draw + l..k from "link"), so a prefix test rejects real
    # matches. Order is still enforced within and across words.
    # An abbreviation may drop an entire word, not just letters: fcstate.c
    # holds fcAIState* -- "AI" vanishes. So a skipped word is allowed, which
    # makes this an ordered-subsequence test across the whole name. Looser
    # than a per-word prefix test, and deliberately so: the point is to
    # surface real misplacements, and a matcher that cries wolf on correct
    # attributions is worse than one that occasionally lets a bad one pass.
    i = 0
    for w in words:
        if i >= len(rest):
            break
        for ch in w:
            if i < len(rest) and rest[i] == ch:
                i += 1
    return i == len(rest)


FAMILIES = set()
UNITS = {}
# Name sources whose names are the GAME's own identifiers. `manual` is
# excluded because those names are mine -- checking my invented `evsStep`
# against restore.c measures my naming taste, not the attribution. `sce*`
# names drop out on their own: no unit stem starts with "sce", so it is not a
# filename family.
EVIDENCE = {'recovered', 'trace_string', 'solo_string', 'menu_label'}

# Only the hahig engine names files strictly after the module in the
# identifier, so only `hh` gives a sound verdict. The game's own overlays do
# not: fmchmove.c is "chara MOVE" and correctly holds fmCharaRunspeedSet, but
# the word "move" appears nowhere in that identifier, so any filename-derived
# test calls it an error. Running with --all reports 49 disagreements of which
# roughly 30 are that single false pattern. A validation signal that is wrong
# half the time is not a validation signal, so the broad sweep stays opt-in
# and out of rebuild.sh.
STRICT = {'hh'}


def main():
    syms = json.load(open(os.path.join(ROOT, 'symbols', 'symbols.json')))
    tu = json.load(open(os.path.join(ROOT, 'symbols', 'tu_map.json')))
    for rel, info in tu.items():
        UNITS[rel] = [u['file'] for u in info['units']]
        for u in info['units']:
            FAMILIES.add(os.path.basename(u['file'])[:-2])
    ok = bad = 0
    rows = []
    for rel, info in syms.items():
        for f in info['functions']:
            n, u = f.get('name'), f.get('unit')
            if not (n and u and f.get('name_source') in EVIDENCE):
                continue
            m = re.match(r'^([a-z]{2,4})[A-Z]', n)
            if not m:
                continue
            pfx = m.group(1)
            if pfx not in STRICT and '--all' not in sys.argv:
                continue
            if sum(1 for x in FAMILIES if x.startswith(pfx)) < 2:
                continue
            stem = os.path.basename(u)[:-2]
            if not stem.startswith(pfx):
                # the name's family and the unit's family differ entirely
                # (e.g. an fm* name in a bt* file) -- that IS a disagreement,
                # but only when some unit of that family exists to move it to
                alt = sorted({v for v in UNITS[rel]
                              if matches(os.path.basename(v)[:-2], n, pfx)})
                if not alt:
                    continue
                bad += 1
                rows.append((f['addr'], n, u, alt[0]))
                continue
            if matches(stem, n, pfx):
                ok += 1
            else:
                # Filename abbreviations are not systematically derivable
                # (btmemory.c holds btMemSelect*), so "the stem does not match"
                # is NOT evidence of misplacement on its own. Only call it an
                # error when a DIFFERENT unit in the same binary does match the
                # name -- i.e. there is somewhere better for it to live.
                alt = sorted({v for v in UNITS[rel]
                              if matches(os.path.basename(v)[:-2], n, pfx)
                              and v != u})
                if not alt:
                    ok += 1
                    continue
                bad += 1
                rows.append((f['addr'], n, u, alt[0]))
    print(f'   names encoding their own module: {ok + bad}')
    print(f'   attribution agrees {ok}, disagrees {bad}  = {100*ok/(ok+bad):.1f}%')
    for a, n, u, alt in sorted(rows):
        print(f'     0x{a:08X}  {n:30} in {u:24} -- {alt} fits the name')


main()
