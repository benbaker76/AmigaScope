# intuition.library: concepts

What sits between the function entries. It covers how a program gets input from its windows
(IDCMP), which Window/Screen fields you may read, tag lists, public screens, and a complete
minimal program. Names are checked against the NDK 3.9 `intuition/intuition.h`, `intuition/screens.h`
and their `.i` counterparts.

## The IDCMP loop

A window opened with non-zero IDCMP flags (`WA_IDCMP` or `NewWindow.IDCMPFlags`) gets a message port
in `Window->UserPort`. Intuition posts one `struct IntuiMessage` per event there. The port has a signal
bit `UserPort->mp_SigBit`, so you can Wait() on it together with other signals.

The rules:

1. **Wait**, then **drain**. After waking, call GetMsg() until it returns NULL. Several messages can
   arrive for one wake-up.
2. **Copy** the fields you need (`Class`, `Code`, `Qualifier`, `IAddress`, `MouseX`, `MouseY`,
   `Seconds`, `Micros`, `IDCMPWindow`) into locals.
3. **ReplyMsg** promptly and never touch the message afterwards: Intuition reuses it.
4. **Act** on the copies. Close the window only after the loop has stopped using the port.

Exceptions to "reply before acting": for `IDCMP_SIZEVERIFY`, `IDCMP_REQVERIFY` and `IDCMP_MENUVERIFY`,
Intuition (and the user) wait for your reply. Finish your drawing, then reply quickly. On a
`IDCMP_MENUVERIFY` with `Code == MENUHOT` you may set `Code = MENUCANCEL` before replying to cancel the
menu. Never call dos.library while a VERIFY class is enabled (see [ModifyIDCMP](windows.md#modifyidcmp)).
For `IDCMP_IDCMPUPDATE` read the tag list at `IAddress` before replying (unverified: that it is
invalid after the reply; handling it first is safe either way).

```c
ULONG winsig = 1UL << win->UserPort->mp_SigBit;
BOOL done = FALSE;

while (!done) {
    ULONG sigs = Wait(winsig | SIGBREAKF_CTRL_C);
    if (sigs & SIGBREAKF_CTRL_C)
        done = TRUE;

    struct IntuiMessage *im;
    while ((im = (struct IntuiMessage *)GetMsg(win->UserPort)) != NULL) {
        ULONG class = im->Class;
        UWORD code  = im->Code;
        WORD  mx    = im->MouseX, my = im->MouseY;
        APTR  iaddr = im->IAddress;
        ReplyMsg((struct Message *)im);          /* reply first ... */

        switch (class) {                         /* ... then act on the copies */
        case IDCMP_CLOSEWINDOW:  done = TRUE; break;
        case IDCMP_VANILLAKEY:   if (code == 27) done = TRUE; break;   /* Esc */
        case IDCMP_MOUSEBUTTONS: if (code == SELECTDOWN) { /* click at mx,my */ } break;
        case IDCMP_GADGETUP:     /* ((struct Gadget *)iaddr)->GadgetID */ break;
        }
    }
}
```

Assembler, same idea (exec calls, A2 keeps the port):

```asm
        include "exec/types.i"
        include "intuition/intuition.i"
        include "lvo/exec_lib.i"

        move.l  window,a0
        move.l  wd_UserPort(a0),a2      ; a2 = UserPort (survives calls)
        move.l  4.w,a6
.wait   move.l  a2,a0
        jsr     _LVOWaitPort(a6)
.next   move.l  a2,a0
        jsr     _LVOGetMsg(a6)
        tst.l   d0
        beq.s   .wait                   ; port empty -> sleep again
        move.l  d0,a1
        move.l  im_Class(a1),d2         ; copy before replying
        move.w  im_Code(a1),d3
        jsr     _LVOReplyMsg(a6)        ; a1 = message
        cmp.l   #IDCMP_CLOSEWINDOW,d2
        bne.s   .next
        ; fall through: close gadget clicked
```

IDCMP classes you normally need (values from intuition.h):

| Class | Value | When / what you get |
|---|---|---|
| `IDCMP_CLOSEWINDOW` | $00000200 | close gadget clicked (needs `WA_CloseGadget`) |
| `IDCMP_VANILLAKEY` | $00200000 | key translated through the keymap; `Code` = character; no HELP/F-keys/cursor |
| `IDCMP_RAWKEY` | $00000400 | raw key code in `Code`, bit 7 set on key-up (`IECODE_UP_PREFIX`); with VANILLAKEY also set you get RAWKEY only for non-character downstrokes and no upstrokes |
| `IDCMP_MOUSEBUTTONS` | $00000008 | `Code` = `SELECTDOWN`/`SELECTUP`/`MENUDOWN`/`MENUUP`/`MIDDLEDOWN`/`MIDDLEUP`; clicks Intuition uses itself (gadgets) are not reported; MENU* only with `WFLG_RMBTRAP` |
| `IDCMP_MOUSEMOVE` | $00000010 | pointer moved; needs `WFLG_REPORTMOUSE` or a `GACT_FOLLOWMOUSE` gadget |
| `IDCMP_DELTAMOVE` | $00100000 | modifier: MOUSEMOVE `MouseX`/`MouseY` become deltas |
| `IDCMP_GADGETDOWN` / `IDCMP_GADGETUP` | $00000020 / $00000040 | `IAddress` = `struct Gadget *` (`GACT_IMMEDIATE` / `GACT_RELVERIFY`) |
| `IDCMP_MENUPICK` | $00000100 | `Code` = menu number (see [Menu numbers](menus.md#menu-numbers)) |
| `IDCMP_NEWSIZE` | $00000002 | user resized the window |
| `IDCMP_CHANGEWINDOW` | $02000000 | moved/sized (V36), depth with `WA_NotifyDepth` (V39: `Code` = `CWCODE_DEPTH`) |
| `IDCMP_REFRESHWINDOW` | $00000004 | damage to repair: [BeginRefresh](windows.md#beginrefresh)/[EndRefresh](windows.md#endrefresh) |
| `IDCMP_ACTIVEWINDOW` / `IDCMP_INACTIVEWINDOW` | $00040000 / $00080000 | activation changes |
| `IDCMP_INTUITICKS` | $00400000 | about 10 per second while active; never more than one queued |
| `IDCMP_IDCMPUPDATE` | $00800000 | BOOPSI notification (`ICA_TARGET` = `ICTARGET_IDCMP`); `IAddress` = tag list |
| `IDCMP_DISKINSERTED` / `IDCMP_DISKREMOVED` | $00008000 / $00010000 | removable media changes |

## IntuiMessage fields

| Field (C / asm) | Type | Meaning |
|---|---|---|
| `ExecMessage` | `struct Message` | exec header; `mn_ReplyPort` belongs to Intuition |
| `Class` / `im_Class` | ULONG | one `IDCMP_` bit |
| `Code` / `im_Code` | UWORD | class-specific: key code, `SELECTDOWN`, menu number, `CWCODE_`, ... |
| `Qualifier` / `im_Qualifier` | UWORD | copy of the input event qualifier (`IEQUALIFIER_` from devices/inputevent.h) |
| `IAddress` / `im_IAddress` | APTR | class-specific: Gadget for GADGETUP/DOWN, tag list for IDCMPUPDATE, ... |
| `MouseX`, `MouseY` / `im_MouseX`, `im_MouseY` | WORD | pointer position relative to the window's top-left corner (outer, even for GimmeZeroZero); deltas with DELTAMOVE |
| `Seconds`, `Micros` / `im_Seconds`, `im_Micros` | ULONG | event timestamp, for [DoubleClick](input-and-prefs.md#doubleclick) |
| `IDCMPWindow` / `im_IDCMPWindow` | `struct Window *` | window this message is for; needed with shared ports |
| `SpecialLink` | `struct IntuiMessage *` | system use |

V39: with `WA_TabletMessages` TRUE, messages are `struct ExtIntuiMessage` with `eim_TabletData`. Do not
read that field on older systems.

## Closing a window with a shared port

Several windows can share one port. Open each with no IDCMP (`WA_IDCMP, 0`), store your own
`struct MsgPort *` in `win->UserPort`, then call `ModifyIDCMP(win, flags)`. Intuition then creates
only its half. When closing such a window you must: (1) remove and reply every queued message for
that window, (2) clear `UserPort` so CloseWindow() does not free your port, (3) stop further
messages, all without Intuition posting in between.

```c
/* Close a window whose UserPort is shared with other windows. */
void CloseSharedWindow(struct Window *win)
{
    struct IntuiMessage *im, *next;

    Forbid();
    im = (struct IntuiMessage *)win->UserPort->mp_MsgList.lh_Head;
    while ((next = (struct IntuiMessage *)im->ExecMessage.mn_Node.ln_Succ) != NULL) {
        if (im->IDCMPWindow == win) {
            Remove((struct Node *)im);
            ReplyMsg((struct Message *)im);   /* next was fetched before the reply */
        }
        im = next;
    }
    win->UserPort = NULL;          /* Intuition must not free the shared port */
    ModifyIDCMP(win, 0);           /* no more messages for this window */
    Permit();

    CloseWindow(win);
}
```

Also, before CloseWindow(): [ClearMenuStrip](menus.md#clearmenustrip) if a menu is attached, restore
`pr_WindowPtr` if you pointed it at this window, and delete the shared port only after the last window
using it is closed.

## Window and Screen fields

Read-only for applications unless stated. Everything past the documented fields is private.

`struct Window` (intuition/intuition.h):

| Field | Type | asm | Use |
|---|---|---|---|
| `LeftEdge`, `TopEdge`, `Width`, `Height` | WORD | `wd_LeftEdge` ... | outer box on the screen |
| `MouseX`, `MouseY` | WORD | `wd_MouseX`, `wd_MouseY` | pointer relative to window |
| `MinWidth`, `MinHeight` / `MaxWidth`, `MaxHeight` | WORD / UWORD | `wd_MinWidth` ... | size limits ([WindowLimits](windows.md#windowlimits)) |
| `Flags` | ULONG | `wd_Flags` | `WFLG_` bits |
| `WScreen` | `struct Screen *` | `wd_WScreen` | screen the window is on |
| `RPort` | `struct RastPort *` | `wd_RPort` | draw here (graphics.library); clipped to the window layer |
| `BorderLeft`, `BorderTop`, `BorderRight`, `BorderBottom` | BYTE | `wd_BorderLeft` ... | border thickness; inner area starts at (`BorderLeft`, `BorderTop`) |
| `BorderRPort` | `struct RastPort *` | `wd_BorderRPort` | border layer of GimmeZeroZero windows |
| `FirstGadget`, `MenuStrip` | pointers | `wd_FirstGadget`, `wd_MenuStrip` | attached gadgets / menus |
| `IDCMPFlags` | ULONG | `wd_IDCMPFlags` | current IDCMP classes |
| `UserPort` | `struct MsgPort *` | `wd_UserPort` | your IDCMP port |
| `GZZWidth`, `GZZHeight` | WORD | `wd_GZZWidth`, `wd_GZZHeight` | inner size of GimmeZeroZero windows |
| `GZZMouseX`, `GZZMouseY` | WORD | `wd_GZZMouseX` ... | pointer relative to the GZZ inner area |
| `UserData` | `BYTE *` | `wd_UserData` | free for the application |
| `WLayer` | `struct Layer *` | `wd_WLayer` | the window's layer |
| `IFont` | `struct TextFont *` | `wd_IFont` | font Intuition opened for `RPort` |

Inner size of a normal window: `Width - BorderLeft - BorderRight` by `Height - BorderTop - BorderBottom`.
Draw at `(win->BorderLeft + x, win->BorderTop + y)` unless the window is GimmeZeroZero (then `RPort`
already starts at the inner corner) or borderless.

`struct Screen` (intuition/screens.h):

| Field | Type | asm | Use |
|---|---|---|---|
| `Width`, `Height` | WORD | `sc_Width`, `sc_Height` | screen size in its own pixels |
| `LeftEdge`, `TopEdge` | WORD | `sc_LeftEdge`, `sc_TopEdge` | position (negative for scrolled oversized screens) |
| `MouseX`, `MouseY` | WORD | `sc_MouseX`, `sc_MouseY` | pointer relative to screen |
| `Flags` | UWORD | `sc_Flags` | `SCREENTYPE` bits (`WBENCHSCREEN`, `PUBLICSCREEN`, `CUSTOMSCREEN`), `SHOWTITLE`, `CUSTOMBITMAP`, ... |
| `Title`, `DefaultTitle` | `UBYTE *` | `sc_Title` ... | current / default title |
| `BarHeight` | BYTE | `sc_BarHeight` | screen title bar height **minus one** |
| `WBorTop`, `WBorLeft`, `WBorRight`, `WBorBottom` | BYTE | `sc_WBorTop` ... | default window border sizes; a window title bar is `WBorTop` + font height + 1 |
| `Font` | `struct TextAttr *` | `sc_Font` | screen font (open it with OpenFont() before using it) |
| `ViewPort` | `struct ViewPort` (embedded) | `sc_ViewPort` | `&scr->ViewPort` for LoadRGB4/LoadRGB32/SetRGB4/GetVPModeID |
| `RastPort` | `struct RastPort` (embedded) | `sc_RastPort` | `&scr->RastPort` draws on the whole screen, no layer clipping |
| `BitMap` | `struct BitMap` (embedded) | `sc_BitMap` | legacy: use `scr->RastPort.BitMap` instead |
| `LayerInfo` | `struct Layer_Info` (embedded) | `sc_LayerInfo` | for LockLayerInfo() |
| `FirstWindow` | `struct Window *` | `sc_FirstWindow` | window list; walk it only under [LockIBase](screens.md#lockibase) |
| `UserData` | `UBYTE *` | `sc_UserData` | free for the screen's owner |

Typical visitor-window placement below the screen title: `WA_Top, scr->BarHeight + 1`.

`struct IntuitionBase` (intuition/intuitionbase.h) exposes `ViewLord`, `ActiveWindow`, `ActiveScreen`,
`FirstScreen`, `MouseX`/`MouseY`, `Seconds`/`Micros`. Read them only between LockIBase() and UnlockIBase(),
and treat the rest of the structure as private.

## Tag-based opening

V36+ functions take a `struct TagItem` array (utility/tagitem.h): pairs of `ti_Tag` (ULONG ID) and
`ti_Data` (ULONG value or pointer), ended by `TAG_DONE` (= `TAG_END` = 0). Screen tags are
`SA_Dummy + n` with `SA_Dummy = TAG_USER + 32`. Window tags are `WA_Dummy + n` with
`WA_Dummy = TAG_USER + 99` ($80000063). Unknown tags are skipped, so V39 tags are harmless on V37.

Most used `SA_` tags ([full table](screens.md#openscreentaglist)):

| Tag | ti_Data |
|---|---|
| `SA_Width`, `SA_Height`, `SA_Left`, `SA_Top` | WORD values; `STDSCREENWIDTH`/`STDSCREENHEIGHT` (-1) = display clip size |
| `SA_Depth` | number of bitplanes (default 1) |
| `SA_DisplayID` | ULONG mode ID from graphics/modeid.h |
| `SA_Title` | `UBYTE *` |
| `SA_Type` | `CUSTOMSCREEN` or `PUBLICSCREEN` |
| `SA_ShowTitle`, `SA_Quiet`, `SA_Behind`, `SA_Draggable`, `SA_Exclusive`, `SA_Interleaved`, `SA_LikeWorkbench` | BOOL |
| `SA_Overscan` | `OSCAN_TEXT` (1), `OSCAN_STANDARD` (2), `OSCAN_MAX` (3), `OSCAN_VIDEO` (4) |
| `SA_Pens` | `UWORD *` ~0-terminated DrawInfo pens (any non-NULL value gives the 3D look) |
| `SA_Colors32` | `ULONG *` LoadRGB32 table (V39) |
| `SA_ErrorCode` | `ULONG *` receives an `OSERR_` code on failure |
| `SA_PubName` | `UBYTE *` public screen name |

Most used `WA_` tags ([full table](windows.md#openwindowtaglist)):

| Tag | ti_Data |
|---|---|
| `WA_Left`, `WA_Top`, `WA_Width`, `WA_Height` | outer box |
| `WA_InnerWidth`, `WA_InnerHeight` | inner size; borders are added for you |
| `WA_Title`, `WA_ScreenTitle` | `UBYTE *` |
| `WA_IDCMP` | ULONG `IDCMP_` flags |
| `WA_Flags` | ULONG `WFLG_` flags in one go |
| `WA_CloseGadget`, `WA_DragBar`, `WA_DepthGadget`, `WA_SizeGadget` | BOOL system gadgets |
| `WA_Activate`, `WA_Borderless`, `WA_Backdrop`, `WA_RMBTrap`, `WA_ReportMouse`, `WA_GimmeZeroZero` | BOOL |
| `WA_SimpleRefresh`, `WA_SmartRefresh` | BOOL (only pass TRUE); `WA_NoCareRefresh` BOOL |
| `WA_CustomScreen` | `struct Screen *` (your own screen) |
| `WA_PubScreen` / `WA_PubScreenName` | `struct Screen *` / `UBYTE *` (visitor window) |
| `WA_AutoAdjust` | BOOL, move/shrink to fit (default TRUE when no NewWindow is passed) |

Static tag lists work fine and are the only option from assembler:

```asm
wintags:
        dc.l    WA_InnerWidth,320
        dc.l    WA_InnerHeight,200
        dc.l    WA_Title,wintitle
        dc.l    WA_IDCMP,IDCMP_CLOSEWINDOW
        dc.l    WA_CloseGadget,1
        dc.l    WA_DragBar,1
        dc.l    WA_Activate,1
        dc.l    TAG_DONE
```

## Public screens

A public screen is a named screen that other programs may open "visitor" windows on. "Workbench"
is always one. The *default public screen* (usually Workbench) is used when you pass a NULL name.

- To open on one: [LockPubScreen](screens.md#lockpubscreen) (name or NULL) returns the screen and keeps
  it from closing. Read what you need for layout (`Font`, `BarHeight`, `WBorTop`, `Width`, the DrawInfo
  from [GetScreenDrawInfo](screens.md#getscreendrawinfo)). Open the window with `WA_PubScreen, scr`,
  then [UnlockPubScreen](screens.md#unlockpubscreen)`(NULL, scr)`. The open window now keeps the screen
  alive until CloseWindow().
- Alternatively pass `WA_PubScreenName` (plus `WA_PubScreenFallBack, TRUE` to fall back to the default
  screen) and skip the lock, if you need no screen data beforehand.
- Forbid() is **not** a substitute for the lock.
- To create one: open a screen with `SA_PubName`. It starts private; call
  [PubScreenStatus](screens.md#pubscreenstatus)`(scr, 0)` to make it public. `SA_PubTask`/`SA_PubSig`
  signal you when the last visitor leaves. CloseScreen() fails while visitors or locks remain.
- Names are at most `MAXPUBSCREENNAME` (139) characters. [LockPubScreenList](screens.md#lockpubscreenlist)
  is for screen-manager utilities only.
- Service windows for a client window (your own requesters) should open on `client->WScreen` with
  `WA_CustomScreen`, not as visitors, so they also work on private screens.

## Varargs stubs and inline macros

Tag-list functions have a varargs twin that builds the array on the stack:

| Library call | Varargs form |
|---|---|
| OpenWindowTagList | OpenWindowTags |
| OpenScreenTagList | OpenScreenTags |
| NewObjectA | NewObject |
| SetAttrsA | SetAttrs |
| SetGadgetAttrsA | SetGadgetAttrs |
| DoGadgetMethodA | DoGadgetMethod |
| SetWindowPointerA | SetWindowPointer |
| EasyRequestArgs | EasyRequest |
| BuildEasyRequestArgs | BuildEasyRequest |

Classic compilers get these as stubs from amiga.lib. With Bartman's m68k-amiga-elf-gcc and
`#include <proto/intuition.h>` they are macros in `inline/intuition.h`. Each argument is stored as a
32-bit ULONG, so pointers need a `(ULONG)` cast, and `EasyRequest` format strings need `%ld` for integers.
Defining `NO_INLINE_STDARG` (tag macros) or `NO_INLINE_VARARGS` (EasyRequest/BuildEasyRequest)
removes them. From assembler, build the array yourself and call the library function.

## Complete example: window on Workbench

Opens a window on the default public screen, draws a line of text inside the borders, waits for the
close gadget or Esc, and cleans up in reverse order. Fits Bartman's toolchain, where the program
declares its own library bases.

```c
#include <exec/types.h>
#include <exec/execbase.h>
#include <intuition/intuition.h>
#include <intuition/intuitionbase.h>
#include <graphics/gfxbase.h>
#include <dos/dos.h>
#include <proto/exec.h>
#include <proto/intuition.h>
#include <proto/graphics.h>

struct ExecBase      *SysBase;
struct IntuitionBase *IntuitionBase;
struct GfxBase       *GfxBase;

int main(void)
{
    struct Screen *scr;
    struct Window *win = NULL;
    int rc = 20;

    SysBase = *((struct ExecBase **)4UL);
    IntuitionBase = (struct IntuitionBase *)OpenLibrary((CONST_STRPTR)"intuition.library", 37);
    GfxBase = (struct GfxBase *)OpenLibrary((CONST_STRPTR)"graphics.library", 37);
    if (!IntuitionBase || !GfxBase)
        goto done;

    scr = LockPubScreen(NULL);                    /* default public screen */
    if (scr) {
        win = OpenWindowTags(NULL,
            WA_PubScreen,    (ULONG)scr,
            WA_Left,         40,
            WA_Top,          scr->BarHeight + 1,  /* just below the screen title */
            WA_InnerWidth,   320,
            WA_InnerHeight,  100,
            WA_Title,        (ULONG)"Hello Intuition",
            WA_DragBar,      TRUE,
            WA_DepthGadget,  TRUE,
            WA_CloseGadget,  TRUE,
            WA_Activate,     TRUE,
            WA_SmartRefresh, TRUE,
            WA_NoCareRefresh, TRUE,
            WA_AutoAdjust,   TRUE,
            WA_IDCMP,        IDCMP_CLOSEWINDOW | IDCMP_VANILLAKEY,
            TAG_DONE);
        UnlockPubScreen(NULL, scr);               /* the open window keeps the screen alive */
    }
    if (!win)
        goto done;

    {
        struct RastPort *rp = win->RPort;
        SetAPen(rp, 1);
        Move(rp, win->BorderLeft + 8, win->BorderTop + 8 + rp->TxBaseline);
        Text(rp, (CONST_STRPTR)"Press Esc or close me.", 22);
    }

    {
        BOOL done = FALSE;
        while (!done) {
            struct IntuiMessage *im;
            WaitPort(win->UserPort);
            while ((im = (struct IntuiMessage *)GetMsg(win->UserPort)) != NULL) {
                ULONG class = im->Class;
                UWORD code  = im->Code;
                ReplyMsg((struct Message *)im);
                if (class == IDCMP_CLOSEWINDOW ||
                    (class == IDCMP_VANILLAKEY && code == 27))
                    done = TRUE;
            }
        }
    }
    rc = 0;

done:
    if (win)           CloseWindow(win);
    if (GfxBase)       CloseLibrary((struct Library *)GfxBase);
    if (IntuitionBase) CloseLibrary((struct Library *)IntuitionBase);
    return rc;
}
```

Started from Workbench rather than the Shell, a program must also receive and reply the Workbench
startup message (`struct WBStartup`, workbench/startup.h) unless its startup code already does.

## Common mistakes

- Using an IntuiMessage after ReplyMsg(), or keeping pointers into it.
- Processing only one message per Wait(): drain the port with a GetMsg() loop.
- Forgetting the `(ULONG)` casts in `OpenWindowTags`/`NewObject` varargs macros, or `%d` instead of
  `%ld` in EasyRequest formats.
- Closing a window that still has a menu strip ([ClearMenuStrip](menus.md#clearmenustrip) first), or
  whose shared UserPort still holds its messages ([see above](#closing-a-window-with-a-shared-port)).
- Drawing at (0,0) of `win->RPort` on a bordered, non-GimmeZeroZero window: that is the border.
- Keeping a screen pointer from LockPubScreen() after UnlockPubScreen() without a window open on it.
- Closing a screen while windows, locks, ScreenBuffers or DrawInfos are outstanding. CloseScreen()
  returns FALSE when windows or locks remain (V36+).
- Calling dos.library (or anything that can put up a requester) with `IDCMP_SIZEVERIFY`/`REQVERIFY`/
  `MENUVERIFY` enabled: deadlock.
- Using `&scr->BitMap` instead of `scr->RastPort.BitMap`, or assuming `&scr->RastPort` clips like a
  window RastPort (it has no layer: stay inside the screen bounds).
- Opening intuition.library with version 0 and then calling V36+ functions (tags, public screens,
  EasyRequest). Ask for at least 37 (Kickstart 2.04) or check the version.
