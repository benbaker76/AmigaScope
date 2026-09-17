# Detecting AGA

Decide "AGA or not" before touching any AGA register or opening a 256-colour display.
Two correct ways: read the Lisa ID register, or ask graphics.library. Register details:
[LISAID](../registers/aga.md#lisaid), [VPOSR](../registers/aga.md#vposr).

## Hardware way: LISAID ($DFF07C)

The low byte of `$DFF07C` identifies the video chip:

| Chip | Low byte | Bit 2 | Bit 1 |
|---|---|---|---|
| OCS Denise 8362 | not a register: whatever is left on the bus | random | random |
| ECS Denise 8373 | $FC (revision nibble may count down) | 1 | 0 = ECS |
| Lisa (AGA) | $F8 (revision nibble may count down) | 0 = AA | 0 |

Rules that make the test reliable (RandyAGA's routine, refined by DDT/HBT):

1. Read the **word** and mask `$00FF`. The high byte comes from the mouse serial bus.
2. Re-read it about 30 times; OCS Denise returns floating bus data that changes. Any
   difference = not AGA.
3. OR the revision nibble to `$F0` before comparing, so later Lisa revisions still match.
4. Compare with `$F8`.

```asm
        include "hardware/custom.i"
; IsAGA -- d0.l = 1 on AGA (Lisa), 0 otherwise. Trashes d1-d2/a0. No OS calls.
IsAGA:
        lea     $dff000,a0
        move.w  deniseid(a0),d0     ; $DFF07C, read as a WORD
        andi.w  #$00ff,d0
        moveq   #32-1,d2
.again  move.w  deniseid(a0),d1
        andi.w  #$00ff,d1
        cmp.w   d0,d1
        bne.s   .no                 ; value moves: OCS Denise floating bus
        dbf     d2,.again
        ori.w   #$00f0,d0           ; ignore revision (bits 7-4)
        cmpi.w  #$00f8,d0
        bne.s   .no
        moveq   #1,d0
        rts
.no     moveq   #0,d0
        rts
```

```c
#include <hardware/custom.h>

static int IsAGA(void)
{
    struct Custom *custom = (struct Custom *)0xdff000;
    UWORD first = custom->deniseid & 0xff;   /* volatile: every access re-reads */
    for (int i = 0; i < 32; i++)
        if ((custom->deniseid & 0xff) != first)
            return 0;
    return (first | 0xf0) == 0xf8;
}
```

Works without graphics.library (bootblocks, trackmos, WHDLoad slaves), in supervisor or
user mode.

## OS way: GfxBase->ChipRevBits0 (V39+)

graphics.library V39 records the chips it found and is using:

| Flag (graphics/gfxbase.h, .i) | Bit | Meaning |
|---|---|---|
| `GFXF_HR_AGNUS` (= `GFXF_BIG_BLITS`) | 0 | ECS Agnus |
| `GFXF_HR_DENISE` | 1 | ECS Denise |
| `GFXF_AA_ALICE` | 2 | Alice |
| `GFXF_AA_LISA` | 3 | Lisa |
| `GFXF_AA_MLISA` | 4 | internal use only |

```asm
        include "exec/libraries.i"
        include "graphics/gfxbase.i"
; a6 = GfxBase (already opened)
        cmpi.w  #39,LIB_VERSION(a6)
        blo.s   .noaga              ; older graphics: field has no AA bits (or no field)
        btst    #GFXB_AA_ALICE,gb_ChipRevBits0(a6)
        beq.s   .noaga
        btst    #GFXB_AA_LISA,gb_ChipRevBits0(a6)
        beq.s   .noaga
        ; ... AGA path ...
.noaga
```

```c
#include <graphics/gfxbase.h>
extern struct GfxBase *GfxBase;

BOOL aga = GfxBase->LibNode.lib_Version >= 39 &&
           (GfxBase->ChipRevBits0 & (GFXF_AA_ALICE | GFXF_AA_LISA)) ==
           (GFXF_AA_ALICE | GFXF_AA_LISA);
```

- In the 1.3 header layout (`#ifdef __KICK13__`) the same space is `reserved[23]`: check
  the library version before reading `ChipRevBits0`.
- `SetChipRev(SETCHIPREV_BEST)` (V39) asks graphics to enable the best chips present (the
  ULONG result is the resulting chip bits -- unverified, no autodoc in the source set); `SETCHIPREV_AA` = `GFXF_AA_ALICE|GFXF_AA_LISA|SETCHIPREV_ECS`.
- The OS bits say what graphics is *using*; the LISAID test says what is *fitted*. A
  machine booted with the chipset forced to "original" in the early startup menu can
  differ (unverified). For bare-metal code test LISAID; for OS displays trust the OS
  (and the display database, see [OS level](os-level.md)).

## What not to do

- **`cmpi.b #$f8,$dff07c`** -- a byte access reads the high byte (mouse bus bits), not the
  ID. Always read the word and mask the low byte.
- **One read only** -- OCS Denise can leave `$xxF8` on the bus by chance.
- **Exact `$F8` without masking the revision** -- a later Lisa revision returns `$E8` etc.
- **Testing bit 3 for AGA** -- RandyAGA's comment says "bit 3 = AGA"; the AA spec puts the
  AA flag in bit 2 (low = AA). Bit 3 is "keep 1".
- **Agnus ID alone** -- the printed VPOSR tables give $22 for both an 8372 rev 5 (ECS) and
  an early Alice on PAL.
- **Kickstart version or CPU type** -- Kickstart 3.x runs on OCS/ECS Amigas, and OCS
  machines are commonly fitted with 68020+ accelerators.
- **Reading `ChipRevBits0` on V33/V34** -- that memory is `reserved[]` in the 1.3 GfxBase.
- **Refusing to run on non-AGA without need** -- RandyAGA fixed several demos that insisted
  on AGA through a wrong test. If AGA is optional, keep an OCS path.

**See also:** [overview](overview.md), [fixing software](fixing-software.md), [LISAID](../registers/aga.md#lisaid)
