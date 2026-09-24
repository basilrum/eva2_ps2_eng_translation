# The free-roam AI model

Field meanings here are cross-checked against the official guide's AI chapter.
Where the guide settles something the binary could not, it says so; where the
binary is the only source, that is marked too.

## Desires -- 16 of them, plus a default

The guide states there are **16** desire types driving NPC behaviour. The table
at FREE.BIN **0x01F80AF8** holds **17** entries, and the extra one is index 0,
`普通モード` / "Normal Mode" -- the neutral state, not a desire. So 1 + 16 = 17
and the lists correspond exactly, in order:

     0  Normal Mode              (not a desire; the default state)
     1  restore stamina          9  power / classified info
     2  thirst                  10  be liked by everyone
     3  sleep                   11  serve justice
     4  avoid disliked people   12  live for love      (恋)
     5  lust                    13  do nothing
     6  possessions             14  toilet
     7  money                   15  live for friendship (友情)
     8  fame                    16  live for affection  (親愛)

The order is the game's, confirmed slot by slot. Two things the guide adds that
the binary does not show:

  * indexes 12, 15 and 16 each point at a *different relationship score* -- the
    NPC seeks out whoever it rates highest in 愛情, 友情 and 親愛 respectively.
    Those are three separate evaluations, which is why the three desires exist.
  * index 9 is not brute strength: it is the drive to obtain classified
    information that only a few characters hold.

That trio is also why the translation collision at 12/16 mattered -- see
`toolkit/translation_collisions.py`.

## Memory

Each NPC's memory is split into three regions, and the guide gives both the
split and the decay:

    hippocampus   20%   newest; top 20 promoted every 24 h
    neocortex     70%   months to years; top 20 promoted every year
    paleocortex   10%   oldest; never forgotten within a playthrough

Strength decays by 1 per **minute** in the hippocampus and 1 per **day** in the
neocortex, and repeating an action you have already done stores a weaker copy
than the first time.

Per-character region sizes are printed on p.045 and vary a lot -- the oldest
character has by far the largest neocortex and the smallest hippocampus, and
the guide ties that directly to how slowly his A.T. rises. **These numbers have
not been located in the binary yet**; they are a good target, because 16
characters x 3 values is a distinctive shape to search for.

## Status fields

The status screen carries name, A.T., money, condition and skill levels, where

    condition     5 values: hunger, hydration, sleepiness, WC, bath
    skill levels  3 values: information, administration, close combat

The 5-value condition set matches the item tables, which are grouped by exactly
those recovery categories.
