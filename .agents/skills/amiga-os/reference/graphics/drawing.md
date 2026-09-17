# graphics.library: drawing

All drawing goes through a RastPort (see [RastPort basics](concepts.md#rastport-basics)): the
pens, draw mode, line pattern and area pattern set with the
[rastport-attrs](rastport-attrs.md#setapen) calls decide what is written, and the RastPort's
Layer (if any) clips it. Lines are drawn from the current pen position (`cp_x`, `cp_y`), which
[Move](#move) sets and [Draw](#draw), [PolyDraw](#polydraw) and [Text](text-and-fonts.md#text)
advance. Coordinates are relative to the RastPort (a window's RastPort includes its borders).
Most calls may leave the blitter running: [WaitBlit](blitter-and-timing.md#waitblit) before the
CPU reads the bitplanes. Filled polygons live in [area-fill](area-fill.md#initarea); rectangle
blits in [bitmaps-and-blits](bitmaps-and-blits.md#bltbitmap).

## Move
`VOID Move(struct RastPort *rp, LONG x, LONG y)` — LVO -240 (-$F0)
Registers: rp=A1, x=D0, y=D1; no result

Set the RastPort's current pen position without drawing.

- **rp** — the RastPort.
- **x**, **y** — new position; stored in `rp->cp_x` / `rp->cp_y` (asm `rp_cp_x`, `rp_cp_y`).

Move sets the start point for both [Draw](#draw) and [Text](text-and-fonts.md#text) (for text,
`y` is the baseline, not the top of the characters).

### Example
```asm
; draw an unfilled 100x50 box at (20,10) in pen 1
; a1 = RastPort
DrawBox:
        movem.l a2/a6,-(sp)
        move.l  _GfxBase,a6
        move.l  a1,a2                   ; keep rp: a1 is scratch
        moveq   #1,d0
        jsr     _LVOSetAPen(a6)
        move.l  a2,a1
        moveq   #20,d0
        moveq   #10,d1
        jsr     _LVOMove(a6)
        move.l  a2,a1
        move.l  #119,d0
        moveq   #10,d1
        jsr     _LVODraw(a6)
        move.l  a2,a1
        move.l  #119,d0
        moveq   #59,d1
        jsr     _LVODraw(a6)
        move.l  a2,a1
        moveq   #20,d0
        moveq   #59,d1
        jsr     _LVODraw(a6)
        move.l  a2,a1
        moveq   #20,d0
        moveq   #10,d1
        jsr     _LVODraw(a6)
        movem.l (sp)+,a2/a6
        rts
```

**See also:** [Draw](#draw), [PolyDraw](#polydraw), [Text](text-and-fonts.md#text)

## Draw
`VOID Draw(struct RastPort *rp, LONG x, LONG y)` — LVO -246 (-$F6)
Registers: rp=A1, x=D0, y=D1; no result

Draw a line from the current pen position to (x,y) and make (x,y) the new position.

- **rp** — the RastPort; uses FgPen, BgPen (JAM2 pattern gaps), DrawMode and `LinePtrn`.
- **x**, **y** — end point of the line.

### Example
```c
void cross(struct RastPort *rp, WORD cx, WORD cy, WORD r)
{
    SetAPen(rp, 2);
    Move(rp, cx - r, cy);  Draw(rp, cx + r, cy);
    Move(rp, cx, cy - r);  Draw(rp, cx, cy + r);
}
```

### Gotchas
- Dashed lines: set the pattern with [SetDrPt](rastport-attrs.md#setdrpt); changing pens or draw
  mode restarts the pattern.
- Without a Layer there is no clipping: stay inside the BitMap.

**See also:** [Move](#move), [PolyDraw](#polydraw), [SetDrPt](rastport-attrs.md#setdrpt)

## PolyDraw
`VOID PolyDraw(struct RastPort *rp, LONG count, CONST WORD *polyTable)` — LVO -336 (-$150)
Registers: rp=A1, count=D0, polyTable=A0; no result

Draw connected lines through a table of (x,y) points.

- **rp** — the RastPort.
- **count** — number of (x,y) PAIRS in the table (not number of WORDs).
- **polyTable** — WORD array `x0,y0, x1,y1, ...`. A line is drawn from the current pen position
  to the first point, then to each following point.

### Example
```c
static const WORD tri[] = { 50,10,  90,70,  10,70,  50,10 };

void triangle(struct RastPort *rp)
{
    Move(rp, tri[0], tri[1]);          /* otherwise a line comes from the old cp */
    PolyDraw(rp, 4, tri);              /* 4 pairs */
}
```

### Gotchas
- Move to the first point first, or you get a stray line from the old pen position.
- The shape is not closed automatically: repeat the first point at the end.

**See also:** [Draw](#draw), [Move](#move), [AreaDraw](area-fill.md#areadraw)

## DrawEllipse
`VOID DrawEllipse(struct RastPort *rp, LONG xCenter, LONG yCenter, LONG a, LONG b)` — LVO -180 (-$B4)
Registers: rp=A1, xCenter=D0, yCenter=D1, a=D2, b=D3; no result

Draw an ellipse outline centred at (xCenter,yCenter) in the current APen.

- **rp** — the RastPort.
- **xCenter**, **yCenter** — centre, RastPort coordinates.
- **a** — horizontal radius, must be > 0.
- **b** — vertical radius, must be > 0.

### Gotchas
- Not clipped on a non-layered RastPort: the whole ellipse must fit in the BitMap.
- For a filled ellipse use [AreaEllipse](area-fill.md#areaellipse) + AreaEnd.

**See also:** [DrawCircle](#drawcircle), [AreaEllipse](area-fill.md#areaellipse)

## DrawCircle

Macro (graphics/gfxmacros.h) — not a library call; expands to DrawEllipse(rp,cx,cy,r,r).

`DrawCircle(rp, cx, cy, r)` draws a circle outline of radius `r`; all
[DrawEllipse](#drawellipse) rules apply (radius > 0, no clipping without a Layer). Include
`<graphics/gfxmacros.h>`. In asm call `_LVODrawEllipse` with D2 = D3 = radius.

**See also:** [DrawEllipse](#drawellipse), [AreaCircle](area-fill.md#areacircle)

## RectFill
`VOID RectFill(struct RastPort *rp, LONG xMin, LONG yMin, LONG xMax, LONG yMax)` — LVO -306 (-$132)
Registers: rp=A1, xMin=D0, yMin=D1, xMax=D2, yMax=D3; no result

Fill a rectangle using the APen, draw mode and area pattern.

- **rp** — the RastPort. With no area pattern (`AreaPtrn` NULL) the rectangle is filled with
  FgPen honouring DrawMode; with a pattern (see [SetAfPt](rastport-attrs.md#setafpt)) JAM1/JAM2
  use FgPen/BgPen for the 1/0 bits.
- **xMin**, **yMin** — top-left corner (inclusive).
- **xMax**, **yMax** — bottom-right corner (inclusive).

### Example
```asm
; clear a 64x16 score panel at (8,4) to pen 0
; a1 = RastPort
ClearPanel:
        movem.l d2-d3/a2/a6,-(sp)
        move.l  _GfxBase,a6
        move.l  a1,a2
        moveq   #0,d0
        jsr     _LVOSetAPen(a6)
        move.l  a2,a1
        moveq   #8,d0                   ; xMin
        moveq   #4,d1                   ; yMin
        moveq   #8+64-1,d2              ; xMax (inclusive)
        moveq   #4+16-1,d3              ; yMax (inclusive)
        jsr     _LVORectFill(a6)
        movem.l (sp)+,d2-d3/a2/a6
        rts
```

### Gotchas
- `xMax >= xMin` and `yMax >= yMin` MUST hold; the call does not guard against an empty or
  inverted rectangle, so check computed sizes before calling.
- Max coordinates are inclusive: a w x h box is `(x, y, x+w-1, y+h-1)`.
- BUG: in COMPLEMENT mode it complements all bitplanes, not just the FgPen bits; restrict the
  planes with the write mask ([SetWriteMask](rastport-attrs.md#setwritemask)) if that matters.
- Not clipped without a Layer.

**See also:** [SetRast](#setrast), [EraseRect](#eraserect), [AreaEnd](area-fill.md#areaend),
[SetAfPt](rastport-attrs.md#setafpt)

## SetRast
`VOID SetRast(struct RastPort *rp, ULONG pen)` — LVO -234 (-$EA)
Registers: rp=A1, pen=D0; no result

Set every pixel of the RastPort's drawing area to one pen.

- **rp** — the RastPort (for a layered one, only the layer area).
- **pen** — pen number 0-255.

### Example
```c
void clear_offscreen(struct RastPort *rp)
{
    SetRast(rp, 0);      /* whole BitMap to colour 0 */
    WaitBlit();          /* before the CPU looks at the planes */
}
```

### Gotchas
- Does not change the APen. On a window RastPort it also wipes the border area; use
  [EraseRect](#eraserect) or [RectFill](#rectfill) on the inner box instead.

**See also:** [RectFill](#rectfill), [BltClear](bitmaps-and-blits.md#bltclear)

## EraseRect
`VOID EraseRect(struct RastPort *rp, LONG xMin, LONG yMin, LONG xMax, LONG yMax)` — LVO -810 (-$32A)
Registers: rp=A1, xMin=D0, yMin=D1, xMax=D2, yMax=D3; no result

Clear a rectangle through the layer's backfill hook (plain clear when not layered).

- **rp** — the RastPort. Layered: `Layer->BackFill` hook renders the area (the window/screen
  backfill). Not layered: the rectangle is cleared.
- **xMin**, **yMin**, **xMax**, **yMax** — inclusive rectangle; `xMax >= xMin`, `yMax >= yMin`
  MUST hold.

Since V36.

### Example
```c
/* erase the inside of a window so custom backfills (patterns) are kept */
void erase_inner(struct Window *win)
{
    EraseRect(win->RPort, win->BorderLeft, win->BorderTop,
              win->Width - win->BorderRight - 1,
              win->Height - win->BorderBottom - 1);
}
```

### Gotchas
- Same size rule as RectFill: an empty/negative rectangle is not allowed.
- V36+ only.

**See also:** [RectFill](#rectfill), [ScrollRasterBF](#scrollrasterbf)

## WritePixel
`LONG WritePixel(struct RastPort *rp, LONG x, LONG y)` — LVO -324 (-$144)
Registers: rp=A1, x=D0, y=D1; result in D0

Set one pixel to the APen, obeying the draw mode.

- **rp** — the RastPort.
- **x**, **y** — pixel position.
- **Result** — 0 if the pixel was written, -1 if (x,y) is outside the RastPort.

### Gotchas
- One library call per pixel is slow; for images use [WritePixelArray8](#writepixelarray8),
  [WriteChunkyPixels](#writechunkypixels) or a blit.

**See also:** [ReadPixel](#readpixel), [WritePixelLine8](#writepixelline8)

## ReadPixel
`ULONG ReadPixel(struct RastPort *rp, LONG x, LONG y)` — LVO -318 (-$13E)
Registers: rp=A1, x=D0, y=D1; result in D0

Read the pen number of one pixel.

- **rp** — the RastPort.
- **x**, **y** — pixel position.
- **Result** — pen number, or -1 if the pixel cannot be read (e.g. outside the RastPort).

### Example
```c
BOOL is_background(struct RastPort *rp, WORD x, WORD y)
{
    LONG pen;
    WaitBlit();                          /* pending blits may still change it */
    pen = (LONG)ReadPixel(rp, x, y);
    return pen == 0;                     /* -1 = unreadable, not background */
}
```

### Gotchas
- The NDK 3.9 prototype returns ULONG while the autodoc documents LONG -1: cast to LONG (or
  compare with `(ULONG)-1`) before testing for the error value.

**See also:** [WritePixel](#writepixel), [ReadPixelArray8](#readpixelarray8)

## ReadPixelLine8
`LONG ReadPixelLine8(struct RastPort *rp, ULONG xstart, ULONG ystart, ULONG width, UBYTE *array, struct RastPort *tempRP)` — LVO -768 (-$300)
Registers: rp=A0, xstart=D0, ystart=D1, width=D2, array=A2, tempRP=A1; result in D0

Read a horizontal run of pixels into an array of pen bytes.

- **rp** — source RastPort.
- **xstart**, **ystart** — first pixel.
- **width** — number of pixels to read (non-negative).
- **array** — UBYTE buffer receiving one pen (0-255) per pixel; allocate at least
  `((width+15)>>4)<<4` bytes (width rounded up to 16).
- **tempRP** — temporary RastPort: a copy of `rp` with `Layer` = NULL, whose `BitMap` has
  `Rows` = 1, `BytesPerRow` = `((width+15)>>4)<<1`, and allocated `Planes[]` (one row each).
  The recipe is shown under [WritePixelArray8](#writepixelarray8).
- **Result** — number of pixels read.

Since V36.

### Gotchas
- The array needs the rounded size, not just `width` bytes.
- The temp RastPort's planes are used by the blitter: allocate them in chip RAM
  ([AllocRaster](bitmaps-and-blits.md#allocraster)).

**See also:** [ReadPixelArray8](#readpixelarray8), [WritePixelLine8](#writepixelline8),
[ReadPixel](#readpixel)

## WritePixelLine8
`LONG WritePixelLine8(struct RastPort *rp, ULONG xstart, ULONG ystart, ULONG width, UBYTE *array, struct RastPort *tempRP)` — LVO -774 (-$306)
Registers: rp=A0, xstart=D0, ystart=D1, width=D2, array=A2, tempRP=A1; result in D0

Write a horizontal run of pixels from an array of pen bytes.

- **rp** — destination RastPort.
- **xstart**, **ystart** — first pixel.
- **width** — number of pixels (non-negative).
- **array** — UBYTE pens; allocate at least `((width+15)>>4)<<4` bytes.
- **tempRP** — temporary RastPort built as for [WritePixelArray8](#writepixelarray8)
  (Layer NULL, BitMap Rows 1, BytesPerRow `((width+15)>>4)<<1`, planes allocated).
- **Result** — number of pixels written.

Since V36.

**See also:** [WritePixelArray8](#writepixelarray8), [ReadPixelLine8](#readpixelline8)

## ReadPixelArray8
`LONG ReadPixelArray8(struct RastPort *rp, ULONG xstart, ULONG ystart, ULONG xstop, ULONG ystop, UBYTE *array, struct RastPort *temprp)` — LVO -780 (-$30C)
Registers: rp=A0, xstart=D0, ystart=D1, xstop=D2, ystop=D3, array=A2, temprp=A1; result in D0

Read a rectangle of pixels into an array of pen bytes, row by row.

- **rp** — source RastPort.
- **xstart**, **ystart** — top-left pixel.
- **xstop**, **ystop** — bottom-right pixel (inclusive); `xstop >= xstart`, `ystop >= ystart`.
- **array** — UBYTE buffer; allocate at least `(((width+15)>>4)<<4) * (ystop-ystart+1)` bytes,
  width = `xstop-xstart+1`.
- **temprp** — temporary RastPort as for [WritePixelArray8](#writepixelarray8).
- **Result** — number of pixels read.

Since V36.

### Gotchas
- Rows are stored consecutively `width` bytes apart; the 16-pixel rounding is working
  space (unverified: the autodoc only gives the buffer size).
- [WaitBlit](blitter-and-timing.md#waitblit) first if blits into `rp` may still be running.

**See also:** [WritePixelArray8](#writepixelarray8), [ReadPixelLine8](#readpixelline8)

## WritePixelArray8
`LONG WritePixelArray8(struct RastPort *rp, ULONG xstart, ULONG ystart, ULONG xstop, ULONG ystop, UBYTE *array, struct RastPort *temprp)` — LVO -786 (-$312)
Registers: rp=A0, xstart=D0, ystart=D1, xstop=D2, ystop=D3, array=A2, temprp=A1; result in D0

Write a rectangle of pixels from an array of pen bytes (chunky to planar).

- **rp** — destination RastPort (layered is fine).
- **xstart**, **ystart** — top-left pixel.
- **xstop**, **ystop** — bottom-right pixel (inclusive); `xstop >= xstart`, `ystop >= ystart`.
- **array** — UBYTE pens, rows one after another (`width` bytes per row, unverified);
  allocate at least `(((width+15)>>4)<<4) * (ystop-ystart+1)` bytes, width = `xstop-xstart+1`.
- **temprp** — temporary RastPort: copy of `rp` with `Layer` = NULL, `BitMap` with `Rows` = 1,
  `BytesPerRow` = `((width+15)>>4)<<1` and allocated planes.
- **Result** — number of pixels written.

Since V36.

### Example
```c
/* buffer for pens: width rounded up to 16 pixels, times height */
UBYTE *alloc_pen_array(UWORD w, UWORD h)
{
    return AllocVec((((ULONG)w + 15) >> 4 << 4) * h, MEMF_ANY | MEMF_CLEAR);
}

/* draw w x h pens (w bytes per row) at (x,y) */
LONG put_pens(struct RastPort *rp, UWORD x, UWORD y, UWORD w, UWORD h, UBYTE *array)
{
    struct RastPort temprp;
    struct BitMap tempbm;
    LONG depth = rp->BitMap->Depth;
    LONG i, count = 0;

    temprp = *rp;                        /* copy of rp ...            */
    temprp.Layer = NULL;                 /* ... without its Layer     */
    InitBitMap(&tempbm, depth, w, 1);    /* Rows 1, BytesPerRow ((w+15)>>4)<<1 */
    temprp.BitMap = &tempbm;
    for (i = 0; i < depth; i++) {
        tempbm.Planes[i] = AllocRaster(w, 1);   /* chip RAM, one row */
        if (!tempbm.Planes[i])
            goto done;
    }
    count = WritePixelArray8(rp, x, y, x + w - 1, y + h - 1, array, &temprp);
done:
    WaitBlit();
    while (--i >= 0)
        FreeRaster(tempbm.Planes[i], w, 1);
    return count;
}
```

### Gotchas
- Follow the temp RastPort recipe exactly: a temp RastPort that still has the Layer, or a temp
  BitMap with the full height or another BytesPerRow, does not meet the documented contract.
- Keep the temp RastPort around for repeated calls of the same width instead of reallocating.
- On V40+ [WriteChunkyPixels](#writechunkypixels) needs no temp RastPort.

**See also:** [ReadPixelArray8](#readpixelarray8), [WritePixelLine8](#writepixelline8),
[WriteChunkyPixels](#writechunkypixels)

## WriteChunkyPixels
`VOID WriteChunkyPixels(struct RastPort *rp, ULONG xstart, ULONG ystart, ULONG xstop, ULONG ystop, CONST UBYTE *array, LONG bytesperrow)` — LVO -1056 (-$420)
Registers: rp=A0, xstart=D0, ystart=D1, xstop=D2, ystop=D3, array=A2, bytesperrow=D4; no result

Write a rectangle of pen bytes with an explicit row stride; no temp RastPort needed.

- **rp** — destination RastPort.
- **xstart**, **ystart**, **xstop**, **ystop** — inclusive rectangle; `xstop >= xstart`,
  `ystop >= ystart`.
- **array** — UBYTE pens; may be in fast RAM.
- **bytesperrow** — row stride of `array` in bytes, at least the number of pixels per line.

Since V40.

### Example
```c
void show_chunky(struct RastPort *rp, UBYTE *pix, UWORD w, UWORD h)
{
    if (GfxBase->LibNode.lib_Version >= 40)
        WriteChunkyPixels(rp, 0, 0, w - 1, h - 1, pix, w);
    /* else: WritePixelArray8() with a temp RastPort, or your own converter */
}
```

### Gotchas
- V40 (3.1) only: check `GfxBase->LibNode.lib_Version >= 40` (asm: `LIB_VERSION(a6)`).
- Slow without chunky-to-planar hardware. `GfxBase->ChunkyToPlanarPtr` (asm
  `gb_ChunkyToPlanarPtr`) is non-NULL when such hardware exists; the field only exists from
  V40, so check the version before reading it. Games may use their own converter when it is NULL.
- To drive that hardware directly you must own the blitter
  ([OwnBlitter](blitter-and-timing.md#ownblitter)): write 8 longwords (32 chunky pixels) to it,
  then read back up to 8 longwords of plane data, plane 0 first.

**See also:** [WritePixelArray8](#writepixelarray8), [WritePixel](#writepixel)

## ScrollRaster
`VOID ScrollRaster(struct RastPort *rp, LONG dx, LONG dy, LONG xMin, LONG yMin, LONG xMax, LONG yMax)` — LVO -396 (-$18C)
Registers: rp=A1, dx=D0, dy=D1, xMin=D2, yMin=D3, xMax=D4, yMax=D5; no result

Shift the bits inside a rectangle by (dx,dy) towards (0,0) and clear what is uncovered.

- **rp** — the RastPort.
- **dx**, **dy** — shift amount: positive values move the contents LEFT/UP, negative
  RIGHT/DOWN. `(0,1)` scrolls up one row.
- **xMin**, **yMin**, **xMax**, **yMax** — the rectangle; bits outside are untouched. A max
  beyond the RastPort is clipped to its lower-right corner.

The vacated strip is filled with BgPen (RectFill semantics).

### Example
```c
/* scroll a text area up by one 8-pixel line */
void scroll_up(struct RastPort *rp, WORD x0, WORD y0, WORD x1, WORD y1)
{
    SetBPen(rp, 0);                         /* colour of the new empty line */
    ScrollRaster(rp, 0, 8, x0, y0, x1, y1);
}
```

### Gotchas
- The uncovered area uses BgPen, not pen 0: set it first. For windows with a custom backfill use
  [ScrollRasterBF](#scrollrasterbf).
- SIMPLE_REFRESH layers: from V36 the scrolled-in areas are added to the damage list; check
  `rp->Layer->Flags & LAYERREFRESH` and do the refresh (intuition BeginRefresh or layers
  BeginUpdate). This is NOT done for SMART_REFRESH layers.
- 1.2/1.3 bug: scrolling a SuperBitMap exactly left/right without a TmpRas leaked an internally
  allocated TmpRas; attach a TmpRas of at least `MAXBYTESPERROW` bytes on those systems (fixed V36).

**See also:** [ScrollRasterBF](#scrollrasterbf), [EraseRect](#eraserect),
[ScrollVPort](views-and-viewports.md#scrollvport)

## ScrollRasterBF
`VOID ScrollRasterBF(struct RastPort *rp, LONG dx, LONG dy, LONG xMin, LONG yMin, LONG xMax, LONG yMax)` — LVO -1002 (-$3EA)
Registers: rp=A1, dx=D0, dy=D1, xMin=D2, yMin=D3, xMax=D4, yMax=D5; no result

Like ScrollRaster, but the uncovered area is cleared with EraseRect (backfill hook).

- **rp**, **dx**, **dy**, **xMin**, **yMin**, **xMax**, **yMax** — as for
  [ScrollRaster](#scrollraster).

Since V39.

### Gotchas
- Same SIMPLE_REFRESH damage rules as ScrollRaster.
- V39+ only; on older systems use ScrollRaster with BgPen set.

**See also:** [ScrollRaster](#scrollraster), [EraseRect](#eraserect)

## BltPattern
`VOID BltPattern(struct RastPort *rp, CONST PLANEPTR mask, LONG xMin, LONG yMin, LONG xMax, LONG yMax, ULONG maskBPR)` — LVO -312 (-$138)
Registers: rp=A1, mask=A0, xMin=D0, yMin=D1, xMax=D2, yMax=D3, maskBPR=D4; no result

Fill a rectangle through an optional 2-D mask using pens, draw mode and area pattern.

- **rp** — destination RastPort; rendering follows the area-fill rules (FgPen/BgPen,
  DrawMode, `AreaPtrn`).
- **mask** — mask plane for the rectangle (1 = render), or NULL to fill the whole rectangle.
- **xMin**, **yMin**, **xMax**, **yMax** — inclusive destination rectangle.
- **maskBPR** — bytes per row of the mask.

### Gotchas
- The mask is read by the blitter: keep it in chip RAM.
- With a NULL mask it behaves like a patterned RectFill.

**See also:** [BltTemplate](#blttemplate), [RectFill](#rectfill), [AreaEnd](area-fill.md#areaend)

## BltTemplate
`VOID BltTemplate(CONST PLANEPTR source, LONG xSrc, LONG srcMod, struct RastPort *destRP, LONG xDest, LONG yDest, LONG xSize, LONG ySize)` — LVO -36 (-$24)
Registers: source=A0, xSrc=D0, srcMod=D1, destRP=A1, xDest=D2, yDest=D3, xSize=D4, ySize=D5; no result

Cookie-cut a 1-bit template into the RastPort in the current APen and draw mode.

- **source** — pointer to the word containing the template's first pixel (round the address
  down to a word).
- **xSrc** — bit offset of the first pixel inside that word, 0-15.
- **srcMod** — bytes per row of the template.
- **destRP** — destination RastPort.
- **xDest**, **yDest** — top-left destination.
- **xSize**, **ySize** — size of the template rectangle.

1 bits are drawn in FgPen; 0 bits leave the destination (JAM1) or get BgPen (JAM2). Output is
truncated at the RastPort edges.

### Example
```c
/* 16x8 arrow, one word per row; copied to chip RAM because the blitter reads it */
static const UWORD arrow[8] = {
    0x0100, 0x0180, 0xFFC0, 0xFFE0, 0xFFE0, 0xFFC0, 0x0180, 0x0100
};

BOOL draw_arrow(struct RastPort *rp, WORD x, WORD y)
{
    UWORD *chip = AllocMem(sizeof(arrow), MEMF_CHIP);
    if (!chip)
        return FALSE;
    CopyMem((APTR)arrow, chip, sizeof(arrow));
    SetABPenDrMd(rp, 3, 0, JAM1);
    BltTemplate((PLANEPTR)chip, 0, 2, rp, x, y, 16, 8);   /* srcMod 2 bytes/row */
    WaitBlit();                                           /* before freeing it */
    FreeMem(chip, sizeof(arrow));
    return TRUE;
}
```

### Gotchas
- The template must not overlap the destination bitmap.
- The template is read by the blitter: it must be in chip RAM (exec AllocMem `MEMF_CHIP` and
  copy, or put it in a chip data section), and WaitBlit before freeing it.
- `srcMod` is in BYTES (not words); rows are word-aligned, so it is normally even.

**See also:** [BltPattern](#bltpattern), [BltMaskBitMapRastPort](bitmaps-and-blits.md#bltmaskbitmaprastport)
