# Custom chips: DMA control and beam counter

Addresses are 68k addresses (`$DFF000` + chip offset). Every custom register is either
read-only or write-only: never read a write-only register (it can trash it) and never
write a read-only one. NDK offsets come from `hardware/custom.i` (use them as
`label(a6)` with `a6 = $DFF000`); C code uses `struct Custom` from `hardware/custom.h`.

## DMACON
`$DFF096` · write (set/clear) · Agnus (+ Denise, Paula) · OCS · read back via DMACONR `$DFF002`

Enable or disable DMA channels, the DMA master switch and blitter priority.

| Bit | Name | Meaning |
|---|---|---|
| 15 | SET/CLR | 1 = set every bit written as 1; 0 = clear every bit written as 1. 0-bits are untouched |
| 14 | BBUSY | status only (see DMACONR); write 0 |
| 13 | BZERO | status only (see DMACONR); write 0 |
| 12-11 | -- | unused, write 0 |
| 10 | BLTPRI | "blitter nasty": blitter DMA gets full priority, CPU cannot steal chip-bus cycles during a blit |
| 9 | DMAEN | master enable: bits 8-0 only take effect while this is 1 (ECS: also UHRES DMA) |
| 8 | BPLEN | bitplane DMA |
| 7 | COPEN | Copper DMA |
| 6 | BLTEN | blitter DMA |
| 5 | SPREN | sprite DMA (all 8 sprites) |
| 4 | DSKEN | disk DMA |
| 3-0 | AUD3EN-AUD0EN | audio channel 3-0 DMA |

NDK: `dmacon` (custom.i); `DMAF_SETCLR`, `DMAF_BLITHOG` (bit 10), `DMAF_MASTER`,
`DMAF_RASTER`, `DMAF_COPPER`, `DMAF_BLITTER`, `DMAF_SPRITE`, `DMAF_DISK`,
`DMAF_AUD0`-`DMAF_AUD3`, `DMAF_AUDIO` ($000F), `DMAF_ALL` ($01FF) and the `DMAB_` bit
numbers (dmabits.i); C `custom->dmacon`.

### Example
```asm
        include "hardware/custom.i"
        include "hardware/dmabits.i"
        lea     $dff000,a6
        move.w  dmaconr(a6),OldDma              ; save for exit
        move.w  #$7fff,dmacon(a6)               ; bit 15 = 0: clear every channel
        move.l  #MyCopper,cop1lc(a6)            ; valid Copper list BEFORE COPEN
        move.w  d0,copjmp1(a6)
        move.w  #DMAF_SETCLR!DMAF_MASTER!DMAF_RASTER!DMAF_COPPER!DMAF_BLITTER,dmacon(a6)
        ; ... on exit:
        move.w  #$7fff,dmacon(a6)
        move.w  OldDma,d0
        and.w   #$07ff,d0                       ; drop status bits 14-13
        or.w    #DMAF_SETCLR,d0
        move.w  d0,dmacon(a6)
```

### Gotchas
- Setting some bits and clearing others needs two writes (one with bit 15 = 1, one with 0).
- `$7FFF` clears everything; a value without bit 15 never enables anything.
- When restoring a value read from DMACONR, mask it with `$07FF` before OR-ing
  `DMAF_SETCLR`: bits 14-13 are status, not controls.
- Point COP1LC at a valid list and strobe COPJMP1 before setting COPEN, or the Copper
  runs from an undefined address.
- Turning sprite DMA off while a sprite is being drawn leaves a vertical bar: switch it
  during vertical blank.
- Disk DMA also needs the DSKLEN double write; audio DMA starts playing as soon as its
  AUDxEN bit goes to 1.

**See also:** DMACONR, [INTENA](interrupts.md#intena), [BLTSIZE](blitter.md#bltsize), [DSKLEN](disk.md#dsklen)

## DMACONR
`$DFF002` · read · Agnus (+ Paula) · OCS · write via DMACON `$DFF096`

Read the DMA enable bits plus the blitter busy and blitter zero flags.

| Bit | Name | Meaning |
|---|---|---|
| 15 | -- | no meaning on read |
| 14 | BBUSY | 1 = blit in progress (NDK `DMAB_BLTDONE`) |
| 13 | BZERO | 1 = every result bit of the last blit was 0 (NDK `DMAB_BLTNZERO`) |
| 12-11 | -- | unused |
| 10-0 | BLTPRI..AUD0EN | current enables, as in DMACON |

NDK: `dmaconr` (custom.i); `DMAF_BLTDONE` ($4000), `DMAF_BLTNZERO` ($2000),
`DMAB_BLTDONE` (14), `DMAB_BLTNZERO` (13) (dmabits.i); C `custom->dmaconr`.

### Example
```asm
; wait until the blitter is idle (a6 = $DFF000)
WaitBlitter:
        btst    #DMAB_BLTDONE-8,dmaconr(a6)     ; dummy test first (see gotchas)
.wait   btst    #DMAB_BLTDONE-8,dmaconr(a6)     ; btst on memory tests the high byte
        bne.s   .wait
        rts
```

### Gotchas
- NDK names are misleading: `DMAF_BLTDONE` is 1 while the blitter is BUSY, and
  `DMAF_BLTNZERO` is 1 when the result WAS zero.
- Test BBUSY twice after starting a blit: on pre-Fat-Agnus chips the flag is not set until
  the blitter gets its first DMA cycle, and a CPU running from fast RAM can test too early.
- The zero flag is valid only after the blit has finished; it is computed even with USED
  (D output) disabled, so an AND blit with D off is a cheap pixel-overlap test.
- `btst #n,dmaconr(a6)` is a byte test of `$DFF002`: use `n-8` for bits 15-8.

**See also:** DMACON, [BLTSIZE](blitter.md#bltsize), [BLTCON0](blitter.md#bltcon0)

## VPOSR
`$DFF004` · read · Agnus · OCS (ID bits, LOL, V10-V9 documented for ECS/AGA) · pairs with VHPOSR as a longword

Read the long-frame flag, the Agnus chip ID and the top vertical beam position bit(s).

| Bit | Name | Meaning |
|---|---|---|
| 15 | LOF | 1 = long frame (interlace field flag; auto-toggles when BPLCON0 LACE is set) |
| 14-8 | I6-I0 | Agnus/Alice identification (table below) |
| 7 | LOL | ECS/AGA: long line; 0 = short raster line |
| 6-3 | -- | unused |
| 2-1 | V10-V9 | ECS/AGA Agnus only |
| 0 | V8 | vertical beam counter bit 8 |

| ID (bits 14-8) | Chip |
|---|---|
| $00 | 8367 / 8371 (Fat) Agnus, PAL |
| $10 | 8361 / 8370 (Fat) Agnus, NTSC |
| $20 / $30 | 8372 ECS Agnus up to rev 4, PAL / NTSC |
| $22 / $31 | 8372 ECS Agnus rev 5, PAL / NTSC |
| $22 / $32 | 8374 Alice (AGA) up to rev 2, PAL / NTSC |
| $23 / $33 | 8374 Alice rev 3-4, PAL / NTSC |

NDK: `vposr` (custom.i); C `custom->vposr` (Bartman's custom.h also has `vpos32`,
`vposr_h`, `vposr_l`). graphics.library sets `GFXF_HR_AGNUS` in `GfxBase->ChipRevBits0`
from this register.

### Example
```asm
; d0 = current raster line (V8-V0); use $7ff to include V10-V9 on ECS/AGA
        move.l  vposr(a6),d0                    ; VPOSR in high word, VHPOSR in low word
        lsr.l   #8,d0
        and.l   #$1ff,d0

; d0 = Agnus ID
        move.w  vposr(a6),d0
        lsr.w   #8,d0
        and.w   #$7f,d0
```

### Gotchas
- Read VPOSR and VHPOSR together with one `move.l`: two word reads can straddle a line
  change and pair a new V8 with old V7-V0.
- In every ID of the table the `$10` bit marks the NTSC variant. `$22` is ambiguous
  (8372 rev 5 PAL or early Alice PAL): use DENISEID or `ChipRevBits0` to tell ECS from AGA.
- Mask out LOL and V10-V9 on OCS, where those bits are undefined.
- With BPLCON0 LPEN set, VPOSR/VHPOSR return the latched light-pen position, not the beam
  (ECS: unless BEAMCON0 LPENDIS is set).

**See also:** VHPOSR, VPOSW, [BPLCON0](playfield.md#bplcon0), [DENISEID](ecs.md#deniseid), [BEAMCON0](ecs.md#beamcon0)

## VPOSW
`$DFF02A` · write · Agnus · OCS · test/sync use only

Write the long-frame flip-flop (bit 15) and V8, same layout as VPOSR.

NDK: `vposw` (custom.i); C `custom->vposw`.

### Gotchas
- Bit 15 writes the long-frame flip-flop (interlace field type). The HRM lists the
  counter bits for chip-test synchronisation only; writing them disturbs display timing.

**See also:** VPOSR, VHPOSW

## VHPOSR
`$DFF006` · read · Agnus · OCS · low word of the VPOSR longword

Read the low 8 bits of the vertical beam position and the horizontal position.

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | V7-V0 | vertical position, low 8 bits (V8 is in VPOSR) |
| 7-0 | H8-H1 | horizontal position in colour clocks (280 ns = 2 lores pixels) |

NDK: `vhposr` (custom.i); C `custom->vhposr` (or `vhposr_h` / `vhposr_l`).

### Example
```asm
; wait for raster line $F0 (only valid for lines below 256)
.wait   cmp.b   #$f0,vhposr(a6)                 ; byte read = V7-V0
        bne.s   .wait
```

### Gotchas
- A byte compare ignores V8: line $F0 and line $1F0 look the same. Use the longword read
  from VPOSR for PAL lines 256-312.
- The horizontal field uses the same units as a Copper WAIT (which only compares H8-H2).
- Light pen: with BPLCON0 LPEN set this returns the latched pen position.

**See also:** VPOSR, VHPOSW, [COPINS](copper.md#copins)

## VHPOSW
`$DFF02C` · write · Agnus · OCS · test only

Write the beam counter (V7-V0, H8-H1); meant for chip test synchronisation only.

NDK: `vhposw` (custom.i); C `custom->vhposw`.

### Gotchas
- Do not write it in normal programs: it moves the beam counter and corrupts the display.

**See also:** VHPOSR, VPOSW

## REFPTR
`$DFF028` · write · Agnus · OCS · test only: never write

Dynamic RAM refresh address generator, writable only for chip testing.

NDK: `refptr` (custom.i); C `custom->refptr`.

### Gotchas
- The HRM says the CPU must never write it.

**See also:** STREQU

## STREQU
`$DFF038` · strobe (chip bus only) · Denise · OCS · not for CPU or Copper

Strobe for horizontal sync with vertical blank and equalisation pulses (Agnus to Denise).

Agnus puts STREQU, STRVBL or STRHOR on the internal register bus during the first
refresh slot of each line; a refresh slot not used by a strobe carries the null address
`$1FE`.

NDK: `strequ` (custom.i); C `custom->strequ`.

### Gotchas
- Internal timing signal: nothing useful happens when the CPU touches it, and the Copper
  can never write registers below `$040`.

**See also:** STRVBL, STRHOR, STRLONG

## STRVBL
`$DFF03A` · strobe (chip bus only) · Denise · OCS · not for CPU or Copper

Strobe for horizontal sync during vertical blank (Agnus to Denise).

NDK: `strvbl` (custom.i); C `custom->strvbl`.

**See also:** STREQU, STRHOR, STRLONG

## STRHOR
`$DFF03C` · strobe (chip bus only) · Denise, Paula · OCS · not for CPU or Copper

Strobe for horizontal sync on ordinary lines (Agnus to Denise and Paula).

NDK: `strhor` (custom.i); C `custom->strhor`.

**See also:** STREQU, STRVBL, STRLONG

## STRLONG
`$DFF03E` · strobe (chip bus only) · Denise · OCS (ECS: can be disabled) · not for CPU or Copper

Strobe marking long horizontal lines (228 colour clocks NTSC), sent on alternate lines.

Agnus sends it in the second refresh slot of every other line. ECS: with variable beam
counters the long line is HTOTAL+2; BEAMCON0 LOLDIS suppresses the long/short toggle
and therefore this strobe.

NDK: `strlong` (custom.i); C `custom->strlong`.

**See also:** STREQU, [BEAMCON0](ecs.md#beamcon0), [HTOTAL](ecs.md#htotal), [VPOSR](#vposr)
