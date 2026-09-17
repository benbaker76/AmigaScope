# graphics.library: bitmaps and blits

A `struct BitMap` is a header (`BytesPerRow`, `Rows`, `Flags`, `Depth`, `Planes[8]`) pointing at
planar bitplane memory. From V39 allocate the whole thing with [AllocBitMap](#allocbitmap) (it
knows the alignment and chip-RAM rules); before V39 use [InitBitMap](#initbitmap) plus one
[AllocRaster](#allocraster) per plane. The blit calls copy rectangles between BitMaps
([BltBitMap](#bltbitmap)), from a BitMap into a RastPort ([BltBitMapRastPort](#bltbitmaprastport),
[BltMaskBitMapRastPort](#bltmaskbitmaprastport)) or between RastPorts ([ClipBlit](#clipblit)); use
the RastPort forms whenever the destination belongs to a window (layers/clipping). All of them
may leave the blitter running when they return: call [WaitBlit](blitter-and-timing.md#waitblit)
before reading the result with the CPU or freeing the memory. Minterm names (`ABC`, `ABNC`, ...)
are in hardware/blit.h / blit.i. See [bitmap concepts](concepts.md#bitmaps-planar-and-interleaved).

## AllocBitMap
`struct BitMap * AllocBitMap(ULONG sizex, ULONG sizey, ULONG depth, ULONG flags, CONST struct BitMap *friend_bitmap)` — LVO -918 (-$396)
Registers: sizex=D0, sizey=D1, depth=D2, flags=D3, friend_bitmap=A0; result in D0

Allocate a BitMap structure and all its bitplanes in one call.

- **sizex**, **sizey** — size in pixels.
- **depth** — number of planes (at least this many bits per pixel are provided).
- **flags** — `BMF_CLEAR` (fill with colour 0), `BMF_DISPLAYABLE` (align so it can be shown in a
  ViewPort / as an Intuition custom bitmap), `BMF_INTERLEAVED` (one chunk for all planes, less
  colour flashing on deep displays; silently falls back to planar if no contiguous RAM),
  `BMF_MINPLANES` (system use only). Bits `BMB_CLEAR` 0, `BMB_DISPLAYABLE` 1,
  `BMB_INTERLEAVED` 2, `BMB_MINPLANES` 4 (gfx.h / gfx.i).
- **friend_bitmap** — NULL, or a BitMap you will blit to/from a lot (e.g. `win->RPort->BitMap`
  or `scr->RastPort.BitMap`); the new bitmap is then allocated in the most efficient format for
  that pairing (on a graphics card: card memory, possibly not planar).
- **Result** — pointer to the BitMap, or NULL. Free with [FreeBitMap](#freebitmap).

Since V39.

### Example
```c
/* off-screen buffer that blits fast to a window's screen */
struct BitMap *make_buffer(struct Window *win, ULONG w, ULONG h)
{
    struct BitMap *friend = win->RPort->BitMap;
    ULONG depth = GetBitMapAttr(friend, BMA_DEPTH);
    struct BitMap *bm = AllocBitMap(w, h, depth, BMF_CLEAR, friend);
    if (!bm)
        return NULL;                  /* always test */
    return bm;
}
```

```asm
; d0 = BitMap for a 320x256 5-plane displayable screen, or 0
AllocScreenBM:
        movem.l d2-d3/a6,-(sp)
        move.l  _GfxBase,a6
        move.l  #320,d0
        move.l  #256,d1
        moveq   #5,d2
        moveq   #BMF_DISPLAYABLE!BMF_CLEAR,d3
        sub.l   a0,a0                   ; no friend
        jsr     _LVOAllocBitMap(a6)
        movem.l (sp)+,d2-d3/a6
        tst.l   d0
        rts
```

### Gotchas
- Without `BMF_DISPLAYABLE` the bitmap must not be put in a `RasInfo` or used as an Intuition
  CustomBitMap -- only blitted to a displayable one.
- With a friend bitmap that is not standard Amiga planar memory (graphics card), do not touch
  `Planes[]` directly: only blit to/from it or render into it through a RastPort.
- Pass `win->RPort->BitMap` or `scr->RastPort.BitMap` as friend, never `&scr->BitMap` (the
  embedded Screen BitMap copy is not the real one).
- Sizes in the structure may be rounded up for alignment; read them back with
  [GetBitMapAttr](#getbitmapattr).
- V39+ only. For V37 fall back to [InitBitMap](#initbitmap) + [AllocRaster](#allocraster).

**See also:** [FreeBitMap](#freebitmap), [GetBitMapAttr](#getbitmapattr),
[InitBitMap](#initbitmap), [ChangeVPBitMap](views-and-viewports.md#changevpbitmap)

## FreeBitMap
`VOID FreeBitMap(struct BitMap *bm)` — LVO -924 (-$39C)
Registers: bm=A0; no result

Free a BitMap and all planes obtained with AllocBitMap.

- **bm** — BitMap from [AllocBitMap](#allocbitmap); NULL is a safe no-op.

Since V39.

### Example
```c
void free_buffer(struct BitMap *bm)
{
    WaitBlit();          /* a blit into bm may still be running */
    FreeBitMap(bm);      /* NULL is fine */
}
```

### Gotchas
- Call [WaitBlit](blitter-and-timing.md#waitblit) first if you rendered into or blitted from it.
- Only for bitmaps from AllocBitMap. A hand-built BitMap (InitBitMap + AllocRaster) is freed
  plane by plane with [FreeRaster](#freeraster).
- Make sure it is no longer shown (RasInfo, screen, DBufInfo) before freeing.

**See also:** [AllocBitMap](#allocbitmap), [WaitBlit](blitter-and-timing.md#waitblit)

## GetBitMapAttr
`ULONG GetBitMapAttr(CONST struct BitMap *bm, ULONG attrnum)` — LVO -960 (-$3C0)
Registers: bm=A0, attrnum=D1; result in D0

Query width, height, depth or flags of a BitMap without reading its fields.

- **bm** — the BitMap.
- **attrnum** — `BMA_HEIGHT` (0), `BMA_DEPTH` (4), `BMA_WIDTH` (8), `BMA_FLAGS` (12).
- **Result** — the value. For `BMA_FLAGS`: `BMF_DISPLAYABLE`, `BMF_INTERLEAVED`, and
  `BMF_STANDARD` (set when the data is ordinary planar Amiga chip RAM). Unknown attributes
  return 0.

Since V39.

### Example
```c
BOOL is_planar_chip(struct BitMap *bm)
{
    return (GetBitMapAttr(bm, BMA_FLAGS) & BMF_STANDARD) != 0;
}
```

### Gotchas
- Sizes may differ from what you asked AllocBitMap for (alignment padding).
- `BMF_DISPLAYABLE` is only reported when all alignment rules are met; a bitmap without it may
  still display, just less efficiently.
- Test `BMF_STANDARD` before poking `Planes[]` of any bitmap you did not allocate yourself.

**See also:** [AllocBitMap](#allocbitmap)

## InitBitMap
`VOID InitBitMap(struct BitMap *bitMap, LONG depth, LONG width, LONG height)` — LVO -390 (-$186)
Registers: bitMap=A0, depth=D0, width=D1, height=D2; no result

Fill in BytesPerRow, Rows, Depth and Flags of a caller-supplied BitMap structure.

- **bitMap** — your `struct BitMap` (C `sizeof` 40 bytes, asm `bm_SIZEOF`).
- **depth** — number of planes (1-8).
- **width** — width in pixels; BytesPerRow becomes the width rounded up to a 16-bit word, in bytes.
- **height** — rows.

`Planes[]` are NOT touched: allocate and store each plane pointer yourself
([AllocRaster](#allocraster) or any chip RAM block of `RASSIZE(w,h)` bytes).

### Example
```asm
; build a 320x256x4 BitMap by hand (V37-compatible)
InitMyBM:
        movem.l d2-d4/a2/a6,-(sp)
        move.l  _GfxBase,a6
        lea     MyBitMap(pc),a0
        moveq   #4,d0                   ; depth
        move.l  #320,d1
        move.l  #256,d2
        jsr     _LVOInitBitMap(a6)
        lea     MyBitMap+bm_Planes(pc),a2
        moveq   #4-1,d4
.plane: move.l  #320,d0
        move.l  #256,d1
        jsr     _LVOAllocRaster(a6)     ; chip RAM plane
        move.l  d0,(a2)+
        beq.s   .fail                   ; caller must free the planes already got
        dbf     d4,.plane
        moveq   #1,d0
        bra.s   .out
.fail:  moveq   #0,d0
.out:   movem.l (sp)+,d2-d4/a2/a6
        rts

MyBitMap:
        ds.b    bm_SIZEOF
```

### Gotchas
- `Flags` and `pad` are reserved; leave them as InitBitMap sets them.
- The Planes array holds 8 pointers; code may truncate or extend the structure but graphics only
  looks at `Depth` planes.
- On V39+ prefer [AllocBitMap](#allocbitmap): displayed bitmaps may need alignment that a
  hand-made one lacks (MakeVPort can then fail with `MVP_NO_DISPLAY`).

**See also:** [AllocRaster](#allocraster), [AllocBitMap](#allocbitmap), [concepts](concepts.md#view-viewport-rasinfo-bitmap)

## AllocRaster
`PLANEPTR AllocRaster(ULONG width, ULONG height)` — LVO -492 (-$1EC)
Registers: width=D0, height=D1; result in D0

Allocate chip RAM for one bitplane of width x height pixels.

- **width** — columns (bits).
- **height** — rows.
- **Result** — plane pointer, or NULL. Size is `RASSIZE(width,height)` bytes (width rounded up
  to 16 bits).

### Example
```c
BOOL with_scratch_plane(void)
{
    PLANEPTR plane = AllocRaster(320, 256);   /* RASSIZE(320,256) = 10240 bytes */
    if (!plane)
        return FALSE;
    /* ... use ... */
    WaitBlit();
    FreeRaster(plane, 320, 256);              /* same width/height */
    return TRUE;
}
```

### Gotchas
- Free with [FreeRaster](#freeraster) using the SAME width and height.
- Not guaranteed to meet V39 display alignment rules; for anything shown in a ViewPort or screen
  use [AllocBitMap](#allocbitmap) with `BMF_DISPLAYABLE`.
- Also a handy way to get a chip RAM `TmpRas` buffer for
  [InitTmpRas](area-fill.md#inittmpras).

**See also:** [FreeRaster](#freeraster), [InitBitMap](#initbitmap)

## FreeRaster
`VOID FreeRaster(PLANEPTR p, ULONG width, ULONG height)` — LVO -498 (-$1F2)
Registers: p=A0, width=D0, height=D1; no result

Free one bitplane obtained with AllocRaster.

- **p** — pointer from [AllocRaster](#allocraster).
- **width**, **height** — exactly the values passed to AllocRaster.

### Gotchas
- A wrong size corrupts the free memory list.
- [WaitBlit](blitter-and-timing.md#waitblit) first if the blitter may still be using the plane.

**See also:** [AllocRaster](#allocraster)

## BltBitMap
`LONG BltBitMap(CONST struct BitMap *srcBitMap, LONG xSrc, LONG ySrc, struct BitMap *destBitMap, LONG xDest, LONG yDest, LONG xSize, LONG ySize, ULONG minterm, ULONG mask, PLANEPTR tempA)` — LVO -30 (-$1E)
Registers: srcBitMap=A0, xSrc=D0, ySrc=D1, destBitMap=A1, xDest=D2, yDest=D3, xSize=D4, ySize=D5, minterm=D6, mask=D7, tempA=A2; result in D0

Copy a rectangle between two BitMaps (or within one) with a minterm and plane mask.

- **srcBitMap**, **destBitMap** — source and destination; may be the same BitMap (overlap is
  handled). A source plane pointer of 0 acts as all-zero, `$FFFFFFFF` as all-one (V36).
- **xSrc**, **ySrc** — top-left of the source rectangle.
- **xDest**, **yDest** — top-left of the destination.
- **xSize**, **ySize** — rectangle size in pixels.
- **minterm** — logic applied inside the rectangle (B = source, C = destination): `$C0` plain
  copy (`ABC|ABNC`), `$30` copy inverted source, `$50` invert destination (source ignored).
- **mask** — plane write mask: bit n set = plane n takes part. Normally `$FF`. Only planes below
  the smaller Depth of the two bitmaps are touched.
- **tempA** — NULL, or a chip RAM buffer of one source line used when the copy overlaps exactly
  left/right; allocated internally if NULL and needed.
- **Result** — number of planes actually blitted.

### Example
```asm
; copy a 32x32 tile from the tile sheet to the back buffer
; a0 = source BitMap, a1 = dest BitMap, d0/d1 = tile x/y, d2/d3 = dest x/y
BlitTile:
        movem.l d4-d7/a2/a6,-(sp)
        move.l  _GfxBase,a6
        moveq   #32,d4                  ; width
        moveq   #32,d5                  ; height
        move.l  #ABC!ABNC,d6            ; $c0 = copy
        moveq   #-1,d7                  ; all planes ($ff)
        sub.l   a2,a2                   ; tempA: let graphics decide
        jsr     _LVOBltBitMap(a6)
        movem.l (sp)+,d4-d7/a2/a6
        rts
```

```c
void copy_rect(struct BitMap *src, struct BitMap *dst, WORD x, WORD y, WORD w, WORD h)
{
    BltBitMap(src, x, y, dst, x, y, w, h, 0xC0, 0xFF, NULL);
    WaitBlit();          /* only needed before the CPU reads dst or src is freed */
}
```

### Gotchas
- No clipping or bounds checks at all: a rectangle outside either BitMap trashes memory.
- Never blit into a window's `RPort->BitMap` directly: it ignores layers and overwrites other
  windows. Use [ClipBlit](#clipblit) or [BltBitMapRastPort](#bltbitmaprastport).
- The mask selects planes, it is not a cookie-cut shape; for a shape mask use
  [BltMaskBitMapRastPort](#bltmaskbitmaprastport).
- Returns before the blitter finishes: [WaitBlit](blitter-and-timing.md#waitblit) before the CPU
  reads the destination or before freeing either bitmap.
- Chip RAM planes are required for blitter use; standard AllocBitMap/AllocRaster planes are chip.

**See also:** [ClipBlit](#clipblit), [BltBitMapRastPort](#bltbitmaprastport),
[BltMaskBitMapRastPort](#bltmaskbitmaprastport), [WaitBlit](blitter-and-timing.md#waitblit)

## BltBitMapRastPort
`VOID BltBitMapRastPort(CONST struct BitMap *srcBitMap, LONG xSrc, LONG ySrc, struct RastPort *destRP, LONG xDest, LONG yDest, LONG xSize, LONG ySize, ULONG minterm)` — LVO -606 (-$25E)
Registers: srcBitMap=A0, xSrc=D0, ySrc=D1, destRP=A1, xDest=D2, yDest=D3, xSize=D4, ySize=D5, minterm=D6; no result

Blit a rectangle from a BitMap into a RastPort, honouring the RastPort's layer clipping.

- **srcBitMap** — source BitMap.
- **xSrc**, **ySrc** — top-left in the source.
- **destRP** — destination RastPort (e.g. `win->RPort`).
- **xDest**, **yDest** — top-left in the RastPort's coordinates.
- **xSize**, **ySize** — size in pixels.
- **minterm** — as for [BltBitMap](#bltbitmap); `$C0` = copy.

### Example
```c
/* draw a pre-rendered image into a window */
void show_image(struct Window *win, struct BitMap *img, WORD w, WORD h)
{
    BltBitMapRastPort(img, 0, 0, win->RPort,
                      win->BorderLeft, win->BorderTop, w, h, 0xC0);
}
```

### Gotchas
- The NDK 3.9 prototype is `VOID`; the autodoc documents a BOOL result (always TRUE). Do not
  rely on D0.
- Destination coordinates are relative to the RastPort (window origin), not the screen.

**See also:** [BltMaskBitMapRastPort](#bltmaskbitmaprastport), [ClipBlit](#clipblit),
[BltBitMap](#bltbitmap)

## BltMaskBitMapRastPort
`VOID BltMaskBitMapRastPort(CONST struct BitMap *srcBitMap, LONG xSrc, LONG ySrc, struct RastPort *destRP, LONG xDest, LONG yDest, LONG xSize, LONG ySize, ULONG minterm, CONST PLANEPTR bltMask)` — LVO -636 (-$27C)
Registers: srcBitMap=A0, xSrc=D0, ySrc=D1, destRP=A1, xDest=D2, yDest=D3, xSize=D4, ySize=D5, minterm=D6, bltMask=A2; no result

Blit a BitMap into a RastPort only where a one-plane mask has 1 bits (cookie-cut).

- **srcBitMap**, **xSrc**, **ySrc**, **destRP**, **xDest**, **yDest**, **xSize**, **ySize** —
  as for [BltBitMapRastPort](#bltbitmaprastport).
- **minterm** — `ABC|ABNC|ANBC` (`$E0`) copies the source through the mask; `ANBC` (`$20`)
  copies the inverted source through the mask.
- **bltMask** — single plane, same width/height/BytesPerRow layout as the source planes, in
  chip RAM; 1 = draw source pixel, 0 = keep destination.

### Example
```c
/* draw a sprite-like image with transparency onto a window */
void draw_masked(struct RastPort *rp, struct BitMap *img, PLANEPTR mask,
                 WORD x, WORD y, WORD w, WORD h)
{
    BltMaskBitMapRastPort(img, 0, 0, rp, x, y, w, h,
                          (ABC | ABNC | ANBC), mask);
}
```

### Gotchas
- The mask must be laid out like one plane of the source bitmap (same row width), starting at
  source (0,0) -- (xSrc,ySrc) index into both.
- Build the mask by ORing all planes of the image if colour 0 is the transparent colour.
- Use only the two documented minterms; others give undefined results.

**See also:** [BltBitMapRastPort](#bltbitmaprastport), [BltTemplate](drawing.md#blttemplate),
[BltBitMap](#bltbitmap)

## ClipBlit
`VOID ClipBlit(struct RastPort *srcRP, LONG xSrc, LONG ySrc, struct RastPort *destRP, LONG xDest, LONG yDest, LONG xSize, LONG ySize, ULONG minterm)` — LVO -552 (-$228)
Registers: srcRP=A0, xSrc=D0, ySrc=D1, destRP=A1, xDest=D2, yDest=D3, xSize=D4, ySize=D5, minterm=D6; no result

Blit a rectangle between two RastPorts, handling layers and ClipRects on either side.

- **srcRP**, **xSrc**, **ySrc** — source RastPort and top-left.
- **destRP**, **xDest**, **yDest** — destination RastPort and top-left.
- **xSize**, **ySize** — size in pixels (at least 1 each).
- **minterm** — SRCB is the source, SRCC the destination; `$C0` = copy.

### Example
```c
/* scroll-copy one area of a window to another */
void dup_area(struct Window *win)
{
    ClipBlit(win->RPort, 10, 10, win->RPort, 110, 10, 80, 40, 0xC0);
}
```

### Gotchas
- This is the call to use for blits involving an Intuition window's RastPort; plain
  [BltBitMap](#bltbitmap) would ignore overlapping windows.
- Either side, both or neither may be layered.

**See also:** [BltBitMap](#bltbitmap), [BltBitMapRastPort](#bltbitmaprastport)

## BltClear
`VOID BltClear(PLANEPTR memBlock, ULONG byteCount, ULONG flags)` — LVO -300 (-$12C)
Registers: memBlock=A1, byteCount=D0, flags=D1; no result

Clear (or fill) a chip RAM block to zero using the blitter.

- **memBlock** — even address of chip RAM.
- **byteCount** — if flags bit 1 is clear: even number of bytes. If bit 1 is set: low word =
  bytes per row, high word = number of rows.
- **flags** — bit 0: wait until the blit is done before returning. Bit 1: use rows/bytes-per-row
  form of byteCount. Bit 2 (V36): fill with the upper 16 bits of `flags` instead of 0.

### Example
```asm
; clear a 320x256 plane and wait for it (flags bit 0)
ClearPlane:
        move.l  a6,-(sp)
        move.l  _GfxBase,a6
        move.l  PlanePtr(pc),a1
        move.l  #(320/8)*256,d0         ; bytes, even
        moveq   #1,d1                   ; wait for completion
        jsr     _LVOBltClear(a6)
        move.l  (sp)+,a6
        rts
PlanePtr:
        dc.l    0
```

### Gotchas
- Memory must be chip RAM (the blitter writes it) and even-aligned; fast RAM is not cleared.
- Without flags bit 0 it returns while the blitter is still clearing: set bit 0 or call
  [WaitBlit](blitter-and-timing.md#waitblit) before using the memory.
- In rows/bytes-per-row mode on pre-ECS blitters rows must be <= 1024.
- No named constants exist for the flag bits; use 1, 2, 4.

**See also:** [WaitBlit](blitter-and-timing.md#waitblit), [SetRast](drawing.md#setrast)

## BitMapScale
`VOID BitMapScale(struct BitScaleArgs *bitScaleArgs)` — LVO -678 (-$2A6)
Registers: bitScaleArgs=A0; no result

Scale a rectangle of one BitMap into another BitMap by rational factors.

- **bitScaleArgs** — `struct BitScaleArgs` (graphics/scale.h):
  `bsa_SrcX`/`bsa_SrcY`, `bsa_SrcWidth`/`bsa_SrcHeight` (source rectangle);
  `bsa_XSrcFactor`:`bsa_XDestFactor` and `bsa_YSrcFactor`:`bsa_YDestFactor` (scale ratios,
  each 1..16383); `bsa_DestX`/`bsa_DestY` (destination origin); `bsa_SrcBitMap`,
  `bsa_DestBitMap`; `bsa_Flags` must be 0. `bsa_DestWidth`/`bsa_DestHeight` are OUTPUTS set by
  the call. Other fields are reserved.

Since V36.

### Example
```c
/* scale a 320x200 image to half size */
void half_size(struct BitMap *src, struct BitMap *dst)
{
    struct BitScaleArgs bsa = {0};
    bsa.bsa_SrcWidth = 320;  bsa.bsa_SrcHeight = 200;
    bsa.bsa_XSrcFactor = 2;  bsa.bsa_XDestFactor = 1;
    bsa.bsa_YSrcFactor = 2;  bsa.bsa_YDestFactor = 1;
    bsa.bsa_SrcBitMap = src; bsa.bsa_DestBitMap = dst;
    BitMapScale(&bsa);
    WaitBlit();
}
```

### Gotchas
- Source and destination must not overlap.
- No size check on the destination: compute the result size first with [ScalerDiv](#scalerdiv).
- May use the blitter. Does not use big-blit support: avoid equal X factors with widths above
  1024, and avoid Y expansion when `((DestX & 15) + DestWidth) >= 1024` (1008 is always safe).

**See also:** [ScalerDiv](#scalerdiv)

## ScalerDiv
`UWORD ScalerDiv(ULONG factor, ULONG numerator, ULONG denominator)` — LVO -684 (-$2AC)
Registers: factor=D0, numerator=D1, denominator=D2; result in D0

Compute factor * numerator / denominator exactly the way BitMapScale rounds sizes.

- **factor** — source size, 0..16383.
- **numerator** — the destination factor (e.g. `bsa_XDestFactor`), 1..16383.
- **denominator** — the source factor (e.g. `bsa_XSrcFactor`), 1..16383.
- **Result** — the destination size BitMapScale will produce (UWORD).

Since V36.

### Example
```c
UWORD scaled_width(UWORD src_w)
{
    return ScalerDiv(src_w, 1, 2);    /* dest:src factor 1:2 -> half width */
}
```

**See also:** [BitMapScale](#bitmapscale)
