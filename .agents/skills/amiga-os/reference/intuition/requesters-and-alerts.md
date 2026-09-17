# intuition.library: requesters and alerts

Three generations of user queries live here. Use **EasyRequestArgs** (V36+) for message boxes:
it lays itself out for the screen font and returns the chosen gadget number. For a non-blocking
box, build it with **BuildEasyRequestArgs**, poll it with **SysReqHandler** and remove it with
**FreeSysRequest**. **AutoRequest**/**BuildSysRequest** are the 1.x IntuiText versions. **Request**
and the DMRequest calls put a hand-built `struct Requester` inside one of your windows. **DisplayAlert**
takes over the whole display and is only for real emergencies. **DisplayBeep** flashes a screen.

## EasyRequestArgs
`LONG EasyRequestArgs(struct Window *window, CONST struct EasyStruct *easyStruct, ULONG *idcmpPtr, CONST APTR args)` — LVO -588 (-$24C)
Registers: window=A0, easyStruct=A1, idcmpPtr=A2, args=A3; result in D0

Show a font-sensitive system requester from printf-style strings; wait for the answer.

- **window** — reference window: the requester opens on its screen and borrows its title. NULL =
  default public screen (normally Workbench).
- **easyStruct** — `struct EasyStruct`: `es_StructSize` = `sizeof(struct EasyStruct)`, `es_Flags` = 0,
  `es_Title` (NULL -> reference window title, else "System Request"), `es_TextFormat` (body, `\n`
  splits lines), `es_GadgetFormat` (gadget labels separated by `|`; at least one).
- **idcmpPtr** — NULL, or pointer to a ULONG of extra `IDCMP_` classes that also end the requester
  (e.g. `IDCMP_DISKINSERTED`). When one fires, the ULONG is overwritten with that single class.
- **args** — pointer to the argument array for the format strings: body arguments first, then
  gadget-label arguments.
- **Result** — gadget number: leftmost = 1, next = 2, ..., **rightmost = 0**; -1 = one of the extra
  IDCMP classes arrived.

The varargs form `EasyRequest(window, easyStruct, idcmpPtr, arg1, ...)` is an amiga.lib stub, or an
inline macro with the Bartman headers (see [varargs](concepts.md#varargs-stubs-and-inline-macros)).

Since V36.

### Example
```c
struct EasyStruct es = {
    sizeof(struct EasyStruct), 0,
    (UBYTE *)"Save",
    (UBYTE *)"File %s is %ld bytes.\nOverwrite it?",
    (UBYTE *)"Overwrite|Cancel"
};

LONG answer = EasyRequest(win, &es, NULL, (ULONG)name, size);
if (answer == 1) {
    /* "Overwrite" (leftmost); 0 = "Cancel" (rightmost) */
}
```

```asm
        include "exec/types.i"
        include "intuition/intuition.i"
        include "lvo/intuition_lib.i"

        move.l  IntuitionBase,a6
        sub.l   a0,a0                   ; no window: default public screen
        lea     easy(pc),a1
        sub.l   a2,a2                   ; no extra IDCMP classes
        lea     args(pc),a3
        jsr     _LVOEasyRequestArgs(a6)
        tst.l   d0                      ; 1 = Retry, 0 = Quit
        ...
easy:   dc.l    EasyStruct_SIZEOF,0,title,body,gads
args:   dc.l    3                       ; one %ld argument
title:  dc.b    "Demo",0
body:   dc.b    "Level %ld failed to load.",0
gads:   dc.b    "Retry|Quit",0
        even
```

### Gotchas
- Formatting is exec RawDoFmt: `%d`/`%x`/`%u` read a 16-bit WORD. Every argument packed by the
  varargs macro (or in an asm array of `dc.l`) is 32 bits, so write `%ld`/`%lx`/`%lu`. `%s` takes a
  32-bit pointer.
- The rightmost gadget is 0, not N. A single-gadget requester always returns 0 from its gadget.
- With no format arguments call `EasyRequestArgs(win, &es, NULL, NULL)`. The varargs macro wants at
  least one argument, and each pointer argument needs a `(ULONG)` cast.
- If you pass several classes in `*idcmpPtr`, reload the variable before calling again: it holds
  only the class that fired.
- It blocks your task and runs its own loop. Messages for your own windows queue up meanwhile.
- In asm the size label is `EasyStruct_SIZEOF` (it was renamed from `es_SIZEOF`, which clashes with
  graphics ExtSprite).
- DOS "insert volume" requesters use this. They open on the screen of the window in your Process
  `pr_WindowPtr`; `pr_WindowPtr = -1` suppresses them. Restore the old value before closing that window.
- Switches to a private stack, so it is safe with small task stacks. The `\n` character in
  `es_GadgetFormat` is reserved.

**See also:** [BuildEasyRequestArgs](#buildeasyrequestargs), [SysReqHandler](#sysreqhandler), [AutoRequest](#autorequest), exec.library RawDoFmt

## BuildEasyRequestArgs
`struct Window * BuildEasyRequestArgs(struct Window *window, CONST struct EasyStruct *easyStruct, ULONG idcmp, CONST APTR args)` — LVO -594 (-$252)
Registers: window=A0, easyStruct=A1, idcmp=D0, args=A3; result in D0

Open an EasyRequest-style requester and return its window without waiting for the user.

- **window**, **easyStruct**, **args** — as for [EasyRequestArgs](#easyrequestargs). `args` is in A3;
  A2 is unused.
- **idcmp** — the extra `IDCMP_` classes themselves (a value, not a pointer).
- **Result** — the requester window. If it could not be built you may instead get `0` (treat as the
  rightmost/Cancel gadget) or `1` (the leftmost gadget).

The varargs form is `BuildEasyRequest()`. Since V36.

### Gotchas
- Always pass the result, even 0 or 1, to [SysReqHandler](#sysreqhandler) and [FreeSysRequest](#freesysrequest).
  Both accept those values. Check `(ULONG)win > 1` before you touch `win->UserPort`.
- No fallback alert is shown on failure, despite older documentation.

**See also:** [SysReqHandler](#sysreqhandler), [FreeSysRequest](#freesysrequest), [EasyRequestArgs](#easyrequestargs)

## SysReqHandler
`LONG SysReqHandler(struct Window *window, ULONG *idcmpPtr, LONG waitInput)` — LVO -600 (-$258)
Registers: window=A0, idcmpPtr=A1, waitInput=D0; result in D0

Process pending input for a system requester window and report whether it was answered.

- **window** — result of [BuildEasyRequestArgs](#buildeasyrequestargs) or [BuildSysRequest](#buildsysrequest)
  (the values 0 and 1 are returned immediately).
- **idcmpPtr** — NULL, or pointer to a ULONG that receives the application IDCMP class when -1 is
  returned. Reload it before the next call if you watch several classes.
- **waitInput** — TRUE: WaitPort() if nothing is queued. FALSE: return at once.
- **Result** — gadget number (leftmost 1 ... rightmost 0), -1 = application IDCMP class, -2 = input did
  not satisfy the requester (or nothing pending with `waitInput` FALSE).

Since V36.

### Example
```c
/* Requester that stays up while the program keeps working */
struct Window *req = BuildEasyRequestArgs(win, &es, 0, NULL);
LONG r;
while ((r = SysReqHandler(req, NULL, FALSE)) == -2) {
    /* only reached for a real window (0/1 return at once) */
    Wait((1UL << req->UserPort->mp_SigBit) | mySignals);
    /* ... service mySignals here ... */
}
FreeSysRequest(req);
```

### Gotchas
- It never closes the requester. You still call [FreeSysRequest](#freesysrequest), even after a gadget was hit.

**See also:** [BuildEasyRequestArgs](#buildeasyrequestargs), [FreeSysRequest](#freesysrequest), exec.library WaitPort

## FreeSysRequest
`VOID FreeSysRequest(struct Window *window)` — LVO -372 (-$174)
Registers: window=A0; no result

Close and free a requester window made by BuildSysRequest or BuildEasyRequestArgs.

- **window** — the value the Build call returned. V36+: NULL or 1 are accepted and do nothing.

### Gotchas
- Never CloseWindow() such a window yourself. This call also frees the requester and its gadgets.

**See also:** [BuildSysRequest](#buildsysrequest), [BuildEasyRequestArgs](#buildeasyrequestargs), [SysReqHandler](#sysreqhandler)

## AutoRequest
`BOOL AutoRequest(struct Window *window, CONST struct IntuiText *body, CONST struct IntuiText *posText, CONST struct IntuiText *negText, ULONG pFlag, ULONG nFlag, ULONG width, ULONG height)` — LVO -348 (-$15C)
Registers: window=A0, body=A1, posText=A2, negText=A3, pFlag=D0, nFlag=D1, width=D2, height=D3; result in D0

Old-style two-choice requester built from IntuiText; blocks until answered.

- **window** — reference window. NULL = default public screen.
- **body** — `struct IntuiText` chain for the message.
- **posText** — IntuiText for the left (TRUE) gadget, or NULL for no positive choice.
- **negText** — IntuiText for the right (FALSE) gadget. **Must not be NULL.**
- **pFlag**, **nFlag** — `IDCMP_` classes that answer TRUE / FALSE (0 for none). They are OR-ed with
  `IDCMP_GADGETUP` and `IDCMP_RAWKEY` to form the requester IDCMP.
- **width**, **height** — requester size. Ignored from V36 (automatic layout).
- **Result** — TRUE (left gadget, pFlag class, Left-Amiga+V) or FALSE (right gadget, nFlag class,
  Left-Amiga+B, or failure).

`AUTOFRONTPEN` (0), `AUTOBACKPEN` (1), `AUTODRAWMODE` (JAM2), `AUTOLEFTEDGE` (6), `AUTOTOPEDGE` (3),
`AUTOITEXTFONT`/`AUTONEXTTEXT` (NULL) give suitable IntuiText defaults.

### Gotchas
- Prefer [EasyRequestArgs](#easyrequestargs) on V36+. Several IntuiText fields are ignored there so the
  requester matches the new look.
- V36+ no longer falls back to an alert when memory is short; it just returns FALSE.

**See also:** [EasyRequestArgs](#easyrequestargs), [BuildSysRequest](#buildsysrequest), [PrintIText](drawing.md#printitext)

## BuildSysRequest
`struct Window * BuildSysRequest(struct Window *window, CONST struct IntuiText *body, CONST struct IntuiText *posText, CONST struct IntuiText *negText, ULONG flags, ULONG width, ULONG height)` — LVO -360 (-$168)
Registers: window=A0, body=A1, posText=A2, negText=A3, flags=D0, width=D1, height=D2; result in D0

Build an AutoRequest-style requester and return its window for your own event handling.

- **window** — reference window (the requester window opens on its screen). NULL = default public screen.
- **body**, **posText**, **negText** — as for [AutoRequest](#autorequest). `negText` must be valid. The
  generated gadgets have `GadgetID` TRUE (left) and FALSE (right).
- **flags** — IDCMP classes for the requester window. `NOISYREQ` is set, so `IDCMP_RAWKEY`,
  `IDCMP_MOUSEBUTTONS` etc. are delivered.
- **width**, **height** — ignored from V36.
- **Result** — window pointer. If the requester could not be posted: FALSE (V36+), or TRUE/FALSE from
  the fallback alert on old versions.

### Gotchas
- Pops its screen to the front; V36+ pushes it back afterwards if the user did not rearrange screens.
- Handle it with [SysReqHandler](#sysreqhandler), free it with [FreeSysRequest](#freesysrequest).
- Linked IntuiText lists as gadget labels are not supported in V36+.

**See also:** [AutoRequest](#autorequest), [FreeSysRequest](#freesysrequest), [BuildEasyRequestArgs](#buildeasyrequestargs)

## InitRequester
`VOID InitRequester(struct Requester *requester)` — LVO -138 (-$8A)
Registers: requester=A0; no result

Clear a Requester structure to zero before you fill in your own fields.

- **requester** — the `struct Requester` to clear. Call this first, then set fields.

### Gotchas
- Old manuals filled the structure first and called this afterwards, which wipes your settings.
  Intuition cannot assume anyone calls it, so clearing the memory yourself is equivalent.

**See also:** [Request](#request)

## Request
`BOOL Request(struct Requester *requester, struct Window *window)` — LVO -240 (-$F0)
Registers: requester=A0, window=A1; result in D0

Display a custom requester (`struct Requester`) inside a window.

- **requester** — initialised requester: `LeftEdge`/`TopEdge`/`Width`/`Height`, `RelLeft`/`RelTop`,
  `ReqGadget` (gadgets must have `GTYP_REQGADGET` set; one with `GACT_ENDGADGET` ends it),
  `ReqBorder`, `ReqText`, `BackFill` pen, `Flags` (`POINTREL`, `PREDRAWN` + `ImageBMap`, `NOISYREQ`,
  `SIMPLEREQ`, `USEREQIMAGE` + `ReqImage`, `NOREQBACKFILL`).
- **window** — the window it appears in. `Window->ReqCount` counts the requesters blocking it.
- **Result** — TRUE if displayed.

V36+: with `POINTREL` on a normal (non-DMR) requester it is centred in the window, offset by
`RelLeft`/`RelTop`.

### Gotchas
- Ignores `IDCMP_REQVERIFY`. Use `IDCMP_REQSET`/`IDCMP_REQCLEAR` to track requesters.
- At most 8 requesters in a window that can be sized, moved or depth-arranged.
- Before V36 the return value is unreliable. A requester with an ENDGADGET may already be gone.
- For simple questions use [EasyRequestArgs](#easyrequestargs) instead.

**See also:** [EndRequest](#endrequest), [InitRequester](#initrequester), [SetDMRequest](#setdmrequest), [AddGList](gadgets.md#addglist)

## EndRequest
`VOID EndRequest(struct Requester *requester, struct Window *window)` — LVO -120 (-$78)
Registers: requester=A0, window=A1; no result

Erase one requester and detach it from its window.

- **requester** — the requester to remove. Other requesters in the window stay up.
- **window** — the window it was shown in.

**See also:** [Request](#request)

## SetDMRequest
`BOOL SetDMRequest(struct Window *window, struct Requester *requester)` — LVO -258 (-$102)
Registers: window=A0, requester=A1; result in D0

Attach a double-menu requester that the user opens by double-clicking the menu button.

- **window** — window to attach it to.
- **requester** — the requester. With `POINTREL` in its `Flags` it opens as near the pointer as possible,
  fine-tuned by `RelLeft`/`RelTop`.
- **Result** — TRUE if set. FALSE if the current DMRequest is in use (nothing changed).

### Gotchas
- To replace one, call [ClearDMRequest](#cleardmrequest) until it returns TRUE, then SetDMRequest.

**See also:** [ClearDMRequest](#cleardmrequest), [Request](#request)

## ClearDMRequest
`BOOL ClearDMRequest(struct Window *window)` — LVO -48 (-$30)
Registers: window=A0; result in D0

Detach the double-menu requester from a window unless the user has it open.

- **window** — the window.
- **Result** — TRUE if detached. FALSE if it is in use (nothing changed).

### Gotchas
- `IDCMP_REQCLEAR` arrives only when the *last* requester in the window goes away, so it is not a
  precise "DMR closed" signal.

**See also:** [SetDMRequest](#setdmrequest)

## DisplayAlert
`BOOL DisplayAlert(ULONG alertNumber, CONST_STRPTR string, ULONG height)` — LVO -90 (-$5A)
Registers: alertNumber=D0, string=A0, height=D1; result in D0

Show a full-display alert message; recoverable alerts wait for a mouse button.

- **alertNumber** — only the `ALERT_TYPE` bit (bit 31) matters: `RECOVERY_ALERT` ($00000000) waits for
  a button; `DEADEND_ALERT` ($80000000) returns at once. The other bits are ignored here (the system
  alert codes live in `exec/alerts.h`).
- **string** — one or more substrings, each: 16-bit X position, 8-bit Y position (text baseline), the
  NUL-terminated text, then a continuation byte (non-zero = another substring follows, 0 = last).
- **height** — alert height in display lines.
- **Result** — TRUE if the user pressed the left button on a recovery alert. FALSE for the right button,
  a dead-end alert, or when the alert could not be shown (e.g. no memory, V33+).

V36+: always Topaz 8. Recovery alerts are amber, dead-end alerts red. The alert has the display to itself on black.

### Example
```asm
        move.l  IntuitionBase,a6
        moveq   #RECOVERY_ALERT,d0
        lea     alertmsg(pc),a0
        moveq   #32,d1                  ; alert height in lines
        jsr     _LVODisplayAlert(a6)
        tst.l   d0                      ; TRUE = left button
        ...
alertmsg:
        dc.b    0,24                    ; X = 24 (word, big-endian)
        dc.b    14                      ; Y baseline
        dc.b    "Out of chip RAM. Left: retry   Right: quit",0
        dc.b    0                       ; last substring
        even
```

### Gotchas
- Write the X word as two `dc.b` bytes. A `dc.w` after an odd number of bytes can be auto-aligned by
  the assembler, which inserts a pad byte and corrupts the substring layout.
- Clicks that dismiss the alert can still reach applications because of input buffering.
- Only for serious trouble. Use [EasyRequestArgs](#easyrequestargs) for normal messages.

**See also:** [TimedDisplayAlert](#timeddisplayalert), exec.library Alert

## TimedDisplayAlert
`BOOL TimedDisplayAlert(ULONG alertNumber, CONST_STRPTR string, ULONG height, ULONG time)` — LVO -822 (-$336)
Registers: alertNumber=D0, string=A0, height=D1, time=A1; result in D0

DisplayAlert that removes itself after a given number of video frames.

- **alertNumber**, **string**, **height** — as for [DisplayAlert](#displayalert).
- **time** — timeout in video frames (50/s PAL, 60/s NTSC). **Passed in A1**, not a data register.
- **Result** — as DisplayAlert. FALSE on timeout.

Since V39.

**See also:** [DisplayAlert](#displayalert)

## DisplayBeep
`VOID DisplayBeep(struct Screen *screen)` — LVO -96 (-$60)
Registers: screen=A0; no result

Flash a screen's background colour as a visual "bell".

- **screen** — screen to flash, or NULL to flash every screen (reserve that for dire cases).

V36+: Intuition's own beeps go through the library vector too, so a SetFunction() patch (e.g. an audible
beep) affects them all.

### Gotchas
- It temporarily changes colour 0 of the screen. That can upset a program which reads back or cycles
  its palette at the same moment.

**See also:** [EasyRequestArgs](#easyrequestargs), exec.library SetFunction
