# Neon Genesis Evangelion 2 — English Translation (PS2)

A complete English fan-translation of **Shin Seiki Evangelion 2 — Evangelions**
(PlayStation 2, SLPS-252.99, Japan-only).

Distributed as an xdelta patch: it contains only the difference from the
original disc, so you supply your own copy of the game. No copyrighted data is
distributed here.

---

## Apply the patch

**Linux / macOS**

```sh
xdelta3 -d -s "Shin Seiki Evangelion 2 - Evangelions (Japan).iso" \
           patch/nge2_english.xdelta \
           "NGE2 English.iso"
```

**Windows** — drag both files onto xdelta UI, or:

```
xdelta3.exe -d -s "Shin Seiki Evangelion 2 - Evangelions (Japan).iso" patch\nge2_english.xdelta "NGE2 English.iso"
```

### Check your source disc first

```
md5  cbe94757814172a7f210ca167154db0a
     Shin Seiki Evangelion 2 - Evangelions (Japan).iso
     3,105,521,664 bytes
```

An xdelta applied to a different dump produces a corrupt image **and will not
warn you** — the game simply hangs or shows a black screen. Check the md5.

The result should come out to `48d05ad18cfcb194b21d302a1ee07532`
(3,162,275,840 bytes). Both checksums are in [`patch/CHECKSUMS.txt`](patch/CHECKSUMS.txt),
and this exact round-trip is verified before every release.

Play the result in PCSX2. No settings changes are needed.

---

## What is translated

* **All dialogue** — 10,754 pages across 451 scripts, every event and battle.
* **Every menu and HUD** — options, shop, save/load, status, map, battle
  displays, mission reports, the pilot and unit panels.
* All 11 A.T. Field tutorial screens.
* 103 episode subtitle cards.
* Item, unit and pilot names, and the equipment descriptions.
* The Kaworu dialogue choices in the Terminal Dogma battle.
* The free-time conversation menus and replies.
* System messages: controller check, memory card, save warnings.
* **The developer debug menus**, in the executable and in every overlay —
  555 menu labels plus 82 console/log strings, including the cut-scene tables
  and the battle prompt bar. These are not reachable in normal play; they are
  translated for completeness.

Every menu is fully navigable in English.

---

## Credits and licence

The reverse-engineering groundwork for the **PSP** version of this game
(`Neon Genesis Evangelion 2: Another Cases`) was done by an earlier
public-domain project, which is where the `.EVS` script format was first
worked out. This is the **PlayStation 2** translation, built on top of that
research.

The tooling that produced the patch -- extraction, texture and dialogue
editing, disc rebuild -- is not published here; this repository is the patch
itself.

Released to the public domain, no restrictions — the same terms as the upstream
project.

This is an unofficial fan project. Neon Genesis Evangelion is the property of
its respective rights holders; no game data is distributed here.
