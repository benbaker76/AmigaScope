# intuition.library: screens

Open screens with [OpenScreenTagList](#openscreentaglist) (V36+ `SA_` tags; the old `NewScreen` path is
[OpenScreen](#openscreen)) and close them with [CloseScreen](#closescreen) after every window is gone.
Visitor windows go on public screens: [LockPubScreen](#lockpubscreen) -> open window -> [UnlockPubScreen](#unlockpubscreen).
Depth and position calls are Intuition-cooperative; V39 adds attached screen families, [ScreenDepth](#screendepth),
[ScreenPosition](#screenposition) and double buffering ([AllocScreenBuffer](#allocscreenbuffer) ->
[ChangeScreenBuffer](#changescreenbuffer) -> [FreeScreenBuffer](#freescreenbuffer)).
Render through `Screen->RastPort`; use `Screen->RastPort.BitMap`, never `&Screen->BitMap`.

## OpenScreenTagList
`struct Screen * OpenScreenTagList(CONST struct NewScreen *newScreen, CONST struct TagItem *tagList)` — LVO -612 (-$264)
Registers: newScreen=A0, tagList=A1; result in D0

Open a screen described by an optional NewScreen plus a tag list (the V36+ way).

- **newScreen** — optional `struct NewScreen *` (NULL = all defaults); tags override its fields.
  Passing a NewScreen also fixes left/top/width/height, which defeats `SA_Overscan` centring.
- **tagList** — `TAG_DONE`-terminated `SA_` tags (screens.h, `SA_Dummy` = `TAG_USER+32`); see table.
  NULL for both arguments gives a default screen, but always give at least `SA_Title`.
- **Result** — `struct Screen *`, or NULL; the reason is written through `SA_ErrorCode`.

C varargs form: `OpenScreenTags(newScreen, tag1, ...)` (amiga.lib stub, or macro in the GCC inline headers).

| Tag | ti_Data | Meaning / default |
|---|---|---|
| `SA_Left`, `SA_Top` | LONG | position in screen pixels; default = DisplayClip MinX/MinY, but 0 if you give a non-default `SA_Width`/`SA_Height` |
| `SA_Width`, `SA_Height` | LONG | raster size; `STDSCREENWIDTH`/`STDSCREENHEIGHT` (-1) = DisplayClip size |
| `SA_Depth` | LONG | bitplanes (default 1) |
| `SA_DisplayID` | ULONG | 32-bit mode ID from graphics/modeid.h, e.g. `PAL_MONITOR_ID\|LORES_KEY` |
| `SA_Overscan` | ULONG | `OSCAN_TEXT` (1, default), `OSCAN_STANDARD` (2), `OSCAN_MAX` (3), `OSCAN_VIDEO` (4) |
| `SA_DClip` | `struct Rectangle *` | explicit DisplayClip (use instead of `SA_Overscan`) |
| `SA_Title` | `UBYTE *` | default screen title (default NULL) |
| `SA_Type` | ULONG | `CUSTOMSCREEN` (0x000F) or `PUBLICSCREEN` (0x0002) |
| `SA_PubName` | `UBYTE *` | makes it a public screen with this name (opens in private state); give it BEFORE `SA_PubSig`/`SA_PubTask` |
| `SA_PubSig` | UBYTE | signal NUMBER (not mask) sent when the last visitor window closes |
| `SA_PubTask` | `struct Task *` | task to signal (default: the opener) |
| `SA_ShowTitle` | BOOL | title bar in front of backdrop windows (default TRUE) |
| `SA_Behind` | BOOL | open behind all screens (= `SCREENBEHIND`, default FALSE) |
| `SA_Quiet` | BOOL | no title bar / screen gadgets rendered (= `SCREENQUIET`, default FALSE) |
| `SA_AutoScroll` | BOOL | autoscroll a screen larger than its DisplayClip (= `AUTOSCROLL`) |
| `SA_Pens` | `UWORD *` | `~0`-terminated DrawInfo pen array; presence (even just `{~0}`) = new 3D look |
| `SA_Font` | `struct TextAttr *` | default font; must already be in memory (ROM font or opened with OpenDiskFont) |
| `SA_SysFont` | ULONG | 0 = fixed-width default font, 1 = Workbench screen font; overrides `SA_Font` |
| `SA_BitMap` | `struct BitMap *` | your own display bitmap (implies `CUSTOMBITMAP`) |
| `SA_Colors` | `struct ColorSpec *` | initial 4-bit-per-gun colours, array ends with `ColorIndex = -1` |
| `SA_FullPalette` | BOOL | load all 32 preference colours, not just 0-3 and 17-19 (default FALSE) |
| `SA_ErrorCode` | `LONG *` | receives an `OSERR_` code on failure (0 = none) |
| `SA_Colors32` | `ULONG *` | V39: LoadRGB32() table; wins over `SA_Colors` |
| `SA_Interleaved` | BOOL | V39: request an interleaved bitmap (falls back to normal) |
| `SA_Draggable` | BOOL | V39: FALSE = user cannot drag it (default TRUE) |
| `SA_Exclusive` | BOOL | V39: never shares the display with other screens (default FALSE) |
| `SA_SharePens` | BOOL | V39: leave non-DrawInfo pens unallocated so you can ObtainPen() them |
| `SA_LikeWorkbench` | BOOL | V39: clone Workbench mode/depth/colours/pens (best effort) |
| `SA_Parent` | `struct Screen *` | V39: attach this screen as child of an open parent |
| `SA_FrontChild`, `SA_BackChild` | `struct Screen *` | V39: attach an open child at front/back of the new family |
| `SA_VideoControl` | `struct TagItem *` | V39: tags passed to graphics VideoControl() after opening |
| `SA_ColorMapEntries` | ULONG | V39: ColorMap size (default `1<<depth`, minimum 32) |
| `SA_BackFill` | `struct Hook *` | V39: backfill hook for the screen's Layer_Info |
| `SA_MinimizeISG` | BOOL | V40: smallest inter-screen gap (use with `VC_NoColorPaletteLoad`) |

`OSERR_` codes: `OSERR_NOMONITOR` 1, `OSERR_NOCHIPS` 2, `OSERR_NOMEM` 3, `OSERR_NOCHIPMEM` 4,
`OSERR_PUBNOTUNIQUE` 5, `OSERR_UNKNOWNMODE` 6, `OSERR_TOODEEP` 7 (V39), `OSERR_ATTACHFAIL` 8 (V39),
`OSERR_NOTAVAILABLE` 9 (screens.h only).

Since V36.

### Example
```c
#include <proto/exec.h>
#include <proto/intuition.h>
#include <intuition/intuition.h>
#include <graphics/modeid.h>

/* Game/demo screen: 320x256 PAL lores, 32 colours, no Intuition imagery. */
LONG err = 0;
struct Screen *scr = OpenScreenTags(NULL,
    SA_DisplayID,  PAL_MONITOR_ID | LORES_KEY,
    SA_Width,      320,
    SA_Height,     256,
    SA_Depth,      5,
    SA_Type,       CUSTOMSCREEN,
    SA_Quiet,      TRUE,
    SA_ShowTitle,  FALSE,
    SA_Draggable,  FALSE,             /* ignored before V39 */
    SA_Title,      (ULONG)"MyGame",
    SA_ErrorCode,  (ULONG)&err,
    TAG_DONE);
if (scr == NULL) {
    /* err: OSERR_NOMONITOR/OSERR_UNKNOWNMODE if no PAL monitor, OSERR_NOCHIPMEM ... */
    return;
}
/* Full-screen input window: borderless backdrop, RMB trapped so no menu bar is drawn. */
struct Window *win = OpenWindowTags(NULL,
    WA_CustomScreen, (ULONG)scr,
    WA_Left, 0, WA_Top, 0, WA_Width, 320, WA_Height, 256,
    WA_Backdrop,     TRUE,
    WA_Borderless,   TRUE,
    WA_RMBTrap,      TRUE,
    WA_Activate,     TRUE,
    WA_IDCMP,        IDCMP_RAWKEY | IDCMP_MOUSEBUTTONS,
    TAG_DONE);
if (win) {
    /* draw via win->RPort (or &scr->RastPort); bitmap = scr->RastPort.BitMap */
    /* ... IDCMP loop ... */
    CloseWindow(win);
}
CloseScreen(scr);                     /* only after every window is closed */
```

### Gotchas
- Explicit `SA_Width`/`SA_Height` without `SA_Left`/`SA_Top` puts the screen at 0,0, not at the
  DisplayClip origin; for overscan screens take `MinX`/`MinY` from [QueryOverscan](#queryoverscan).
- `SA_Font` is not loaded for you: Intuition never calls OpenDiskFont; keep the font open until the
  screen is open.
- `SA_SysFont` 1: windows on the screen still get the old default font (sysfont 0) in their RastPort.
- A `SA_PubName` screen starts private; call [PubScreenStatus](#pubscreenstatus)`(scr, 0)` to go public.
- DOS requesters ("insert volume") still appear on Workbench unless you set your Process
  `pr_WindowPtr` to a window on your screen (restore it before closing that window).
- Use `scr->RastPort.BitMap`, never `&scr->BitMap`: the embedded BitMap cannot describe future bitmaps.
- `SA_LikeWorkbench` is a request, not a guarantee; read the resulting screen instead of assuming.

**See also:** [OpenScreen](#openscreen), [CloseScreen](#closescreen), [QueryOverscan](#queryoverscan),
[PubScreenStatus](#pubscreenstatus), [OpenWindowTagList](windows.md#openwindowtaglist),
[Tag-based opening](concepts.md#tag-based-opening), [OpenDiskFont](../diskfont/diskfont.md#opendiskfont),
graphics.library ModeNotAvailable, graphics.library GetColorMap

## OpenScreen
`struct Screen * OpenScreen(CONST struct NewScreen *newScreen)` — LVO -198 (-$C6)
Registers: newScreen=A0; result in D0

Open a screen from a NewScreen (or ExtNewScreen) structure; the pre-V36 entry point.

- **newScreen** — `struct NewScreen`: `LeftEdge`, `TopEdge` (0 before V36), `Width`, `Height`
  (`STDSCREENWIDTH`/`STDSCREENHEIGHT` = -1 for default), `Depth`, `DetailPen` (usually 0), `BlockPen`
  (usually 1), `ViewModes` (`HIRES`, `LACE`, `SPRITES`... superseded by `SA_DisplayID`), `Type`
  (`CUSTOMSCREEN`, optionally `|CUSTOMBITMAP|SCREENBEHIND|SCREENQUIET|NS_EXTENDED`), `Font`
  (`struct TextAttr *`, must be in memory), `DefaultTitle`, `Gadgets` (must be NULL), `CustomBitMap`.
  May be freed right after the call.
- **NS_EXTENDED** (0x1000) — the structure is an `ExtNewScreen` whose `Extension` points to `SA_` tags;
  V34 and older ignore it, so it is a way to pass tags that degrade gracefully.
- **Result** — `struct Screen *`, or NULL (V36+: details via `SA_ErrorCode` in the tags).

### Gotchas
- `SHOWTITLE` is on after opening; call [ShowTitle](#showtitle) to change it.
- Everything in the [OpenScreenTagList](#openscreentaglist) gotchas applies (font must be in memory,
  `pr_WindowPtr` for DOS requesters, `Screen->RastPort.BitMap`).
- For V36+ code prefer [OpenScreenTagList](#openscreentaglist) with a NULL NewScreen.

**See also:** [OpenScreenTagList](#openscreentaglist), [CloseScreen](#closescreen),
[QueryOverscan](#queryoverscan), diskfont.library OpenDiskFont, graphics.library GetColorMap

## CloseScreen
`BOOL CloseScreen(struct Screen *screen)` — LVO -66 (-$42)
Registers: screen=A0; result in D0

Close a screen and free everything Intuition allocated for it.

- **screen** — a screen you opened.
- **Result** — V36+: TRUE if closed, FALSE if windows are still open on it or LockPubScreen locks
  are outstanding (nothing is freed). Before V36 there is no result and it closes regardless.

If it was the last screen, Intuition tries to reopen Workbench.

### Gotchas
- Close every window first (and [FreeScreenBuffer](#freescreenbuffer) all buffers, and
  [FreeScreenDrawInfo](#freescreendrawinfo)). On V34 closing under open windows crashes the machine.
- For a public screen, first make it private ([PubScreenStatus](#pubscreenstatus) with `PSNF_PRIVATE`)
  so no new visitors arrive. It can only close once all visitors have left: check the result and retry later.
- Free resources that depend on the screen (fonts you opened for `SA_Font`, custom bitmaps passed
  with `SA_BitMap`) only AFTER CloseScreen succeeds.

**See also:** [OpenScreenTagList](#openscreentaglist), [PubScreenStatus](#pubscreenstatus),
[CloseWindow](windows.md#closewindow)

## LockPubScreen
`struct Screen * LockPubScreen(CONST_STRPTR name)` — LVO -510 (-$1FE)
Registers: name=A0; result in D0

Find a public screen by name and stop it closing while you inspect it.

- **name** — public screen name, `"Workbench"`, or NULL for the default public screen. `"Workbench"` or
  NULL-with-no-default opens Workbench if it is not open.
- **Result** — `struct Screen *`, or NULL (no such screen, or it is in private state).

The lock acts like a visitor window. Release it with [UnlockPubScreen](#unlockpubscreen) as soon as your
window is open; the window itself then keeps the screen alive.

Since V36.

### Example
```c
struct Screen *pub = LockPubScreen(NULL);         /* default public screen (usually Workbench) */
if (pub) {
    struct Window *win = OpenWindowTags(NULL,
        WA_PubScreen,    (ULONG)pub,
        WA_Left,         20,
        WA_Top,          pub->BarHeight + 1,      /* just below the screen title bar */
        WA_InnerWidth,   320,
        WA_InnerHeight,  200,
        WA_Title,        (ULONG)"Demo",
        WA_DragBar,      TRUE,
        WA_DepthGadget,  TRUE,
        WA_CloseGadget,  TRUE,
        WA_Activate,     TRUE,
        WA_IDCMP,        IDCMP_CLOSEWINDOW,
        TAG_DONE);
    UnlockPubScreen(NULL, pub);                    /* window (if any) now holds the screen */
    if (win) {
        /* ... WaitPort(win->UserPort) loop ... */
        CloseWindow(win);
    }
}
```

### Gotchas
- Do not use the Screen pointer after unlocking unless a window of yours is still open on it.
- `Forbid()` is not a substitute for the lock.
- Screen dimensions, font (`pub->Font`), `BarHeight` and `WBorTop` vary per user; lay out from them.

**See also:** [UnlockPubScreen](#unlockpubscreen), [OpenWindowTagList](windows.md#openwindowtaglist),
[GetScreenDrawInfo](#getscreendrawinfo), [Public screens](concepts.md#public-screens)

## UnlockPubScreen
`VOID UnlockPubScreen(CONST_STRPTR name, struct Screen *screen)` — LVO -516 (-$204)
Registers: name=A0, screen=A1; no result

Release a lock obtained with LockPubScreen.

- **name** — NULL (recommended) to identify the screen by pointer; if non-NULL the screen is found by
  name and **screen** is ignored.
- **screen** — the pointer LockPubScreen returned. NULL name and NULL screen is a harmless no-op.

Since V36.

**See also:** [LockPubScreen](#lockpubscreen)

## LockPubScreenList
`struct List * LockPubScreenList(VOID)` — LVO -522 (-$20A)
Registers: none; result in D0

Lock and return the system list of public screens (for screen-manager tools).

- **Result** — `struct List *` of `struct PubScreenNode` (`psn_Node.ln_Name` = name, `psn_Screen`,
  `psn_Flags` (`PSNF_PRIVATE`), `psn_VisitorCount`, `psn_SigTask`, `psn_SigBit`).

Copy what you need and call [UnlockPubScreenList](#unlockpubscreenlist) immediately.

Since V36.

### Gotchas
- The [LockIBase](#lockibase) restrictions apply: hold it briefly, call no Intuition/graphics/DOS
  functions while holding it.
- To open a window on a listed screen, copy the name and use [LockPubScreen](#lockpubscreen) after
  unlocking the list.

**See also:** [UnlockPubScreenList](#unlockpubscreenlist), [NextPubScreen](#nextpubscreen)

## UnlockPubScreenList
`VOID UnlockPubScreenList(VOID)` — LVO -528 (-$210)
Registers: none; no result

Release the public screen list lock taken by LockPubScreenList.

Since V36.

**See also:** [LockPubScreenList](#lockpubscreenlist)

## NextPubScreen
`STRPTR NextPubScreen(CONST struct Screen *screen, STRPTR namebuf)` — LVO -534 (-$216)
Registers: screen=A0, namebuf=A1; result in D0

Get the name of the next public screen in the system cycle (for "jump screen" features).

- **screen** — screen your window is on, or NULL.
- **namebuf** — buffer of at least `MAXPUBSCREENNAME+1` (140) bytes, filled with the name.
- **Result** — `namebuf`, or NULL if there are no public screens.

Since V36.

### Gotchas
- The buffer must be `MAXPUBSCREENNAME+1` bytes (bug: one more than first documented).
- The named screen may be gone or private by the time you call LockPubScreen; handle failure.
- The cycle order is undefined.

**See also:** [LockPubScreen](#lockpubscreen), [PubScreenStatus](#pubscreenstatus)

## PubScreenStatus
`UWORD PubScreenStatus(struct Screen *screen, ULONG statusFlags)` — LVO -552 (-$228)
Registers: screen=A0, statusFlags=D0; result in D0

Switch a public screen you own between private and public state.

- **screen** — a public screen YOU opened (with `SA_PubName`). Never the Workbench screen.
- **statusFlags** — `PSNF_PRIVATE` (0x0001) to make it private, 0 to make it public.
- **Result** — bit 0 is 0 if the change failed: the screen was not public, or cannot go private because
  visitor windows are open. Other bits reserved.

Since V36.

### Example
```c
/* scr opened with SA_PubName, (ULONG)"MYAPP" */
PubScreenStatus(scr, 0);                              /* now visitors may open */
/* ... at exit: go private first; fails while visitor windows are open */
while (!(PubScreenStatus(scr, PSNF_PRIVATE) & 1))
    Wait(1UL << pubsig);                              /* SA_PubSig signal: last visitor left */
CloseScreen(scr);
```

**See also:** [OpenScreenTagList](#openscreentaglist), [CloseScreen](#closescreen),
[Public screens](concepts.md#public-screens)

## SetDefaultPubScreen
`VOID SetDefaultPubScreen(CONST_STRPTR name)` — LVO -540 (-$21C)
Registers: name=A0; no result

Make a named public screen the default target for visitor windows.

- **name** — public screen name, or NULL to make Workbench the default.

Used for windows asking for the default public screen and for fallback when a named one is missing.
Meant for public screen manager utilities, not ordinary applications.

Since V36.

**See also:** [GetDefaultPubScreen](#getdefaultpubscreen), [SetPubScreenModes](#setpubscreenmodes)

## GetDefaultPubScreen
`VOID GetDefaultPubScreen(STRPTR nameBuffer)` — LVO -582 (-$246)
Registers: nameBuffer=A0; no result

Copy the name of the current default public screen into a buffer.

- **nameBuffer** — buffer of `MAXPUBSCREENNAME` (139) bytes (use +1 to be safe), or NULL.
  Receives `"Workbench"` if no default is set.

Since V36.

### Gotchas
- Undocumented-in-prototype return: D0 holds the default screen pointer (0 if none set, NOT the
  Workbench pointer). The screen may close at any time; only compare it for identity with a screen you
  have locked or have a window on.
- To open on the default screen you do not need the name: `LockPubScreen(NULL)`.

**See also:** [SetDefaultPubScreen](#setdefaultpubscreen), [LockPubScreen](#lockpubscreen)

## SetPubScreenModes
`UWORD SetPubScreenModes(ULONG modes)` — LVO -546 (-$222)
Registers: modes=D0; result in D0

Set global public screen behaviour flags.

- **modes** — `SHANGHAI` (0x0001): Workbench-type windows open on the default public screen;
  `POPPUBSCREEN` (0x0002): a screen comes to front when a visitor window opens on it.
- **Result** — previous mode flags.

Since V36.

### Gotchas
- User preference territory; applications should not change it.

**See also:** [SetDefaultPubScreen](#setdefaultpubscreen), [GetScreenData](#getscreendata)

## OpenWorkBench
`ULONG OpenWorkBench(VOID)` — LVO -210 (-$D2)
Registers: none; result in D0

Open the Workbench screen if it is not already open.

- **Result** — non-zero if Workbench is (now) open, 0 on failure. The value is the Workbench screen
  address, but treat it only as a success flag: the screen can close at any time.

### Example
```asm
        include "lvo/intuition_lib.i"

        move.l  IntuitionBase,a6        ; your saved library base
        jsr     _LVOCloseWorkBench(a6)  ; free its chip RAM for the demo
        move.l  d0,wbclosed             ; remember: reopen only if we closed it
        ; ... run ...
        tst.l   wbclosed
        beq.s   .skip
        jsr     _LVOOpenWorkBench(a6)
.skip:
```

### Gotchas
- Spelled `OpenWorkBench` (capital B) in the library; there is no `OpenWorkbench`.

**See also:** [CloseWorkBench](#closeworkbench), [LockPubScreen](#lockpubscreen)

## CloseWorkBench
`LONG CloseWorkBench(VOID)` — LVO -78 (-$4E)
Registers: none; result in D0

Try to close the Workbench screen (e.g. to free chip RAM).

- **Result** — TRUE if Workbench was closed; FALSE if it was not open or has non-drawer windows open
  (Shells, other programs' windows).

### Gotchas
- Call [OpenWorkBench](#openworkbench) at exit only if this returned TRUE (see example there).
- Rewritten in V36 but still not foolproof; a user-selectable option is friendlier than doing it
  unconditionally.

**See also:** [OpenWorkBench](#openworkbench), [WBenchToBack](#wbenchtoback)

## WBenchToFront
`BOOL WBenchToFront(VOID)` — LVO -342 (-$156)
Registers: none; result in D0

Bring the Workbench screen in front of all other screens (depth only, no vertical move).

- **Result** — TRUE if Workbench is open, else FALSE.

**See also:** [WBenchToBack](#wbenchtoback), [ScreenToFront](#screentofront)

## WBenchToBack
`BOOL WBenchToBack(VOID)` — LVO -336 (-$150)
Registers: none; result in D0

Send the Workbench screen behind all other screens (depth only, no vertical move).

- **Result** — TRUE if Workbench is open, else FALSE.

**See also:** [WBenchToFront](#wbenchtofront), [ScreenToBack](#screentoback)

## ScreenToFront
`VOID ScreenToFront(struct Screen *screen)` — LVO -252 (-$FC)
Registers: screen=A0; no result

Bring a screen to the front of the display.

- **screen** — screen to raise. An attached screen moves with its whole family.

### Example
```c
ScreenToFront(scr);          /* e.g. after opening with SA_Behind and preparing imagery */
```

**See also:** [ScreenToBack](#screentoback), [ScreenDepth](#screendepth)

## ScreenToBack
`VOID ScreenToBack(struct Screen *screen)` — LVO -246 (-$F6)
Registers: screen=A0; no result

Send a screen behind all other screens.

- **screen** — screen to lower. An attached screen moves with its whole family.

**See also:** [ScreenToFront](#screentofront), [ScreenDepth](#screendepth)

## ScreenDepth
`VOID ScreenDepth(struct Screen *screen, ULONG flags, APTR reserved)` — LVO -786 (-$312)
Registers: screen=A0, flags=D0, reserved=A1; no result

Depth-arrange a screen, optionally only within its attached-screen family.

- **screen** — screen to move.
- **flags** — `SDEPTH_TOFRONT` (0) or `SDEPTH_TOBACK` (1), optionally `| SDEPTH_INFAMILY` (2) to move a
  child only within its family (otherwise the whole family moves). `SDEPTH_CHILDONLY` is an old alias.
- **reserved** — must be NULL.

Since V39.

### Gotchas
- Only the screen's owner should use `SDEPTH_INFAMILY` (style rule, not enforced).

**See also:** [ScreenToFront](#screentofront), [ScreenToBack](#screentoback), [OpenScreenTagList](#openscreentaglist) (`SA_Parent`)

## ScreenPosition
`VOID ScreenPosition(struct Screen *screen, ULONG flags, LONG x1, LONG y1, LONG x2, LONG y2)` — LVO -792 (-$318)
Registers: screen=A0, flags=D0, x1=D1, y1=D2, x2=D3, y2=D4; no result

Move a screen relatively, absolutely, or so that a given rectangle becomes visible.

- **screen** — screen to move.
- **flags** — `SPOS_RELATIVE` (0: x1,y1 are deltas), `SPOS_ABSOLUTE` (1: x1,y1 are the new position) or
  `SPOS_MAKEVISIBLE` (2: scroll an oversized screen so (x1,y1)-(x2,y2) is on view); may add
  `SPOS_FORCEDRAG` (4) to move a `SA_Draggable` FALSE screen.
- **x1, y1, x2, y2** — screen-resolution pixels; x2,y2 used only by `SPOS_MAKEVISIBLE`.

The move is clipped to legal limits; read `screen->LeftEdge`/`TopEdge` afterwards for the real result.
Negative edges are valid for screens larger than their DisplayClip.

Since V39.

### Gotchas
- Only the owner should use `SPOS_FORCEDRAG`.

**See also:** [MoveScreen](#movescreen), [RethinkDisplay](#rethinkdisplay)

## MoveScreen
`VOID MoveScreen(struct Screen *screen, LONG dx, LONG dy)` — LVO -162 (-$A2)
Registers: screen=A0, dx=D0, dy=D1; no result

Move a screen by a delta in screen pixels (clipped to what is allowed).

- **screen** — screen to move.
- **dx, dy** — deltas in the screen's own resolution. Horizontal movement works from V36 (must be 0
  before). Check `LeftEdge`/`TopEdge` afterwards to see where it ended up.

### Example
```c
MoveScreen(scr, 0, -scr->TopEdge);     /* pull the screen fully down to the top */
```

**See also:** [ScreenPosition](#screenposition), [RethinkDisplay](#rethinkdisplay)

## ShowTitle
`VOID ShowTitle(struct Screen *screen, LONG showIt)` — LVO -282 (-$11A)
Registers: screen=A0, showIt=D0; no result

Choose whether the screen title bar shows in front of backdrop windows.

- **screen** — target screen.
- **showIt** — TRUE: title bar in front of `WFLG_BACKDROP` windows (default after opening); FALSE: behind
  all windows. Non-backdrop windows are always in front of the title bar.

**See also:** [OpenScreenTagList](#openscreentaglist) (`SA_ShowTitle`)

## GetScreenDrawInfo
`struct DrawInfo * GetScreenDrawInfo(struct Screen *screen)` — LVO -690 (-$2B2)
Registers: screen=A0; result in D0

Get the read-only DrawInfo (pens, font, depth, resolution) of an open screen.

- **screen** — a screen you own, have a window on, or have locked.
- **Result** — `struct DrawInfo *`: `dri_Version` (`DRI_VERSION` 2), `dri_NumPens`, `dri_Pens`,
  `dri_Font`, `dri_Depth`, `dri_Resolution.X/Y`, `dri_Flags` (`DRIF_NEWLOOK`), `dri_CheckMark`,
  `dri_AmigaKey` (V39). Index `dri_Pens[]` with `DETAILPEN` 0, `BLOCKPEN` 1, `TEXTPEN` 2, `SHINEPEN` 3,
  `SHADOWPEN` 4, `FILLPEN` 5, `FILLTEXTPEN` 6, `BACKGROUNDPEN` 7, `HIGHLIGHTTEXTPEN` 8, and (only if
  `dri_Version >= 2`) `BARDETAILPEN` 9, `BARBLOCKPEN` 10, `BARTRIMPEN` 11.

Since V36.

### Example
```c
struct DrawInfo *dri = GetScreenDrawInfo(win->WScreen);
if (dri) {
    SetAPen(win->RPort, dri->dri_Pens[SHINEPEN]);
    /* ... draw ... */
    FreeScreenDrawInfo(win->WScreen, dri);
}
```

### Gotchas
- Always pair with [FreeScreenDrawInfo](#freescreendrawinfo); use the data only in between.
- Does not keep the screen open, and the pointer is invalid after the screen closes.
- Does not track later mode/depth/pen changes.

**See also:** [FreeScreenDrawInfo](#freescreendrawinfo), [LockPubScreen](#lockpubscreen)

## FreeScreenDrawInfo
`VOID FreeScreenDrawInfo(struct Screen *screen, struct DrawInfo *drawInfo)` — LVO -696 (-$2B8)
Registers: screen=A0, drawInfo=A1; no result

Release a DrawInfo obtained with GetScreenDrawInfo.

- **screen** — the same screen passed to GetScreenDrawInfo.
- **drawInfo** — the returned pointer; NULL is allowed (no-op).

Since V36.

**See also:** [GetScreenDrawInfo](#getscreendrawinfo)

## QueryOverscan
`LONG QueryOverscan(ULONG displayID, struct Rectangle *rect, LONG oScanType)` — LVO -474 (-$1DA)
Registers: displayID=A0, rect=A1, oScanType=D0; result in D0

Fill a Rectangle with a standard overscan region for a display mode.

- **displayID** — 32-bit mode ID (graphics/modeid.h), passed in A0.
- **rect** — `struct Rectangle` (`MinX`, `MinY`, `MaxX`, `MaxY`) to fill; width = `MaxX-MinX+1`.
- **oScanType** — `OSCAN_TEXT` (1: fully visible, Left/Top always 0,0), `OSCAN_STANDARD` (2: just past
  the visible edges, Left/Top may be negative), `OSCAN_MAX` (3: largest region that also allows any
  smaller one), `OSCAN_VIDEO` (4: absolute maximum, use as-is).
- **Result** — 0 if the monitor/mode does not exist, non-zero otherwise.

Since V36.

### Example
```c
struct Rectangle r;
if (QueryOverscan(PAL_MONITOR_ID | LORES_KEY, &r, OSCAN_STANDARD)) {
    struct Screen *s = OpenScreenTags(NULL,
        SA_DisplayID, PAL_MONITOR_ID | LORES_KEY,
        SA_DClip,     (ULONG)&r,
        SA_Left,      r.MinX,  SA_Top,    r.MinY,
        SA_Width,     r.MaxX - r.MinX + 1,
        SA_Height,    r.MaxY - r.MinY + 1,
        SA_Depth,     4,
        TAG_DONE);
    /* ... */
}
```

### Gotchas
- If you only want a standard region at DisplayClip size, just pass `SA_Overscan` with no
  `SA_Left/Top/Width/Height` and no NewScreen.
- Larger overscan costs chip RAM and chip bandwidth; use the smallest region that works.

**See also:** [OpenScreenTagList](#openscreentaglist)

## GetScreenData
`LONG GetScreenData(APTR buffer, ULONG size, ULONG type, CONST struct Screen *screen)` — LVO -426 (-$1AA)
Registers: buffer=A0, size=D0, type=D1, screen=A1; result in D0

Copy (part of) a Screen structure, e.g. of Workbench, into your buffer (pre-V36 way).

- **buffer** — destination.
- **size** — bytes to copy (e.g. `sizeof(struct Screen)`).
- **type** — `WBENCHSCREEN` (0x0001) for Workbench (opens it if needed), or `CUSTOMSCREEN` (0x000F).
- **screen** — used only with `CUSTOMSCREEN`: plain copy of `size` bytes from it.
- **Result** — non-zero on success, 0 if the standard screen could not be opened.

### Gotchas
- V36+ lies for compatibility about Workbench: `ViewPort.Modes` is reported as `HIRES` or `HIRES|LACE`
  and dimensions are clipped to `OSCAN_TEXT` (A2024 modes excepted). Under `SHANGHAI` it reports the
  default public screen.
- Use [LockPubScreen](#lockpubscreen)`("Workbench")` and graphics GetVPModeID() for real data.

**See also:** [LockPubScreen](#lockpubscreen), [SetPubScreenModes](#setpubscreenmodes), graphics.library GetVPModeID

## ViewAddress
`struct View * ViewAddress(VOID)` — LVO -294 (-$126)
Registers: none; result in D0

Return the address of Intuition's View structure (for graphics calls that need a View).

- **Result** — `struct View *` owned by Intuition. Do not LoadView() your own changes into it; use
  [MakeScreen](#makescreen) + [RethinkDisplay](#rethinkdisplay).

**See also:** [ViewPortAddress](#viewportaddress), [RethinkDisplay](#rethinkdisplay)

## ViewPortAddress
`struct ViewPort * ViewPortAddress(CONST struct Window *window)` — LVO -300 (-$12C)
Registers: window=A0; result in D0

Return the ViewPort of the screen a window is on.

- **window** — an open window.
- **Result** — `&window->WScreen->ViewPort`; valid while the window stays open.

### Example
```c
LoadRGB4(ViewPortAddress(win), palette, 32);   /* same as &win->WScreen->ViewPort */
```

### Gotchas
- Redundant: `&win->WScreen->ViewPort` is identical. Only change colours of a screen you own.

**See also:** [ViewAddress](#viewaddress), graphics.library LoadRGB4, graphics.library LoadRGB32

## MakeScreen
`LONG MakeScreen(struct Screen *screen)` — LVO -378 (-$17A)
Registers: screen=A0; result in D0

Rebuild the copper list of your custom screen's ViewPort in an Intuition-safe way.

- **screen** — your custom screen, after you changed its ViewPort (e.g. `RasInfo` scroll offsets,
  `UCopIns` user copper list, modes).
- **Result** — V39+: 0 on success, non-zero if MakeVPort failed. Before V39 the value is garbage.

Locks the Intuition View, sets interlace state, calls graphics MakeVPort(). Follow it with
[RethinkDisplay](#rethinkdisplay) to put the result on the display.

### Example
```c
scr->ViewPort.RasInfo->RxOffset = scrollx;     /* hardware scroll a large bitmap */
MakeScreen(scr);
RethinkDisplay();
```

### Gotchas
- Never call graphics MakeVPort()/MrgCop()/LoadView() on an Intuition screen directly.
- May remake every screen if the global interlace state changes (slow).

**See also:** [RethinkDisplay](#rethinkdisplay), [RemakeDisplay](#remakedisplay), graphics.library MakeVPort

## RethinkDisplay
`LONG RethinkDisplay(VOID)` — LVO -390 (-$186)
Registers: none; result in D0

Recompute the whole Intuition display (visibility, merge copper lists, load the View).

- **Result** — V39+: 0 on success, non-zero if MakeVPort()/MrgCop() failed. Invalid before V39.

Sets `VP_HIDE` on hidden/incompatible ViewPorts, remakes ViewPorts when heights, interlace or scan rate
changed, then MrgCop() + LoadView().

### Gotchas
- Takes several milliseconds; do not call it every frame unless you must.
- V35 and older: an interlaced screen coming to front may not trigger a full remake.

**See also:** [MakeScreen](#makescreen), [RemakeDisplay](#remakedisplay), graphics.library MrgCop, graphics.library LoadView

## RemakeDisplay
`LONG RemakeDisplay(VOID)` — LVO -384 (-$180)
Registers: none; result in D0

Remake every screen's ViewPort and then rethink the whole display (the expensive one).

- **Result** — V39+: 0 on success, non-zero on MakeVPort()/MrgCop() failure. Invalid before V39.

### Gotchas
- Many milliseconds; for one screen use [MakeScreen](#makescreen) + [RethinkDisplay](#rethinkdisplay).

**See also:** [MakeScreen](#makescreen), [RethinkDisplay](#rethinkdisplay)

## AllocScreenBuffer
`struct ScreenBuffer * AllocScreenBuffer(struct Screen *sc, struct BitMap *bm, ULONG flags)` — LVO -768 (-$300)
Registers: sc=A0, bm=A1, flags=D0; result in D0

Allocate a ScreenBuffer (and normally a BitMap) for double buffering a screen.

- **sc** — screen to double-buffer.
- **bm** — NULL to let Intuition allocate a matching BitMap; for `CUSTOMBITMAP` screens you may pass your
  own matching BitMap (must be NULL for normal screens).
- **flags** — `SB_SCREEN_BITMAP` (1): wrap the screen's current BitMap (normal screens; for
  `CUSTOMBITMAP` pass that BitMap in **bm** instead); `SB_COPY_BITMAP` (2): copy the current display
  (title bar, gadgets) into the new BitMap; omit it for the screen's own buffer or a quiet screen.
- **Result** — `struct ScreenBuffer *` (`sb_BitMap`, `sb_DBufInfo`), or NULL.

`sb_DBufInfo` is a graphics DBufInfo you may use (`dbi_SafeMessage`, `dbi_DispMessage`, `dbi_UserData1/2`)
to learn when the old buffer is safe to draw into.

Since V39.

### Example
```c
#include <proto/graphics.h>

struct ScreenBuffer *sb[2];
struct RastPort rp;
struct MsgPort *safe = CreateMsgPort();
int cur = 1;                                  /* index of the buffer we draw (not shown) */

sb[0] = AllocScreenBuffer(scr, NULL, SB_SCREEN_BITMAP);
sb[1] = AllocScreenBuffer(scr, NULL, SB_COPY_BITMAP);
if (safe && sb[0] && sb[1]) {
    sb[0]->sb_DBufInfo->dbi_SafeMessage.mn_ReplyPort = safe;
    sb[1]->sb_DBufInfo->dbi_SafeMessage.mn_ReplyPort = safe;
    InitRastPort(&rp);
    while (running) {
        rp.BitMap = sb[cur]->sb_BitMap;
        draw_frame(&rp);
        WaitBlit();                           /* rendering finished */
        while (!ChangeScreenBuffer(scr, sb[cur]))
            WaitTOF();                        /* user busy with menus/gadgets: retry */
        WaitPort(safe);                       /* old buffer is now off-screen */
        GetMsg(safe);
        cur ^= 1;
    }
}
WaitBlit();
FreeScreenBuffer(scr, sb[1]);                 /* NULL is OK */
FreeScreenBuffer(scr, sb[0]);
if (safe) DeleteMsgPort(safe);
CloseScreen(scr);
```

### Gotchas
- Drawing into the buffer that is still displayed (or was just swapped out) corrupts what the user
  sees and Intuition's menu/gadget imagery; wait for the safe message or at least a frame.
- The example sets the reply port on every buffer's DBufInfo because which one ChangeScreenBuffer uses
  is not stated in the autodoc.

**See also:** [ChangeScreenBuffer](#changescreenbuffer), [FreeScreenBuffer](#freescreenbuffer),
graphics.library AllocDBufInfo, graphics.library ChangeVPBitMap

## ChangeScreenBuffer
`ULONG ChangeScreenBuffer(struct Screen *sc, struct ScreenBuffer *sb)` — LVO -780 (-$30C)
Registers: sc=A0, sb=A1; result in D0

Install a ScreenBuffer's BitMap as the screen's displayed bitmap.

- **sc** — the screen.
- **sb** — a ScreenBuffer from AllocScreenBuffer for this screen.
- **Result** — non-zero on success; 0 if Intuition cannot swap now (user is using menus or gadgets) --
  retry later.

The previous BitMap may be reused once graphics signals it is safe (see graphics ChangeVPBitMap).

Since V39.

### Gotchas
- Always check the result; a 0 means nothing changed.
- No need to restore the original buffer before closing: free all buffers, then CloseScreen. Never call
  it with a buffer you already freed.

**See also:** [AllocScreenBuffer](#allocscreenbuffer), [FreeScreenBuffer](#freescreenbuffer), graphics.library ChangeVPBitMap

## FreeScreenBuffer
`VOID FreeScreenBuffer(struct Screen *sc, struct ScreenBuffer *sb)` — LVO -774 (-$306)
Registers: sc=A0, sb=A1; no result

Free a ScreenBuffer (and the BitMap Intuition allocated for it).

- **sc** — the screen it belongs to.
- **sb** — ScreenBuffer to free; NULL is a no-op.

Free every buffer, including the installed one, BEFORE [CloseScreen](#closescreen). For the currently
installed buffer Intuition frees only the support structures; CloseScreen frees that BitMap.

Since V39.

### Gotchas
- Call graphics WaitBlit() first: before V40 FreeScreenBuffer did not wait for the blitter.

**See also:** [AllocScreenBuffer](#allocscreenbuffer), [ChangeScreenBuffer](#changescreenbuffer)

## LockIBase
`ULONG LockIBase(ULONG dontknow)` — LVO -414 (-$19E)
Registers: dontknow=D0; result in D0

Take Intuition's internal lock to read IntuitionBase and screen/window lists safely.

- **dontknow** — lock number; always pass 0.
- **Result** — lock value to pass to [UnlockIBase](#unlockibase).

### Example
```c
#include <intuition/intuitionbase.h>

ULONG ilock = LockIBase(0);
struct Screen *front = IntuitionBase->FirstScreen;   /* frontmost screen */
UWORD fw = front ? front->Width : 0;                 /* copy what you need */
UnlockIBase(ilock);
```

### Gotchas
- Hold it very briefly: all Intuition input processing waits for you.
- While holding it call NO Intuition, graphics, layers, DOS or other high-level functions.
- Never call it while holding layer/LayerInfo locks. Always pair with UnlockIBase.
- Pointers read under the lock (e.g. `ActiveWindow`) can go stale right after unlocking.

**See also:** [UnlockIBase](#unlockibase), exec.library ObtainSemaphore, layers.library LockLayerInfo

## UnlockIBase
`VOID UnlockIBase(ULONG ibLock)` — LVO -420 (-$1A4)
Registers: ibLock=A0; no result

Release the Intuition lock obtained with LockIBase.

- **ibLock** — the value LockIBase returned; passed in A0 (not D0) for historical reasons.

### Gotchas
- Unlocking a lock you do not hold crashes the system immediately.

**See also:** [LockIBase](#lockibase)
