# ECS registers: programmable beam, UHRES, DIWHIGH, DENISEID

The Enhanced Chip Set is the 8372 "hires" Agnus plus the 8373 Denise (standard in the
A3000, installable in the A500 and A2000); AGA's Alice and Lisa keep every register
here. These registers do not exist on OCS chips. Since V36, graphics.library programs
them for its display modes; the HRM warns that wrong sync and blank values
(especially BEAMCON0) can damage multisync monitors. All are write-only except HHPOSR and
DENISEID.

Horizontal positions are in colour clocks (280 ns) with the HTOTAL bit layout
(bits 7-0 = H8-H1); vertical positions are line numbers.

## BEAMCON0
`$DFF1DC` · write · Agnus · ECS · monitor danger

Beam counter control: variable sync/blank, PAL/NTSC decodes and sync polarities.

| Bit | Name | Meaning | C (`ECS_SPECIFIC`) |
|---|---|---|---|
| 15 | -- | write 0 | |
| 14 | HARDDIS | disable the hardwired blank / display-window limits | |
| 13 | LPENDIS | 1 = beam reads ignore the light-pen latch | |
| 12 | VARVBEN | use VBSTRT/VBSTOP for vertical blank; removes the hard vertical window stop | `VARVBLANK` |
| 11 | LOLDIS | disable the long line / short line toggle | `LOLDIS` |
| 10 | CSCBEN | variable composite sync on the HSY pin, composite blank on VSY | `CSCBLANKEN` |
| 9 | VARVSYEN | VSY pin from VSSTRT/VSSTOP | `VARVSYNC` |
| 8 | VARHSYEN | HSY pin from HSSTRT/HSSTOP | `VARHSYNC` |
| 7 | VARBEAMEN | use HTOTAL/VTOTAL; removes the hard display stops | `VARBEAM` |
| 6 | DUAL | UHRES timing from the second horizontal counter (HHPOS) | `DISPLAYDUAL` |
| 5 | PAL | PAL decodes in normal mode (in variable mode: short lines only) | `DISPLAYPAL` |
| 4 | VARCSYEN | variable composite sync on the CSY pin | `VARCSYNC` |
| 3 | BLANKEN | composite blank out to the CSY pin (unused on AGA) | `CSBLANK` |
| 2 | CSYTRUE | CSY pin active high | `CSYNCTRUE` |
| 1 | VSYTRUE | VSY pin active high | `VSYNCTRUE` |
| 0 | HSYTRUE | HSY pin active high | `HSYNCTRUE` |

NDK: `beamcon0` (custom.i); flags only in C `hardware/custom.h` under
`#ifdef ECS_SPECIFIC` (no names for bits 14-13). AGA uses the same register: see the
amiga-aga skill.

### Example
```asm
; bare metal on ECS/AGA only: plain PAL (or NTSC) decodes, no variable timing
        move.w  #$0020,beamcon0(a6)             ; DISPLAYPAL; $0000 = NTSC
```

### Gotchas
- Check the Agnus ID in VPOSR (or `GfxBase->ChipRevBits0` `GFXF_HR_AGNUS`) first: OCS
  has no BEAMCON0.
- Switching PAL/NTSC changes line counts and timing only; the crystal (audio and serial
  clock constants) stays the same.
- Any VAR* bit takes the matching sync/blank/total registers out of the hardwired
  defaults: load them before setting the bit.
- OS programs must not write it: use display mode IDs through graphics.library.

**See also:** HTOTAL, VTOTAL, [VPOSR](dma-beam.md#vposr), [STRLONG](dma-beam.md#strlong)

## HTOTAL
`$DFF1C0` · write · Agnus · ECS · active with BEAMCON0 VARBEAMEN (or DUAL)

Highest horizontal colour-clock count: a line lasts HTOTAL+1 colour clocks.

| Bit | Meaning |
|---|---|
| 15-8 | write 0 |
| 7-0 | H8-H1 count |

NDK: `htotal` (custom.i); C `custom->htotal`.

### Gotchas
- Unless PAL or LOLDIS is set, lines alternate long/short: every other line is HTOTAL+2.
- Changing it changes line rate, which also scales pot counts and audio limits.

**See also:** BEAMCON0, HSSTRT, HSSTOP, HCENTER

## HSSTOP
`$DFF1C2` · write · Agnus · ECS · active with BEAMCON0 VARHSYEN

Horizontal position (colour clocks) where HSYNC ends.

Bit layout as HTOTAL.

NDK: `hsstop` (custom.i); C `custom->hsstop`.

**See also:** HSSTRT, BEAMCON0

## HBSTRT
`$DFF1C4` · write · Agnus · ECS · used by the variable composite blank

Horizontal position (colour clocks) where horizontal blanking starts.

Bits 7-0 as HTOTAL. AGA adds bits 10-8 for 35 ns fine positioning: see the amiga-aga skill.

NDK: `hbstrt` (custom.i); C `custom->hbstrt`.

### Gotchas
- HRM composite recipe: HBSTRT = HSSTRT - (HSSTOP - HSSTRT).

**See also:** HBSTOP, HCENTER

## HBSTOP
`$DFF1C6` · write · Agnus · ECS · used by the variable composite blank

Horizontal position (colour clocks) where horizontal blanking ends.

Bits 7-0 as HTOTAL. AGA adds bits 10-8 for 35 ns fine positioning: see the amiga-aga skill.

NDK: `hbstop` (custom.i); C `custom->hbstop`.

### Gotchas
- HRM composite recipe: HBSTOP = HCENTER - (HSSTOP - HSSTRT).

**See also:** HBSTRT, HCENTER

## VTOTAL
`$DFF1C8` · write · Agnus · ECS · active with BEAMCON0 VARBEAMEN

Highest line number: the vertical counter resets after it (VTOTAL+1 lines per field).

NDK: `vtotal` (custom.i); C `custom->vtotal`.

### Gotchas
- With BPLCON0 LACE set, the long field has VTOTAL+2 lines and the short field VTOTAL+1.

**See also:** HTOTAL, VSSTRT, VBSTRT

## VSSTOP
`$DFF1CA` · write · Agnus · ECS · active with BEAMCON0 VARVSYEN

Line number where vertical sync ends.

NDK: `vsstop` (custom.i); C `custom->vsstop`.

**See also:** VSSTRT, HCENTER

## VBSTRT
`$DFF1CC` · write · Agnus · ECS · active with BEAMCON0 VARVBEN

Line number where vertical blanking starts.

| Bit | Meaning |
|---|---|
| 15-11 | write 0 |
| 10-0 | V10-V0 line |

NDK: `vbstrt` (custom.i); C `custom->vbstrt`.

### Gotchas
- VARVBEN also moves the chip-internal vertical blank (sprite restart, light-pen reset)
  to this programmable blank.

**See also:** VBSTOP, BEAMCON0

## VBSTOP
`$DFF1CE` · write · Agnus · ECS · active with BEAMCON0 VARVBEN

Line number where vertical blanking ends (bits 10-0).

NDK: `vbstop` (custom.i); C `custom->vbstop`.

**See also:** VBSTRT

## HSSTRT
`$DFF1DE` · write · Agnus · ECS · active with BEAMCON0 VARHSYEN

Horizontal position (colour clocks) where HSYNC starts.

Bit layout as HTOTAL.

NDK: `hsstrt` (custom.i); C `custom->hsstrt`.

**See also:** HSSTOP, HCENTER

## VSSTRT
`$DFF1E0` · write · Agnus · ECS · active with BEAMCON0 VARVSYEN

Line number where vertical sync starts.

NDK: `vsstrt` (custom.i); C `custom->vsstrt`.

### Gotchas
- VSYNC is set on VSSTRT and reset on VSSTOP, at horizontal position HSSTRT on short
  fields and HCENTER on long fields.

**See also:** VSSTOP, HCENTER

## HCENTER
`$DFF1E2` · write · Agnus · ECS · needed for interlace with variable beam counters

Horizontal position (colour clocks) of VSYNC on long (interlace) fields.

Bit layout as HTOTAL.

NDK: `hcenter` (custom.i); C `custom->hcenter`.

### Gotchas
- HRM composite recipe: HCENTER half a line after HSSTRT.

**See also:** HSSTRT, VSSTRT, BEAMCON0

## SPRHSTRT, SPRHSTOP
`$DFF1D0` / `$DFF1D2` · write · Agnus · ECS · UHRES only

First and last line of the UHRES sprite pointer fetch.

| Register | Bit | Meaning |
|---|---|---|
| SPRHSTRT | 10-0 | V10-V0 start line |
| SPRHSTOP | 15 | SPRHWRM: invert ARW* polarity when SPRHDAT is output (external VRAM) |
| SPRHSTOP | 10-0 | V10-V0 stop line |

NDK: `sprhstrt`, `sprhstop` (custom.i); C `custom->sprhstrt`, `custom->sprhstop`.

### Gotchas
- Only meaningful with external UHRES video memory (VRAM) hardware.

**See also:** BPLHSTRT, BPLHSTOP, BPLHPTH, BPLHPTL, BPLHMOD, SPRHPTH, SPRHPTL, BPLHDAT, SPRHDAT

## BPLHSTRT, BPLHSTOP
`$DFF1D4` / `$DFF1D6` · write · Agnus · ECS · UHRES only

First and last line of the UHRES bitplane pointer fetch.

| Register | Bit | Meaning |
|---|---|---|
| BPLHSTRT | 10-0 | V10-V0 start line |
| BPLHSTOP | 15 | BPLHWRM: invert ARW* polarity when BPLHDAT is output (external VRAM) |
| BPLHSTOP | 10-0 | V10-V0 stop line |

NDK: `bplhstrt`, `bplhstop` (custom.i); C `custom->bplhstrt`, `custom->bplhstop`.

**See also:** SPRHSTRT, SPRHSTOP, BPLHPTH, BPLHPTL, BPLHMOD, SPRHPTH, SPRHPTL, BPLHDAT, SPRHDAT

## HHPOSW
`$DFF1D8` · write · Agnus · ECS · DUAL mode

Write the secondary (DUAL mode) horizontal beam counter.

Bit layout as HTOTAL. With BEAMCON0 DUAL this counter drives the UHRES pointers and the
HTOTAL, HSSTRT, HSSTOP, HBSTRT, HBSTOP comparisons.

NDK: `hhposw` (custom.i); C `custom->hhposw`.

**See also:** HHPOSR, BEAMCON0

## HHPOSR
`$DFF1DA` · read · Agnus · ECS · DUAL mode

Read the secondary (DUAL mode) horizontal beam counter.

Bit layout as HTOTAL; returns the light-pen latch like VHPOSR unless BEAMCON0 LPENDIS.

NDK: `hhposr` (custom.i); C `custom->hhposr`.

**See also:** HHPOSW, [VHPOSR](dma-beam.md#vhposr)

## DIWHIGH
`$DFF1E4` · write · Agnus + Denise · ECS

Upper bits of the display window start and stop positions (removes the OCS limits).

| Bit | Name | Meaning |
|---|---|---|
| 15-14 | -- | write 0 |
| 13 | H8 | HSTOP bit 8 |
| 12-11 | -- | write 0 on ECS (AGA: HSTOP fine bits) |
| 10-8 | V10-V8 | VSTOP bits 10-8 |
| 7-6 | -- | write 0 |
| 5 | H8 | HSTART bit 8 |
| 4-3 | -- | write 0 on ECS (AGA: HSTART fine bits) |
| 2-0 | V10-V8 | VSTART bits 10-8 |

AGA adds the H1/H0 fine positioning bits 12-11 and 4-3: see the amiga-aga skill.

NDK: `diwhigh` (custom.i); C `custom->diwhigh`.

### Example
```asm
; PAL 320x256 window with explicit upper bits: start $02C/$081, stop $12C/$1C1
        dc.w    diwstrt,$2c81
        dc.w    diwstop,$2cc1
        dc.w    diwhigh,$2100                   ; stop V8 (bit 8) + stop H8 (bit 13)
```

### Gotchas
- Write DIWHIGH after DIWSTRT and DIWSTOP: only then are the explicit positions used;
  without it the OCS implied-bit rules apply.
- With ECS Denise present, V36+ graphics.library builds its Copper lists with DIWHIGH:
  code that edits those lists by hand must keep it consistent.
- Not present on OCS Denise.

**See also:** [DIWSTRT](playfield.md#diwstrt), [DIWSTOP](playfield.md#diwstop), [BPLCON3](playfield.md#bplcon3)

## DENISEID
`$DFF07C` · read · Denise · ECS (OCS: returns bus garbage)

Video chip revision: identifies OCS Denise, ECS Denise or AGA Lisa.

| Bit | Meaning |
|---|---|
| 15-8 | reserved (loaded from the serial mouse bus on Lisa) |
| 7-4 | revision, inverted (`$F` = revision 0) |
| 3 | 1 |
| 2 | 0 = AGA feature set (Lisa) |
| 1 | 0 = ECS feature set (ECS Denise or Lisa) |
| 0 | 1 |

ECS Denise 8373 returns `$FC` in the low byte, Lisa `$F8`; OCS Denise 8362 has no
register.

NDK: `deniseid` (custom.i); C `custom->deniseid`. graphics.library sets
`GFXF_HR_DENISE` / `GFXF_AA_LISA` in `GfxBase->ChipRevBits0` from it.

### Example
```asm
; d0 = 0 OCS Denise, 1 ECS Denise, 2 AGA Lisa  (a6 = $DFF000)
VideoChip:
        move.w  deniseid(a6),d1
        moveq   #30,d2
.same   move.w  deniseid(a6),d3
        cmp.b   d1,d3                           ; OCS: open bus, value changes
        bne.s   .ocs
        dbf     d2,.same
        moveq   #0,d0
        btst    #1,d1
        bne.s   .done                           ; bit 1 = 1: no ECS features
        moveq   #1,d0
        btst    #2,d1
        bne.s   .done                           ; bit 2 = 1: not AGA
        moveq   #2,d0
.done   rts
.ocs    moveq   #0,d0
        rts
```

### Gotchas
- On OCS the value is whatever was last on the bus: read it repeatedly and treat an
  unstable value as OCS.
- OS programs should test `GfxBase->ChipRevBits0` instead.

**See also:** [VPOSR](dma-beam.md#vposr), BEAMCON0

## BPLHPTH, BPLHPTL, BPLHMOD, SPRHPTH, SPRHPTL, BPLHDAT, SPRHDAT
`$DFF1EC`/`$DFF1EE`, `$DFF1E6`, `$DFF1E8`/`$DFF1EA`, `$DFF07A`, `$DFF078` · write · Agnus · ECS · UHRES only, no custom.i labels

UHRES (external VRAM) bitplane and sprite pointers, modulo and bus identifiers.

| Register | Address | Meaning |
|---|---|---|
| BPLHPTH, BPLHPTL | `$DFF1EC`, `$DFF1EE` | UHRES bitplane pointer; output on the 2nd free DMA slot of each line, modulo added each time |
| BPLHMOD | `$DFF1E6` | signed modulo added to the UHRES bitplane pointer each line (plus 2) |
| SPRHPTH, SPRHPTL | `$DFF1E8`, `$DFF1EA` | UHRES sprite pointer; 1st and 3rd free DMA slots, increments per line |
| BPLHDAT | `$DFF07A` | identifier placed on the register bus when BPLHPT is valid (for external logic) |
| SPRHDAT | `$DFF078` | identifier placed on the register bus when SPRHPT is valid |

Enabled by BPLCON0 UHRES plus the DMACON master enable; BEAMCON0 DUAL runs them from
the secondary horizontal counter.

NDK: no labels in custom.i and no fields in `struct Custom` for these addresses.

### Gotchas
- They only matter to external VRAM hardware that decodes these pointers and bus
  identifiers; ordinary displays never need them.

**See also:** SPRHSTRT, SPRHSTOP, BPLHSTRT, BPLHSTOP, BEAMCON0, [BPLCON0](playfield.md#bplcon0)
