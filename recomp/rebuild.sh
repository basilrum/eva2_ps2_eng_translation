#!/usr/bin/env bash
# Rebuild the whole map, in the only order that is correct.
#
# Written because getting this wrong three times cost real accuracy:
#   * a pass reading unit_windows4 (the REJECTED caller-locality data)
#   * a pass crashing while the chain carried on with stale input, reporting
#     68% when the truth was 77%
#   * naming passes run weakest-first, letting the vaguest source claim
#     functions that had better evidence available
#
# set -e so a crash stops the chain instead of poisoning everything after it.
set -euo pipefail
cd "$(dirname "$0")"

echo "== structure =="
python3 tools/tu_map.py          --json symbols/tu_map.json      | tail -1
python3 tools/unit_order.py      --json symbols/unit_order.json  | tail -1
python3 tools/func_scan.py       --json symbols/functions.json   | tail -1

echo "== attribution (each step reads the previous one) =="
python3 tools/anchor_expand.py   --json symbols/unit_windows.json  | tail -1
python3 tools/data_anchor.py     --json symbols/unit_windows2.json | tail -1
python3 tools/bss_anchor.py      --json symbols/unit_windows3.json | tail -1
python3 tools/table_propagate.py --json symbols/unit_windows5.json | tail -1
#  NOTE: unit_windows4 is deliberately absent -- it holds rejected data.

echo "== evidence =="
python3 tools/prune_funcs.py     --json symbols/functions_pruned.json | tail -1
python3 tools/asserts.py         --json symbols/asserts.json          | tail -1

echo "== merge =="
python3 tools/build_symbols.py | tail -2
python3 tools/sandwich_attr.py --apply | tail -2   # validated at 99.99% on a 7,064-function hold-out
python3 tools/classify_sdk.py --apply | tail -1

echo "== naming, STRONGEST FIRST (each pass skips already-named functions) =="
python3 tools/apply_manual.py      | tail -1
python3 tools/name_syscalls.py     --apply | tail -2   # exact-shape match, no guesswork
python3 tools/name_funcs.py        --apply | tail -1
python3 tools/name_trace_strings.py --apply | tail -2   # literal C identifiers the code prints about itself; beats every pass below
python3 tools/name_from_tables.py  --apply | tail -1
python3 tools/name_solo_strings.py --apply | tail -1
python3 tools/name_prose.py        --apply | tail -1

echo "== where it stands =="
python3 tools/stats.py

python3 tools/codebase_map.py
python3 tools/string_tables.py > notes/string_tables.txt   # the game's own English name tables
python3 tools/assert_glossary.py > notes/assert_glossary.txt  # fields/constants the asserts name
python3 tools/locate_arrays.py  > notes/arrays.txt            # where those named arrays live
python3 tools/imstrlist.py    > notes/imstrlist.txt      # 956 IM scene names

echo "== export =="
python3 tools/export.py | head -1

echo "== validation (signals the attribution never consumed) =="
python3 tools/check_lines.py | sed -n '2p'
python3 tools/check_names_vs_units.py | sed -n '2p'
python3 -c "
import ast; ast.parse(open('export/ghidra_import.py').read())
print('   ghidra export parses OK')"
