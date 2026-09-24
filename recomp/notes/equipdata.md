# equipdata -- the battle equipment table

BATTLE.BIN **0x01F62390**, 13 entries of 40 bytes. Both bounds agree: the
assert at btequip.c:59 names the array and the code checks the index against
13, and exactly 13 name pointers appear at a 40-byte stride.

    +0x00  ptr    name
    +0x04  u32    0 on every melee weapon and shield; set on every gun
    +0x08  f32    scales up with weapon power (0.88 .. 2.56)
    +0x0C  s32    -1 on melee and shields, 2..10 on guns
    +0x10  f32    \  paired multipliers, 0.2 .. 1.0
    +0x14  f32    /
    +0x18  u32    0 except the two shields (200 and 300)
    +0x1C  u32    1, 2 or 3 -- 3 only on the longest-ranged weapon
    +0x20  u32    small ascending id, 0 on both shields
    +0x24  ptr    description, or "(none)"

## What the data itself establishes

The 13 entries are, in order: Smash Hawk, Sonic Glaive, MP Sword, Pallet Rifle,
Handgun, Bazooka, Rifle, Positron Rifle, Positron S, Shield, Heavy Shield,
Mastema, Dual Saw.

Three fields are pinned by the descriptions the game itself prints:

  * **+0x18 is durability.** It is zero for all eleven weapons and non-zero
    only for Shield (200) and Heavy Shield (300), whose descriptions are about
    adding durability -- and the tougher one carries the larger number.
  * **+0x10 / +0x14 are movement multipliers.** The three entries whose
    descriptions mention a movement penalty (Positron Rifle, Positron S, Dual
    Saw) are exactly the ones with values below 1.0 in these fields, and
    Positron S -- described as the extreme-range option -- has the lowest pair
    in the table (0.4 / 0.2).
  * **+0x0C separates melee from ranged.** It is -1 for every sword and shield
    and a small positive count for every gun.

## What is inferred, not established

+0x04, +0x08, +0x1C and +0x20 all correlate sensibly with weapon power, but
which is attack, which is ammo, which is a weight or slot cost, and which is a
model or icon id is **not determined**. +0x08 rising monotonically with the
weapon's evident strength makes a damage coefficient the obvious reading; it is
still a reading.

This is the table to check against the official guide's equipment chart. Its
columns should map onto these four fields directly, which would settle them.
