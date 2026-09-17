# graphics.library: area fill and flood fill

Filled polygons and ellipses are collected as vectors and rendered in one go. Before the first
call attach two work areas to the RastPort: an `AreaInfo` vector table ([InitArea](#initarea),
5 bytes of buffer per vector) in `rp->AreaInfo`, and a `TmpRas` chip RAM scratch plane
([InitTmpRas](#inittmpras)) in `rp->TmpRas`. Then [AreaMove](#areamove) starts a shape,
[AreaDraw](#areadraw) adds corners, [AreaEllipse](#areaellipse) adds ellipses, and
[AreaEnd](#areaend) fills everything with the A pen, draw mode and area pattern (plus an outline
in the O pen when `AREAOUTLINE` is set). [Flood](#flood) is a separate seed fill that also needs
the TmpRas. You own both buffers: detach them from the RastPort before freeing.

## InitArea
`VOID InitArea(struct AreaInfo *areaInfo, APTR vectorBuffer, LONG maxVectors)` — LVO -282 (-$11A)
Registers: areaInfo=A0, vectorBuffer=A1, maxVectors=D0; no result

Initialise an AreaInfo structure to collect up to maxVectors fill vertices in a buffer.

- **areaInfo** — your `struct AreaInfo` (asm `ai_SIZEOF`).
- **vectorBuffer** — memory of at least 5 x maxVectors bytes (e.g. from exec AllocVec).
- **maxVectors** — capacity. Every AreaMove/AreaDraw point uses one vector, every AreaEllipse
  two; AreaMove may add one more to close the previous polygon.

After InitArea store the AreaInfo pointer in `rp->AreaInfo`.

### Example
```c
#define MAXVEC 32

/* filled, outlined triangle plus ellipse into rp (w x h = size of rp's BitMap) */
BOOL fill_shapes(struct RastPort *rp, UWORD w, UWORD h)
{
    struct AreaInfo ai;
    struct TmpRas tr;
    APTR vbuf = AllocVec(MAXVEC * 5, MEMF_ANY | MEMF_CLEAR);  /* 5 bytes per vector */
    PLANEPTR plane = AllocRaster(w, h);                         /* chip RAM TmpRas */
    BOOL ok = FALSE;

    if (vbuf && plane) {
        InitArea(&ai, vbuf, MAXVEC);
        InitTmpRas(&tr, plane, RASSIZE(w, h));
        rp->AreaInfo = &ai;
        rp->TmpRas = &tr;

        SetAPen(rp, 2);
        SetOutlinePen(rp, 1);                /* V39: border in pen 1, AREAOUTLINE on */
        AreaMove(rp, 10, 10);
        AreaDraw(rp, 100, 20);
        AreaDraw(rp, 50, 80);                /* polygon closed automatically */
        AreaEllipse(rp, 160, 60, 40, 25);
        ok = (AreaEnd(rp) == 0);
        BNDRYOFF(rp);

        WaitBlit();                          /* fill may still be running on the TmpRas */
        rp->AreaInfo = NULL;                 /* detach before freeing */
        rp->TmpRas = NULL;
    }
    if (plane)
        FreeRaster(plane, w, h);
    FreeVec(vbuf);                           /* NULL is allowed */
    return ok;
}
```

### Gotchas
- Size the table for the largest single fill; AreaMove/AreaDraw/AreaEllipse return -1 once it
  is full and the shape is silently incomplete.
- The AreaInfo and buffer must stay valid while `rp->AreaInfo` points at them (a stack
  AreaInfo is fine only if you clear the pointer before returning, as above).

**See also:** [InitTmpRas](#inittmpras), [AreaMove](#areamove), [AreaEnd](#areaend)

## InitTmpRas
`struct TmpRas * InitTmpRas(struct TmpRas *tmpRas, PLANEPTR buffer, LONG size)` — LVO -468 (-$1D4)
Registers: tmpRas=A0, buffer=A1, size=D0; result in D0

Set up a TmpRas structure describing a chip RAM scratch buffer for fills and flood fills.

- **tmpRas** — your `struct TmpRas` (asm `tr_SIZEOF`).
- **buffer** — contiguous chip RAM, e.g. from [AllocRaster](bitmaps-and-blits.md#allocraster).
- **size** — buffer size in bytes, e.g. `RASSIZE(width,height)`.
- **Result** — the NDK 3.9 prototype declares a `struct TmpRas *` result, the autodoc documents
  none; do not rely on it.

Store the TmpRas pointer in `rp->TmpRas`. Used by [AreaEnd](#areaend), [Flood](#flood) and, per the
autodoc, text rendering.

### Gotchas
- The buffer must be chip RAM: the blitter renders the fill mask into it.
- For [Flood](#flood) it must be at least one bitplane as large as the whole RastPort. For area
  fills one plane covering the filled area is enough (unverified); sizing it to the full
  BitMap (`RASSIZE(w,h)`) is always safe.
- One TmpRas cannot be shared by several RastPorts (autodoc BUGS).
- Set `rp->TmpRas = NULL` and [WaitBlit](blitter-and-timing.md#waitblit) before freeing the
  buffer.

**See also:** [InitArea](#initarea), [Flood](#flood), [AllocRaster](bitmaps-and-blits.md#allocraster)

## AreaMove
`LONG AreaMove(struct RastPort *rp, LONG x, LONG y)` — LVO -252 (-$FC)
Registers: rp=A1, x=D0, y=D1; result in D0

Close the current polygon (if any) and start a new one at (x,y) in the vector list.

- **rp** — RastPort with an initialised `AreaInfo`.
- **x**, **y** — start point.
- **Result** — 0 on success, -1 if the vector table is full.

### Example
```asm
; filled triangle; a1 = RastPort with AreaInfo and TmpRas attached; d0 = 0 ok, -1 error
FillTriangle:
        movem.l a2/a6,-(sp)
        move.l  _GfxBase,a6
        move.l  a1,a2
        moveq   #3,d0
        jsr     _LVOSetAPen(a6)         ; a1 = rp, d0 = pen
        move.l  a2,a1
        moveq   #10,d0
        moveq   #10,d1
        jsr     _LVOAreaMove(a6)
        tst.l   d0
        bne.s   .out
        move.l  a2,a1
        moveq   #100,d0
        moveq   #20,d1
        jsr     _LVOAreaDraw(a6)
        tst.l   d0
        bne.s   .out
        move.l  a2,a1
        moveq   #50,d0
        moveq   #80,d1
        jsr     _LVOAreaDraw(a6)
        tst.l   d0
        bne.s   .out
        move.l  a2,a1
        jsr     _LVOAreaEnd(a6)         ; fill; d0 = 0 or -1
.out:   movem.l (sp)+,a2/a6
        rts
```

### Gotchas
- A1 (the RastPort) is a scratch register: reload it before every call.
- Closing the previous polygon can consume an extra vector.

**See also:** [AreaDraw](#areadraw), [AreaEnd](#areaend), [InitArea](#initarea)

## AreaDraw
`LONG AreaDraw(struct RastPort *rp, LONG x, LONG y)` — LVO -258 (-$102)
Registers: rp=A1, x=D0, y=D1; result in D0

Add a corner point to the current polygon in the vector list.

- **rp** — RastPort with an initialised `AreaInfo`.
- **x**, **y** — next vertex.
- **Result** — 0 on success, -1 if the vector table is full.

### Gotchas
- Nothing is drawn until [AreaEnd](#areaend); there is no need to repeat the first point, the
  polygon is closed automatically.

**See also:** [AreaMove](#areamove), [AreaEnd](#areaend)

## AreaEllipse
`LONG AreaEllipse(struct RastPort *rp, LONG xCenter, LONG yCenter, LONG a, LONG b)` — LVO -186 (-$BA)
Registers: rp=A1, xCenter=D0, yCenter=D1, a=D2, b=D3; result in D0

Add a filled ellipse (centre plus horizontal and vertical radius) to the vector list.

- **rp** — RastPort with an initialised `AreaInfo`.
- **xCenter**, **yCenter** — centre.
- **a** — horizontal radius, must be > 0.
- **b** — vertical radius, must be > 0.
- **Result** — 0 on success, -1 if the vector table is full.

### Gotchas
- Uses two vectors of the table per call.
- For a circle use the [AreaCircle](#areacircle) macro (C) or pass a = b.

**See also:** [AreaCircle](#areacircle), [AreaEnd](#areaend), [DrawEllipse](drawing.md#drawellipse)

## AreaEnd
`LONG AreaEnd(struct RastPort *rp)` — LVO -264 (-$108)
Registers: rp=A1; result in D0

Fill all collected polygons and ellipses into the RastPort, then reset the vector list.

- **rp** — RastPort with `AreaInfo` and `TmpRas` attached.
- **Result** — 0 on success, -1 on any error.

The fill uses the A pen, B pen, draw mode and area pattern ([SetAfPt](rastport-attrs.md#setafpt));
when `AREAOUTLINE` is set ([SetOutlinePen](rastport-attrs.md#setoutlinepen) /
[SetOPen](rastport-attrs.md#setopen)) the shapes get a border in the outline pen. The
TmpRas holds the fill mask. The list is emptied afterwards, ready for the next AreaMove.

### Gotchas
- The fill mask is built in the TmpRas: attach one big enough before calling, and check for -1
  (behaviour without a TmpRas is undocumented).
- Outline mode stays on until [BNDRYOFF](rastport-attrs.md#bndryoff).
- May leave the blitter running: [WaitBlit](blitter-and-timing.md#waitblit) before freeing the
  TmpRas or reading pixels.

**See also:** [InitArea](#initarea), [InitTmpRas](#inittmpras), [AreaMove](#areamove),
[AreaEllipse](#areaellipse), [BltPattern](drawing.md#bltpattern)

## Flood
`BOOL Flood(struct RastPort *rp, ULONG mode, LONG x, LONG y)` — LVO -330 (-$14A)
Registers: rp=A1, mode=D2, x=D0, y=D1; result in D0

Seed-fill an area starting at (x,y), bounded by the outline pen or by a colour change.

- **rp** — RastPort with a `TmpRas` at least as large as the whole RastPort.
- **mode** — 0: fill all connected pixels that are NOT the outline pen colour (`AOlPen`, set with
  [SetOutlinePen](rastport-attrs.md#setoutlinepen)); 1: fill connected pixels that have the same
  colour as the pixel at (x,y).
- **x**, **y** — seed point.
- **Result** — BOOL; the autodoc does not document its meaning (it names it "error").

The fill itself follows the normal area-fill rules (A pen, draw mode, area pattern).

### Example
```c
/* paint-bucket: replace the region of equal colour under (x,y) with pen */
void bucket(struct RastPort *rp, WORD x, WORD y, ULONG pen)
{
    SetAPen(rp, pen);
    Flood(rp, 1, x, y);       /* rp->TmpRas must cover the whole RastPort */
    WaitBlit();
}
```

### Gotchas
- Asm register order is unusual: mode in D2, x in D0, y in D1, rp in A1.
- Mode 0 runs until it meets the outline pen colour; if the region is not closed in that colour
  the whole connected area floods.
- No TmpRas, or a smaller one, is not a valid setup (autodoc NOTES).

**See also:** [InitTmpRas](#inittmpras), [AreaEnd](#areaend), [SetOutlinePen](rastport-attrs.md#setoutlinepen)

## AreaCircle

Macro (graphics/gfxmacros.h) — not a library call; expands to AreaEllipse(rp,cx,cy,r,r).

`AreaCircle(rp,cx,cy,radius)` adds a circle to the area vector list; it costs two vectors like
[AreaEllipse](#areaellipse) and returns 0 or -1 the same way. The autodoc shows a register
synopsis, but there is no `_LVOAreaCircle`: in asm call `_LVOAreaEllipse` with D2 = D3 = radius.

**See also:** [AreaEllipse](#areaellipse), [AreaEnd](#areaend), [DrawCircle](drawing.md#drawcircle)
