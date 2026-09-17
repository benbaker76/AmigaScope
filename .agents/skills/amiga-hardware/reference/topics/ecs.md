# ECS: Enhanced Chip Set

What ECS (8372 Agnus, 8373 Denise) adds over OCS, how to detect it, BEAMCON0 and DIWHIGH.

ECS is standard in the A3000 and was fitted to later A500/A2000 (Fat Agnus 8372/8372A,
Hires Denise 8373). Everything in the OCS guides still applies. AGA (Alice/Lisa: 24-bit
palette, 8 planes, FMODE) is covered by the amiga-aga skill.

Registers: [BEAMCON0](../registers/ecs.md#beamcon0), [DIWHIGH](../registers/ecs.md#diwhigh),
[DENISEID](../registers/ecs.md#deniseid), [VPOSR](../registers/dma-beam.md#vposr),
[BPLCON0](../registers/playfield.md#bplcon0), [BPLCON2](../registers/playfield.md#bplcon2),
[BPLCON3](../registers/playfield.md#bplcon3), [BLTSIZV](../registers/blitter.md#bltsizv),
[BLTSIZH](../registers/blitter.md#bltsizh), [BLTCON0L](../registers/blitter.md#bltcon0l),
[COPCON](../registers/copper.md#copcon).

## What ECS adds

| Feature | Registers / bits |
|---|---|
| Up to 2 MB chip RAM (A3000; 1 MB on A500/A2000) | pointer high words widened from 3 to 5 bits: DSKPTH, BLTxPTH, COP1LCH, COP2LCH, AUDxLCH |
| Big blits, up to 32768 x 32768 | BLTSIZV (`$05C`), BLTSIZH (`$05E`) |
| Minterm-only write | BLTCON0L (`$05B` in `custom.i`, byte access) |
| Blit without writing D | BLTCON1 bit 7 DOFF |
| SuperHires 35 ns pixels (1280 across, max 2 planes) | BPLCON0 bit 6 SHRES |
| 70 ns sprite positioning in SuperHires | SPRxCTL bits 4-3 |
| Programmable scan rates/sync/blanking | HTOTAL, HSSTRT, HSSTOP, HBSTRT, HBSTOP, VTOTAL, VSSTRT, VSSTOP, VBSTRT, VBSTOP, HCENTER, BEAMCON0 |
| PAL/NTSC switchable on one Agnus | BEAMCON0 bit 5 |
| Wider display window ranges | DIWHIGH (`$1E4`) |
| Genlock: colour key, bitplane key, border blank/opaque, EHB kill | BPLCON2 bits 14-9, BPLCON3 bits 5-4, BPLCON0 bit 0 |
| Copper danger range extended | COPCON bit 1 |
| Chip identification | VPOSR bits 14-8, DENISEID (`$07C`) |

## Detecting ECS

With graphics.library V36+, use `gb_ChipRevBits0` in GfxBase (`graphics/gfxbase.i`):

| Bit | NDK | Meaning |
|---|---|---|
| 0 | `GFXB_HR_AGNUS` (= `GFXB_BIG_BLITS`) | ECS Agnus present |
| 1 | `GFXB_HR_DENISE` | ECS Denise present |
| 2 | `GFXB_AA_ALICE` | AGA Alice |
| 3 | `GFXB_AA_LISA` | AGA Lisa |

From hardware (e.g. in a trackloader):

**Agnus ID** -- VPOSR bits 14-8:

| ID | Chip |
|---|---|
| `$00` | 8367 / 8371 (OCS, PAL) |
| `$10` | 8361 / 8370 (OCS, NTSC) |
| `$20` / `$30` | 8372 ECS Agnus up to rev 4, PAL / NTSC |
| `$22` / `$31` | 8372 rev 5, PAL / NTSC |
| `$22`, `$23` / `$32`, `$33` | 8374 Alice (AGA), PAL / NTSC |

`$22` is ambiguous (8372 rev 5 or Alice) -- combine with DENISEID.

**DENISEID** (`$DFF07C`, read): OCS Denise (8362) has no such register, so the bus floats;
ECS Denise returns `$FC` in the low byte, Lisa `$F8` (upper nibble of the low byte counts
revisions down from `$F`). Read it several times and require a stable value:

```asm
; out: d0 = 0 OCS Denise, 1 ECS Denise, 2 AGA Lisa. a6 = $dff000
DeniseType:
        move.w  deniseid(a6),d1
        and.w   #$00ff,d1
        moveq   #31-1,d2
.again  move.w  deniseid(a6),d3
        and.w   #$00ff,d3
        cmp.b   d1,d3
        bne.s   .ocs                    ; floating bus: no register
        dbf     d2,.again
        or.b    #$f0,d1                 ; ignore the revision nibble
        moveq   #1,d0
        cmp.b   #$fc,d1
        beq.s   .done
        moveq   #2,d0
        cmp.b   #$f8,d1
        beq.s   .done
.ocs    moveq   #0,d0
.done   rts
```

## BEAMCON0 and PAL/NTSC switching

BEAMCON0 (`$1DC`, write-only, ECS Agnus and later). Bit names from `hardware/custom.h`
(C only, `ECS_SPECIFIC`; define your own equates in assembler):

| Bit | NDK (C) | HRM name | Effect |
|---|---|---|---|
| 14 | -- | HARDDIS | disable hardwired blank/window limits |
| 13 | -- | LPENDIS | ignore the light-pen latch on beam counter reads |
| 12 | `VARVBLANK` | VARVBEN | use VBSTRT/VBSTOP |
| 11 | `LOLDIS` | LOLDIS | no long/short line toggle |
| 10 | `CSCBLANKEN` | CSCBEN | composite sync/blank redirection |
| 9 | `VARVSYNC` | VARVSYEN | use VSSTRT/VSSTOP |
| 8 | `VARHSYNC` | VARHSYEN | use HSSTRT/HSSTOP |
| 7 | `VARBEAM` | VARBEAMEN | use HTOTAL/VTOTAL |
| 6 | `DISPLAYDUAL` | DUAL | UHRES dual display |
| 5 | `DISPLAYPAL` | PAL | PAL decodes (312/313 lines) |
| 4 | `VARCSYNC` | VARCSYEN | variable composite sync |
| 3 | `CSBLANK` | BLANKEN | composite blank to CSY* pin |
| 2 / 1 / 0 | `CSYNCTRUE` / `VSYNCTRUE` / `HSYNCTRUE` | | sync polarity |

The NDK standard values are `STANDARD_PAL_BEAMCON = DISPLAYPAL` (`$0020`) and
`STANDARD_NTSC_BEAMCON = $0000` (`graphics/monitor.h`).

```asm
        move.w  #$0020,beamcon0(a6)     ; PAL: 312 lines, 50 Hz
        ; move.w #$0000,beamcon0(a6)    ; NTSC: 262 lines, 60 Hz
```

- Only on an ECS/AGA Agnus (check the Agnus ID first); OCS has no BEAMCON0.
- The HRM warns against writing BEAMCON0 at all: wrong sync settings can damage a multisync
  monitor. Only ever write the two standard values above, and only from a standard PAL/NTSC
  display.
- The crystal does not change: audio/serial clock constants and CIA E clock stay those of the
  machine's crystal. GfxBase `gb_DisplayFlags` bit `REALLY_PALn` (4) reports the crystal, bit
  `PALn` (2) the current mode.
- After switching, your copper list, DIWSTOP and line counts must match the new standard.
  On exit restore the OS setting (`gb_DisplayFlags` PAL bit) before `LoadView(oldView)`
  (whether LoadView alone reprograms BEAMCON0 is unverified).

## DIWHIGH

Without DIWHIGH, DIWSTRT/DIWSTOP keep their OCS implicit bits (start H8 = 0, V8 = 0; stop
H8 = 1, V8 = NOT V7). Writing DIWHIGH **after** DIWSTRT and DIWSTOP supplies the upper bits
explicitly, so the window can start and stop anywhere:

| Bit | Field |
|---|---|
| 15-14, 12-11 | 0 (AGA uses 12-11 for fine stop bits) |
| 13 | stop H8 |
| 10-8 | stop V10-V8 |
| 7-6, 4-3 | 0 (AGA uses 4-3 for fine start bits) |
| 5 | start H8 |
| 2-0 | start V10-V8 |

Example, standard PAL window with explicit bits (VSTOP `$12C`, HSTOP `$1C1`):

```asm
        dc.w    diwstrt,$2c81
        dc.w    diwstop,$2cc1
        dc.w    diwhigh,$2100           ; stop H8=1 (bit 13), stop V8=1 (bit 8)
```

## Big blits

Write BLTSIZV (15-bit height) first, then BLTSIZH (11-bit width in words), which **starts**
the blit. BLTSIZE still works (up to 1024 x 1024). Check `GFXB_BIG_BLITS` first.

```asm
        move.w  #2000,bltsizv(a6)       ; 2000 rows
        move.w  #100,bltsizh(a6)        ; 100 words wide -> starts
```

## SuperHires and genlock (summary)

- SHRES (BPLCON0 bit 6) with HIRES = 0: 35 ns pixels, 1-2 planes, no HAM. SuperHires colours
  are encoded across the colour registers (2 bits per gun); graphics.library handles the
  encoding. Sprites can be positioned in 70 ns steps via SPRxCTL bits 4-3.
- BPLCON2: bit 9 KILLEHB, bit 10 ZDCTEN (colour-keyed genlock), bit 11 ZDBPEN with bits 14-12
  ZDBPSEL (bitplane-keyed genlock).
- BPLCON3: bit 5 border blank, bit 4 border opaque (NDK C names `BPLCON3_BRDNBLNK`,
  `BPLCON3_BRDNTRAN`); they need BPLCON0 bit 0 set (`USE_BPLCON3` in `custom.h`).
- Genlock features work with PAL/NTSC timings only, not 31 kHz modes.

## Copper danger on ECS

The HRM describes ECS as extending COPCON: with CDANG set the copper may write every
register; without it the `$040`-`$07E` range is already reachable. The OCS rules (only
`$080`+ without CDANG, `$040`+ with it) are safe on every chipset -- see
[copper.md](copper.md#register-write-restrictions-copper-danger).

## Common mistakes

- Writing BEAMCON0, BLTSIZV/BLTSIZH or DIWHIGH on an OCS machine (undefined addresses).
- Writing DIWHIGH before DIWSTRT/DIWSTOP, or forgetting it and expecting explicit positions.
- Big blit started with BLTSIZH before BLTSIZV.
- Treating VPOSR ID `$22` as proof of ECS (could be Alice).
- Trusting a single DENISEID read on OCS (floating bus can look like `$FC`).
- Assuming a PAL-switched NTSC machine uses PAL audio/timer constants.
- Relying on ECS copper-danger relaxations in code meant to run on OCS.
