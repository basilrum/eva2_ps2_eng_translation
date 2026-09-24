# Boot: crt0, main, and the memory layout a recomp needs

Recovered by disassembling from the ELF entry point. None of this was in the
map before -- `_start` was **missing from the function list entirely**, because
nothing `jal`s it and no `jr $ra` precedes it, so neither of func_scan's two
sources could see it. It is the root of the call graph, so every reachability
question was starting from the wrong place. `func_scan` now seeds itself from
the ELF header's `e_entry`.

## The chain

    _start   0x00100008   (ELF e_entry)
    main     0x00100310
    exit     0x001A3110

## What _start does, in order

1. Clears all GPRs (128-bit MMI stores capstone renders as raw bytes), `hi`,
   `lo`, all 32 FPRs, and the FPU control register.
2. **Zeroes .bss** from `0x00215800` to `0x0039ADE0`, sixteen bytes per
   iteration with 128-bit stores.
3. Sets **`$gp = 0x0021D770`**.
4. `syscall 60` with (gp, stack, size, args); the return value becomes `$sp`.
5. `syscall 61` with (`0x0039ADE0`, -1) -- the heap starts where .bss ends.
6. Calls the libc initialiser at `0x001A2D28`, then `FlushCache(0)`.
7. Loads argc/argv from `0x00215880` and calls `main(argc, argv)`.
8. Tail-calls `exit` with main's return value.

## Numbers a recomp needs

    gp                0x0021D770
    .bss              0x00215800 .. 0x0039ADE0
    heap base         0x0039ADE0   (passed straight to syscall 61)
    argc/argv block   0x00215880

`$gp` matters most: the compiler addresses small globals as offsets from it, so
every gp-relative load is unreadable until you know its value.

## Two syscalls identified by use rather than by guess

`name_syscalls.py` deliberately refuses to put Sony's names on the stub table.
These two are exceptions, because _start's own code shows what they do:

    syscall 60  InitMainThread   given (gp, stack, size, args), returns the
                                 value that becomes $sp
    syscall 61  InitHeap         called immediately after with (heap, -1)

That is evidence, not recall. The other 158 stubs keep their numbers.

## main

Allocates a 0x90020-byte frame (589,856 bytes -- the whole engine's scratch),
keeps argc/argv, and runs an init sequence before returning 0. Its early calls
are 0x001B9CE8, 0x00105010, 0x001001D8, then a chain through 0x00106618 /
0x00106818 / 0x00106950 / 0x001068C0 / 0x00106780 -- the top-level game loop
scaffolding, and the obvious next thing to name.

## The frame loop

`gameMainLoop` @ **0x00106950**, reached as the third-from-last call in `main`.
It is instrumented, and the profiler labels name its phases outright:

    profilerBegin("Main Loop")            0x0012E410 / 0x0012E5E0
        ... per-frame setup ...
        profilerBegin("Game")
            while (ticks-- > 0) {                 fixed-step catch-up loop
                profilerBegin("GameTask");   GameTask()   0x00137250
                profilerBegin("UpdateAll");  UpdateAll()  0x00121C08
                hook = *(void(**)())0x00219000;  if (hook) hook();
            }
        profilerEnd("Game")
        ... render, then a do/while that waits on 0x00106FE0 ...
    profilerEnd("Main Loop")

Globals it runs on:

    0x00219000   per-tick callback hook, called through jalr if non-null
    0x00219004   quit flag (byte); non-zero breaks the loop
    0x001D3A38   frame counter, incremented once per frame
    0x001D3A3C   vsync counter, sampled to measure frame time
    0x001D3A44   incremented when two frames in a row run long -- a dropped
                 frame counter
    0x001D3A4C   "run this tick again" flag, cleared each pass

The per-tick hook at 0x00219000 is the interesting one for tooling: it is a
plain function pointer in memory, called every tick with no arguments, and
null by default. That is a ready-made place to attach code.

## Profiler labels as a naming source

13 `profilerBegin` sites carry a literal label, and they name real functions:
MatrixInv, HahiGModelDraw, HahiGMotion, HahiGDrawAll, HahiGHierarchyAll,
AlphaSort, HahiGParticleDraw, HahiG3DPrimDraw, GameTask, UpdateAll.

**Four of those functions were already named identically by other passes**
(MatrixInv, HahiGModelDraw, HahiGMotion, HahiG3DPrimDraw) -- an independent
source agreeing on the same names, which is worth more than the handful of new
names it produced.

A caution: an automated version of this got two of them wrong. The labels are
hoisted into callee-saved registers *before* the loop, so "the most recent
literal load before the call" picks up a stale string -- it reported
`UpdateAll` for GameTask's callee. The assignments above are from reading the
code. Two functions in hhpartic.c share the label `HahiGParticleDraw`, and
which is the real one is not established.

## The mode manager -- how the game reaches its overlays

`gmModeManager` @ **0x0015C348** is boot-mode table entry 0, i.e. the retail
boot path. Everything the player ever sees runs underneath it.

    g_currentModeId   0x00317BE8   set to 1 at startup
    overlay paths     0x001DC338   indexed by that id

        1  prog/title.bin
        2  prog/free.bin
        3  prog/battle.bin
        4  prog/ending.bin
        5  prog/minigame.bin

So the whole call chain is now continuous:

    _start -> main -> createTask(boot-mode table[0x001D3914])
           -> gameMainLoop -> GameTask/UpdateAll
           -> gmModeManager -> load prog/<mode>.bin -> the overlay's own code

That closes the gap between the ELF entry point and the five overlays, which
were previously five disconnected binaries in the map.

The manager also keeps an 8-entry ring of 0x18-byte records at 0x00317C58
(index at 0x001DC330) and prints `<Memory held by mode>` and
`<Memory status>\nAt start: %4d blocks (%8d Bytes)` through dbgPrintf -- it is
checking each mode gives its memory back.

**Practical:** the mode id is a plain word in memory. Writing 3 to 0x00317BE8
should send the game to the battle overlay. Untested, and the overlay will
expect state the title screen normally sets up, so it may well not survive --
but it is the obvious lever for reaching a mode directly.

## How an overlay is loaded and entered -- definitively

    overlayLoad  @0x001408B0
    overlayEnter @0x00140990

`overlayLoad(path)` memsets **1 MB at 0x01F00000** and reads the file into it,
after printing `overlay '%s' loading...`. Which source it reads from is a debug
switch: bit 0x10 of the flags word at 0x001D3910 selects the dev host
(0x001088D0) instead of the disc (0x00146FA8).

`overlayEnter(ctx)` is four instructions of substance:

    FlushCache(0)          eeSyscall_100
    FlushCache(2)
    jal 0x01F00000         with ctx in a0
    -> return value

So an overlay's entry point is simply **its first word**, and its return value
is the next mode id. That settles three things that were previously assumed:

  * the overlay load base really is 0x01F00000, and the region is 1 MB
  * there is no header and no relocation -- the image is entered at offset 0
  * `eeSyscall_100` is FlushCache, confirmed by the only place it could be
    (flushing before executing freshly loaded code)

`overlayMain` @0x01F00000 now exists in all five overlay binaries. **None of
them had it before**: nothing inside an overlay calls its own entry, and no
`jr $ra` precedes offset 0, so neither of func_scan's sources could see it --
the same blind spot that hid `_start`. func_scan seeds it now.
