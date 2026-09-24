# evseq.c -- the event sequencer

297 functions, the largest translation unit in the game, and the one that has
been "the EVS script interpreter, not located" for a long time. It is located
now, and the reason it was hard to find is that **it is not a bytecode VM**.

## The context object

One global pointer holds everything:

    ctx = *(void **)0x001DE41C

Field use, counted across all 188 functions that touch the global (loads and
stores tracked through the register that actually holds the pointer, not any
register with the same offset):

    +0x00   request struct           62 functions read it
    +0x04   caller-supplied argument
    +0x08   .har archive handle
    +0x0C   .evs buffer
    +0x10   .evs size
    +0x14   count, from *(buf+4)
    +0x18   script body, = buf+8
    +0x20   PROGRAM COUNTER          119 loads / 91 stores  <- the hot field
    +0x3C   result/status            12 stores, 2 loads
    +0x40   callback, set by Create

## The .EVS file

`Create` @ 0x00170390 builds the path, loads it, and validates it:

    +0x00  char magic[4]  ".EVS"   memcmp'd, 4 bytes -- a real format magic
    +0x04  u32 count              -> ctx->0x14
    +0x08  body                   -> ctx->0x18

The path comes from a 10-case switch (jump table at 0x0020DF30) on the event
category, each case picking a directory prefix:

    0 f    1 bs   2 ba   3 bb   4 bk
    5 n    6 a    7 s    8 e    9 d

built as `sprintf("%s%3.3d", prefix, id)`, then `event/<name>.har`, then
`<name>.evs` inside that archive. Categories 2 and 9 skip the archive load.

## Why there is no opcode table

There isn't one, and that is not an oversight -- it was the wrong thing to look
for. Checks that came back empty:

  * no function-pointer table anywhere in the binary covering the handler range
    (exactly 2 words in the whole file point at one, both isolated)
  * the 93-case switch at 0x0020F5D0 is not it: 93 cases sharing 288 bytes of
    target space is ~3 bytes per case, so each case only loads a constant

What the ~120 small functions in 0x00172800-0x00177000 actually are is script
**primitives**, and they all have the same shape. 0x00172D78, in full:

    ctx = *0x001DE41C;
    if (ctx->request->0x18 == a2)  ctx->pc += a0;
    else                           ctx->pc += a1;
    return 1;

That is `if (field == value) goto then; else goto else;` with both branch
targets passed as **relative deltas on the program counter**. 0x00173F58 is the
same with a compound test (`req->0x18 == 11 && req->0x10 == 4`).

So the sequencer has a real PC and real branches -- it just dispatches by
calling these helpers directly rather than through a table.

## How a step is dispatched -- SOLVED

Two functions in restore.c give the whole answer.

`evsStep` @ 0x0016DAA8, in full:

    ctx = *0x001DE41C;
    return ctx->buffer + ctx->body[ctx->pc];

So `ctx->0x18` is not the script text -- it is an **array of u32 offsets**
indexed by the program counter, each relative to the start of the buffer.

`evsIsOp1` @ 0x0016DBA8, in full:

    return *(u16 *)evsStep() == 1;

Every record begins with a **u16 opcode**, and the sequencer recognises opcodes
with a chain of one-predicate-per-opcode functions. Six are decoded so far:

    opcode   1  evsIsOp1   @0x0016DBA8       opcode 144  evsIsOp144 @0x0016DC70
    opcode 140  evsIsOp140 @0x0016DBD0       opcode 145  evsIsOp145 @0x0016DC48
    opcode 141  evsIsOp141 @0x0016DBF8       opcode 146  evsIsOp146 @0x0016DC20

The interpreter loop is at **0x001725C8** (func_scan merged it into 0x00172538,
which is really four functions -- three tail-call stubs then this one):

    pc = ctx->pc; ctx->pc = pc + 1;
    for (i = 0; i < n; i++) {
        ctx->pc = pc + 1 + i;
        if      (evsIsOp1())   r = handler_171438(rec[1], rec[2], rec[3], rec+0x10);
        else if (evsIsOp140()) r = handler_175DF8(rec->4, rec+8);
        else if (evsIsOp141()) r = handler_175EB8(rec->4, rec+8);
        else if (evsIsOp146()) r = handler_176748(rec->4);
        else if (evsIsOp145()) r = handler_176710(rec->4);
        if (!r) return 0;
    }
    ctx->pc = pc + 1 + n;

## The file format, validated against all 374 archives

    +0x00  char  magic[4]   ".EVS"
    +0x04  u32   count
    +0x08  u32   offset[count]      indexed by the PC, relative to +0x00
    ...    records, each  u16 opcode

    op 1 (dialogue, half of all steps):
      u16 opcode = 1
      u16 length          record length in bytes
      u32 speaker id
      u32 flags
      u32 voice id        0 when the line is silent
      char text[]         NUL-terminated

Checks that passed, on the real game data:

  * 370 of 370 archives parse with every offset in range. The 11 that first
    looked malformed are simply EMPTY scripts -- an 8-byte header, count 0.
  * 19,584 steps, 141 distinct opcodes, densely filling 1..155.
  * the six opcodes decoded from the predicates are all in the top eight by
    frequency -- the ELF and the data agree without being fitted to each other.
  * all 9,869 op-1 records: the declared length fits before the next step,
    zero overruns. Padding is always 4..7 bytes, exactly
    `4 + ((4 - (off+len) % 4) % 4)` -- a 4-byte gap, then 4-byte alignment.

`tools/evs.py` dumps a script or prints an opcode histogram over a tree.

## How the other 135 opcodes are handled

Not by a bigger predicate chain. Searches that came back empty, across all six
binaries:

  * **no switch on the opcode exists anywhere** -- no function that calls
    evsStep contains a computed jump
  * only **6 opcode values are ever compared** in the whole game (1, 140, 141,
    144, 145, 146), by the six predicates
  * the five overlays never call evsStep and never load the context global, so
    nothing is hiding in BATTLE/FREE/TITLE/ENDING/MINIGAME

There are **11 interpreter loops** (found by taking the predicates' callers):

    0x0016EBD0  0x0016EE90  0x0016F098   restore.c, opcode 144
    0x00170A28  0x00171D10  0x00171DE8  0x00171F70  0x00172108
    0x001722E0  0x001728A8               evseq.c,   opcode 1
    0x001725C8                           evseq.c,   ops 1/140/141/145/146

What they have instead of a table is **indirect calls**. 0x00172108 takes a
callback in a3 and invokes it per step (`jalr $fp`), and 0x0016DEB0 /
0x0016DEF0 call function pointers hanging off the event object itself:

    jalr  ctx->request->0x0C->0x20
    jalr  ctx->request->0x0C->0x2C

So the event object carries its own handlers, installed by whoever started the
event. The opcode in the record is a *tag for those handlers* to interpret, not
an index the sequencer dispatches on -- which is the real reason no opcode
table exists, and why looking for one kept failing.

## Still open

What each of the 135 remaining opcode values means. That now requires reading
the installed callbacks per event type rather than finding one table -- more
work than a lookup, but no longer a mystery about the architecture.

## Also closed

The 93-case switch at 0x0020F5D0 is `SidToSeSelect` @ 0x00179D78: a switch on a
scene id that picks one of the 152-byte `SidToSe*` mappers and its entry count
(each case loads a pointer 152 bytes on from the last). It has nothing to do
with script opcodes.

## Named from trace strings

43 functions here named themselves in their own debug output, including a
contiguous run of 152-byte `SidToSe*` scene-to-sound-effect mappers
(0x00178588-0x00179C18): Free1-10, Battle03..95, Angel, Start01..11, End1-4.

## How an event is started -- the request struct

Two developer harnesses in the debug menu build an event from nothing and run
it, which documents the entry point better than any caller in the game does:

    dummyBattleSyncTest  @0x00103888
    dummyNonagTest       @0x00103460

Both do the same three allocations, all on the stack, all memset to zero:

    request   0x74 bytes
    handlers  0x4C bytes   -> stored at request+0x0C
    result    0x1C bytes   -> passed alongside the request

then call `evseqRun` @0x0016FE28 with (request, result, x).

Request fields confirmed against `evseqCreate`, which reads them:

    +0x00  u32  category   0..9, bounds-checked with sltiu 10, indexes the
                           jump table at 0x0020DF30 that picks the directory
                           prefix (f / bs / ba / bb / bk / n / a / s / e / d)
    +0x04  u32  event id   formatted with "%s%3.3d"
    +0x0C  ptr  handlers   the 0x4C-byte struct whose +0x20 and +0x2C are the
                           function pointers evsCallHook20 / evsCallHook2C
                           invoke -- this is where per-event behaviour lives
    +0x48  ptr  callback   set by dummyNonagTest       (0x00103420)
    +0x4C  ptr  callback   set by dummyBattleSyncTest  (0x00103880)

After the run the harness printf's the first word of the result struct.

A note on method: an automated scan for "address-load of a function, then a
`sw` at +0x20/+0x2C" reported both harnesses as installing callbacks at those
offsets. Reading the code shows that is wrong -- the store at +0x20 is a
constant 2, and the function pointer goes to +0x48/+0x4C. The scan paired an
address load with an unrelated nearby store. The offsets above come from
reading the disassembly, not from that scan.


## Cross-check against the existing translation tooling

`nge_2_re-master/tools/evs.py` already parses EVS -- it came from the PSP port
and carries a 256-entry per-opcode parameter table. So the container format
recovered above was, in part, already known to the project. Worth stating
plainly rather than presenting it as new.

What the independent PS2-binary derivation is good for is checking it, and the
two agree exactly on the container: magic, count, offset table, then per entry
a u16 type and u16 size. Two further checks against all 374 PS2 archives:

  * **its HAS_CONTENT_SECTION is correct for PS2.** Every opcode in it that
    occurs in PS2 data does carry text (0x01 88%, 0x8C 84%, 0x8D 69%,
    0x8E 93%, 0x95 100% -- the shortfall from 100% is short lines, not
    mis-typing). 0xA3 never occurs in PS2 data at all; it looks PSP-only and
    is harmless.
  * **no opcode is missing from it.** Sweeping every other opcode for
    text-shaped tails found none above 50%. So no dialogue is being silently
    parsed as parameters and dropped -- which was the failure worth ruling out,
    since it would corrupt the translation without any error.

The opcodes the PS2 sequencer explicitly tests (0x01, 0x8C, 0x8D, 0x90, 0x91,
0x92) are a different set from the text-bearing ones, and that is expected:
being recognised by a predicate is not the same as carrying a content section.
0x90/0x91/0x92 carry no text, consistent with both.

## imstrlist -- the game names its own IM scenes

The assert in `btim319.c:652` is `imid>0 && imid<Arraysize(imstrlist)`, and the
function holding it indexes a table at **0x01F5B278** in BATTLE.BIN by IM id,
then sprintf's the two words it finds as `"%s\n%s"`. So:

    imstrlist[imid] = { char *line1, char *line2 }     956 entries, 8 bytes each

Every entry is populated and **already in English** -- this is the table the
player's action menu is drawn from, so the translation pass covered it.

It is worth more than that suggests. Both overlays hold units named after an IM
id (`../im/im0423.c` in FREE, `btim003.c` in BATTLE -- the same id space, which
`btim003.c`'s own `im003_arg_dump` string confirms), and the table says what
each one *is*:

    ../im/im0423.c    NPC Asuka Only / Close to Hikari 1
    ../im/im0915.c    Their work / Cut into talk
    ../im/im0331.c    System: / After harmonics
    btim660.c         Battle … / ...An Angel?

That is the game's own description of the scene, not an inference. 16 IM units
in FREE and 3 in BATTLE now carry theirs in `notes/codebase_map.txt`, and
`tools/imstrlist.py` dumps or looks up the whole table.
