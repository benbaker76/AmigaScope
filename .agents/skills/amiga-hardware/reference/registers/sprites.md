# Custom chips: sprite and collision registers

Eight hardware sprites, 16 pixels wide, 3 colours + transparent each (15 colours when an
even/odd pair is attached). Sprite DMA reads a data list per sprite from chip RAM:

```text
SPRxPOS word, SPRxCTL word      ; position + control (first two words)
DATA word, DATB word            ; one pair per displayed line
...
DATA word, DATB word
next POS, next CTL              ; reuse the sprite lower down (VSTART > previous VSTOP)
...
0, 0                            ; end: sprite unused for the rest of the frame
```

## SPRxPTH, SPRxPTL
`$DFF120`-`$DFF13E` · write · Agnus · OCS (high word: 3 address bits OCS, 5 ECS) · pointer pairs, x = 0-7

Chip-RAM address of sprite x's data list; reload it every vertical blank.

| x | SPRxPTH | SPRxPTL |
|---|---|---|
| 0 | `$DFF120` | `$DFF122` |
| 1 | `$DFF124` | `$DFF126` |
| 2 | `$DFF128` | `$DFF12A` |
| 3 | `$DFF12C` | `$DFF12E` |
| 4 | `$DFF130` | `$DFF132` |
| 5 | `$DFF134` | `$DFF136` |
| 6 | `$DFF138` | `$DFF13A` |
| 7 | `$DFF13C` | `$DFF13E` |

NDK: `sprpt` (custom.i, `sprpt+x*4`); C `custom->sprpt[x]`.

### Example
```asm
CopSpr: dc.w    sprpt+0,0,sprpt+2,0             ; sprite 0, patched at run time
        dc.w    sprpt+4,0,sprpt+6,0             ; sprite 1 ... repeat for 2-7

        section sprites,data_c
Ship:   dc.w    $6d60,$7200                     ; VSTART $6D, HSTART $C0, VSTOP $72
        dc.w    $0990,$07e0                     ; line 1: DATA, DATB
        ; ... 4 more lines
        dc.w    0,0                             ; end of sprite
NullSpr:dc.l    0                               ; for unused sprite channels
```

### Gotchas
- SPREN enables DMA for all 8 sprites: every pointer must point at a real sprite or a
  null list (`dc.l 0`), or garbage sprites appear.
- Chip RAM, word aligned.
- DDFSTRT below `$38` (overscan, horizontal scroll) makes the highest sprites unusable.
- The OS uses sprite 0 as the mouse pointer.

**See also:** SPRxPOS, SPRxCTL, [DMACON](dma-beam.md#dmacon), [DDFSTRT](playfield.md#ddfstrt)

## SPRxPOS
`$DFF140 + x*8` · write · Agnus + Denise · OCS · normally loaded by sprite DMA, x = 0-7

Sprite x vertical start (low 8 bits) and horizontal start (high 8 bits).

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | SV7-SV0 | VSTART low 8 bits (SV8 in SPRxCTL) |
| 7-0 | SH8-SH1 | HSTART high 8 bits (SH0 in SPRxCTL) |

Addresses: SPR0POS `$DFF140`, SPR1POS `$148`, SPR2POS `$150`, SPR3POS `$158`,
SPR4POS `$160`, SPR5POS `$168`, SPR6POS `$170`, SPR7POS `$178`.

Positions are lores non-interlaced beam coordinates, whatever the playfield mode;
VSTART uses the same line numbers as DIWSTRT (the HRM example sprite at line 65 of a
`$2C81` window has VSTART `$2C + 65 = $6D`).

NDK: `spr` (custom.i) + `sd_pos` (`spr+x*sd_SIZEOF+sd_pos`, `sd_SIZEOF` = 8);
C `custom->spr[x].pos`.

### Gotchas
- A CPU write to SPRxPOS moves the sprite horizontally at once, even under DMA.
- HSTART equal to the DIWSTRT horizontal value minus 1 lines the sprite up with the
  window's left edge (unverified).
- AGA moves SH2-SH0 into SPRxCTL and reuses SH10 for scan doubling: see the amiga-aga skill.

**See also:** SPRxCTL, [DIWSTRT](playfield.md#diwstrt), [BPLCON2](playfield.md#bplcon2)

## SPRxCTL
`$DFF142 + x*8` · write · Agnus + Denise · OCS (ECS bits 4-3) · writing disarms the sprite, x = 0-7

Sprite x vertical stop, attach flag and the high/low position bits.

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | EV7-EV0 | VSTOP low 8 bits (first line NOT drawn) |
| 7 | ATT | attach: set in the odd sprite of a pair for 15 colours |
| 6-5 | -- | write 0 on OCS/ECS |
| 4 | SHSH1 | ECS: superhires 70 ns horizontal step (SHRES screens only) |
| 3 | SHSH0 | ECS: 35 ns step (unimplemented), write 0 |
| 2 | SV8 | VSTART bit 8 |
| 1 | EV8 | VSTOP bit 8 |
| 0 | SH0 | HSTART bit 0 |

Addresses: SPR0CTL `$DFF142`, SPR1CTL `$14A`, SPR2CTL `$152`, SPR3CTL `$15A`,
SPR4CTL `$162`, SPR5CTL `$16A`, SPR6CTL `$172`, SPR7CTL `$17A`. AGA adds SV9, EV9 (bits
6-5) and SH1/SH0 (bits 4-3): see the amiga-aga skill.

NDK: `spr` + `sd_ctl` (custom.i); C `custom->spr[x].ctl`.

### Example
```c
/* x = HSTART (0-511), y = VSTART (0-511), h = height in lines */
static void SpriteHeader(UWORD *spr, UWORD x, UWORD y, UWORD h, int attach)
{
    UWORD ystop = y + h;
    spr[0] = (UWORD)(((y & 0xff) << 8) | ((x >> 1) & 0xff));          /* SPRxPOS */
    spr[1] = (UWORD)(((ystop & 0xff) << 8) | (attach ? 0x80 : 0)
                     | ((y >> 8) & 1) << 2 | ((ystop >> 8) & 1) << 1
                     | (x & 1));                                     /* SPRxCTL */
}
```

### Gotchas
- VSTOP - VSTART = number of lines, and the data list must hold exactly that many pairs.
- ATT goes in the odd sprite only; keep both sprites at the same position or the
  colours break up.
- A CPU write to SPRxCTL turns the sprite off until SPRxDATA is written again.
- ECS 70 ns positioning is only valid on superhires screens.

**See also:** SPRxPOS, SPRxDATA, SPRxDATB

## SPRxDATA
`$DFF144 + x*8` · write · Denise · OCS · normally loaded by sprite DMA; writing arms the sprite, x = 0-7

Low-order colour bit of the 16 pixels of the current sprite line (MSB = leftmost).

| DATB bit | DATA bit | Single sprite colour |
|---|---|---|
| 0 | 0 | transparent |
| 0 | 1 | COLOR17 + 4*(x/2) |
| 1 | 0 | COLOR18 + 4*(x/2) |
| 1 | 1 | COLOR19 + 4*(x/2) |

Attached pair (odd sprite bits are the high two): 4-bit value n gives COLOR(16+n),
0 = transparent. Addresses: SPR0DATA `$DFF144`, `$14C`, `$154`, `$15C`, `$164`, `$16C`,
`$174`, SPR7DATA `$17C`.

NDK: `spr` + `sd_dataa` (custom.i); C `custom->spr[x].dataa`.

### Gotchas
- Manual (non-DMA) sprites: write SPRxPOS/SPRxCTL, then SPRxDATB, then SPRxDATA last;
  the same data repeats on every line until changed (a vertical bar).
- In the DMA list the DATA word comes first in each pair.

**See also:** SPRxDATB, SPRxCTL, [COLORxx](playfield.md#colorxx)

## SPRxDATB
`$DFF146 + x*8` · write · Denise · OCS · normally loaded by sprite DMA, x = 0-7

High-order colour bit of the 16 pixels of the current sprite line (MSB = leftmost).

Colour table under SPRxDATA. Addresses: SPR0DATB `$DFF146`, `$14E`, `$156`, `$15E`,
`$166`, `$16E`, `$176`, SPR7DATB `$17E`.

NDK: `spr` + `sd_dataB` (custom.i; note the capital B); C `custom->spr[x].datab`.

**See also:** SPRxDATA

## CLXCON
`$DFF098` · write · Denise · OCS

Select the bitplanes, match values and odd sprites used for collision detection.

| Bit | Name | Meaning |
|---|---|---|
| 15 | ENSP7 | include sprite 7 (ORed with sprite 6) |
| 14 | ENSP5 | include sprite 5 (ORed with sprite 4) |
| 13 | ENSP3 | include sprite 3 (ORed with sprite 2) |
| 12 | ENSP1 | include sprite 1 (ORed with sprite 0) |
| 11-6 | ENBP6-ENBP1 | include bitplane 6-1 in the match |
| 5-0 | MVBP6-MVBP1 | value bitplane 6-1 must have for a collision |

AGA: writing CLXCON also clears CLXCON2 (planes 7-8): see the amiga-aga skill.

NDK: `clxcon` (custom.i); no bit constants; C `custom->clxcon`.

### Example
```asm
        move.w  #$0041,clxcon(a6)               ; ENBP1 + MVBP1: pixels with plane 1 set
```

### Gotchas
- Even sprites are always included; odd sprites only via ENSPx.
- Excluded planes always "match": with all ENBP bits 0, every sprite/playfield bit in
  CLXDAT fires continuously.
- Write-only.

**See also:** CLXDAT, [BPLCON2](playfield.md#bplcon2)

## CLXDAT
`$DFF00E` · read (clears on read) · Denise · OCS

Collision flags since the last read; reading clears the register.

| Bit | Collision |
|---|---|
| 15 | unused |
| 14 | sprite 4/5 - sprite 6/7 |
| 13 | sprite 2/3 - sprite 6/7 |
| 12 | sprite 2/3 - sprite 4/5 |
| 11 | sprite 0/1 - sprite 6/7 |
| 10 | sprite 0/1 - sprite 4/5 |
| 9 | sprite 0/1 - sprite 2/3 |
| 8 | even planes (PF2) - sprite 6/7 |
| 7 | even planes (PF2) - sprite 4/5 |
| 6 | even planes (PF2) - sprite 2/3 |
| 5 | even planes (PF2) - sprite 0/1 |
| 4 | odd planes (PF1) - sprite 6/7 |
| 3 | odd planes (PF1) - sprite 4/5 |
| 2 | odd planes (PF1) - sprite 2/3 |
| 1 | odd planes (PF1) - sprite 0/1 |
| 0 | odd planes (PF1) - even planes (PF2) |

NDK: `clxdat` (custom.i); C `custom->clxdat`.

### Example
```asm
        move.w  clxdat(a6),d0                   ; read ONCE per frame (clears it)
        btst    #1,d0                           ; sprite 0/1 hit playfield 1?
        bne.s   Hit
```

### Gotchas
- Read once, keep the value, test the copy: a second read returns the collisions since
  the first.
- "Odd/even planes" means the plane bits themselves, in single- and dual-playfield mode
  alike, filtered by CLXCON.
- "(or 1)"-style odd sprites count only if enabled in CLXCON.

**See also:** CLXCON, [INTREQ](interrupts.md#intreq)
