# layers.library: creating and arranging layers

The life cycle of a private set of layers: [NewLayerInfo](#newlayerinfo), one or more
[CreateUpfrontLayer](#createupfrontlayer) / [CreateBehindLayer](#createbehindlayer) (or the V36
hook variants), render through `layer->rp`, rearrange with the Move/Size/Upfront/Behind calls,
repair simple-refresh damage with [BeginUpdate](#beginupdate) / [EndUpdate](#endupdate), then
[DeleteLayer](#deletelayer) every layer and [DisposeLayerInfo](#disposelayerinfo). Never use the
arranging calls on an Intuition window's layer: use the Intuition equivalents. Rectangles are
inclusive BitMap coordinates; structures and flags: [concepts.md](concepts.md).

Every call that changes the arrangement returns FALSE when it runs out of memory (the operation is
then not done) and may generate damage in other simple-refresh layers of the same Layer_Info.

## NewLayerInfo
`struct Layer_Info * NewLayerInfo(VOID)` — LVO -144 (-$90)
Registers: none; result in D0

Allocate and initialise a Layer_Info, unlocked and ready for layers.

- **Result** — the Layer_Info, or NULL if there is not enough memory.

### Example
```asm
; create a Layer_Info with one simple-refresh layer covering a 320x256 BitMap
        include "graphics/layers.i"
        include "graphics/clip.i"
        include "lvo/layers_lib.i"

        movem.l d2-d4/a2,-(sp)
        move.l  _LayersBase,a6
        jsr     _LVONewLayerInfo(a6)
        move.l  d0,layerinfo
        beq.s   .fail
        move.l  d0,a0                   ; li
        move.l  bitmap,a1               ; shared BitMap
        moveq   #0,d0                   ; x0
        moveq   #0,d1                   ; y0
        move.l  #319,d2                 ; x1 (inclusive)
        move.l  #255,d3                 ; y1 (inclusive)
        moveq   #LAYERSIMPLE,d4
        sub.l   a2,a2                   ; no SuperBitMap
        jsr     _LVOCreateUpfrontLayer(a6)
        move.l  d0,layer
        beq.s   .nolayer
        move.l  d0,a0
        move.l  lr_rp(a0),rastport      ; render through this RastPort
        ; ...
.nolayer:
.fail:  movem.l (sp)+,d2-d4/a2
        rts
```

**See also:** [DisposeLayerInfo](#disposelayerinfo), [CreateUpfrontLayer](#createupfrontlayer), [InstallLayerInfoHook](clipping.md#installlayerinfohook)

## DisposeLayerInfo
`VOID DisposeLayerInfo(struct Layer_Info *li)` — LVO -150 (-$96)
Registers: li=A0; no result

Free a Layer_Info from NewLayerInfo and everything attached to it.

- **li** — Layer_Info from [NewLayerInfo](#newlayerinfo).

### Gotchas
- Delete every layer of this Layer_Info with [DeleteLayer](#deletelayer) first; for SuperBitMap
  layers keep your own pointer to the SuperBitMap, it is not freed.
- Never for an Intuition screen's embedded `LayerInfo`.

**See also:** [NewLayerInfo](#newlayerinfo), [DeleteLayer](#deletelayer)

## CreateUpfrontLayer
`struct Layer * CreateUpfrontLayer(struct Layer_Info *li, struct BitMap *bm, LONG x0, LONG y0, LONG x1, LONG y1, LONG flags, struct BitMap *bm2)` — LVO -36 (-$24)
Registers: li=A0, bm=A1, x0=D0, y0=D1, x1=D2, y1=D3, flags=D4, bm2=A2; result in D0

Create a layer in front of all existing layers of a Layer_Info.

- **li** — Layer_Info from [NewLayerInfo](#newlayerinfo).
- **bm** — the BitMap all layers of this Layer_Info share (the display or an off-screen BitMap).
- **x0, y0** — upper-left corner in `bm`; **x1, y1** — lower-right corner, inclusive.
- **flags** — exactly one of `LAYERSIMPLE` (1), `LAYERSMART` (2), or `LAYERSMART|LAYERSUPER` (6);
  optionally `LAYERBACKDROP` ($40).
- **bm2** — for `LAYERSUPER`: your SuperBitMap, at least as large as the layer; its contents are
  copied into the display. Otherwise NULL.
- **Result** — the new Layer (render through `layer->rp`), or NULL on failure.

The layer gets the default backfill hook (clearing). Use
[CreateUpfrontHookLayer](#createupfronthooklayer) to choose another.

### Example
```c
#include <proto/layers.h>
#include <proto/graphics.h>
#include <graphics/layers.h>
#include <graphics/clip.h>

extern struct Library *LayersBase;
extern struct GfxBase *GfxBase;

/* a 100x50 smart-refresh panel at (20,30) in bm, filled with pen 2 */
struct Layer *OpenPanel(struct Layer_Info *li, struct BitMap *bm)
{
    struct Layer *l = CreateUpfrontLayer(li, bm, 20, 30, 20 + 100 - 1, 30 + 50 - 1,
                                         LAYERSMART, NULL);
    if (l != NULL) {
        SetAPen(l->rp, 2);
        RectFill(l->rp, 0, 0, 99, 49);          /* layer-relative coordinates */
    }
    return l;
}
```

### Gotchas
- With `LAYERSUPER` always set `LAYERSMART` too (autodoc).
- Keep the rectangle inside `bm`: the move/scroll calls document that they may not handle
  positions outside the BitMap.

**See also:** [CreateBehindLayer](#createbehindlayer), [CreateUpfrontHookLayer](#createupfronthooklayer), [DeleteLayer](#deletelayer)

## CreateBehindLayer
`struct Layer * CreateBehindLayer(struct Layer_Info *li, struct BitMap *bm, LONG x0, LONG y0, LONG x1, LONG y1, LONG flags, struct BitMap *bm2)` — LVO -42 (-$2A)
Registers: li=A0, bm=A1, x0=D0, y0=D1, x1=D2, y1=D3, flags=D4, bm2=A2; result in D0

Create a layer behind the existing layers of a Layer_Info.

- **li, bm, x0, y0, x1, y1, flags, bm2** — as for [CreateUpfrontLayer](#createupfrontlayer).
- **Result** — the new Layer, or NULL on failure.

Placement: a backdrop layer goes behind ALL layers, backdrop ones included; a non-backdrop layer
goes behind the other non-backdrop layers but in front of the backdrop ones.

**See also:** [CreateUpfrontLayer](#createupfrontlayer), [CreateBehindHookLayer](#createbehindhooklayer), [DeleteLayer](#deletelayer)

## CreateUpfrontHookLayer
`struct Layer * CreateUpfrontHookLayer(struct Layer_Info *li, struct BitMap *bm, LONG x0, LONG y0, LONG x1, LONG y1, LONG flags, struct Hook *hook, struct BitMap *bm2)` — LVO -186 (-$BA)
Registers: li=A0, bm=A1, x0=D0, y0=D1, x1=D2, y1=D3, flags=D4, hook=A3, bm2=A2; result in D0

Create a layer in front of all others, with a chosen backfill hook.

- **li, bm, x0, y0, x1, y1, flags, bm2** — as for [CreateUpfrontLayer](#createupfrontlayer).
- **hook** — backfill Hook installed as `layer->BackFill` (message layout in
  [concepts.md](concepts.md#backfill-hooks)); `LAYERS_BACKFILL` (0) for the default fill;
  `LAYERS_NOBACKFILL` (1) for no fill (V39).
- **Result** — the new Layer, or NULL on failure.

Since V36.

### Gotchas
- `hook` goes in **A3** and `bm2` in A2.
- The Hook must stay valid until the layer is deleted or the hook replaced.

**See also:** [InstallLayerHook](clipping.md#installlayerhook), [CreateBehindHookLayer](#createbehindhooklayer), [DeleteLayer](#deletelayer)

## CreateBehindHookLayer
`struct Layer * CreateBehindHookLayer(struct Layer_Info *li, struct BitMap *bm, LONG x0, LONG y0, LONG x1, LONG y1, LONG flags, struct Hook *hook, struct BitMap *bm2)` — LVO -192 (-$C0)
Registers: li=A0, bm=A1, x0=D0, y0=D1, x1=D2, y1=D3, flags=D4, hook=A3, bm2=A2; result in D0

Create a layer behind the others, with a chosen backfill hook.

- **li, bm, x0, y0, x1, y1, flags, bm2** — as for [CreateUpfrontLayer](#createupfrontlayer);
  placement as for [CreateBehindLayer](#createbehindlayer).
- **hook** — as for [CreateUpfrontHookLayer](#createupfronthooklayer).
- **Result** — the new Layer, or NULL on failure.

Since V36.

**See also:** [CreateUpfrontHookLayer](#createupfronthooklayer), [InstallLayerHook](clipping.md#installlayerhook), [DeleteLayer](#deletelayer)

## DeleteLayer
`LONG DeleteLayer(LONG dummy, struct Layer *layer)` — LVO -90 (-$5A)
Registers: dummy=A0, layer=A1; result in D0

Remove a layer, free its memory and repair the layers it was covering.

- **dummy** — unused, pass 0.
- **layer** — layer to delete (A1).
- **Result** — TRUE if deleted, FALSE if not (probably out of memory).

Uncovered areas are refreshed (damage in simple-refresh layers, Layer_Info backfill where no layer
remains). A SuperBitMap is brought up to date and left to you.

### Gotchas
- Remove any installed clip region first: `InstallClipRegion(layer, NULL)` (autodoc of
  [InstallClipRegion](clipping.md#installclipregion)).
- Not for Intuition windows: CloseWindow does it.
- Check the result: on FALSE the layer still exists.

**See also:** [CreateUpfrontLayer](#createupfrontlayer), [DisposeLayerInfo](#disposelayerinfo)

## UpfrontLayer
`LONG UpfrontLayer(LONG dummy, struct Layer *layer)` — LVO -48 (-$30)
Registers: dummy=A0, layer=A1; result in D0

Bring a layer in front of all other layers.

- **dummy** — unused, pass 0.
- **layer** — non-backdrop layer (A1). A backdrop layer can be brought fully to the front only by
  clearing `LAYERBACKDROP` in its Flags first (autodoc).
- **Result** — TRUE on success, FALSE if out of memory.

Obscured parts are swapped in; damage is collected where needed.

**See also:** [BehindLayer](#behindlayer), [MoveLayerInFrontOf](#movelayerinfrontof)

## BehindLayer
`LONG BehindLayer(LONG dummy, struct Layer *layer)` — LVO -54 (-$36)
Registers: dummy=A0, layer=A1; result in D0

Send a layer behind the other layers.

- **dummy** — unused, pass 0.
- **layer** — layer to move (A1). A backdrop layer goes behind all other backdrop layers; a normal
  layer goes behind all normal layers, just in front of the frontmost backdrop layer.
- **Result** — TRUE on success, FALSE if out of memory.

Revealed simple-refresh layers get damage and `LAYERREFRESH`.

**See also:** [UpfrontLayer](#upfrontlayer), [MoveLayerInFrontOf](#movelayerinfrontof)

## MoveLayerInFrontOf
`LONG MoveLayerInFrontOf(struct Layer *layer_to_move, struct Layer *other_layer)` — LVO -168 (-$A8)
Registers: layer_to_move=A0, other_layer=A1; result in D0

Place a layer directly in front of another layer.

- **layer_to_move** — layer to rearrange (A0).
- **other_layer** — target layer it should end up in front of (A1).
- **Result** — TRUE on success, FALSE if out of memory.

**See also:** [UpfrontLayer](#upfrontlayer), [BehindLayer](#behindlayer)

## MoveLayer
`LONG MoveLayer(LONG dummy, struct Layer *layer, LONG dx, LONG dy)` — LVO -60 (-$3C)
Registers: dummy=A0, layer=A1, dx=D0, dy=D1; result in D0

Move a non-backdrop layer by a relative offset within the shared BitMap.

- **dummy** — unused, pass 0.
- **layer** — non-backdrop layer (A1).
- **dx, dy** — pixels to add to the position.
- **Result** — TRUE on success, FALSE if out of memory.

### Gotchas
- Moving any part of the layer outside the BitMap bounds may not be handled (autodoc BUGS): clamp
  the deltas yourself.

**See also:** [SizeLayer](#sizelayer), [MoveSizeLayer](#movesizelayer)

## SizeLayer
`LONG SizeLayer(LONG dummy, struct Layer *layer, LONG dx, LONG dy)` — LVO -66 (-$42)
Registers: dummy=A0, layer=A1, dx=D0, dy=D1; result in D0

Grow or shrink a non-backdrop layer by moving its lower-right corner.

- **dummy** — unused, pass 0.
- **layer** — non-backdrop layer (A1).
- **dx, dy** — pixels to add to width and height (negative shrinks).
- **Result** — TRUE on success, FALSE if out of memory.

SuperBitMap layers copy pixels between the display and the SuperBitMap as the layer changes size.

**See also:** [MoveLayer](#movelayer), [MoveSizeLayer](#movesizelayer)

## MoveSizeLayer
`LONG MoveSizeLayer(struct Layer *layer, LONG dx, LONG dy, LONG dw, LONG dh)` — LVO -180 (-$B4)
Registers: layer=A0, dx=D0, dy=D1, dw=D2, dh=D3; result in D0

Move the upper-left corner and change the size of a layer in one operation.

- **layer** — non-backdrop layer (A0; no dummy argument).
- **dx, dy** — offset added to the upper-left corner.
- **dw, dh** — change of width and height.
- **Result** — TRUE on success; FALSE if out of memory or the new bounds are illegal.

Since V36.

### Gotchas
- The autodoc INPUTS still list `dummy` and `l`: ignore that, the prototype and registers above are
  correct (layer in A0).

**See also:** [MoveLayer](#movelayer), [SizeLayer](#sizelayer)

## ScrollLayer
`VOID ScrollLayer(LONG dummy, struct Layer *layer, LONG dx, LONG dy)` — LVO -72 (-$48)
Registers: dummy=A0, layer=A1, dx=D0, dy=D1; no result

Scroll a SuperBitMap layer's view, or offset the coordinates of a normal layer.

- **dummy** — unused, pass 0.
- **layer** — layer to scroll (A1).
- **dx, dy** — amounts added to `Scroll_X`, `Scroll_Y`.

For a SuperBitMap layer the SuperBitMap is updated from the display and the layer then shows a
different part of it. For other layers nothing is copied: only the coordinate offset changes, so
`ScrollLayer(0, l, -3, -10)` makes rendering at (0,0) appear at (3,10). Combined with
InstallClipRegion this imitates a GimmeZeroZero window without a second layer.

### Gotchas
- Scrolling a SuperBitMap view past the SuperBitMap edges may not be handled (autodoc BUGS).

**See also:** [CreateUpfrontLayer](#createupfrontlayer), [InstallClipRegion](clipping.md#installclipregion)

## BeginUpdate
`LONG BeginUpdate(struct Layer *l)` — LVO -78 (-$4E)
Registers: l=A0; result in D0

Start repairing a layer: rendering is clipped to its damaged areas only.

- **l** — layer with damage (`LAYERREFRESH` set in `Flags`).
- **Result** — TRUE: the damage list now acts as the ClipRect list and the layer is locked against
  layer changes; FALSE: the conversion failed (probably out of memory).

Always followed by [EndUpdate](#endupdate), also after FALSE.

### Example
```c
#include <proto/layers.h>
#include <graphics/layers.h>
#include <graphics/clip.h>

extern struct Library *LayersBase;

void RepairLayer(struct Layer *l, void (*redraw)(struct RastPort *))
{
    if (l->Flags & LAYERREFRESH) {
        if (BeginUpdate(l)) {
            redraw(l->rp);              /* draw everything; only damage gets touched */
            EndUpdate(l, TRUE);         /* damage repaired: clear the damage list */
        } else {
            EndUpdate(l, FALSE);        /* restore state, keep the damage for later */
        }
    }
}
```

### Gotchas
- On FALSE do not render; call `EndUpdate(l, FALSE)` (autodoc BUGS).
- Intuition windows: use BeginRefresh/EndRefresh instead.
- Between BeginUpdate and EndUpdate only render; no layer operations, no Intuition calls.

**See also:** [EndUpdate](#endupdate), [LockLayerInfo](locking.md#locklayerinfo)

## EndUpdate
`VOID EndUpdate(struct Layer *layer, ULONG flag)` — LVO -84 (-$54)
Registers: layer=A0, flag=D0; no result

Finish a BeginUpdate: restore the normal ClipRects and unlock the layer.

- **layer** — the layer passed to [BeginUpdate](#beginupdate).
- **flag** — TRUE: the repair is complete, the damage list is cleared. FALSE: partial repair, the
  damage list is kept (you may trim it yourself with the graphics region calls).

Multi-pass refresh = several BeginUpdate / EndUpdate(FALSE) pairs and a final EndUpdate(TRUE).

**See also:** [BeginUpdate](#beginupdate)

## WhichLayer
`struct Layer * WhichLayer(struct Layer_Info *li, LONG x, LONG y)` — LVO -132 (-$84)
Registers: li=A0, x=D0, y=D1; result in D0

Return the frontmost layer containing a BitMap point.

- **li** — Layer_Info to search (for a screen: `&screen->LayerInfo`).
- **x, y** — point in BitMap (screen) coordinates. The autodoc and SFD type them WORD: pass
  sign-extended longs.
- **Result** — the topmost layer containing the point, or NULL if no layer covers it.

### Example
```c
#include <proto/layers.h>
#include <intuition/screens.h>
#include <graphics/clip.h>

extern struct Library *LayersBase;

/* is the pointer over a layer other than 'mine'? */
BOOL PointerOverOther(struct Screen *scr, struct Layer *mine)
{
    struct Layer *l;
    BOOL other;

    LockLayerInfo(&scr->LayerInfo);
    l = WhichLayer(&scr->LayerInfo, scr->MouseX, scr->MouseY);
    other = (l != NULL && l != mine);
    UnlockLayerInfo(&scr->LayerInfo);
    return other;
}
```

### Gotchas
- The result is only stable while you hold [LockLayerInfo](locking.md#locklayerinfo): another task
  may move or delete the layer at any time.

**See also:** [LockLayerInfo](locking.md#locklayerinfo)
