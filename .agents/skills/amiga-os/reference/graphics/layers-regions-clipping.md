# graphics.library: regions and layer locking

A `struct Region` (graphics/regions.h) is a bounding `struct Rectangle bounds` plus a linked list
of `struct RegionRectangle` (`Next`, `Prev`, `bounds`). Build one with [NewRegion](#newregion),
combine rectangles/regions with the And/Or/Xor/Clear calls, hand it to layers.library
InstallClipRegion to clip all rendering in a layer (window), and free it with
[DisposeRegion](#disposeregion). `struct Rectangle` is `MinX, MinY, MaxX, MaxY` (WORDs); Max values
are inclusive, as for RectFill (unverified). The Or/Xor/ClearRect and ...RegionRegion calls
allocate memory and return FALSE when it runs out; [AndRectRegion](#andrectregion),
[ClearRegion](#clearregion) and [DisposeRegion](#disposeregion) cannot fail. asm (regions.i,
gfx.i): `rg_bounds`, `rg_RegionRectangle`, `rg_SIZEOF`; `rr_Next`, `rr_Prev`, `rr_bounds`,
`rr_SIZEOF`; `ra_MinX`, `ra_MinY`, `ra_MaxX`, `ra_MaxY`, `ra_SIZEOF`.

The layer lock calls let rendering code keep a layer's ClipRects stable; they take the Layer in
A5 (asm callers must save/restore A5, often used as a frame pointer; the gcc inline stubs handle
it). SuperBitMap layers are synchronised with [SyncSBitMap](#syncsbitmap) /
[CopySBitMap](#copysbitmap).

## NewRegion
`struct Region * NewRegion(VOID)` — LVO -516 (-$204)
Registers: none; result in D0

Allocate a new, empty Region.

- **Result** — pointer to the Region, or NULL if out of memory.

### Example
```c
#include <proto/layers.h>

/* render into a window, clipped to a 100x40 box at (20,20) */
void draw_clipped(struct Window *win)
{
    struct Rectangle box = { 20, 20, 119, 59 };
    struct Region *rg = NewRegion();
    struct Region *old;

    if (!rg)
        return;
    if (OrRectRegion(rg, &box)) {             /* FALSE = out of memory */
        old = InstallClipRegion(win->WLayer, rg);
        SetAPen(win->RPort, 2);
        RectFill(win->RPort, 0, 0, 199, 99);  /* only the box area is drawn */
        InstallClipRegion(win->WLayer, old);  /* restore before disposing */
    }
    DisposeRegion(rg);
}
```

### Gotchas
- Always test for NULL.
- Before DeleteLayer or Intuition's CloseWindow, remove an installed region with
  `InstallClipRegion(layer, NULL)` (required by the layers.library autodoc, see
  [InstallClipRegion](../layers/clipping.md#installclipregion)); also uninstall it (reinstall the
  previous one) before [DisposeRegion](#disposeregion) (standard practice, unverified).

**See also:** [DisposeRegion](#disposeregion), [OrRectRegion](#orrectregion),
[ClearRegion](#clearregion)

## DisposeRegion
`VOID DisposeRegion(struct Region *region)` — LVO -534 (-$216)
Registers: region=A0; no result

Free a Region and all of its RegionRectangles.

- **region** — Region from [NewRegion](#newregion).

**See also:** [NewRegion](#newregion), [ClearRegion](#clearregion)

## ClearRegion
`VOID ClearRegion(struct Region *region)` — LVO -528 (-$210)
Registers: region=A0; no result

Remove all rectangles from a Region, leaving it empty but allocated.

- **region** — Region to empty.

**See also:** [NewRegion](#newregion), [DisposeRegion](#disposeregion)

## AndRectRegion
`VOID AndRectRegion(struct Region *region, CONST struct Rectangle *rectangle)` — LVO -504 (-$1F8)
Registers: region=A0, rectangle=A1; no result

Clip a Region to a rectangle: everything outside the rectangle is removed.

- **region** — Region to modify (receives the result).
- **rectangle** — clipping rectangle.

### Gotchas
- The only rectangle/region operation that cannot fail, hence no return value.

**See also:** [AndRegionRegion](#andregionregion), [OrRectRegion](#orrectregion)

## OrRectRegion
`BOOL OrRectRegion(struct Region *region, CONST struct Rectangle *rectangle)` — LVO -510 (-$1FE)
Registers: region=A0, rectangle=A1; result in D0

Add a rectangle to a Region (union).

- **region** — Region to modify (receives the result).
- **rectangle** — rectangle to add.
- **Result** — TRUE on success, FALSE if out of memory.

**See also:** [AndRectRegion](#andrectregion), [OrRegionRegion](#orregionregion),
[XorRectRegion](#xorrectregion)

## XorRectRegion
`BOOL XorRectRegion(struct Region *region, CONST struct Rectangle *rectangle)` — LVO -558 (-$22E)
Registers: region=A0, rectangle=A1; result in D0

Exclusive-or a rectangle with a Region: add uncovered parts, remove covered parts.

- **region** — Region to modify (receives the result).
- **rectangle** — rectangle to toggle.
- **Result** — TRUE on success, FALSE if out of memory.

**See also:** [OrRectRegion](#orrectregion), [XorRegionRegion](#xorregionregion)

## ClearRectRegion
`BOOL ClearRectRegion(struct Region *region, CONST struct Rectangle *rectangle)` — LVO -522 (-$20A)
Registers: region=A0, rectangle=A1; result in D0

Cut a rectangle out of a Region: everything inside the rectangle is removed.

- **region** — Region to modify (receives the result).
- **rectangle** — area to remove.
- **Result** — TRUE on success, FALSE if out of memory.

**See also:** [AndRectRegion](#andrectregion), [ClearRegion](#clearregion)

## AndRegionRegion
`BOOL AndRegionRegion(CONST struct Region *srcRegion, struct Region *destRegion)` — LVO -624 (-$270)
Registers: srcRegion=A0, destRegion=A1; result in D0

Intersect two Regions, storing the result in the second one.

- **srcRegion** — region1, left unchanged.
- **destRegion** — region2; keeps only the parts also in srcRegion.
- **Result** — TRUE on success, FALSE if out of memory.

### Gotchas
- The result goes into the SECOND argument (A1), not the first.

**See also:** [OrRegionRegion](#orregionregion), [AndRectRegion](#andrectregion)

## OrRegionRegion
`BOOL OrRegionRegion(CONST struct Region *srcRegion, struct Region *destRegion)` — LVO -612 (-$264)
Registers: srcRegion=A0, destRegion=A1; result in D0

Unite two Regions, storing the result in the second one.

- **srcRegion** — region1, left unchanged.
- **destRegion** — region2; everything in srcRegion is added to it.
- **Result** — TRUE on success, FALSE if out of memory.

**See also:** [OrRectRegion](#orrectregion), [AndRegionRegion](#andregionregion)

## XorRegionRegion
`BOOL XorRegionRegion(CONST struct Region *srcRegion, struct Region *destRegion)` — LVO -618 (-$26A)
Registers: srcRegion=A0, destRegion=A1; result in D0

Exclusive-or two Regions, storing the result in the second one.

- **srcRegion** — region1, left unchanged.
- **destRegion** — region2; becomes the area covered by exactly one of the two regions.
- **Result** — TRUE on success, FALSE if out of memory.

**See also:** [OrRegionRegion](#orregionregion), [AndRegionRegion](#andregionregion),
[XorRectRegion](#xorrectregion)

## LockLayerRom
`VOID LockLayerRom(struct Layer *layer)` — LVO -432 (-$1B0)
Registers: layer=A5; no result

Lock a Layer so no other task can change its ClipRects; waits until the lock is free.

- **layer** — the Layer (e.g. `win->WLayer`, `rp->Layer`), in A5.

Preserves ALL registers. Nests: the owning task may lock again, and needs one
[UnlockLayerRom](#unlocklayerrom) per lock. Same effect as layers.library LockLayer (whose NDK 3.9
prototype takes a dummy argument in A0 and the layer in A1).

### Example
```asm
; a0 = Layer: hold its lock around some rendering
DrawLocked:
        movem.l a5-a6,-(sp)
        move.l  _GfxBase,a6
        move.l  a0,a5                   ; layer must be in A5
        jsr     _LVOLockLayerRom(a6)    ; blocks until locked, no registers changed
        ; ... render through lr_rp(a5) ...
        jsr     _LVOUnlockLayerRom(a6)  ; trashes d0/d1/a0/a1
        movem.l (sp)+,a5-a6
        rts
```

### Gotchas
- Never call Intuition (or anything that may lock layers the other way round) while holding the
  lock: deadlock.
- Holding the lock blocks Intuition and every layers user; keep the locked section short.
- Save and restore A5 in asm; in C the proto/inline stubs swap A5 for you.

**See also:** [UnlockLayerRom](#unlocklayerrom), [AttemptLockLayerRom](#attemptlocklayerrom),
layers.library LockLayer

## AttemptLockLayerRom
`BOOL AttemptLockLayerRom(struct Layer *layer)` — LVO -654 (-$28E)
Registers: layer=A5; result in D0

Lock a Layer only if it is free right now; never waits.

- **layer** — the Layer, in A5.
- **Result** — TRUE if you now hold the lock (unlock it later), FALSE if another task has it.

Preserves ALL registers (D0 carries the result). Nests like [LockLayerRom](#locklayerrom).

### Gotchas
- Only call [UnlockLayerRom](#unlocklayerrom) when the result was TRUE.

**See also:** [LockLayerRom](#locklayerrom), [UnlockLayerRom](#unlocklayerrom)

## UnlockLayerRom
`VOID UnlockLayerRom(struct Layer *layer)` — LVO -438 (-$1B6)
Registers: layer=A5; no result

Release one level of a Layer lock taken with LockLayerRom or AttemptLockLayerRom.

- **layer** — the Layer, in A5.

### Gotchas
- Unlike the lock calls this one DOES trash the scratch registers (D0/D1/A0/A1).
- The layer becomes free for other tasks only after as many unlocks as locks.
- Same as layers.library UnlockLayer (layer in A0 there).

**See also:** [LockLayerRom](#locklayerrom), [AttemptLockLayerRom](#attemptlocklayerrom)

## SyncSBitMap
`VOID SyncSBitMap(struct Layer *layer)` — LVO -444 (-$1BC)
Registers: layer=A0; no result

Copy what is visible in a SuperBitMap layer's ClipRects into its SuperBitMap.

- **layer** — a Layer created with a SuperBitMap; lock it first
  ([LockLayerRom](#locklayerrom)).

After this the SuperBitMap can be read or modified directly; write it back with
[CopySBitMap](#copysbitmap).

**See also:** [CopySBitMap](#copysbitmap), [LockLayerRom](#locklayerrom)

## CopySBitMap
`VOID CopySBitMap(struct Layer *layer)` — LVO -450 (-$1C2)
Registers: layer=A0; no result

Copy a SuperBitMap's contents back into the on-screen parts of its layer.

- **layer** — a SuperBitMap Layer, already locked by the caller.

The inverse of [SyncSBitMap](#syncsbitmap): use it after changing the SuperBitMap directly.

**See also:** [SyncSBitMap](#syncsbitmap), [LockLayerRom](#locklayerrom)
