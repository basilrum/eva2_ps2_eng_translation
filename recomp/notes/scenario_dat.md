# game/S###.DAT -- per-scenario starting data

Found by searching the data tree for the starting-money figures the official
guide prints, then decoding what surrounds them.

## Format

    u32  tag      high 16 = record index, low 16 = record type
    u32  length   payload bytes
    ...  payload  padded to a 4-byte boundary

**All 28 files parse exactly**, each consuming everything but an 8-byte
terminator. That is what makes the format certain rather than merely plausible
-- a wrong guess would desynchronise and fail long before the end.

Every file holds **16 records of each per-character type**, one per character,
and the ordering is stable across files.

## Record types

    type  2   28000 B   per character -- THE MEMORY AREA, see below
    type  4   5 x u16   the five condition stats -- exactly the five the status
                        screen shows: hunger, hydration, sleepiness, WC, bath
    type  5   4 x u16   skills: (unused, information, administration, close
                        combat)
    type  7   u32       starting money
    type 27   2 x u32   256 records = 16 x 16, so a character-by-character
                        matrix
    ~30 more types, mostly one-off scenario settings

## How the indexing was confirmed

Not by assuming the guide's column order. One character has a distinctive
99/99 skill pair, and **that pair sits at index 15 in 24 of the 28 files** --
the other four presumably being scenarios he does not appear in. A stable
index across two dozen files is evidence; a matching column order in one
photograph would not have been.

The first four indices also read correctly against the guide's per-scenario
starting skills, including a 40/50/60 that is distinctive.

## Which file is which scenario -- SOLVED

TITLE.BIN holds the answer at **0x01F03B88**: 54 alternating entries pairing a
filename with its display name. **The file numbers are not the scenario
order**, which is why per-character values refused to line up at first:

    s001 Angel Attack          s006 Another World
    s002 Asuka Arrives         s008 Toji Again
    s003 Rei, Beyond the Heart s009 VS. SEELE
    s005 Women's Battle   <--  s007 Angel Buster      <--
    s004 Final Messenger  <--  s010 Shibamuratic Balance
                               s011 Instrumentality

s004 and s005 are swapped relative to story order, and s007/s008/s009 run
9-7-8. s012-s027 all share one name in Japanese too, so that is the game's
own doing and not a translation slip.

## Character indices -- 6 of 16 confirmed

Confirmed by matching a unique skill triple against the player-character
skills the guide lists per scenario:

    idx  1   Shinji      idx 11   Kaji
    idx  2   Asuka       idx 13   Toji
    idx  4   Misato      idx 15   Kaworu
    idx  5   Gendo

**Index 15 is the strongest of these.** It reads 99/99/0 in every scenario
except Angel Buster, where it drops to 50/50/0 -- and Angel Buster is exactly
the scenario in which that character becomes the player, with exactly those
skills in the guide. A value that changes in precisely the one file where it
should is much better evidence than a value that merely matches.

Indices 1 and 3 both hold 10/10/0, which the guide gives to two different
characters, so they cannot be told apart on skills alone; 1 is taken as Shinji
by convention and 3 is unproven. The remaining nine are unidentified.

## What is NOT established

  * the identity of indices 3, 6-10, 12, 14 and 16.
  * that type 27 is the interpersonal-evaluation matrix. 16 x 16 with two
    words each is suggestive and nothing more -- a direct search for the
    guide's evaluation triples as signed bytes found nothing, so either the
    layout differs or those numbers live elsewhere.

`toolkit/scenario_dat.py` parses and dumps these files.

## Type 2 is the memory area -- 1400 slots of 20 bytes

28000 bytes divides many ways, so the stride was found from the data rather
than from arithmetic: the same 4-byte value recurs at a **20-byte** pitch, and
at that stride the used slots are contiguous from index 0, which is how a
record array fills. 28000 / 20 = **1400 slots** per character, of which
542-647 are in use in S001.

    +0x00  u32   probably a timestamp -- see below
    +0x04  u32   the same value in 97% of consecutive slots
    +0x08  u32   likewise, 94%
    +0x0C  u32   85%
    +0x10  u16   a small id, roughly 1..60
    +0x12  u16   often, but NOT always, a multiple of 9 (507 of 647)

**+0x00 is most likely a clock.** Across consecutive used slots it strictly
increases 29% of the time and strictly decreases only 5%, with the remaining
66% holding the same value -- many memories share a tick. A six-to-one bias
towards increasing is what a timestamp looks like when entries are appended in
batches.

**Correction, and a warning about the statistic that produced it.** An earlier
pass here reported +0x00 as "94.9% non-decreasing" and +0x04 as "98.6%
descending", and concluded that the array was held sorted by memory strength,
matching what the guide says about how memories are stored. **That conclusion
was wrong.** Both percentages were dominated by *equal* values: +0x04 is the
same in 97.2% of consecutive slots, so calling it "descending" was measuring
ties, not order. Nothing in this record is sorted -- the strongest strictly
decreasing field manages 18%.

So the guide's "sorted by strength" describes what the engine does in RAM, or
some other structure; it is not visible in the on-disc data. The lesson worth
keeping is that *non-decreasing* and *non-increasing* are both near-100% for a
column of mostly-identical values, and neither is evidence of sorting. Count
strict inequalities.

Not identified: +0x04..+0x0C, and what +0x10 and +0x12 mean.

## Where the interpersonal evaluations are NOT

Ruled out by inspection, so the search does not get repeated:

  * types 3, 6, 8 and 9 -- the per-character arrays of the right sort of size.
    Their values are 0..3 and 52, nowhere near the -30..+96 range the
    evaluations use.
  * type 27 -- 256 records is the right shape for 16 x 16, but each holds only
    a `(index, value)` pair, and one value cannot carry the three separate
    scores that friendship, love and affection need.
  * a byte-level search of the whole data tree for a run of the guide's
    evaluation triples, as signed 8- and 16-bit values, found nothing.

## The code confirms the format, from the other side

`datainitalfunclist` (SLPS 0x001DBE00, 43 entries) is indexed by
`chank->header.type` -- "chank" is *chunk*, and its types are exactly the
record types in these files. So each handler can be read against the payload
shape derived from the data, and the two agree.

`gmSaveChunkMoney` @0x0015A048 is the whole format in eight instructions:

    lw   $a1, 8($a0)      payload
    lhu  $a0, 2($a0)      character index
    jal  gm_money_set

It takes the character index from the **u16 at +2**, which is the upper half of
the tag word -- confirming `tag = idx<<16 | type` from the code, having derived
it from the data.

The loop bounds line up too:

    type 4   handler iterates 5 times   payload 10 B = 5 x u16   condition stats
    type 5   handler iterates 4 times   payload  8 B = 4 x u16   skills
    type 2   no loop, bulk copy of      payload 28000 B          memory area
             (pointer, length)

Two independent derivations -- record sizes measured off the data, iteration
counts read out of the code -- meeting on the same numbers. That is what makes
the format settled rather than merely consistent.

Handlers named so far: types 2, 4, 5 and 7, plus the four setters they call.
The other 35 entries in the table are unexamined but trivially reachable the
same way: index the table by record type and read the handler.
