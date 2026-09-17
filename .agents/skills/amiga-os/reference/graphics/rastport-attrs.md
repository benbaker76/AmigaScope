# graphics.library: RastPort attributes

A RastPort holds the rendering state every drawing call uses: target BitMap (and Layer),
primary pen (`FgPen`, "A pen"), secondary pen (`BgPen`, "B pen"), area outline pen (`AOlPen`,
"O pen"), draw mode, write mask, line and area patterns, font. Set it up with
[InitRastPort](#initrastport), then change it with the setters below. From V39 use the
Get/Set functions instead of reading or poking the fields, and prefer
[SetABPenDrMd](#setabpendrmd) or [SetRPAttrsA](#setrpattrsa) to set several values at once.
The gfxmacros.h macros at the end poke fields directly and are the pre-V39 way. Asm: the
V39 getters and SetOutlinePen/SetWriteMask/SetMaxPen/Set/GetRPAttrsA take the RastPort in
**A0**, the old setters in **A1**. See [RastPort basics](concepts.md#rastport-basics) and
[drawing modes](concepts.md#drawing-modes).

## InitRastPort
`VOID InitRastPort(struct RastPort *rp)` — LVO -198 (-$C6)
Registers: rp=A1; no result

Initialise a caller-allocated RastPort to default rendering values.

- **rp** — your `struct RastPort` (C `sizeof` 100 bytes, asm `rp_SIZEOF`).

Afterwards everything is zero except: `Mask`, `FgPen`, `AOlPen` and `LinePtrn` = -1 (all bits),
`DrawMode` = `JAM2`, `Font` = the default system font. `BitMap` is NOT set: store your BitMap
pointer yourself before drawing.

### Example
```c
/* RastPort for drawing into an off-screen BitMap */
void init_offscreen_rp(struct RastPort *rp, struct BitMap *bm)
{
    InitRastPort(rp);
    rp->BitMap = bm;                  /* InitRastPort leaves this NULL */
    SetABPenDrMd(rp, 1, 0, JAM1);     /* V39; else SetAPen/SetBPen/SetDrMd */
}
```

```asm
; a0 = BitMap; out: a0 = RastPort ready to draw into it
SetupRP:
        movem.l d2/a2/a6,-(sp)
        move.l  _GfxBase,a6
        move.l  a0,a2
        lea     MyRP,a1
        jsr     _LVOInitRastPort(a6)
        lea     MyRP,a1
        move.l  a2,rp_BitMap(a1)
        moveq   #1,d0                   ; A pen
        moveq   #0,d1                   ; B pen
        moveq   #RP_JAM1,d2             ; draw mode
        jsr     _LVOSetABPenDrMd(a6)    ; V39+, rp in a1
        lea     MyRP,a0
        movem.l (sp)+,d2/a2/a6
        rts

        section rpbss,bss
MyRP:   ds.b    rp_SIZEOF
```

### Gotchas
- Only defaults are set; there is no Layer, so no clipping: coordinates outside the BitMap write
  outside its planes. Clip yourself or use a layered RastPort (window).
- No AreaInfo/TmpRas is attached: area fills and Flood need
  [InitArea](area-fill.md#initarea) and [InitTmpRas](area-fill.md#inittmpras) first.

**See also:** [SetABPenDrMd](#setabpendrmd), [SetFont](text-and-fonts.md#setfont),
[InitTmpRas](area-fill.md#inittmpras), [concepts](concepts.md#rastport-basics)

## SetAPen
`VOID SetAPen(struct RastPort *rp, ULONG pen)` — LVO -342 (-$156)
Registers: rp=A1, pen=D0; no result

Set the primary (A / foreground) pen used for lines, fills and text.

- **rp** — RastPort.
- **pen** — pen number 0-255.

Also recomputes the RastPort minterms and restarts the line pattern.

### Example
```asm
; set pen 3 (asm: rp in a1, pen in d0)
SetPen3:
        move.l  a6,-(sp)
        move.l  _GfxBase,a6
        move.l  RPPtr,a1
        moveq   #3,d0
        jsr     _LVOSetAPen(a6)
        move.l  (sp)+,a6
        rts
RPPtr:  dc.l    0
```

### Gotchas
- Setting A pen, B pen and draw mode in three calls regenerates the minterms three times; on
  V39+ use [SetABPenDrMd](#setabpendrmd).
- Poking `rp->FgPen` directly skips the minterm update: rendering then uses stale state.

**See also:** [SetBPen](#setbpen), [GetAPen](#getapen), [SetABPenDrMd](#setabpendrmd)

## SetBPen
`VOID SetBPen(struct RastPort *rp, ULONG pen)` — LVO -348 (-$15C)
Registers: rp=A1, pen=D0; no result

Set the secondary (B / background) pen used by JAM2 text, patterns and line gaps.

- **rp** — RastPort.
- **pen** — pen number 0-255.

Also recomputes the minterms and restarts the line pattern.

### Gotchas
- The B pen only shows in `JAM2` mode (text background, zero bits of line/area patterns) and
  as the fill colour of the area vacated by [ScrollRaster](drawing.md#scrollraster).

**See also:** [SetAPen](#setapen), [GetBPen](#getbpen), [SetABPenDrMd](#setabpendrmd)

## SetDrMd
`VOID SetDrMd(struct RastPort *rp, ULONG drawMode)` — LVO -354 (-$162)
Registers: rp=A1, drawMode=D0; no result

Set the drawing mode for lines, fills and text.

- **rp** — RastPort.
- **drawMode** — `JAM1` (0), `JAM2` (1), `COMPLEMENT` (2), optionally ORed with `INVERSVID` (4)
  (graphics/rastport.h; asm `RP_JAM1`, `RP_JAM2`, `RP_COMPLEMENT`, `RP_INVERSVID` in
  rastport.i). Values 0-255 are accepted; odd combinations are not meaningful.

Also recomputes the minterms and restarts the line pattern. Mode meanings:
[drawing modes](concepts.md#drawing-modes).

### Example
```c
/* toggle a highlight: call twice to restore the original pixels */
void toggle_highlight(struct RastPort *rp, WORD x0, WORD y0, WORD x1, WORD y1)
{
    SetDrMd(rp, COMPLEMENT);
    RectFill(rp, x0, y0, x1, y1);
    SetDrMd(rp, JAM2);
}
```

### Gotchas
- `COMPLEMENT` with RectFill inverts all bitplanes, not just those set in the pen (RectFill BUGS).
- Asm names carry the `RP_` prefix; plain `JAM1` etc. are C only.

**See also:** [SetABPenDrMd](#setabpendrmd), [GetDrMd](#getdrmd),
[drawing modes](concepts.md#drawing-modes)

## SetABPenDrMd
`VOID SetABPenDrMd(struct RastPort *rp, ULONG apen, ULONG bpen, ULONG drawmode)` — LVO -894 (-$37E)
Registers: rp=A1, apen=D0, bpen=D1, drawmode=D2; no result

Set A pen, B pen and draw mode in one call, far faster than three separate calls.

- **rp** — RastPort.
- **apen** — primary pen.
- **bpen** — secondary pen.
- **drawmode** — `JAM1`/`JAM2`/`COMPLEMENT` [| `INVERSVID`].

Minterms are regenerated once, or not at all when nothing changed.

Since V39.

### Example
```c
void text_colours(struct RastPort *rp)
{
    SetABPenDrMd(rp, 2, 0, JAM2);     /* pen 2 text on pen 0 background */
}
```

### Gotchas
- Because unchanged values are skipped, a RastPort whose fields were poked directly may not get
  its minterms rebuilt -- never mix poking with this call.
- V39+. On V37 call SetAPen, SetBPen and SetDrMd.

**See also:** [SetAPen](#setapen), [SetBPen](#setbpen), [SetDrMd](#setdrmd),
[SetRPAttrsA](#setrpattrsa)

## GetAPen
`ULONG GetAPen(struct RastPort *rp)` — LVO -858 (-$35A)
Registers: rp=A0; result in D0

Return the current primary (A) pen of a RastPort.

- **rp** — RastPort.
- **Result** — pen number (ULONG).

Since V39.

### Example
```c
ULONG current_apen(struct RastPort *rp)
{
    if (GfxBase->LibNode.lib_Version >= 39)
        return GetAPen(rp);
    return (UBYTE)rp->FgPen;          /* V37 and older: read the field */
}
```

### Gotchas
- Asm: rp goes in A0 (the setter SetAPen takes A1).
- Use instead of reading `rp->FgPen`; future devices may store pens differently.

**See also:** [SetAPen](#setapen), [GetBPen](#getbpen), [GetRPAttrsA](#getrpattrsa)

## GetBPen
`ULONG GetBPen(struct RastPort *rp)` — LVO -864 (-$360)
Registers: rp=A0; result in D0

Return the current secondary (B) pen of a RastPort.

- **rp** — RastPort.
- **Result** — pen number (ULONG).

Since V39.

### Gotchas
- Asm: rp in A0. Pre-V39: read `(UBYTE)rp->BgPen`.

**See also:** [SetBPen](#setbpen), [GetAPen](#getapen)

## GetDrMd
`ULONG GetDrMd(struct RastPort *rp)` — LVO -870 (-$366)
Registers: rp=A0; result in D0

Return the current drawing mode of a RastPort.

- **rp** — RastPort.
- **Result** — draw mode bits (`JAM1`/`JAM2`/`COMPLEMENT`/`INVERSVID`).

Since V39.

### Gotchas
- Asm: rp in A0. Pre-V39: read `rp->DrawMode`.

**See also:** [SetDrMd](#setdrmd), [GetRPAttrsA](#getrpattrsa)

## SetOutlinePen
`ULONG SetOutlinePen(struct RastPort *rp, ULONG pen)` — LVO -978 (-$3D2)
Registers: rp=A0, pen=D0; result in D0

Set the area outline (O) pen and switch area-outline mode on.

- **rp** — RastPort.
- **pen** — outline pen number.
- **Result** — the previous outline pen.

The outline pen draws a border around fills done by [AreaEnd](area-fill.md#areaend) (and bounds
[Flood](area-fill.md#flood) mode 0). Sets `AREAOUTLINE` in `rp->Flags`; clear it again with
[BNDRYOFF](#bndryoff).

Since V39.

### Example
```c
void outlined_fills(struct RastPort *rp)
{
    ULONG old = SetOutlinePen(rp, 1);     /* V39: pen 1 border, outline on */
    /* ... AreaMove/AreaDraw/AreaEnd ... */
    SetOutlinePen(rp, old);
    BNDRYOFF(rp);                         /* outline mode off again */
}
```

### Gotchas
- Asm: rp in A0, pen in D0.
- V39+. For V37 use the [SetOPen](#setopen) macro, or
  [SafeSetOutlinePen](#safesetoutlinepen) to cover both.

**See also:** [GetOutlinePen](#getoutlinepen), [SetOPen](#setopen), [BNDRYOFF](#bndryoff),
[AreaEnd](area-fill.md#areaend)

## GetOutlinePen
`ULONG GetOutlinePen(struct RastPort *rp)` — LVO -876 (-$36C)
Registers: rp=A0; result in D0

Return the current area outline (O) pen of a RastPort.

- **rp** — RastPort.
- **Result** — outline pen number.

The NDK 3.9 autodoc documents this call under the name `GetOPen`; the LVO and prototype name is
GetOutlinePen (asm `_LVOGetOutlinePen`).

Since V39.

### Gotchas
- NDK 3.9 `graphics/gfxmacros.h` contains `#define GetOutlinePen(rp) GetOPen(rp)`, but no
  `GetOPen` prototype exists: with the pure NDK 3.9 headers, including gfxmacros.h turns every
  GetOutlinePen call into an undeclared function (gcc: implicit-declaration error, link failure).
  Bartman's m68k-amiga-elf sys-include reverses the macro (`#define GetOPen(rp)
  GetOutlinePen(rp)`), so both spellings work there. With the original NDK 3.9 headers put
  `#undef GetOutlinePen` after `#include <graphics/gfxmacros.h>`.
- Asm: rp in A0. Pre-V39: read `rp->AOlPen` (asm `rp_AOLPen`).

**See also:** [SetOutlinePen](#setoutlinepen), [GetOPen](#getopen)

## SetWriteMask
`ULONG SetWriteMask(struct RastPort *rp, ULONG msk)` — LVO -984 (-$3D8)
Registers: rp=A0, msk=D0; result in D0

Set the bitplane write mask: only planes whose mask bit is 1 are changed by rendering.

- **rp** — RastPort.
- **msk** — plane mask, bit n = plane n.
- **Result** — non-zero on success, 0 if the graphics device cannot mask individual bits.

Since V39.

### Example
```c
/* draw an overlay into planes 0-1 only, leaving planes 2+ untouched */
BOOL overlay_mode(struct RastPort *rp)
{
    return SetWriteMask(rp, 0x03) != 0;   /* 0 = not supported (e.g. chunky device) */
}
```

### Gotchas
- Asm: rp in A0, mask in D0.
- Check the result: on non-planar devices the mask is not honoured.
- V39+. For V37 use [SetWrMsk](#setwrmsk) (pokes `rp->Mask`) or
  [SafeSetWriteMask](#safesetwritemask).

**See also:** [SetMaxPen](#setmaxpen), [SetWrMsk](#setwrmsk), [SafeSetWriteMask](#safesetwritemask)

## SetMaxPen
`VOID SetMaxPen(struct RastPort *rp, ULONG maxpen)` — LVO -990 (-$3DE)
Registers: rp=A0, maxpen=D0; no result

Promise that no pen above maxpen will be rendered, allowing device speed-ups.

- **rp** — RastPort.
- **maxpen** — highest pen index you will draw with.

On planar displays this typically sets the write mask to the planes needed; where masking would
be slower (chunky devices) it does nothing.

Since V39.

### Gotchas
- maxpen must also cover the colours already in the area you draw over, not only the pens you
  draw with, or pixels of higher pens get corrupted.
- `SetMaxPen(rp, 0)` is meaningless.
- Asm: rp in A0.

**See also:** [SetWriteMask](#setwritemask), [SetRPAttrsA](#setrpattrsa)

## SetRPAttrsA
`VOID SetRPAttrsA(struct RastPort *rp, CONST struct TagItem *tags)` — LVO -1038 (-$40E)
Registers: rp=A0, tags=A1; no result

Change several RastPort settings from a tag list.

- **rp** — RastPort.
- **tags** — tag list (graphics/rpattr.h, asm rpattr.i):
  `RPTAG_Font` (`$80000000`, struct TextFont *), `RPTAG_APen` (`$80000002`),
  `RPTAG_BPen` (`$80000003`), `RPTAG_DrMd` (`$80000004`), `RPTAG_OutlinePen` (`$80000005`,
  old spelling `RPTAG_OutLinePen`, same value), `RPTAG_WriteMask` (`$80000006`),
  `RPTAG_MaxPen` (`$80000007`, see [SetMaxPen](#setmaxpen)). Varargs form: `SetRPAttrs()`.

The NDK 3.9 autodoc calls it `SetRPAttrA` ([stub](#setrpattra)).

### Example
```c
void setup_text_rp(struct RastPort *rp, struct TextFont *font)
{
    SetRPAttrs(rp, RPTAG_Font, (ULONG)font,
                   RPTAG_APen, 1,
                   RPTAG_BPen, 0,
                   RPTAG_DrMd, JAM2,
                   TAG_DONE);
}
```

### Gotchas
- The autodoc also lists `RPTAG_SoftStyle`, but no such constant exists in the NDK 3.9
  rpattr.h/rpattr.i; use [SetSoftStyle](text-and-fonts.md#setsoftstyle).
- Only present from V39 (listed under `==version 39` in graphics_lib.sfd); asm: rp in A0,
  tags in A1.

**See also:** [GetRPAttrsA](#getrpattrsa), [SetABPenDrMd](#setabpendrmd),
[SetFont](text-and-fonts.md#setfont)

## GetRPAttrsA
`VOID GetRPAttrsA(CONST struct RastPort *rp, CONST struct TagItem *tags)` — LVO -1044 (-$414)
Registers: rp=A0, tags=A1; no result

Read several RastPort settings through a tag list of result pointers.

- **rp** — RastPort to examine.
- **tags** — tag list; each `ti_Data` is a POINTER to a LONG that receives the value. Tags as
  for [SetRPAttrsA](#setrpattrsa) plus `RPTAG_DrawBounds` (`$80000008`, get only): `ti_Data`
  points to a `struct Rectangle` that receives the area rendering commands would currently
  touch; `MinX > MaxX` means there are no active ClipRects (nothing visible).

The NDK 3.9 autodoc calls it `GetRPAttrA` ([stub](#getrpattra)).

### Example
```c
/* skip redrawing a window whose rendering would be fully clipped */
BOOL anything_visible(struct RastPort *rp, LONG *apen)
{
    struct Rectangle r;
    GetRPAttrs(rp, RPTAG_APen, (ULONG)apen,
                   RPTAG_DrawBounds, (ULONG)&r,
                   TAG_DONE);
    return r.MinX <= r.MaxX;
}
```

### Gotchas
- Every value is written as a 32-bit LONG: pointing `ti_Data` at a UBYTE or WORD variable
  overwrites neighbouring memory.
- V39+ (sfd `==version 39`); asm: rp in A0, tags in A1.

**See also:** [SetRPAttrsA](#setrpattrsa), [GetAPen](#getapen), [GetDrMd](#getdrmd),
[GetOutlinePen](#getoutlinepen)

## GetRPAttrA

Autodoc spelling of GetRPAttrsA; no such symbol in NDK 3.9 protos or LVO includes.

Write [GetRPAttrsA](#getrpattrsa) (`_LVOGetRPAttrsA`) or the varargs `GetRPAttrs()`.

## SetRPAttrA

Autodoc spelling of SetRPAttrsA; no such symbol in NDK 3.9 protos or LVO includes.

Write [SetRPAttrsA](#setrpattrsa) (`_LVOSetRPAttrsA`) or the varargs `SetRPAttrs()`.

## SetOPen

Macro (graphics/gfxmacros.h) — not a library call; expands to AOlPen/AREAOUTLINE pokes.

`SetOPen(rp,pen)` stores `pen` in `rp->AOlPen` and sets `AREAOUTLINE` in `rp->Flags`, so
[AreaEnd](area-fill.md#areaend) draws a border in that pen. This is the pre-V39 form of
[SetOutlinePen](#setoutlinepen); pen is 0-255.

### Example
```asm
; asm equivalent of SetOPen(rp,1); a1 = RastPort
        move.b  #1,rp_AOLPen(a1)
        or.w    #RPF_AREAOUTLINE,rp_Flags(a1)
        rts
```

### Gotchas
- No minterm or device update; on V39+ call [SetOutlinePen](#setoutlinepen) instead
  ([SafeSetOutlinePen](#safesetoutlinepen) picks automatically).
- Turn outlining off with [BNDRYOFF](#bndryoff).

**See also:** [SetOutlinePen](#setoutlinepen), [BNDRYOFF](#bndryoff), [AreaEnd](area-fill.md#areaend)

## GetOPen

Macro (graphics/gfxmacros.h) — not a library call; expands to GetOutlinePen(rp).

`GetOPen` is the name the NDK 3.9 autodoc uses for [GetOutlinePen](#getoutlinepen) (V39). It is
a macro only in fixed headers such as Bartman's sys-include (`#define GetOPen(rp)
GetOutlinePen(rp)`). The original NDK 3.9 gfxmacros.h defines it the other way round and
declares no GetOPen function, so there `GetOPen()` does not exist and `GetOutlinePen()` breaks
once gfxmacros.h is included (see [GetOutlinePen](#getoutlinepen)). There is no `_LVOGetOPen`.

**See also:** [GetOutlinePen](#getoutlinepen), [SetOutlinePen](#setoutlinepen)

## SetDrPt

Macro (graphics/gfxmacros.h) — not a library call; expands to LinePtrn/Flags pokes.

`SetDrPt(rp,pattern)` sets `rp->LinePtrn` to the 16-bit line pattern, sets `FRST_DOT` in
`rp->Flags` and `rp->linpatcnt` = 15, so the next line starts at the pattern's top bit. 1 bits
draw in the A pen; 0 bits are skipped in `JAM1` or drawn in the B pen in `JAM2`. Used by
[Draw](drawing.md#draw), [PolyDraw](drawing.md#polydraw) and outlines. There is no library
function for this; `0xFFFF` restores solid lines.

### Example
```c
void dashed_line(struct RastPort *rp)
{
    SetDrPt(rp, 0xF0F0);          /* 4 pixels on, 4 off */
    Move(rp, 0, 50);
    Draw(rp, 319, 50);
    SetDrPt(rp, 0xFFFF);          /* solid again */
}
```

**See also:** [SetAfPt](#setafpt), [Draw](drawing.md#draw), [SetDrMd](#setdrmd)

## SetAfPt

Macro (graphics/gfxmacros.h) — not a library call; expands to AreaPtrn/AreaPtSz pokes.

`SetAfPt(rp,pattern,n)` sets `rp->AreaPtrn` to an array of 2^n UWORDs (16 pixels wide, 2^n rows
tall, repeated) and `rp->AreaPtSz` to n. [RectFill](drawing.md#rectfill),
[AreaEnd](area-fill.md#areaend) and [Flood](area-fill.md#flood) then fill through the pattern:
1 bits in the A pen, 0 bits left alone (`JAM1`) or in the B pen (`JAM2`).
`SetAfPt(rp,NULL,0)` returns to solid fills.

### Example
```c
static UWORD checker[] = { 0x5555, 0xAAAA };    /* 2^1 = 2 rows */

void checker_fill(struct RastPort *rp)
{
    SetAfPt(rp, checker, 1);
    RectFill(rp, 10, 10, 100, 60);
    SetAfPt(rp, NULL, 0);
}
```

### Gotchas
- n is the log2 of the row count, not the count: 4 rows is `n = 2`.
- A negative `AreaPtSz` selects a multicolour pattern with one 2^|n|-word block per bitplane
  (unverified -- not described in the NDK 3.9 includes or autodocs).
- The pattern must stay valid while the RastPort uses it; keep it in chip RAM if in doubt
  (whether graphics copies it before blitting is undocumented, unverified).

**See also:** [SetDrPt](#setdrpt), [RectFill](drawing.md#rectfill), [AreaEnd](area-fill.md#areaend)

## SetWrMsk

Macro (graphics/gfxmacros.h) — not a library call; expands to rp->Mask = m.

`SetWrMsk(rp,mask)` pokes the 8-bit plane write mask. Pre-V39 form of
[SetWriteMask](#setwritemask); on V39+ call the function (or
[SafeSetWriteMask](#safesetwritemask)) so devices can react and report failure.

**See also:** [SetWriteMask](#setwritemask), [SafeSetWriteMask](#safesetwritemask)

## BNDRYOFF

Macro (graphics/gfxmacros.h) — not a library call; expands to clearing AREAOUTLINE.

`BNDRYOFF(rp)` clears `AREAOUTLINE` in `rp->Flags`, so later [AreaEnd](area-fill.md#areaend)
fills get no border. There is no V39 function for this; use the macro with both
[SetOPen](#setopen) and [SetOutlinePen](#setoutlinepen). Asm:
`and.w #~RPF_AREAOUTLINE,rp_Flags(a1)`.

**See also:** [SetOutlinePen](#setoutlinepen), [SetOPen](#setopen)

## SafeSetOutlinePen

Macro (graphics/gfxmacros.h) — not a library call; expands to SetOPen or SetOutlinePen.

`SafeSetOutlinePen(rp,pen)` tests `GfxBase->LibNode.lib_Version`: below 39 it uses the
[SetOPen](#setopen) field pokes, otherwise it calls [SetOutlinePen](#setoutlinepen). Use it in C
code that must run on V37 and V39+. The previous pen is not returned.

### Gotchas
- Needs `GfxBase` declared as `struct GfxBase *` (true with `<proto/graphics.h>`) and
  `<graphics/gfxbase.h>` included.

**See also:** [SafeSetWriteMask](#safesetwritemask), [SetOutlinePen](#setoutlinepen)

## SafeSetWriteMask

Macro (graphics/gfxmacros.h) — not a library call; expands to SetWrMsk or SetWriteMask.

`SafeSetWriteMask(rp,mask)` uses the [SetWrMsk](#setwrmsk) poke when `GfxBase` is below V39 and
calls [SetWriteMask](#setwritemask) otherwise. The success result is discarded.

**See also:** [SafeSetOutlinePen](#safesetoutlinepen), [SetWriteMask](#setwritemask)
