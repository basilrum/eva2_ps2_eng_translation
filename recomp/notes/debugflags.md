# The debug-flags word at 0x001D3910

One word in .data gates every developer feature left in the retail build. It is
**zero in the shipped ELF**, so all of this is dormant rather than removed.

Regenerate with `tools/debug_flags.py`: it resolves every address load to the
word, follows the `lw`, and collects the `andi` masks applied to that register.
**76 test sites, 14 distinct bits.** What each bit does is read off the
functions that test it -- the list below is evidence, not a guess at Alfa
System's naming.

(The first version of this sweep reported 74 sites and 13 bits. It looked only
24 bytes past the `lw` and so missed bit 0x2000, which `cdGetMediaType` tests
28 bytes after its load -- that function reads the word once and tests three
bits in a row. The window is 64 bytes now and the register is tracked, so an
unrelated `andi` cannot be mistaken for one.)

## Bits with a confirmed effect

    0x0001   the built-in BMP screenshot feature (see below), plus debug paths
             in choose/evseq/pad and the title screen
    0x0010   overlayLoad reads prog/<mode>.bin from the DEV HOST (0x001088D0)
             instead of the disc (0x00146FA8)
    0x0020   the free-roam IM test harness inside FREE.BIN (see below)
    0x0100   cdGetMediaType returns 1 (CD) without asking the drive
    0x0200   cdGetMediaType returns 2 (DVD) without asking the drive
    0x0400   cdInit returns early -- disc bring-up is SKIPPED entirely
    0x2000   cdGetMediaType actually queries the drive (sceCdGetDiskType,
             compared against 0x12 = CD and 0x14 = DVD). With none of 0x0100,
             0x0200 or 0x2000 set it assumes DVD, which is what shipped
    0x4000   dbgPrintf actually prints. 40 sites -- by far the most-tested bit,
             and the one to set first
    0x0801   TITLE's overlayMain returns 2 (FREE) immediately instead of
             running the title screen -- it needs BOTH bit 0x0001 and 0x0800

Bits 0x0100 / 0x0200 / 0x0400 / 0x0010 together describe a machine with no disc
in it: skip disc init, assume a media type, and pull the overlays over the
dev-kit link instead. That is the configuration the game was developed in.

## To turn them on

    patch=1,EE,001D3910,word,00004801     // debug printing + skip the title

`patch=1` re-applies every frame, which matters: the word is plain .data and
the game is free to rewrite it. Nothing here is tested in motion.

**Do NOT set bit 0x0010.** It redirects overlayLoad to the dev host, and the
network IRX modules that would serve it are not on the retail disc -- so every
mode transition would try to load prog/<mode>.bin from a machine that is not
there. That bit is only meaningful on a DTL-T10000 with the programmer's PC
attached. Setting it on a normal build should be expected to hang the game at
the first mode change, which is the title screen handing off.

## Every test site

  0x0001   9 sites
           SLPS_252.99    No_message
           SLPS_252.99    SnapShotExit
           SLPS_252.99    SnapShotInit
           SLPS_252.99    SnapShotUpdate
           SLPS_252.99    choose_001501B0
           SLPS_252.99    evseq_0017AA80
           SLPS_252.99    pad_001073F8
           TITLE.BIN      func_01F00570
           TITLE.BIN      overlayMain
  0x0002   2 sites
           SLPS_252.99    pad_00107070
           SLPS_252.99    pad_001070F0
  0x0003   1 sites
           SLPS_252.99    main
  0x0004   2 sites
           SLPS_252.99    adpcm_00143060
           SLPS_252.99    daysdisp_00184688
  0x0010   1 sites
           SLPS_252.99    overlayLoad
  0x0020   5 sites
           FREE.BIN       fm3doff_01F51B28
           FREE.BIN       init_01F007A0
           FREE.BIN       init_01F008B0
           FREE.BIN       test_01F01B40
           FREE.BIN       test_01F01C08
  0x0040   1 sites
           SLPS_252.99    memfind_00163098
  0x0100   1 sites
           SLPS_252.99    pad_00106DA8
  0x0200   1 sites
           SLPS_252.99    pad_00106DA8
  0x0400   4 sites
           SLPS_252.99    adpcm_00141860
           SLPS_252.99    cddir_00107D30
           SLPS_252.99    cdfile_001074F0
           SLPS_252.99    pad_00106E28
  0x0800   5 sites
           FREE.BIN       bgm_Music
           FREE.BIN       im0915_01F1F9B8
           FREE.BIN       im0915_01F1FBF0
           SLPS_252.99    evseq_0017AA80
           TITLE.BIN      overlayMain
  0x1000   3 sites
           FREE.BIN       im0915_01F202B0
           SLPS_252.99    assertFail
           SLPS_252.99    hhcamera_00113200
  0x2000   1 sites
           SLPS_252.99    pad_00106DA8
  0x4000   40 sites
           SLPS_252.99    SidToSeAngel
           SLPS_252.99    SidToSeBattle03
           SLPS_252.99    SidToSeBattle04
           SLPS_252.99    SidToSeBattle06
           SLPS_252.99    SidToSeBattle16
           SLPS_252.99    SidToSeBattle17
           SLPS_252.99    SidToSeBattle18
           SLPS_252.99    SidToSeBattle20
           SLPS_252.99    SidToSeBattle39
           SLPS_252.99    SidToSeBattle57
           SLPS_252.99    SidToSeBattle87
           SLPS_252.99    SidToSeBattle91
           SLPS_252.99    SidToSeBattle94
           SLPS_252.99    SidToSeBattle95
           SLPS_252.99    SidToSeEnd1
           SLPS_252.99    SidToSeEnd2
           SLPS_252.99    SidToSeEnd3
           SLPS_252.99    SidToSeEnd4
           SLPS_252.99    SidToSeFree1
           SLPS_252.99    SidToSeFree10
           SLPS_252.99    SidToSeFree2
           SLPS_252.99    SidToSeFree3
           SLPS_252.99    SidToSeFree4
           SLPS_252.99    SidToSeFree5
           SLPS_252.99    SidToSeFree6
           SLPS_252.99    SidToSeFree7
           SLPS_252.99    SidToSeFree8
           SLPS_252.99    SidToSeFree9
           SLPS_252.99    SidToSeStart01
           SLPS_252.99    SidToSeStart02
           SLPS_252.99    SidToSeStart03
           SLPS_252.99    SidToSeStart04
           SLPS_252.99    SidToSeStart05
           SLPS_252.99    SidToSeStart06
           SLPS_252.99    SidToSeStart09
           SLPS_252.99    SidToSeStart10
           SLPS_252.99    SidToSeStart11
           SLPS_252.99    dbgPrintf
           SLPS_252.99    debug_00105160
           SLPS_252.99    evseq_00178B78

## Worked example: what bit 0x0001 actually unlocks

Bit 0x0001 gates a **built-in screenshot feature**, complete end to end:

    SnapShotInit     0x001401F0   gated on bit 0x0001; builds the struct at
                                  0x002C77D8, stores the two GS framebuffer
                                  addresses 0x04000000 / 0x04100000, and
                                  starts a task named "SnapShot"
    SnapShotTask     0x00140118   polls the pad word at 0x00215808; holding
                                  bit 0x0800 for 60 consecutive frames sets
                                  the request flag
    SnapShotUpdate   0x00140188   called EVERY FRAME from gameMainLoop; on a
                                  request it runs four capture steps and
                                  clears the flag
    SnapShotWriteBmp 0x00140048   reads the RTC and writes the image

The filename format settles what it does:

    host:%s/../temp/pic/%d%d%d%d-%d%d%d%d%d%d.bmp        with %s = ../../cdimg

opened with flags 0x602 (WRONLY|CREAT|TRUNC). So it saves a timestamped **BMP**
-- but to a `host:` path, i.e. the programmer's PC over the dev-kit link. On a
retail disc there is nowhere for it to go, so enabling bit 0x0001 will run the
capture and then fail at the write. The capture half is real; only the
destination is unavailable.

Pad bit 0x0800 is R1 in the standard PS2 button layout. That mapping is
assumed, not verified against this game's own pad handling.

## Bit 0x0020 -- the free-roam developer harness

Tested only inside FREE.BIN, at five sites in `../im/init.c` and `../im/test.c`.
Two of them show what it is:

  * `init_01F007A0` builds a debug text object (0x00132968 with 0x1e/0x16/0x1e),
    parks it at y = 16.0, enables it, and keeps the handle at 0x01FB6008+0x14
  * `test_01F01480` is a driver that calls `imInit`, `imExit`, a `choose` menu
    and the BGM control -- i.e. it starts and stops IM scenes on demand

So this is the interaction-memory test harness, not a readout: it lets a
developer launch an IM scene straight from a menu. The text object it creates
is the harness's own display. Nothing here writes to a host path, so unlike the
screenshot feature there is no reason it could not run under emulation --
untested either way.

## Bit 0x1000 -- make asserts REPORT instead of crash

`assertFail` @0x001051D0 has 684 call sites, and its behaviour forks on bit
0x1000 of the debug word:

**bit clear (retail).** Jumps to 0x00105270, calls `assertHalt`, then executes

    lb  $v1, ($s0)          ; load a byte
    sw  $v0, 1($v1)         ; store a WORD at that byte + 1

a deliberately misaligned word store, followed by an infinite loop at
0x00105288. The machine stops, and nothing says why.

**bit set.** Formats through `dbgVPrintf` with

    "assertion: %s\n%s:(%d)"        expression, file, line

and then, if bit 0x0002 is also clear, builds the same message with `sprintf`
and hands it to `0x0014FC38` in **choose.c** -- the on-screen message-box
path, not the console. So a failed assertion draws its own expression, source
file and line number on the TV, then loops.

That is worth having. It converts "the game froze" into "hhcamera.c:225
self->objtype == HHCA_OBJTYPE", which is exactly the information a recomp or a
patch author needs.

    patch=1,EE,001D3910,word,00005001     // asserts report + dbgPrintf on

A correction to an earlier note in this project: **the asserts are not compiled
out.** 684 live call sites reach assertFail, and 346 of them were recovered
with their file and line intact. What retail does is fail *silently* -- the
strings, the checks and the reporting path are all still in the binary.
