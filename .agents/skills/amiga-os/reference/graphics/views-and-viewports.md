# graphics.library: views and viewports

A display is a `View` holding a linked list of `ViewPort`s; each ViewPort points to a `RasInfo`
(BitMap + scroll offsets) and a `ColorMap` (see
[View, ViewPort, RasInfo, BitMap](concepts.md#view-viewport-rasinfo-bitmap)). Building one by hand
is: [InitView](#initview), [InitVPort](#initvport), fill in the structures, (V36+) attach a
ViewExtra and ViewPortExtra, [MakeVPort](#makevport) for every ViewPort (intermediate copper
lists), [MrgCop](#mrgcop) (hardware copper lists), [LoadView](#loadview) (show it at the next
vertical blank). Tear down in reverse: LoadView the old View, WaitTOF, then
[FreeVPortCopLists](#freevportcoplists), [FreeCprList](#freecprlist), FreeColorMap,
[GfxFree](#gfxfree). Intuition screens do all of this for you (intuition MakeScreen,
RethinkDisplay); use these calls directly only for a private View or to tweak a screen's ViewPort.
Double buffering: [AllocDBufInfo](#allocdbufinfo) + [ChangeVPBitMap](#changevpbitmap).
Complete example under [MakeVPort](#makevport).

## InitView
`VOID InitView(struct View *view)` — LVO -360 (-$168)
Registers: view=A1; no result

Clear a View structure and set default display offsets.

- **view** — your `struct View` (C 18 bytes, asm `v_SIZEOF`). All fields are zeroed, then
  `DxOffset`/`DyOffset` get values that position a default display on the monitor.

### Gotchas
- Previous contents are ignored: call it before linking ViewPorts into `view->ViewPort`.
- On V36+ also give the View a ViewExtra (GfxNew + GfxAssociate, set `EXTEND_VSTRUCT` in
  `view->Modes`) so MrgCop/LoadView know the monitor; see the example under
  [MakeVPort](#makevport). The `EXTEND_VSTRUCT` requirement is (unverified).

**See also:** [InitVPort](#initvport), [MakeVPort](#makevport), [GfxNew](#gfxnew)

## InitVPort
`VOID InitVPort(struct ViewPort *vp)` — LVO -204 (-$CC)
Registers: vp=A0; no result

Clear a ViewPort structure to defaults before filling it in.

- **vp** — your `struct ViewPort` (C 40 bytes, asm `vp_SIZEOF`). All fields become 0 except
  `SpritePriorities` = `$24` (since 1.2).

After it, set at least `DWidth`, `DHeight`, `RasInfo`, `Modes` (C `HIRES`, `LACE`, `HAM`,
`EXTRA_HALFBRITE`, `DUALPF`, `SPRITES`...; asm `V_HIRES`, `V_LACE`, ...), `ColorMap`, and link
it into `view->ViewPort` (further ViewPorts via `vp->Next`).

### Gotchas
- The autodoc synopsis misnames the prototype `InitViewPort`; the call is `InitVPort`.
- A ViewPort with a NULL `ColorMap` gets default colours from MakeVPort, and colour calls
  (SetRGB4, LoadRGB32...) have nowhere to store values.

**See also:** [InitView](#initview), [MakeVPort](#makevport)

## MakeVPort
`ULONG MakeVPort(struct View *view, struct ViewPort *vp)` — LVO -216 (-$D8)
Registers: view=A0, vp=A1; result in D0

Build the intermediate copper lists for one ViewPort of a View.

- **view** — the View the ViewPort belongs to.
- **vp** — the ViewPort; must have a valid `RasInfo`. With `DUALPF` in `Modes`, `RasInfo->Next`
  must point to the second playfield's RasInfo. A NULL `ColorMap` uses default colours.
- **Result** (V39+) — `MVP_OK` (0), `MVP_NO_MEM` (1), `MVP_NO_VPE` (2, no ViewPortExtra and
  none could be made), `MVP_NO_DSPINS` (3, no memory for copper instructions),
  `MVP_NO_DISPLAY` (4, BitMap misaligned for this mode/depth -- use AllocBitMap with
  `BMF_DISPLAYABLE`). `MVP_OFF_BOTTOM` (5) is private. Before V39 nothing was returned.

The results go into `vp->DspIns` (and `SprIns`, `ClrIns`, `UCopIns` from other calls); run
[MrgCop](#mrgcop) and [LoadView](#loadview) afterwards.

### Example
```c
/* A private 320x200 4-colour display, V39+, then back to the Workbench view. */
#define W 320
#define H 200
#define D 2

static UWORD colors[] = { 0x000, 0xF00, 0x0F0, 0x00F };

int custom_view(void)
{
    struct View view, *oldview = GfxBase->ActiView;   /* save first */
    struct ViewPort vp;
    struct RasInfo ri;
    struct RastPort rp;
    struct DimensionInfo dims;
    struct ViewExtra *vextra = NULL;
    struct ViewPortExtra *vpextra = NULL;
    struct MonitorSpec *mon = NULL;
    struct ColorMap *cm = NULL;
    struct BitMap *bm = NULL;
    DisplayInfoHandle dh;
    ULONG modeid = LORES_KEY;                    /* default monitor lores */
    struct TagItem vctags[] = {
        { VTAG_ATTACH_CM_SET, 0 },
        { VTAG_VIEWPORTEXTRA_SET, 0 },
        { VTAG_NORMAL_DISP_SET, 0 },
        { VTAG_END_CM, 0 }
    };
    int ok = 0, i;

    InitView(&view);                             /* both first: cleanup relies on it */
    InitVPort(&vp);
    if (!(vextra = GfxNew(VIEW_EXTRA_TYPE))) goto done;
    GfxAssociate(&view, vextra);
    view.Modes |= EXTEND_VSTRUCT;
    if (!(mon = OpenMonitor(NULL, modeid))) goto done;
    vextra->Monitor = mon;

    if (!(bm = AllocBitMap(W, H, D, BMF_DISPLAYABLE | BMF_CLEAR, NULL))) goto done;
    view.ViewPort = &vp;
    ri.Next = NULL; ri.BitMap = bm; ri.RxOffset = 0; ri.RyOffset = 0;
    vp.RasInfo = &ri;
    vp.DWidth = W;
    vp.DHeight = H;

    if (!(vpextra = GfxNew(VIEWPORT_EXTRA_TYPE))) goto done;
    if (!(dh = FindDisplayInfo(modeid))) goto done;
    if (!GetDisplayInfoData(dh, (APTR)&dims, sizeof(dims), DTAG_DIMS, modeid)) goto done;
    vpextra->DisplayClip = dims.Nominal;

    if (!(cm = GetColorMap(1 << D))) goto done;
    vctags[0].ti_Data = (ULONG)&vp;
    vctags[1].ti_Data = (ULONG)vpextra;
    vctags[2].ti_Data = (ULONG)dh;
    if (VideoControl(cm, vctags)) goto done;     /* non-zero = error */
    vp.ColorMap = cm;
    LoadRGB4(&vp, colors, 1 << D);

    if (MakeVPort(&view, &vp) != MVP_OK) goto done;
    if (MrgCop(&view) != MCOP_OK) goto done;
    LoadView(&view);

    InitRastPort(&rp);                           /* draw into the BitMap */
    rp.BitMap = bm;
    SetAPen(&rp, 1);
    RectFill(&rp, 20, 20, W - 21, H - 21);
    for (i = 0; i < 150; i++)
        WaitTOF();
    ok = 1;

    LoadView(oldview);                           /* back to Intuition's view */
    WaitTOF();
    WaitTOF();
done:
    FreeVPortCopLists(&vp);                      /* whatever MakeVPort built */
    if (view.LOFCprList) FreeCprList(view.LOFCprList);
    if (view.SHFCprList) FreeCprList(view.SHFCprList);
    FreeColorMap(cm);                            /* NULL ok (V39) */
    if (vpextra) GfxFree(vpextra);
    if (mon) CloseMonitor(mon);
    if (vextra) GfxFree(vextra);
    WaitBlit();
    FreeBitMap(bm);
    return ok;
}
```

### Gotchas
- Before V39 the return value is garbage (the function was void): only test it when
  `GfxBase->LibNode.lib_Version >= 39`.
- Call it again (then MrgCop + LoadView) after changing `Modes`, `DxOffset`/`DyOffset`,
  `DWidth`/`DHeight` or the ColorMap attachment; on ECS a vertical move without MakeVPort
  displays wrongly.
- V37 and earlier: narrow ViewPorts (right edge under ~3/4 of the display width) do not work.
- For an Intuition screen's ViewPort use intuition MakeScreen + RethinkDisplay, not
  MakeVPort/LoadView on Intuition's View.
- Intuition knows nothing about a private View: any RethinkDisplay by another program (screen
  opened, dragged, depth-arranged) replaces your display.

**See also:** [MrgCop](#mrgcop), [LoadView](#loadview), [InitVPort](#initvport),
[VideoControl](#videocontrol), [AllocBitMap](bitmaps-and-blits.md#allocbitmap),
[GetColorMap](colors-and-pens.md#getcolormap)

## MrgCop
`ULONG MrgCop(struct View *view)` — LVO -210 (-$D2)
Registers: view=A1; result in D0

Merge all ViewPorts' copper lists into the View's hardware copper lists.

- **view** — the View; every ViewPort in it must already have been made with
  [MakeVPort](#makevport). Fills `view->LOFCprList` (and `SHFCprList` for interlace).
- **Result** (V39+) — `MCOP_OK` (0), `MCOP_NO_MEM` (1, no memory for the system copper lists),
  `MCOP_NOP` (2, nothing to merge, e.g. no ViewPorts or all hidden). Before V39 void.

### Gotchas
- Each intermediate list (including user copper lists) must be sorted in Y,X order and
  terminated with [CEND](copper-macros.md#cend); the merge relies on it.
- Only test the result on V39+.
- Nothing is shown until [LoadView](#loadview).

**See also:** [MakeVPort](#makevport), [LoadView](#loadview), [FreeCprList](#freecprlist)

## LoadView
`VOID LoadView(struct View *view)` — LVO -222 (-$DE)
Registers: view=A1; no result

Install a View's merged copper lists as the display from the next vertical blank.

- **view** — a View prepared with [MakeVPort](#makevport) + [MrgCop](#mrgcop), or NULL for no
  View at all (blank display, only the copper start-up list runs).

### Example
```asm
; take over / give back the display from an OS-friendly program
TakeDisplay:
        move.l  a6,-(sp)
        move.l  _GfxBase,a6
        move.l  gb_ActiView(a6),OldView ; remember Intuition's View
        sub.l   a1,a1
        jsr     _LVOLoadView(a6)        ; LoadView(NULL)
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOWaitTOF(a6)         ; second one for interlaced displays
        move.l  (sp)+,a6
        rts

GiveDisplay:
        move.l  a6,-(sp)
        move.l  _GfxBase,a6
        move.l  OldView(pc),a1
        jsr     _LVOLoadView(a6)
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOWaitTOF(a6)
        move.l  gb_copinit(a6),$dff000+cop1lc   ; restart system copper list
        move.l  (sp)+,a6
        rts

OldView:
        dc.l    0
```

### Gotchas
- `LoadView(NULL)` does not turn off DMA: bitplane DMA stays enabled and the sprites (mouse
  pointer) keep displaying until you do `OFF_SPRITE` (graphics/gfxmacros.h) or write DMACON.
- Save `GfxBase->ActiView` (asm `gb_ActiView`) BEFORE the first LoadView, and restore it on exit;
  follow with intuition RethinkDisplay if Intuition's screens must be rebuilt. See
  [taking over the display](concepts.md#taking-over-the-display).
- The switch happens at the next vertical blank: WaitTOF before freeing the copper lists of the
  View you just replaced. Two WaitTOF calls (covering both fields of an interlaced View) are the
  usual practice; Bartman's amiga-debug template does `LoadView(0); WaitTOF(); WaitTOF();`.

**See also:** [MrgCop](#mrgcop), [MakeVPort](#makevport),
[WaitTOF](blitter-and-timing.md#waittof), intuition RethinkDisplay

## FreeVPortCopLists
`VOID FreeVPortCopLists(struct ViewPort *vp)` — LVO -540 (-$21C)
Registers: vp=A0; no result

Free all intermediate copper lists of a ViewPort and clear its list pointers.

- **vp** — the ViewPort. Frees the display, colour, sprite and user copper lists and sets
  `DspIns`, `SprIns`, `ClrIns`, `UCopIns` to NULL.

### Gotchas
- The ViewPort must no longer be displayed: LoadView another View and WaitTOF first.
- A user copper list attached to `UCopIns` is freed here too -- do not free it again yourself.
- Does not free the View's hardware lists; use [FreeCprList](#freecprlist) for those.

**See also:** [FreeCprList](#freecprlist), [FreeCopList](#freecoplist),
[UCopperListInit](user-copper-lists.md#ucopperlistinit)

## FreeCprList
`VOID FreeCprList(struct cprlist *cprList)` — LVO -564 (-$234)
Registers: cprList=A0; no result

Free a hardware copper list (cprlist) built by MrgCop.

- **cprList** — `view->LOFCprList`, and for interlaced Views also `view->SHFCprList`.

### Gotchas
- Only after the View is no longer shown (LoadView another View, WaitTOF).
- Check the pointer first: `SHFCprList` is NULL for non-interlaced Views.

**See also:** [MrgCop](#mrgcop), [FreeVPortCopLists](#freevportcoplists)

## FreeCopList
`VOID FreeCopList(struct CopList *copList)` — LVO -546 (-$222)
Registers: copList=A0; no result

Free one intermediate copper list (CopList) and all its instruction blocks.

- **copList** — a `struct CopList`.

### Gotchas
- Rarely needed: [FreeVPortCopLists](#freevportcoplists) frees every list hanging off a
  ViewPort, including the user copper list.
- Never free a list that is still attached to a displayed ViewPort.

**See also:** [FreeVPortCopLists](#freevportcoplists)

## GetVPModeID
`LONG GetVPModeID(CONST struct ViewPort *vp)` — LVO -792 (-$318)
Registers: vp=A0; result in D0

Return the 32-bit display mode ID associated with a ViewPort.

- **vp** — the ViewPort (e.g. `&scr->ViewPort`).
- **Result** — the ModeID, or `INVALID_ID` (`~0`) if none is associated.

Since V36.

### Example
```c
BOOL screen_is_pal(struct Screen *scr)
{
    ULONG id = GetVPModeID(&scr->ViewPort);
    if (id == INVALID_ID)
        return FALSE;
    return (id & MONITOR_ID_MASK) == PAL_MONITOR_ID;
}
```

### Gotchas
- Test against `INVALID_ID`, never against 0: `LORES_KEY` on the default monitor IS 0.
- Do not decode other ModeID bits; ask the display database (GetDisplayInfoData with
  `DTAG_DISP`) for properties.

**See also:** [ModeNotAvailable](display-database.md#modenotavailable),
[FindDisplayInfo](display-database.md#finddisplayinfo), [mode IDs](concepts.md#display-mode-ids)

## ScrollVPort
`VOID ScrollVPort(struct ViewPort *vp)` — LVO -588 (-$24C)
Registers: vp=A0; no result

Update a displayed ViewPort's copper lists after changing its RasInfo offsets or BitMap.

- **vp** — the ViewPort currently displayed. Change `vp->RasInfo->RxOffset` / `RyOffset`
  (hardware scroll within a larger BitMap) or `RasInfo->BitMap` first, then call this.

### Example
```c
/* smooth horizontal scroll of a 640-wide BitMap in a 320-wide ViewPort */
void pan(struct ViewPort *vp)
{
    WORD x;
    for (x = 0; x <= 320; x++) {
        vp->RasInfo->RxOffset = x;
        ScrollVPort(vp);
        WaitTOF();
    }
}
```

### Gotchas
- V37 and earlier poke the lists too slowly and the display can visibly tear; rewritten in V39
  (about 10x faster).
- Swapping `RasInfo->BitMap` here gives a crude double-buffer; on V39 prefer
  [ChangeVPBitMap](#changevpbitmap) with its synchronisation messages.

**See also:** [MakeVPort](#makevport), [ChangeVPBitMap](#changevpbitmap)

## CalcIVG
`UWORD CalcIVG(struct View *v, struct ViewPort *vp)` — LVO -828 (-$33C)
Registers: v=A0, vp=A1; result in D0

Return how many blank lines above a ViewPort its copper instructions need.

- **v** — the View.
- **vp** — the ViewPort; it must have been made (non-NULL `vp->DspIns`).
- **Result** — number of ViewPort-resolution lines needed, or 0 on error.

Since V39.

### Gotchas
- Only the display list (`DspIns`) is counted; user, sprite and colour instructions are ignored.
- Intuition still keeps a gap of at least 3 non-interlaced (6 interlaced) lines between screens,
  so for screens use `MAX(CalcIVG(v, vp), laced ? 6 : 3)`.
- A screen opened behind others may never have been made: result 0.

**See also:** [MakeVPort](#makevport), [VideoControl](#videocontrol)

## VideoControl
`BOOL VideoControl(struct ColorMap *colorMap, struct TagItem *tagarray)` — LVO -708 (-$2C4)
Registers: colorMap=A0, tagarray=A1; result in D0

Read or change ViewPort/ColorMap display options (genlock, sprites, palette) via tags.

- **colorMap** — ColorMap from [GetColorMap](colors-and-pens.md#getcolormap), normally attached
  to a ViewPort (`vp->ColorMap`, e.g. `scr->ViewPort.ColorMap`).
- **tagarray** — `VTAG_*` / `VC_*` tag list (graphics/videocontrol.h, videocontrol.i). Varargs
  form `VideoControlTags(cm, tag, data, ..., TAG_DONE)`.
- **Result** — 0 on success; non-zero for a bad ColorMap, missing or unknown tag (V36-V38
  return an error for the V39 tags).

Since V36. Changes normally take effect at the next MakeVPort (for a screen: intuition
MakeScreen + RethinkDisplay).

| Tag base | _SET | _CLR | _GET | Purpose |
|---|---|---|---|---|
| `VTAG_ATTACH_CM` | `$8000000B` | -- | `$8000001B` | ViewPort the ColorMap belongs to |
| `VTAG_VIEWPORTEXTRA` | `$80000014` | -- | `$80000013` | attach ViewPortExtra |
| `VTAG_NORMAL_DISP` | `$80000010` | -- | `$8000000F` | DisplayInfoHandle (natural mode) |
| `VTAG_COERCE_DISP` | `$80000012` | -- | `$80000011` | DisplayInfoHandle (coerced mode) |
| `VTAG_BORDERBLANK` | `$80000005` | `$80000004` | `$80000017` | border blanking (genlock) |
| `VTAG_BORDERNOTRANS` | `$80000007` | `$80000006` | `$80000018` | border not transparent |
| `VTAG_CHROMAKEY` | `$80000001` | `$80000000` | `$80000015` | chroma-key mode |
| `VTAG_BITPLANEKEY` | `$80000003` | `$80000002` | `$80000016` | bitplane-key mode |
| `VTAG_CHROMA_PEN` | `$80000009` | `$80000008` | `$80000019` | chroma-key pen number |
| `VTAG_CHROMA_PLANE` | `$8000000A` | -- | `$8000001A` | bitplane-key plane number |
| `VTAG_USERCLIP` | `$80000024` | `$80000025` | `$80000023` | clip user copper list at ViewPort bottom (default off) |
| `VTAG_BATCH_CM` | `$8000000E` | `$8000000D` | `$8000001C` | batch mode on/off |
| `VTAG_BATCH_ITEMS` | `$8000001E` | ADD `$8000001F` | `$8000001D` | install/add batched tag lists |
| `VTAG_PF1_BASE` (V39) | `$8000002A` | -- | `$80000026` | colour base of playfield 1 |
| `VTAG_PF2_BASE` (V39) | `$8000002B` | -- | `$80000027` | colour base of playfield 2 |
| `VTAG_SPEVEN_BASE` (V39) | `$8000002C` | -- | `$80000028` | colour base of even sprites |
| `VTAG_SPODD_BASE` (V39) | `$8000002D` | -- | `$80000029` | colour base of odd sprites |
| `VTAG_BORDERSPRITE` (V39) | `$8000002F` | `$80000030` | `$8000002E` | sprites visible in the border |
| `VTAG_SPRITERESN` (V39) | `$80000031` | -- | `$80000032` | `SPRITERESN_ECS` 0, `_140NS` 1, `_70NS` 2, `_35NS` 3, `_DEFAULT` -1 |
| `VTAG_DEFSPRITERESN` | `$8000003B` | -- | `$8000003C` | default sprite resolution |
| `VTAG_PF1_TO_SPRITEPRI` (V39) | `$80000033` | -- | `$80000034` | playfield 1 vs sprite priority |
| `VTAG_PF2_TO_SPRITEPRI` (V39) | `$80000035` | -- | `$80000036` | playfield 2 vs sprite priority |
| `VTAG_FULLPALETTE` (V39) | `$80000038` | `$8000003A` | `$80000039` | load all colours, not just the depth's |
| `VTAG_VPMODEID` | `$80000021` | `$80000022` | `$80000020` | private (Intuition only) |

Single tags: `VTAG_END_CM` `$00000000` (end), `VTAG_NEXTBUF_CM` `$8000000C` (continue in another
tag buffer), `VTAG_IMMEDIATE` `$80000037` (V39; data = pointer to a LONG that is cleared if all
changes were applied at once). V40 `VC_*` tags take a value, their `_Query` twins a pointer to a
LONG: `VC_IntermediateCLUpdate` `$80000080` / `_Query` `$80000081` (default TRUE; FALSE makes
colour loads, ScrollVPort and ChangeVPBitMap faster), `VC_NoColorPaletteLoad` `$80000082` /
`_Query` `$80000083` (load only colour 0, inherit the rest from the ViewPort above; never on
the first ViewPort, undefined with `VTAG_FULLPALETTE`), `VC_DUALPF_Disable` `$80000084` /
`_Query` `$80000085` (dual-playfield ViewPort without the DPF bit: two independently scrolled
bitmaps mixed as one palette).

### Example
```c
/* blank the border of a screen (genlock-style) and remake it */
void blank_border(struct Screen *scr)
{
    if (VideoControlTags(scr->ViewPort.ColorMap,
                         VTAG_BORDERBLANK_SET, TRUE,
                         TAG_DONE) == 0) {
        MakeScreen(scr);
        RethinkDisplay();
    }
}
```

### Gotchas
- `_GET` tags are rewritten IN PLACE to the matching `_SET`/`_CLR` tag (data holds the value):
  never pass a read-only/const tag array, and re-initialise a reused array. `VTAG_IMMEDIATE` and
  the V40 `VC_*` tags are not rewritten.
- After changing a palette base (`VTAG_PF1_BASE` etc.) remake the ViewPort before calling any
  colour function (SetRGB4, LoadRGB32...).
- `VTAG_IMMEDIATE` only covers some changes; if the flag is still non-zero, MakeVPort + MrgCop
  (screens: MakeScreen + RethinkDisplay).
- Sprite resolution follows Intuition's default unless you set `VTAG_SPRITERESN_SET`.
- The NDK 3.9 prototype returns `BOOL`; the autodoc says ULONG error. Test for non-zero.

**See also:** [GetColorMap](colors-and-pens.md#getcolormap), [MakeVPort](#makevport),
[CalcIVG](#calcivg), [UCopperListInit](user-copper-lists.md#ucopperlistinit)

## AllocDBufInfo
`struct DBufInfo * AllocDBufInfo(struct ViewPort *vp)` — LVO -966 (-$3C6)
Registers: vp=A0; result in D0

Allocate the DBufInfo structure needed for double buffering a ViewPort.

- **vp** — the ViewPort to double-buffer.
- **Result** — DBufInfo pointer, or 0 if out of memory or the ViewPort's mode cannot
  double-buffer (`DIPF_IS_DBUFFER` not set).

Since V39.

Applications may only use `dbi_SafeMessage`, `dbi_DispMessage` (set their `mn_ReplyPort`),
`dbi_UserData1` and `dbi_UserData2`. `dbi_SafeMessage` is replied when the previously shown
BitMap may be drawn into; `dbi_DispMessage` when the new BitMap has been displayed at least once
and ChangeVPBitMap may be called again.

### Example
```c
/* flip two BMF_DISPLAYABLE bitmaps of identical layout on a ViewPort */
BOOL flip_loop(struct ViewPort *vp, struct BitMap *bm[2], struct RastPort *rp, int frames)
{
    struct MsgPort *safe = CreateMsgPort(), *disp = CreateMsgPort();
    struct DBufInfo *dbi = AllocDBufInfo(vp);
    BOOL can_write = TRUE, can_swap = TRUE;
    int cur = 1;

    if (safe && disp && dbi) {
        dbi->dbi_SafeMessage.mn_ReplyPort = safe;
        dbi->dbi_DispMessage.mn_ReplyPort = disp;
        while (frames--) {
            if (!can_write) { WaitPort(safe); GetMsg(safe); can_write = TRUE; }
            rp->BitMap = bm[cur];                /* render the hidden buffer */
            SetRast(rp, frames & 1);
            if (!can_swap) { WaitPort(disp); GetMsg(disp); can_swap = TRUE; }
            WaitBlit();                          /* rendering must be finished */
            ChangeVPBitMap(vp, bm[cur], dbi);
            can_write = can_swap = FALSE;
            cur ^= 1;
        }
        if (!can_swap) { WaitPort(disp); GetMsg(disp); }   /* collect pending replies */
        if (!can_write) { WaitPort(safe); GetMsg(safe); }
    }
    FreeDBufInfo(dbi);                           /* NULL is a no-op */
    if (safe) DeleteMsgPort(safe);
    if (disp) DeleteMsgPort(disp);
    return dbi != NULL;
}
```

### Gotchas
- Allocate DBufInfo only with this call: the structure grows in later releases.
- For Intuition screens use intuition AllocScreenBuffer/ChangeScreenBuffer instead of calling
  this on `scr->ViewPort`.

**See also:** [ChangeVPBitMap](#changevpbitmap), [FreeDBufInfo](#freedbufinfo),
[AllocBitMap](bitmaps-and-blits.md#allocbitmap)

## FreeDBufInfo
`VOID FreeDBufInfo(struct DBufInfo *dbi)` — LVO -972 (-$3CC)
Registers: dbi=A1; no result

Free a DBufInfo obtained from AllocDBufInfo.

- **dbi** — the DBufInfo; NULL is a no-op.

Since V39.

### Gotchas
- If you used the reply-port synchronisation, every pending `dbi_SafeMessage` /
  `dbi_DispMessage` must have come back before freeing.

**See also:** [AllocDBufInfo](#allocdbufinfo), [ChangeVPBitMap](#changevpbitmap)

## ChangeVPBitMap
`VOID ChangeVPBitMap(struct ViewPort *vp, struct BitMap *bm, struct DBufInfo *db)` — LVO -942 (-$3AE)
Registers: vp=A0, bm=A1, db=A2; no result

Swap the BitMap a displayed ViewPort shows, synced to the display (double buffering).

- **vp** — the displayed ViewPort; `vp->RasInfo->BitMap` is set to `bm`.
- **bm** — new BitMap with exactly the same layout as the current one (depth, alignment,
  BytesPerRow) -- allocate both the same way with `BMF_DISPLAYABLE`.
- **db** — DBufInfo from [AllocDBufInfo](#allocdbufinfo) for this ViewPort.

Since V39. See the loop under [AllocDBufInfo](#allocdbufinfo).

### Gotchas
- WaitBlit before swapping so the new frame is completely rendered.
- When using the reply messages, do not call it again with the same DBufInfo until
  `dbi_DispMessage` came back (and all replies are in before FreeDBufInfo).
- `VC_IntermediateCLUpdate` FALSE (V40, [VideoControl](#videocontrol)) makes it faster.

**See also:** [AllocDBufInfo](#allocdbufinfo), [ScrollVPort](#scrollvport),
[AllocBitMap](bitmaps-and-blits.md#allocbitmap)

## GfxNew
`APTR GfxNew(ULONG gfxNodeType)` — LVO -660 (-$294)
Registers: gfxNodeType=D0; result in D0

Allocate a graphics extended-node structure (ViewExtra, ViewPortExtra, MonitorSpec...).

- **gfxNodeType** — `VIEW_EXTRA_TYPE` (1), `VIEWPORT_EXTRA_TYPE` (2), `SPECIAL_MONITOR_TYPE` (3),
  `MONITOR_SPEC_TYPE` (4) (graphics/gfxnodes.h, gfxnodes.i).
- **Result** — pointer to the new structure (starts with `struct ExtendedNode`), or NULL.

Since V36.

### Gotchas
- The NDK 3.9 prototype returns `APTR`; the autodoc says `struct ExtendedNode *`. Assign it to
  `struct ViewExtra *` / `struct ViewPortExtra *` directly in C.
- Free only with [GfxFree](#gfxfree), never exec FreeMem.
- A ViewExtra is linked to its View with [GfxAssociate](#gfxassociate); a ViewPortExtra is
  attached with VideoControl `VTAG_VIEWPORTEXTRA_SET` (see the [MakeVPort](#makevport) example).

**See also:** [GfxFree](#gfxfree), [GfxAssociate](#gfxassociate), [GfxLookUp](#gfxlookup)

## GfxFree
`VOID GfxFree(APTR gfxNodePtr)` — LVO -666 (-$29A)
Registers: gfxNodePtr=A0; no result

Free a structure allocated with GfxNew, removing any association first.

- **gfxNodePtr** — pointer from [GfxNew](#gfxnew).

Since V36.

### Gotchas
- Passing anything not obtained from GfxNew causes an Alert.
- Remove the View from the display (LoadView another View) before freeing its ViewExtra.

**See also:** [GfxNew](#gfxnew), [GfxAssociate](#gfxassociate)

## GfxAssociate
`VOID GfxAssociate(CONST APTR associateNode, APTR gfxNodePtr)` — LVO -672 (-$2A0)
Registers: associateNode=A0, gfxNodePtr=A1; no result

Link a GfxNew structure to another structure so GfxLookUp can find it from that pointer.

- **associateNode** — pointer of the owning structure (e.g. `&view`).
- **gfxNodePtr** — the extended node from [GfxNew](#gfxnew) (e.g. a ViewExtra).

Since V36.

### Gotchas
- The association is removed automatically when the node is freed with [GfxFree](#gfxfree).
- For a custom View also set `EXTEND_VSTRUCT` in `view.Modes` (unverified that it is required).

**See also:** [GfxLookUp](#gfxlookup), [GfxNew](#gfxnew)

## GfxLookUp
`APTR GfxLookUp(CONST APTR associateNode)` — LVO -702 (-$2BE)
Registers: associateNode=A0; result in D0

Find the extended node (e.g. ViewExtra) associated with a structure pointer.

- **associateNode** — the pointer used with [GfxAssociate](#gfxassociate) (typically a View).
- **Result** — the associated extended node. Test for NULL before use.

Since V36. The autodoc file spells it `GfxLookUP`; the function, LVO and prototype are
`GfxLookUp`.

### Example
```c
/* which monitor does the current display use? */
struct MonitorSpec *current_monitor(void)
{
    struct ViewExtra *ve = NULL;
    if (GfxBase->ActiView)
        ve = GfxLookUp(GfxBase->ActiView);
    return ve ? ve->Monitor : NULL;
}
```

### Gotchas
- Prototype returns `APTR` in NDK 3.9 (autodoc: `struct ExtendedNode *`).

**See also:** [GfxAssociate](#gfxassociate), [GfxNew](#gfxnew), [GfxFree](#gfxfree)
