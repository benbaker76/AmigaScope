# Playfields: bitplanes, display window, scrolling

Bitplane displays: modes, window/fetch formulas, modulos, scrolling, EHB, HAM, interlace.

A playfield is 1-6 bitplanes in chip RAM, fetched by bitplane DMA and serialised by Denise.
You describe it with BPLCON0, the display window (DIWSTRT/DIWSTOP), the data fetch window
(DDFSTRT/DDFSTOP), the modulos and the plane pointers -- normally all from a copper list
([copper.md](copper.md)), because the plane pointers must be reloaded every field.

Registers: [BPLCON0](../registers/playfield.md#bplcon0),
[BPLCON1](../registers/playfield.md#bplcon1), [BPLCON2](../registers/playfield.md#bplcon2),
[BPL1MOD](../registers/playfield.md#bpl1mod), [BPL2MOD](../registers/playfield.md#bpl2mod),
[BPLxPTH, BPLxPTL](../registers/playfield.md#bplxpth-bplxptl),
[DIWSTRT](../registers/playfield.md#diwstrt), [DIWSTOP](../registers/playfield.md#diwstop),
[DDFSTRT](../registers/playfield.md#ddfstrt), [DDFSTOP](../registers/playfield.md#ddfstop),
[COLORxx](../registers/playfield.md#colorxx), [VPOSR](../registers/dma-beam.md#vposr).

## Bitplanes and colour selection

Each pixel's colour register number is built from one bit per plane: plane 1 is bit 0 (least
significant) ... plane 5 is bit 4. With 5 planes a pixel can select COLOR00-COLOR31.

| Colours | Planes |
|---|---|
| 2 | 1 |
| 4 | 2 |
| 8 | 3 |
| 16 | 4 |
| 32 | 5 |
| 64 (EHB) / 4096 (HAM6) | 6 |

- Colour registers hold `$0RGB` (bits 11-8 red, 7-4 green, 3-0 blue; bits 15-12 = 0). They are
  write-only: keep a shadow copy if you need to read colours back.
- COLOR00 is the background: shown wherever no plane bit is set and in the whole border
  outside the display window.
- COLOR16-COLOR31 are also the **sprite colours** (see [sprites.md](sprites.md)): a 5-plane
  playfield and sprites share them.
- A plane is a run of words: `bytes per row = width / 8` (must be even, i.e. width a multiple
  of 16 is simplest); `plane size = bytes per row * rows`. Bitplanes must be in chip RAM.

## BPLCON0

| Bit | Name | Meaning |
|---|---|---|
| 15 | HIRES | 1 = hires (640 across), max 4 planes |
| 14-12 | BPU2-0 | number of planes 0-6 (7 invalid); 0 = background colour only |
| 11 | HOMOD | hold-and-modify (with 5 or 6 planes, lores, single playfield) |
| 10 | DBLPF | dual playfield |
| 9 | COLOR | composite colour burst (only matters on the A1000 composite output) |
| 8 | GAUD | genlock audio |
| 3 | LPEN | light pen enable (freezes the beam counters -- keep 0) |
| 2 | LACE | interlace |
| 1 | ERSY | external sync (genlock) -- keep 0 |

ECS adds bit 6 SHRES and bit 0 (see [ecs.md](ecs.md)). The bits are not independent: always
write the complete word.

| Mode | BPLCON0 |
|---|---|
| lores 1 / 2 / 3 / 4 / 5 planes | `$1200` / `$2200` / `$3200` / `$4200` / `$5200` |
| lores 6 planes EHB | `$6200` |
| lores 6 planes HAM6 | `$6A00` |
| dual playfield 3+3 lores | `$6600` |
| hires 4 planes | `$C200` |
| hires 2 planes interlaced | `$A204` |

## Display window: DIWSTRT / DIWSTOP

The display window is where playfield (and sprite) pixels may appear; everything else shows
COLOR00. Coordinates are **always lores, non-interlaced**, whatever the mode.

- `DIWSTRT = VSTART<<8 ! HSTART`. HSTART 0-`$FF` (implicit H8 = 0), VSTART 0-`$FF`.
- `DIWSTOP = (VSTOP&$FF)<<8 ! (HSTOP&$FF)`. HSTOP is `$100`-`$1FF` (implicit H8 = 1: write
  HSTOP-`$100`). VSTOP's hidden bit 8 is the complement of bit 7, so VSTOP covers `$080`-`$17F`.
- `HSTOP = HSTART + width in lores pixels` (640 hires pixels = 320 lores);
  `VSTOP = VSTART + height in non-lace lines`.
- Nothing is shown during vertical blank: PAL lines 0-`$1C` (29 lines), NTSC 0-`$14` (21 lines).

| Standard screen | DIWSTRT | DIWSTOP | DDFSTRT | DDFSTOP | bytes/row |
|---|---|---|---|---|---|
| PAL lores 320x256 | `$2C81` | `$2CC1` | `$0038` | `$00D0` | 40 |
| NTSC lores 320x200 | `$2C81` | `$F4C1` | `$0038` | `$00D0` | 40 |
| PAL hires 640x256 | `$2C81` | `$2CC1` | `$003C` | `$00D4` | 80 |
| NTSC hires 640x200 | `$2C81` | `$F4C1` | `$003C` | `$00D4` | 80 |

(Interlaced 512/400-line screens use the same window values.)

ECS lifts the window limits with DIWHIGH ([ecs.md](ecs.md)).

## Data fetch: DDFSTRT / DDFSTOP

The fetch window says on which horizontal positions (colour clocks) bitplane words are
fetched. Lores respects multiples of `$08`, hires multiples of `$04`. The hardware needs time
between fetch and display, which fixes the relationship to HSTART:

| | lores | hires |
|---|---|---|
| DDFSTRT | `(HSTART - 17) / 2` | `(HSTART - 9) / 2` |
| DDFSTOP | `DDFSTRT + 8*(words - 1)` | `DDFSTRT + 4*(words - 2)` |
| bytes fetched per line | `2*((DDFSTOP-DDFSTRT)/8 + 1)` | `2*((DDFSTOP-DDFSTRT)/4 + 2)` |

`words` = pixels across / 16. Check: lores `($81-17)/2 = $38`, `$38+8*19 = $D0`; hires
`($81-9)/2 = $3C`, `$3C+4*38 = $D4`.

Limits: DDFSTRT >= `$18`, DDFSTOP <= `$D8` (25 lores words, 49 hires words); horizontal
blanking hides everything beyond about 368 lores pixels. **A DDFSTRT below `$38` steals the
sprite DMA slots:** `$30` (one extra word, needed for scrolling) disables sprite 7; earlier
values lose more sprites, highest-numbered first. See
[sprites.md](sprites.md#sprite-dma-and-ddfstrt).

## Modulos and plane pointers

After the last fetched word of a line, the signed 16-bit modulo (in bytes) is added to the
plane pointer. BPL1MOD applies to the odd planes (1,3,5), BPL2MOD to the even planes (2,4,6).

```text
modulo = stored bytes per row - bytes fetched per line   (+ one row if interleaved lace)
```

The pointers advance as the field is displayed, so they must be rewritten before every field:
put the BPLxPTH/BPLxPTL MOVEs in the copper list. `BPLxPTH` is `bplpt+(x-1)*4`,
`BPLxPTL` is `bplpt+(x-1)*4+2` in `hardware/custom.i`.

### Worked example: PAL overscan 352x272 lores

```text
width 352 = 22 words, height 272
HSTART = $81 - 16 = $71          HSTOP = $71 + 352 = $1D1 -> write $D1
VSTART = $2C - 8  = $24          VSTOP = $24 + 272 = $134 -> write $34 (bit 7 = 0 -> bit 8 = 1)
DIWSTRT = $2471                  DIWSTOP = $34D1
DDFSTRT = ($71 - 17)/2 = $30     DDFSTOP = $30 + 8*21 = $D8 (hardware maximum)
fetched = 2*(($D8-$30)/8 + 1) = 44 bytes = 352/8 -> modulo 0
side effect: DDFSTRT $30 -> sprite 7 unusable
```

## Vertical scrolling

Move the starting pointer by whole rows: `pointer = plane + y * bytes_per_row` (written into
the copper list during vertical blank). In interlace, scroll by 2 stored rows to keep the
long/short field order.

## Horizontal scrolling (BPLCON1)

BPLCON1 delays the serialised data by 0-15 lores pixels: bits 3-0 for playfield 1 (odd
planes), bits 7-4 for playfield 2 (even planes). In hires one delay step is 2 hires pixels.

Recipe for a lores playfield wider than the window:

1. Fetch one extra word: DDFSTRT one word earlier (`$30` instead of `$38`), DDFSTOP unchanged.
   The extra word lands left of the window and is hidden.
2. Modulo = stored bytes per row - 42 (320 wide window).
3. Per field, for scroll position `sx` (pixels):
   `pointer = row start + (sx>>4)*2`, `BPLCON1 = (15 - (sx&15)) * $11`.
   The left window edge then shows stored column `sx+1` (a constant 1-pixel offset -- derived
   from the HRM rules, unverified on hardware).

```asm
; d0 = sx (0 .. storedwidth-336), a6 = $dff000
; patches the copper list values for 5 planes of a 640x256 playfield (80 bytes/row)
SetScrollX:
        move.w  d0,d1
        and.w   #$000f,d1
        moveq   #15,d2
        sub.w   d1,d2                   ; delay = 15 - (sx & 15)
        move.w  d2,d1
        lsl.w   #4,d1
        or.w    d2,d1                   ; same delay for PF1 and PF2
        move.w  d1,cop_bplcon1+2        ; value word of "dc.w bplcon1,xxxx"
        moveq   #0,d1
        move.w  d0,d1
        lsr.w   #4,d1
        add.w   d1,d1                   ; byte offset of the first fetched word
        lea     cop_planes+2,a0
        lea     planes,a1
        moveq   #5-1,d7
.p      lea     (a1,d1.l),a2
        move.l  a2,d2
        swap    d2
        move.w  d2,(a0)                 ; BPLxPTH value
        swap    d2
        move.w  d2,4(a0)                ; BPLxPTL value
        addq.l  #8,a0
        lea     80*256(a1),a1
        dbf     d7,.p
        rts
```

(`cop_bplcon1`, `cop_planes` and `planes` are labels in your copper list and chip BSS, as in
the complete example below.) Patch while the copper is not reading those words: the list is
re-read every field, so any time after the copper has executed the MOVEs (early in the field)
and before the next vertical-blank restart is safe -- typically from a copper interrupt or a
beam wait below the last display line. Writing the two words of a pointer pair is not atomic;
avoid the first lines after vertical blank starts, when the copper executes them.

## Dual playfield

Set DBLPF (BPLCON0 bit 10). Planes 1,3,5 form playfield 1, planes 2,4,6 playfield 2; each has
up to 3 planes (2 in hires).

| | Playfield 1 | Playfield 2 |
|---|---|---|
| planes | 1, 3, 5 (bit weights 1,2,4) | 2, 4, 6 (bit weights 1,2,4) |
| colours | 000 transparent, 001-111 -> COLOR01-COLOR07 | 000 transparent, 001-111 -> COLOR09-COLOR15 |
| modulo | BPL1MOD | BPL2MOD |
| scroll delay | BPLCON1 bits 3-0 | BPLCON1 bits 7-4 |

- Playfield 1 is in front unless BPLCON2 bit 6 (PF2PRI) is set. Where both are transparent,
  COLOR00 shows.
- Both playfields share DDFSTRT/DDFSTOP. If you scroll only one of them (with DDFSTRT `$30`),
  give the stationary one modulo `-2` and a pointer 2 bytes before its row start (hires: `-4`
  and 4 bytes), so it stays put.

## Priorities (BPLCON2)

Sprites are prioritised in four pairs (0/1 front ... 6/7 back). PF1P (bits 2-0) and PF2P
(bits 5-3) place each playfield among them:

| Code | Playfield position |
|---|---|
| 0 | in front of all sprites |
| 1 | behind sprites 0/1 |
| 2 | behind 0-3 |
| 3 | behind 0-5 |
| 4 | behind all sprites |

`$0024` = both playfields behind all sprites; `$0000` = both in front. The HRM notes that in
single-playfield mode PF2P (bits 5-3) holds the playfield's code, so write the same code into
both fields. Bit 6 PF2PRI puts playfield 2 in front of playfield 1.

## Extra Half-Brite (EHB)

Six planes, HOMOD = 0, DBLPF = 0 (`BPLCON0 = $6200`). Planes 1-5 select COLOR00-COLOR31;
when plane 6 is set that colour is shown at half intensity -- 64 colours from 32 registers.
(ECS: BPLCON2 bit 9 KILLEHB turns this off.)

## Hold-and-modify (HAM6)

Six lores planes, HOMOD = 1 (`BPLCON0 = $6A00`). Planes 6 and 5 form a control code for each
pixel; planes 4-1 form a 4-bit value:

| Plane 6,5 | Result |
|---|---|
| 00 | colour = COLOR00-COLOR15 selected by planes 4-1 |
| 01 | copy the pixel to the left, replace **blue** with the value |
| 10 | copy the pixel to the left, replace **red** with the value |
| 11 | copy the pixel to the left, replace **green** with the value |

With only 5 planes and HOMOD, plane 6 reads as 0 (palette or blue modify only). The colour
"to the left" of the first pixel on a line is the border/background colour (unverified).
HAM needs HIRES = 0 and DBLPF = 0.

## Interlace

- Set LACE (BPLCON0 bit 2) in the copper list. The display window stays in non-lace
  coordinates (PAL `$2C81`/`$2CC1` gives 512 lines).
- Store the image interleaved (row 0, 1, 2, ... of the 512-line image) and use
  `modulo = bytes per row` (plus any width difference) so each field skips the other field's
  rows.
- Long field (VPOSR bit 15 LOF = 1): pointers at the plane start. Short field (LOF = 0):
  pointers one row later. Use two copper lists and select them in the vertical-blank
  interrupt ([copper.md](copper.md#interlace)).
- Scroll vertically by 2 rows; keep the window height even.

## Complete example: 320x256, 32 colours (PAL)

Assumes the machine has been taken over ([system-takeover.md](system-takeover.md)) and
`a6 = $dff000`. Draws 32 horizontal colour bands and waits for the left mouse button.

```asm
        include "hardware/custom.i"
        include "hardware/dmabits.i"
        include "hardware/cia.i"

PLANES  equ     5
WIDTH   equ     320
HEIGHT  equ     256
BPR     equ     WIDTH/8                 ; bytes per row

        section code,code
ShowScreen:
        lea     cop_planes+2,a0         ; value word of the first BPLxPTH MOVE
        lea     planes,a1
        moveq   #PLANES-1,d7
.pl     move.l  a1,d0
        swap    d0
        move.w  d0,(a0)                 ; BPLxPTH
        swap    d0
        move.w  d0,4(a0)                ; BPLxPTL
        addq.l  #8,a0
        lea     BPR*HEIGHT(a1),a1
        dbf     d7,.pl

        lea     cop_sprites+2,a0        ; all 8 sprites -> null sprite
        move.l  #nullsprite,d0
        moveq   #8-1,d7
.sp     swap    d0
        move.w  d0,(a0)
        swap    d0
        move.w  d0,4(a0)
        addq.l  #8,a0
        dbf     d7,.sp

        bsr.s   DrawBands

        move.l  #coplist,cop1lc(a6)
        move.w  d0,copjmp1(a6)
        move.w  #DMAF_SETCLR!DMAF_MASTER!DMAF_RASTER!DMAF_COPPER!DMAF_SPRITE,dmacon(a6)

.wait   btst    #CIAB_GAMEPORT0,$bfe001 ; left mouse button, 0 = pressed
        bne.s   .wait
        rts

; band colour = y/8 (0..31); set plane k rows where bit k of the colour is 1
DrawBands:
        lea     planes,a0
        moveq   #0,d6                   ; plane number k
.plane  move.l  a0,a1
        moveq   #0,d4                   ; y
        move.w  #HEIGHT-1,d5
.row    move.w  d4,d0
        lsr.w   #3,d0
        btst    d6,d0
        sne     d1
        ext.w   d1                      ; $FFFF or $0000
        moveq   #BPR/2-1,d3
.word   move.w  d1,(a1)+
        dbf     d3,.word
        addq.w  #1,d4
        dbf     d5,.row
        lea     BPR*HEIGHT(a0),a0
        addq.w  #1,d6
        cmp.w   #PLANES,d6
        bne.s   .plane
        rts

        section copper,data_c
coplist:
        dc.w    diwstrt,$2c81,diwstop,$2cc1
        dc.w    ddfstrt,$0038,ddfstop,$00d0
        dc.w    bplcon0,$5200           ; 5 lores planes
        dc.w    bplcon1,$0000
        dc.w    bplcon2,$0024
        dc.w    bpl1mod,$0000,bpl2mod,$0000
cop_planes:
        dc.w    bplpt+$00,0,bplpt+$02,0
        dc.w    bplpt+$04,0,bplpt+$06,0
        dc.w    bplpt+$08,0,bplpt+$0a,0
        dc.w    bplpt+$0c,0,bplpt+$0e,0
        dc.w    bplpt+$10,0,bplpt+$12,0
cop_sprites:
        dc.w    sprpt+$00,0,sprpt+$02,0
        dc.w    sprpt+$04,0,sprpt+$06,0
        dc.w    sprpt+$08,0,sprpt+$0a,0
        dc.w    sprpt+$0c,0,sprpt+$0e,0
        dc.w    sprpt+$10,0,sprpt+$12,0
        dc.w    sprpt+$14,0,sprpt+$16,0
        dc.w    sprpt+$18,0,sprpt+$1a,0
        dc.w    sprpt+$1c,0,sprpt+$1e,0
        dc.w    color+$00,$000,color+$02,$111,color+$04,$222,color+$06,$333
        dc.w    color+$08,$444,color+$0a,$555,color+$0c,$666,color+$0e,$777
        dc.w    color+$10,$888,color+$12,$999,color+$14,$aaa,color+$16,$bbb
        dc.w    color+$18,$ccc,color+$1a,$ddd,color+$1c,$eee,color+$1e,$fff
        dc.w    color+$20,$f00,color+$22,$f40,color+$24,$f80,color+$26,$fc0
        dc.w    color+$28,$ff0,color+$2a,$cf0,color+$2c,$8f0,color+$2e,$4f0
        dc.w    color+$30,$0f0,color+$32,$0f4,color+$34,$0f8,color+$36,$0fc
        dc.w    color+$38,$0ff,color+$3a,$0cf,color+$3c,$08f,color+$3e,$04f
        dc.w    $ffff,$fffe
nullsprite:
        dc.w    0,0,0,0

        section planes,bss_c
planes: ds.b    BPR*HEIGHT*PLANES
```

## Common mistakes

- Bitplanes allocated in fast RAM, or an odd number of bytes per row.
- Setting plane pointers once from the CPU and expecting them to stay: they advance every field;
  reload them in the copper list.
- DIWSTOP written with the real HSTOP (`$1C1`) instead of its low byte, or a VSTOP outside
  `$80`-`$17F`.
- DDFSTRT/DDFSTOP not matching DIWSTRT: the picture is shifted by a word or the left/right
  columns are garbage.
- Forgetting the modulo when the stored image is wider than the fetch window (image shears
  diagonally).
- Using 5 or more hires planes (not allowed), or HAM with HIRES/DBLPF set.
- Enabling HAM/EHB with 5 planes and expecting 64 colours (EHB needs 6 planes).
- Sprites disappearing after switching to a wide or scrolling display (DDFSTRT < `$38`).
- Updating BPLCON1 and the plane pointers at different times: one field shows a 16-pixel jump.
- BPLCON1 with only bits 3-0 set in single-playfield mode: the even planes are not delayed and
  the colours split. Set both nibbles.
