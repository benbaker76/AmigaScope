# layers.library: locking

Two lock levels protect layers from other tasks. The **Layer_Info lock**
([LockLayerInfo](#locklayerinfo)) freezes the arrangement: no layer can be created, deleted, moved,
sized or depth-arranged. A **layer lock** ([LockLayer](#locklayer)) freezes one layer's ClipRects
and blocks rendering into it by other tasks. Every layers.library operation takes these locks
internally; you need them yourself only when you read layer structures, render in several steps that
must see a stable layout, or write into a layer's BitMap behind graphics.library's back. Both are
semaphores: the owning task may nest them, and each lock needs exactly one unlock.

Lock order (to avoid deadlocks):

1. LockLayerInfo **before** locking more than one layer (autodoc: required to lock several layers).
2. Then LockLayer for each layer, or [LockLayers](#locklayers) for all of them.
3. Unlock in reverse order.

While you hold any layer lock, Intuition blocks on window dragging, sizing, depth changes and menus
of that screen, and so does any task rendering into the locked layers. Keep the locked section
short and make no Intuition calls, no dos.library I/O and no Wait for something the input task
must do first. graphics.library LockLayerRom / UnlockLayerRom are the same layer lock with the layer
in A5.

## LockLayer
`VOID LockLayer(LONG dummy, struct Layer *layer)` — LVO -96 (-$60)
Registers: dummy=A0, layer=A1; no result

Lock a layer's ClipRects against other tasks, waiting until the lock is free.

- **dummy** — unused, pass 0.
- **layer** — layer to lock (A1), e.g. `win->WLayer`.

Same effect as graphics.library LockLayerRom (layer in A5 there).

### Example
```asm
; hold a window's layer stable while reading its ClipRect list: a2 = struct Window *
        include "graphics/clip.i"
        include "intuition/intuition.i"
        include "lvo/layers_lib.i"

        move.l  _LayersBase,a6
        sub.l   a0,a0                   ; dummy
        move.l  wd_WLayer(a2),a1
        jsr     _LVOLockLayer(a6)
        move.l  wd_WLayer(a2),a0
        moveq   #0,d2
        move.l  lr_ClipRect(a0),a1
.count: move.l  a1,d0
        beq.s   .done
        addq.l  #1,d2                   ; d2 = number of ClipRects
        move.l  cr_Next(a1),a1
        bra.s   .count
.done:  move.l  wd_WLayer(a2),a0
        jsr     _LVOUnlockLayer(a6)     ; layer in A0 here
```

### Gotchas
- To lock more than one layer, hold [LockLayerInfo](#locklayerinfo) first (autodoc).
- No Intuition calls while the lock is held: Intuition waits for it (autodoc).
- The unlock call takes the layer in A0, not A1.

**See also:** [UnlockLayer](#unlocklayer), [LockLayerInfo](#locklayerinfo), graphics.library LockLayerRom

## UnlockLayer
`VOID UnlockLayer(struct Layer *layer)` — LVO -102 (-$66)
Registers: layer=A0; no result

Release one lock level taken with LockLayer (or graphics LockLayerRom).

- **layer** — the locked layer (A0).

**See also:** [LockLayer](#locklayer), graphics.library UnlockLayerRom

## LockLayers
`VOID LockLayers(struct Layer_Info *li)` — LVO -108 (-$6C)
Registers: li=A0; no result

Lock the Layer_Info and then every layer in it.

- **li** — Layer_Info to freeze, e.g. `&screen->LayerInfo`.

Calls [LockLayerInfo](#locklayerinfo) itself first, so the order rule is met. Stops all layered
rendering and layer operations on that Layer_Info until [UnlockLayers](#unlocklayers).

### Example
```c
#include <proto/layers.h>
#include <intuition/screens.h>

extern struct Library *LayersBase;

/* write straight into a screen's BitMap without any task drawing at the same time */
void PokeScreen(struct Screen *scr, void (*poke)(struct BitMap *))
{
    LockLayers(&scr->LayerInfo);
    poke(scr->RastPort.BitMap);         /* short, no OS calls that could wait */
    UnlockLayers(&scr->LayerInfo);
}
```

### Gotchas
- Menus, window dragging and every other task's window rendering on that screen stop until you
  unlock: keep it very short.

**See also:** [UnlockLayers](#unlocklayers), [LockLayer](#locklayer), [LockLayerInfo](#locklayerinfo)

## UnlockLayers
`VOID UnlockLayers(struct Layer_Info *li)` — LVO -114 (-$72)
Registers: li=A0; no result

Unlock every layer of a Layer_Info, then the Layer_Info itself.

- **li** — Layer_Info locked with [LockLayers](#locklayers).

Graphics output that was waiting on the layers continues.

**See also:** [LockLayers](#locklayers), [UnlockLayer](#unlocklayer)

## LockLayerInfo
`VOID LockLayerInfo(struct Layer_Info *li)` — LVO -120 (-$78)
Registers: li=A0; no result

Gain exclusive use of a Layer_Info, waiting until no other task holds it.

- **li** — Layer_Info to lock, e.g. `&screen->LayerInfo`.

Needed around any access to the Layer_Info that layers.library does not do for you: walking
`top_layer`/`back`, using a [WhichLayer](layers.md#whichlayer) result, locking several layers, or
keeping several [BeginUpdate](layers.md#beginupdate) passes consistent. Pair every call with
[UnlockLayerInfo](#unlocklayerinfo).

### Example
```asm
; count the layers of a screen: a2 = struct Screen *
        include "graphics/layers.i"
        include "graphics/clip.i"
        include "intuition/screens.i"
        include "lvo/layers_lib.i"

        move.l  _LayersBase,a6
        lea     sc_LayerInfo(a2),a0
        jsr     _LVOLockLayerInfo(a6)
        moveq   #0,d2
        move.l  sc_LayerInfo+li_top_layer(a2),a0
.walk:  move.l  a0,d0
        beq.s   .done
        addq.l  #1,d2                   ; includes the screen bar layer
        move.l  lr_back(a0),a0
        bra.s   .walk
.done:  lea     sc_LayerInfo(a2),a0
        jsr     _LVOUnlockLayerInfo(a6)
```

### Gotchas
- Never combine it with Intuition's LockIBase: the intuition autodoc forbids LockIBase while you hold
  layer or LayerInfo locks, and forbids layers calls while you hold the IBase lock.

**See also:** [UnlockLayerInfo](#unlocklayerinfo), [LockLayers](#locklayers), [WhichLayer](layers.md#whichlayer)

## UnlockLayerInfo
`VOID UnlockLayerInfo(struct Layer_Info *li)` — LVO -138 (-$8A)
Registers: li=A0; no result

Release a Layer_Info lock taken with LockLayerInfo.

- **li** — the locked Layer_Info.

**See also:** [LockLayerInfo](#locklayerinfo)
