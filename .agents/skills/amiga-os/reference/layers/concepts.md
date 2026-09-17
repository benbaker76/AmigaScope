# layers.library: concepts

How layers divide a BitMap, what the structures hold, how the refresh types differ, what backfill
hooks receive, and how all of this sits under Intuition windows. Structure offsets below were
checked by compiling against the NDK 3.9 headers (gcc `offsetof`) and assembling the NDK `.i`
files (vasm).

## Layer_Info and Layer

One **`struct Layer_Info`** (graphics/layers.h, layers.i) manages a set of layers that share one
BitMap: their front-to-back order, the lock that serialises layer operations, and the backfill
hook for areas no layer covers. Get it from [NewLayerInfo](layers.md#newlayerinfo); an Intuition
Screen embeds one (`Screen->LayerInfo`, asm `sc_LayerInfo`). Almost all of it is private:

| Offset | asm | C | Meaning |
|---|---|---|---|
| $00 | `li_top_layer` | `top_layer` | frontmost layer; follow `back` for the rest |
| $08 | `li_obs` | `obs` | (header gives no comment) |
| $18 | `li_Lock` | `Lock` | private SignalSemaphore, use [LockLayerInfo](locking.md#locklayerinfo) |
| $58 | `li_Flags` | `Flags` | `NEWLAYERINFO_CALLED` (1) when made by NewLayerInfo |
| $66 | `li_SIZEOF` | `sizeof` = 102 | never allocate one yourself: NewLayerInfo |

One **`struct Layer`** (graphics/clip.h, clip.i) per rectangle. Treat every field as read-only
and change layers only through the library:

| Offset | asm | C | Meaning |
|---|---|---|---|
| $00 | `lr_front` | `front` | next layer towards the viewer, NULL for the top one |
| $04 | `lr_back` | `back` | next layer further back, NULL for the last |
| $08 | `lr_ClipRect` | `ClipRect` | list of ClipRects graphics renders through |
| $0C | `lr_rp` | `rp` | the layer's RastPort: draw here |
| $10 | `lr_MinX` .. `lr_MaxY` | `bounds` | position in the shared BitMap, inclusive corners (WORDs) |
| $1E | `lr_Flags` | `Flags` | `LAYER*` flags (below) |
| $20 | `lr_SuperBitMap` | `SuperBitMap` | the SuperBitMap of a LAYERSUPER layer |
| $28 | `lr_Window` | `Window` | "reserved for user interface use": Intuition keeps the window there (unverified) |
| $2C | `lr_Scroll_X`, `lr_Scroll_Y` | `Scroll_X`, `Scroll_Y` | offset set by [ScrollLayer](layers.md#scrolllayer) |
| $44 | `lr_LayerInfo` | `LayerInfo` | owning Layer_Info |
| $48 | `lr_Lock` | `Lock` | the layer's SignalSemaphore, use [LockLayer](locking.md#locklayer) |
| $76 | `lr_BackFill` | `BackFill` | backfill Hook |
| $7E | `lr_ClipRegion` | `ClipRegion` | region set by [InstallClipRegion](clipping.md#installclipregion) |
| $9C | `lr_DamageList` | `DamageList` | Region of damage waiting for refresh |
| $A0 | `lr_SIZEOF` | `sizeof` = 160 | |

`Flags` (both include flavours): `LAYERSIMPLE` 1, `LAYERSMART` 2, `LAYERSUPER` 4, `LAYERUPDATING`
$10 (no header comment; by its name set during BeginUpdate/EndUpdate, unverified),
`LAYERBACKDROP` $40, `LAYERREFRESH` $80 (has damage to repair), `LAYER_CLIPRECTS_LOST` $100 (ran
out of memory building ClipRects), `LAYERIREFRESH` $200, `LAYERIREFRESH2` $400 (no comment in the
headers; Intuition-internal, unverified).

The asm include names the C `SuperSaveClipRects` field `lr_SuperSaverClipRects`; `lr_Front`,
`lr_Back`, `lr_RastPort` are old aliases for `lr_front`, `lr_back`, `lr_rp`.

Coordinates: the create/move calls and `bounds` use BitMap coordinates; drawing through
`layer->rp` uses coordinates relative to the layer's top-left corner, so (0,0) is `bounds.MinX`,
`bounds.MinY` (minus `Scroll_X`/`Scroll_Y` once scrolled).

## ClipRects and damage

A layer's visible shape is kept as a linked list of `struct ClipRect` (`Next` $00, `BitMap` $0C,
`bounds` $10..$16). graphics.library walks that list for every call on a layered RastPort, so the
program never sees it. The parts hidden behind other layers are either skipped, stored off-screen
or taken from a SuperBitMap, depending on the refresh type. ClipRects allocated by layers are
bigger than `struct ClipRect` (asm `cr_SIZEOF` 40 includes a private `cr_Flags`, the C struct is 36
bytes without `NEWCLIPRECTS_1_1`): never declare ClipRects of your own.

When a hidden area of a layer becomes visible and its pixels were not kept, layers adds the area
to `DamageList` and sets `LAYERREFRESH`. The owner repairs it with
[BeginUpdate](layers.md#beginupdate) (rendering is now clipped to the damage only), redraws, then
[EndUpdate](layers.md#endupdate)`(layer, TRUE)`. Intuition turns this into
`IDCMP_REFRESHWINDOW` + BeginRefresh/EndRefresh for windows.

## Refresh types

| Flags | Hidden parts | Owner must |
|---|---|---|
| `LAYERSIMPLE` | discarded | redraw damage after every uncover, move or size |
| `LAYERSMART` | saved in off-screen bitmaps by layers | redraw only newly created area (e.g. after growing) |
| `LAYERSMART` + `LAYERSUPER`, SuperBitMap passed as `bm2` | kept in your full-size SuperBitMap | nothing; synchronise with graphics SyncSBitMap/CopySBitMap before reading it |

- Simple refresh costs no memory but needs a redraw routine; smart refresh costs memory
  proportional to the obscured area and depth, and every depth-arrange copies pixels.
- The autodocs require `LAYERSMART` whenever `LAYERSUPER` is used.
- `LAYERBACKDROP` layers stay behind all non-backdrop layers
  ([BehindLayer](layers.md#behindlayer), [CreateBehindLayer](layers.md#createbehindlayer)).
  [MoveLayer](layers.md#movelayer), [SizeLayer](layers.md#sizelayer) and
  [UpfrontLayer](layers.md#upfrontlayer) are documented for non-backdrop layers.
- Any layer operation can generate damage in OTHER simple-refresh layers of the same Layer_Info.

## Backfill hooks

Areas of a layer that must be cleared (uncovered simple-refresh damage, graphics EraseRect and
ScrollRasterBF, and presumably a newly created layer, unverified) are filled by the layer's
backfill Hook; areas not covered by any layer (after DeleteLayer or MoveLayer) by the
Layer_Info's hook. Hooks follow the utility.library convention
(A0 = hook, A2 = object, A1 = message; see the [hooks reference](../utility/hooks.md)):

| | Layer hook ([InstallLayerHook](clipping.md#installlayerhook), `WA_BackFill`, hook create calls) | Layer_Info hook ([InstallLayerInfoHook](clipping.md#installlayerinfohook), `SA_BackFill`) |
|---|---|---|
| A2 object | `struct RastPort *` | `struct RastPort *` |
| A1 +$00 | `struct Layer *` | undefined LONG (looks like a layer pointer, is NOT one) |
| A1 +$04 | `struct Rectangle` bounds: MinX, MinY, MaxX, MaxY (WORDs, inclusive) | same |
| A1 +$0C | LONG OffsetX | -- |
| A1 +$10 | LONG OffsetY | -- |

The NDK 3.9 includes define no structure for this message; declare your own
(`struct BackFillMsg { struct Layer *Layer; struct Rectangle Bounds; LONG OffsetX, OffsetY; };`).
The autodoc example uses the bounds directly as BitMap coordinates for BltBitMap on
`rp->BitMap`. The offsets are for aligning a fill pattern.

- Special values instead of a hook pointer: `LAYERS_BACKFILL` (0) = default fill (clears),
  `LAYERS_NOBACKFILL` (1, V39) = do nothing.
- Render with BitMap-level calls (BltBitMap, BltPattern on a RastPort copy). The passed RastPort
  may be layered: if you need RastPort calls, copy it and set the copy's `Layer` to NULL (autodoc
  NOTES). Never use layered rendering calls on it inside the hook.
- The hook runs inside a layer operation, often on Intuition's input.device task: no DOS, no
  Wait, no Intuition calls, keep it fast.

## Layers under Intuition windows

Each Intuition screen's Layer_Info contains the screen bar layer (`Screen->BarLayer`) and one layer
per window, created on the screen's BitMap. `WFLG_SIMPLE_REFRESH`, `WFLG_SMART_REFRESH`,
`WFLG_SUPER_BITMAP` and `WFLG_BACKDROP` select the corresponding layer types (the obvious mapping,
unverified). GimmeZeroZero windows use a second layer for the border.

Do NOT move, size, depth-arrange, scroll or delete a window's layer with layers.library: Intuition
tracks the layer and its gadgets, borders and IDCMP messages depend on doing it through Intuition
(MoveWindow, SizeWindow, ChangeWindowBox, WindowToFront/WindowToBack, MoveWindowInFrontOf,
BeginRefresh/EndRefresh, CloseWindow). Calls that ARE meant for window layers:

- [InstallClipRegion](clipping.md#installclipregion)`(win->WLayer, region)` to clip your rendering
  to an area of the window (remove it with NULL before CloseWindow).
- [InstallLayerHook](clipping.md#installlayerhook) (or `WA_BackFill` at open time) for a custom
  background; `SA_BackFill` / [InstallLayerInfoHook](clipping.md#installlayerinfohook) for a screen.
- [LockLayer](locking.md#locklayer) / [LockLayerInfo](locking.md#locklayerinfo) to keep the layout
  stable while you read it, and [WhichLayer](layers.md#whichlayer)`(&scr->LayerInfo, x, y)` to hit-test.
- [DoHookClipRects](clipping.md#dohookcliprects) to run BitMap-level rendering through the window's
  visible rectangles.

## When games use layers directly

A bare-metal game with its own View/copper list and bitmaps does not need layers at all. Direct use
makes sense for:

- **Clipping on a private BitMap.** Rendering through a RastPort whose `Layer` is NULL is not
  clipped (graphics concepts; the DrawImage and DrawEllipse autodocs say so explicitly): a RectFill,
  Draw or Text running past the edge can write beyond the planes. One `LAYERSIMPLE` layer covering
  the whole BitMap gives a clipped `layer->rp` for free (example below).
- **No background flash.** A game drawing its whole window each frame can install
  `LAYERS_NOBACKFILL` (V39) so layers stops clearing exposed areas before the redraw.
- **Freezing a screen.** [LockLayers](locking.md#locklayers)`(&scr->LayerInfo)` stops all layered
  rendering and layer changes on a screen while you write into its BitMap directly; keep it short,
  Intuition blocks too (menus, dragging).
- **A playfield window inside a GUI:** InstallClipRegion restricts drawing to the map area without an
  extra window or layer.

## Complete example: clipped RastPort on your own BitMap

```c
#include <proto/exec.h>
#include <proto/graphics.h>
#include <proto/layers.h>
#include <graphics/gfx.h>
#include <graphics/clip.h>
#include <graphics/layers.h>
#include <graphics/rastport.h>

struct GfxBase *GfxBase;
struct Library *LayersBase;             /* opened with version 39 */

struct ClipCanvas {
    struct Layer_Info *li;
    struct Layer      *layer;
};

/* bm: planar BitMap from AllocBitMap (chip RAM for native blits), w x h pixels */
BOOL CanvasOpen(struct ClipCanvas *cc, struct BitMap *bm, LONG w, LONG h)
{
    cc->layer = NULL;
    cc->li = NewLayerInfo();
    if (cc->li == NULL)
        return FALSE;
    /* keep the picture when the layer is created and deleted: no clearing */
    InstallLayerInfoHook(cc->li, LAYERS_NOBACKFILL);
    cc->layer = CreateUpfrontHookLayer(cc->li, bm, 0, 0, w - 1, h - 1,
                                       LAYERSIMPLE, LAYERS_NOBACKFILL, NULL);
    if (cc->layer == NULL) {
        DisposeLayerInfo(cc->li);
        cc->li = NULL;
        return FALSE;
    }
    return TRUE;
}

void CanvasDraw(struct ClipCanvas *cc)
{
    struct RastPort *rp = cc->layer->rp;

    SetAPen(rp, 1);
    RectFill(rp, 280, 200, 400, 300);   /* cut at the BitMap edge, no overrun */
    Move(rp, -50, 10);
    Draw(rp, 1000, 20);
}

void CanvasClose(struct ClipCanvas *cc)
{
    if (cc->layer)
        DeleteLayer(0, cc->layer);
    if (cc->li)
        DisposeLayerInfo(cc->li);
    cc->layer = NULL;
    cc->li = NULL;
}
```

## Common mistakes

- Calling MoveLayer/SizeLayer/UpfrontLayer/DeleteLayer on `win->WLayer`: use the Intuition calls.
- Forgetting the dummy 0: `DeleteLayer(layer)` does not compile in C; in asm the layer goes in A1.
- Deleting a layer (or closing a window) with a clip region still installed: always
  `InstallClipRegion(layer, NULL)` first.
- DisposeLayerInfo while layers still exist: delete every layer first.
- Drawing through `rp` after BeginUpdate returned FALSE: call `EndUpdate(layer, FALSE)` and give up.
- Calling Intuition, dos or anything that may wait for the input task while holding layer locks.
- Walking `top_layer`/`back` without [LockLayerInfo](locking.md#locklayerinfo).
- Using layered rendering calls inside a backfill hook.
- Expecting smart-refresh or SuperBitMap layers to be free: they allocate backing store and copy
  pixels on every depth change.

**See also:** [layers.md](layers.md), [locking.md](locking.md), [clipping.md](clipping.md),
[hooks](../utility/hooks.md), graphics.library regions (NewRegion, OrRectRegion)
