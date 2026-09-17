# AGA bitplanes and display modes

How to set up 7/8-plane, EHB/KILLEHB, HAM6/HAM8, superhires and 4+4 dual-playfield
displays on the bare metal, plus border and display-window control. Registers:
[BPLCON0](../registers/aga.md#bplcon0), [BPLCON2](../registers/aga.md#bplcon2),
[BPLCON3](../registers/aga.md#bplcon3), [DIWHIGH](../registers/aga.md#diwhigh).
For OCS basics (DIW/DDF, modulos, copper) see the amiga-hardware skill.

## Plane counts

The plane count is a 4-bit value BPU: bits 14-12 hold BPU2-BPU0, bit 4 holds BPU3.

| Planes | BPLCON0 lores (+COLOR) | Colours |
|---|---|---|
| 1 | $1200 | 2 |
| 2 | $2200 | 4 |
| 3 | $3200 | 8 |
| 4 | $4200 | 16 |
| 5 | $5200 | 32 |
| 6 | $6200 | EHB (32 + 32 half-bright), or 64 with KILLEHB |
| 7 | $7200 | 128 |
| 8 | $0210 | 256 |

Add $8000 for hires or $0040 for superhires, $0800 for HAM, $0400 for dual playfield,
$0001 (ECSENA) when you use the BPLCON3 border bits.

Minimum fetch bandwidth (AA mode tables; set with [FMODE](fmode-and-fetch.md)):

| Resolution | 1x (FMODE 0) | 2x | 4x |
|---|---|---|---|
| lores | 1-8 planes, HAM8, DPF | - | - |
| hires | 1-4 planes | 5-8 planes, HAM6, HAM8, EHB | - |
| superhires | 1-2 planes | 3-4 planes | 5-8 planes, HAM6, HAM8, EHB |
| productivity 640x480 | 1-2 planes | 3-4 planes | 5-8 planes |

The colour index of a pixel is plane 8..plane 1 as bits 7..0, XORed with BPLAM
(BPLCON4 bits 15-8, normally 0).

## EHB and KILLEHB

- EHB is active when BPU = 6, HAM = 0 and DPF = 0. Plane 6 set shows entry `pixel & 31` at
  half brightness. On AGA it also works in hires and superhires (V39 mode IDs
  `HIRESEHB_KEY`, `SUPEREHB_KEY` in graphics/modeid.h).
- KILLEHB (BPLCON2 bit 9) turns the same 6 planes into 64 palette entries.
- BPLCON2 is not reset by the OS for you: write the whole register, with bit 9 chosen.

```asm
        dc.w    bplcon0,$6200       ; 6 planes lores
        dc.w    bplcon2,$0224       ; KILLEHB: 64 colours (use $0024 for EHB)
```

## HAM6 and HAM8

HAM6 (BPU 6 + HAM): planes 6 and 5 are control, planes 4-1 data.

| Planes 6,5 | Action |
|---|---|
| 00 | colour = palette entry 0-15 (planes 4-1) |
| 01 | keep red, green; modify blue |
| 10 | modify red; keep green, blue |
| 11 | keep red, blue; modify green |

HAM8 (BPU 8 + HAM, BPLCON0 lores $0A10): planes 2 and 1 are control, planes 8-3 data.

| Planes 2,1 | Action |
|---|---|
| 00 | colour = palette entry 0-63 (planes 8-3) |
| 01 | modify blue: its top 6 bits = planes 8-3 |
| 10 | modify red |
| 11 | modify green |

- HAM8 reverses HAM6's layout: control is in the **low** planes. graphics.library hides
  this for OS rendering; bare-metal code must encode it.
- A modify never changes the 2 low bits of the gun: they come from the last base colour.
  Pick the 64 base colours with that in mind (a converter such as ADPro does).
- Only 64 base entries are used: load banks 0 and 1 (two BPLCON3 banks).
- HAM6 and HAM8 work in all three resolutions (hires HAM8 needs 2x, superhires 4x).

```c
/* HAM8 pixel values (0-255) */
#define HAM8_BASE(i)    ((UBYTE)((i) << 2))         /* palette entry 0-63 */
#define HAM8_BLUE(v6)   ((UBYTE)(((v6) << 2) | 1))  /* v6 = new top 6 bits of the gun */
#define HAM8_RED(v6)    ((UBYTE)(((v6) << 2) | 2))
#define HAM8_GREEN(v6)  ((UBYTE)(((v6) << 2) | 3))

/* store an 8-bit value into 8 separate planes, bytes per row = bpr */
static void put8(UBYTE **plane, int bpr, int x, int y, UBYTE v)
{
    ULONG off = (ULONG)y * bpr + (x >> 3);
    UBYTE bit = (UBYTE)(0x80 >> (x & 7));
    for (int p = 0; p < 8; p++, v >>= 1) {
        if (v & 1) plane[p][off] |= bit;
        else       plane[p][off] &= (UBYTE)~bit;
    }
}
```

## Superhires (SHRES, 35ns pixels)

- BPLCON0 bit 6 ($0040), HIRES bit clear. 1280 pixels across the width of a 320 lores
  screen.
- ECS superhires needed "scrambled" colour table entries; on AGA every plane count uses
  the palette directly ("no colour fudging"), so load it normally.
- Above 2 planes it needs FMODE bandwidth and fetch-aligned bitplanes.
- Sprite pixels default to 70ns on a superhires screen (SPRES = 00); choose with SPRES.

## Dual playfield 4+4

- DPF (BPLCON0 bit 10) with BPU up to 8: PF1 = planes 1, 3, 5, 7; PF2 = planes 2, 4, 6, 8.
  8 planes lores DPF = $0610.
- PF1 uses entries 0-15. PF2 uses its pixel value plus the PF2OF offset (BPLCON3 bits
  12-10); value 0 is transparent.
- The OCS offset 8 (PF2OF=011, the $0C00 value) overlaps PF1's entries 8-15 as soon as PF1
  has 4 planes. Use PF2OF=100 (16) and, if sprites are used, move them off 16-31:

```asm
        dc.w    bplcon0,$0610       ; 4+4 dual playfield lores
        dc.w    bplcon2,$0024       ; PF1 in front, sprites in front of both
        dc.w    bplcon3,$1000       ; PF2OF=100: PF2 uses entries 16-31
        dc.w    bplcon4,$0022       ; sprites use 32-47 (even and odd banks = 2)
        dc.w    bplcon1,$0000       ; separate 8-bit scroll per playfield
```

- Scan doubling (FMODE BSCAN2) shares one modulo between both playfields: the OS has no
  scan-doubled dual-playfield modes (graphics/modeid.h), and you should not use it either.
- OS-level equivalents: `VTAG_PF1_BASE_SET`, `VTAG_PF2_BASE_SET` (see [OS level](os-level.md)).

## Border: blank, opaque, sprites

All three need ECSENA (BPLCON0 bit 0) or Lisa ignores them.

| BPLCON3 bit | Effect |
|---|---|
| 5 BRDRBLNK | border shown black (blanked) instead of COLOR00 |
| 4 BRDNTRAN | border opaque to a genlock (ZD low) |
| 1 BRDSPRT | sprites visible outside the display window |

```asm
        dc.w    bplcon0,$0211       ; 8 planes lores + ECSENA
        dc.w    bplcon3,$0c22       ; PF2OF=011, BRDRBLNK + BRDSPRT
```

Toggling ECSENA off in a later viewport masks these bits; turning it on again restores
them.

## Display window with DIWHIGH

DIWHIGH supplies the bits OCS implied: vertical bits 10-8 and horizontal bit 10 for both
corners, plus the 70ns/35ns horizontal bits. Write it **after** DIWSTRT and DIWSTOP
(either write clears DIWHIGH).

```c
/* h in 35ns steps (lores pixel = 4), v in lines */
static void set_diw(UWORD *strt, UWORD *stop, UWORD *high,
                    UWORD hstart, UWORD vstart, UWORD hstop, UWORD vstop)
{
    *strt = (UWORD)(((vstart & 0xff) << 8) | ((hstart >> 2) & 0xff));
    *stop = (UWORD)(((vstop & 0xff) << 8) | ((hstop >> 2) & 0xff));
    *high = (UWORD)((((hstop >> 10) & 1) << 13) | (((hstop >> 1) & 1) << 12)
          | ((hstop & 1) << 11) | (((vstop >> 8) & 7) << 8)
          | (((hstart >> 10) & 1) << 5) | (((hstart >> 1) & 1) << 4)
          | ((hstart & 1) << 3) | ((vstart >> 8) & 7));
}
/* PAL 320x256: hstart $81*4, vstart $2c, hstop $1c1*4, vstop $12c
   -> DIWSTRT $2c81, DIWSTOP $2cc1, DIWHIGH $2100 */
```

## Full example: 320x256, 8 planes, lores, PAL

Run after [AGA detection](detection.md) and after taking over the display (the takeover
and restore sequence is in the amiga-hardware and amiga-os skills).

```asm
        include "exec/memory.i"
        include "lvo/exec_lib.i"
        include "hardware/custom.i"
        include "hardware/dmabits.i"
        include "graphics/gfxbase.i"

W       EQU     320
H       EQU     256
PLANESZ EQU     (W/8)*H             ; 10240 bytes per plane

; in: _GfxBase opened. out: d0 = 0 if out of chip RAM
Show8:
        move.l  4.w,a6
        move.l  #PLANESZ*8,d0
        move.l  #MEMF_CHIP!MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        move.l  d0,PlaneMem
        beq.s   .out
        lea     CopPlanes+2,a0      ; value word of BPL1PTH
        moveq   #8-1,d1
.ptr    swap    d0
        move.w  d0,(a0)             ; BPLxPTH value
        swap    d0
        move.w  d0,4(a0)            ; BPLxPTL value
        addi.l  #PLANESZ,d0
        addq.l  #8,a0
        dbf     d1,.ptr
        lea     Palette,a0          ; 256 x ULONG $00RRGGBB
        lea     CopPalette,a1
        bsr     CopPal256           ; palette topic
        move.l  _GfxBase,a0
        moveq   #0,d1
        move.w  gb_DisplayFlags(a0),d0
        btst    #PALn,d0
        beq.s   .ntsc
        moveq   #$20,d1             ; DISPLAYPAL
.ntsc   lea     $dff000,a6
        move.w  #$7fff,dmacon(a6)   ; all DMA off (sprites stay off)
        move.w  d1,beamcon0(a6)     ; plain 15kHz beam
        move.l  #Copper,cop1lc(a6)
        move.w  d0,copjmp1(a6)      ; strobe (any value; never CLR a strobe)
        move.w  #DMAF_SETCLR!DMAF_MASTER!DMAF_RASTER!DMAF_COPPER,dmacon(a6)
        moveq   #1,d0
.out    rts

        section chipdata,data_c
Copper:
        dc.w    fmode,$0000         ; 1x fetch: enough for 8 lores planes
        dc.w    diwstrt,$2c81
        dc.w    diwstop,$2cc1
        dc.w    diwhigh,$2100       ; after DIWSTRT/DIWSTOP
        dc.w    ddfstrt,$0038
        dc.w    ddfstop,$00d0
        dc.w    bplcon0,$0210       ; 8 planes lores + COLOR
        dc.w    bplcon1,$0000
        dc.w    bplcon2,$0024
        dc.w    bplcon3,$0c00
        dc.w    bplcon4,$0011
        dc.w    bpl1mod,$0000
        dc.w    bpl2mod,$0000
CopPlanes:
        dc.w    bplpt+$00,0,bplpt+$02,0
        dc.w    bplpt+$04,0,bplpt+$06,0
        dc.w    bplpt+$08,0,bplpt+$0a,0
        dc.w    bplpt+$0c,0,bplpt+$0e,0
        dc.w    bplpt+$10,0,bplpt+$12,0
        dc.w    bplpt+$14,0,bplpt+$16,0
        dc.w    bplpt+$18,0,bplpt+$1a,0
        dc.w    bplpt+$1c,0,bplpt+$1e,0
CopPalette:
        dcb.w   529*2,0             ; 529 MOVEs written by CopPal256 (~10 lines of vblank)
        dc.w    $ffff,$fffe

        section bss,bss
PlaneMem:
        ds.l    1
```

Free with `FreeMem(PlaneMem, PLANESZ*8)` after restoring the OS copper list.

## Common mistakes

- 8 planes as `8<<12`: that is the HIRES bit. Use $0010 (BPU3) with bits 14-12 clear.
- 6-plane pictures in the wrong mode: EHB when you wanted 64 colours (set KILLEHB) or 64
  colours when the picture is EHB (clear it).
- HAM8 data in planes 5-8 like HAM6: HAM8 control is planes 1-2.
- 4+4 dual playfield with the OCS PF2OF (8): PF2 overwrites PF1's upper 8 colours.
- DIWHIGH written before DIWSTRT/DIWSTOP: it is cleared again.
- Border bits without ECSENA: nothing happens.
- Hires above 4 planes or superhires above 2 planes with FMODE 0: the extra planes are not
  fetched correctly. See [FMODE and fetch](fmode-and-fetch.md).

**See also:** [palette](palette.md), [FMODE and fetch](fmode-and-fetch.md), [sprites](sprites.md), [BPLCON0](../registers/aga.md#bplcon0)
