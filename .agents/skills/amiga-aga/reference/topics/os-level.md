# AGA through the OS (graphics.library V39+)

On an OS-friendly program never poke the AGA registers: graphics.library V39 (Kickstart
3.0) drives Alice/Lisa itself, handles alignment, bandwidth, HAM8 plane order and palette
banking, and promotes/scan-doubles for the user's monitor. This page says which calls to
use for what. Prototypes, LVOs, registers and full parameter lists: see the amiga-os skill.

Check `GfxBase->LibNode.lib_Version >= 39` (and intuition V39) before using anything
here; see [detection](detection.md) for the chip bits.

## Mode IDs and the display database

- A display mode is a 32-bit **ModeID**: monitor ID OR mode key (graphics/modeid.h), e.g.
  `PAL_MONITOR_ID | LORES_KEY`, `DBLPAL_MONITOR_ID | DBLPALLORES_KEY`.
- AA-only keys (V39): `HIRESHAM_KEY`, `SUPERHAM_KEY`, `HIRESEHB_KEY`, `SUPEREHB_KEY`, the
  `...LACE` variants, `VGAPRODUCTHAM_KEY`, `EURO72PRODUCTHAM_KEY`...; V39 monitors
  `DBLNTSC_MONITOR_ID`, `DBLPAL_MONITOR_ID`; V40 scan-doubled keys (`LORESSDBL_KEY`...).
- Do not decode ModeID bits. modeid.h guarantees only $80 = EHB and $800 = HAM. HAM8 is a
  HAM key with depth 8.
- Hardcoded IDs may not exist on the user's machine or monitor: prefer asking the database.

| Call | Use it to |
|---|---|
| `BestModeIDA(tags)` | pick the best available ModeID for a size/depth/monitor (`BIDTAG_NominalWidth`, `BIDTAG_NominalHeight`, `BIDTAG_DesiredWidth`, `BIDTAG_DesiredHeight`, `BIDTAG_Depth`, `BIDTAG_MonitorID`, `BIDTAG_DIPFMustHave`, `BIDTAG_DIPFMustNotHave`, `BIDTAG_RedBits`/`GreenBits`/`BlueBits`, `BIDTAG_SourceID`, `BIDTAG_ViewPort`). Returns `INVALID_ID` if none |
| `NextDisplayInfo(id)` | iterate every ModeID in the database (start with `INVALID_ID`) |
| `FindDisplayInfo(id)` | get a `DisplayInfoHandle` for a ModeID |
| `GetDisplayInfoData(handle, buf, size, tagID, id)` | read `DTAG_DISP` (DisplayInfo: `NotAvailable`, `PropertyFlags`, `RedBits`...), `DTAG_DIMS` (DimensionInfo: `MaxDepth`, raster limits, overscan rectangles), `DTAG_MNTR`, `DTAG_NAME` |
| `ModeNotAvailable(id)` | 0 if usable, else `DI_AVAIL_NOCHIPS`, `DI_AVAIL_NOMONITOR`, `DI_AVAIL_NOTWITHGENLOCK` |
| `GetVPModeID(vp)` | ModeID of an existing ViewPort (e.g. the Workbench screen) |
| `CoerceMode(vp, monitorid, flags)` | find the mode a ViewPort is coerced to on another monitor (`PRESERVE_COLORS`, `AVOID_FLICKER`, `IGNORE_MCOMPAT`, graphics/coerce.h) |
| `OpenMonitor(name, id)` | get a MonitorSpec by name or ModeID |

Useful DisplayInfo `PropertyFlags` (graphics/displayinfo.h): `DIPF_IS_AA` (needs AA chips
and the right memory bandwidth), `DIPF_IS_HAM`, `DIPF_IS_EXTRAHALFBRITE`, `DIPF_IS_DUALPF`,
`DIPF_IS_SCANDBL`, `DIPF_IS_SPRITES_CHNG_RES`, `DIPF_IS_SPRITES_BORDER`,
`DIPF_IS_SPRITES_CHNG_BASE`, `DIPF_IS_DBUFFER`, `DIPF_IS_ECS`.

## Opening a 256-colour or HAM8 screen

intuition `OpenScreenTagList(NULL, tags)` with:

| Tag | Purpose |
|---|---|
| `SA_DisplayID` | the ModeID (from BestModeIDA or a key) |
| `SA_Depth` | 8 for 256 colours or HAM8 |
| `SA_Colors32` | initial palette as a LoadRGB32 table ([palette](palette.md)) |
| `SA_ColorMapEntries` | ColorMap size when you need more than `1<<depth` or 32 (palette banking) |
| `SA_Interleaved` | interleaved bitmap |
| `SA_Exclusive` | do not share the display with other screens |
| `SA_SharePens` | Intuition obtains its pens shared; you manage the rest |
| `SA_VideoControl` | tag list passed to VideoControl() on open |
| `SA_FullPalette` | start from the full preferences palette |

Sketch (C):

```c
ULONG id = BestModeIDA((struct TagItem[]){
    { BIDTAG_NominalWidth, 320 }, { BIDTAG_NominalHeight, 256 },
    { BIDTAG_Depth, 8 }, { TAG_DONE, 0 } });
if (id == INVALID_ID || ModeNotAvailable(id)) { /* fall back to a 32-colour mode */ }

struct Screen *scr = OpenScreenTags(NULL,
    SA_DisplayID, id, SA_Depth, 8, SA_Width, 320, SA_Height, 256,
    SA_Colors32, (ULONG)pal32, SA_ShowTitle, FALSE, SA_Quiet, TRUE,
    SA_Exclusive, TRUE, TAG_DONE);
```

## Bitmaps

| Call | Use it to |
|---|---|
| `AllocBitMap(w, h, depth, flags, friend)` | allocate a bitmap and its planes. `BMF_DISPLAYABLE` = aligned/placed so it can be shown in any mode (needed for 2x/4x fetch), `BMF_CLEAR`, `BMF_INTERLEAVED`, `BMF_MINPLANES`; `friend` = a bitmap to be blit-compatible with (e.g. the screen's) |
| `FreeBitMap(bm)` | free a bitmap from AllocBitMap |
| `GetBitMapAttr(bm, attr)` | read `BMA_WIDTH`, `BMA_HEIGHT`, `BMA_DEPTH`, `BMA_FLAGS` instead of peeking `struct BitMap` |
| `AllocDBufInfo(vp)`, `ChangeVPBitMap(vp, bm, dbi)`, `FreeDBufInfo(dbi)` | double buffering on a ViewPort |
| `WriteChunkyPixels(rp, ...)`, `WritePixelArray8`, `ReadPixelArray8` | move 8-bit chunky pixels to/from planar bitmaps |

## Palette and pens

| Call | Use it to |
|---|---|
| `LoadRGB32(vp, table)` | load runs of 32-bit-per-gun colours ([table format](palette.md#os-way-loadrgb32-table-format-v39)) |
| `SetRGB32(vp, n, r, g, b)` | set one colour (32-bit left-justified guns), updates the display |
| `SetRGB32CM(cm, n, r, g, b)` | set a ColorMap entry without touching the display |
| `GetRGB32(cm, first, count, table)` | read colours back (3 ULONGs per colour) |
| `ObtainPen(cm, n, r, g, b, flags)` | allocate a specific or any free pen; `PENF_EXCLUSIVE` (you own the colour), `PENF_NO_SETCOLOR` |
| `ObtainBestPenA(cm, r, g, b, tags)` | share the closest existing colour or allocate one; `OBP_Precision` (`PRECISION_EXACT`, `PRECISION_IMAGE`, `PRECISION_ICON`, `PRECISION_GUI`), `OBP_FailIfBad` |
| `FindColor(cm, r, g, b, maxpen)` | closest pen without allocating |
| `ReleasePen(cm, n)` | release a pen from ObtainPen/ObtainBestPenA (do it for every one before closing) |
| `SetMaxPen(rp, maxpen)`, `SetWriteMask(rp, mask)` | limit rendering to the planes you use (speed) |
| `LoadRGB4`, `SetRGB4` | legacy 12-bit calls; still work, but only 4 bits per gun |

On public screens (Workbench) always go through ObtainBestPen/ObtainPen; on your own
`SA_Exclusive` screen LoadRGB32 on the whole palette is fine.

## VideoControl (graphics/videocontrol.h)

`VideoControl(cm, tags)` sets AGA display features per ViewPort's ColorMap (when changes
take effect, and `VTAG_IMMEDIATE`: see the amiga-os skill):

| Tag | AGA feature |
|---|---|
| `VTAG_BORDERBLANK_SET` / `_CLR` | BRDRBLNK: black border |
| `VTAG_BORDERNOTRANS_SET` / `_CLR` | BRDNTRAN: opaque border for genlock |
| `VTAG_BORDERSPRITE_SET` / `_CLR` | BRDSPRT: sprites in the border |
| `VTAG_SPRITERESN_SET` | SPRES (`SPRITERESN_ECS`, `_140NS`, `_70NS`, `_35NS`) |
| `VTAG_SPEVEN_BASE_SET`, `VTAG_SPODD_BASE_SET` | BPLCON4 sprite colour bases |
| `VTAG_PF1_BASE_SET`, `VTAG_PF2_BASE_SET` | dual-playfield colour bases |
| `VTAG_PF1_TO_SPRITEPRI_SET`, `VTAG_PF2_TO_SPRITEPRI_SET` | sprite priorities |
| `VTAG_CHROMAKEY_SET`, `VTAG_BITPLANEKEY_SET`, `VTAG_CHROMA_PEN_SET`, `VTAG_CHROMA_PLANE_SET` | genlock keying (ZDCTEN / ZDBPEN) |
| `VTAG_FULLPALETTE_SET` | full-palette ColorMap mode (`CMAF_FULLPALETTE`, graphics/view.h) |

## Sprites

`GetExtSpriteA`, `AllocSpriteDataA`, `ChangeExtSpriteA`, `FreeSpriteData` (V39 extended
sprites: allocate sprite data from a bitmap, change the image, release).
`GfxBase->SpriteWidth`/`SpriteFMode` show the current sprite fetch width.

## Chipset and memory information

| Item | Meaning |
|---|---|
| `GfxBase->ChipRevBits0` | `GFXF_AA_ALICE`, `GFXF_AA_LISA`, `GFXF_HR_AGNUS`, `GFXF_HR_DENISE` |
| `SetChipRev(want)` | enable chip features: `SETCHIPREV_A`, `SETCHIPREV_ECS`, `SETCHIPREV_AA`, `SETCHIPREV_BEST` |
| `GfxBase->MemType` | chip RAM bandwidth: `BANDWIDTH_1X`, `BANDWIDTH_2XNML`, `BANDWIDTH_2XDBL`, `BANDWIDTH_4X` |
| `GfxBase->DisplayFlags` | `PAL`, `NTSC`, `GENLOC`, `REALLY_PAL` (V39) |

## Common mistakes

- Poking BPLCON3/COLORxx on an Intuition screen: the next display rebuild overwrites it,
  and other screens get corrupted.
- Allocating planes with AllocMem/AllocRaster for a mode that needs 2x/4x fetch: use
  `AllocBitMap` with `BMF_DISPLAYABLE`.
- Reading `bm->BytesPerRow`/`bm->Depth` of an AllocBitMap bitmap instead of
  `GetBitMapAttr`.
- Hardcoding `PAL_MONITOR_ID|LORES_KEY` for 8 planes and not checking `ModeNotAvailable`.
- Right-justified 8-bit values in SetRGB32/LoadRGB32 (`$FF` instead of `$FFFFFFFF`).
- Obtaining pens and never releasing them on exit.

**See also:** [palette](palette.md), [detection](detection.md), [bitplanes and modes](bitplanes-and-modes.md), [overview](overview.md)
