# AGA sprites

AGA keeps the eight OCS hardware sprites (same data format, same SPRxPT/POS/CTL/DATA
registers) and adds: selectable sprite resolution, 35ns horizontal positioning, 10-bit
vertical positions, a 16-colour bank per even/odd sprite group, sprites in the border,
attached sprites in every mode, scan doubling and wider sprite fetches. OCS sprite basics
are in the amiga-hardware skill. Registers: [SPRxPOS](../registers/aga.md#sprxpos),
[SPRxCTL](../registers/aga.md#sprxctl), [BPLCON3](../registers/aga.md#bplcon3),
[BPLCON4](../registers/aga.md#bplcon4).

## Sprite resolution: SPRES (BPLCON3 bits 7-6)

| SPRES1-0 | Sprite pixel | NDK value (graphics/view.h) |
|---|---|---|
| 00 | ECS default: 140ns on lores and hires screens, 70ns on superhires | `SPRITERESN_ECS` 0 |
| 01 | 140ns (lores) on any screen | `SPRITERESN_140NS` 1 |
| 10 | 70ns (hires) on any screen | `SPRITERESN_70NS` 2 |
| 11 | 35ns (superhires) on any screen | `SPRITERESN_35NS` 3 |

- Applies to all eight sprites; independent of the bitplane resolution (35ns sprites on a
  lores screen, 140ns sprites on superhires).
- Keep PF2OF and the other BPLCON3 bits when you set it: lores screen with hires sprites =
  `bplcon3,$0c80`.
- Mode 01 is not the ECS default: on a superhires screen it gives 140ns, not 70ns.
- OS: `VTAG_SPRITERESN_SET` / `VTAG_DEFSPRITERESN_SET` (graphics/videocontrol.h).

## 35ns horizontal position

The start position is 11 bits in 35ns steps (one lores pixel = 4):

| Position bits | Register bits | Step |
|---|---|---|
| SH10-SH3 | SPRxPOS bits 7-0 | 280ns (OCS H8-H1) |
| SH2 | SPRxCTL bit 0 | 140ns (OCS H0) |
| SH1 | SPRxCTL bit 4 | 70ns |
| SH0 | SPRxCTL bit 3 | 35ns |

Vertical start/stop gain bit 9: SV9 = SPRxCTL bit 6, EV9 = bit 5 (SV8/EV8 stay in bits 2/1).

```asm
; MakeCtl -- d0.w = x (35ns steps, lores pixel = 4), d1.w = first line, d2.w = last line + 1
;            a0 -> sprite data block: writes the two control words. Trashes d3.
MakeCtl:
        move.w  d1,d3
        lsl.w   #8,d3               ; SV7-SV0
        move.w  d0,-(sp)
        lsr.w   #3,d0
        move.b  d0,d3               ; SH10-SH3
        move.w  (sp)+,d0
        move.w  d3,(a0)             ; SPRxPOS word
        move.w  d2,d3
        lsl.w   #8,d3               ; EV7-EV0, low byte now 0
        btst    #8,d1
        beq.s   .1
        bset    #2,d3               ; SV8
.1      btst    #9,d1
        beq.s   .2
        bset    #6,d3               ; SV9
.2      btst    #8,d2
        beq.s   .3
        bset    #1,d3               ; EV8
.3      btst    #9,d2
        beq.s   .4
        bset    #5,d3               ; EV9
.4      btst    #2,d0
        beq.s   .5
        bset    #0,d3               ; SH2 (140ns)
.5      btst    #1,d0
        beq.s   .6
        bset    #4,d3               ; SH1 (70ns)
.6      btst    #0,d0
        beq.s   .7
        bset    #3,d3               ; SH0 (35ns)
.7      move.w  d3,2(a0)            ; SPRxCTL word (ATT = 0)
        rts
```

- To move an OCS lores coordinate `x` to AGA: use `x*4`; the result is identical, and you
  can now add 1-3 for sub-pixel motion.
- Odd sprites used attached: set bit 7 of the second word after calling (ATT).

## Colour banks: BPLCON4 ESPRM / OSPRM

Sprite colour index = `base<<4 | (pair*4 + pixel)`, pair = sprite number / 2, pixel = 1-3
(0 is transparent):

| BPLCON4 field | Sprites | Default (OCS) |
|---|---|---|
| bits 7-4 ESPRM7-4 | 0, 2, 4, 6 | 0001 -> colours 16-31 |
| bits 3-0 OSPRM7-4 | 1, 3, 5, 7 | 0001 -> colours 16-31 |

- Sprite 2 pixel 3 with ESPRM = %0101: 80 + 4 + 3 = colour 87.
- Attached sprites (15 colours) take their colours from the **odd** base (OSPRM).
- Reset leaves BPLCON4 = 0: sprites use colours 0-15, i.e. the background. Always write it.
- Moving sprites off 16-31 frees those entries for 32-colour or 4+4 dual-playfield screens.
- OS: `VTAG_SPEVEN_BASE_SET`, `VTAG_SPODD_BASE_SET`.

```asm
        dc.w    bplcon4,$00ef       ; even sprites use 224-239, odd sprites 240-255
```

## Sprites in the border: BRDSPRT

BPLCON3 bit 1 lets sprites show outside the display window. It only works with ECSENA
(BPLCON0 bit 0) set.

```asm
        dc.w    bplcon0,$0211       ; 8 planes lores + ECSENA
        dc.w    bplcon3,$0c02       ; PF2OF=011 + BRDSPRT
```

OS: `VTAG_BORDERSPRITE_SET`; `DIPF_IS_SPRITES_BORDER` in the display database.

## Scan doubling: SSCAN2

- FMODE bit 15 enables sprite scan doubling globally; then SH10 (SPRxPOS bit 7) of each
  sprite is its own scan-double enable and no longer a position bit.
- Lisa repeats the previous line's sprite data on the alternate lines; only POS/CTL need
  changing, not the data.
- Start and stop lines must have the same parity.

## Wide sprite fetch: SPR32 / SPAGEM

- FMODE bits 2/3 fetch sprite data as 32 or 64 bits per word, like the bitplane bits. The
  OS tracks this as `GfxBase->SpriteFMode` and `GfxBase->SpriteWidth` ("current width in
  words of sprites").
- RandyAGA documents 32- and 64-bit layouts (control words in the high word of each long,
  data 64-bit aligned) -- unverified; no Commodore layout is in the source set.
- For normal 16-pixel sprites keep FMODE bits 3-2 at 0 and write `fmode` in your copper list.
- Unused sprites: point them at zero data. With wide fetches RandyAGA recommends four zero
  longwords on a 64-bit boundary; `$0` is not guaranteed to hold zeros.

## Sprites lost to an early bitplane fetch

Sprite DMA slots come at fixed positions early in each line; if DDFSTRT starts the
bitplane fetch before a sprite's slot, that sprite disappears. Wide fetch modes and fine
scrolling push the fetch start earlier. Details and measurements (sprite n at recorder
hpos $19+4n/$1B+4n; fetch at $34 loses sprite 7, at $24 loses sprites 3-7):
[FMODE and fetch](fmode-and-fetch.md#bitplane-dma-vs-sprite-dma-the-sprite-steal).

## Common mistakes

- BPLCON4 not written: sprites draw in colours 0-15 (reset value), or in whatever bank the
  OS left.
- Composing BPLCON3 for SPRES/BRDSPRT and wiping PF2OF/BANK/LOCT.
- BRDSPRT without ECSENA.
- Shifting an OCS position left by 3 into SPRxPOS and forgetting SH2 in SPRxCTL bit 0.
- SSCAN2 or SPR32 left on from an OS screen.
- Hardware sprites 4-7 with an early DDFSTRT.

**See also:** [FMODE and fetch](fmode-and-fetch.md), [bitplanes and modes](bitplanes-and-modes.md), [SPRxCTL](../registers/aga.md#sprxctl), [BPLCON4](../registers/aga.md#bplcon4)
