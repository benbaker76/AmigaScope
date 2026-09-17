# Hardware sprites

How to build, position, colour, attach, reuse and collide the eight hardware sprites.

Sprites are 16-pixel-wide lores objects drawn by eight sprite DMA channels, independent of the
playfield mode (they stay lores and non-interlaced even on a hires/lace screen). Each channel
reads a data list from chip RAM once per field.

Registers: [SPRxPTH, SPRxPTL](../registers/sprites.md#sprxpth-sprxptl),
[SPRxPOS](../registers/sprites.md#sprxpos), [SPRxCTL](../registers/sprites.md#sprxctl),
[SPRxDATA](../registers/sprites.md#sprxdata), [SPRxDATB](../registers/sprites.md#sprxdatb),
[CLXCON](../registers/sprites.md#clxcon), [CLXDAT](../registers/sprites.md#clxdat),
[BPLCON2](../registers/playfield.md#bplcon2), [COLORxx](../registers/playfield.md#colorxx),
[DMACON](../registers/dma-beam.md#dmacon).

## Sprite data layout

A sprite is a list of words in **chip RAM**, word aligned:

| Offset | Word | Loaded into |
|---|---|---|
| 0 | position word: VSTART low 8 bits, HSTART bits 8-1 | SPRxPOS |
| 2 | control word: VSTOP low 8 bits, ATTACH, VSTART bit 8, VSTOP bit 8, HSTART bit 0 | SPRxCTL |
| 4, 6 | line 1: data A (colour bit 0), data B (colour bit 1) | SPRxDATA, SPRxDATB |
| ... | two words per line, `VSTOP - VSTART` lines | |
| end | `0,0` -- or the POS/CTL pair of the next use of this channel | |

The pixel colour of each of the 16 columns is `B bit * 2 + A bit` (most significant bit =
leftmost pixel):

| Code | Colour for sprites 0/1 | 2/3 | 4/5 | 6/7 |
|---|---|---|---|---|
| 00 | transparent | transparent | transparent | transparent |
| 01 | COLOR17 | COLOR21 | COLOR25 | COLOR29 |
| 10 | COLOR18 | COLOR22 | COLOR26 | COLOR30 |
| 11 | COLOR19 | COLOR23 | COLOR27 | COLOR31 |

COLOR16/20/24/28 are never used by unattached sprites. COLOR16-31 are also playfield colours
16-31 on a 5-plane screen -- plan the palette for both.

Example: a pixel row `0000123321000000` (colour numbers) gives A = bits where the colour is
odd, B = bits where it is 2 or 3:

```text
colours  0000 1233 2100 0000
A (bit0) 0000 1011 0100 0000  = $0B40
B (bit1) 0000 0111 1000 0000  = $0780
```

## SPRxPOS / SPRxCTL encoding

| Register | Bit(s) | Field |
|---|---|---|
| SPRxPOS | 15-8 | SV7-SV0: VSTART low 8 bits |
| SPRxPOS | 7-0 | SH8-SH1: HSTART bits 8-1 |
| SPRxCTL | 15-8 | EV7-EV0: VSTOP low 8 bits |
| SPRxCTL | 7 | ATTACH (odd-numbered sprite of a pair only) |
| SPRxCTL | 6-3 | 0 (ECS uses bits 4-3 for SuperHires positioning) |
| SPRxCTL | 2 | SV8: VSTART bit 8 |
| SPRxCTL | 1 | EV8: VSTOP bit 8 |
| SPRxCTL | 0 | SH0: HSTART bit 0 |

- VSTART/VSTOP are beam lines (VSTOP = first line **after** the sprite; height =
  VSTOP - VSTART). HSTART is in lores pixels, 9 bits (0-447 range).
- To place a sprite at display-window pixel (x, y) of a standard `$2C81` window:
  `VSTART = $2C + y`; `HSTART = $80 + x` (the horizontal offset of one pixel relative to the
  DIWSTRT value is unverified -- check against a bitplane pixel once).
- Coordinates never change with hires or interlace playfields.

```asm
; Write the position/control words of a sprite.
; in: d0.w = HSTART (9 bits), d1.w = VSTART (9 bits), d2.w = VSTOP (9 bits)
;     a0 -> sprite data (POS word). Keeps the ATTACH bit. Trashes d3-d5.
SetSpritePos:
        move.w  d1,d3
        lsl.w   #8,d3                   ; VSTART bits 7-0 -> 15-8
        move.w  d0,d4
        lsr.w   #1,d4
        move.b  d4,d3                   ; HSTART bits 8-1 -> 7-0
        move.w  d2,d4
        lsl.w   #8,d4                   ; VSTOP bits 7-0 -> 15-8
        move.w  d1,d5
        lsr.w   #6,d5
        and.w   #$0004,d5               ; VSTART bit 8 -> bit 2
        or.w    d5,d4
        move.w  d2,d5
        lsr.w   #7,d5
        and.w   #$0002,d5               ; VSTOP bit 8 -> bit 1
        or.w    d5,d4
        move.w  d0,d5
        and.w   #$0001,d5               ; HSTART bit 0 -> bit 0
        or.w    d5,d4
        move.w  2(a0),d5
        and.w   #$0080,d5               ; preserve ATTACH
        or.w    d5,d4
        move.w  d3,(a0)
        move.w  d4,2(a0)
        rts
```

Change these words only while the sprite DMA is not reading them (e.g. below the sprite or
after the last display line); otherwise one field can pick up the new start and the old stop
and glitch.

## Displaying sprites

1. Put every sprite list (and a **null sprite**) in chip RAM.
2. Load all eight SPRxPTH/SPRxPTL from the copper list, before the first display line, every
   field -- the pointers advance while the sprite is drawn. `SPRxPT` is `sprpt+x*4` in
   `hardware/custom.i`.
3. Enable `DMAF_SPRITE` (with `DMAF_MASTER`). Sprite DMA is all-or-nothing: once on, all eight
   channels run, so unused ones must point at the null sprite.
4. Set colours 17-19 (21-23, ...) and BPLCON2 priorities.

```asm
        section spritedata,data_c
ship:   dc.w    $8050,$8500             ; VSTART=$80 HSTART=$A0, VSTOP=$85 (5 lines)
        dc.w    $0180,$0000             ; 0000000110000000
        dc.w    $0240,$0180             ; 0000001221000000
        dc.w    $05a0,$03c0             ; 0000012332100000
        dc.w    $0240,$0180
        dc.w    $0180,$0000
        dc.w    0,0                     ; end: channel stops for this field
nullsprite:
        dc.w    0,0,0,0

coplist:
        dc.w    sprpt+$00,0,sprpt+$02,0 ; sprite 0 -> ship (patched at run time)
        dc.w    sprpt+$04,0,sprpt+$06,0 ; sprites 1-7 -> nullsprite (patched)
        ; ... sprpt+$08 .. sprpt+$1e likewise
        dc.w    color+$22,$0ff0         ; COLOR17 yellow
        dc.w    color+$24,$00ff         ; COLOR18 cyan
        dc.w    color+$26,$0f0f         ; COLOR19 magenta
        dc.w    bplcon2,$0024           ; sprites in front of both playfields
        dc.w    $ffff,$fffe
```

Enable with `move.w #DMAF_SETCLR!DMAF_MASTER!DMAF_COPPER!DMAF_RASTER!DMAF_SPRITE,dmacon(a6)`.
Turning sprite DMA off in the middle of a sprite leaves its last line repeating as a vertical
bar; only switch it during vertical blank.

## Attached sprites (15 colours)

Pairs 0+1, 2+3, 4+5, 6+7 can be attached: set ATTACH (SPRxCTL bit 7) in the **odd** sprite's
control word, give both sprites the same position and height. Each pixel then has 4 bits:

```text
colour = odd.B*8 + odd.A*4 + even.B*2 + even.A   ->  0 transparent, 1..15 = COLOR17..COLOR31
```

Both halves must move together; if they drift apart, each falls back to 3 colours and the
odd sprite picks colours 20/24/28 instead of its normal set.

## Reusing a channel

After the last data line, instead of `0,0` write the POS/CTL of the next use and its data;
end the chain with `0,0`. The next VSTART must be **at least one line below the previous
VSTOP** (the channel needs a blank line to fetch the new control words):
`VSTART(next) >= VSTOP(previous) + 1`. Reuses can have different shapes and positions; colour
changes between uses are copper MOVEs to COLOR17-31 on the gap line.

```asm
multi:  dc.w    $3050,$3400             ; use 1: lines $30-$33
        dc.w    $ffff,$0000,$ffff,$0000,$ffff,$0000,$ffff,$0000
        dc.w    $3570,$3900             ; use 2: VSTART $35 >= VSTOP $34 + 1
        dc.w    $0000,$ffff,$0000,$ffff,$0000,$ffff,$0000,$ffff
        dc.w    0,0
```

## Priorities

- Among sprites the order is fixed: sprite 0 in front of 1, ..., 7 at the back. Use a lower
  number for foreground objects when overlapping.
- Against playfields sprites are grouped in pairs; BPLCON2 PF1P/PF2P (0-4) put each playfield
  in front of all sprites (0), behind pair 0/1 (1), ... behind all (4). See
  [playfields.md](playfields.md#priorities-bplcon2).

## Hardware collision detection

CLXDAT (read-only) latches collisions; **reading it clears it**. CLXCON (write-only) selects
what counts:

| CLXCON bits | Meaning |
|---|---|
| 15-12 ENSP7/5/3/1 | include odd sprite 7/5/3/1 (ORed with 6/4/2/0) |
| 11-6 ENBP6-ENBP1 | include bitplane 6-1 in playfield matching |
| 5-0 MVBP6-MVBP1 | value the enabled plane must have for a "playfield" hit |

| CLXDAT bit | Collision |
|---|---|
| 14 / 13 / 12 | sprites 4(5)-6(7) / 2(3)-6(7) / 2(3)-4(5) |
| 11 / 10 / 9 | sprites 0(1)-6(7) / 0(1)-4(5) / 0(1)-2(3) |
| 8-5 | even planes (playfield 2) vs sprites 6(7), 4(5), 2(3), 0(1) |
| 4-1 | odd planes (playfield 1) vs sprites 6(7), 4(5), 2(3), 0(1) |
| 0 | playfield 1 vs playfield 2 |

A playfield "hit" happens where all enabled planes equal their match values; with no planes
enabled every pixel matches (collisions are always reported).

```asm
; each frame: did sprite 0 touch sprite 2, or any pixel with plane 1 set?
        move.w  #$0041,clxcon(a6)       ; ENBP1 + MVBP1: plane 1 must be 1
        ; ...                           ; one field later:
        move.w  clxdat(a6),d0           ; read clears
        btst    #9,d0                   ; sprite 0/1 vs sprite 2/3
        bne     .hitsprite
        btst    #1,d0                   ; odd planes vs sprite 0/1
        bne     .hitwall
```

## Manual (non-DMA) sprites

A sprite channel can be driven by the CPU or copper when its DMA is not using it: write SPRxPOS
and SPRxCTL (writing CTL disarms), then SPRxDATB and last SPRxDATA (writing DATA arms). The
same 16 pixels repeat on every line at HSTART until disarmed or reloaded -- e.g. a copper list
that rewrites SPR0DATA/DATB each line.

## Sprite DMA and DDFSTRT

Bitplane DMA outranks sprite DMA. A data fetch that starts earlier than the standard `$38`
takes cycles the sprite channels need, and those sprites vanish:

- HRM: DDFSTRT `$30` (one extra word for horizontal scrolling) disables sprite 7.
- Earlier starts lose more sprites, highest numbers first. Derived from the AmigaScope DMA
  recorder's sprite-slot positions (spr0 `$19`/`$1B`, spr1 `$1D`/`$1F`, ... 4 clocks apart):
  `$28` loses 5-7, `$20` loses 3-7, `$18` leaves only sprite 0 (unverified on OCS hardware).
- The amigascope-workflow skill's `dma_profile.py parse` reports exactly which sprite slots a
  given fetch start steals.

## Common mistakes

- Sprite data or the null sprite in fast RAM.
- Enabling sprite DMA with some SPRxPT never loaded: random memory is shown as sprites
  (the OS mouse pointer keeps running after `LoadView(NULL)` too).
- Writing the pointers once from the CPU instead of every field from the copper.
- Swapping the A and B words (colours 1 and 2 exchanged).
- Forgetting the 9th bits: sprites jump when crossing HSTART 256 or line 256.
- Setting ATTACH on the even sprite, or moving attached halves separately.
- Reusing a channel with no blank line between VSTOP and the next VSTART.
- Expecting CLXDAT to accumulate across reads (it clears on read) or reading it before a full
  field was drawn.
- Scrolling playfield with DDFSTRT `$30` plus 8 sprites: sprite 7 silently disappears.
