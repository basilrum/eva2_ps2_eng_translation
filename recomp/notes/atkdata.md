# atkdata, and a fixed-point rate decoded

BATTLE.BIN **0x01F619E0**, 51 entries of 36 bytes. Named by the assert at
btattack.c:174, bound confirmed by the code's check; the 36-byte stride is
confirmed by the name pointers landing on it across the whole table.

    +0x00  ptr   internal name    ("EVA's Prog Knife thrust")
    +0x04  u32   10 .. 300, set on every entry
    +0x08  u32   ranged only -- see below
    +0x0C  f32   ranged only, 0.24 .. 2.56
    +0x10  u32   often a packed pair of u16 (high half usually zero)
    +0x14  u32   likewise
    +0x18  ptr   display name, or null
    +0x1C  ptr   description
    +0x20  u32   small id

## +0x08 is a 16.16 fixed-point rate -- 65536 / frames

Only guns have a value here, and the values are not arbitrary. Every one of the
seven distinct values in the table is **exactly** `round(65536 / n)` for a small
integer n, and each round-trips back to itself:

    value    n frames
    21845       3
    16384       4
     5461      12
     1820      36
     1456      45
     1092      60
      546     120

Seven values all landing on clean integers is not coincidence: the field is a
16.16 fixed-point increment that accumulates to 1.0 after n frames. So n is a
cooldown or charge time in frames, and at 60 Hz the range is 1/20 s to 2 s.

It reads correctly against the weapons. The Pallet Rifle -- described in game as
a wide, low-power spray -- sits at n=4, the fastest in the table. Positron S,
the extreme-range option, sits at n=120: two full seconds between shots.

**The same pair lives in equipdata.** `equipdata+0x04/+0x08` holds byte-for-byte
the same values as `atkdata+0x08/+0x0C` for every gun (Pallet Rifle 16384/0.88,
Rifle 1820/1.2, Positron Rifle 1456/1.44, Positron S 546/2.56). So the two
tables share one definition of a ranged weapon's timing and its scalar, and
whichever is authoritative, they agree.

## Settled by the official guide (p.049)

The guide plots the main attacks on a charge-time axis and prints a number
beside each one. Both map onto this table exactly.

**+0x04 is ATTACK POWER.** Eight attacks appear on that chart, and +0x04
equals the printed number for all eight -- Chop and Middle Kick 90, Prog Knife
Slash 110, Pallet Rifle 120, Prog Knife Thrust 140, Impact Bolt 180, Positron
S 250, Two-Platoon Kick 300.

**+0x10 is CHARGE TIME IN FRAMES.** Divided by 60 it lands on the guide's
printed seconds:

    Chop / Middle Kick        90f = 1.50s
    Pallet Rifle / Rifle     107f = 1.78s  -> 1.8
    Prog Knife Slash         120f = 2.00s
    Prog Knife Thrust        210f = 3.50s
    Impact Bolt              240f = 4.00s
    Two-Platoon Kick         300f = 5.00s
    Positron S               420f = 7.00s

17 of the 23 named attacks land on a tick the guide prints; the other 6 sit at
1.00, 3.00, 2.38 and 3.78 s, which the chart simply does not plot because it
only graphs seven examples.

A note on method: two entries looked like mismatches at first. They were not --
Pallet Rifle and Prog Knife Slash are adjacent thumbnails on adjacent ticks and
I had read them the wrong way round. The binary was right and my reading of the
photograph was wrong, which is worth remembering when a cross-check disagrees
by one position.

**And +0x08 is therefore NOT charge time.** That was the open question, and it
is now answered in the negative: charge lives in +0x10, so the 16.16 reciprocal
in +0x08 (n = 3..120 frames) must be the firing interval -- Pallet Rifle fires
every 4 frames while charging for 107, which is exactly how a rapid low-power
spray behaves.

## Still open

+0x14, +0x1C and +0x20 remain unidentified.
