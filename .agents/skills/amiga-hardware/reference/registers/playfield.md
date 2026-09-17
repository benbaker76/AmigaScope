# Custom chips: playfield (bitplane) registers

All playfield registers are write-only: keep shadow copies of anything you need to read
back. Positions are in lores, non-interlaced beam coordinates whatever the display mode.
Standard 320x200 NTSC / 320x256 PAL lores setup: BPLCON0 `$n200`, BPLCON1 `0`,
BPLCON2 `$0024`, DDFSTRT `$0038`, DDFSTOP `$00D0`, DIWSTRT `$2C81`, DIWSTOP `$F4C1`
(NTSC) or `$2CC1` (PAL), modulos `0`.

## BPLCON0
`$DFF100` · write · Agnus + Denise · OCS (ECS bits 7, 6, 0) · all bits written at once

Display mode: bitplane count, hires, HAM, dual playfield, interlace and genlock bits.

| Bit | Name | Meaning |
|---|---|---|
| 15 | HIRES | 1 = hires (70 ns pixels); 0 with SHRES |
| 14-12 | BPU2-BPU0 | bitplanes used, 0-6 (7 is not used on OCS/ECS) |
| 11 | HOMOD | hold-and-modify |
| 10 | DBLPF | dual playfield: odd planes = playfield 1, even planes = playfield 2 |
| 9 | COLOR | composite colour burst enable: always set it |
| 8 | GAUD | genlock audio enable |
| 7 | UHRES | ECS: enable the UHRES pointers (also needs DMACON bits); 0 on OCS |
| 6 | SHRES | ECS: superhires, 35 ns pixels, at most 2 planes; 0 on OCS |
| 5-4 | -- | write 0 on OCS/ECS |
| 3 | LPEN | light-pen latch enable (beam registers then read the pen) |
| 2 | LACE | interlace |
| 1 | ERSY | external resync: HSYNC/VSYNC pins become inputs (genlock) |
| 0 | ENBPLCN3 | ECS: 1 = honour BPLCON3 border/genlock bits |

Extra half-brite: BPU = 6 with HOMOD = 0 and DBLPF = 0; plane 6 halves the brightness of
the colour chosen by planes 1-5. AGA adds BYPASS (bit 5) and BPU3 (bit 4, up to 8 planes)
and calls bit 0 ECSENA: see the amiga-aga skill.

NDK: `bplcon0` (custom.i); no bit constants in hardware/*.i; C `custom->bplcon0`,
`USE_BPLCON3` (bit 0, `hardware/custom.h` under `#ifdef ECS_SPECIFIC`).

### Example
```asm
        dc.w    bplcon0,$1200                   ; 1 plane lores, colour on
        dc.w    bplcon0,$5200                   ; 5 planes lores (32 colours)
        dc.w    bplcon0,$6a00                   ; 6 planes HAM
        dc.w    bplcon0,$9204                   ; 1 plane hires interlaced
```

### Gotchas
- Write-only and not set/clear: every write replaces all bits, so compose the full value.
- Set COLOR (`$0200`) in every write; without it composite output is monochrome and some
  video/genlock hardware shows a corrupt picture.
- Changing BPLCON0 mid-frame (from the Copper) is legal and is how split screens work.
- BPU is the number of planes, not a mask: `$4000` = 4 planes.
- LACE needs separate long/short-field handling (VPOSR LOF) and twice the lines of data.

**See also:** BPLCON1, BPLCON2, BPLCON3, [DMACON](dma-beam.md#dmacon), [VPOSR](dma-beam.md#vposr)

## BPLCON1
`$DFF102` · write · Denise · OCS

Horizontal scroll delay (0-15 lores pixels) for playfield 1 and playfield 2.

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | -- | write 0 on OCS/ECS |
| 7-4 | PF2H3-PF2H0 | delay of even planes (playfield 2) |
| 3-0 | PF1H3-PF1H0 | delay of odd planes (playfield 1) |

One step is one lores pixel (140 ns), i.e. two hires pixels. AGA adds bits 15-8 (finer and
wider scroll codes): see the amiga-aga skill.

NDK: `bplcon1` (custom.i); C `custom->bplcon1`.

### Example
```asm
; single playfield: d0 = pixel offset 0-15
        move.w  d0,d1
        lsl.w   #4,d1
        or.w    d0,d1                           ; same delay in both nibbles
        move.w  d1,BplCon1Value+2               ; patch the Copper list MOVE
```

### Gotchas
- With one playfield, set both nibbles to the same value (HRM warning).
- A larger delay moves the image right. Smooth scrolling needs one extra fetched word:
  DDFSTRT `$0030` (lores) and a modulo two bytes smaller.
- DDFSTRT `$0030` costs sprite 7.

**See also:** DDFSTRT, BPL1MOD, BPLCON0

## BPLCON2
`$DFF104` · write · Denise · OCS (ECS genlock bits 14-9)

Playfield priority against sprites and each other, plus ECS genlock keying.

| Bit | Name | Meaning |
|---|---|---|
| 15 | -- | write 0 |
| 14-12 | ZDBPSEL2-0 | ECS: bitplane used as genlock key (with ZDBPEN) |
| 11 | ZDBPEN | ECS: use the selected bitplane as genlock key |
| 10 | ZDCTEN | ECS: colour-register genlock keying (ColorKey) |
| 9 | KILLEHB | ECS: disable extra half-brite |
| 8-7 | -- | write 0 on OCS/ECS |
| 6 | PF2PRI | 1 = playfield 2 in front of playfield 1 |
| 5-3 | PF2P2-PF2P0 | playfield 2 position among the sprite pairs (0-4) |
| 2-0 | PF1P2-PF1P0 | playfield 1 position among the sprite pairs (0-4) |

| Code | Front to back |
|---|---|
| 0 | PF, SP01, SP23, SP45, SP67 |
| 1 | SP01, PF, SP23, SP45, SP67 |
| 2 | SP01, SP23, PF, SP45, SP67 |
| 3 | SP01, SP23, SP45, PF, SP67 |
| 4 | SP01, SP23, SP45, SP67, PF |

AGA adds RDRAM (bit 8) and SOGEN (bit 7): see the amiga-aga skill.

NDK: `bplcon2` (custom.i); C `custom->bplcon2`, `BPLCON2_ZDCTEN`, `BPLCON2_ZDBPEN`,
`BPLCON2_ZDBPSEL0`-`BPLCON2_ZDBPSEL2` (`hardware/custom.h`, `#ifdef ECS_SPECIFIC`).

### Example
```asm
        dc.w    bplcon2,$0024                   ; sprites in front of both playfields
        dc.w    bplcon2,$0000                   ; both playfields in front of all sprites
```

### Gotchas
- The HRM warns that in single-playfield mode the PF2P bits (5-3) set the priority:
  write the same code into both fields to be safe.
- Only codes 0-4 are documented.
- Sprite-to-sprite priority is fixed: the lower-numbered sprite is always in front.

**See also:** BPLCON0, [CLXCON](sprites.md#clxcon), [SPRxPOS](sprites.md#sprxpos)

## BPLCON3
`$DFF106` · write · Denise · ECS · ignored unless BPLCON0 bit 0 is set

ECS enhanced display features: border blanking and border genlock transparency.

| Bit | Name | Meaning |
|---|---|---|
| 15-6 | -- | write 0 on ECS |
| 5 | BRDRBLNK | border area blanked (black) instead of COLOR00 |
| 4 | BRDNTRAN | border area opaque to genlock (not transparent) |
| 3-0 | -- | write 0 on ECS |

AGA adds BANK2-0, PF2OF2-0, LOCT, SPRES1-0, ZDCLKEN, BRDSPRT and EXTBLKEN (bits 15-6 and
2-0): see the amiga-aga skill.

NDK: `bplcon3` (custom.i); C `BPLCON3_BRDNBLNK` (bit 5), `BPLCON3_BRDNTRAN` (bit 4),
plus `BPLCON3_ZDCLKEN` (2), `BPLCON3_EXTBLKZD` (1), `BPLCON3_EXTBLNKEN` (0)
(`hardware/custom.h`, `#ifdef ECS_SPECIFIC`; the HRM documents only bits 5-4 for ECS).

### Gotchas
- Does not exist on OCS Denise.
- Code meant to also run on AGA should write BPLCON3 explicitly: its AGA reset default is
  `$0C00` (PF2OF = 011), and stale OS values (colour bank, sprite resolution) otherwise
  leak into your display.

**See also:** BPLCON0, BPLCON2, [DIWHIGH](ecs.md#diwhigh)

## BPL1MOD
`$DFF108` · write · Agnus · OCS

Signed modulo added to the odd bitplane pointers (1, 3, 5) at the end of each line.

Value = bytes per line in memory - bytes fetched per line. Bytes fetched: lores
`((DDFSTOP - DDFSTRT) / 8 + 1) * 2`, hires `((DDFSTOP - DDFSTRT) / 4 + 1) * 2`.

NDK: `bpl1mod` (custom.i); C `custom->bpl1mod`.

### Example
```asm
        dc.w    bpl1mod,0                       ; 320-wide lores bitmap, no scroll
        dc.w    bpl2mod,0
        ; 320x400 bitmap shown interlaced: skip one line per field
        dc.w    bpl1mod,40
        dc.w    bpl2mod,40
```

### Gotchas
- Must be even. It is 15 bits plus sign, so negative modulos work.
- Separate odd/even modulos let the two playfields of a dual-playfield display have
  different widths.
- AGA scan-doubling (FMODE BSCAN2) turns BPL2MOD into an alternate-line modulo: see the
  amiga-aga skill.

**See also:** BPL2MOD, DDFSTRT, DDFSTOP, BPLxPTH, BPLxPTL

## BPL2MOD
`$DFF10A` · write · Agnus · OCS

Signed modulo added to the even bitplane pointers (2, 4, 6) at the end of each line.

Same rules as BPL1MOD. For a single playfield write the same value to both.

NDK: `bpl2mod` (custom.i); C `custom->bpl2mod`.

**See also:** BPL1MOD, BPLxPTH, BPLxPTL

## BPLxPTH, BPLxPTL
`$DFF0E0`-`$DFF0F6` · write · Agnus · OCS (high word: 3 address bits OCS, 5 ECS) · pointer pairs, x = 1-6

Chip-RAM address of bitplane x; it advances during display, so reload it every frame.

| x | BPLxPTH | BPLxPTL |
|---|---|---|
| 1 | `$DFF0E0` | `$DFF0E2` |
| 2 | `$DFF0E4` | `$DFF0E6` |
| 3 | `$DFF0E8` | `$DFF0EA` |
| 4 | `$DFF0EC` | `$DFF0EE` |
| 5 | `$DFF0F0` | `$DFF0F2` |
| 6 | `$DFF0F4` | `$DFF0F6` |

BPL7PTH/L and BPL8PTH/L (`$DFF0F8`-`$DFF0FE`) are AGA only: see the amiga-aga skill.

NDK: `bplpt` (custom.i, base of 8 longwords: `bplpt+(x-1)*4`); C `custom->bplpt[x-1]`.

### Example
```asm
CopBpl: dc.w    bplpt+0,0                       ; BPL1PTH
        dc.w    bplpt+2,0                       ; BPL1PTL
        ; at setup (Plane1 in chip RAM):
        move.l  #Plane1,d0
        move.w  d0,CopBpl+6                     ; low word
        swap    d0
        move.w  d0,CopBpl+2                     ; high word
```

### Gotchas
- Reload the pointers at the top of every frame (Copper list, or CPU during vertical
  blank); otherwise the next frame continues from where the last one stopped.
- Chip RAM only, even address.
- Writing a pointer from the CPU in mid-display glitches the picture: use the Copper list
  or the vertical blank.

**See also:** BPL1MOD, BPLCON0, [COP1LCH, COP1LCL](copper.md#cop1lch-cop1lcl)

## BPLxDAT
`$DFF110`-`$DFF11A` · write · Denise · OCS · DMA-only in practice, x = 1-6

Bitplane serialiser input words, filled by bitplane DMA and not needed by software.

Addresses: BPL1DAT `$DFF110`, BPL2DAT `$112`, BPL3DAT `$114`, BPL4DAT `$116`, BPL5DAT
`$118`, BPL6DAT `$11A`. The parallel-to-serial conversion is triggered by the write to
BPL1DAT; the MSB is the leftmost pixel. BPL7DAT/BPL8DAT (`$11C`/`$11E`) are AGA.

NDK: `bpldat` (custom.i, `bpldat+(x-1)*2`); C `custom->bpldat[x-1]`.

**See also:** BPLxPTH, BPLxPTL

## DIWSTRT
`$DFF08E` · write · Agnus + Denise · OCS (ECS: see DIWHIGH)

Upper-left corner of the display window (VSTART, HSTART).

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | V7-V0 | VSTART (V8 = 0 implied) |
| 7-0 | H7-H0 | HSTART (H8 = 0 implied) |

Standard value `$2C81` (NTSC and PAL).

NDK: `diwstrt` (custom.i); C `custom->diwstrt`.

### Example
```asm
        dc.w    diwstrt,$2c81
        dc.w    diwstop,$2cc1                   ; PAL 320x256
```

### Gotchas
- Coordinates are always lores non-interlaced, even for hires or interlaced screens.
- On OCS the start is limited to the top part (V8 = 0) and left 3/4 (H8 = 0) of the
  beam range; ECS lifts this with DIWHIGH.
- The window only clips; what is fetched is set by DDFSTRT/DDFSTOP. Matching fetch start:
  lores `HSTART/2 - 8.5` (`$81` gives `$38`), hires `HSTART/2 - 4.5` (`$3C`).

**See also:** DIWSTOP, DDFSTRT, [DIWHIGH](ecs.md#diwhigh)

## DIWSTOP
`$DFF090` · write · Agnus + Denise · OCS (ECS: see DIWHIGH)

Lower-right corner of the display window (VSTOP, HSTOP), exclusive.

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | V7-V0 | VSTOP; V8 = NOT V7 implied |
| 7-0 | H7-H0 | HSTOP - `$100` (H8 = 1 implied) |

Standard values: NTSC `$F4C1` (200 lines), PAL `$2CC1` (256 lines, VSTOP `$12C`).

NDK: `diwstop` (custom.i); C `custom->diwstop`.

### Gotchas
- VSTOP bytes `$80`-`$FF` mean lines `$80`-`$FF`; bytes `$00`-`$7F` mean lines
  `$100`-`$17F` (V8 is the complement of V7).
- HSTOP is written as `actual - $100` (`$1C1` is written `$C1`).
- ECS: writing DIWHIGH after DIWSTRT/DIWSTOP gives explicit upper bits instead.

**See also:** DIWSTRT, [DIWHIGH](ecs.md#diwhigh)

## DDFSTRT
`$DFF092` · write · Agnus · OCS

Horizontal beam position where bitplane data fetch starts (left edge of fetched data).

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | -- | write 0 |
| 7-2 | H8-H3 | start position; H3 (bit 2) is honoured in hires only |
| 1-0 | -- | write 0 |

| | Lores | Hires |
|---|---|---|
| DDFSTRT standard | `$0038` | `$003C` |
| DDFSTOP standard | `$00D0` | `$00D4` |
| DDFSTRT hardware limit | `$0018` | `$0018` |
| DDFSTOP hardware limit | `$00D8` | `$00D8` |
| max words fetched | 25 | 49 |

Relation to width: lores `DDFSTRT = DDFSTOP - 8 * (words - 1)`, hires
`DDFSTRT = DDFSTOP - 4 * (words - 1)`.

NDK: `ddfstrt` (custom.i); C `custom->ddfstrt`.

### Gotchas
- Values below `$38` steal sprite DMA slots: `$30` (horizontal scrolling) disables sprite 7,
  wider overscan loses more sprites.
- One DDFSTRT/DDFSTOP pair serves both playfields.
- Change the modulo whenever you change the number of fetched words.

**See also:** DDFSTOP, DIWSTRT, BPL1MOD, BPLCON1

## DDFSTOP
`$DFF094` · write · Agnus · OCS

Horizontal beam position of the last bitplane data fetch (right edge).

Bit layout and value table as DDFSTRT: lores `$00D0`, hires `$00D4`, limit `$00D8`.

NDK: `ddfstop` (custom.i); C `custom->ddfstop`.

**See also:** DDFSTRT, DIWSTOP

## COLORxx
`$DFF180`-`$DFF1BE` · write · Denise · OCS · xx = 00-31

12-bit RGB palette entry `$0RGB`; COLOR00 is the background and border colour.

| Bit | Meaning |
|---|---|
| 15-12 | unused, write 0 |
| 11-8 | red |
| 7-4 | green |
| 3-0 | blue |

Address = `$DFF180 + xx*2`. Uses: bitplane value n selects COLORn; dual playfield uses
0-7 for playfield 1 and 8-15 for playfield 2; sprites 0/1, 2/3, 4/5, 6/7 use 17-19, 21-23,
25-27, 29-31 (attached pairs: 17-31); EHB value 32-63 = COLOR(n-32) at half brightness;
HAM6 planes 6-5: 00 = COLORn from planes 4-1, 01 = modify blue, 10 = modify red,
11 = modify green.

AGA adds 24-bit colour via BPLCON3 LOCT and 256 entries via BANK: see the amiga-aga skill.

NDK: `color` (custom.i, `color+xx*2`); C `custom->color[xx]`.

### Example
```asm
        dc.w    color+0,$0000                   ; COLOR00 black
        dc.w    color+2,$0fff                   ; COLOR01 white
        dc.w    color+34,$0f80                  ; COLOR17 orange (sprite 0/1 colour 1)
```

### Gotchas
- Four bits per gun on OCS/ECS: `$0F80`, not `$FF8800`.
- Write-only: keep your own palette table for fades.
- Colour registers 16-31 are shared between 5-plane playfield pixels and sprites.
- With a genlock, COLOR00 areas show the external video.
- ECS superhires reinterprets the registers (2 bits per gun, sprite colours in 16-31).

**See also:** BPLCON0, [SPRxDATA](sprites.md#sprxdata), [COPINS](copper.md#copins)
