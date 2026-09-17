# layers.library: clipping, backfill hooks and low-level support

A layer's rendering can be clipped further with a graphics.library Region
([InstallClipRegion](#installclipregion)), its background painted by a Hook
([InstallLayerHook](#installlayerhook), [InstallLayerInfoHook](#installlayerinfohook)), and a Hook can
be run over the visible rectangles of any RastPort ([DoHookClipRects](#dohookcliprects)). The rest of
this file is low-level or obsolete: [SwapBitsRastPortClipRect](#swapbitsrastportcliprect),
[SortLayerCR](#sortlayercr), and the pre-1.1 Layer_Info initialisers [InitLayers](#initlayers),
[FattenLayerInfo](#fattenlayerinfo), [ThinLayerInfo](#thinlayerinfo). Backfill hook message layout
and rules: [concepts.md](concepts.md#backfill-hooks); writing hooks: [hooks](../utility/hooks.md).

## InstallClipRegion
`struct Region * InstallClipRegion(struct Layer *layer, CONST struct Region *region)` — LVO -174 (-$AE)
Registers: layer=A0, region=A1; result in D0

Clip all later rendering in a layer to a Region, returning the previously installed one.

- **layer** — the layer, e.g. `win->WLayer` (A0).
- **region** — graphics.library Region (NewRegion + OrRectRegion ...), or NULL to remove clipping.
  Coordinates are relative to the layer, like rendering coordinates (unverified in the autodoc).
- **Result** — the region that was installed before, or NULL if there was none. If memory runs out
  while the ClipRects are rebuilt, `LAYER_CLIPRECTS_LOST` is set in `layer->Flags`.

The region stays yours: layers only references it.

### Example
```asm
; clip drawing in a window to the rectangle in 'box': a2 = struct Window *
        include "graphics/regions.i"
        include "intuition/intuition.i"
        include "lvo/graphics_lib.i"
        include "lvo/layers_lib.i"

        move.l  _GfxBase,a6
        jsr     _LVONewRegion(a6)
        move.l  d0,d3                   ; d3 = region
        beq     .noregion
        move.l  d3,a0
        lea     box(pc),a1
        jsr     _LVOOrRectRegion(a6)
        tst.l   d0
        beq.s   .free                   ; out of memory
        move.l  _LayersBase,a6
        move.l  wd_WLayer(a2),a0
        move.l  d3,a1
        jsr     _LVOInstallClipRegion(a6)
        move.l  d0,d4                   ; d4 = previous region
        ; ... render through wd_RPort(a2): clipped to box ...
        move.l  wd_WLayer(a2),a0
        move.l  d4,a1
        jsr     _LVOInstallClipRegion(a6)   ; put the old one back
.free:  move.l  _GfxBase,a6
        move.l  d3,a0
        jsr     _LVODisposeRegion(a6)
.noregion:
        rts

box:    dc.w    10,10,209,109           ; MinX, MinY, MaxX, MaxY (inclusive)
```

### Gotchas
- Before DeleteLayer or Intuition CloseWindow, call `InstallClipRegion(layer, NULL)` if you installed
  a region (autodoc). Uninstall before DisposeRegion too.
- Out of memory during layer operations can sweep the ClipRect list away until the next layers call
  rebuilds it (autodoc BUGS).

**See also:** graphics.library NewRegion, OrRectRegion, DisposeRegion; [BeginUpdate](layers.md#beginupdate), [ScrollLayer](layers.md#scrolllayer)

## InstallLayerHook
`struct Hook * InstallLayerHook(struct Layer *layer, struct Hook *hook)` — LVO -198 (-$C6)
Registers: layer=A0, hook=A1; result in D0

Replace a layer's backfill hook safely, returning the previous one.

- **layer** — the layer (A0), e.g. `win->WLayer`.
- **hook** — new backfill Hook; `LAYERS_BACKFILL` (NULL) for the default fill, `LAYERS_NOBACKFILL`
  (1) for none (V39). Called with A2 = RastPort, A1 = message
  `{ struct Layer *; struct Rectangle bounds; LONG OffsetX; LONG OffsetY; }`.
- **Result** — previous hook; NULL if it was the default; from V39 possibly `LAYERS_NOBACKFILL` (1).

The call waits until it is safe and locks the layer while the hooks are exchanged. Since V36.

### Example
```c
#include <proto/exec.h>
#include <proto/graphics.h>
#include <proto/layers.h>
#include <graphics/clip.h>
#include <graphics/layers.h>
#include <graphics/rastport.h>
#include <utility/hooks.h>

extern struct GfxBase *GfxBase;
extern struct Library *LayersBase;

ULONG HookStub(void);                   /* A0/A2/A1 -> C stub, see utility hooks.md */

struct BackFillMsg {                    /* not in the NDK includes */
    struct Layer    *Layer;
    struct Rectangle Bounds;
    LONG             OffsetX, OffsetY;
};

/* fill exposed areas with the pen in h_Data instead of pen 0 */
static ULONG PenFill(struct Hook *hook, struct RastPort *rp, struct BackFillMsg *msg)
{
    struct RastPort copy = *rp;

    copy.Layer = NULL;                  /* raw BitMap rendering only (autodoc NOTES) */
    SetAPen(&copy, (ULONG)hook->h_Data);
    RectFill(&copy, msg->Bounds.MinX, msg->Bounds.MinY, msg->Bounds.MaxX, msg->Bounds.MaxY);
    return 0;
}

static struct Hook penHook;             /* must outlive the window */

void SetWindowBackground(struct Layer *layer, UBYTE pen)
{
    penHook.h_Entry    = (HOOKFUNC)HookStub;
    penHook.h_SubEntry = (HOOKFUNC)(void (*)(void))PenFill;
    penHook.h_Data     = (APTR)(ULONG)pen;
    InstallLayerHook(layer, &penHook);
}
```

### Gotchas
- The hook must stay valid until the layer is deleted or another hook is installed; restore the old
  hook before freeing yours on a layer you do not own.
- No layered rendering on the passed RastPort; the hook may run on another task (concepts).
- For Intuition windows, `WA_BackFill` installs the hook at open time.

**See also:** [InstallLayerInfoHook](#installlayerinfohook), [DoHookClipRects](#dohookcliprects), [CreateUpfrontHookLayer](layers.md#createupfronthooklayer)

## InstallLayerInfoHook
`struct Hook * InstallLayerInfoHook(struct Layer_Info *li, CONST struct Hook *hook)` — LVO -204 (-$CC)
Registers: li=A0, hook=A1; result in D0

Set the hook that fills areas of a Layer_Info's BitMap not covered by any layer.

- **li** — the Layer_Info.
- **hook** — backfill Hook, `LAYERS_BACKFILL` (0) for the default, `LAYERS_NOBACKFILL` (1) for none.
  Called with A2 = RastPort and A1 = `{ ULONG undefined; struct Rectangle bounds; }`: no layer
  pointer, no offsets.
- **Result** — the previous hook, `LAYERS_BACKFILL` or `LAYERS_NOBACKFILL`; -1 on failure.

Since V39.

### Gotchas
- Installing does NOT call the hook. To have the whole area filled once, create and delete a backdrop
  layer covering it (autodoc NOTES).
- The first long of the message is undefined, even though it may look like a layer pointer.
- Intuition screens: pass it at open time with `SA_BackFill`.

**See also:** [InstallLayerHook](#installlayerhook), [NewLayerInfo](layers.md#newlayerinfo)

## DoHookClipRects
`VOID DoHookClipRects(struct Hook *hook, struct RastPort *rport, CONST struct Rectangle *rect)` — LVO -216 (-$D8)
Registers: hook=A0, rport=A1, rect=A2; no result

Call a hook for every renderable ClipRect of a RastPort, optionally within a rectangle.

- **hook** — Hook called like a layer backfill hook (A2 = RastPort, A1 = `{ layer, bounds, OffsetX,
  OffsetY }`); or `LAYERS_BACKFILL` to run the layer's default fill, `LAYERS_NOBACKFILL` for nothing.
- **rport** — RastPort to operate on. If it has a Layer, the layer is locked during the call. If not,
  the hook is called once with `rect`, the RastPort and a NULL layer.
- **rect** — bounding rectangle the ClipRects are cut to, or NULL for no bounding. MUST be non-NULL
  for a non-layered RastPort.

Hidden simple-refresh ClipRects are skipped; on-screen, smart-refresh off-screen and SuperBitMap
ClipRects are all visited. This is how layers runs backfill hooks. Since V39.

### Example
```c
#include <proto/layers.h>
#include <graphics/clip.h>
#include <graphics/gfx.h>
#include <intuition/intuition.h>
#include <utility/hooks.h>

extern struct Library *LayersBase;

/* paint a window area through its visible parts with a BitMap-level hook (e.g. penHook above);
   x0..y1 in window coordinates (layer-relative, unverified) */
void PaintArea(struct Window *win, struct Hook *hook, WORD x0, WORD y0, WORD x1, WORD y1)
{
    struct Rectangle r = { x0, y0, x1, y1 };

    DoHookClipRects(hook, win->RPort, &r);
}
```

### Gotchas
- Same hook rules as backfill hooks: BitMap-level rendering only, or a RastPort copy with Layer NULL
  (autodoc NOTES).

**See also:** [InstallLayerHook](#installlayerhook), [concepts](concepts.md#backfill-hooks)

## SwapBitsRastPortClipRect
`VOID SwapBitsRastPortClipRect(struct RastPort *rp, struct ClipRect *cr)` — LVO -126 (-$7E)
Registers: rp=A0, cr=A1; no result

Exchange the pixels of a ClipRect's BitMap with the same area of a RastPort's display.

- **rp** — RastPort of the display (shared BitMap).
- **cr** — ClipRect whose `BitMap` and `bounds` describe the area to swap.

A support routine for code doing its own obscuring outside layers.library; no extra memory is used.

### Gotchas
- The blit runs asynchronously: WaitBlit before freeing or touching the structures (autodoc NOTE).
- ClipRects made by layers are larger than `struct ClipRect` in clip.h: never declare your own
  instances expecting layers to accept them.

**See also:** graphics.library WaitBlit

## SortLayerCR
`VOID SortLayerCR(struct Layer *layer, LONG dx, LONG dy)` — LVO -210 (-$D2)
Registers: layer=A0, dx=D0, dy=D1; no result

Sort a layer's ClipRects into the best order for scrolling its contents by dx, dy.

- **layer** — the layer, locked by the caller.
- **dx, dy** — scroll direction the order should suit. The SFD and inline macro pass them as WORD.

Since V39.

Source: NDK 3.9 includes (no autodoc in the source set).

Applications have no reason to call it. The NDK 3.2 autodoc, a later source, describes it as sorting
the ClipRects "for scroll raster", marks it for layers/graphics internal use only and requires the
layer to be locked.

**See also:** [LockLayer](locking.md#locklayer), graphics.library ScrollRaster

## InitLayers
`VOID InitLayers(struct Layer_Info *li)` — LVO -30 (-$1E)
Registers: li=A0; no result

Obsolete: initialise a caller-allocated Layer_Info (use NewLayerInfo instead).

- **li** — Layer_Info memory you allocated.

Initialises the structure and leaves it unlocked. Without [FattenLayerInfo](#fattenlayerinfo) layers
allocates and frees its 1.1 extension on most calls; after FattenLayerInfo, call
[ThinLayerInfo](#thinlayerinfo) before freeing the memory.

**See also:** [NewLayerInfo](layers.md#newlayerinfo), [DisposeLayerInfo](layers.md#disposelayerinfo)

## FattenLayerInfo
`LONG FattenLayerInfo(struct Layer_Info *li)` — LVO -156 (-$9C)
Registers: li=A0; result in D0

Obsolete: add the 1.1 extensions to a Layer_Info that was not made by NewLayerInfo.

- **li** — a 1.0-style Layer_Info (e.g. set up with [InitLayers](#initlayers)).
- **Result** — not documented in the autodoc.

Preallocates the extra data so layers need not allocate and free it on every call. Pair with
[ThinLayerInfo](#thinlayerinfo) before freeing the memory. Not needed with NewLayerInfo /
DisposeLayerInfo.

**See also:** [ThinLayerInfo](#thinlayerinfo), [NewLayerInfo](layers.md#newlayerinfo)

## ThinLayerInfo
`VOID ThinLayerInfo(struct Layer_Info *li)` — LVO -162 (-$A2)
Registers: li=A0; no result

Obsolete: free the extensions added by FattenLayerInfo before freeing a Layer_Info.

- **li** — Layer_Info previously passed to [FattenLayerInfo](#fattenlayerinfo).

**See also:** [FattenLayerInfo](#fattenlayerinfo), [DisposeLayerInfo](layers.md#disposelayerinfo)
