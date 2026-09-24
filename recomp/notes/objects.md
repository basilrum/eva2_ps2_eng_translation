# The hahig object

Every drawable thing in the engine is a "hahig object" with a common header.
The offsets below are each backed by code that was read, not by pattern
guessing; where something is inferred it says so.

## Type tag -- u16 at object +0xF4

The engine tags each object with a **two-character ASCII code**, and functions
that operate on one class assert on it before doing anything. Found by
scanning every `lhu rt, 0xF4(rs)` and taking the immediate it is compared
against:

    'CA'  0x4143   camera        ../hahig/hhcamera.c     HHCA_OBJTYPE
    'MO'  0x4F4D   model         ../hahig/hhmodel.c      HHMO_OBJTYPE
    'P3'  0x3350   3D primitive  ../hahig/hhprim3d.c     HHP3_OBJTYPE
    'PA'  0x4150   particle      ../hahig/hhpartic.c     HHPA_OBJTYPE
    'LI'  0x494C   light         ../hahig/hhlight.c
    'SP'  0x5053   sprite/motion ../hahig/hhobjmot.c, btuobj.c
    'ML'  0x4C4D                 ../hahig/hhobject.c, btdemo.c
    'DL'  0x4C44                 fm3dtrce.c, fvchara.c
    'PR'  0x5250                 ../hahig/hhobject.c
    'TX'  0x5854                 btprim.c

The first four are **confirmed twice over**: the tag's home unit matches the
`HH??_OBJTYPE` constant that `tools/assert_glossary.py` recovers from that same
unit's assert text. The rest are read off the code alone, so the class names
for ML/DL/PR are deliberately left blank rather than invented -- 'DL' being
"draw list" is a plausible guess and nothing more.

A caution for anyone repeating the scan: filtering to *printable* 16-bit
immediates is not enough on its own. It also matches structure offsets that
happen to be printable ('X$' 0x2458 and '`#' 0x2360 in hhtext.c, '00' 0x3030 in
hhprim3d.c). The tags above are the ones whose unit corroborates them.

## Known fields

    +0x30/34/38   f32   world position X/Y/Z
    +0x80/0x84    f32   text/sprite screen position, written by
                        choose_text_set_pos; 0x8000 in the argument leaves an
                        axis alone, 0x4000 means centre it
    +0xE4         ptr   scene -> camera (from the scene object)
    +0xF4         u16   type tag, above
    +0x104        u32   flags. bit 0x10 is set/cleared by hhObjectEnableSet
                        (193 call sites); 0x00440000 is OR'd in when a text
                        position is set. The *meaning* of bit 0x10 is inferred
                        from the setter's shape, not proven.
    +0x214        ptr   camera's follow target (read by gmModeManager's caller)

## Camera extension

A camera object carries its angle limits at +0x1D0..+0x1D8 -- see
notes/camera.md, which documents the sentinel that disables them.

## The object command interpreter

`hhObjectCmdExec` @0x001264E8 runs a **byte-coded command stream** -- a second,
much smaller VM than the event sequencer, and unrelated to it. The dispatch
forks on the opcode value:

    lbu   $s3, ($v1)          read the opcode byte
    slti  $v0, $s3, 0x20      under 0x20?
      yes -> table[op] at 0x001D8150, 32 entries, 4-byte
      no  -> scan the runtime registry at 0x00330BA0

**Static table, opcodes 0x00-0x1F.** `hhObjectCmdTable` @0x001D8150, 32 slots,
21 distinct handlers. The other 12 hold `hhObjectCmdNop` @0x00124120, which is
eight bytes of `jr $ra; nop` -- so a third of the opcode space is deliberately
unused, and any table-derived "names" for those slots would have been twelve
names for one empty function. `hhobjmot.c` indexes the same table, so motion
and object commands share the opcode space.

**Runtime registry, opcodes 0x20 and up.** Dispatch is by **object type tag**:
the loop reads the tag at `object+0xF4` and walks a table at 0x00330BA0
comparing it against each entry, then calls the pointer at entry+8.

    entry stride   0x0C bytes      (from `addiu $s0, $s0, 0xc`)
    +0x00   u16    object type tag ('CA', 'MO', 'P3', ...)
    +0x08   ptr    handler
    count          the word at 0x00215830

0x00330BA0 is above the .bss start (0x00215800), so it is **empty in the image
and filled at run time**. That is why no static scan finds handlers there, and
it is the reason a purely static map of this engine has a hole in it: which
function services which type tag for opcodes >= 0x20 can only be recovered by
reading whatever registers them, or by looking at live memory.
