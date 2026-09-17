# AGA registers (Alice, Lisa)

AGA-only registers and the AGA extensions of OCS/ECS registers. The OCS/ECS meaning of
shared bits (priorities, DIW/DDF basics, sprite data, blitter) is in the amiga-hardware
skill; only what AGA adds or changes is here.

- Addresses are absolute (`$DFF000` + offset). NDK labels in the NDK lines are the
  offsets from `hardware/custom.i` (`lea $dff000,a6` then `move.w #x,bplcon3(a6)`).
- Bit names come from the Commodore AA spec. Very few have NDK symbols; when a name is
  "doc name" it does not exist in any NDK include, so define your own EQU.
- Only write these registers after AGA detection ([detection topic](../topics/detection.md)).
  Write unused ("x") bits as 0.
- The Lisa reset input clears BPLCON3, BPLCON4, CLXCON2, DIWHIGH and FMODE to 0. That is
  not always the value OCS-style code needs (see BPLCON3, BPLCON4).

## BPLCON0
`$DFF100` · write · Lisa (+Alice) · AGA extension of OCS register · NDK `bplcon0`

Plane count, resolution and mode bits, with BPU3, SHRES, BYPASS and ECSENA added on AGA.

| Bit | Name | Meaning |
|---|---|---|
| 15 | HIRES | 70ns (hires) pixels |
| 14-12 | BPU2-BPU0 | plane count 0-7 (low 3 bits of the 4-bit BPU value) |
| 11 | HAM (HAMEN) | hold-and-modify: HAM6 with 6 planes, HAM8 with 8 planes, any resolution |
| 10 | DPF (DBLPF) | dual playfield (odd planes = PF1, even = PF2), up to 4+4, any resolution |
| 9 | COLOR | colour burst on composite output |
| 8 | GAUD | genlock audio on the ZD pin during blanking |
| 7 | UHRES | UHRES (VRAM) pointers; not usable on stock AGA machines |
| 6 | SHRES | superhires, 35ns pixels |
| 5 | BYPASS | bypass the colour table (raw 8-bit data to video out); keep 0 |
| 4 | BPU3 | BPU bit 3: set with bits 14-12 = 000 for 8 planes |
| 3 | LPEN | light pen enable |
| 2 | LACE | interlace |
| 1 | ERSY | external resync |
| 0 | ECSENA | enables BPLCON3 bits BRDRBLNK, BRDNTRAN, ZDCLKEN, BRDSPRT, EXTBLKEN |

| Planes | Bits 14-12 | Bit 4 | Colours |
|---|---|---|---|
| 1-6 | 001-110 | 0 | 2-64 (6 = EHB unless KILLEHB/HAM/DPF) |
| 7 | 111 | 0 | 128 |
| 8 | 000 | 1 | 256 (or HAM8 with bit 11) |

NDK: `bplcon0` (custom.i); `MODE_640` $8000, `PLNCNTMSK` $7, `PLNCNTSHFT` 12, `HOLDNMODIFY`
$800, `DBLPF` $400, `COLORON` $200, `INTERLACE` 4 (graphics/display.h, OCS view: "7 =
reserved"); `USE_BPLCON3` 1 (hardware/custom.h, `#ifdef ECS_SPECIFIC`). BPU3, SHRES,
BYPASS, UHRES, ECSENA are doc names.

### Example
```asm
BPL_LORES7      EQU     $7200       ; 7 planes lores, COLOR
BPL_LORES8      EQU     $0210       ; 8 planes lores (BPU3), COLOR
BPL_HAM8        EQU     $0a10       ; HAM8 lores: BPU3 + HAM + COLOR
BPL_HIRES8      EQU     $8211       ; 8 planes hires + ECSENA (needs 2x fetch, see FMODE)
BPL_SHRES8      EQU     $0250       ; 8 planes superhires (needs 4x fetch)

        dc.w    bplcon0,BPL_LORES8  ; in the copper list, after the palette
```

### Gotchas
- `depth<<12` breaks at 8: `8<<12` = $8000 = HIRES with 0 planes. Encode 8 planes as bit 4.
- With bit 4 set keep bits 14-12 at 000; other combinations are undefined.
- `SUPERHIRES` ($0020) in graphics/view.h is a ViewPort `Modes` flag, not the BPLCON0 SHRES
  bit ($0040). Do not OR view.h flags into BPLCON0.
- Bandwidth: lores takes 8 planes at 1x fetch; hires above 4 planes and superhires above
  2 planes need 2x, superhires above 4 planes needs 4x (AA mode tables). Set FMODE to match.
- ECSENA=0 only masks the five BPLCON3 border/genlock bits; setting it again restores
  the values last written to BPLCON3.
- OS-friendly code ORs `GfxBase->system_bplcon0` (genlock bits) into its BPLCON0 value.

**See also:** BPLCON2, BPLCON3, FMODE, [bitplanes and modes](../topics/bitplanes-and-modes.md)

## BPLCON1
`$DFF102` · write · Lisa · AGA extension of OCS register · NDK `bplcon1`

Two 8-bit horizontal scroll values, one per playfield, in 35ns (superhires pixel) steps.

| Bit | Name | Meaning |
|---|---|---|
| 15-14 | PF2H7-PF2H6 | PF2 scroll, high bits (AGA) |
| 13-12 | PF2H1-PF2H0 | PF2 scroll, 70ns/35ns fine bits (AGA) |
| 11-10 | PF1H7-PF1H6 | PF1 scroll, high bits (AGA) |
| 9-8 | PF1H1-PF1H0 | PF1 scroll, 70ns/35ns fine bits (AGA) |
| 7-4 | PF2H5-PF2H2 | PF2 scroll, the OCS nibble (140ns steps) |
| 3-0 | PF1H5-PF1H2 | PF1 scroll, the OCS nibble (140ns steps) |

Scroll value S (0-255) per playfield: bits H1-H0 = `S & 3`, H5-H2 = `(S>>2) & $F`,
H7-H6 = `(S>>6) & 3`. One lores pixel = 4 steps, hires = 2, superhires = 1. An OCS
value written unchanged keeps its OCS meaning (whole lores pixels 0-15).

NDK: `bplcon1` (custom.i); `PFA_FINE_SCROLL` $F, `PFB_FINE_SCROLL_SHIFT` 4,
`PF_FINE_SCROLL_MASK` $F (graphics/display.h, OCS nibbles only). PFxHy are doc names.

### Example
```asm
; d0.w = scroll 0-255 (35ns steps), same for both playfields -> d1.w = BPLCON1
; trashes d2
ScrollToCon1:
        move.w  d0,d1
        lsr.w   #2,d1
        andi.w  #$000f,d1           ; PF1H5-PF1H2
        move.w  d1,d2
        lsl.w   #4,d2
        or.w    d2,d1               ; PF2H5-PF2H2
        move.w  d0,d2
        andi.w  #$0003,d2
        lsl.w   #8,d2               ; PF1H1-PF1H0 -> bits 9-8
        or.w    d2,d1
        lsl.w   #4,d2               ; PF2H1-PF2H0 -> bits 13-12
        or.w    d2,d1
        move.w  d0,d2
        lsr.w   #6,d2
        andi.w  #$0003,d2
        lsl.w   #8,d2
        lsl.w   #2,d2               ; PF1H7-PF1H6 -> bits 11-10
        or.w    d2,d1
        lsl.w   #4,d2               ; PF2H7-PF2H6 -> bits 15-14
        or.w    d2,d1
        rts
```
S = 136 (34 lores pixels) gives $8822.

### Gotchas
- The fine and high bits are not contiguous: never add a pixel offset straight to the register.
- The useful range is one fetch unit: on a lores screen 16 lores pixels at 1x fetch, 32 at
  2x, 64 at 4x; half that on hires, a quarter on superhires (AA scroll-range tables). The fetch must start early enough to supply the extra data.
- Some 1993 docs (RandyAGA's bit list) still use the OCS names PF1H0-PF1H3 for bits 3-0;
  the AA spec renamed them PF1H2-PF1H5.

**See also:** FMODE, [FMODE and fetch](../topics/fmode-and-fetch.md)

## BPLCON2
`$DFF104` · write · Lisa · AGA/ECS extension of OCS register · NDK `bplcon2`

Playfield/sprite priorities plus genlock (ZD) control, KILLEHB and RDRAM.

| Bit | Name | Meaning |
|---|---|---|
| 15 | - | write 0 |
| 14-12 | ZDBPSEL2-0 | plane mirrored on ZD when ZDBPEN=1 (000 = plane 1 ... 111 = plane 8) |
| 11 | ZDBPEN | ZD pin follows the selected bitplane (ORed with ZDCTEN mode) |
| 10 | ZDCTEN | ZD follows the T bit (bit 15) of the displayed colour entry; 0 = colour 0 is transparent |
| 9 | KILLEHB | disable extra-halfbrite: 6 planes give 64 real colours |
| 8 | RDRAM | colour table accesses become reads; keep 0 |
| 7 | SOGEN | drive the SOG output pin high |
| 6 | PF2PRI | playfield 2 in front of playfield 1 |
| 5-3 | PF2P2-0 | PF2 priority versus sprites (OCS) |
| 2-0 | PF1P2-0 | PF1 priority versus sprites (OCS) |

NDK: `bplcon2` (custom.i); `PF2PRI` $40 (graphics/display.h); `BPLCON2_ZDCTEN` (1<<10),
`BPLCON2_ZDBPEN` (1<<11), `BPLCON2_ZDBPSEL0`-`BPLCON2_ZDBPSEL2` (1<<12..14) in
hardware/custom.h under `#ifdef ECS_SPECIFIC`. KILLEHB, RDRAM, SOGEN are doc names.

### Example
```asm
        dc.w    bplcon2,$0224       ; KILLEHB + sprites in front: 6-plane 64-colour screen
```

### Gotchas
- RDRAM=1 silently turns every COLORxx write into a read: the palette stops changing.
- KILLEHB left set by earlier code turns a 6-plane EHB picture into 64 wrong colours;
  write the whole register (bit 9 = 0) when you want EHB.
- RandyAGA labels bit 7 "SOGEN (ZDCLKEN)"; ZDCLKEN is BPLCON3 bit 2.

**See also:** BPLCON0, BPLCON3, [bitplanes and modes](../topics/bitplanes-and-modes.md)

## BPLCON3
`$DFF106` · write · Lisa · AGA (bits 5,4,2,1,0 from ECS) · NDK `bplcon3`

Colour bank and LOCT for palette loads, PF2 colour offset, sprite resolution, border bits.

| Bit | Name | Meaning |
|---|---|---|
| 15-13 | BANK2-BANK0 | which 32 of the 256 entries COLOR00-COLOR31 address (bank n = entries 32n..32n+31) |
| 12-10 | PF2OF2-PF2OF0 | dual-playfield PF2 colour offset: 000=0, 001=2, 010=4, 011=8 (OCS), 100=16, 101=32, 110=64, 111=128 |
| 9 | LOCT | 0 = COLOR writes load the high nibbles (copied to low), 1 = load low nibbles only |
| 8 | - | write 0 |
| 7-6 | SPRES1-SPRES0 | sprite resolution: 00 ECS default, 01 lores 140ns, 10 hires 70ns, 11 superhires 35ns |
| 5 | BRDRBLNK | border blanked (black) instead of colour 0; needs ECSENA |
| 4 | BRDNTRAN | border opaque for genlock (ZD low in border); needs ECSENA |
| 3 | - | write 0 |
| 2 | ZDCLKEN | ZD pin outputs a 14MHz clock (disables other ZD functions); needs ECSENA |
| 1 | BRDSPRT | sprites visible in the border; needs ECSENA |
| 0 | EXTBLKEN | programmable BLANK output; needs ECSENA |

NDK: `bplcon3` (custom.i). hardware/custom.h (`#ifdef ECS_SPECIFIC`, ECS-era names):
`BPLCON3_EXTBLNKEN` (1<<0), `BPLCON3_EXTBLKZD` (1<<1), `BPLCON3_ZDCLKEN` (1<<2),
`BPLCON3_BRDNTRAN` (1<<4), `BPLCON3_BRDNBLNK` (1<<5). SPRES values match `SPRITERESN_ECS`
0, `SPRITERESN_140NS` 1, `SPRITERESN_70NS` 2, `SPRITERESN_35NS` 3 (graphics/view.h).
BANK, PF2OF, LOCT, SPRES, BRDSPRT are doc names.

### Example
```asm
        dc.w    bplcon0,$0211       ; 8 planes lores + ECSENA
        dc.w    bplcon3,$0c20       ; PF2OF=011 (OCS), BRDRBLNK: black border
```

### Gotchas
- `$0C00` (PF2OF=011, everything else 0) is the OCS-compatible value. Reset clears the
  register to 0 (PF2OF=000), so write $0C00 yourself.
- BANK and LOCT stay in force until rewritten: end every palette load with `bplcon3,$0c00`
  (or your normal value) or later COLOR writes land in the wrong bank or nibble.
- The NDK ECS_SPECIFIC names disagree with the AA spec: bit 1 is `BPLCON3_EXTBLKZD` there
  but BRDSPRT in AA docs, bit 5 is `BPLCON3_BRDNBLNK`. Use the AA meaning on AGA.
- SPRES applies to all eight sprites at once.

**See also:** COLORxx, BPLCON4, [palette](../topics/palette.md), [sprites](../topics/sprites.md)

## BPLCON4
`$DFF10C` · write · Lisa · AGA · NDK `bplcon4`

Bitplane colour-index XOR mask and the colour bases of even and odd sprites.

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | BPLAM7-BPLAM0 | XORed with the 8-bit bitplane colour index before the colour table |
| 7-4 | ESPRM7-ESPRM4 | high nibble of the colour index for sprites 0, 2, 4, 6 (0001 = OCS colours 16-31) |
| 3-0 | OSPRM7-OSPRM4 | high nibble of the colour index for sprites 1, 3, 5, 7 (0001 = OCS) |

Sprite pixel colour index = `xSPRM<<4 | (pair*4 + pixel)`, where pair = sprite number / 2.

NDK: `bplcon4` (custom.i). Bit names are doc names. OS equivalents: `VTAG_SPEVEN_BASE_SET`,
`VTAG_SPODD_BASE_SET`, `VTAG_PF1_BASE_SET`, `VTAG_PF2_BASE_SET` (graphics/videocontrol.h).

### Example
```asm
        dc.w    bplcon4,$0011       ; OCS-compatible: no mask, sprites use 16-31
        ; ... later, one MOVE swaps colours 0-127 with 128-255 for the bitplanes:
        dc.w    bplcon4,$8011
```

### Gotchas
- Reset value is 0: sprites then take colours 0-15. Write $0011 in every copper list.
- BPLAM is a bit flip, not an add: bit n swaps every block of 2^n colours with its neighbour.
- RandyAGA's bit list numbers this register backwards (ESPRM on bits 0-3); the AA spec
  layout above is the one the AGA doc tables and default $0011 agree with.

**See also:** BPLCON3, SPRxCTL, [sprites](../topics/sprites.md)

## CLXCON2
`$DFF10E` · write · Lisa · AGA · NDK `clxcon2`

Adds bitplanes 7 and 8 to collision detection.

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | - | write 0 |
| 7 | ENBP8 | include plane 8 (match required) |
| 6 | ENBP7 | include plane 7 (match required) |
| 5-2 | - | write 0 |
| 1 | MVBP8 | match value for plane 8 |
| 0 | MVBP7 | match value for plane 7 |

NDK: `clxcon2` (custom.i). Bit names are doc names. Results appear in CLXDAT as usual.

### Example
```asm
        lea     $dff000,a6
        move.w  #$0fc0,clxcon(a6)   ; planes 1-6 enabled, match 0 -- also clears CLXCON2
        move.w  #$00c0,clxcon2(a6)  ; then add planes 7+8, match 0
```

### Gotchas
- Every CLXCON write clears CLXCON2 (so old games collide correctly). Write CLXCON first.
- Solo's register PDF lists CLXCON2 at $10C; the NDK and the AA address list give $10E.

**See also:** BPLCON0

## FMODE
`$DFF1FC` · write · Alice + Lisa · AGA · NDK `fmode`

Chip RAM fetch width for bitplanes and sprites, plus scan-doubling enables.

| Bit | Name | Meaning |
|---|---|---|
| 15 | SSCAN2 | global sprite scan-doubling enable (per-sprite enable = SH10 in SPRxPOS) |
| 14 | BSCAN2 | bitplane scan-doubling: BPL1MOD/BPL2MOD alternate by line |
| 13-4 | - | write 0 |
| 3 | SPAGEM | sprite page mode (double CAS) |
| 2 | SPR32 | sprite 32-bit bus fetch |
| 1 | BPAGEM | bitplane page mode (double CAS) |
| 0 | BPL32 | bitplane 32-bit bus fetch |

| PAGEM | x32 | Fetch step | Memory cycle | Bus | Bandwidth |
|---|---|---|---|---|---|
| 0 | 0 | 2 bytes | normal CAS | 16 | 1x (OCS) |
| 0 | 1 | 4 bytes | normal CAS | 32 | 2x |
| 1 | 0 | 4 bytes | double CAS | 16 | 2x |
| 1 | 1 | 8 bytes | double CAS | 32 | 4x |

NDK: `fmode` (custom.i). Bit names are doc names. graphics/gfxbase.h describes the
machine's chip bus with the same bit values: `BUS_32` 1, `DBL_CAS` 2, `BANDWIDTH_1X` 0,
`BANDWIDTH_2XNML` 1, `BANDWIDTH_2XDBL` 2, `BANDWIDTH_4X` 3 (`GfxBase->MemType`); the OS keeps
its sprite setting in `GfxBase->SpriteFMode` / `SpriteWidth`.

### Example
```asm
        dc.w    fmode,$0000         ; 1x fetch: any OCS-style display, 8 lores planes
        ; high-bandwidth display (all planes 64-bit aligned, rows multiple of 64 bits):
        ; dc.w  fmode,$0003
```

### Gotchas
- The OS leaves FMODE non-zero after high-bandwidth or scan-doubled screens (DblPAL,
  productivity, superhires). OCS-style copper lists must write `fmode,0`.
- A wider fetch changes how many bytes each fetch consumes: bitplane rows and pointers
  must be aligned to the fetch size, DDFSTRT/DDFSTOP and modulos change. See the
  [FMODE and fetch topic](../topics/fmode-and-fetch.md).
- BSCAN2 makes both playfields share one modulo per line: dual playfield breaks.
- The AA spec table misspells bit 0 as BLP32; howtocode's "$01/$10/$11" values quoted in
  RandyAGA are binary for bits 1-0, not hex.

**See also:** BPLCON1, SPRxPOS, BPL1MOD, BPL2MOD, [FMODE and fetch](../topics/fmode-and-fetch.md)

## COLORxx
`$DFF180-$DFF1BE` · write · Lisa · AGA extension of OCS register · NDK `color` ($180)

32 addresses reaching all 256 24-bit entries via BANK, one nibble set at a time (LOCT).

| Write with | 15 | 14-12 | 11-8 | 7-4 | 3-0 |
|---|---|---|---|---|---|
| LOCT=0 | T | 0 | R7-R4 | G7-G4 | B7-B4 |
| LOCT=1 | 0 | 0 | R3-R0 | G3-G0 | B3-B0 |

xx = 00-31; entry = BANK*32 + xx (BANK in BPLCON3). T = genlock transparency bit (only
in the high set; see ZDCTEN in BPLCON2).

NDK: `color` EQU $180 (custom.i), `color[32]` (hardware/custom.h).

### Example
```asm
; copper: colour 200 = $123456 (200 = bank 6, register 8)
        dc.w    bplcon3,$cc00       ; BANK=110, PF2OF=011, LOCT=0
        dc.w    color+8*2,$0135     ; high nibbles R=1 G=3 B=5 (also copied to low)
        dc.w    bplcon3,$ce00       ; same bank, LOCT=1
        dc.w    color+8*2,$0246     ; low nibbles R=2 G=4 B=6
        dc.w    bplcon3,$0c00       ; back to bank 0, LOCT=0
```

### Gotchas
- Order matters: a LOCT=0 write overwrites the low nibbles with copies of the high ones.
  Always high, then low.
- A plain 12-bit OCS write gives each 8-bit gun nibble*$11 ($0F80 -> $FF8800): old code
  stays correct, but only 4096 of the colours are reachable that way.
- Write-only. Keep a 24-bit shadow palette in RAM.

**See also:** BPLCON3, [palette](../topics/palette.md)

## BPL7PTH, BPL7PTL
`$DFF0F8` / `$DFF0FA` · write · Alice · AGA · no NDK label (`bplpt+6*4`)

Chip RAM address of bitplane 7 data, reloaded every frame like the OCS plane pointers.

- **PTH** — high word of the address; **PTL** — low word. Load both from the copper.
- Used when BPU >= 7.

NDK: none per plane; `bplpt` EQU $0E0 (custom.i), `bplpt[8]` (hardware/custom.h).

### Example
```asm
        dc.w    bplpt+6*4,0         ; BPL7PTH, patched with plane 7 high word
        dc.w    bplpt+6*4+2,0       ; BPL7PTL, patched with plane 7 low word
```

### Gotchas
- Plane numbering is 1-based: plane 7 is `bplpt+(7-1)*4`.

**See also:** BPL8PTH, BPL8PTL, BPLCON0

## BPL8PTH, BPL8PTL
`$DFF0FC` / `$DFF0FE` · write · Alice · AGA · no NDK label (`bplpt+7*4`)

Chip RAM address of bitplane 8 data, reloaded every frame.

- **PTH** — high word; **PTL** — low word. Needed for 8-plane, HAM8 and 4+4 dual playfield.

NDK: none per plane; `bplpt` EQU $0E0 (custom.i).

### Example
```asm
        dc.w    bplpt+7*4,0         ; BPL8PTH
        dc.w    bplpt+7*4+2,0       ; BPL8PTL
```

**See also:** BPL7PTH, BPL7PTL, BPLCON0

## BPL7DAT, BPL8DAT
`$DFF11C` / `$DFF11E` · write · Lisa · AGA · normally DMA-loaded

Parallel-to-serial data buffers for planes 7 and 8 (16/32/64 bits per fetch).

- Loaded by bitplane DMA; the CPU or copper may write them. As on OCS, the conversion is
  triggered by the plane 1 buffer.

NDK: none per plane; `bpldat` EQU $110 (custom.i), `bpldat[8]` (hardware/custom.h).

**See also:** BPL7PTH, BPL7PTL, FMODE

## BPL1MOD, BPL2MOD
`$DFF108` / `$DFF10A` · write · Alice · AGA change with BSCAN2 · NDK `bpl1mod`, `bpl2mod`

With FMODE BSCAN2 the two modulos become per-line (primary/alternate) instead of odd/even.

- **BSCAN2=0** — OCS behaviour: BPL1MOD for odd planes, BPL2MOD for even planes.
- **BSCAN2=1** — lines whose vertical LSB matches DIWSTRT's use BPL1MOD, the other lines
  BPL2MOD; all planes share it.
- The modulo value depends on the fetch width; see the fetch topic.

NDK: `bpl1mod` $108, `bpl2mod` $10A (custom.i).

### Gotchas
- Scan-doubled OS screens own the modulos; a copper list that does not write both inherits
  the OS values. RandyAGA's fix list: always write $108, $10A, DIWSTRT and DIWSTOP.

**See also:** FMODE, [FMODE and fetch](../topics/fmode-and-fetch.md)

## SPRxPOS
`$DFF140+8x` · write · Alice + Lisa · AGA renamed bits · x = 0-7 · NDK `spr` (+`sd_pos`)

Sprite vertical start low 8 bits and horizontal start bits SH10-SH3.

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | SV7-SV0 | start line, low 8 bits (SV8, SV9 in SPRxCTL) |
| 7-0 | SH10-SH3 | horizontal start, 280ns steps (the OCS H8-H1); SH2-SH0 in SPRxCTL |

With FMODE SSCAN2=1, SH10 is not compared: it becomes this sprite's scan-double enable.

NDK: `spr` EQU $140, `sd_pos` 0, `sd_SIZEOF` 8 (custom.i). SVx/SHx are doc names.

### Gotchas
- Horizontal position is 11 bits in 35ns steps (lores pixel = 4). An OCS-style 9-bit
  lores position still puts its low bit into SPRxCTL bit 0 (SH2).

**See also:** SPRxCTL, FMODE, [sprites](../topics/sprites.md)

## SPRxCTL
`$DFF142+8x` · write · Alice + Lisa · AGA extension of OCS register · x = 0-7 · NDK `spr` (+`sd_ctl`)

Sprite end line, attach bit, and the extra vertical and 35ns horizontal position bits.

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | EV7-EV0 | stop line, low 8 bits |
| 7 | ATT | attach to the previous sprite (odd sprites) |
| 6 | SV9 | start line bit 9 (AGA) |
| 5 | EV9 | stop line bit 9 (AGA) |
| 4 | SH1 | horizontal start, 70ns bit (AGA) |
| 3 | SH0 | horizontal start, 35ns bit (AGA) |
| 2 | SV8 | start line bit 8 |
| 1 | EV8 | stop line bit 8 |
| 0 | SH2 | horizontal start, 140ns bit (the OCS SH0) |

H (35ns steps) = `SPRxPOS[7:0]<<3 | CTL0<<2 | CTL4<<1 | CTL3`.

NDK: `spr` EQU $140, `sd_ctl` 2 (custom.i). Bit names are doc names.

### Example
```c
/* control words for a sprite: x in 35ns steps (lores pixel = 4), lines 0-1023 */
static void spr_ctl(UWORD *cw, UWORD x, UWORD y, UWORD ystop, int att)
{
    cw[0] = (UWORD)(((y & 0xff) << 8) | ((x >> 3) & 0xff));
    cw[1] = (UWORD)(((ystop & 0xff) << 8) | (att ? 0x80 : 0)
          | (((y >> 9) & 1) << 6) | (((ystop >> 9) & 1) << 5)
          | (((x >> 1) & 1) << 4) | ((x & 1) << 3)
          | (((y >> 8) & 1) << 2) | (((ystop >> 8) & 1) << 1)
          | ((x >> 2) & 1));
}
```

### Gotchas
- Writing SPRxCTL disarms the sprite (as on OCS); writing SPRxDATA re-arms it.
- OCS code that leaves bits 6-3 at 0 still positions correctly, in 140ns steps.
- Scan-doubled sprites need start and stop lines of the same parity.

**See also:** SPRxPOS, BPLCON3, BPLCON4, [sprites](../topics/sprites.md)

## DIWSTRT, DIWSTOP
`$DFF08E` / `$DFF090` · write · Alice + Lisa · AGA renamed bits · NDK `diwstrt`, `diwstop`

Display window corners; on AGA the low byte holds H9-H2 and any write clears DIWHIGH.

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | V7-V0 | line, low 8 bits |
| 7-0 | H9-H2 | horizontal position in 140ns steps (the OCS H7-H0) |

Without DIWHIGH the OCS rules for the missing high bits still apply.

NDK: `diwstrt` $08E, `diwstop` $090 (custom.i); `DIW_HORIZ_POS`, `DIW_VRTCL_POS`,
`DIW_VRTCL_POS_SHIFT` (graphics/display.h).

### Gotchas
- A DIWSTRT or DIWSTOP write resets DIWHIGH (interlock inherited from ECS Denise).
  Write DIWHIGH after them, never before.

**See also:** DIWHIGH

## DIWHIGH
`$DFF1E4` · write · Alice + Lisa · ECS/AGA (H1, H0 AGA) · NDK `diwhigh`

High and 35ns bits for the display window, lifting the OCS start/stop restrictions.

| Bit | Name | Meaning |
|---|---|---|
| 15-14 | - | write 0 |
| 13 | H10 | stop, horizontal bit 10 |
| 12 | H1 | stop, 70ns bit |
| 11 | H0 | stop, 35ns bit |
| 10-8 | V10-V8 | stop line, bits 10-8 |
| 7-6 | - | write 0 |
| 5 | H10 | start, horizontal bit 10 |
| 4 | H1 | start, 70ns bit |
| 3 | H0 | start, 35ns bit |
| 2-0 | V10-V8 | start line, bits 10-8 |

Full horizontal position (35ns steps) = `H10<<10 | DIWxxxx[7:0]<<2 | H1<<1 | H0`.

NDK: `diwhigh` EQU $1e4 (custom.i). Bit names are doc names.

### Example
```asm
        dc.w    diwstrt,$2c81       ; PAL 320x256
        dc.w    diwstop,$2cc1
        dc.w    diwhigh,$2100       ; stop H10 + stop V8: same window, stated explicitly
```

### Gotchas
- Not writing DIWHIGH keeps the OCS behaviour; writing it switches to the explicit bits.
  A stale OS value survives only until your next DIWSTRT/DIWSTOP write.

**See also:** DIWSTRT, DIWSTOP

## HBSTRT, HBSTOP
`$DFF1C4` / `$DFF1C6` · write · Alice + Lisa · ECS register, AGA fine bits · NDK `hbstrt`, `hbstop`

Programmable horizontal blank start/stop; AGA adds a 35ns fine field in bits 10-8.

| Bit | Name | Meaning |
|---|---|---|
| 15-11 | - | write 0 |
| 10 | H2 | 140ns |
| 9 | H1 | 70ns |
| 8 | H0 | 35ns |
| 7-0 | H10-H3 | position in 280ns (colour clock) steps |

NDK: `hbstrt` $1c4, `hbstop` $1c6 (custom.i). Active only with the variable-beam bits in
BEAMCON0 (see the amiga-hardware skill).

**See also:** BEAMCON0

## BEAMCON0
`$DFF1DC` · write · Alice · ECS register, still decisive on AGA · NDK `beamcon0`

Beam counter mode: PAL/NTSC decode, variable sync/blank/beam enables and sync polarity.

| Bit | AA doc name | NDK name (value) | Meaning |
|---|---|---|---|
| 15 | - | - | write 0 |
| 14 | HARDDIS | - | disable hardwired window limits |
| 13 | LPENDIS | - | beam position reads ignore the light pen latch |
| 12 | VARVBEN | `VARVBLANK` ($1000) | VBSTRT/VBSTOP vertical blank |
| 11 | LOLDIS | `LOLDIS` ($0800) | no long/short line toggle |
| 10 | CSCBEN | `CSCBLANKEN` ($0400) | composite sync/blank redirected to HSY/VSY |
| 9 | VARVSYEN | `VARVSYNC` ($0200) | programmable VSYNC |
| 8 | VARHSYEN | `VARHSYNC` ($0100) | programmable HSYNC |
| 7 | VARBEAMEN | `VARBEAM` ($0080) | HTOTAL/VTOTAL beam counters |
| 6 | DUAL | `DISPLAYDUAL` ($0040) | UHRES dual beam counter |
| 5 | PAL | `DISPLAYPAL` ($0020) | PAL decodes |
| 4 | VARCSYEN | `VARCSYNC` ($0010) | programmable composite sync |
| 3 | (formerly BLANKEN) | `CSBLANK` ($0008) | composite blank out to CSY |
| 2 | CSYTRUE | `CSYNCTRUE` ($0004) | CSY polarity |
| 1 | VSYTRUE | `VSYNCTRUE` ($0002) | VSY polarity |
| 0 | HSYTRUE | `HSYNCTRUE` ($0001) | HSY polarity |

NDK: `beamcon0` (custom.i); flag names in hardware/custom.h under `#ifdef ECS_SPECIFIC`;
`STANDARD_PAL_BEAMCON` (`DISPLAYPAL`), `STANDARD_NTSC_BEAMCON` ($0000) in graphics/monitor.h.

### Example
```asm
        include "graphics/gfxbase.i"
        move.l  _GfxBase,a0
        moveq   #0,d0               ; NTSC decodes
        move.w  gb_DisplayFlags(a0),d1
        btst    #PALn,d1
        beq.s   .ntsc
        moveq   #$20,d0             ; DISPLAYPAL
.ntsc   lea     $dff000,a6
        move.w  d0,beamcon0(a6)     ; standard 15kHz beam, no variable timing
```

### Gotchas
- After DblPAL/DblNTSC, productivity or multiscan screens the variable-beam bits are set;
  a bare-metal 15kHz display must reset BEAMCON0 (and FMODE, DIWHIGH).
- Setting PAL on an NTSC machine (or clearing it on PAL) changes the refresh rate.
- The AA spec says bit 3 is unused; the NDK defines `CSBLANK` there and graphics'
  `SPECIAL_BEAMCON` sets it.

**See also:** FMODE, HBSTRT, HBSTOP, [fixing software](../topics/fixing-software.md)

## LISAID
`$DFF07C` · read · Lisa (Denise on ECS) · ECS/AGA · NDK `deniseid` (DENISEID)

Video chip ID: the low byte tells OCS Denise, ECS Denise and AGA Lisa apart.

| Bit | Meaning |
|---|---|
| 15-8 | loaded from the serial mouse bus, reserved: mask off |
| 7-4 | revision, counting down: $F = revision 0 |
| 3 | AA spec: "maintain as 1" |
| 2 | 0 = AA feature set (Lisa) |
| 1 | 0 = ECS feature set (ECS Denise or Lisa) |
| 0 | AA spec: "maintain as 1" |

| Chip | Low byte |
|---|---|
| OCS Denise 8362 | no register: leftover bus value, changes between reads |
| ECS Denise 8373 | $FC |
| Lisa (AGA) | $F8 |

NDK: `deniseid` EQU $07C (custom.i), `deniseid` field (hardware/custom.h).

### Example
```asm
        lea     $dff000,a6
        move.w  deniseid(a6),d0     ; word read: the ID is the LOW byte
        andi.w  #$00ff,d0
        ori.w   #$00f0,d0           ; ignore the revision nibble
        cmpi.w  #$00f8,d0           ; one read is not enough: see the detection topic
```

### Gotchas
- `cmpi.b #$f8,$dff07c` reads the high (mouse bus) byte, not the ID. Read the word.
- On OCS the value is random bus data that may match $F8 by chance: re-read ~30 times.
- Lisa ($F8) and ECS Denise ($FC) both have bit 0 = 0 despite the "maintain as 1" note.

**See also:** VPOSR, [detection](../topics/detection.md)

## VPOSR
`$DFF004` · read · Alice · Agnus/Alice ID bits · NDK `vposr`

Long-frame flag, Agnus/Alice chip ID, long-line flag and vertical beam bits 10-8.

| Bit | Name | Meaning |
|---|---|---|
| 15 | LOF | long frame (interlace) |
| 14-8 | I6-I0 | Agnus/Alice ID |
| 7 | LOL | long line; 0 = short line |
| 6-3 | - | unused |
| 2-0 | V10-V8 | vertical beam bits 10-8 (V9, V10 on ECS/AGA only) |

| Chip | ID (I6-I0) |
|---|---|
| 8367 / 8371 Agnus PAL | $00 |
| 8361 / 8370 Agnus NTSC | $10 |
| 8372 Fat Agnus (ECS) through rev 4 | $20 PAL, $30 NTSC |
| 8372 rev 5 | $22 PAL, $31 NTSC (as printed) |
| 8374 Alice through rev 2 | $22 PAL, $32 NTSC |
| 8374 Alice rev 3-4 | $23 PAL, $33 NTSC |

NDK: `vposr` $004 (custom.i); `VPOSRLOF` $8000 (graphics/display.h).

### Example
```c
#include <hardware/custom.h>
static UWORD agnus_id(void)
{
    struct Custom *custom = (struct Custom *)0xdff000;
    return (custom->vposr >> 8) & 0x7f;
}
```

### Gotchas
- The printed tables give $22 for both 8372 rev 5 PAL and early Alice PAL: do not use the
  Agnus ID alone to detect AGA. Use LISAID.
- Mask the vertical position with $0007 (V10-V8) when beam counters exceed 511 lines.

**See also:** LISAID, BEAMCON0
