# graphics.library: concepts

Background shared by many graphics.library calls: the GfxBase fields programs actually read,
the View -> ViewPort -> RasInfo -> BitMap display chain, RastPorts and drawing modes, display
mode IDs, colour value formats, bitmap layouts, and the rules for taking over the display and
the blitter. Offsets below were checked by compiling against the NDK 3.9 headers (gcc
`offsetof`) and assembling against the NDK `.i` files (vasm).

## GfxBase fields

`struct GfxBase` (graphics/gfxbase.h, asm graphics/gfxbase.i) starts with a `struct Library`,
so `lib_Version` is at `LIB_VERSION` ($14). Most other fields are private; these are the ones
programs commonly read. Never write them.

| C field | asm label | Offset | Meaning |
|---|---|---|---|
| `ActiView` | `gb_ActiView` | $22 | `struct View *` currently loaded (save it before `LoadView`) |
| `copinit` | `gb_copinit` | $26 | system copper start-up list; write it to COP1LC to give the display back |
| `LOFlist` | `gb_LOFlist` | $32 | copper list running for long (or non-interlaced) frames |
| `SHFlist` | `gb_SHFlist` | $36 | copper list for short frames (interlace) |
| `DefaultFont` | `gb_DefaultFont` | $9A | default system `struct TextFont *` |
| `Modes` | `gb_Modes` | $9E | copy of the current first BPLCON0 (asm comment says "bltcon0") |
| `DisplayFlags` | `gb_DisplayFlags` | $CE | `NTSC` 1, `GENLOC` 2, `PAL` 4, `TODA_SAFE` 8, `REALLY_PAL` 16 (V39), `LPEN_SWAP_FRAMES` 32 (V40) |
| `MaxDisplayRow` | `gb_MaxDisplayRow` | $D4 | hardware internal -- header says do not use |
| `MaxDisplayColumn` | `gb_MaxDisplayColumn` | $D6 | hardware internal -- do not use |
| `NormalDisplayRows` | `gb_NormalDisplayRows` | $D8 | default visible rows of the standard display |
| `NormalDisplayColumns` | `gb_NormalDisplayColumns` | $DA | default visible columns |
| `ChipRevBits0` | `gb_ChipRevBits0` | $EC | UBYTE chip set feature bits (below) |
| `MemType` | `gb_MemType` | $ED | chip RAM bandwidth: `BUS_16`/`NML_CAS` 0, `BUS_32` 1, `DBL_CAS` 2 |
| `TopLine` | `gb_TopLine` | $19A | internal |
| `ActiViewCprSemaphore` | `gb_ActiViewCprSemaphore` | $19C | lock for the active View's copper lists |
| `ChunkyToPlanarPtr` (= `HWEmul[0]`) | `gb_ChunkyToPlanarPtr` | $1FC | chunky-to-planar hardware register, or NULL; only exists from V40 |

`ChipRevBits0` bits (`GFXB_` bit numbers / `GFXF_` masks, same names in C and asm):
`GFXB_HR_AGNUS` 0 (= `GFXB_BIG_BLITS`, ECS Agnus), `GFXB_HR_DENISE` 1 (ECS Denise),
`GFXB_AA_ALICE` 2 (AGA Alice), `GFXB_AA_LISA` 3 (AGA Lisa), `GFXB_AA_MLISA` 4 (internal).
[SetChipRev](blitter-and-timing.md#setchiprev) takes `SETCHIPREV_A`, `SETCHIPREV_ECS`,
`SETCHIPREV_AA`, `SETCHIPREV_BEST`.

`DisplayFlags` `PAL`/`NTSC` reflect how the system started the display; `REALLY_PAL` (V39) is
the real crystal frequency, which can differ when a boot menu forced the other mode.

```c
/* chip set / video standard checks */
BOOL have_aga(void)
{
    return GfxBase->LibNode.lib_Version >= 39 &&
           (GfxBase->ChipRevBits0 & GFXF_AA_ALICE) != 0;
}

BOOL is_pal(void)
{
    return (GfxBase->DisplayFlags & PAL) != 0;
}
```

```asm
; d0 = 1 if AGA, else 0
IsAGA:
        move.l  a6,-(sp)
        move.l  _GfxBase,a6
        moveq   #0,d0
        cmp.w   #39,LIB_VERSION(a6)
        blo.s   .out
        btst    #GFXB_AA_ALICE,gb_ChipRevBits0(a6)
        beq.s   .out
        moveq   #1,d0
.out:   move.l  (sp)+,a6
        rts
```

## View, ViewPort, RasInfo, BitMap

A display is described by a chain of structures (graphics/view.h, view.i):

```text
struct View  (18 bytes, v_SIZEOF)
  ViewPort ----> struct ViewPort (40 bytes, vp_SIZEOF)   one per screen band, linked by Next
                   ColorMap ----> struct ColorMap   (GetColorMap; colours of this band)
                   DspIns/SprIns/ClrIns/UCopIns      intermediate copper lists (MakeVPort)
                   DWidth, DHeight, DxOffset, DyOffset, Modes (HIRES, LACE, HAM, DUALPF...)
                   RasInfo ----> struct RasInfo (12 bytes, ri_SIZEOF)
                                   Next  -> second RasInfo for DUALPF playfield 2
                                   BitMap -> struct BitMap (40 bytes, bm_SIZEOF)
                                   RxOffset, RyOffset  scroll position inside the BitMap
  LOFCprList / SHFCprList             final hardware copper lists (MrgCop)
```

| C | asm | Offset |
|---|---|---|
| `View.ViewPort` / `LOFCprList` / `SHFCprList` / `Modes` | `v_ViewPort` / `v_LOFCprList` / `v_SHFCprList` / `v_Modes` | 0 / 4 / 8 / $10 |
| `ViewPort.ColorMap` / `DxOffset` / `Modes` / `RasInfo` | `vp_ColorMap` / `vp_DxOffset` / `vp_Modes` / `vp_RasInfo` | 4 / $1C / $20 / $24 |
| `RasInfo.Next` / `BitMap` / `RxOffset` | `ri_Next` / `ri_BitMap` / `ri_RxOffset` | 0 / 4 / 8 |
| `BitMap.Depth` / `Planes[0]` | `bm_Depth` / `bm_Planes` | 5 / 8 |

Building one by hand: [InitView](views-and-viewports.md#initview),
[InitVPort](views-and-viewports.md#initvport), fill the fields, attach a ColorMap and BitMap,
[MakeVPort](views-and-viewports.md#makevport) (per ViewPort) ->
[MrgCop](views-and-viewports.md#mrgcop) -> [LoadView](views-and-viewports.md#loadview). After
changing `RxOffset`/`RyOffset` call [ScrollVPort](views-and-viewports.md#scrollvport). Intuition
builds all of this for each screen: use `&screen->ViewPort`, `&screen->RastPort` and
`screen->RastPort.BitMap` rather than your own View when an Intuition screen is enough.

## RastPort basics

A `struct RastPort` (graphics/rastport.h, 100 bytes, `rp_SIZEOF`) is the drawing context all
rendering calls take: where to draw (`BitMap`, `Layer`), with what (`FgPen`, `BgPen`, `AOlPen`,
`DrawMode`, `Mask`, patterns, `Font`) and the current pen position (`cp_x`, `cp_y`).

- [InitRastPort](rastport-attrs.md#initrastport) sets defaults but not the BitMap: set
  `rp.BitMap` yourself.
- `Layer` NULL means no clipping at all: drawing outside the BitMap overwrites memory. A window's
  `RPort` has a Layer and is clipped.
- From V39 use the accessors ([SetAPen](rastport-attrs.md#setapen),
  [GetAPen](rastport-attrs.md#getapen), [SetABPenDrMd](rastport-attrs.md#setabpendrmd),
  [SetWriteMask](rastport-attrs.md#setwritemask)...) instead of poking fields: the setters also
  rebuild the cached `minterms`.
- Area fills ([AreaMove](area-fill.md#areamove)... [AreaEnd](area-fill.md#areaend)) need
  `rp->AreaInfo` ([InitArea](area-fill.md#initarea)) AND `rp->TmpRas`
  ([InitTmpRas](area-fill.md#inittmpras), chip RAM at least one plane of the area);
  [Flood](area-fill.md#flood) needs a TmpRas as large as the RastPort's raster.
- GELs need `rp->GelsInfo` ([InitGels](gels.md#initgels)).
- Asm field names: `rp_Layer` 0, `rp_BitMap` 4, `rp_TmpRas` $C, `rp_AreaInfo` $10, `rp_GelsInfo`
  $14, `rp_FgPen` $19, `rp_BgPen` $1A, `rp_AOLPen` $1B, `rp_DrawMode` $1C, `rp_cp_x` $24,
  `rp_Font` $34.

## Drawing modes

`DrawMode` values (C rastport.h / asm rastport.i):

| C | asm | Value | Effect |
|---|---|---|---|
| `JAM1` | `RP_JAM1` | 0 | set bits of the shape drawn in APen; background untouched |
| `JAM2` | `RP_JAM2` | 1 | set bits in APen, clear bits in BPen (text cells, patterns) |
| `COMPLEMENT` | `RP_COMPLEMENT` | 2 | set bits invert (XOR) the destination pixels |
| `INVERSVID` | `RP_INVERSVID` | 4 | OR-in flag: swap the sense of the shape (inverse text) |

Combine the flag: `JAM2|INVERSVID`, `JAM1|INVERSVID`. `COMPLEMENT` twice restores the original
(rubber-band lines). The write `Mask` still limits which planes change.

## Display mode IDs

From V36 a display mode is a 32-bit ModeID (graphics/modeid.h / modeid.i) = monitor part
(`MONITOR_ID_MASK` $FFFF1000) OR a mode key. `INVALID_ID` is ~0 ($FFFFFFFF).

| Monitor | ID | Mode keys (default/NTSC/PAL monitors) | Value |
|---|---|---|---|
| `DEFAULT_MONITOR_ID` | $00000000 | `LORES_KEY` | $00000000 |
| `NTSC_MONITOR_ID` | $00011000 | `HIRES_KEY` | $00008000 |
| `PAL_MONITOR_ID` | $00021000 | `SUPER_KEY` | $00008020 |
| `VGA_MONITOR_ID` | $00031000 | `HAM_KEY` | $00000800 |
| `A2024_MONITOR_ID` | $00041000 | `LORESLACE_KEY` / `HIRESLACE_KEY` | $00000004 / $00008004 |
| `EURO72_MONITOR_ID` | $00061000 | `EXTRAHALFBRITE_KEY` | $00000080 |
| `EURO36_MONITOR_ID` | $00071000 | `LORESDPF_KEY` | $00000400 |
| `SUPER72_MONITOR_ID` | $00081000 | `HIRESHAM_KEY` / `SUPERHAM_KEY` (V39) | $00008800 / $00008820 |
| `DBLNTSC_MONITOR_ID` | $00091000 | `HIRESEHB_KEY` / `SUPEREHB_KEY` (V39) | $00008080 / $000080A0 |
| `DBLPAL_MONITOR_ID` | $000A1000 | `LORESSDBL_KEY` (V40) | $00000008 |

Example: PAL low resolution = `PAL_MONITOR_ID|LORES_KEY` = $00021000; PAL HAM interlace =
`PAL_MONITOR_ID|HAMLACE_KEY`. The header warns not to decode ModeID bits (only $80 = EHB and
$800 = HAM are guaranteed); ask the database instead
([GetDisplayInfoData](display-database.md#getdisplayinfodata) with `DTAG_DISP` and the
`DIPF_IS_...` flags), pick modes with [BestModeIDA](display-database.md#bestmodeida), check with
[ModeNotAvailable](display-database.md#modenotavailable), read a ViewPort's mode with
[GetVPModeID](views-and-viewports.md#getvpmodeid). The old `ViewPort.Modes` bits (`HIRES`
$8000, `LACE` 4, `SUPERHIRES` $20, `HAM` $800, `EXTRA_HALFBRITE` $80, `DUALPF` $400, `PFBA` $40;
asm `V_HIRES`...) coincide with the default-monitor keys.

## 32-bit colour values

The V39 colour calls ([SetRGB32](colors-and-pens.md#setrgb32),
[LoadRGB32](colors-and-pens.md#loadrgb32), [GetRGB32](colors-and-pens.md#getrgb32),
[ObtainBestPenA](colors-and-pens.md#obtainbestpena), [FindColor](colors-and-pens.md#findcolor))
take each gun as an unsigned 32-bit fraction, left-justified: `$FFFFFFFF` = 100%, `$80000000`
= 50%, 0 = none. The display keeps only its top bits (4 on OCS/ECS, 8 on AGA; query
`DisplayInfo.RedBits` etc.).

- 8-bit component `c` -> `c * $01010101` (e.g. `$C0` -> `$C0C0C0C0`).
- 4-bit component `c` -> `c * $11111111`.
- 32-bit back to 8-bit: `v >> 24`.
- LoadRGB32 table: repeated `UWORD count, UWORD first, count x (ULONG r, g, b)`, ended by a
  count of 0 (`dc.l 0` is a safe terminator). GetRGB32 fills a bare `r,g,b,...` array with no
  header.

The old calls ([SetRGB4](colors-and-pens.md#setrgb4), [LoadRGB4](colors-and-pens.md#loadrgb4),
[GetRGB4](colors-and-pens.md#getrgb4)) use `$0RGB` words, 0-15 per gun.

## Pen sharing vs direct colour setting

- Your own screen or hand-built View: set any colour directly with LoadRGB32/SetRGB32 (or the
  RGB4 calls). Fastest for fades and palette effects.
- A public screen (Workbench or someone else's): the palette is shared. Get colours with
  [ObtainBestPenA](colors-and-pens.md#obtainbestpena) (shared, may return an existing close
  colour) and give them back with [ReleasePen](colors-and-pens.md#releasepen). Never SetRGB a
  shared pen. For a pen you must recolour (cycling), use
  [ObtainPen](colors-and-pens.md#obtainpen) with `PENF_EXCLUSIVE`.
- If no sharable pens remain, [FindColor](colors-and-pens.md#findcolor) gives the nearest
  existing pen without allocating.
- Sharing needs a `PalExtra` on the ColorMap: Intuition screens have one; hand-built ColorMaps
  need [AttachPalExtra](colors-and-pens.md#attachpalextra).
- All of this is V39+. Under V37 there is no allocation: use fixed pens (DrawInfo pens from
  Intuition) on shared screens.

## Bitmaps: planar and interleaved

A standard Amiga BitMap is planar: `Depth` separate planes, each `BytesPerRow * Rows` bytes of
chip RAM, 1 bit per pixel, bit 7 of byte 0 = leftmost pixel. Pixel value = the bits of all
planes at that position (plane 0 = bit 0). `BytesPerRow` is even (rows are word-aligned);
the obsolete macro `RASSIZE(w,h)` gives one plane's size.

[AllocBitMap](bitmaps-and-blits.md#allocbitmap) flags (gfx.h / gfx.i, `BMB_` bit numbers):

| Flag | Bit | Meaning |
|---|---|---|
| `BMF_CLEAR` | 0 | clear all planes to colour 0 |
| `BMF_DISPLAYABLE` | 1 | allocate with the alignment needed to be displayed (RasInfo, custom screen bitmap) |
| `BMF_INTERLEAVED` | 2 | one allocation for all planes, less colour flashing on deep displays; falls back to planar if no contiguous memory |
| `BMF_STANDARD` | 3 | reported by [GetBitMapAttr](bitmaps-and-blits.md#getbitmapattr): ordinary planar chip RAM |
| `BMF_MINPLANES` | 4 | system use: allocate only `depth` plane pointers |

- A friend bitmap makes the allocation match another bitmap's format (on a graphics card it
  may not be planar at all): then only blit to/from it or draw through a RastPort.
- Read sizes and flags back with GetBitMapAttr rather than trusting `BytesPerRow`/`Rows`; they
  may be padded.
- Everything the custom chips touch (displayed planes, blitter sources/destinations, masks,
  TmpRas, sprite and bob images) must be chip RAM.

## Taking over the display

Games and demos that want the whole display while staying OS-friendly remove the OS View,
own the blitter, then run their own copper list; on exit they give everything back:

1. `oldview = GfxBase->ActiView`.
2. `LoadView(NULL)` then `WaitTOF()` twice (so both fields of an interlaced display are gone).
   Sprites (the pointer) and display DMA stay on after `LoadView(NULL)` -- switch sprite DMA
   off yourself.
3. `OwnBlitter()` + `WaitBlit()` before touching blitter registers yourself; do not call graphics
   rendering functions while you own it.
4. Install your copper list (COP1LC, COPJMP1), set DMACON/INTENA as needed -- register-level
   details are in the amiga-hardware skill.
5. Exit: `WaitBlit()`, restore DMA/interrupts, write `GfxBase->copinit` back to COP1LC (the
   template does it before `LoadView(oldview)`, the [LoadView](views-and-viewports.md#loadview)
   example after -- both end with the system copper running), `DisownBlitter()`,
   `LoadView(oldview)`, `WaitTOF()` twice; intuition `RethinkDisplay()` rebuilds the screens if
   needed.

Bartman's amiga-debug project template follows the same order (it also Forbids and Disables
around the hardware access).

```c
static struct View *old_view;

void take_display(void)
{
    old_view = GfxBase->ActiView;
    LoadView(NULL);
    WaitTOF();
    WaitTOF();
    OwnBlitter();
    WaitBlit();
}

void give_back_display(void)
{
    struct Custom *hw = (struct Custom *)0xDFF000;

    WaitBlit();
    hw->cop1lc = (ULONG)GfxBase->copinit;   /* system copper start-up list */
    DisownBlitter();
    LoadView(old_view);
    WaitTOF();
    WaitTOF();
}
```

```asm
TakeDisplay:
        move.l  a6,-(sp)
        move.l  _GfxBase,a6
        move.l  gb_ActiView(a6),OldView
        sub.l   a1,a1
        jsr     _LVOLoadView(a6)        ; LoadView(NULL)
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOOwnBlitter(a6)
        jsr     _LVOWaitBlit(a6)
        move.l  (sp)+,a6
        rts

GiveBackDisplay:
        move.l  a6,-(sp)
        move.l  _GfxBase,a6
        jsr     _LVOWaitBlit(a6)
        move.l  gb_copinit(a6),$dff080  ; COP1LC
        jsr     _LVODisownBlitter(a6)
        move.l  OldView(pc),a1
        jsr     _LVOLoadView(a6)
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOWaitTOF(a6)
        move.l  (sp)+,a6
        rts

OldView:
        dc.l    0
```

## Blitter ownership

- Every graphics rendering call may start the blitter and return before it finishes. Before the
  CPU reads blitted data, frees memory the blitter uses, or pokes blitter registers, call
  [WaitBlit](blitter-and-timing.md#waitblit) (it preserves D0/D1/A0/A1).
- Direct register use: [OwnBlitter](blitter-and-timing.md#ownblitter) -> WaitBlit -> write
  registers (BLTSIZE last) -> WaitBlit -> [DisownBlitter](blitter-and-timing.md#disownblitter).
  OwnBlitter does not nest and sleeps: no graphics blits, no second OwnBlitter, no interrupts.
- Asynchronous use: [QBlit](blitter-and-timing.md#qblit)/[QBSBlit](blitter-and-timing.md#qbsblit)
  callbacks run in interrupt context -- no Wait, allocation, FreeMem or DOS in them.

## Asm vs C names

The asm includes rename several graphics constants; the C spelling does not assemble.

| C (include_h) | asm (include_i) |
|---|---|
| `JAM1`, `JAM2`, `COMPLEMENT`, `INVERSVID` | `RP_JAM1`, `RP_JAM2`, `RP_COMPLEMENT`, `RP_INVERSVID` |
| `FRST_DOT`, `ONE_DOT`, `DBUFFER`, `AREAOUTLINE`, `NOCROSSFILL` | `RPF_FRST_DOT`, `RPF_ONE_DOT`, `RPF_DBUFFER`, `RPF_AREAOUTLINE`, `RPF_NOCROSSFILL` (+ `RPB_` bit numbers; `FRST_DOT`/`ONE_DOT` also exist) |
| `RastPort.AOlPen` | `rp_AOLPen` |
| `HIRES`, `LACE`, `SUPERHIRES`, `HAM`, `DUALPF`, `PFBA`, `EXTRA_HALFBRITE`, `SPRITES`, `VP_HIDE`, `DOUBLESCAN`, `EXTENDED_MODE` | `V_HIRES`, `V_LACE`, `V_SUPERHIRES`, `V_HAM`, `V_DUALPF`, `V_PFBA`, `V_EXTRA_HALFBRITE`, `V_SPRITES`, `V_VP_HIDE`, `V_DOUBLESCAN`, `V_EXTENDED_MODE` |
| `BORDERSPRITES` | `BORDER_SPRITES` |
| `VPXF_LAST` | `VPXF_VP_LAST` |
| `VSPRITE`, `SAVEBACK`, `OVERLAY`, `MUSTDRAW`, ... | `VSF_VSPRITE`, `VSF_SAVEBACK`, ... (`VSB_` bit numbers) |
| `SAVEBOB`, `BOBISCOMP`, `BOBSAWAY`, ... | `BF_SAVEBOB`, `BF_BOBISCOMP`, `BF_BOBSAWAY`, ... (`BB_` bit numbers) |
| `CLEANUP` (bltnode stat) | `CLEANME` |
| `SPECIAL_FLAGS` (modeid.h) | `MUST_FLAGS` (modeid.i) |
| `SPRITE_ATTACHED` | not defined in the asm includes (`$80`) |
| `DisplayInfo.RedBits`/`GreenBits`/`BlueBits` | `RedBits`/`GreenBits`/`BlueBits` (no `dis_` prefix, unlike the other fields) |
| `GfxBase->ChunkyToPlanarPtr` | `gb_ChunkyToPlanarPtr` |

Asm label clashes: `STRUCTURE GfxBase,...` in gfxbase.i defines the symbol `GfxBase` (likewise
`RastPort`, `BitMap`, `View`, `ViewPort`, `TextFont`, `SimpleSprite`, `DisplayInfo`, and the gels.i
names `VS`, `BOB`, `AC`, `AO`, `DBP`). A program variable with one of those
names fails to assemble ("label redefined") -- name the library base `_GfxBase`.
