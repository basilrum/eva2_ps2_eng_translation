# The game's own English name tables

91 arrays of C-string pointers, found by `tools/string_tables.py` (runs of >=12
consecutive words that all resolve to short strings). All of them are already
translated, which makes them the best documentation in the binary of what the
code is actually about -- better than any name I could invent.

Dump one with `python3 tools/string_tables.py 0x<addr>`.

## The ones worth knowing

| where | n | what it is |
|-------|---|------------|
| FREE `0x01F84AE8` | 958 | IM action labels, the free-roam mirror of imstrlist |
| BATTLE `0x01F5B278` | 956 | **imstrlist** -- see notes/evseq.md; names every IM scene |
| FREE `0x01F7F264` | 345 | **place names**: Closet, Guest Room, Misato's Room, Misato's Fridge, Shinji's Laptop ... |
| FREE `0x01F7EE50` | 104 | **animation states**: "Run -> Stand (Norm)", "Relax 1 (Norm 1)" |
| SLPS `0x001D3438` | 99 | status/effect names indexed by id (`003 : Bsrk`) |
| BATTLE `0x01F5BFB0` | 97 | IM labels, battle side |
| FREE `0x01F7F0D8` | 96 | scenario list (`Misato Promoted`, `Israfel Appears, 1st`) |
| SLPS `0x001D32C0` | 93 | **scenario list**, numbered (`03 : Israfel Appears, 1st time`) |
| SLPS `0x001D36A0` | 91 | numbered dialogue lines (`001 : 01: You betrayed me!`) |
| SLPS `0x001D35C8` | 53 | battle prompts (`000 : AT Field Neutralize ...`) |
| SLPS `0x001DC1F0` | 61 | IM outcome labels, tagged `IMP0` |
| TITLE `0x01F03B88` | 54 | **scenario table**: alternating `game/s001.dat` / `Angel Attack` |
| FREE `0x01F8B740` | 48 | four-character bone/joint names (`FSTP HEAD RCLA RFI0`) |
| SLPS `0x001DC140` | 43 | battle outcome labels, tagged `BIM0` |
| BATTLE `0x01F64380` | 29 | **battle animation identifiers**: `btSCENE_EvaPunchA`, `btSCENE_SachielBeam`, `btSCENE_BardielBearClaw` |
| TITLE `0x01F039C8` | 17 | `Shinji Scenario`, `Asuka Scenario`, ... |
| BATTLE `0x01F64680` | 16 | character names, read by `func_01F5A6E0` |

## What they are not

The `btSCENE_*` table looks like it should name functions -- they are real C
identifiers -- but there is **no parallel function-pointer array**: I checked
every alignment within +/-116 bytes of it and found no run where 5 or more
words are function starts. So it is an id->name table for logging, not a
dispatch table, and it cannot be used to name code.

Same for the rest: these tables name *data*, not functions. Their value is
that they say what an id means, which is what you need when reading a function
that switches on one.
