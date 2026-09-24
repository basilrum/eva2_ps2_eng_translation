# NGE2 recomp

Working toward a named, understood reconstruction of *Neon Genesis Evangelion 2*
(PS2, SLPS-252.99). Started 2026-09-03, off the back of the English translation
in `~/Downloads/nge_2_re-master/`.

## Where the leverage is

The ELF has **no symbol table at all** (0 symbols), but the asserts are very
much alive — 684 call sites reach the panic handler, and their `__FILE__` and
expression text survives in full. The code that passes those strings still
loads their addresses, which makes the original translation-unit layout
recoverable without any symbols.

(An earlier version of this file said the asserts were "compiled out". They are
not; retail merely fails *silently*, doing a deliberately misaligned store and
spinning. Set bit 0x1000 in the debug word at 0x001D3910 and a failed assert
prints its own expression, file and line instead — see `notes/debugflags.md`.)

That is what `tools/tu_map.py` does, and it is the reason this project is
tractable at all. It already took `choose.c` from "somewhere in 2 MB of
anonymous MIPS" to one function at `0x1511F0` in about three steps.

## Scale (measured, not guessed)

| | functions | notes |
|---|---|---|
| `SLPS_252.99` | ~4,410 | 201k instructions of `.text` |
| `prog/BATTLE.BIN` | ~1,827 | |
| `prog/FREE.BIN` | ~2,552 | |
| `prog/TITLE.BIN` / `ENDING.BIN` / `MINIGAME.BIN` | ~99 | |
| **total** | **~8,888** | ~522k instructions |

Between *SM64* and *Ocarina of Time* in size. A full matching decomp is a
multi-year, multi-person job; a *useful partial* — a named function map and the
UI/text layer understood well enough to patch freely — is not.

## Load addresses

    SLPS_252.99      0x000FF000     (vaddr = file offset + 0xFF000)
    all 5 overlays   0x01F00000     they share one slot

The overlay base is solved, not assumed: BATTLE and FREE each land on it
independently (167 and 95 address loads resolve exactly onto a `__FILE__`
literal, against 90 and 42 for the next candidate), and under it every unit
range sits inside its own image with zero overlaps in ascending order — which
is what a linker produces. An earlier note of mine said `0x1ECDF20`; that is
wrong, and under it the units would run past the end of the image.

## What is hard

* **No symbols.** Every function name has to be inferred.
* **VU microcode.** `.vutext` is 56 KB of VU1 code, plus DMA chains and GS
  packets. This is where PS2 decomps stall; there is no `libultra` to lean on.
* **Toolchain.** Flags say `mips3, eabi64`; matching output byte-for-byte means
  identifying the exact SN Systems / EE-GCC build.
* Static recompilation (the N64Recomp approach) is not viable on PS2 yet, for
  the same VU/GS reasons.

## Layout

    tools/tu_map.py          bound translation units via their __FILE__ literal
    tools/func_scan.py       function boundaries, attributed to those units
    tools/unit_order.py      full link order from .rodata; narrows each function
    tools/split_gaps.py      REJECTED call-graph splitter, kept for the record
    tools/validate_split.py  the hold-out test that rejected it
    tools/rodata_anchor.py   measures the rodata-reference hypothesis (97.7%)
    tools/anchor_expand.py   applies it; the current best map
    tools/whatis.py ADDR     look an address up (add --disasm)
    symbols/tu_map.json      179 translation units bounded
    symbols/functions.json   10,252 function candidates
    symbols/unit_order.json  248 units in link order + per-function windows
    symbols/unit_windows.json   rodata-anchored map
    symbols/unit_windows2.json  CURRENT BEST -- + .data, 71% on one .c file
    notes/*.txt              the same, readable

## Where the map stands

    179   translation units bounded
 10,252   function candidates
  6,586   directly called (`jal`) -- the firm LOWER bound on the real count
  1,148   pinned to exactly one .c file
  7,403   narrowed to two adjacent files
  8,551   placed in total (83%)

The 10,252 is an over-count: it unions `jal` targets with post-`jr $ra`
boundaries, and the latter over-fires on functions that have several returns.
The truth is between 6,586 and 10,252. Where the two sources agree -- 83% of
`jal` targets in the ELF -- an entry is certain.

Attribution is only 11% *pinned* because a unit's `__FILE__` references pin
just the span between the first and last of them. But the linker emits units
contiguously, so anything in the gap between unit i and unit i+1 belongs to one
of the two; those are reported as `a.c|b.c` rather than dropped or guessed.

### Validated against known ground truth

    0x00112F10  camera angle-limit setter   -> PINNED to ../hahig/hhcamera.c
    0x001511F0  selection-menu centring     -> narrowed to choose.c|gmmemory.c

The first is a semantic check, not just a mechanical one: the function the
freecam patch hooks lands in the camera module. The second was found by hand
earlier from `choose.c`'s `__FILE__` reference, and the boundary scan
independently recovers the same function start.

## Disassembling

Use capstone with **`CS_MODE_MIPS64 + CS_MODE_LITTLE_ENDIAN` and
`skipdata=True`**. Without `skipdata` the R5900's extra opcodes abort the sweep
after a handful of instructions — an easy way to convince yourself a region is
empty when it is not.

## A call-graph split was tried and REJECTED

`tools/split_gaps.py` assumed a gap between units A and B has a single split
point, and scored candidate splits on the call graph. It "resolved" 6,109 of
7,403 -- and then failed its own hold-out test.

`tools/validate_split.py` manufactures synthetic seams out of pinned functions
(blank the labels either side of a real unit boundary, re-run the same scoring,
see if the split goes back where it belongs):

    per-function accuracy   402/636 = 63.2%    (coin flip is 50%)
    split placed exactly    10/53   = 18.9%

Not good enough to name anything from. Output kept only as
`symbols/functions_split.REJECTED.json`.

**Why it failed:** 69 of the 248 source files have literals that no address
load ever references, so those units are unlocated and sit INSIDE the gaps. A
gap is not "A or B" -- it can contain whole unnamed units. The model was wrong
by construction.

## What replaced it: link order from .rodata

The compiler emits a unit's .rodata in the same order as its .text, and here
that holds exactly -- ranking located units by literal offset against code
address gives **Spearman rho = +1.000 with zero inversions** over 5,296
pairwise comparisons.

So literal order IS link order. `tools/unit_order.py` puts all 248 files in
sequence and narrows each function to the ordered window of units between the
nearest anchors either side. This is correct by construction rather than
probabilistic:

    2,795 functions narrowed to exactly ONE unit
    median window 2 units for the rest

Worked example -- the selection-menu centring function at `0x001511F0` comes
out as `choose.c | gmmemory.c`. That is a genuine two-way ambiguity, and an
earlier note of mine asserting it was `choose.c` was a guess, not a finding.

## rodata references as anchors -- VALIDATED, 100%

A unit's .rodata is one contiguous block, and the blocks are in link order. So
a function's reference into .rodata should land in its OWN unit's block. It
does, measured on pinned functions: **341/349 = 97.7%** per reference, 98.6%
within one unit.

Taking the majority across each function's references removes that residual
error entirely. Hold-out test (`the __FILE__ pin ignored, rodata refs only`):

    SLPS_252.99       135/135
    prog/BATTLE.BIN   141/141
    prog/FREE.BIN      74/74
    TOTAL             350/350 = 100.0%

Unlike `__FILE__` references, rodata references also land in the blocks of the
69 units that no address load ever names -- which is exactly what was missing.
`tools/anchor_expand.py` applies it:

    anchors    1,148 from __FILE__  ->  2,150 (1,002 new)
    functions  2,795 pinned to one unit  ->  7,137 (71%), median window 1

The selection-menu centring function at `0x001511F0` now collapses to
`choose.c` -- derived from the anchor structure, not assumed.

## .data -- validated but nearly worthless here

Same idea applied to `.data`: bootstrap an offset -> unit map from the already
anchored functions, then use it on the rest. It is sound -- hold-out **94.7%**
(270/285) -- but it only resolves **+27 functions**, 7,137 -> 7,164.

The reason is that .data statics are largely shared, and the functions that
touch them were mostly already anchored through .rodata. Worth having, not
worth building on.

## Where the method tops out

**57% of functions land on exactly one .c file.** (This read 71% until two
attribution bugs were found and fixed -- see "Two corrections" below.) The remaining ~2,900 are
functions that reference no string and no identifiable static -- pure logic,
sitting between two anchors of *different* units. Nothing in the data
distinguishes them; resolving those needs a different signal, not more of this
one.

Contiguity is already exploited: two anchors of the SAME unit collapse
everything between them automatically.

## Two corrections that cost 14 points of coverage

Both were caught by sanity-checking the OUTPUT, not the method.

**Unbounded edge windows.** Outside the anchored range the window has no bound
on one side, and collapsing it to the first/last unit in link order swept the
whole head and tail of each image into one file: 1,296 functions across 256KB
of tail all became `chara.c`, and 150 across 420KB of head became
`../im/test.c`. Those regions contain units with no `__FILE__` literal at all,
which this method cannot see. Functions outside the anchored range are now
marked `outside` and left unattributed. Cost: 70% -> 56%.

**Non-monotonic anchors.** Units are contiguous and ordered, so anchors must be
non-decreasing in unit index as address rises. A few were not -- functions
referencing a string in another unit's block. Keeping only the longest
non-decreasing subsequence drops them. The 100%% hold-out had not caught this
because it only sampled functions pinned by `__FILE__`, which cluster where
literals are referenced; it was a biased sample.

Sanity check that now passes: median unit span **2,544 bytes** across 206
units, largest 51KB. Before the fixes the largest was 420KB, which is not a
.c file.

## Function list

    10,252 candidates
       331 dropped -- provably branched into from the function above
     8,115 REACHED  -- jal target, stored pointer, or address taken
     1,806 kept but unreferenced -- flagged, not trusted

Pruning by SHAPE was tried and rejected: 74-85% of known-good `jal` targets
start with a stack adjust, but so do 58-72% of the questionable ones, so the
test cannot separate them. Reachability can. An early version missed the
address-taken class (`lui`/`addiu` then `jalr`) and wrongly dropped 240.

## Naming -- real names recovered

Two sources in the binary state names outright.

**Assert sites.** The asserts were compiled out of the *messages* but not the
*calls*: each site passes `__FILE__`, the line number, and the failed
expression as text. `tools/asserts.py` extracts **860 of them, 838 with an
expression** -- `'self->objtype == HHCA_OBJTYPE'`, `'dir_max<DIR_TABLE_MAX'`,
`'ret==SCECdComplete'`. That is the best naming evidence in the image: it names
variables, constants, struct fields and states each function's contract. A few
use the `assert(p && "func_name: message")` idiom and give the name directly.

**Identifier strings.** Some functions reference a string that is an identifier
rather than a message -- `hhMemFree`, `btIm319Test`, `fmCharaWarp`. Referencing
such a string is not proof it is that function's name (it could name a callee),
so each candidate is checked against the unit the function was independently
attributed to, and a name claimed by two functions is dropped rather than
guessed. **36 names survive**, e.g.

    0x00113BD8  hhFileClose             ../hahig/hhfile.c
    0x00119240  hhMemFree               ../hahig/hhmem.c
    0x01F19AF0  btIm319Test             btim319.c
    0x01F4C130  fmCharaWarp             fmchara.c

`btIm319Test` landing in `btim319.c` is the kind of agreement that makes these
trustworthy -- the name and the file were derived by completely separate means.

## The assert files validate the whole map

Each assert states the file its function is in, which is an INDEPENDENT check
of the attribution. Excluding functions pinned by their own assert (where
agreement would be circular):

    attributed by rodata anchor : 376/386 = 97.4%
    overall (non-circular)      : 379/391 = 96.9%

So the 57% of functions that carry a unit are right about 97% of the time.

## Three independent validations

The attribution was built from `__FILE__` and `.rodata` references. These
three checks use signals it never consumed, so they are tests rather than
restatements:

    assert FILE agrees with the attributed unit   379/391 = 96.9%
      (functions pinned by their own assert excluded -- circular)
    assert LINE order rises with address, per file 754/760 = 99.2%
      (random ordering would be ~50%)
    rodata-anchor hold-out, __FILE__ pin ignored  350/350 = 100%
      (biased sample: only functions that HAVE a __FILE__ pin)

Line-order inversions flag just 3 files -- `btmemory.c` (4 of 10 pairs),
`btinfo2.c`, `gmaround.c` -- which are where to look first for a
misattribution or a mis-associated assert.

## Export

`tools/export.py` writes everything into formats other tools take:

    export/symbol_addrs.txt   splat / spimdisasm style
    export/ghidra_import.py   applies names AND attaches the evidence
                              (unit, asserts, reachability) as a plate
                              comment on each function -- self-contained,
                              needs no other file
    export/*.csv              flat per-binary tables

## A correction the map produced

`0x001511F0` was reported earlier -- including in a pnach that shipped -- as
the selection-menu TEXT centring. **It is not.** Disassembled against the
symbol map it makes three `ui_draw_sprite(handle, x, y)` calls whose y is
offset by a value from a 40-entry table at `0x001DA310`:

    0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,8,8,7,7,...,1,1,0,0,0,0

a triangle wave of amplitude 8 -- an animation. So it draws the menu's
**bobbing cursor / scroll arrows**. The centring arithmetic is real and the
patch works; it just moves the arrows. The pnach now ships with both lines
commented out and the correction written into it.

This is what the map is for: the claim survived weeks because nothing could
check it, and the first real read of the function overturned it.

## The 2D draw path, now understood

    ui_draw_sprite     0x0014B5A0   (handle, x, y) -> resolves both, then draws
      ui_resolve_x     0x0014FBE8   if (x == 0x4000) x = (512 - w)/2
      ui_resolve_y     0x0014FC10   if (y == 0x4000) y = (448 - h)/2

`0x4000` is a "centre me on screen" sentinel and 512x448 is the framebuffer.
Every sprite drawn through this path accepts it, so these two functions are
the single place that decides where anything centred lands.

Also identified: `choose_draw_cursor_arrows` (0x001511F0),
`cursor_bob_table` (0x001DA310), `choose_text_draw_fmt` (0x0014D238, a
printf-style wrapper into hhtext.c) and `choose_text_set_colour` (0x0014D618).

## SOLVED: where the menu text position is set

Followed through the slot table at `0x002CB5A0`, which turned out to front a
whole family of ~21 small wrappers -- one per text property. The one that
matters:

    choose_text_set_pos   0x0014CEB8
      choose_text_width   0x0014D528   (charW + gap) * nchars - gap
      choose_text_height  0x0014D5A0

    void choose_text_set_pos(int slot, int x, int y) {
        if (slot == -1) return;
        if (x != 0x8000) {                    // 0x8000 = leave this axis alone
            if (x & 0x4000)                   // 0x4000 = centre this axis
                x = ui_resolve_x(x, choose_text_width(slot));
            obj->x /* +0x80, float */ = (float)x;
            obj->flags /* +0x104 */  |= 0x00440000;
        }
        if (y != 0x8000) { ...same, (448 - h)/2 -> +0x84... }
    }

Its callers include **window.c and choose.c** -- the dialogue window and the
selection menu, which is exactly the pair we were after.

Above it sits `choose_set_menu_pos` (0x0014E900), which hands the same x,y to
the menu background, the text and a third element. It is reached only through
a function pointer, so the coordinates originate in the script layer; the
chain ends at that API boundary.

**The practical result**: the two instructions that carry the resolved
coordinate into the register about to be stored --

    0x0014CF08  move $s0,$v0  ->  addiu $s0,$v0,N    X
    0x0014CF64  move $s1,$v0  ->  addiu $s1,$v0,N    Y

nudge every piece of text that asked to be centred, and nothing else. The
pnach ships with the encodings worked out and commented off.

## 1,289 of the "functions" are not game code

The 256KB after the last game translation unit references `sceSifMCallRpc`,
`libpad: Module version mismatch`, DMA registers (`D1_TADR`, `D2_MADR`), MPEG
decoder messages (`slice_start_code(0x%08x) out of range`, and Sony's own typos
`skiped macroblock in I picure`) and libc float formatting (`Inf`, `e+%d`,
`0123456789abcdef`).

That is the linked Sony SDK and C runtime. It explains why attribution can
never reach it -- there are no game `__FILE__` literals in there -- and in a
decomp you would **link the real library instead of decompiling any of it**.

    9,921 functions total
    1,289 Sony SDK / libc
    8,632 actual game code

`tools/classify_sdk.py` marks them. It also guesses a per-library split
(libmpeg / kernel / libdma / libc / libsif / libpad) but **only 15 functions
carry direct string evidence** and the rest are labelled by nearest neighbour
across 256KB -- treat the SDK/game boundary as solid and the library
breakdown as a rough hint, no more.

The head region (0x001001C8..0x001049A0, 65 functions) is the opposite: real
game code -- debug menus, `dummyEventTest`, `movie/opening.pss`, and strings
the translation already touched -- that simply sits before the first unit with
an assert in it.

## Two more signals tried

**Assert line numbers as a ruler -- FAILED.** Bytes per source line is ~5.6
(median over 62 files) but with a standard deviation of 2.0, and more
importantly the ratio is only measurable *between* asserts. How far a unit
extends *past* its last assert is exactly the unknown, and line numbers say
nothing about it. Tested against 84 known gaps: median error 0.50, i.e. no
better than guessing the midpoint. Ruled out cheaply.

(That test also exposed a data-quality bug: `fcstate.c` reports a 33-million
line span, so at least one assert is being mis-associated by the register
window in `asserts.py`.)

**.bss references -- WORKED.** `.bss` holds file-scope statics and is laid out
in link order like everything else, but it lives past the end of the file image
so every earlier pass silently discarded references to it -- 938 of them in the
ELF, more than twice the `.data` count. Bootstrapped the same way:

    .bss hold-out   122/136 = 89.7%      +85 functions resolved

Note that is meaningfully below the `.rodata` signal's 100%, so `.bss`-derived
attributions carry more risk; they are tagged `src: bss` in the map.

## The translation pays the recomp back: 133 names from menu labels

The debug menus are tables pairing a label with the function that runs it --
and those labels are in ENGLISH because this project translated them. So they
read as descriptions rather than identifiers:

    Bardiel_VS_Unit_01   0x01F18838   btpcgen.c
    Debug_Camera_EX      0x01F252A8   freedbg.c
    Sever_power_cable    0x01F184D8   btpcgen.c
    Sprite_parenting     0x0013E8D0   ../hahig/hhprim3d.c

482 label/handler pairs, 136 unambiguous after dropping shared handlers (a
table of asset filenames all pointing at one function names nothing) and
duplicate labels. **133 applied.** They land in coherent units -- the sprite
demos in `hhprim3d.c`, the battle events in `btpcgen.c` -- which is a decent
consistency check on both the names and the attribution.

Names now: **185** (36 recovered from strings, 16 hand-derived, 133 menu labels).

## Two more ideas rejected

**Caller locality.** A C `static` function can only be called from its own
file, so "all callers agree" should imply the same unit. Measured: **65.7%**,
and even requiring five agreeing callers only reaches 80.2%. Functions here
cross file boundaries too freely. Rejected -- the other signals run 90-100%.

**Data size predicts code size.** A unit's .rodata block size vs its code
span: r = +0.72 in the ELF but +0.08 in BATTLE.BIN and +0.53 in FREE.BIN. Not
consistent enough to place boundaries. Rejected.

**Byte-identical twins across binaries** worked but is tiny: only 11 functions
appear in more than one binary, transferring 5 attributions. Two of those are
the only attribution `MINIGAME.BIN` will ever get -- it has no `__FILE__`
literals at all.

## Naming, round two: +55 from solo identifier strings

`name_funcs.py` had rejected names like `imLookDouble` because it demanded the
name's prefix match the NUMBERED filename it was attributed to -- and
`imLookDouble` in `../im/im0501.c` never will. Comparing the leading
*alphabetic* run instead (`im` vs `im`) fixes it, with assert expressions,
asset paths and prose filtered out and any string used by two functions
dropped. **55 more real developer names**, including the whole AI layer:

    fc_ai_npc_actsel_by_desire   fc_ai_state_task_start   fcAIStateResume
    fc_cron_on_init_hospital_leave                        imGoAway
    gm_savedata_initialize_statplayer

**Names now 240.**

A follow-up check found 0 cases where a recovered name's number disagrees with
a real unit -- e.g. `im0215_wait_zone_clear` sits in `im0096.c`, but `im0215.c`
has no `__FILE__` literal so it is not in the unit list at all and there is
nothing to correct to.

## What the game is made of

`notes/codebase_map.txt`, generated from the map:

    bt      battle system                    1467 functions
    fv      free-roam view (3D chara/motion)  489
    im      interaction memories (AI scripts) 475
    hh      hahig engine (Alfa System)        460
    fm      free-roam map (movement/paths)    419
    fc      free-roam AI (NPC state/desires)  357
    gm      game shell                        201
    mem/cp/sound/gs/cd                        447
    (Sony SDK / libc)                        1289
    (unattributed)                           2895

## Dispatch tables: a 98.3% signal

A run of consecutive function pointers is a dispatch table, and its handlers
are written together in one source file -- every table checked by hand had all
of its targets in a single unit. So a table whose entries are mostly attributed
can place the rest.

    dispatch-table hold-out   459/467 = 98.3%      +27 functions

Only 27, but at the accuracy of the best signal available. It doubles as
another independent check on the attribution: 67 tables across the three
binaries, and their targets essentially never straddle a unit boundary.

**A mistake worth recording:** the first run of this built on
`unit_windows4.json`, which contains the REJECTED 65.7% caller-locality data.
It reported +27 on top of poisoned input. Rebuilt from `unit_windows3`, the
last trusted state, and the rejected file is renamed
`unit_windows4.REJECTED-caller-data.json` so it cannot be picked up by
accident. Always check which input a pass is reading.

Looked for parallel label arrays beside the handler tables (which would name
every handler at once) -- there are none, and those particular handlers sit 16
bytes apart, so they are trivial stubs not worth naming.

## Names now come in four tiers -- and they are NOT equal

    RECOVERED         91   the developers' own names, lifted from strings in
                           the binary (hhMemFree, fcAIStateResume) or from
                           assert(p && "func_name: msg")
    MENU-LABEL       133   from debug menu label/handler tables. The label
                           names the ACTION, and is in English because this
                           project translated it (Bardiel_VS_Unit_01)
    HAND-DERIVED      16   read out of the disassembly, each with its
                           justification recorded in manual_names.json
    DESCRIPTIVE-ONLY 226   the single string a function references, which is a
                           HINT and often not its name at all: Memory_Pool_Block
                           is probably what the function allocates, and
                           Exceeded_Max_Available_Profile_Samples is an error
                           message it prints

**466 names total**, but only the first three tiers should be trusted as names.
The export tags every one, and the Ghidra comment on a descriptive-only entry
says outright that the string is a hint rather than the function's name.

## Reading the text engine by hand

The map is now good enough to just sit and read code. Four functions in
`../hahig/hhtext.c`, named from what they demonstrably do:

    hhtext_format_number  0x00131178  integer -> string. Switches on 'd'/'x'/'X'
                                      AND their full-width Shift-JIS forms
                                      (0x8263 D, 0x8284 d, 0x8298 x). Radix 10
                                      or 16 via divu/mfhi/mflo, +0x30 for ASCII,
                                      +7 or +0x27 for hex letter case, '-' for
                                      negatives.
    hhtext_put_char       0x00131018  the per-character emitter it drives
    hhtext_draw_string    0x00132330  main emitter; detects a Shift-JIS lead
                                      byte with (c-0x80) < 0x20 or c < 0xE0 and
                                      combines (c<<8)|next
    hhtext_parse_escape   0x00131818  handles the script's $-escapes -- it
                                      compares against 0x24 ('$'), which is the
                                      $n / $m markers the dialogue tooling uses

**The engine does not word-wrap.** Every width-shaped constant in the text
engine turned out to be character classification or an escape-code table, not a
running-width limit. The script must carry its own newlines -- which is exactly
why this project's dialogue pipeline pre-wraps to 34 cells and why `box_audit`
has to exist. That constraint is now confirmed in the code rather than inferred
from crashes.

## The biggest single win was a bug in my own scanner

Every pass paired a `lui` with its low half only 1-2 instructions later.
Compilers separate them much further. Measured on the ELF:

    narrow window (+4/+8)    4,696 address loads
    proper register liveness 9,026 address loads

**Roughly half of all address references were invisible**, and address
references are the evidence the entire attribution and half the naming runs
on. `tools/addrloads.py` now does it properly -- follow the register forward
until something supplies the low half, and abandon it if the register is
reused for something else -- and every pass shares it.

    attribution   67% -> 77% of game functions   (+873)
    developer names recovered   36 -> 154        (4x)

For comparison, the last two genuinely NEW ideas were worth +85 and +27. The
bug fix beat both by an order of magnitude.

## The engine API is now readable

Every recovered name lands in the file it should:

    hhCameraRollSet          ../hahig/hhcamera.c
    hhFileSizeGet            ../hahig/hhfile.c
    hhFontLoadByID           ../hahig/hhfont.c
    hhObjectCreate           ../hahig/hhobject.c
    hhTextureLoadFromFile    ../hahig/hhtex.c
    hhDrawLinkAdd            ../hahig/hhdrawlk.c
    hhTaskTrans              ../hahig/hhtask.c
    hhFadeStart              ../hahig/hhfade.c
    fcIMFlowExecWithScriptBackup   fcim.c

Name and file were derived by completely separate means, so agreeing on every
one of them is a strong check on both.

## Naming passes must run strongest-first

Each namer skips functions that already carry a name, so running the weakest
source first lets it claim functions a stronger source would have named
correctly. Correct order:

    apply_manual -> name_funcs -> name_from_tables -> name_solo_strings -> name_prose

Running it backwards once cost ~100 good names and inflated `prose_label` with
functions that had better evidence available.

**757 names**: 154 recovered, 139 solo-string, 133 menu-label, 20 hand-derived,
311 descriptive-only.

## The same class of bug in the assert scanner

`asserts.py` reconstructs each call's arguments by replaying `lui`/`addiu`
backwards from the call. It modelled only those two instructions -- so when a
register was set by something else (a `move`, a load), it kept a STALE constant
from further back and reported it as the line number.

Widening the window alone made it worse, which is how the bug surfaced:

    window   invalidate   sites   line-order consistency
      48       no          843        99.2%
      64       no          952        98.6%
      96       no         1154        96.4%
     128       no         1323        95.6%     <- more sites, more nonsense
      48       yes         631        99.5%
     128       yes         724        99.6%     <- chosen

With invalidation (drop a register the moment something unmodelled writes it)
accuracy holds at ~99.5% no matter how wide the window gets. Taking 724 correct
sites over 843 partly-wrong ones.

Final validation numbers, all on signals the attribution never consumed:

    assert line order vs address     908/913 = 99.5%
    assert FILE vs attributed unit   338/343 = 98.5%   (non-circular)
    dispatch-table coherence         459/467 = 98.3%

The pruner's address-taken test had the same narrow-scanner flaw; fixing it
confirmed **+144 more functions as genuinely reachable**.

## Rebuilding

    ./rebuild.sh

That exists because getting the order wrong cost real accuracy three separate
times: a pass reading the REJECTED caller-locality data; a pass crashing while
the chain carried on with stale input and reported 68% when the truth was 77%;
and the naming passes run weakest-first, letting the vaguest source claim
functions that had better evidence. The script runs everything in the only
correct order under `set -e`, and ends by re-running the independent
validations.

## The foundation had the bug too

`tu_map.py` -- which bounds every translation unit, and which everything else
is derived from -- used the same narrow `lui`/`addiu` pairing. Fixing it:

    translation units located   179 -> 219

    SLPS_252.99      70 -> 82
    prog/BATTLE.BIN  62 -> 79
    prog/FREE.BIN    45 -> 56

Four tools carried that bug (`tu_map`, `classify_sdk`, `asserts`,
`prune_funcs`) plus every anchoring and naming pass. All now share
`tools/addrloads.py`.

## Where it stands

**The live numbers are printed by `./rebuild.sh`** and written to
`notes/codebase_map.txt`; they are deliberately NOT copied here, because the
hardcoded copy went stale three separate times and twice reported a percentage
that was materially wrong. Run the script.

As of the last run: 10,915 functions, 1,308 of them Sony SDK/libc, 7,731 of the
remaining 9,607 attributed to a .c file (80.5%), 1,171 named, 9,571 reached,
219 translation units bounded.

"Reached" jumped by 701 when `prune_funcs` learned that a `j` from OUTSIDE the
function above is a tail call, and therefore a real reference. It had only ever
read `j` as evidence that a candidate was a continuation of its predecessor --
correct until the tail-call boundary fix proved tail calls are used
everywhere. 701 functions were being filed as "unreferenced" while being
called on every frame.

About 160 of those names are EE kernel syscall stubs, matched on their exact
four-instruction shape (`addiu $v1,$zero,N; syscall; jr $ra; nop`). They are
named `eeSyscall_<N>` and deliberately NOT given Sony's own names for those
calls -- the number is verifiable from the instruction, the name would be me
guessing, and a plausible-looking wrong name on a kernel call is worse than a
number the reader can look up.

`./rebuild.sh` prints this table every run, deliberately. A bare attribution
percentage has been wrong twice, in opposite directions:

  * **Denominator.** Attribution means "which game .c file is this in", so the
    1,308 SDK functions can never be attributed and must not be counted. They
    are one contiguous run at 0x001863B8-0x001C4A50, and including them turned
    a real 80.6% into a reported 70.9%.
  * **Numerator.** `func_scan` used to end functions only at `jr $ra` and miss
    TAIL CALLS, so ~1,048 functions were glued onto whichever function
    tail-called into them. The old "77%" was measured against a function list
    missing about a tenth of the program.

Both are fixed, and the two effects were pulling opposite ways, which is
exactly why neither showed up as an obviously wrong number.

## How accurate is the attribution, really

Two independent checks run on every `./rebuild.sh`, both on signals the
attribution never consumes:

    assert line ordering          933/938  = 99.5%
    names vs. units               105/108  = 97.2%

The second is new and is the sharper of the two: attribution comes from
`__FILE__` windows and linker layout, naming comes from strings, asserts, menu
tables and trace output, and neither pass ever reads the other. Where a
recovered name encodes its own module (`hhMemFree` -> hhmem.c) the two can be
compared at FUNCTION granularity, which the assert check cannot do -- that one
only measures ordering.

Getting a trustworthy number out of it took two corrections, both in the
CHECK rather than the map:

  * engine filenames abbreviate by dropping interior letters, not just
    trailing ones (`hhdrawlk.c` <- hhDrawLink), so the match has to accept a
    subsequence of each word. A prefix test called 9 correct functions wrong.
  * `hhobjmot.c` really is "object motion", so 8 correctly-placed
    `hhObjectMotion*` functions looked like errors until compound
    abbreviations were handled.

It then earned its keep immediately by finding two real errors that the
sandwich rule's own 99.99% hold-out could not: `hhdprint.c` is referenced from
exactly one place, so its window is ZERO BYTES wide and it owns no functions --
invisible to a neighbour test, but the gap around it is not homogeneous, and
hhDbgPrintBegin/Row either side of it were being swallowed by hhcamera.c. The
rule now refuses to cross another unit's anchor (5 gaps blocked), and the
function-granularity score went 94.6% -> 96.3%.

The remaining 3 disagreements sit in gaps between unit windows, 72-172 bytes
from the unit the name implies. They are consistent with anchor_expand's own
measured error rate -- a rodata reference identifies the right unit 97.7% of
the time, and 3 misses in 108 is 97.2%. So this is the expected residual, not
a policy bug, and it is not worth "fixing" by hand.

**The check only covers the `hh` family, on purpose.** The hahig engine names
files strictly after the module in the identifier; the game's own overlays do
not. `fmchmove.c` is "chara MOVE" and correctly holds `fmCharaRunspeedSet`, but
"move" appears nowhere in that identifier, so any filename-derived test calls
it an error. Running `check_names_vs_units.py --all` reports 49 disagreements
of which about 30 are that one false pattern. A signal that is wrong half the
time is not validation, so the broad sweep is opt-in and stays out of
rebuild.sh.

156 functions in TITLE/ENDING/MINIGAME are unattributable rather than
unattributed: those overlays contain one `__FILE__` literal each (scenario.c,
staff.c) referenced from a single place, so their unit windows are zero bytes
wide, and MINIGAME.BIN has no literal at all. There is no evidence to work
from short of a different technique.

## Next

1. **Keep naming.** `tools/dossier.py UNIT` prints every function in a unit
   with its asserts, strings, callers and callees -- enough to name by hand
   with justification. 71% attribution plus the call graph is enough to work
   with. Begin with `../hahig/hhtext.c`, `hhcamera.c` and `choose.c`, where
   the translation work gives ground truth to check against.
2. **Prune the function over-count** (10,103 candidates vs 6,586 `jal` targets).
3. Jump tables are the one untried reference class.
2. **Prune the function over-count.** An interior `jr $ra` followed by more of
   the same function is the main false positive; a real entry almost always
   begins with a stack adjust (`addiu $sp, $sp, -N`) or is a `jal` target.
3. **Name the UI/text layer first** -- `hhtext.c`, `hhcamera.c`, `window.c` --
   where the translation work already gives ground truth to check against.


## Prior art and tooling worth pulling in

Checked 2026-09-03. Nothing exists for this game beyond `rezual/nge_2_re`
(which this project already builds on), but the PS2 decomp ecosystem is real:

* **m2c** (`matt-kempster/m2c`) -- MIPS -> C aimed at *matching* output, which
  is the relevant kind. Takes GNU `as` syntax, so it pairs with spimdisasm.
* **splat** -- splits a binary into per-function asm plus a linker script. The
  standard front end for this kind of project.
* **ps2split** (`Kneesnap/ps2split`) -- PS2-specific splitter.
* **decomp-permuter** -- for functions that are semantically right but a few
  instructions off; brute-forces source variations until the output matches.
* **asm-differ** -- side-by-side diff of compiled vs original.
* **PS2Recomp** (`ran-j/PS2Recomp`), **psretrox** -- static recompilation
  attempts. Worth watching, not depending on.

Reference projects to copy structure from: `sly1` (Sly Cooper),
`god-hand-decomp`, `kl2_lv_decomp` (Klonoa 2), `DCDecomp` (Dark Cloud).

**Toolchain.** Matching needs the original compiler, not a modern one:
SN Systems ProDG / ee-gcc 2.95.2, mirrored at
`AngheloAlf/SN-Systems-ProDG_for_PS2_2.0`. Our ELF's flags (`mips3`,
`eabi64`, R5900) are consistent with that family. `decomp.wiki` has the
per-game compiler notes.

**Symbols -- CHECKED, dead end.** Alfa System's PS2 catalogue is Abarenbou
Princess, Shikigami no Shiro, Castle Shikigami 2, Vampire Panic, Shikigami no
Shiro: Nanayozuki Gensoukyoku, and the three Gunparade Orchestra titles. **None
of them appears in retroreversing's unstripped list**, so there is no sibling
binary to lift `hahig` engine names from. Two other Evangelion PS2 games do
have symbols -- Ayanami Ikusei Keikaku (SLPM-65334) and Koutetsu no Girlfriend
2nd (SLPM-65867) -- but they are different developers and will not share this
engine. They could still be useful for identifying Sony SDK library functions
by signature, which is a separate and much smaller win.

Original reasoning, kept for context: Many early PS2
games shipped with a populated `.mdebug` section; the Chaos Compiler Collection
extracts it for Ghidra. **Ours is empty** (`.mdebug.eabi64`, size 0), so there
is nothing to recover here directly. But the engine layer is shared code --
`../hahig/hhcamera.c`, `hhmodel.c`, `hhobject.c` -- so if any other Alfa System
PS2 title shipped unstripped, its symbol names would transfer onto our engine
functions wholesale. No public dump of the `hahig` engine exists that I could
find, but retroreversing's unstripped list is the place to check title by title.
