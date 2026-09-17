# Custom chips: blitter registers

The blitter is a word-based DMA device in Agnus with three sources (A, B, C) and one
destination (D). Each channel has a pointer, modulo and data register; A and B have
shift counters; A has first/last word masks. Every blitter register lives in
`$040`-`$07E`: the Copper can only write them with COPCON CDANG set. Load all registers
first; the write to BLTSIZE (or BLTSIZH on ECS) starts the blit, and the CPU keeps
running while the blit executes. Wait for DMACONR BBUSY = 0 before touching any blitter
register again.

## BLTCON0
`$DFF040` · write · Agnus · OCS · copper danger

Channel enables, A shift value and the minterm logic function of the blit.

| Bit | Name | Meaning (area mode) | Line mode |
|---|---|---|---|
| 15-12 | ASH3-ASH0 | shift source A right by 0-15 | start x mod 16 |
| 11 | USEA | enable source A (`SRCA`) | 1 |
| 10 | USEB | enable source B (`SRCB`) | 0 |
| 9 | USEC | enable source C (`SRCC`) | 1 |
| 8 | USED | enable destination D (`DEST`) | 1 |
| 7-0 | LF7-LF0 | minterms: which A/B/C combinations give D = 1 | minterms |

| Bit | Mask | NDK | A | B | C |
|---|---|---|---|---|---|
| 7 | $80 | `ABC` | 1 | 1 | 1 |
| 6 | $40 | `ABNC` | 1 | 1 | 0 |
| 5 | $20 | `ANBC` | 1 | 0 | 1 |
| 4 | $10 | `ANBNC` | 1 | 0 | 0 |
| 3 | $08 | `NABC` | 0 | 1 | 1 |
| 2 | $04 | `NABNC` | 0 | 1 | 0 |
| 1 | $02 | `NANBC` | 0 | 0 | 1 |
| 0 | $01 | `NANBNC` | 0 | 0 | 0 |

Common minterms: D = A `$F0`; D = C `$AA`; D = A OR C `$FA`; D = A XOR C `$5A`;
cookie-cut D = AB + (NOT A)C `$CA` (A = mask, B = image, C = background); clear D `$00`.

NDK: `bltcon0` (custom.i); `ABC`...`NANBNC`, `SRCA`, `SRCB`, `SRCC`, `DEST`,
`BC0F_SRCA`...`BC0F_DEST`, `BC0B_SRCA`...`BC0B_DEST`, `ASHIFTSHIFT` (12) (blit.i);
C also `A_OR_B`, `A_OR_C`, `A_XOR_C`, `A_TO_D` (blit.h); `custom->bltcon0`.

### Example
```asm
; copy one 320x200 lores plane: a0 = source, a1 = destination (chip RAM)
        include "hardware/blit.i"
        bsr     WaitBlitter                     ; see DMACONR
        move.w  #SRCA!DEST!$f0,bltcon0(a6)      ; D = A
        move.w  #0,bltcon1(a6)
        move.l  #-1,bltafwm(a6)                 ; BLTAFWM and BLTALWM = $FFFF
        move.w  #0,bltamod(a6)
        move.w  #0,bltdmod(a6)
        move.l  a0,bltapt(a6)
        move.l  a1,bltdpt(a6)
        move.w  #(200<<HSIZEBITS)!(320/16),bltsize(a6)   ; starts the blit: LAST
```

### Gotchas
- A disabled source still provides a constant from its data register (BLTxDAT), which is
  how masks and fills are done without fetching memory.
- Enabling B costs two extra clock ticks per word; C and D together cost two more.
  A-to-D copies are the fastest.
- Never write blitter registers while a blit runs (OS code: `OwnBlitter` / `WaitBlit`,
  see the amiga-os skill).
- Line mode reuses these bits differently: see BLTCON1.

**See also:** BLTCON1, BLTSIZE, BLTAFWM, [DMACONR](dma-beam.md#dmaconr), [COPCON](copper.md#copcon)

## BLTCON0L
`$DFF05A` · write · Agnus · ECS · copper danger

ECS shortcut that writes only BLTCON0 bits 7-0 (the minterms).

NDK: `bltcon0l EQU $05B` (custom.i, byte offset, "byte access only"); C `custom->bltcon0l`
(UBYTE).

### Example
```asm
        move.b  #$ca,bltcon0l(a6)               ; change minterm only (ECS/AGA)
```

### Gotchas
- The NDK label addresses the low byte (`$05B`): use `move.b`, not `move.w`.
- Not on OCS Agnus: code that must run on OCS writes the full BLTCON0.

**See also:** BLTCON0

## BLTCON1
`$DFF042` · write · Agnus · OCS (ECS bit 7 DOFF) · copper danger

Area/line mode select, B shift, fill modes and direction; in line mode, octant and flags.

Area mode (bit 0 = 0):

| Bit | Name | Meaning | NDK |
|---|---|---|---|
| 15-12 | BSH3-BSH0 | shift source B right by 0-15 | `BSHIFTSHIFT` (12) |
| 11-8 | -- | write 0 | |
| 7 | DOFF | ECS: D output disabled (bus tristated, for external logic) | |
| 6-5 | -- | write 0 | |
| 4 | EFE | exclusive fill | `FILL_XOR` $10 |
| 3 | IFE | inclusive fill | `FILL_OR` $08 |
| 2 | FCI | fill carry input (starting fill state) | `FILL_CARRYIN` $04 |
| 1 | DESC | descending: pointers step -2, modulos subtracted | `BLITREVERSE` / `BC1F_DESC` $02 |
| 0 | LINE | 0 = area mode | |

Line mode (bit 0 = 1):

| Bit | Name | Meaning | NDK |
|---|---|---|---|
| 15-12 | TEXTURE3-0 | bit of BLTBDAT the texture starts at | |
| 11-7 | -- | write 0 | |
| 6 | SIGN | 1 if (4*dy - 2*dx) < 0 | `SIGNFLAG` $40 |
| 5 | OVF | write 0 | `OVFLAG` $20 |
| 4-2 | SUD SUL AUL | octant code | `SUD` $10, `SUL` $08, `AUL` $04, `OCTANT1`-`OCTANT8` |
| 1 | SING | one pixel per row (outlines for area fill) | `ONEDOT` $02 |
| 0 | LINE | 1 = line mode | `LINEMODE` $01 |

Octant codes (bits 4-2) from blit.i: `OCTANT1` 16, `OCTANT2` 0, `OCTANT3` 8,
`OCTANT4` 20, `OCTANT5` 28, `OCTANT6` 12, `OCTANT7` 4, `OCTANT8` 24 (the HRM numbers
the same octants 7..0: HRM octant n = `OCTANT(8-n)`).

Line setup (HRM): dx = max(|x2-x1|, |y2-y1|), dy = min(...); BLTADAT `$8000`, BLTBDAT
texture (`$FFFF` solid), BLTAFWM/BLTALWM `$FFFF`, BLTAMOD `4*(dy-dx)`, BLTBMOD `4*dy`,
BLTCMOD/BLTDMOD = bitplane width in bytes, BLTAPTL `4*dy - 2*dx`, BLTCPT/BLTDPT = word
holding the first pixel, BLTCON0 = `(x1 & 15) << 12 | SRCA!SRCC!DEST | $CA`
(or `$4A` for XOR lines), BLTSIZE = `(dx+1) << 6 | 2`.

NDK: `bltcon1` (custom.i); flags above (blit.i); C `custom->bltcon1`.

### Gotchas
- Area fill works only in descending mode (DESC = 1), on outlines drawn with SING.
- DESC reverses everything: pointers must address the LAST word, BLTAFWM masks the last
  (rightmost) word of each row and BLTALWM the first.
- Line mode width must be 2 and height is the line length (dx + 1).
- `BLITREVERSE` and `ONEDOT` are both `$02`: same bit, different mode.

**See also:** BLTCON0, BLTSIZE, BLTxMOD, BLTxDAT

## BLTAFWM
`$DFF044` · write · Agnus · OCS · copper danger

Mask ANDed with the first word of every row of source A (a 0 bit blocks A's data).

NDK: `bltafwm` (custom.i); C `custom->bltafwm`.

### Gotchas
- Set to `$FFFF` for fill and line modes.
- BLTAFWM and BLTALWM are adjacent: `move.l #-1,bltafwm(a6)` sets both.
- A one-word-wide blit applies both masks to the same word.
- The masks apply to source A data only: to mask a B or C copy, keep A disabled with
  BLTADAT `$FFFF` and use a minterm that ANDs with A.

**See also:** BLTALWM, BLTCON0

## BLTALWM
`$DFF046` · write · Agnus · OCS · copper danger

Mask ANDed with the last word of every row of source A.

NDK: `bltalwm` (custom.i); C `custom->bltalwm`.

### Example
```asm
; image 23 pixels wide stored in 2 words: keep only those 23 bits
        move.w  #$ffff,bltafwm(a6)
        move.w  #$fe00,bltalwm(a6)              ; last word: 7 bits used
```

**See also:** BLTAFWM

## BLTxPTH, BLTxPTL
`$DFF048`-`$DFF056` · write · Agnus · OCS (high word: 3 address bits OCS, 5 ECS) · pointer pairs, x = A, B, C, D; copper danger

Chip-RAM address of the next word for source A, B, C or destination D.

| x | BLTxPTH | BLTxPTL | NDK |
|---|---|---|---|
| C | `$DFF048` | `$DFF04A` | `bltcpt` |
| B | `$DFF04C` | `$DFF04E` | `bltbpt` |
| A | `$DFF050` | `$DFF052` | `bltapt` |
| D | `$DFF054` | `$DFF056` | `bltdpt` |

Note the address order C, B, A, D. NDK labels are longwords (custom.i); C
`custom->bltcpt` etc.

### Gotchas
- Load them with `move.l` before every blit: after a blit they hold the last address plus
  increment and modulo, not your start address.
- Chip RAM only. Pointers of disabled channels are ignored.
- Line mode: BLTAPTL is the error accumulator (`4*dy - 2*dx`), not an address.

**See also:** BLTxMOD, BLTSIZE

## BLTSIZE
`$DFF058` · write · Agnus · OCS · copper danger · starts the blit

Blit height (lines) and width (words); the write starts the blitter.

| Bit | Name | Meaning |
|---|---|---|
| 15-6 | H9-H0 | height in lines, 1-1024 (0 = 1024) |
| 5-0 | W5-W0 | width in words, 1-64 (0 = 64) |

NDK: `bltsize` (custom.i); `HSIZEBITS` (6), `VSIZEBITS`, `HSIZEMASK` ($3F), `VSIZEMASK`
($3FF), `MINBYTESPERROW`, `MAXBYTESPERROW` (blit.i); C `custom->bltsize`.

### Example
```asm
        move.w  #(64<<HSIZEBITS)!2,bltsize(a6)  ; 64 lines x 2 words (32 pixels)
```

### Gotchas
- Write it LAST, after every pointer, modulo, mask and control register.
- Width is in WORDS, height in lines; line mode: width 2, height = line length.
- Wait for the previous blit to finish before loading the next one; CPUs faster than a
  68000 regularly start the next setup mid-blit.
- On ECS/AGA use BLTSIZV + BLTSIZH for anything larger than 1024x1024.

**See also:** BLTSIZV, BLTSIZH, [DMACONR](dma-beam.md#dmaconr), BLTCON0

## BLTSIZV
`$DFF05C` · write · Agnus · ECS · copper danger

ECS blit height, 15 bits (up to 32768 lines); written before BLTSIZH.

| Bit | Meaning |
|---|---|
| 15 | write 0 |
| 14-0 | height in lines |

NDK: `bltsizv` (custom.i); C `custom->bltsizv`. graphics.library sets `GFXF_BIG_BLITS`
in `GfxBase->ChipRevBits0` when these registers exist.

### Gotchas
- Does not start the blit; it keeps its value, so it need not be rewritten when the
  height is unchanged.
- Not on OCS Agnus.

**See also:** BLTSIZH, BLTSIZE

## BLTSIZH
`$DFF05E` · write · Agnus · ECS · copper danger · starts the blit

ECS blit width, 11 bits (up to 32768 pixels); the write starts the blit.

| Bit | Meaning |
|---|---|
| 15-11 | write 0 |
| 10-0 | width in words |

NDK: `bltsizh` (custom.i); C `custom->bltsizh`.

### Example
```asm
        move.w  #1200,bltsizv(a6)               ; height first
        move.w  #80,bltsizh(a6)                 ; 80 words wide: starts the blit
```

**See also:** BLTSIZV, BLTSIZE

## BLTxMOD
`$DFF060`-`$DFF066` · write · Agnus · OCS · x = C, B, A, D; copper danger

Signed modulo added to channel x's pointer at the end of each row.

| x | Address | NDK |
|---|---|---|
| C | `$DFF060` | `bltcmod` |
| B | `$DFF062` | `bltbmod` |
| A | `$DFF064` | `bltamod` |
| D | `$DFF066` | `bltdmod` |

Value = bytes per row of that bitmap - (2 * blit width in words). C `custom->bltcmod` etc.

### Gotchas
- Even values only; different sources may have different row widths.
- In descending mode the modulo is subtracted.
- Line mode: BLTAMOD = `4*(dy-dx)`, BLTBMOD = `4*dy`, BLTCMOD = BLTDMOD = bitplane
  width in bytes.

**See also:** BLTxPTH, BLTxPTL, BLTSIZE

## BLTxDAT
`$DFF070`-`$DFF074` · write · Agnus · OCS · x = C, B, A; copper danger

Source data register: filled by DMA when the channel is enabled, otherwise a constant.

| x | Address | NDK |
|---|---|---|
| C | `$DFF070` | `bltcdat` |
| B | `$DFF072` | `bltbdat` |
| A | `$DFF074` | `bltadat` |

C `custom->bltcdat` etc.

### Example
```asm
; fill a plane with a pattern: B disabled, constant in BLTBDAT, D = B
        move.w  #$aaaa,bltbdat(a6)
        move.w  #DEST!$cc,bltcon0(a6)           ; $CC = ABC+ABNC+NABC+NABNC = B
```

### Gotchas
- Line mode: BLTADAT must be `$8000` (moving pixel), BLTBDAT is the texture (`$FFFF` solid).
- These registers are write-only: you cannot read back what the DMA loaded.

**See also:** BLTCON0, BLTDDAT

## BLTDDAT
`$DFF000` · DMA-only (early read) · Agnus · OCS · never accessed by the CPU

Holds each result word until the blitter writes it to destination D.

NDK: `bltddat` (custom.i); C `custom->bltddat`.

### Gotchas
- A dummy address: the CPU cannot read the result through it. Read the destination
  memory instead.

**See also:** BLTxDAT, BLTxPTH, BLTxPTL
