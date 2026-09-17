# graphics.library: GELs (VSprites, Bobs, animation)

GELs are the OS software-sprite system: VSprites (virtual sprites multiplexed onto the 8 hardware
sprites through the copper), Bobs (blitter objects drawn into a RastPort) and AnimObs/AnimComps
(sequenced animation built from Bobs). Everything hangs off `rp->GelsInfo`, which you allocate and
fill before [InitGels](#initgels). Each frame: move the gels (or [Animate](#animate)), then
[SortGList](#sortglist) -> [DoCollision](#docollision) (optional) -> [DrawGList](#drawglist) ->
install the copper lists if VSprites are used (`MrgCop()`/`LoadView()` of the View, or intuition
`RethinkDisplay()`) -> `WaitTOF()`. Image, mask and save buffers are used by the blitter/copper and
must be chip RAM. Games that own the display usually drive sprites and the blitter directly instead:
GELs are convenient but slow. Asm field names differ from C (`vs_VSFlags`, `bob_BobFlags`; flag
BITDEFs `VSF_*`/`BF_*` in gels.i); the asm STRUCTURE names are `VS`, `BOB`, `AC`, `AO`, `DBP`.

## InitGels
`VOID InitGels(struct VSprite *head, struct VSprite *tail, struct GelsInfo *gelsInfo)` — LVO -120 (-$78)
Registers: head=A0, tail=A1, gelsInfo=A2; no result

Initialise a GelsInfo and link two dummy VSprites as the head and tail of its gel list.

- **head**, **tail** — two `struct VSprite` you provide (contents are set up by the call; they are
  sort sentinels, never drawn). Keep them allocated while the list is in use.
- **gelsInfo** — your `struct GelsInfo` (graphics/rastport.h). Before the call fill in:
  `nextLine` -> array of 8 WORDs, `lastColor` -> array of 8 `WORD *`, `collHandler` -> a
  `struct collTable` (16 function pointers), `leftmost`/`rightmost`/`topmost`/`bottommost` =
  boundaries for border collisions (usually the raster size - 1), `sprRsrvd` = bitmask of hardware
  sprites to reserve from the VSprite system (header wording). Zero the rest.

After InitGels store the GelsInfo in `rp->GelsInfo` of every RastPort that draws these gels.

### Example
```c
static struct VSprite gel_head, gel_tail;
static struct GelsInfo gels;
static struct collTable coll;
static WORD next_line[8];
static WORD *last_color[8];

void setup_gels(struct RastPort *rp)
{
    gels.nextLine    = next_line;
    gels.lastColor   = last_color;
    gels.collHandler = &coll;
    gels.leftmost    = 0;
    gels.topmost     = 0;
    gels.rightmost   = GetBitMapAttr(rp->BitMap, BMA_WIDTH) - 1;
    gels.bottommost  = GetBitMapAttr(rp->BitMap, BMA_HEIGHT) - 1;
    gels.sprRsrvd    = 0;               /* only Bobs in this program */
    InitGels(&gel_head, &gel_tail, &gels);
    rp->GelsInfo = &gels;
}
```

### Gotchas
- Allocate `collHandler` before calling: InitGels clears the boundary-hit vector (entry 0) only if
  the table pointer is set, and DoCollision reads the table.
- The autodoc says the head/tail are stored "in GfxBase"; they actually go into
  `gelsInfo->gelHead`/`gelTail`.
- The dummy head/tail must stay valid (not stack variables of a function that returns).

**See also:** [AddBob](#addbob), [AddVSprite](#addvsprite), [SetCollision](#setcollision),
[concepts](concepts.md#rastport-basics)

## AddVSprite
`VOID AddVSprite(struct VSprite *vSprite, struct RastPort *rp)` — LVO -102 (-$66)
Registers: vSprite=A0, rp=A1; no result

Link a VSprite into the RastPort's gel list (sorted by Y,X).

- **vSprite** — initialised `struct VSprite`: `Flags` = `VSPRITE` (plus `MUSTDRAW` if wanted),
  `Y`/`X` position, `Height` in lines, `Width` in words (1 for a 16 pixel sprite), `Depth` 2,
  `ImageData` -> Height x 2 WORDs (two bitplanes per line, no posctl header, chip RAM),
  `SprColors` -> 3 WORD `$0RGB` colours for sprite pens 1-3,
  `MeMask`/`HitMask` for collisions, `BorderLine`/`CollMask` buffers if you use collisions
  (see [InitMasks](#initmasks)).
- **rp** — RastPort whose `GelsInfo` was set up by [InitGels](#initgels).

### Gotchas
- A VSprite only becomes visible after [DrawGList](#drawglist) and a remerge of the copper lists
  (`MrgCop()` + `LoadView()`, or intuition `RethinkDisplay()`).
- Too many VSprites on one line cannot all get a hardware sprite; they are then skipped
  (`VSOVERFLOW` is set in Flags).
- Sprite colours come from the shared sprite colour registers; DrawGList loads each VSprite's
  `SprColors` through the copper, so neighbouring VSprites can differ (unverified in the NDK
  sources).

**See also:** [RemVSprite](#remvsprite), [AddBob](#addbob), [DrawGList](#drawglist),
[GetSprite](sprites.md#getsprite)

## AddBob
`VOID AddBob(struct Bob *bob, struct RastPort *rp)` — LVO -96 (-$60)
Registers: bob=A0, rp=A1; no result

Add a Bob to the RastPort's gel list (sets its system flags, then links its VSprite).

- **bob** — `struct Bob` with `BobVSprite` -> its VSprite (and `vs->VSBob` pointing back),
  `SaveBuffer` (if `SAVEBACK`), `ImageShadow` (if `OVERLAY`), `Before`/`After` (draw-order links
  or NULL), `DBuffer` (NULL unless double-buffering), `Flags` user bits (`SAVEBOB` = leave the
  image behind when it moves, `BOBISCOMP` = part of an AnimComp).
- **rp** — RastPort with an initialised `GelsInfo`; the Bob is drawn into its BitMap.

The Bob's VSprite must NOT have `VSPRITE` set. Fill it in: `Flags` (`SAVEBACK` to restore the
background, `OVERLAY` to cut the image in through ImageShadow instead of drawing a solid
rectangle), `Y`/`X`, `Height` lines, `Width` in words, `Depth` = planes in `ImageData`,
`ImageData` (Depth x Height x Width words, plane 0 rows first, chip RAM), `PlanePick` (which
RastPort planes receive the image planes), `PlaneOnOff` (value written into the unpicked planes),
`BorderLine` (Width words) and `CollMask` (Height x Width words), `MeMask`/`HitMask`.

Buffer sizes (all chip RAM): `SaveBuffer` = Width x Height x (RastPort depth) words;
`ImageShadow`/`CollMask` = Width x Height words (the same buffer may serve both);
`BorderLine` = Width words.

### Example
```c
#include <exec/memory.h>

#define BW 1                      /* Bob width in words (16 pixels) */
#define BH 8                      /* height in lines */

static struct VSprite bob_vs;
static struct Bob bob;

/* image: 2 planes x BH lines x BW words in chip RAM; returns the buffer block to FreeMem later */
WORD *start_bob(struct RastPort *rp, WORD *chip_image, ULONG *blocksize)
{
    ULONG plane = BW * BH * sizeof(WORD);
    ULONG depth = GetBitMapAttr(rp->BitMap, BMA_DEPTH);
    ULONG size  = BW * sizeof(WORD) + plane + plane * depth;
    WORD *mem   = AllocMem(size, MEMF_CHIP | MEMF_CLEAR);
    if (!mem)
        return NULL;
    *blocksize = size;

    bob_vs.Flags      = SAVEBACK | OVERLAY;     /* no VSPRITE: this is a Bob */
    bob_vs.Width      = BW;
    bob_vs.Height     = BH;
    bob_vs.Depth      = 2;
    bob_vs.X          = 50;
    bob_vs.Y          = 40;
    bob_vs.ImageData  = chip_image;
    bob_vs.PlanePick  = 0x03;                   /* image planes -> planes 0,1 */
    bob_vs.PlaneOnOff = 0x00;
    bob_vs.BorderLine = mem;
    bob_vs.CollMask   = mem + BW;
    bob_vs.VSBob      = &bob;

    bob.ImageShadow = bob_vs.CollMask;          /* shared with CollMask */
    bob.SaveBuffer  = mem + BW + BW * BH;
    bob.BobVSprite  = &bob_vs;

    InitMasks(&bob_vs);                         /* builds BorderLine + CollMask */
    AddBob(&bob, rp);                           /* rp->GelsInfo already set */
    return mem;
}
```

### Gotchas
- Every buffer the blitter touches (`ImageData`, `SaveBuffer`, `ImageShadow`) must be chip RAM.
- A Bob is only drawn by [DrawGList](#drawglist); moving it = change `X`/`Y`, then the per-frame
  SortGList/DrawGList sequence.
- To remove: [RemBob](#rembob) (deferred) or [RemIBob](#remibob) (immediate). Free the buffers
  only after it is out of the list.

**See also:** [InitMasks](#initmasks), [DrawGList](#drawglist), [RemIBob](#remibob),
[GetGBuffers](#getgbuffers)

## InitMasks
`VOID InitMasks(struct VSprite *vSprite)` — LVO -126 (-$7E)
Registers: vSprite=A0; no result

Build the BorderLine and CollMask of a VSprite or Bob from its image data.

- **vSprite** — the VSprite (for a Bob: its `BobVSprite`), with `ImageData`, `Width`, `Height`,
  `Depth` set and `BorderLine`/`CollMask` pointing at allocated buffers. VSprite vs Bob is detected
  from the `VSPRITE` flag.

### Gotchas
- Allocates nothing: both buffers must exist. Call it again whenever `ImageData` changes shape.
- For a Bob using `OVERLAY`, `ImageShadow` is normally the same buffer as `CollMask`, so this also
  builds the cookie-cut mask.

**See also:** [InitGMasks](#initgmasks), [AddBob](#addbob)

## SortGList
`VOID SortGList(struct RastPort *rp)` — LVO -150 (-$96)
Registers: rp=A1; no result

Sort the gel list into Y,X order after positions changed.

- **rp** — RastPort holding the `GelsInfo`.

### Gotchas
- Required before every [DrawGList](#drawglist) and [DoCollision](#docollision) whenever any gel
  moved; both depend on the order.

**See also:** [DrawGList](#drawglist), [DoCollision](#docollision)

## DoCollision
`VOID DoCollision(struct RastPort *rp)` — LVO -108 (-$6C)
Registers: rp=A1; no result

Test all gels for border and gel-to-gel hits and call the matching collision routines.

- **rp** — RastPort holding the `GelsInfo`; the list must be sorted ([SortGList](#sortglist)).

Border test: a gel with bit 0 (`BORDERHIT`, graphics/collide.h) set in `HitMask` that crosses
`leftmost`/`rightmost`/`topmost`/`bottommost` calls routine 0 with the gel and a WORD of
`TOPHIT` 1, `BOTTOMHIT` 2, `LEFTHIT` 4, `RIGHTHIT` 8. Gel-to-gel: when one gel's `HitMask`
shares bits with the other's `MeMask`, the routine for a common bit (1..15) is called with both
gels (which bit wins when several match is unverified).

### Gotchas
- Uses `BorderLine`/`CollMask`: run [InitMasks](#initmasks) first.
- Routines run synchronously inside DoCollision, on your task.

**See also:** [SetCollision](#setcollision), [SortGList](#sortglist)

## SetCollision
`VOID SetCollision(ULONG num, VOID (*routine)(struct VSprite *gelA, struct VSprite *gelB), struct GelsInfo *gelsInfo)` — LVO -144 (-$90)
Registers: num=D0, routine=A0, gelsInfo=A1; no result

Install a collision routine in slot num of a GelsInfo's collision table.

- **num** — 0 = boundary-hit routine, 1..15 = gel-to-gel routine for that HitMask/MeMask bit.
- **routine** — function pointer. Slot 0 is called as `(struct VSprite *gel, WORD borderbits)`;
  slots 1..15 as `(struct VSprite *gelA, struct VSprite *gelB)` (per the gels.h comment),
  arguments on the stack like a C call (asm: read them at 4(sp)/8(sp) -- unverified).
- **gelsInfo** — the GelsInfo whose `collHandler` table receives the pointer.

### Example
```c
#include <graphics/collide.h>       /* BORDERHIT, TOPHIT..RIGHTHIT: not pulled in by gels.h */

/* VUserExt holds the gel's x speed in this program */
static LONG hit_border(struct VSprite *vs, WORD where)
{
    if (where & (LEFTHIT | RIGHTHIT))
        vs->VUserExt = -vs->VUserExt;           /* bounce */
    return 0;
}

void install_border_hit(struct GelsInfo *gi)
{
    SetCollision(0, (VOID (*)(struct VSprite *, struct VSprite *))hit_border, gi);
}
```

### Gotchas
- The NDK prototype types every routine as `VOID (*)(struct VSprite *, struct VSprite *)`; cast
  the boundary routine as shown.
- `BORDERHIT`/`TOPHIT`/`BOTTOMHIT`/`LEFTHIT`/`RIGHTHIT` live in graphics/collide.h (C only; no
  collide.i), which gels.h does not include.
- `collHandler` must point at a real `struct collTable` (16 LONG slots, asm `cp_collPtrs` in
  view.i) before InitGels/SetCollision.

**See also:** [DoCollision](#docollision), [InitGels](#initgels)

## DrawGList
`VOID DrawGList(struct RastPort *rp, struct ViewPort *vp)` — LVO -114 (-$72)
Registers: rp=A1, vp=A0; no result

Draw one pass of the gel list: Bobs into rp, VSprite copper instructions for vp.

- **rp** — RastPort with the `GelsInfo`; Bobs are drawn into its BitMap.
- **vp** — ViewPort for which VSprite copper lists are built (e.g. `&screen->ViewPort`).

### Example
```c
void gels_frame(struct Screen *scr)
{
    SortGList(&scr->RastPort);
    DoCollision(&scr->RastPort);
    DrawGList(&scr->RastPort, &scr->ViewPort);
    MrgCop(ViewAddress());          /* only needed when VSprites are in the list */
    LoadView(ViewAddress());
    WaitTOF();
}
```

### Gotchas
- Sort first ([SortGList](#sortglist)).
- VSprites change only the intermediate copper lists: merge and load the View afterwards
  (`MrgCop`/`LoadView`, or intuition `RethinkDisplay`) or nothing changes on screen.
- BUGS: `MUSTDRAW` is not implemented.
- Uses the blitter for Bobs; do not hold [OwnBlitter](blitter-and-timing.md#ownblitter) while
  calling it.

**See also:** [SortGList](#sortglist), [MrgCop](views-and-viewports.md#mrgcop),
[LoadView](views-and-viewports.md#loadview)

## RemVSprite
`VOID RemVSprite(struct VSprite *vSprite)` — LVO -138 (-$8A)
Registers: vSprite=A0; no result

Unlink a VSprite from the gel list.

- **vSprite** — a VSprite added with [AddVSprite](#addvsprite).

### Gotchas
- The hardware sprite keeps showing the old copper data until the next
  [DrawGList](#drawglist) + copper merge/load.

**See also:** [AddVSprite](#addvsprite), [RemIBob](#remibob)

## RemBob

Macro (graphics/gels.h) — not a library call; sets BOBSAWAY in the Bob's Flags.

C expansion: `{(b)->Flags |= BOBSAWAY;}` (`BOBSAWAY` = `$0400`). The Bob is erased and unlinked by
the next [DrawGList](#drawglist); a double-buffered Bob needs two DrawGList passes to vanish.

### Example
```asm
; a0 = struct Bob *; asm equivalent of RemBob (the gels.i macro does not assemble)
RemoveBobLater:
        or.w    #BF_BOBSAWAY,bob_BobFlags(a0)
        rts
```

### Gotchas
- The asm `RemBob` macro in gels.i refers to a non-existent label `b_BobFlags` and fails to
  assemble with the NDK includes; write the `or.w` yourself as above.
- Keep the Bob's buffers allocated until DrawGList has removed it (`BOBNIX` set in Flags).

**See also:** [RemIBob](#remibob), [DrawGList](#drawglist)

## RemIBob
`VOID RemIBob(struct Bob *bob, struct RastPort *rp, struct ViewPort *vp)` — LVO -132 (-$84)
Registers: bob=A0, rp=A1, vp=A2; no result

Remove a Bob immediately: unlink it and erase it from the RastPort.

- **bob** — Bob in the gel list.
- **rp** — RastPort it was drawn into (the image is erased there).
- **vp** — ViewPort used to beam-synchronise the erase.

### Gotchas
- Use this when you must free the Bob's buffers right away; [RemBob](#rembob) only marks it.

**See also:** [RemBob](#rembob), [RemVSprite](#remvsprite)

## InitAnimate

Macro (graphics/gels.h) — not a library call; expands to `*animKey = NULL;`.

C: `#define InitAnimate(animKey) {*(animKey) = NULL;}`. Asm (gels.i): `InitAnimate MACRO` ->
`CLR.L \1`, so pass the address expression of your key variable (`InitAnimate AnimKey`). Call it
once before the first [AddAnimOb](#addanimob).

**See also:** [AddAnimOb](#addanimob), [Animate](#animate)

## AddAnimOb
`VOID AddAnimOb(struct AnimOb *anOb, struct AnimOb **anKey, struct RastPort *rp)` — LVO -156 (-$9C)
Registers: anOb=A0, anKey=A1, rp=A2; no result

Link an AnimOb into an animation list and add all its components' Bobs to the gel list.

- **anOb** — `struct AnimOb` with `HeadComp` -> first `AnimComp`, position `AnY`/`AnX`,
  velocities `YVel`/`XVel`, accelerations `YAccel`/`XAccel`, optional `AnimORoutine`.
- **anKey** — address of your list-head pointer (NULL list = pointer set by
  [InitAnimate](#initanimate)).
- **rp** — RastPort whose `GelsInfo` is initialised; component timers are reset and `AddBob` is
  called for each component Bob.

Positions, velocities and accelerations are fixed point with `ANFRACSIZE` (6) fraction bits:
1 pixel = 64, `ANIMHALF` (`$0020`) = half a pixel.

### Gotchas
- Asm: gels.i declares `ao_XAccel` before `ao_YAccel` (commented "backwards"), the opposite of
  the C struct; lay out data in the C order (YAccel first) -- the ROM most likely follows the C
  layout (unverified).
- Every component's Bob needs its buffers ([GetGBuffers](#getgbuffers)) before the first draw.
- Bartman gcc 15: the inline macro turns `struct AnimOb **` into `volatile struct AnimOb **`,
  which is an incompatible-pointer-types ERROR (verified by compiling). Build the file with
  `-Wno-error=incompatible-pointer-types` or wrap the call in
  `#pragma GCC diagnostic ignored "-Wincompatible-pointer-types"`; the generated call is correct.

**See also:** [Animate](#animate), [InitAnimate](#initanimate), [GetGBuffers](#getgbuffers)

## Animate
`VOID Animate(struct AnimOb **anKey, struct RastPort *rp)` — LVO -162 (-$A2)
Registers: anKey=A0, rp=A1; no result

Advance every AnimOb in the list one step (motion, sequence timers, user routines).

- **anKey** — address of the list-head pointer.
- **rp** — RastPort with the GelsInfo.

For each AnimOb: updates position from velocity/acceleration, calls `AnimORoutine`; for each
component: when `Timer` runs out switches to `NextSeq` (reloading `TimeSet`), calls
`AnimCRoutine`, and sets the component VSprite's Y/X from the object position plus
`YTrans`/`XTrans`. Ring motion (`RingYTrans`/`RingXTrans` applied when a component has
`RINGTRIGGER` set) follows the RKM model (unverified).

### Gotchas
- Only computes positions: follow with [SortGList](#sortglist), [DrawGList](#drawglist) and
  `WaitTOF()`.
- Bartman gcc 15 rejects the `struct AnimOb **` argument through the inline macro (same
  incompatible-pointer-types error and workaround as [AddAnimOb](#addanimob)).

**See also:** [AddAnimOb](#addanimob), [DrawGList](#drawglist)

## InitGMasks
`VOID InitGMasks(struct AnimOb *anOb)` — LVO -174 (-$AE)
Registers: anOb=A0; no result

Call InitMasks for every sequence of every component of an AnimOb.

- **anOb** — the AnimOb; all component Bobs must have their mask buffers.

**See also:** [InitMasks](#initmasks), [GetGBuffers](#getgbuffers)

## GetGBuffers
`BOOL GetGBuffers(struct AnimOb *anOb, struct RastPort *rp, LONG flag)` — LVO -168 (-$A8)
Registers: anOb=A0, rp=A1, flag=D0; result in D0

Allocate the save, border, collision/shadow (and double-buffer) buffers of a whole AnimOb.

- **anOb** — AnimOb whose component Bobs (all sequences) need buffers.
- **rp** — RastPort the object will be drawn into (its depth sizes `SaveBuffer`).
- **flag** — TRUE to also allocate `DBufPacket` and `BufBuffer` for double-buffering.
- **Result** — TRUE if every allocation succeeded.

### Gotchas
- BUGS: on failure the allocations that did succeed are NOT freed. Walk the components and free
  non-NULL buffers yourself (whether [FreeGBuffers](#freegbuffers) tolerates a partial set is not
  documented).
- `CollMask` and `ImageShadow` share one buffer.

**See also:** [FreeGBuffers](#freegbuffers), [InitGMasks](#initgmasks)

## FreeGBuffers
`VOID FreeGBuffers(struct AnimOb *anOb, struct RastPort *rp, LONG flag)` — LVO -600 (-$258)
Registers: anOb=A0, rp=A1, flag=D0; no result

Free the buffers GetGBuffers allocated for an AnimOb.

- **anOb** — the AnimOb.
- **rp** — the same RastPort passed to GetGBuffers.
- **flag** — TRUE if it was allocated with double-buffering (also frees `DBufPacket`/`BufBuffer`).

### Gotchas
- Remove the object's Bobs from the gel list first (and WaitBlit), or DrawGList uses freed memory.

**See also:** [GetGBuffers](#getgbuffers)
