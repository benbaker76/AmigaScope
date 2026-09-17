# graphics.library: display database and monitors

Since V36 every display mode is a 32-bit ModeID (see [display mode IDs](concepts.md#display-mode-ids))
with a record in the graphics display database. Walk all records with
[NextDisplayInfo](#nextdisplayinfo), get a handle with [FindDisplayInfo](#finddisplayinfo) and copy
out typed data with [GetDisplayInfoData](#getdisplayinfodata): `DTAG_DISP` ($80000000,
`struct DisplayInfo`: availability, `DIPF_IS_*` properties, colour bits), `DTAG_DIMS` ($80001000,
`struct DimensionInfo`: depth and overscan rectangles), `DTAG_MNTR` ($80002000,
`struct MonitorInfo`), `DTAG_NAME` ($80003000, `struct NameInfo`). Check a mode is usable with
[ModeNotAvailable](#modenotavailable); let the system pick one with [BestModeIDA](#bestmodeida)
(V39) or [CoerceMode](#coercemode) (V39). Do not decode ModeID bits yourself (modeid.h: only bit 7
= EHB and bit 11 = HAM are stable). [OpenMonitor](#openmonitor) gets the `MonitorSpec` a custom
View's ViewExtra needs. Structures and `DIPF_`/`DI_AVAIL_` flags: graphics/displayinfo.h
(asm displayinfo.i: `dis_`, `dim_`, `mtr_`, `nif_` prefixes; `RedBits`/`GreenBits`/`BlueBits` have
no prefix).

## NextDisplayInfo
`ULONG NextDisplayInfo(ULONG displayID)` — LVO -732 (-$2DC)
Registers: displayID=D0; result in D0

Return the ModeID following displayID in the display database.

- **displayID** — previous ModeID, or `INVALID_ID` (`~0`) to start.
- **Result** — next ModeID, or `INVALID_ID` at the end of the list.

Since V36.

### Example
```c
/* list every available mode with its name and nominal size */
void list_modes(void)
{
    ULONG id = INVALID_ID;
    struct NameInfo name;
    struct DimensionInfo dims;

    while ((id = NextDisplayInfo(id)) != INVALID_ID) {
        DisplayInfoHandle h;
        if (ModeNotAvailable(id))
            continue;                               /* not usable on this machine */
        h = FindDisplayInfo(id);
        if (!h)
            continue;
        if (!GetDisplayInfoData(h, (UBYTE *)&dims, sizeof(dims), DTAG_DIMS, INVALID_ID))
            continue;
        if (!GetDisplayInfoData(h, (UBYTE *)&name, sizeof(name), DTAG_NAME, INVALID_ID))
            name.Name[0] = 0;                       /* not every mode has a name */
        Printf((CONST_STRPTR)"%08lx %-24s %ldx%ld depth %ld\n", id, (LONG)name.Name,
               (LONG)(dims.Nominal.MaxX - dims.Nominal.MinX + 1),
               (LONG)(dims.Nominal.MaxY - dims.Nominal.MinY + 1),
               (LONG)dims.MaxDepth);
    }
}
```

### Gotchas
- Compare with `INVALID_ID`, not 0: 0 is a valid key (`LORES_KEY` on the default monitor).
- The list includes modes the machine cannot show; filter with [ModeNotAvailable](#modenotavailable).

**See also:** [FindDisplayInfo](#finddisplayinfo), [GetDisplayInfoData](#getdisplayinfodata)

## FindDisplayInfo
`DisplayInfoHandle FindDisplayInfo(ULONG displayID)` — LVO -726 (-$2D6)
Registers: displayID=D0; result in D0

Look up the database record handle for a ModeID.

- **displayID** — 32-bit ModeID.
- **Result** — `DisplayInfoHandle` (opaque APTR), or NULL if no record has that key.

Since V36.

**See also:** [GetDisplayInfoData](#getdisplayinfodata), [NextDisplayInfo](#nextdisplayinfo)

## GetDisplayInfoData
`ULONG GetDisplayInfoData(CONST DisplayInfoHandle handle, APTR buf, ULONG size, ULONG tagID, ULONG displayID)` — LVO -756 (-$2F4)
Registers: handle=A0, buf=A1, size=D0, tagID=D1, displayID=D2; result in D0

Copy one typed chunk (DisplayInfo, DimensionInfo, MonitorInfo, NameInfo) of a mode record.

- **handle** — from [FindDisplayInfo](#finddisplayinfo), or NULL to look up `displayID` instead.
- **buf** — destination buffer (starts with a `struct QueryHeader`).
- **size** — buffer size in bytes, normally `sizeof(struct DisplayInfo)` etc.
- **tagID** — `DTAG_DISP`, `DTAG_DIMS`, `DTAG_MNTR` or `DTAG_NAME`.
- **displayID** — ModeID used when handle is NULL (pass `INVALID_ID` otherwise).
- **Result** — bytes copied, or 0 if that information is not available.

Key fields: DisplayInfo `NotAvailable` (0 = available, else `DI_AVAIL_NOCHIPS` 1,
`DI_AVAIL_NOMONITOR` 2, `DI_AVAIL_NOTWITHGENLOCK` 4), `PropertyFlags` (`DIPF_IS_LACE` $1,
`DIPF_IS_DUALPF` $2, `DIPF_IS_HAM` $8, `DIPF_IS_ECS` $10, `DIPF_IS_PAL` $20, `DIPF_IS_EXTRAHALFBRITE`
$1000, `DIPF_IS_AA` $10000, `DIPF_IS_SCANDBL` $20000, `DIPF_IS_DBUFFER` $100000, `DIPF_IS_FOREIGN`
$80000000, ...), `RedBits`/`GreenBits`/`BlueBits` (V39; use instead of the obsolete
`PaletteRange`). DimensionInfo `MaxDepth`, `MinRasterWidth`..`MaxRasterHeight`, and rectangles
`Nominal`, `MaxOScan`, `VideoOScan`, `TxtOScan`, `StdOScan` (inclusive Min/Max coordinates).
MonitorInfo `Mspc`, `TotalRows`, `TotalColorClocks`, `Compatibility` (`MCOMPAT_MIXED` 0,
`MCOMPAT_SELF` 1, `MCOMPAT_NOBODY` -1). NameInfo `Name[DISPLAYNAMELEN]` (32).

Since V36.

### Example
```asm
; d0 = ModeID; out: d0 = RedBits of that mode (0 if no DisplayInfo)
ModeRedBits:
        movem.l d2/a6,-(sp)
        move.l  _GfxBase,a6
        move.l  d0,d2                   ; displayID (handle = NULL)
        sub.l   a0,a0
        lea     DispBuf,a1
        move.l  #dis_SIZEOF,d0
        move.l  #DTAG_DISP,d1
        jsr     _LVOGetDisplayInfoData(a6)
        tst.l   d0
        beq.s   .out
        moveq   #0,d0
        move.b  DispBuf+RedBits,d0      ; no dis_ prefix in displayinfo.i
.out:   movem.l (sp)+,d2/a6
        rts

        section dispbuf,bss
DispBuf:
        ds.b    dis_SIZEOF
```

### Gotchas
- The NDK 3.9 prototype takes 5 arguments; always pass `displayID` in C (and load D2 in asm)
  even though the autodoc marks it optional.
- A result of 0 is normal for chunks a mode does not provide (e.g. `DTAG_NAME`).
- Size overscan-aware screens from `TxtOScan`/`StdOScan` (user preferences), not `MaxOScan`.

**See also:** [FindDisplayInfo](#finddisplayinfo), [ModeNotAvailable](#modenotavailable),
[GetVPModeID](views-and-viewports.md#getvpmodeid)

## ModeNotAvailable
`LONG ModeNotAvailable(ULONG modeID)` — LVO -798 (-$31E)
Registers: modeID=D0; result in D0

Tell why a ModeID cannot be used right now (0 = it can).

- **modeID** — 32-bit ModeID.
- **Result** — 0 if nothing is known to prevent it; otherwise a superset of the
  `DisplayInfo.NotAvailable` bits (`DI_AVAIL_NOCHIPS`, `DI_AVAIL_NOMONITOR`,
  `DI_AVAIL_NOTWITHGENLOCK`); `INVALID_ID` for a ModeID that does not exist.

Since V36.

### Example
```c
BOOL can_use_mode(ULONG id)
{
    return id != INVALID_ID && ModeNotAvailable(id) == 0;
}
```

### Gotchas
- Expect modes of other chipsets/monitors in the database; check this before offering a mode
  (e.g. AGA modes on an ECS machine should report `DI_AVAIL_NOCHIPS` -- unverified).
- The SFD declares a `LONG` result; treat it as unsigned flags.

**See also:** [GetDisplayInfoData](#getdisplayinfodata), [GetVPModeID](views-and-viewports.md#getvpmodeid)

## BestModeIDA
`ULONG BestModeIDA(CONST struct TagItem *tags)` — LVO -1050 (-$41A)
Registers: tags=A0; result in D0

Ask the database for the ModeID that best matches size, depth, properties and monitor.

- **tags** — (hex values from graphics/modeid.h)
  `BIDTAG_DIPFMustHave` ($80000001, `DIPF_IS_*` mask required, default 0),
  `BIDTAG_DIPFMustNotHave` ($80000002, default `SPECIAL_FLAGS` = DUALPF|PF2PRI|HAM|EXTRAHALFBRITE;
  asm name `MUST_FLAGS`), `BIDTAG_ViewPort` ($80000003, match this ViewPort),
  `BIDTAG_NominalWidth`/`BIDTAG_NominalHeight` ($80000004/5, aspect; default from SourceID,
  ViewPort, else 640x200), `BIDTAG_DesiredWidth`/`BIDTAG_DesiredHeight` ($80000006/7, tie-break
  between equal aspects; default = nominal), `BIDTAG_Depth` ($80000008, minimum depth; default
  ViewPort bitmap depth or 1), `BIDTAG_MonitorID` ($80000009, restrict to one monitor),
  `BIDTAG_SourceID` ($8000000a, use this ModeID's properties instead of a ViewPort),
  `BIDTAG_RedBits` ($8000000b), `BIDTAG_BlueBits` ($8000000c), `BIDTAG_GreenBits` ($8000000d)
  (minimum bits per gun, default 4).
- **Result** — best ModeID, or `INVALID_ID` if nothing fits.

Since V39.

### Example
```c
/* 320x256 (or nearest) with 64 colours on the Workbench's monitor, AGA required */
ULONG pick_mode(struct Screen *wb)
{
    ULONG monitor = GetVPModeID(&wb->ViewPort) & MONITOR_ID_MASK;
    ULONG id = BestModeID(BIDTAG_NominalWidth,  320,
                          BIDTAG_NominalHeight, 256,
                          BIDTAG_Depth,         6,
                          BIDTAG_DIPFMustHave,  DIPF_IS_AA,
                          BIDTAG_MonitorID,     monitor,
                          TAG_END);
    return id;                      /* INVALID_ID if none */
}
```

### Gotchas
- Nominal and desired sizes must be non-zero if given.
- Matching is against `DimensionInfo.Nominal`, never overscan sizes.
- Monitor compatibility is honoured: an incompatible source ViewPort/ModeID gives `INVALID_ID`.
- Tag order in the header is Red, Blue, Green ($0b, $0c, $0d) -- do not assume RGB order.
- Autodoc typos: `BIDTAG_Greenits`, `BIDTAG_MustHave`, `DIFP_IS_LACE` do not exist; use
  `BIDTAG_GreenBits`, `BIDTAG_DIPFMustHave`, `DIPF_IS_LACE`.

**See also:** [CoerceMode](#coercemode), [GetDisplayInfoData](#getdisplayinfodata)

## CoerceMode
`ULONG CoerceMode(struct ViewPort *vp, ULONG monitorid, ULONG flags)` — LVO -936 (-$3A8)
Registers: vp=A0, monitorid=D0, flags=D1; result in D0

Find the mode on another monitor that a ViewPort's mode should be coerced to.

- **vp** — the ViewPort to coerce.
- **monitorid** — target monitor (a ModeID masked with `MONITOR_ID_MASK`, e.g. `VGA_MONITOR_ID`).
- **flags** — graphics/coerce.h: `PRESERVE_COLORS` (1, keep the depth), `AVOID_FLICKER` (2, no
  interlaced result), `IGNORE_MCOMPAT` (4, ignore monitor compatibility; header only).
- **Result** — coerced ModeID, or `INVALID_ID`.

Since V39.

### Example
```c
ULONG vga_version(struct ViewPort *vp)
{
    return CoerceMode(vp, VGA_MONITOR_ID, PRESERVE_COLORS | AVOID_FLICKER);
}
```

**See also:** [BestModeIDA](#bestmodeida), [VideoControl](views-and-viewports.md#videocontrol)

## OpenMonitor
`struct MonitorSpec * OpenMonitor(CONST_STRPTR monitorName, ULONG displayID)` — LVO -714 (-$2CA)
Registers: monitorName=A1, displayID=D0; result in D0

Open a MonitorSpec by name or by ModeID.

- **monitorName** — e.g. `DEFAULT_MONITOR_NAME` ("default.monitor"), `NTSC_MONITOR_NAME`
  ("ntsc.monitor"), `PAL_MONITOR_NAME` ("pal.monitor"), `VGA_MONITOR_NAME` ("vga.monitor") from
  graphics/monitor.h (C only; the VGA70 names there are marked obsolete); or NULL to open by ID.
- **displayID** — ModeID/monitor ID used when the name is NULL; name NULL and ID 0 = default
  monitor.
- **Result** — `struct MonitorSpec *`, or NULL. Close with [CloseMonitor](#closemonitor).

Since V36.

### Example
```c
/* attach the monitor of a mode to a custom View's ViewExtra (V36+) */
BOOL set_view_monitor(struct ViewExtra *vx, ULONG modeid)
{
    vx->Monitor = OpenMonitor(NULL, modeid);   /* a mode or monitor ID both work */
    return vx->Monitor != NULL;     /* CloseMonitor(vx->Monitor) when the View goes */
}
```

### Gotchas
- A custom View built with InitView/MakeVPort/MrgCop needs a ViewExtra (GfxNew) with `Monitor`
  set on V36+; see [GfxNew](views-and-viewports.md#gfxnew).
- The asm monitor.i has no `*_MONITOR_NAME` strings; define them yourself.

**See also:** [CloseMonitor](#closemonitor), [GfxNew](views-and-viewports.md#gfxnew)

## CloseMonitor
`BOOL CloseMonitor(struct MonitorSpec *monitorSpec)` — LVO -720 (-$2D0)
Registers: monitorSpec=A0; result in D0

Release a MonitorSpec obtained with OpenMonitor.

- **monitorSpec** — pointer from [OpenMonitor](#openmonitor), or NULL.
- **Result** — FALSE (0) if it closed normally, TRUE if it could not be closed (inverted sense!).

Since V36.

### Gotchas
- The NDK 3.9 SFD declares `BOOL`, the autodoc `LONG`; either way non-zero means FAILURE.
- NULL is documented as allowed in the NDK 3.9 autodoc only (not in the V37 autodoc); test
  before calling if you support V36/V37.

**See also:** [OpenMonitor](#openmonitor)
