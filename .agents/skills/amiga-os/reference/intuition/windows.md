# intuition.library: windows

A window is a layer on a screen with its own RastPort (`Window->RPort`) and, when IDCMP flags are
set, a message port (`Window->UserPort`) that Intuition posts IntuiMessages to. Open it with
OpenWindowTagList (V36+) or OpenWindow, service its IDCMP port (see
[The IDCMP loop](concepts.md#the-idcmp-loop)), and close it with CloseWindow after removing menus.
Move/size/depth calls are *requests*: Intuition performs them later on its input task and reports
completion with `IDCMP_CHANGEWINDOW`.

## OpenWindowTagList
`struct Window * OpenWindowTagList(CONST struct NewWindow *newWindow, CONST struct TagItem *tagList)` — LVO -606 (-$25E)
Registers: newWindow=A0, tagList=A1; result in D0

Open a window described by an optional NewWindow plus a `WA_` tag list.

- **newWindow** — optional `struct NewWindow *`; pass NULL and describe everything with tags.
  Tags override the matching NewWindow fields.
- **tagList** — `TAG_DONE`-terminated `struct TagItem` array (table below). NULL gives a default
  window on the default public screen. Varargs form: `OpenWindowTags(newWindow, tag1, ...)`
  (amiga.lib stub; a macro in the GCC inline headers).
- **Result** — `struct Window *`, or NULL on failure (no memory, no free signal bit, screen gone).

Since V36.

| Tag (`WA_Dummy` = `TAG_USER+99`) | +off | ti_Data | Meaning |
|---|---|---|---|
| `WA_Left`, `WA_Top` | $01, $02 | LONG | outer position on the screen |
| `WA_Width`, `WA_Height` | $03, $04 | LONG | outer size including borders |
| `WA_DetailPen`, `WA_BlockPen` | $05, $06 | UBYTE pen | only override a NewWindow pen of -1; ignored for new-look borders |
| `WA_IDCMP` | $07 | ULONG | initial `IDCMP_` classes (see [ModifyIDCMP](#modifyidcmp)) |
| `WA_Flags` | $08 | ULONG | initial `WFLG_` bits, applied before the boolean tags |
| `WA_Gadgets` | $09 | `struct Gadget *` | first application gadget |
| `WA_Checkmark` | $0A | `struct Image *` | menu checkmark image (V39 default: scaled new-look one with WA_NewLookMenus) |
| `WA_Title` | $0B | `UBYTE *` | window title |
| `WA_ScreenTitle` | $0C | `UBYTE *` | screen title shown while this window is active |
| `WA_CustomScreen` | $0D | `struct Screen *` | open on this (your own) screen; implies CUSTOMSCREEN |
| `WA_SuperBitMap` | $0E | `struct BitMap *` | implies `WFLG_SUPER_BITMAP` |
| `WA_MinWidth`, `WA_MinHeight` | $0F, $10 | LONG | size limits; 0 = current size |
| `WA_MaxWidth`, `WA_MaxHeight` | $11, $12 | ULONG | size limits; `~0` = limited by the screen |
| `WA_InnerWidth`, `WA_InnerHeight` | $13, $14 | LONG | size of the area inside the borders |
| `WA_PubScreenName` | $15 | `UBYTE *` | visitor on the named public screen; NULL = default |
| `WA_PubScreen` | $16 | `struct Screen *` | visitor on this public screen (must be locked/owned); NULL = default |
| `WA_PubScreenFallBack` | $17 | BOOL | use the default public screen if the named one is missing |
| `WA_WindowName`, `WA_Colors` | $18, $19 | -- | not implemented |
| `WA_Zoom` | $1A | `WORD *` (4 WORDs) | alternate Left/Top/Width/Height; adds a zoom gadget. V39: Left/Top = ~0 means size-only zoom |
| `WA_MouseQueue` | $1B | ULONG | max pending `IDCMP_MOUSEMOVE` messages (default `DEFAULTMOUSEQUEUE` = 5) |
| `WA_BackFill` | $1C | `struct Hook *` | layer backfill hook |
| `WA_RptQueue` | $1D | ULONG | max pending repeated RAWKEY/VANILLAKEY/IDCMPUPDATE messages |
| `WA_SizeGadget` .. `WA_RMBTrap` | $1E-$27 | BOOL | same as `WFLG_SIZEGADGET`, `_DRAGBAR`, `_DEPTHGADGET`, `_CLOSEGADGET`, `_BACKDROP`, `_REPORTMOUSE`, `_NOCAREREFRESH`, `_BORDERLESS`, `_ACTIVATE`, `_RMBTRAP` (in that order) |
| `WA_WBenchWindow` | $28 | BOOL | system private |
| `WA_SimpleRefresh`, `WA_SmartRefresh` | $29, $2A | BOOL | refresh type; only pass TRUE |
| `WA_SizeBRight`, `WA_SizeBBottom` | $2B, $2C | BOOL | which border holds the size gadget |
| `WA_AutoAdjust` | $2D | BOOL | allow Intuition to move/shrink the window to fit; default TRUE when newWindow is NULL |
| `WA_GimmeZeroZero` | $2E | BOOL | same as `WFLG_GIMMEZEROZERO` |
| `WA_MenuHelp` | $2F | BOOL | HELP during menus sends `IDCMP_MENUHELP` (V37) |
| `WA_NewLookMenus` | $30 | BOOL | new-look menus in DrawInfo bar pens (V39) |
| `WA_AmigaKey` | $31 | `struct Image *` | Amiga-key symbol image for menus (V39) |
| `WA_NotifyDepth` | $32 | BOOL | also send `IDCMP_CHANGEWINDOW` (Code `CWCODE_DEPTH`) on depth changes (V39) |
| `WA_Pointer` | $34 | APTR | pointerclass object; NULL = Preferences pointer (V39) |
| `WA_BusyPointer` | $35 | BOOL | Preferences busy pointer (V39) |
| `WA_PointerDelay` | $36 | BOOL | delay the pointer change briefly (V39) |
| `WA_TabletMessages` | $37 | BOOL | ExtIntuiMessage with `eim_TabletData` (V39) |
| `WA_HelpGroup` | $38 | ULONG | help group ID from utility.library GetUniqueID (V39) |
| `WA_HelpGroupWindow` | $39 | `struct Window *` | join that window's help group (V39) |

`WFLG_` bits (`Window->Flags`, `WA_Flags`, `NewWindow.Flags`):

| Flag | Value | Meaning |
|---|---|---|
| `WFLG_SIZEGADGET` | $00000001 | sizing gadget |
| `WFLG_DRAGBAR` | $00000002 | drag bar |
| `WFLG_DEPTHGADGET` | $00000004 | depth gadget |
| `WFLG_CLOSEGADGET` | $00000008 | close gadget (sends `IDCMP_CLOSEWINDOW`) |
| `WFLG_SIZEBRIGHT` | $00000010 | size gadget widens the right border |
| `WFLG_SIZEBBOTTOM` | $00000020 | size gadget widens the bottom border |
| `WFLG_SMART_REFRESH` | $00000000 | layers keep obscured contents (`WFLG_REFRESHBITS` = $C0) |
| `WFLG_SIMPLE_REFRESH` | $00000040 | you redraw exposed areas |
| `WFLG_SUPER_BITMAP` | $00000080 | contents kept in your own BitMap |
| `WFLG_BACKDROP` | $00000100 | stays behind all other windows, cannot be depth-arranged |
| `WFLG_REPORTMOUSE` | $00000200 | report mouse movement |
| `WFLG_GIMMEZEROZERO` | $00000400 | separate border layer, RPort origin inside borders |
| `WFLG_BORDERLESS` | $00000800 | no border lines |
| `WFLG_ACTIVATE` | $00001000 | activate on open |
| `WFLG_RMBTRAP` | $00010000 | right button events come to you, no menus |
| `WFLG_NOCAREREFRESH` | $00020000 | Intuition clears the refresh state for you |
| `WFLG_NW_EXTENDED` | $00040000 | NewWindow is an ExtNewWindow with an `Extension` tag list (V36) |
| `WFLG_NEWLOOKMENUS` | $00200000 | new-look menus (V39) |
| `WFLG_WINDOWACTIVE` | $00002000 | set by Intuition: window is active (read only) |
| `WFLG_INREQUEST` | $00004000 | set by Intuition (read only) |
| `WFLG_MENUSTATE` | $00008000 | set by Intuition (read only) |
| `WFLG_WINDOWREFRESH` | $01000000 | set by Intuition between BeginRefresh/EndRefresh |
| `WFLG_WBENCHWINDOW` | $02000000 | system private |
| `WFLG_WINDOWTICKED` | $04000000 | set by Intuition |
| `WFLG_VISITOR` | $08000000 | set by Intuition: visitor window (V36) |
| `WFLG_ZOOMED` | $10000000 | set by Intuition: in alternate zoom state (V36) |
| `WFLG_HASZOOM` | $20000000 | set by Intuition: has a zoom gadget (V36) |

### Example
```c
#include <proto/exec.h>
#include <proto/intuition.h>
#include <intuition/intuition.h>

/* Full-screen input window for a game on your own screen. */
struct Window *OpenGameWindow(struct Screen *scr)
{
    struct Window *win = OpenWindowTags(NULL,
        WA_CustomScreen, (ULONG)scr,
        WA_Left,         0,
        WA_Top,          0,
        WA_Width,        scr->Width,
        WA_Height,       scr->Height,
        WA_Borderless,   TRUE,
        WA_Backdrop,     TRUE,
        WA_Activate,     TRUE,
        WA_RMBTrap,      TRUE,          /* right button to us, no menu bar */
        WA_IDCMP,        IDCMP_RAWKEY | IDCMP_MOUSEBUTTONS,
        TAG_DONE);
    return win;                         /* NULL on failure: check it */
}
```

### Gotchas
- The GCC varargs macros store each value in a ULONG array: cast pointers (`(ULONG)scr`,
  `(ULONG)"Title"`); GCC 14+ rejects an implicit pointer-to-integer conversion.
- Each window with its own IDCMP port takes one of the task's 16 user signal bits; opening fails
  when none is free.
- `WA_PubScreen` needs a screen you own, hold a lock on (LockPubScreen) or already have a window on.
  Forbid() is not enough. Pass NULL for the default public screen.
- `WA_Activate` is not synchronous: wait for `IDCMP_ACTIVEWINDOW` before relying on activation
  (e.g. before ActivateGadget).
- Backdrop + borderless on a screen opened with `SA_ShowTitle` FALSE (or ShowTitle(scr, FALSE)) is
  the usual way to own the whole screen area; the screen title bar otherwise stays in front of
  backdrop windows.
- Without `WFLG_GIMMEZEROZERO`, `Window->RPort` coordinates include the borders: draw at
  `BorderLeft`/`BorderTop` offsets. GZZ windows are more expensive (extra layer).
- GZZ bug: the window RastPort gets the system default font, not the screen font (not fixed).
- Varargs tag lists are read at open time only; the tag array may be discarded afterwards.

**See also:** [OpenWindow](#openwindow), [CloseWindow](#closewindow), [ModifyIDCMP](#modifyidcmp),
[Tag-based opening](concepts.md#tag-based-opening), [Public screens](concepts.md#public-screens),
[LockPubScreen](screens.md#lockpubscreen), [OpenScreenTagList](screens.md#openscreentaglist)

## OpenWindow
`struct Window * OpenWindow(CONST struct NewWindow *newWindow)` — LVO -204 (-$CC)
Registers: newWindow=A0; result in D0

Open a window from a NewWindow structure (pre-V36 interface).

- **newWindow** — initialized `struct NewWindow`, may be discarded after the call:
  `LeftEdge`, `TopEdge`, `Width`, `Height`; `DetailPen`, `BlockPen` (-1 = screen pens);
  `IDCMPFlags` (`IDCMP_` classes, 0 = no port); `Flags` (`WFLG_` bits, see table above);
  `FirstGadget`; `CheckMark` (NULL = default); `Title`; `Screen` (only for `Type` CUSTOMSCREEN);
  `BitMap` (only with `WFLG_SUPER_BITMAP`); `MinWidth`, `MinHeight`, `MaxWidth`, `MaxHeight`
  (0 = current size, `~0` max = screen-limited); `Type` = `WBENCHSCREEN`, `CUSTOMSCREEN` or
  `PUBLICSCREEN` (V36).
- **Result** — `struct Window *` or NULL.

V36+: set `WFLG_NW_EXTENDED` and pass an `ExtNewWindow` whose `Extension` points to `WA_` tags, or
better call [OpenWindowTagList](#openwindowtaglist) (all tags are documented there).

### Example
```asm
        include "exec/types.i"
        include "intuition/intuition.i"
        include "intuition/screens.i"
        include "lvo/intuition_lib.i"

        move.l  IntuitionBase,a6
        lea     nw(pc),a0
        jsr     _LVOOpenWindow(a6)
        move.l  d0,d7                   ; Window, keep in non-scratch reg
        beq     .fail
        ...
nw:     dc.w    20,20,300,100           ; LeftEdge TopEdge Width Height
        dc.b    -1,-1                   ; DetailPen BlockPen = screen pens
        dc.l    IDCMP_CLOSEWINDOW       ; IDCMPFlags
        dc.l    WFLG_CLOSEGADGET!WFLG_DRAGBAR!WFLG_DEPTHGADGET!WFLG_ACTIVATE
        dc.l    0,0,title,0,0           ; FirstGadget CheckMark Title Screen BitMap
        dc.w    0,0,0,0                 ; MinWidth MinHeight MaxWidth MaxHeight
        dc.w    WBENCHSCREEN            ; Type
title:  dc.b    "Hello",0
        even
```

### Gotchas
- Always fill the Min/Max fields sensibly even without a size gadget: other programs may call
  SizeWindow/ChangeWindowBox on your window.
- `Type` WBENCHSCREEN may be redirected to the default public screen when `SHANGHAI` mode is on.
- Do not use the obsolete names `WINDOWACTIVE` / `ACTIVEWINDOW` as flags: they are different bits
  in different words (`WFLG_WINDOWACTIVE` vs `IDCMP_ACTIVEWINDOW`).
- V36+: border gadgets (`GACT_RIGHTBORDER`/`GACT_BOTTOMBORDER`) only widen the borders when they are
  also `GFLG_RELRIGHT`/`GFLG_RELBOTTOM`.
- Requester/"service" windows for a client window should open on `client->WScreen` as
  CUSTOMSCREEN (or `WA_CustomScreen`), not as visitors; keep the client open until they close.

**See also:** [OpenWindowTagList](#openwindowtaglist), [CloseWindow](#closewindow),
[ModifyIDCMP](#modifyidcmp), [SetWindowTitles](#setwindowtitles), [WindowLimits](#windowlimits)

## CloseWindow
`VOID CloseWindow(struct Window *window)` — LVO -72 (-$48)
Registers: window=A0; no result

Close a window, free its IDCMP messages and ports, and remove it from the screen.

- **window** — window from OpenWindow/OpenWindowTagList.

### Example
```c
if (win) {
    ClearMenuStrip(win);        /* only if SetMenuStrip() was called */
    CloseWindow(win);
    win = NULL;
}
```

### Gotchas
- Call [ClearMenuStrip](menus.md#clearmenustrip) before closing if a menu strip is attached.
- All messages still queued for the window are freed. With a port shared by several windows, first
  (under Forbid) remove and reply this window's pending messages, set `window->UserPort = NULL`
  and `ModifyIDCMP(window, 0)`, then close -- see
  [Closing a window with a shared port](concepts.md#closing-a-window-with-a-shared-port).
- Never touch an IntuiMessage (or its `IDCMPWindow`) after the window is closed.
- May block while the user is dragging, sizing or using menus/gadgets.
- If `pr_WindowPtr` of your process points at this window, restore it BEFORE closing.
- V36+: closing the last visitor window on a public screen signals the screen's owner.
- The screen cannot close while any window is open on it (V36+ CloseScreen fails).

**See also:** [OpenWindowTagList](#openwindowtaglist), [ModifyIDCMP](#modifyidcmp),
[CloseScreen](screens.md#closescreen), [The IDCMP loop](concepts.md#the-idcmp-loop)

## ModifyIDCMP
`BOOL ModifyIDCMP(struct Window *window, ULONG flags)` — LVO -150 (-$96)
Registers: window=A0, flags=D0; result in D0

Change which IDCMP classes a window receives, creating or deleting its message ports.

- **window** — the window.
- **flags** — new set of `IDCMP_` classes (table). Effects: no port + non-zero flags -> Intuition
  creates `UserPort` (allocating a signal bit) and `WindowPort`; port + 0 -> ports and signal freed;
  port + non-zero -> just changes the class mask. If you set `window->UserPort` to your own port
  first, Intuition uses it and only creates its own `WindowPort` half.
- **Result** — V37+: FALSE if the ports could not be created. Do not test it on V36 or earlier.

| Class | Value | Sent when / Code / IAddress |
|---|---|---|
| `IDCMP_SIZEVERIFY` | $00000001 | user starts sizing; Intuition waits for your reply |
| `IDCMP_NEWSIZE` | $00000002 | after a user resize; read `Width`/`Height` |
| `IDCMP_REFRESHWINDOW` | $00000004 | damage to repair (BeginRefresh/EndRefresh) |
| `IDCMP_MOUSEBUTTONS` | $00000008 | button events not used by Intuition; Code `SELECTDOWN`, `SELECTUP`, `MENUDOWN`, `MENUUP`, `MIDDLEDOWN`, `MIDDLEUP` |
| `IDCMP_MOUSEMOVE` | $00000010 | mouse moved; needs `WFLG_REPORTMOUSE` or a `GACT_FOLLOWMOUSE` gadget |
| `IDCMP_GADGETDOWN` | $00000020 | `GACT_IMMEDIATE` gadget pressed; IAddress = gadget |
| `IDCMP_GADGETUP` | $00000040 | `GACT_RELVERIFY` gadget released inside it (or Return in a string gadget); IAddress = gadget |
| `IDCMP_REQSET` | $00000080 | a requester opened in the window |
| `IDCMP_MENUPICK` | $00000100 | menu selection; Code = menu number or `MENUNULL` |
| `IDCMP_CLOSEWINDOW` | $00000200 | close gadget clicked |
| `IDCMP_RAWKEY` | $00000400 | raw key code in Code (bit 7 = key up), qualifiers in Qualifier |
| `IDCMP_REQVERIFY` | $00000800 | a requester is about to open; Intuition waits for your reply |
| `IDCMP_REQCLEAR` | $00001000 | a requester was removed |
| `IDCMP_MENUVERIFY` | $00002000 | menus about to render; Code `MENUHOT` (your menu: reply with Code `MENUCANCEL` to cancel) or `MENUWAITING` |
| `IDCMP_NEWPREFS` | $00004000 | Preferences changed |
| `IDCMP_DISKINSERTED` | $00008000 | a disk was inserted |
| `IDCMP_DISKREMOVED` | $00010000 | a disk was removed |
| `IDCMP_WBENCHMESSAGE` | $00020000 | system use only |
| `IDCMP_ACTIVEWINDOW` | $00040000 | window became active |
| `IDCMP_INACTIVEWINDOW` | $00080000 | window lost activation |
| `IDCMP_DELTAMOVE` | $00100000 | modifier: MOUSEMOVE MouseX/MouseY become raw deltas |
| `IDCMP_VANILLAKEY` | $00200000 | keymap-translated character in Code (no HELP/F-keys/cursors) |
| `IDCMP_INTUITICKS` | $00400000 | about 10 per second while active; never more than one queued |
| `IDCMP_IDCMPUPDATE` | $00800000 | BOOPSI notification with `ICA_TARGET` = `ICTARGET_IDCMP`; IAddress = attribute tag list (V36) |
| `IDCMP_MENUHELP` | $01000000 | HELP pressed during a menu session (needs `WA_MenuHelp`, V37) |
| `IDCMP_CHANGEWINDOW` | $02000000 | moved/sized/zoomed, Code `CWCODE_MOVESIZE`; depth change Code `CWCODE_DEPTH` with `WA_NotifyDepth` (V36) |
| `IDCMP_GADGETHELP` | $04000000 | gadget help, see [HelpControl](#helpcontrol) (V39) |

`IDCMP_LONELYMESSAGE` ($80000000) is a system bit, never a class you request.

### Example
```asm
; Turn MENUVERIFY off before any dos.library call
        move.l  IntuitionBase,a6
        move.l  window,a0
        move.l  #IDCMP_CLOSEWINDOW!IDCMP_MENUPICK,d0
        jsr     _LVOModifyIDCMP(a6)
        tst.w   d0                      ; BOOL (V37+): 0 = no ports
        beq     .fail
```

### Gotchas
- VERIFY classes (`SIZEVERIFY`, `REQVERIFY`, `MENUVERIFY`) block the user until you reply. Never
  call dos.library (directly or indirectly) while one is enabled: a DOS requester waiting for you
  while Intuition waits for you locks the machine. Switch them off with ModifyIDCMP first. V36+
  times out unanswered verifies, but do not rely on it.
- Setting both `IDCMP_RAWKEY` and `IDCMP_VANILLAKEY` (V36+): non-character keys arrive as RAWKEY
  downstrokes, and you get no RAWKEY upstrokes at all.
- `ModifyIDCMP(win, 0)` must be called by the same task that allocated the signal bit.
- Shared port: open with no IDCMP, set `win->UserPort = sharedPort`, then ModifyIDCMP with the
  wanted flags. Before CloseWindow, strip its messages and set `UserPort` back to NULL.
- Autodoc says `IDCMP_MENUHELP` is V37; intuition.h comments say "new for V36" -- V37 is when
  `WA_MenuHelp` works.

**See also:** [OpenWindowTagList](#openwindowtaglist), [CloseWindow](#closewindow),
[IntuiMessage fields](concepts.md#intuimessage-fields), [The IDCMP loop](concepts.md#the-idcmp-loop),
[ReportMouse](#reportmouse), [SetMouseQueue](#setmousequeue)

## ActivateWindow
`VOID ActivateWindow(struct Window *window)` — LVO -450 (-$1C2)
Registers: window=A0; no result

Ask Intuition to make a window the active (input-receiving) window.

- **window** — window to activate.

### Example
```asm
        move.l  IntuitionBase,a6
        move.l  window,a0
        jsr     _LVOActivateWindow(a6)  ; deferred; wait for IDCMP_ACTIVEWINDOW
```

### Gotchas
- Deferred: the window is not active when the call returns (postponed while the user is using
  gadgets, menus, dragging). Watch for `IDCMP_ACTIVEWINDOW`.
- No return value (some old docs, including the V37 autodoc, claimed a LONG result).
- Calling it in a tight loop can overflow Intuition's deferred-action queue. Only activate in
  response to something the user did.

**See also:** [OpenWindowTagList](#openwindowtaglist) (`WA_Activate`), [ModifyIDCMP](#modifyidcmp)

## WindowToFront
`VOID WindowToFront(struct Window *window)` — LVO -312 (-$138)
Registers: window=A0; no result

Ask Intuition to move a window in front of all other windows on its screen.

- **window** — window to bring forward.

### Gotchas
- Deferred until Intuition's next input event (between 10 and 60 times a second).
- `WFLG_BACKDROP` windows cannot be depth-arranged.

**See also:** [WindowToBack](#windowtoback), [MoveWindowInFrontOf](#movewindowinfrontof),
[MoveWindow](#movewindow)

## WindowToBack
`VOID WindowToBack(struct Window *window)` — LVO -306 (-$132)
Registers: window=A0; no result

Ask Intuition to move a window behind all other windows on its screen.

- **window** — window to send back.

### Gotchas
- Deferred until Intuition's next input event.
- `WFLG_BACKDROP` windows cannot be depth-arranged; the window stays in front of backdrop windows.

**See also:** [WindowToFront](#windowtofront), [MoveWindowInFrontOf](#movewindowinfrontof)

## MoveWindowInFrontOf
`VOID MoveWindowInFrontOf(struct Window *window, struct Window *behindWindow)` — LVO -480 (-$1E0)
Registers: window=A0, behindWindow=A1; no result

Depth-arrange a window directly in front of another window.

- **window** — window to move.
- **behindWindow** — window it should end up in front of.

Since V36.

### Gotchas
- Does not respect backdrop windows.

**See also:** [WindowToFront](#windowtofront), [WindowToBack](#windowtoback),
layers.library MoveLayerInFrontOf

## MoveWindow
`VOID MoveWindow(struct Window *window, LONG dx, LONG dy)` — LVO -168 (-$A8)
Registers: window=A0, dx=D0, dy=D1; no result

Ask Intuition to move a window by a relative amount.

- **window** — window to move.
- **dx**, **dy** — pixels to move right/down (negative = left/up).

### Gotchas
- Deferred to Intuition's input handling; `IDCMP_CHANGEWINDOW` (V36) tells you when it happened.
- Relative deltas combined with deferral can give surprises if the user also drags; for absolute
  placement use [ChangeWindowBox](#changewindowbox).
- V36+ clips the result to legal positions.

**See also:** [ChangeWindowBox](#changewindowbox), [SizeWindow](#sizewindow),
[WindowToFront](#windowtofront)

## SizeWindow
`VOID SizeWindow(struct Window *window, LONG dx, LONG dy)` — LVO -288 (-$120)
Registers: window=A0, dx=D0, dy=D1; no result

Ask Intuition to resize a window by a relative amount.

- **window** — window to resize.
- **dx**, **dy** — pixels to add to width/height (negative shrinks).

### Gotchas
- Deferred; `IDCMP_NEWSIZE` or (V36) `IDCMP_CHANGEWINDOW` reports completion.
- V36+ checks against MinWidth/MaxWidth/MinHeight/MaxHeight only when the window has
  `WFLG_SIZEGADGET`; before V36 the limits were never checked.

**See also:** [ChangeWindowBox](#changewindowbox), [MoveWindow](#movewindow),
[WindowLimits](#windowlimits)

## ChangeWindowBox
`VOID ChangeWindowBox(struct Window *window, LONG left, LONG top, LONG width, LONG height)` — LVO -486 (-$1E6)
Registers: window=A0, left=D0, top=D1, width=D2, height=D3; no result

Ask Intuition to set a window's absolute position and size in one step.

- **window** — window to change.
- **left**, **top** — new outer position on the screen.
- **width**, **height** — new outer size.

Since V36.

### Example
```c
/* Snap a window to the top-left quarter of its screen. */
struct Screen *s = win->WScreen;
ChangeWindowBox(win, 0, s->BarHeight + 1, s->Width / 2, s->Height / 2);
/* completion arrives as IDCMP_CHANGEWINDOW */
```

### Gotchas
- Deferred like MoveWindow/SizeWindow, but absolute values make it robust against deferral --
  prefer it over a MoveWindow + SizeWindow pair.
- Values are clipped to legal limits; still pass sane numbers based on the window limits and
  screen size.

**See also:** [MoveWindow](#movewindow), [SizeWindow](#sizewindow), [ZipWindow](#zipwindow),
layers.library MoveSizeLayer

## ZipWindow
`VOID ZipWindow(struct Window *window)` — LVO -504 (-$1F8)
Registers: window=A0; no result

Toggle a window between its current and alternate ("zoomed") position and size.

- **window** — window to toggle.

Since V36.

### Gotchas
- Deferred; `IDCMP_CHANGEWINDOW` reports completion.
- The zoom gadget appears when the window has a size gadget or `WA_Zoom`. Without `WA_Zoom` the
  first alternate size defaults to "full size".

**See also:** [ChangeWindowBox](#changewindowbox), [OpenWindowTagList](#openwindowtaglist) (`WA_Zoom`)

## WindowLimits
`BOOL WindowLimits(struct Window *window, LONG widthMin, LONG heightMin, ULONG widthMax, ULONG heightMax)` — LVO -318 (-$13E)
Registers: window=A0, widthMin=D0, heightMin=D1, widthMax=D2, heightMax=D3; result in D0

Set the minimum and maximum size the user can size a window to.

- **window** — the window.
- **widthMin**, **heightMin** — minimums; 0 = leave unchanged.
- **widthMax**, **heightMax** — maximums; 0 = leave unchanged, `~0` = as big as the screen allows.
- **Result** — TRUE if all limits were valid; FALSE if any was out of range (minimum larger than
  the current size, maximum smaller). Valid ones are still applied.

### Gotchas
- With `~0` maximums your code must cope with any size up to the screen (check `WScreen->Width`).
- New limits take effect after a sizing operation the user is currently doing.

**See also:** [SizeWindow](#sizewindow), [ChangeWindowBox](#changewindowbox),
[LockPubScreen](screens.md#lockpubscreen)

## SetWindowTitles
`VOID SetWindowTitles(struct Window *window, CONST_STRPTR windowTitle, CONST_STRPTR screenTitle)` — LVO -276 (-$114)
Registers: window=A0, windowTitle=A1, screenTitle=A2; no result

Change the window title and/or the screen title shown while the window is active.

- **windowTitle** — new window title, `(UBYTE *)~0` = keep current, NULL = blank title.
- **screenTitle** — screen title for when this window is active; same ~0 / NULL rules.

### Example
```c
SetWindowTitles(win, (CONST_STRPTR)"Level 2", (CONST_STRPTR)~0);  /* keep screen title */
```

### Gotchas
- Intuition keeps the pointers, not copies: strings must stay valid while shown.
- Titles use the screen's font. Rendering may disturb your own drawing in the top border; use
  [RefreshWindowFrame](#refreshwindowframe) if you draw there.

**See also:** [OpenWindowTagList](#openwindowtaglist) (`WA_Title`, `WA_ScreenTitle`),
[RefreshWindowFrame](#refreshwindowframe)

## RefreshWindowFrame
`VOID RefreshWindowFrame(struct Window *window)` — LVO -456 (-$1C8)
Registers: window=A0; no result

Redraw a window's border, title bar and gadgets.

- **window** — window whose frame is to be redrawn.

### Gotchas
- Only for repairing corruption you could not avoid (e.g. after drawing over the border).
- Never call it between BeginRefresh and EndRefresh (deadlock risk).

**See also:** [SetWindowTitles](#setwindowtitles), [BeginRefresh](#beginrefresh)

## BeginRefresh
`VOID BeginRefresh(struct Window *window)` — LVO -354 (-$162)
Registers: window=A0; no result

Enter the refresh state so rendering is clipped to the window's damaged regions only.

- **window** — window that got `IDCMP_REFRESHWINDOW`.

Sets `WFLG_WINDOWREFRESH` and locks the layers in the correct order; wraps layers.library
BeginUpdate. Always pair with [EndRefresh](#endrefresh).

### Example
```c
case IDCMP_REFRESHWINDOW:           /* WFLG_SIMPLE_REFRESH window */
    BeginRefresh(imsgWin);
    DrawPlayfield(imsgWin->RPort);  /* graphics.library calls only */
    EndRefresh(imsgWin, TRUE);
    break;
```

### Gotchas
- Between BeginRefresh and EndRefresh only do simple rendering: graphics.library drawing,
  DrawImage, DrawBorder, PrintIText. Do NOT call RefreshGadgets/RefreshGList/RefreshWindowFrame,
  SetPointer, LockIBase, or anything that can reach dos.library (EasyRequest) -- deadlock.
- When you receive the message the border and gadgets are already repaired; do not redraw them.
- Even if you draw nothing, call BeginRefresh + EndRefresh(TRUE) on every `IDCMP_REFRESHWINDOW`
  to clear the damage, or open the window with `WFLG_NOCAREREFRESH`.
- Multiple passes with `EndRefresh(w, FALSE)` are unsafe unless you hold
  `LockLayerInfo(&w->WScreen->LayerInfo)` around all passes (new damage could be discarded).
- Using layers BeginUpdate directly on a window layer is unsupported; if you must, hold the
  LayerInfo lock.
- Bug: BeginUpdate's return value is not checked.

**See also:** [EndRefresh](#endrefresh), [OpenWindowTagList](#openwindowtaglist)
(`WA_NoCareRefresh`), layers.library BeginUpdate, layers.library LockLayerInfo

## EndRefresh
`VOID EndRefresh(struct Window *window, LONG complete)` — LVO -366 (-$16E)
Registers: window=A0, complete=D0; no result

Leave the refresh state entered with BeginRefresh.

- **window** — window in refresh state.
- **complete** — TRUE if refreshing is finished (damage list discarded); FALSE if another
  BeginRefresh/EndRefresh pass follows.

Calls layers.library EndUpdate, unlocks the layers, clears `LAYERREFRESH` in the layer and
`WFLG_WINDOWREFRESH` in the window.

### Gotchas
- Pass TRUE unless you really do multi-pass refresh, and then protect the passes with
  LockLayerInfo (see [BeginRefresh](#beginrefresh)).

**See also:** [BeginRefresh](#beginrefresh), layers.library EndUpdate

## ScrollWindowRaster
`VOID ScrollWindowRaster(struct Window *win, LONG dx, LONG dy, LONG xMin, LONG yMin, LONG xMax, LONG yMax)` — LVO -798 (-$31E)
Registers: win=A1, dx=D0, dy=D1, xMin=D2, yMin=D3, xMax=D4, yMax=D5; no result

Scroll part of a window's contents and let Intuition handle the damage it exposes.

- **win** — the window (passed in A1, not A0).
- **dx**, **dy** — scroll amount; positive values move the bits toward (0,0).
- **xMin**, **yMin**, **xMax**, **yMax** — rectangle to scroll in RastPort coordinates; a max
  beyond the RastPort is clipped to it.

Calls graphics.library ScrollRasterBF (vacated area filled via EraseRect / the layer backfill hook).
In a simple-refresh window, areas scrolled in from under other windows become damage and you get
`IDCMP_REFRESHWINDOW`.

Since V39.

### Gotchas
- V39/V40 bug: race with gadget event handling in windows without `WA_NoCareRefresh` (writes to
  freed memory, lost refresh messages). Safe use: `WFLG_SMART_REFRESH` + `WA_NoCareRefresh`.
- The vacated area is NOT damage; redraw it yourself.
- Never call it from inside a BOOPSI gadget dispatcher; gadgets use ScrollRaster/ScrollRasterBF.
- If a simple-refresh window contains gadgets with `GMORE_SCROLLRASTER`, you must use
  ScrollWindowRaster instead of ScrollRaster/ScrollRasterBF.

**See also:** graphics.library ScrollRaster, graphics.library ScrollRasterBF,
graphics.library EraseRect, [BeginRefresh](#beginrefresh)

## SetWindowPointerA
`VOID SetWindowPointerA(struct Window *win, CONST struct TagItem *taglist)` — LVO -816 (-$330)
Registers: win=A0, taglist=A1; no result

Set the mouse pointer shown while a window is active, by tags.

- **win** — the window.
- **taglist** — `WA_Pointer` (pointerclass object, NULL = Preferences default), `WA_BusyPointer`
  (BOOL, standard busy pointer), `WA_PointerDelay` (BOOL, change only after a short delay). An empty
  list restores the default pointer. Varargs form: `SetWindowPointer(win, tag1, ...)`.

Since V39.

### Example
```c
#include <intuition/intuitionbase.h>     /* for LibNode */

if (IntuitionBase->LibNode.lib_Version >= 39) {
    SetWindowPointer(win, WA_BusyPointer, TRUE, WA_PointerDelay, TRUE, TAG_DONE);
    CrunchData();                           /* the slow part */
    SetWindowPointer(win, TAG_DONE);        /* back to normal */
}
```

### Gotchas
- V39+ only; on V37 fall back to [SetPointer](#setpointer)/[ClearPointer](#clearpointer).
- Custom pointers are BOOPSI objects: `NewObject(NULL, POINTERCLASS, POINTERA_BitMap, ...,
  POINTERA_XOffset, ..., POINTERA_YOffset, ..., TAG_DONE)` (intuition/pointerclass.h). Clear the
  window pointer before DisposeObject.
- `WA_PointerDelay` avoids busy-pointer flicker for short operations; a later pointer change
  cancels the pending one.

**See also:** [SetPointer](#setpointer), [ClearPointer](#clearpointer),
[NewObjectA](boopsi.md#newobjecta)

## SetPointer
`VOID SetPointer(struct Window *window, UWORD *pointer, LONG height, LONG width, LONG xOffset, LONG yOffset)` — LVO -270 (-$10E)
Registers: window=A0, pointer=A1, height=D0, width=D1, xOffset=D2, yOffset=D3; no result

Give a window its own sprite-image mouse pointer (classic interface).

- **pointer** — sprite data: 2 reserved words (0,0), then `height` pairs of words (first word =
  low colour bit, second = high colour bit; pointer colours 17-19), then 2 zero words.
- **height** — lines of image data.
- **width** — pixels, at most 16.
- **xOffset**, **yOffset** — offset from the hot spot to the image's top-left corner (usually
  negative or zero): -7 centres a 16-pixel-wide image horizontally.

The change is immediate when the window is active.

### Example
```c
/* exec/memory.h for MEMF_CHIP. 3x3 plus sign, colour 1 (pen 17). */
static const UWORD plus[] = {
    0x0000, 0x0000,
    0x4000, 0x0000,
    0xE000, 0x0000,
    0x4000, 0x0000,
    0x0000, 0x0000
};
UWORD *chipPtr = AllocMem(sizeof(plus), MEMF_CHIP);
if (chipPtr) {
    CopyMem((APTR)plus, chipPtr, sizeof(plus));
    SetPointer(win, chipPtr, 3, 3, -1, -1);
}
/* ... later: ClearPointer(win); then FreeMem(chipPtr, sizeof(plus)); */
```

### Gotchas
- Keep the data in chip RAM and valid until ClearPointer or the window closes (unverified for
  V39+, where Intuition converts it; chip RAM is always safe).
- Call ClearPointer before freeing the data.
- V39+: prefer [SetWindowPointerA](#setwindowpointera) with pointerclass for hi-res pointers.

**See also:** [ClearPointer](#clearpointer), [SetWindowPointerA](#setwindowpointera)

## ClearPointer
`VOID ClearPointer(struct Window *window)` — LVO -60 (-$3C)
Registers: window=A0; no result

Remove a window's custom pointer so the default pointer is used again.

- **window** — window whose SetPointer/SetWindowPointer pointer is removed.

Takes effect immediately if the window is active.

**See also:** [SetPointer](#setpointer), [SetWindowPointerA](#setwindowpointera)

## ReportMouse
`VOID ReportMouse(LONG flag, struct Window *window)` — LVO -234 (-$EA)
Registers: flag=D0, window=A0; no result

Turn mouse-movement reporting for a window on or off.

- **flag** — TRUE to report movement, FALSE to stop. Sets/clears `WFLG_REPORTMOUSE`; while a gadget
  is selected it temporarily changes that gadget's `GACT_FOLLOWMOUSE` behaviour instead.
- **window** — the window.

Movement arrives as `IDCMP_MOUSEMOVE` only if that class is enabled too ([ModifyIDCMP](#modifyidcmp)).

Alias: `ReportMouse1` (same LVO -234) exists for compilers that expect the arguments swapped.

### Example
```asm
        move.l  IntuitionBase,a6
        moveq   #1,d0                   ; flag = TRUE  (D0)
        move.l  window,a0               ; window       (A0)
        jsr     _LVOReportMouse(a6)
```

### Gotchas
- ROM interface is fixed: flag in D0, window in A0, whatever the C argument order.
- `ReportMouse1` is a trap: the NDK pragma declares it `(window, flag)` with window in A0, but the
  SFD and the sfdc-generated GCC inline headers map its first argument (the window) to D0. Use
  `ReportMouse(flag, window)` or `WA_ReportMouse` instead.
- Setting/clearing `WFLG_REPORTMOUSE` in `Window->Flags` yourself is endorsed if done atomically
  (`or.w #WFLG_REPORTMOUSE,wd_Flags+2(a0)`, or bracket with Forbid/Permit).
- Mouse moves flood the port; limit with [SetMouseQueue](#setmousequeue).

**See also:** [ModifyIDCMP](#modifyidcmp), [SetMouseQueue](#setmousequeue),
[OpenWindowTagList](#openwindowtaglist) (`WA_ReportMouse`)

## SetMouseQueue
`LONG SetMouseQueue(struct Window *window, ULONG queueLength)` — LVO -498 (-$1F2)
Registers: window=A0, queueLength=D0; result in D0

Set how many unreplied `IDCMP_MOUSEMOVE` messages a window may have queued.

- **window** — the window.
- **queueLength** — new limit; further mouse moves are dropped while this many are outstanding.
- **Result** — previous limit, or -1 if the window is unknown.

Since V36.

### Gotchas
- Default is `DEFAULTMOUSEQUEUE` (5); `WA_MouseQueue` sets it at open time.
- No function exists for the repeat-key queue; only `WA_RptQueue` at open time.

**See also:** [ReportMouse](#reportmouse), [OpenWindowTagList](#openwindowtaglist)

## HelpControl
`VOID HelpControl(struct Window *win, ULONG flags)` — LVO -828 (-$33C)
Registers: win=A0, flags=D0; no result

Turn gadget help on or off for a window and all windows in its help group.

- **win** — the window.
- **flags** — `HC_GADGETHELP` (1) to enable, 0 to disable.

While enabled, `IDCMP_GADGETHELP` messages report what the mouse is over: IAddress = a gadget with
`GMORE_GADGETHELP`, the window itself, or 0 (outside the window/group). Code is normally `~0`.

Since V39.

### Gotchas
- Help group IDs (`WA_HelpGroup`) must come from utility.library GetUniqueID; never invent one.
- Only the active window (or windows sharing its help group) get help messages; none while the
  mouse moves fast or stands still.

**See also:** [OpenWindowTagList](#openwindowtaglist) (`WA_HelpGroup`, `WA_HelpGroupWindow`),
[ModifyIDCMP](#modifyidcmp)
