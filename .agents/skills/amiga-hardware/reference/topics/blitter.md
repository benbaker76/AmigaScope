# Blitter: copies, masks, fills and lines

How to program the blitter for block copies, cookie-cut bobs, area fill and line drawing.

The blitter is a DMA word processor in Agnus: up to three sources (A, B, C) combined by a
logic function into one destination (D), row by row over a rectangle of words. It runs
asynchronously -- the CPU continues while the blit executes. Everything it reads or writes
must be in **chip RAM**.

Registers: [BLTCON0](../registers/blitter.md#bltcon0), [BLTCON0L](../registers/blitter.md#bltcon0l),
[BLTCON1](../registers/blitter.md#bltcon1), [BLTAFWM](../registers/blitter.md#bltafwm),
[BLTALWM](../registers/blitter.md#bltalwm), [BLTxPTH, BLTxPTL](../registers/blitter.md#bltxpth-bltxptl),
[BLTSIZE](../registers/blitter.md#bltsize), [BLTSIZV](../registers/blitter.md#bltsizv),
[BLTSIZH](../registers/blitter.md#bltsizh), [BLTxMOD](../registers/blitter.md#bltxmod),
[BLTxDAT](../registers/blitter.md#bltxdat), [BLTDDAT](../registers/blitter.md#bltddat),
[DMACONR](../registers/dma-beam.md#dmaconr). NDK constants: `hardware/blit.i`.

## Channels, pointers, size, modulos

- **Enable bits** (BLTCON0 bits 11-8): `SRCA` `$0800`, `SRCB` `$0400`, `SRCC` `$0200`,
  `DEST` `$0100`. A disabled source is not fetched; its **BLTxDAT** value is used as a constant
  for every word.
- **Pointers** BLTAPT/BLTBPT/BLTCPT/BLTDPT: long writes, even chip RAM addresses. After a blit
  they point past the processed area.
- **BLTSIZE** = `height<<6 ! width`: width in **words** 1-64 (0 = 64), height in rows 1-1024
  (0 = 1024). **Writing BLTSIZE starts the blit -- write it last.** (ECS big blits:
  [ecs.md](ecs.md).)
- **Modulos** BLTxMOD: signed bytes added to each pointer after every row.
  `modulo = bytes per row of that bitmap - 2 * blit width in words`. Each channel has its own,
  so sources and destination can have different row widths.
- Pointer to word containing pixel (x, y): `plane + y*bytes_per_row + (x>>4)*2`.

## Minterms (the logic function)

BLTCON0 bits 7-0 (LF7-LF0) hold one output bit for each of the eight A/B/C combinations. Bit
number = `A*4 + B*2 + C`; set the bit if D should be 1 for that combination.

| LF bit | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|
| A B C | 111 | 110 | 101 | 100 | 011 | 010 | 001 | 000 |
| NDK name | `ABC` | `ABNC` | `ANBC` | `ANBNC` | `NABC` | `NABNC` | `NANBC` | `NANBNC` |

Build a function by OR-ing the columns where it is true. Shortcuts: A = `$F0`, B = `$CC`,
C = `$AA`; NOT x = `$FF - x`; AND/OR/XOR of functions = bitwise AND/OR/XOR of these bytes.

| Wanted D | Derivation | Minterm | BLTCON0 (with channels) |
|---|---|---|---|
| A (copy) | A | `$F0` | `$09F0` (A,D) |
| B | B | `$CC` | `$05CC` (B,D) |
| C | C | `$AA` | `$03AA` (C,D) |
| clear | none | `$00` | `$0100` (D only) |
| fill with 1s | all | `$FF` | `$01FF` (D only) |
| A OR C | `$F0 ! $AA` | `$FA` | `$0BFA` (A,C,D) |
| A XOR C | `$F0 ^ $AA` | `$5A` | `$0B5A` |
| NOT A AND C (punch hole) | `$0F & $AA` | `$0A` | `$0B0A` |
| **cookie-cut** AB + (NOT A)C | `($F0&$CC) ! ($0F&$AA)` = `$C0 ! $0A` | `$CA` | `$0FCA` (A,B,C,D) |
| line (normal) | AB + (NOT A)C | `$CA` | `$0BCA` (A,C,D; B is the texture constant) |
| line (XOR) | A B (NOT C) + (NOT A) C = `$40 ! $0A` | `$4A` | `$0B4A` |

Cookie-cut: A = mask (1 where the bob is opaque), B = bob image plane, C = background,
D = background. Where the mask is 1 the image wins, elsewhere the background is kept.

## Shifts and word masks

- **ASH** (BLTCON0 bits 15-12) and **BSH** (BLTCON1 bits 15-12) shift A and B right by 0-15
  bits, for free. Bits shifted out of one word enter the next word of the same row, and the
  last word of a row feeds the first word of the next row; only the very first word gets zeros.
- **BLTAFWM / BLTALWM** are ANDed with the first/last word of every row of source A **before
  shifting**; for a one-word-wide blit both apply. Use `$FFFF` when not needed.
- Load BLTADAT/BLTBDAT **after** setting the shift values: the data register is shifted at
  the moment it is written.
- To place a bob at an arbitrary x: shift = `x & 15`, destination word = `(x>>4)*2`. Store the
  bob and its mask with **at least 15 spare zero bits on the right of every row** (e.g. a
  16-pixel bob in 2-word rows): then shifted-out bits are always zero, the blit width covers
  every shift, and both word masks can stay `$FFFF`.

## Waiting for the blitter

DMACONR bit 14 (`DMAB_BLTDONE`, "blitter busy") is 1 while a blit runs. On old Agnus revisions
it may not be set yet right after BLTSIZE is written, and a CPU running from fast RAM can test
it too early -- so **read it twice**:

```asm
WaitBlit:
        btst    #DMAB_BLTDONE-8,dmaconr(a6)     ; dummy read (byte access to high byte)
.w      btst    #DMAB_BLTDONE-8,dmaconr(a6)
        bne.s   .w
        rts
```

- Wait **before** writing any blitter register (a previous blit may still run) and before
  using or freeing the destination.
- With the OS alive: `OwnBlitter()` (graphics LVO -456), then `WaitBlit()` (LVO -228) before
  touching the registers, `DisownBlitter()` (LVO -462) when done. OwnBlitter calls do not
  nest.
- DMACONR bit 13 (`DMAF_BLTNZERO`) is 1 when **every** destination bit of the finished blit
  was zero (even with D disabled) -- handy for pixel-exact collision (AND two masks, D off,
  minterm `$C0`). The NDK name reads "not zero"; the HRM defines the bit as "all zero".
- INTREQ bit 6 (BLIT, level 3) is set when a blit finishes.

## Example: copy a plane (A -> D)

```asm
        include "hardware/custom.i"
        include "hardware/dmabits.i"
        include "hardware/blit.i"

; a0 = source plane, a1 = destination plane, 320x256, a6 = $dff000
CopyPlane:
        bsr     WaitBlit
        move.w  #SRCA!DEST!$f0,bltcon0(a6)      ; $09F0
        move.w  #0,bltcon1(a6)                  ; ascending, area mode
        move.w  #$ffff,bltafwm(a6)
        move.w  #$ffff,bltalwm(a6)
        move.w  #0,bltamod(a6)                  ; 40 bytes/row - 2*20 words
        move.w  #0,bltdmod(a6)
        move.l  a0,bltapt(a6)
        move.l  a1,bltdpt(a6)
        move.w  #(256<<6)!20,bltsize(a6)        ; starts the blit
        rts
```

Time estimate (HRM): `t(us) = n * height * width_words / 7.16` (PAL `/ 7.09`), with
n = 4 clocks per word for A+D, +2 if B is used, +2 if both C and D are used (max 8; line mode
8). The copy above: 4*256*20/7.09 = about 2.9 ms.

## Example: cookie-cut a 16x16 bob

Bob image and mask are stored in 2-word (32-bit) rows; the right 16 bits of every row are 0.

```asm
; in: d0 = x (0..288), d1 = y (0..240), a0 = bob plane (32x16 bits), a1 = mask (32x16 bits)
;     a2 = destination plane (320 wide, 40 bytes/row), a6 = $dff000
BlitBob:
        bsr     WaitBlit
        moveq   #0,d2
        move.w  d1,d2
        mulu    #40,d2                  ; row offset
        moveq   #0,d3
        move.w  d0,d3
        lsr.w   #4,d3
        add.w   d3,d3                   ; (x>>4)*2
        add.l   d3,d2
        lea     (a2,d2.l),a3            ; destination word
        and.w   #$000f,d0               ; shift
        ror.w   #4,d0                   ; -> bits 15-12
        move.w  d0,d1
        or.w    #SRCA!SRCB!SRCC!DEST!$ca,d1
        move.w  d1,bltcon0(a6)          ; ASH + ABCD + cookie-cut
        move.w  d0,bltcon1(a6)          ; BSH = same shift, area mode
        move.w  #$ffff,bltafwm(a6)
        move.w  #$ffff,bltalwm(a6)
        move.w  #0,bltamod(a6)          ; mask rows are exactly 2 words
        move.w  #0,bltbmod(a6)
        move.w  #40-4,bltcmod(a6)       ; destination rows are 40 bytes
        move.w  #40-4,bltdmod(a6)
        move.l  a1,bltapt(a6)
        move.l  a0,bltbpt(a6)
        move.l  a3,bltcpt(a6)
        move.l  a3,bltdpt(a6)
        move.w  #(16<<6)!2,bltsize(a6)
        rts
```

For several bitplanes repeat with the next image plane and destination plane (same mask).
Restoring the background is the same blit with `$09F0` from a saved copy.

## Descending mode (overlapping copies)

If source and destination overlap and the destination is at a higher address (moving an image
down or right), copy backwards: set BLTCON1 bit 1 (`BLITREVERSE`). The pointers then start at
the **last word** of each area (not one past it), are decremented, the modulos are subtracted,
shifts go left, and BLTAFWM masks the last word of a row (the first one fetched). Use
ascending mode when the destination is at a lower address.

```asm
; scroll a 320x255 region of a plane down by one row (40 bytes/row), in place
        bsr     WaitBlit
        move.w  #SRCA!DEST!$f0,bltcon0(a6)
        move.w  #BLITREVERSE,bltcon1(a6)
        move.w  #$ffff,bltafwm(a6)
        move.w  #$ffff,bltalwm(a6)
        move.w  #0,bltamod(a6)
        move.w  #0,bltdmod(a6)
        lea     254*40+38(a0),a1        ; last word of row 254 (source)
        lea     255*40+38(a0),a2        ; last word of row 255 (destination)
        move.l  a1,bltapt(a6)
        move.l  a2,bltdpt(a6)
        move.w  #(255<<6)!20,bltsize(a6)
```

When shift direction and overlap direction conflict, blit to a temporary buffer first.

## Area fill

Fill happens after masking, shifting and the logic function, so it can be combined with any
blit, but only works in **descending** mode. It scans each row from right to left, toggling a
fill state at every 1 bit, starting with the FCI bit.

| BLTCON1 bit | Name | Effect |
|---|---|---|
| 3 | IFE (`FILL_OR`) | inclusive: fill between edges, keep the edge pixels |
| 4 | EFE (`FILL_XOR`) | exclusive: fill between edges, remove the left edge (1 pixel narrower, sharp vertices) |
| 2 | FCI (`FILL_CARRYIN`) | start state 1: fill outside the edges instead |

The outline must have **exactly one set bit per edge per row**: draw polygon edges in line
mode with ONEDOT set and the XOR minterm (`$4A`) so shared vertex pixels cancel correctly.

```asm
; fill a 320x256 plane in place (a0 = plane), a6 = $dff000
        bsr     WaitBlit
        move.w  #SRCA!DEST!$f0,bltcon0(a6)      ; copy A -> D ...
        move.w  #BLITREVERSE!FILL_XOR,bltcon1(a6) ; ... descending, exclusive fill
        move.w  #$ffff,bltafwm(a6)
        move.w  #$ffff,bltalwm(a6)
        move.w  #0,bltamod(a6)
        move.w  #0,bltdmod(a6)
        lea     256*40-2(a0),a1                 ; last word of the plane
        move.l  a1,bltapt(a6)
        move.l  a1,bltdpt(a6)
        move.w  #(256<<6)!20,bltsize(a6)
```

## Line mode

BLTCON1 bit 0 (`LINEMODE`) turns the blitter into a Bresenham line drawer. The line is
normalised into octant form: `dmaj = max(|dx|,|dy|)`, `dmin = min(|dx|,|dy|)`; the octant
bits in BLTCON1 tell the blitter the real direction.

| BLTCON1 bit | Name | Set when |
|---|---|---|
| 4 | SUD (`$10`) | x is the major axis (`|dx| >= |dy|`) |
| 3 | SUL (`$08`) | the minor-axis step is negative |
| 2 | AUL (`$04`) | the major-axis step is negative |
| 6 | SIGN (`SIGNFLAG` `$40`) | `4*dmin - 2*dmaj < 0` |
| 1 | ONEDOT (`$02`) | one pixel per row (outlines for area fill) |
| 5 | OVF (`OVFLAG` `$20`) | keep 0 |
| 15-12 | BSH | texture start bit (0 for a solid line) |

NDK octant constants (already include SUD/SUL/AUL):

| dx | dy | major | constant | value |
|---|---|---|---|---|
| >= 0 | >= 0 | x | `OCTANT1` | 16 |
| >= 0 | >= 0 | y | `OCTANT2` | 0 |
| < 0 | >= 0 | y | `OCTANT3` | 8 |
| < 0 | >= 0 | x | `OCTANT4` | 20 |
| < 0 | < 0 | x | `OCTANT5` | 28 |
| < 0 | < 0 | y | `OCTANT6` | 12 |
| >= 0 | < 0 | y | `OCTANT7` | 4 |
| >= 0 | < 0 | x | `OCTANT8` | 24 |

Register set-up:

| Register | Value |
|---|---|
| BLTCON0 | `(x1&15)<<12 ! $0BCA` (or `$0B4A` for XOR lines); SRCB must be off |
| BLTCON1 | octant ! `LINEMODE` ! (`SIGNFLAG` if `4*dmin-2*dmaj < 0`) ! (`ONEDOT` for fill) |
| BLTADAT | `$8000` (the moving pixel; write after BLTCON0) |
| BLTBDAT | texture, `$FFFF` = solid (write after BLTCON1) |
| BLTAFWM, BLTALWM | `$FFFF` |
| BLTAPT (low word) | `4*dmin - 2*dmaj` (sign-extended long write) |
| BLTAMOD | `4*dmin - 4*dmaj` |
| BLTBMOD | `4*dmin` |
| BLTCPT, BLTDPT | word containing (x1, y1) |
| BLTCMOD, BLTDMOD | bytes per row of the plane |
| BLTSIZE | `(dmaj+1)<<6 ! 2` (width is always 2) |

```asm
; Draw a solid line. in: d0=x1 d1=y1 d2=x2 d3=y2, d4.w = bytes per row, a0 = plane
; a6 = $dff000. Trashes d0-d6, a0-a1.
BlitLine:
        moveq   #0,d5                   ; bit1 = dx<0, bit0 = dy<0
        sub.w   d0,d2                   ; dx
        bpl.s   .dxok
        neg.w   d2
        bset    #1,d5
.dxok   sub.w   d1,d3                   ; dy
        bpl.s   .dyok
        neg.w   d3
        bset    #0,d5
.dyok   cmp.w   d3,d2
        bhs.s   .xmaj                   ; |dx| >= |dy|
        exg     d2,d3                   ; d2 = dmaj, d3 = dmin
        lea     .ytab(pc),a1
        bra.s   .oct
.xmaj   lea     .xtab(pc),a1
.oct    move.b  (a1,d5.w),d5            ; octant code
        ; destination word
        moveq   #0,d6
        move.w  d1,d6
        mulu    d4,d6
        add.l   d6,a0
        moveq   #0,d6
        move.w  d0,d6
        lsr.w   #3,d6
        bclr    #0,d6
        add.l   d6,a0
        ; BLTCON0
        and.w   #$000f,d0
        ror.w   #4,d0
        or.w    #$0bca,d0
        ; slopes
        add.w   d3,d3
        add.w   d3,d3                   ; d3 = 4*dmin
        add.w   d2,d2                   ; d2 = 2*dmaj
        move.w  d3,d1
        sub.w   d2,d1                   ; d1 = 4*dmin - 2*dmaj
        bpl.s   .nosign
        or.w    #SIGNFLAG,d5
.nosign or.w    #LINEMODE,d5
        bsr     WaitBlit
        move.w  d0,bltcon0(a6)
        move.w  d5,bltcon1(a6)
        move.w  #$8000,bltadat(a6)
        move.w  #$ffff,bltbdat(a6)
        move.w  #$ffff,bltafwm(a6)
        move.w  #$ffff,bltalwm(a6)
        move.w  d3,bltbmod(a6)
        move.w  d4,bltcmod(a6)
        move.w  d4,bltdmod(a6)
        ext.l   d1
        move.l  d1,bltapt(a6)
        sub.w   d2,d1                   ; 4*dmin - 4*dmaj
        move.w  d1,bltamod(a6)
        move.l  a0,bltcpt(a6)
        move.l  a0,bltdpt(a6)
        lsl.w   #5,d2                   ; (2*dmaj)<<5 = dmaj<<6
        add.w   #(1<<6)!2,d2            ; height dmaj+1, width 2
        move.w  d2,bltsize(a6)
        rts
.xtab   dc.b    OCTANT1,OCTANT8,OCTANT4,OCTANT5 ; index = dx<0 *2 + dy<0
.ytab   dc.b    OCTANT2,OCTANT7,OCTANT3,OCTANT6
        even
```

- Maximum length 1024 pixels (height field). Clip before drawing: the blitter does not.
- For fill outlines set `ONEDOT` and use `$0B4A`; the vertex handling details (skipping or
  inverting the first pixel of each edge) are a common source of stray fill lines
  (unverified recipe -- test with your polygon code).

## DMA and the display

The blitter only gets memory cycles that bitplane/sprite/audio/disk DMA and the copper leave.
A large blit started late in vertical blank keeps running into the visible display and slows
down there. Blitter "nasty" (DMACON bit 10, `DMAF_BLITHOG`) lets it keep every free chip
cycle; with it off, the CPU gets one cycle after being starved for three. See
[interrupts-and-dma.md](interrupts-and-dma.md#dma-bus-arbitration). The amigascope-workflow
skill's `dma_profile.py blits` shows each blit's raster span and flags blits that overrun
into the display.

## Common mistakes

- Blitting fast-RAM data (or a mask in a plain `data` section): chip RAM gets corrupted.
- Writing BLTSIZE before the other registers, or writing registers while the previous blit
  still runs (missing the double DMACONR test).
- Width in pixels or bytes instead of words; height and width swapped in BLTSIZE.
- Modulo computed in words, or forgetting that each channel has its own modulo.
- Loading BLTADAT/BLTBDAT before BLTCON0/BLTCON1 (the constant gets the old shift).
- Forgetting BLTAFWM/BLTALWM (`$FFFF`) when they are not wanted: leftover masks from the OS
  cut columns off.
- Area fill in ascending mode, or outlines with more than one pixel per row.
- `clr.w bltamod(a6)`: use `move.w #0` (68000 CLR reads first).
- Freeing a temporary buffer right after starting a blit into or out of it.
- Line mode with SRCB enabled, or BLTSIZE width other than 2.
