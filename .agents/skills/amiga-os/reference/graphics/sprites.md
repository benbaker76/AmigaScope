# graphics.library: hardware sprites

The simple sprite machine hands out the 8 hardware sprites to programs so they can share them with
Intuition (sprite 0 is normally the mouse pointer) and the VSprite system. Workflow:
[GetSprite](#getsprite) (reserve a number) -> [ChangeSprite](#changesprite) (attach a chip-RAM
image) -> [MoveSprite](#movesprite) as often as needed -> [FreeSprite](#freesprite). V39 adds
ExtSprites: [AllocSpriteDataA](#allocspritedataa) converts a BitMap into sprite data (any width the
chips allow, scaling), [GetExtSpriteA](#getextspritea) reserves a sprite for it and
[ChangeExtSpriteA](#changeextspritea) swaps images; an ExtSprite starts with a `struct SimpleSprite`
(`es_SimpleSprite`), so MoveSprite/FreeSprite work on it too. Colours: sprites 0/1 use colour
registers 17-19, 2/3 21-23, 4/5 25-27, 6/7 29-31 (V39 VideoControl `VTAG_SPODD_BASE_SET`/
`VTAG_SPEVEN_BASE_SET` can move them on AGA). Struct: `SimpleSprite` = `posctldata`, `height`,
`x`, `y`, `num` (asm `ss_posctldata` ... `ss_num`, `ss_SIZEOF`); ExtSprite size label in asm is
`ExtSprite_SIZEOF`.

## GetSprite
`WORD GetSprite(struct SimpleSprite *sprite, LONG num)` — LVO -408 (-$198)
Registers: sprite=A0, num=D0; result in D0

Reserve one of the 8 hardware sprites for the simple sprite machine.

- **sprite** — your `struct SimpleSprite`; `num` is filled in (or set to -1 on failure).
- **num** — 0-7 for a specific sprite, -1 for the first free one (search starts at 0).
- **Result** — the sprite number, or -1 if that sprite (or any, for -1) is taken.

### Example
```asm
; reserve any sprite, attach a 7-line image and place it at (100,60)
; in: a0 = ViewPort   out: d0 = sprite number or -1
ShowSprite:
        movem.l a2-a3/a6,-(sp)
        move.l  a0,a3
        move.l  _GfxBase,a6
        lea     MySprite,a0
        moveq   #-1,d0                  ; any free sprite
        jsr     _LVOGetSprite(a6)
        tst.w   d0
        bmi.s   .out                    ; -1: none free
        move.l  a3,a0
        lea     MySprite,a1
        lea     SpriteImage,a2          ; chip RAM (data_c section)
        jsr     _LVOChangeSprite(a6)
        move.l  a3,a0
        lea     MySprite,a1
        moveq   #100,d0
        moveq   #60,d1
        jsr     _LVOMoveSprite(a6)
        move.w  MySprite+ss_num,d0
        ext.l   d0
.out:   movem.l (sp)+,a2-a3/a6
        rts

        section spritestruct,data
MySprite:                               ; struct SimpleSprite
        dc.l    SpriteImage             ; ss_posctldata
        dc.w    7                       ; ss_height: set BEFORE ChangeSprite
        dc.w    0,0                     ; ss_x, ss_y
        dc.w    -1                      ; ss_num

        section spritedata,data_c       ; hardware reads it: chip RAM
SpriteImage:
        dc.w    0,0                     ; posctl, filled in by graphics
        dc.w    $8000,$8000
        dc.w    $c000,$4000
        dc.w    $e000,$a000
        dc.w    $f000,$5000
        dc.w    $f800,$f800
        dc.w    $1800,$1800
        dc.w    $0800,$0800
        dc.w    0,0                     ; end of sprite
```

### Gotchas
- Sprite 0 normally belongs to the Intuition pointer, so asking for 0 explicitly may fail; use -1.
- For a 15-colour attached pair reserve both sprites of a pair (n even, n+1) and set
  `SPRITE_ATTACHED` (`$80`, graphics/sprite.h; no asm equivalent) in `posctl[1]` of the odd one
  after ChangeSprite.
- The VSprite system may take sprites you did not reserve; see [GELs](gels.md#addvsprite).

**See also:** [ChangeSprite](#changesprite), [MoveSprite](#movesprite), [FreeSprite](#freesprite),
[GetExtSpriteA](#getextspritea)

## FreeSprite
`VOID FreeSprite(LONG num)` — LVO -414 (-$19E)
Registers: num=D0; no result

Return a sprite number to the pool for other programs and the VSprite system.

- **num** — 0-7, a sprite you reserved with [GetSprite](#getsprite) or
  [GetExtSpriteA](#getextspritea).

### Gotchas
- Never free a sprite you do not own (the pointer sprite, other programs' sprites).
- The image memory may still be displayed until the copper list is rebuilt; wait at least a frame
  (`WaitTOF()`) before freeing it (unverified how many frames are strictly needed).

**See also:** [GetSprite](#getsprite), [FreeSpriteData](#freespritedata)

## ChangeSprite
`VOID ChangeSprite(struct ViewPort *vp, struct SimpleSprite *sprite, UWORD *newData)` — LVO -420 (-$1A4)
Registers: vp=A0, sprite=A1, newData=A2; no result

Point a reserved simple sprite at a new chip-RAM image.

- **vp** — ViewPort the sprite is relative to, or NULL for relative to the View.
- **sprite** — the SimpleSprite from [GetSprite](#getsprite); `height` must already match the
  new image.
- **newData** — image in chip RAM: 2 WORDs `posctl` (used by graphics), then `height` x 2 WORDs
  (plane 0 word, plane 1 word per line), then 2 WORDs `0,0` you must provide.

### Example
```c
#include <exec/memory.h>

#define ARROW_H 4
static const UWORD arrow_src[2 + ARROW_H * 2 + 2] = {
    0x0000, 0x0000,                 /* posctl: filled in by graphics */
    0xC000, 0x4000,
    0xF000, 0x3000,
    0x7C00, 0x0C00,
    0x3000, 0x3000,
    0x0000, 0x0000                  /* terminator */
};
static struct SimpleSprite arrow;
static UWORD *arrow_chip;

BOOL show_arrow(struct ViewPort *vp, WORD x, WORD y)
{
    arrow_chip = AllocMem(sizeof(arrow_src), MEMF_CHIP);   /* sprite data: chip RAM */
    if (!arrow_chip)
        return FALSE;
    CopyMem((APTR)arrow_src, arrow_chip, sizeof(arrow_src));
    arrow.height = ARROW_H;                                /* before ChangeSprite */
    if (GetSprite(&arrow, -1) < 0) {
        FreeMem(arrow_chip, sizeof(arrow_src));
        return FALSE;
    }
    ChangeSprite(vp, &arrow, arrow_chip);
    MoveSprite(vp, &arrow, x, y);
    return TRUE;
}

void hide_arrow(void)
{
    FreeSprite(arrow.num);
    WaitTOF();
    WaitTOF();                      /* let the copper stop using the image */
    FreeMem(arrow_chip, sizeof(arrow_src));
}
```

### Gotchas
- Image data in fast RAM shows garbage: sprites are fetched by DMA from chip RAM only.
- Set `sprite->height` BEFORE the call.
- More than 8 moving objects: use VSprites ([AddVSprite](gels.md#addvsprite)).

**See also:** [GetSprite](#getsprite), [MoveSprite](#movesprite), [ChangeExtSpriteA](#changeextspritea)

## MoveSprite
`VOID MoveSprite(struct ViewPort *vp, struct SimpleSprite *sprite, LONG x, LONG y)` — LVO -426 (-$1AA)
Registers: vp=A0, sprite=A1, x=D0, y=D1; no result

Move a simple (or Ext) sprite to x,y relative to a ViewPort or the View.

- **vp** — ViewPort the coordinates are relative to, or NULL for the View.
- **sprite** — reserved SimpleSprite (or `&ext->es_SimpleSprite`).
- **x**, **y** — new position; graphics computes the posctl words, shown from the next frame.

### Gotchas
- BUGS: a SimpleSprite appears one pixel left of the requested position (the stored `x` is still
  what you passed). ExtSprites are not affected.
- The change takes effect at the next display frame; calling it more than once per frame only
  shows the last position.

**See also:** [ChangeSprite](#changesprite), [GetSprite](#getsprite)

## AllocSpriteDataA
`struct ExtSprite * AllocSpriteDataA(CONST struct BitMap *bm, CONST struct TagItem *tags)` — LVO -1020 (-$3FC)
Registers: bm=A2, tags=A1; result in D0

Allocate an ExtSprite and convert BitMap data into sprite format (optionally scaled).

- **bm** — source BitMap (planes 0 and 1 are used; need not be chip RAM).
- **tags** — `SPRITEA_Width` (`$81000000`, pixels, default 16; too wide for the hardware = fail),
  `SPRITEA_XReplication` (`$81000002`: 0 = 1:1, 1 = each pixel x2, 2 = x4, -1 = skip every other
  pixel, -2 = take every 4th; default 0), `SPRITEA_YReplication` (`$81000004`, same for lines),
  `SPRITEA_OutputHeight` (`$81000006`, default bitmap height; bitmap must be at least this tall),
  `SPRITEA_Attached` (`$81000008`: build the second sprite of an attached pair from planes 2 and
  3), `SPRITEA_OldDataFormat` (`$8100000a`, header only; requires `SPRITEA_OutputHeight`).
- **Result** — `struct ExtSprite *`, or NULL. Free with [FreeSpriteData](#freespritedata).

Since V39.

### Example
```c
/* build an ExtSprite from a 16x16 BitMap, show it on a screen's ViewPort */
struct ExtSprite *show_ext(struct ViewPort *vp, struct BitMap *bm)
{
    struct ExtSprite *es = AllocSpriteData(bm, SPRITEA_Width, 16,
                                           SPRITEA_OutputHeight, 16, TAG_END);
    if (!es)
        return NULL;
    if (GetExtSprite(es, TAG_END) < 0) {          /* any free sprite */
        FreeSpriteData(es);
        return NULL;
    }
    ChangeExtSprite(vp, NULL, es, TAG_END);
    MoveSprite(vp, &es->es_SimpleSprite, 120, 80);
    return es;
}
```

### Gotchas
- V39 only. BUGS: under V39 the attach bits are not set in the generated data; fix by setting bit 7
  of data word 1 (and of word 2 for a 32-bit-wide sprite, word 4 for 64-bit), counting from 0.
  Do NOT do this under V40, where it is fixed. (That the words are counted in the sprite's
  posctl data is unverified.)
- `ExtSprite.es_wordwidth`/`es_flags` are private.

**See also:** [FreeSpriteData](#freespritedata), [GetExtSpriteA](#getextspritea),
[ChangeExtSpriteA](#changeextspritea)

## FreeSpriteData
`VOID FreeSpriteData(struct ExtSprite *sp)` — LVO -1032 (-$408)
Registers: sp=A2; no result

Free an ExtSprite allocated with AllocSpriteDataA.

- **sp** — the ExtSprite; NULL is a no-op.

Since V39.

### Gotchas
- Release the sprite number first ([FreeSprite](#freesprite)) and make sure it is no longer displayed.

**See also:** [AllocSpriteDataA](#allocspritedataa)

## GetExtSpriteA
`LONG GetExtSpriteA(struct ExtSprite *ss, CONST struct TagItem *tags)` — LVO -930 (-$3A2)
Registers: ss=A2, tags=A1; result in D0

Reserve a hardware sprite for an ExtSprite (extended sprite manager).

- **ss** — ExtSprite from [AllocSpriteDataA](#allocspritedataa).
- **tags** — `GSTAG_SPRITE_NUM` (`$82000020`, a specific sprite number), `GSTAG_ATTACHED`
  (`$82000022`, data = second ExtSprite for an attached pair; free both later),
  `GSTAG_SCANDOUBLED` (`$83000000`, ask for NTSC-like height where possible),
  `GSTAG_SOFTSPRITE` (`$82000024`, header only, undocumented).
- **Result** — sprite number, or -1 (none free, or it would need a sprite mode change that clashes
  with sprites already in use).

Since V39.

### Gotchas
- BUGS: `GSTAG_ATTACHED` does not work under V39; reserve the second sprite with its own
  GetExtSprite call there.
- Varargs form `GetExtSprite(ss, tag, ...)`; register order is unusual (ss = A2, tags = A1).

**See also:** [ChangeExtSpriteA](#changeextspritea), [FreeSprite](#freesprite),
[GetSprite](#getsprite)

## ChangeExtSpriteA
`LONG ChangeExtSpriteA(struct ViewPort *vp, struct ExtSprite *oldsprite, struct ExtSprite *newsprite, CONST struct TagItem *tags)` — LVO -1026 (-$402)
Registers: vp=A0, oldsprite=A1, newsprite=A2, tags=A3; result in D0

Replace the image shown by an extended sprite.

- **vp** — ViewPort the sprite is relative to, or NULL for the View.
- **oldsprite** — ExtSprite currently shown (the example passes NULL for the first image;
  unverified that NULL is accepted on every V39+ release).
- **newsprite** — ExtSprite to show (reserved with [GetExtSpriteA](#getextspritea) or sharing
  its number).
- **tags** — `GSTAG_SCANDOUBLED` is valid here; otherwise `TAG_END`.
- **Result** — 0 on error.

Since V39.

**See also:** [AllocSpriteDataA](#allocspritedataa), [MoveSprite](#movesprite),
[ChangeSprite](#changesprite)
