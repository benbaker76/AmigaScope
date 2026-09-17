# intuition.library

Intuition is the AmigaOS windowing and user-interface layer: screens, windows, IDCMP input messages,
gadgets, menus, requesters, alerts and the BOOPSI object system. Games and demos that bang the
hardware usually need only a little of it: a custom screen or no screen at all, EasyRequest for
errors, and possibly a borderless backdrop window for input. OS-friendly tools use all of it.

## Opening the library

- Name `"intuition.library"`, base variable **`IntuitionBase`** (`struct IntuitionBase *`,
  `<intuition/intuitionbase.h>`). With Bartman's gcc, `<proto/intuition.h>` declares
  `extern struct IntuitionBase *IntuitionBase;` and your program defines and opens it.
- Ask for version **37** (Kickstart 2.04) if you use tags, public screens or EasyRequest; 39 for
  V39 features (ScreenBuffers, attached screens, pointer objects, gadget help). Version 0 accepts
  a 1.x ROM. Always CloseLibrary() on exit.

```c
struct IntuitionBase *IntuitionBase;
...
IntuitionBase = (struct IntuitionBase *)OpenLibrary((CONST_STRPTR)"intuition.library", 37);
if (!IntuitionBase) { /* needs Kickstart 2.04+ */ }
...
CloseLibrary((struct Library *)IntuitionBase);
```

```asm
        include "exec/types.i"
        include "intuition/intuition.i"
        include "lvo/exec_lib.i"
        include "lvo/intuition_lib.i"

        move.l  4.w,a6
        lea     intname(pc),a1
        moveq   #37,d0
        jsr     _LVOOpenLibrary(a6)
        move.l  d0,IntuitionBase
        beq     .nointuition
        ...
intname dc.b    "intuition.library",0
        even
```

## Calling convention

- A6 = IntuitionBase; `jsr _LVOname(a6)`. Arguments go in the registers shown in each entry's
  `Registers:` line, result in D0. D0, D1, A0 and A1 are scratch after every call; all other
  registers are preserved.
- Register quirks to watch in assembler: [UnlockIBase](screens.md#unlockibase) takes its lock in
  **A0**; [QueryOverscan](screens.md#queryoverscan) takes the ULONG display ID in **A0**;
  [ScrollWindowRaster](windows.md#scrollwindowraster) takes the window in **A1**;
  [TimedDisplayAlert](requesters-and-alerts.md#timeddisplayalert) takes the time in **A1**;
  [PointInImage](drawing.md#pointinimage) takes X/Y packed into D0 (X high word);
  [BuildEasyRequestArgs](requesters-and-alerts.md#buildeasyrequestargs) takes args in A3 and leaves A2 unused;
  [ReportMouse](windows.md#reportmouse) is flag=D0, window=A0 (some C stubs swap the arguments).
- Call Intuition from a task or process, never from an interrupt: many functions allocate memory,
  lock layers or wait for Intuition's input handler.
- Tag-list calls (`...TagList`, `...A`, `...Args`) have varargs twins (`OpenWindowTags`, `NewObject`,
  `EasyRequest`, ...). They are amiga.lib stubs, or inline macros with the Bartman headers; see
  [varargs](concepts.md#varargs-stubs-and-inline-macros).

## Version landmarks

| Version | Kickstart | Added (in this reference) |
|---|---|---|
| V33 | 1.2 | AddGList, RemoveGList, RefreshGList, NewModifyProp, ActivateWindow, ActivateGadget, RefreshWindowFrame, GetScreenData |
| V36 | 2.0 | tag lists (OpenScreenTagList, OpenWindowTagList), public screens, EasyRequestArgs/BuildEasyRequestArgs/SysReqHandler, BOOPSI (NewObjectA, MakeClass, ...), DrawInfo, ChangeWindowBox, ZipWindow, QueryOverscan, CloseScreen returns BOOL |
| V37 | 2.04 | ModifyIDCMP returns BOOL, `WA_MenuHelp`/`IDCMP_MENUHELP`; the practical minimum for OS-friendly code |
| V39 | 3.0 | AllocScreenBuffer/ChangeScreenBuffer (double buffering), ScreenDepth, ScreenPosition, attached screens, SetWindowPointerA + pointerclass, HelpControl/gadget help, LendMenus, ScrollWindowRaster, DoGadgetMethodA, TimedDisplayAlert, new-look menus; MakeScreen/RethinkDisplay/RemakeDisplay return an error code |
| V40 | 3.1 | `SA_MinimizeISG`, exclusive attached screen families, FreeScreenBuffer does its own WaitBlit |
| V44/V45 | 3.5/3.9 | no new public LVOs in the NDK 3.9 prototypes |

## Files

- [concepts.md](concepts.md) — IDCMP loop, IntuiMessage fields, shared-port window closing, Window/Screen fields, tag lists, public screens, varargs, a complete window example, common mistakes.
- [screens.md](screens.md) — open/close screens, public screens and locks, Workbench control, depth and position, DrawInfo, overscan, display rebuild, double buffering, LockIBase.
- [windows.md](windows.md) — open/close windows (WA_ tags, WFLG_ flags), IDCMP classes, moving/sizing/depth, titles, refresh, scrolling, pointers, mouse reporting, gadget help.
- [menus.md](menus.md) — menu numbers, attaching/detaching strips, enabling items, ItemAddress, LendMenus.
- [gadgets.md](gadgets.md) — adding/removing/refreshing gadgets, enable/disable, proportional gadgets, BOOPSI gadget attributes and methods.
- [boopsi.md](boopsi.md) — creating and disposing objects, attributes, classes, custom gadget rendering helpers.
- [drawing.md](drawing.md) — Border, Image and IntuiText rendering and measurement.
- [requesters-and-alerts.md](requesters-and-alerts.md) — EasyRequest, system requesters, custom requesters, DMRequests, alerts, DisplayBeep.
- [input-and-prefs.md](input-and-prefs.md) — CurrentTime, DoubleClick, Preferences, global edit hook, AllocRemember, internal entries.

Fonts on disk (FONTS:) are opened with diskfont.library: see [diskfont](../diskfont/index.md).

<!-- FUNCTION TABLE -->
<!-- Generated by tools/skills/build_indexes.py - do not edit by hand. -->

## Functions

| Function | LVO | Registers | Summary |
|---|---|---|---|
| [ActivateGadget](gadgets.md#activategadget) | -462 | gadgets=A0, window=A1, requester=A2 | Make a string or custom gadget active so the user can type without clicking it first. |
| [ActivateWindow](windows.md#activatewindow) | -450 | window=A0 | Ask Intuition to make a window the active (input-receiving) window. |
| [AddClass](boopsi.md#addclass) | -684 | classPtr=A0 | Make a class created with a public name visible to NewObjectA by ID. |
| [AddGadget](gadgets.md#addgadget) | -42 | window=A0, gadget=A1, position=D0 | Link one gadget into a window's gadget list at a given position, without drawing it. |
| [AddGList](gadgets.md#addglist) | -438 | window=A0, gadget=A1, position=D0, numGad=D1, requester=A2 | Link a chain of gadgets into a window or requester gadget list in one call. |
| [AllocRemember](input-and-prefs.md#allocremember) | -396 | rememberKey=A0, size=D0, flags=D1 | AllocMem() that also records the block in a Remember list so it can be freed in one call. |
| [AllocScreenBuffer](screens.md#allocscreenbuffer) | -768 | sc=A0, bm=A1, flags=D0 | Allocate a ScreenBuffer (and normally a BitMap) for double buffering a screen. |
| [AutoRequest](requesters-and-alerts.md#autorequest) | -348 | window=A0, body=A1, posText=A2, negText=A3, pFlag=D0, nFlag=D1, width=D2, height=D3 | Old-style two-choice requester built from IntuiText; blocks until answered. |
| [BeginRefresh](windows.md#beginrefresh) | -354 | window=A0 | Enter the refresh state so rendering is clipped to the window's damaged regions only. |
| [BuildEasyRequestArgs](requesters-and-alerts.md#buildeasyrequestargs) (alias: BuildEasyRequest) | -594 | window=A0, easyStruct=A1, idcmp=D0, args=A3 | Open an EasyRequest-style requester and return its window without waiting for the user. |
| [BuildSysRequest](requesters-and-alerts.md#buildsysrequest) | -360 | window=A0, body=A1, posText=A2, negText=A3, flags=D0, width=D1, height=D2 | Build an AutoRequest-style requester and return its window for your own event handling. |
| [ChangeScreenBuffer](screens.md#changescreenbuffer) | -780 | sc=A0, sb=A1 | Install a ScreenBuffer's BitMap as the screen's displayed bitmap. |
| [ChangeWindowBox](windows.md#changewindowbox) | -486 | window=A0, left=D0, top=D1, width=D2, height=D3 | Ask Intuition to set a window's absolute position and size in one step. |
| [ClearDMRequest](requesters-and-alerts.md#cleardmrequest) | -48 | window=A0 | Detach the double-menu requester from a window unless the user has it open. |
| [ClearMenuStrip](menus.md#clearmenustrip) | -54 | window=A0 | Detach the menu strip from a window. |
| [ClearPointer](windows.md#clearpointer) | -60 | window=A0 | Remove a window's custom pointer so the default pointer is used again. |
| [CloseScreen](screens.md#closescreen) | -66 | screen=A0 | Close a screen and free everything Intuition allocated for it. |
| [CloseWindow](windows.md#closewindow) | -72 | window=A0 | Close a window, free its IDCMP messages and ports, and remove it from the screen. |
| [CloseWorkBench](screens.md#closeworkbench) | -78 | none | Try to close the Workbench screen (e.g. |
| [CurrentTime](input-and-prefs.md#currenttime) | -84 | seconds=A0, micros=A1 | Read Intuition's current time as seconds plus microseconds. |
| [DisplayAlert](requesters-and-alerts.md#displayalert) | -90 | alertNumber=D0, string=A0, height=D1 | Show a full-display alert message; recoverable alerts wait for a mouse button. |
| [DisplayBeep](requesters-and-alerts.md#displaybeep) | -96 | screen=A0 | Flash a screen's background colour as a visual "bell". |
| [DisposeObject](boopsi.md#disposeobject) | -642 | object=A0 | Delete a BOOPSI object and its auxiliary data by sending it `OM_DISPOSE`. |
| [DoGadgetMethodA](gadgets.md#dogadgetmethoda) (alias: DoGadgetMethod) | -810 | gad=A0, win=A1, req=A2, message=A3 | Invoke any method on a BOOPSI gadget with a GadgetInfo filled in from window/requester. |
| [DoubleClick](input-and-prefs.md#doubleclick) | -102 | sSeconds=D0, sMicros=D1, cSeconds=D2, cMicros=D3 | Test whether two timestamps are close enough to count as a double-click. |
| [DrawBorder](drawing.md#drawborder) | -108 | rp=A0, border=A1, leftOffset=D0, topOffset=D1 | Draw a Border (and every Border linked through NextBorder) into a RastPort. |
| [DrawImage](drawing.md#drawimage) | -114 | rp=A0, image=A1, leftOffset=D0, topOffset=D1 | Draw an Image (and every Image linked through NextImage) into a RastPort. |
| [DrawImageState](drawing.md#drawimagestate) | -618 | rp=A0, image=A1, leftOffset=D0, topOffset=D1, state=D2, drawInfo=A2 | Draw an image in a visual state (normal, selected, disabled...), mainly for BOOPSI images. |
| [EasyRequestArgs](requesters-and-alerts.md#easyrequestargs) (alias: EasyRequest) | -588 | window=A0, easyStruct=A1, idcmpPtr=A2, args=A3 | Show a font-sensitive system requester from printf-style strings; wait for the answer. |
| [EndRefresh](windows.md#endrefresh) | -366 | window=A0, complete=D0 | Leave the refresh state entered with BeginRefresh. |
| [EndRequest](requesters-and-alerts.md#endrequest) | -120 | requester=A0, window=A1 | Erase one requester and detach it from its window. |
| [EraseImage](drawing.md#eraseimage) | -630 | rp=A0, image=A1, leftOffset=D0, topOffset=D1 | Erase the area an image occupies, using the layer's backfill. |
| [FreeClass](boopsi.md#freeclass) | -714 | classPtr=A0 | Try to free a class made by MakeClass (class implementors only). |
| [FreeRemember](input-and-prefs.md#freeremember) | -408 | rememberKey=A0, reallyForget=D0 | Free a Remember list: either the nodes and all the blocks, or only the nodes. |
| [FreeScreenBuffer](screens.md#freescreenbuffer) | -774 | sc=A0, sb=A1 | Free a ScreenBuffer (and the BitMap Intuition allocated for it). |
| [FreeScreenDrawInfo](screens.md#freescreendrawinfo) | -696 | screen=A0, drawInfo=A1 | Release a DrawInfo obtained with GetScreenDrawInfo. |
| [FreeSysRequest](requesters-and-alerts.md#freesysrequest) | -372 | window=A0 | Close and free a requester window made by BuildSysRequest or BuildEasyRequestArgs. |
| [GadgetMouse](boopsi.md#gadgetmouse) | -570 | gadget=A0, gInfo=A1, mousePoint=A2 | Obsolete: compute the mouse position relative to a custom gadget's top-left corner. |
| [GetAttr](boopsi.md#getattr) | -654 | attrID=D0, object=A0, storagePtr=A1 | Read one attribute of a BOOPSI object into a longword you supply (`OM_GET`). |
| [GetDefaultPubScreen](screens.md#getdefaultpubscreen) | -582 | nameBuffer=A0 | Copy the name of the current default public screen into a buffer. |
| [GetDefPrefs](input-and-prefs.md#getdefprefs) | -126 | preferences=A0, size=D0 | Copy Intuition's built-in default Preferences (used when no preferences file exists). |
| [GetPrefs](input-and-prefs.md#getprefs) | -132 | preferences=A0, size=D0 | Copy the current Intuition Preferences structure (or its first part) into your buffer. |
| [GetScreenData](screens.md#getscreendata) | -426 | buffer=A0, size=D0, type=D1, screen=A1 | Copy (part of) a Screen structure, e.g. |
| [GetScreenDrawInfo](screens.md#getscreendrawinfo) | -690 | screen=A0 | Get the read-only DrawInfo (pens, font, depth, resolution) of an open screen. |
| [HelpControl](windows.md#helpcontrol) | -828 | win=A0, flags=D0 | Turn gadget help on or off for a window and all windows in its help group. |
| [InitRequester](requesters-and-alerts.md#initrequester) | -138 | requester=A0 | Clear a Requester structure to zero before you fill in your own fields. |
| [IntuiTextLength](drawing.md#intuitextlength) | -330 | iText=A0 | Return the pixel width of an IntuiText's string (the first IntuiText only). |
| [Intuition](input-and-prefs.md#intuition) | -36 | iEvent=A0 | Internal Intuition entry that takes an InputEvent pointer; never call it. |
| [ItemAddress](menus.md#itemaddress) | -144 | menuStrip=A0, menuNumber=D0 | Return the MenuItem (or sub-item) addressed by a packed menu number. |
| [LendMenus](menus.md#lendmenus) | -804 | fromwindow=A0, towindow=A1 | Make menu button presses in one window show another window's menu strip. |
| [LockIBase](screens.md#lockibase) | -414 | dontknow=D0 | Take Intuition's internal lock to read IntuitionBase and screen/window lists safely. |
| [LockPubScreen](screens.md#lockpubscreen) | -510 | name=A0 | Find a public screen by name and stop it closing while you inspect it. |
| [LockPubScreenList](screens.md#lockpubscreenlist) | -522 | none | Lock and return the system list of public screens (for screen-manager tools). |
| [MakeClass](boopsi.md#makeclass) | -678 | classID=A0, superClassID=A1, superClassPtr=A2, instanceSize=D0, flags=D1 | Create a public or private BOOPSI class (class implementors only). |
| [MakeScreen](screens.md#makescreen) | -378 | screen=A0 | Rebuild the copper list of your custom screen's ViewPort in an Intuition-safe way. |
| [ModifyIDCMP](windows.md#modifyidcmp) | -150 | window=A0, flags=D0 | Change which IDCMP classes a window receives, creating or deleting its message ports. |
| [ModifyProp](gadgets.md#modifyprop) | -156 | gadget=A0, window=A1, requester=A2, flags=D0, horizPot=D1, vertPot=D2, horizBody=D3, vertBody=D4 | Set a proportional gadget's PropInfo values and redraw it (and every gadget after it). |
| [MoveScreen](screens.md#movescreen) | -162 | screen=A0, dx=D0, dy=D1 | Move a screen by a delta in screen pixels (clipped to what is allowed). |
| [MoveWindow](windows.md#movewindow) | -168 | window=A0, dx=D0, dy=D1 | Ask Intuition to move a window by a relative amount. |
| [MoveWindowInFrontOf](windows.md#movewindowinfrontof) | -480 | window=A0, behindWindow=A1 | Depth-arrange a window directly in front of another window. |
| [NewModifyProp](gadgets.md#newmodifyprop) | -468 | gadget=A0, window=A1, requester=A2, flags=D0, horizPot=D1, vertPot=D2, horizBody=D3, vertBody=D4, numGad=D5 | Same as ModifyProp, but redraws only numGad gadgets; with 1 it moves the knob smoothly. |
| [NewObjectA](boopsi.md#newobjecta) (alias: NewObject) | -636 | classPtr=A0, classID=A1, tagList=A2 | Create a BOOPSI object from a class pointer or a public class ID, with initial attributes. |
| [NextObject](boopsi.md#nextobject) | -666 | objectPtrPtr=A0 | Walk the objects gathered on an Exec list with `OM_ADDMEMBER` (class implementors only). |
| [NextPubScreen](screens.md#nextpubscreen) | -534 | screen=A0, namebuf=A1 | Get the name of the next public screen in the system cycle (for "jump screen" features). |
| [ObtainGIRPort](boopsi.md#obtaingirport) | -558 | gInfo=A0 | Get a RastPort for rendering from inside a custom gadget method (class implementors only). |
| [OffGadget](gadgets.md#offgadget) | -174 | gadget=A0, window=A1, requester=A2 | Disable a gadget: set `GFLG_DISABLED`, ghost its imagery and block selection. |
| [OffMenu](menus.md#offmenu) | -180 | window=A0, menuNumber=D0 | Disable (ghost) a whole menu, an item, or a sub-item. |
| [OnGadget](gadgets.md#ongadget) | -186 | gadget=A0, window=A1, requester=A2 | Enable a gadget: clear `GFLG_DISABLED`, remove the ghosting and allow selection. |
| [OnMenu](menus.md#onmenu) | -192 | window=A0, menuNumber=D0 | Enable a whole menu, an item, or a sub-item. |
| [OpenIntuition](input-and-prefs.md#openintuition) | -30 | none | Internal Intuition initialisation vector; never call it. |
| [OpenScreen](screens.md#openscreen) | -198 | newScreen=A0 | Open a screen from a NewScreen (or ExtNewScreen) structure; the pre-V36 entry point. |
| [OpenScreenTagList](screens.md#openscreentaglist) (alias: OpenScreenTags) | -612 | newScreen=A0, tagList=A1 | Open a screen described by an optional NewScreen plus a tag list (the V36+ way). |
| [OpenWindow](windows.md#openwindow) | -204 | newWindow=A0 | Open a window from a NewWindow structure (pre-V36 interface). |
| [OpenWindowTagList](windows.md#openwindowtaglist) (alias: OpenWindowTags) | -606 | newWindow=A0, tagList=A1 | Open a window described by an optional NewWindow plus a `WA_` tag list. |
| [OpenWorkBench](screens.md#openworkbench) | -210 | none | Open the Workbench screen if it is not already open. |
| [PointInImage](drawing.md#pointinimage) | -624 | point=D0, image=A0 | Test whether a point lies inside an image (its box, or a class-defined shape). |
| [PrintIText](drawing.md#printitext) | -216 | rp=A0, iText=A1, left=D0, top=D1 | Render an IntuiText chain into a RastPort at an offset. |
| [PubScreenStatus](screens.md#pubscreenstatus) | -552 | screen=A0, statusFlags=D0 | Switch a public screen you own between private and public state. |
| [QueryOverscan](screens.md#queryoverscan) | -474 | displayID=A0, rect=A1, oScanType=D0 | Fill a Rectangle with a standard overscan region for a display mode. |
| [RefreshGadgets](gadgets.md#refreshgadgets) | -222 | gadgets=A0, window=A1, requester=A2 | Redraw every gadget from the given one to the end of its list. |
| [RefreshGList](gadgets.md#refreshglist) | -432 | gadgets=A0, window=A1, requester=A2, numGad=D0 | Redraw up to numGad gadgets, starting with the given one. |
| [RefreshWindowFrame](windows.md#refreshwindowframe) | -456 | window=A0 | Redraw a window's border, title bar and gadgets. |
| [ReleaseGIRPort](boopsi.md#releasegirport) | -564 | rp=A0 | Release a RastPort obtained with ObtainGIRPort. |
| [RemakeDisplay](screens.md#remakedisplay) | -384 | none | Remake every screen's ViewPort and then rethink the whole display (the expensive one). |
| [RemoveClass](boopsi.md#removeclass) | -708 | classPtr=A0 | Take a public class off the public class list so that new objects cannot find it by name. |
| [RemoveGadget](gadgets.md#removegadget) | -228 | window=A0, gadget=A1 | Unlink one gadget from a window, or from a requester in that window. |
| [RemoveGList](gadgets.md#removeglist) | -444 | remPtr=A0, gadget=A1, numGad=D0 | Unlink a run of gadgets from a window or requester gadget list. |
| [ReportMouse](windows.md#reportmouse) (alias: ReportMouse1) | -234 | flag=D0, window=A0 | Turn mouse-movement reporting for a window on or off. |
| [Request](requesters-and-alerts.md#request) | -240 | requester=A0, window=A1 | Display a custom requester (`struct Requester`) inside a window. |
| [ResetMenuStrip](menus.md#resetmenustrip) | -702 | window=A0, menu=A1 | Re-attach a previously set, unchanged menu strip without recomputing its layout. |
| [RethinkDisplay](screens.md#rethinkdisplay) | -390 | none | Recompute the whole Intuition display (visibility, merge copper lists, load the View). |
| [ScreenDepth](screens.md#screendepth) | -786 | screen=A0, flags=D0, reserved=A1 | Depth-arrange a screen, optionally only within its attached-screen family. |
| [ScreenPosition](screens.md#screenposition) | -792 | screen=A0, flags=D0, x1=D1, y1=D2, x2=D3, y2=D4 | Move a screen relatively, absolutely, or so that a given rectangle becomes visible. |
| [ScreenToBack](screens.md#screentoback) | -246 | screen=A0 | Send a screen behind all other screens. |
| [ScreenToFront](screens.md#screentofront) | -252 | screen=A0 | Bring a screen to the front of the display. |
| [ScrollWindowRaster](windows.md#scrollwindowraster) | -798 | win=A1, dx=D0, dy=D1, xMin=D2, yMin=D3, xMax=D4, yMax=D5 | Scroll part of a window's contents and let Intuition handle the damage it exposes. |
| [SetAttrsA](boopsi.md#setattrsa) (alias: SetAttrs) | -648 | object=A0, tagList=A1 | Set attributes of a BOOPSI object with no window context (`OM_SET`, `NULL` GadgetInfo). |
| [SetDefaultPubScreen](screens.md#setdefaultpubscreen) | -540 | name=A0 | Make a named public screen the default target for visitor windows. |
| [SetDMRequest](requesters-and-alerts.md#setdmrequest) | -258 | window=A0, requester=A1 | Attach a double-menu requester that the user opens by double-clicking the menu button. |
| [SetEditHook](input-and-prefs.md#setedithook) | -492 | hook=A0 | Install a global edit hook that sees every keystroke typed into any string gadget. |
| [SetGadgetAttrsA](gadgets.md#setgadgetattrsa) (alias: SetGadgetAttrs) | -660 | gadget=A0, window=A1, requester=A2, tagList=A3 | Set attributes on a BOOPSI gadget that is (or may be) attached, with locking and redraw. |
| [SetMenuStrip](menus.md#setmenustrip) | -264 | window=A0, menu=A1 | Attach a menu strip to a window and precompute its layout. |
| [SetMouseQueue](windows.md#setmousequeue) | -498 | window=A0, queueLength=D0 | Set how many unreplied `IDCMP_MOUSEMOVE` messages a window may have queued. |
| [SetPointer](windows.md#setpointer) | -270 | window=A0, pointer=A1, height=D0, width=D1, xOffset=D2, yOffset=D3 | Give a window its own sprite-image mouse pointer (classic interface). |
| [SetPrefs](input-and-prefs.md#setprefs) | -324 | preferences=A0, size=D0, inform=D1 | Install new Intuition Preferences, optionally notifying windows with IDCMP_NEWPREFS. |
| [SetPubScreenModes](screens.md#setpubscreenmodes) | -546 | modes=D0 | Set global public screen behaviour flags. |
| [SetWindowPointerA](windows.md#setwindowpointera) (alias: SetWindowPointer) | -816 | win=A0, taglist=A1 | Set the mouse pointer shown while a window is active, by tags. |
| [SetWindowTitles](windows.md#setwindowtitles) | -276 | window=A0, windowTitle=A1, screenTitle=A2 | Change the window title and/or the screen title shown while the window is active. |
| [ShowTitle](screens.md#showtitle) | -282 | screen=A0, showIt=D0 | Choose whether the screen title bar shows in front of backdrop windows. |
| [SizeWindow](windows.md#sizewindow) | -288 | window=A0, dx=D0, dy=D1 | Ask Intuition to resize a window by a relative amount. |
| [SysReqHandler](requesters-and-alerts.md#sysreqhandler) | -600 | window=A0, idcmpPtr=A1, waitInput=D0 | Process pending input for a system requester window and report whether it was answered. |
| [TimedDisplayAlert](requesters-and-alerts.md#timeddisplayalert) | -822 | alertNumber=D0, string=A0, height=D1, time=A1 | DisplayAlert that removes itself after a given number of video frames. |
| [UnlockIBase](screens.md#unlockibase) | -420 | ibLock=A0 | Release the Intuition lock obtained with LockIBase. |
| [UnlockPubScreen](screens.md#unlockpubscreen) | -516 | name=A0, screen=A1 | Release a lock obtained with LockPubScreen. |
| [UnlockPubScreenList](screens.md#unlockpubscreenlist) | -528 | none | Release the public screen list lock taken by LockPubScreenList. |
| [ViewAddress](screens.md#viewaddress) | -294 | none | Return the address of Intuition's View structure (for graphics calls that need a View). |
| [ViewPortAddress](screens.md#viewportaddress) | -300 | window=A0 | Return the ViewPort of the screen a window is on. |
| [WBenchToBack](screens.md#wbenchtoback) | -336 | none | Send the Workbench screen behind all other screens (depth only, no vertical move). |
| [WBenchToFront](screens.md#wbenchtofront) | -342 | none | Bring the Workbench screen in front of all other screens (depth only, no vertical move). |
| [WindowLimits](windows.md#windowlimits) | -318 | window=A0, widthMin=D0, heightMin=D1, widthMax=D2, heightMax=D3 | Set the minimum and maximum size the user can size a window to. |
| [WindowToBack](windows.md#windowtoback) | -306 | window=A0 | Ask Intuition to move a window behind all other windows on its screen. |
| [WindowToFront](windows.md#windowtofront) | -312 | window=A0 | Ask Intuition to move a window in front of all other windows on its screen. |
| [ZipWindow](windows.md#zipwindow) | -504 | window=A0 | Toggle a window between its current and alternate ("zoomed") position and size. |

Machine-readable: [../data/intuition.tsv](../data/intuition.tsv)
