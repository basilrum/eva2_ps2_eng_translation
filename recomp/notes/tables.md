# Function-pointer tables

Found by scanning for runs of consecutive words that are function starts.
`tools/string_tables.py` does the string equivalent; this list is kept by hand
because the useful part is which ones are REAL.

## The trap: most big tables are stubs

The largest function table in the game is 992 entries in `fcim.c`
(0x01F81D78) and it looks like a goldmine. It has **3 distinct targets**: 990
of the slots point at the same 24-byte stub, with real handlers only at
indices 0 and 1. Naming 992 functions from it would have invented 990 names
for one function.

So always count distinct targets before treating a table as a naming source:

    table          n    distinct   unit
    0x01F81D78    992      3       fcim.c          <- stubs
    0x01F73194    118      5       btattack.c      <- stubs
    0x01F6E778     27      1       btdemoc.c       <- stubs
    0x001DBE00     43     37       gmsave.c        <- real
    0x01F81380     54     50       fcsp.c          <- real
    0x00207464     63     58       gmdebug.c       <- real
    0x001DBBE4     16     16       cpparams.c      <- real

## datainitalfunclist -- 0x001DBE00, proven

The one table whose identity is established rather than guessed.

`gmSaveDataInitAll` @0x00159DA8 memsets 0x66EA0 bytes of save data, then walks
save chunks and dispatches on `chank->header.type`. Three facts line up:

  * the assert at gmsave.c:309 is `chank->header.type < Arraysize(datainitalfunclist)`
  * the code bounds-checks with `sltiu $v0, $v0, 0x2b` -- 43 entries
  * it then indexes a table at 0x001DBE00 by that value

So the array's name, address, length and index meaning are all pinned. Entries
0/1 and 33/34 are NULL, and 35-38 share one handler; 37 distinct targets over
43 slots.

A note on method: a plain run-scan reported this table as starting at
0x001DBE08 with 31 entries, because the two NULLs at the front are not function
pointers and break the run. The disassembly gives the true base. Run-scanning
finds tables; only the code that indexes them gives their bounds.

## Named arrays still unlocated

`tools/assert_glossary.py` recovers 31 array names from `Arraysize(...)` in
assert text -- `_flagfunclist`, `paramfunclist`, `playerfunclist`,
`rangefunclist`, `relfunclist`, `scenariofunclist` (all fcsp.c),
`gateway_interface_list` (fmcatgor.c), `atkdata` (btattack.c), and more. fcsp.c
does hold two rich tables (0x01F81380 with 50 distinct, 0x01F816F8 with 27),
but which name belongs to which is NOT established, so they are left unnamed.

## Locating the arrays the asserts name

`tools/locate_arrays.py` takes the 31 `Arraysize(<name>)` identifiers and finds
where each array lives, by matching the shape the code must have:

    sltiu $t, $idx, N        the element count, as a literal
    sll   $x, $idx, S        scaling the index
    addu  $y, <base>, $x     base from a lui/addiu pair

25 of the 31 are located. The candidate list is filtered two ways -- a
lui/addiu landing on a C string is an assert argument (the file name or the
expression text), and the target must read like a table rather than like code.

**What to trust.** The BASE and the COUNT are sound: the tool independently
rediscovered `imstrlist` and `datainitalfunclist`, both of which were pinned by
hand first, and its `equipdata` result at 0x01F62390 is unmistakable on sight --
"Smash Hawk", "(none)", "Sonic Glaive", the Eva weapon table.

**What not to trust.** The ELEMENT SIZE is weak. It comes from the first
plausible `sll` in the function, which is frequently scaling some other index.
`equipdata` is reported as 4-byte elements when its entries are visibly much
wider. Read the data before believing it.

**Still ambiguous.** All six fcsp.c `*funclist` arrays resolve to the same
candidate (0x01FD218C), which cannot be right for six different arrays. They
are almost certainly reached through a common structure rather than as
independent globals, so they stay unnamed rather than being assigned a base
that would be wrong for at least five of them.
