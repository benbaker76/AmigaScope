# input.device

input.device merges keyboard, mouse-port, timer and program-written events into one stream of
`struct InputEvent`s and passes it through a priority-ordered chain of **input handlers**. Intuition
is one of those handlers: it turns the events into pointer movement, gadget hits and IDCMP
messages. A program can add its own handler to watch, change or swallow events before (or after)
Intuition sees them, inject events, and set the key-repeat and mouse-port parameters.

For simply reading a joystick or the keyboard in a game, lowlevel.library
([ReadJoyPort](../lowlevel/joyport.md#readjoyport), [GetKey](../lowlevel/keyboard.md#getkey)) or
IDCMP_RAWKEY in a window is easier. Use a handler when events must NOT reach Intuition or
Workbench.

## Opening

- Device name `"input.device"` (no name macro in `devices/input.h`), unit 0, flags 0.
  [OpenDevice](../exec/libraries-devices-resources.md#opendevice) returns 0 on success.
- Request: a `struct IOStdReq` from [CreateIORequest](../exec/io.md#createiorequest).
  [IND_SETTHRESH](commands.md#ind_setthresh) and [IND_SETPERIOD](commands.md#ind_setperiod) read a
  `struct timerequest` (`tr_time` lies where IOStdReq has `io_Actual`/`io_Length`); an IOStdReq-sized
  request (48 bytes) is large enough to be used as one.
- The device base for [PeekQualifier](functions.md#peekqualifier) is the request's `io_Device` after
  OpenDevice (C global `struct Device *InputBase`; asm: A6 = `IO_DEVICE(a1)`).
- C: `#include <devices/input.h>`, `<devices/inputevent.h>`, `<proto/input.h>`. asm:
  `include "devices/input.i"`, `include "devices/inputevent.i"`, `include "lvo/input_lib.i"`.

```c
#include <proto/exec.h>
#include <proto/input.h>
#include <devices/input.h>

struct Device *InputBase;
static struct MsgPort *inputPort;
static struct IOStdReq *inputReq;

BOOL OpenInput(void)
{
    if ((inputPort = CreateMsgPort()) != NULL &&
        (inputReq = (struct IOStdReq *)CreateIORequest(inputPort, sizeof(struct IOStdReq))) != NULL &&
        OpenDevice((CONST_STRPTR)"input.device", 0, (struct IORequest *)inputReq, 0) == 0) {
        InputBase = inputReq->io_Device;
        return TRUE;
    }
    if (inputReq) { DeleteIORequest(inputReq); inputReq = NULL; }
    if (inputPort) { DeleteMsgPort(inputPort); inputPort = NULL; }
    return FALSE;
}

void CloseInput(void)
{
    CloseDevice((struct IORequest *)inputReq);
    DeleteIORequest(inputReq);
    DeleteMsgPort(inputPort);
}
```

## Commands

| Command | Value | Request data | Purpose |
|---|---|---|---|
| [IND_ADDHANDLER](commands.md#ind_addhandler) | 9 | `io_Data` = `struct Interrupt *` | add an input handler |
| [IND_REMHANDLER](commands.md#ind_remhandler) | 10 | `io_Data` = same Interrupt | remove it |
| [IND_WRITEEVENT](commands.md#ind_writeevent) | 11 | `io_Data` = `struct InputEvent *`, `io_Length` = 22 | inject one event |
| [IND_SETTHRESH](commands.md#ind_setthresh) | 12 | `tr_time` | key-repeat delay |
| [IND_SETPERIOD](commands.md#ind_setperiod) | 13 | `tr_time` | key-repeat interval |
| [IND_SETMPORT](commands.md#ind_setmport) | 14 | `io_Data` -> BYTE 0/1, `io_Length` = 1 | which port the mouse is in |
| [IND_SETMTYPE](commands.md#ind_setmtype) | 15 | `io_Data` -> BYTE `GPCT_` type, `io_Length` = 1 | controller type on the mouse port |
| [IND_SETMTRIG](commands.md#ind_setmtrig) | 16 | `io_Data` -> `struct GamePortTrigger`, `io_Length` = 8 | when mouse reports are generated |

Values are `CMD_NONSTD` (9) + n (`devices/input.h`; `DEVCMD` macros in `input.i`).

## Input handlers

A handler is a `struct Interrupt` added with IND_ADDHANDLER:

- `is_Node.ln_Pri` — position in the chain; higher priorities are called first.
  Intuition's handler runs at priority **50** (unverified: not stated in the NDK 3.9 autodocs or
  includes). A handler at 51 or above sees raw keyboard and mouse events before Intuition; one below
  50 only sees what Intuition passes on.
- `is_Node.ln_Type` = `NT_INTERRUPT`, `ln_Name` = a name identifying your program.
- `is_Code` — the handler; `is_Data` — any pointer, handed to it in A1.

Calling convention (IND_ADDHANDLER autodoc): `newEvents = Handler(events, handlerData)`.

| Register | Content |
|---|---|
| A0 (in) | first `struct InputEvent` of a NULL-terminated list linked by `ie_NextEvent` |
| A1 (in) | `is_Data` |
| D0 (out) | first event of the list to pass to the next handler (NULL = no events left) |

- The handler runs on input.device's own task, not in an interrupt (unverified): no Wait, no DOS,
  no calls that can block; Signal a task or PutMsg for real work. Everything input-related, including
  the mouse pointer, stalls while it runs.
- Preserve D2-D7 and A2-A6 (standard compiled-code convention; the autodoc does not list registers,
  unverified).
- Write the handler in asm (vasm) and link it: Bartman's GCC 15 rejects register-parameter
  declarations such as `struct InputEvent *ev __asm("a0")`, so a C function cannot receive A0/A1.
- To change an event, edit it in place. To drop one, unlink it (store its `ie_NextEvent` in the
  previous event, or return the successor if it is the first) or set `ie_Class` to `IECLASS_NULL`.
- The events belong to input.device and are only valid during the call: never free them or keep
  pointers to them; copy what you need.
- The Interrupt structure and handler code must stay in memory until IND_REMHANDLER has returned.

## struct InputEvent

| Off | asm (inputevent.i) | C field | Type | Meaning |
|---|---|---|---|---|
| $00 | `ie_NextEvent` | `ie_NextEvent` | `struct InputEvent *` | next event or NULL |
| $04 | `ie_Class` | `ie_Class` | UBYTE | `IECLASS_` |
| $05 | `ie_SubClass` | `ie_SubClass` | UBYTE | `IESUBCLASS_`; gameport RAWMOUSE reports: 0 = left port, 1 = right port |
| $06 | `ie_Code` | `ie_Code` | UWORD | raw key code / mouse button code |
| $08 | `ie_Qualifier` | `ie_Qualifier` | UWORD | `IEQUALIFIER_` bits |
| $0A | `ie_X`, `ie_EventAddress`, `ie_Prev1DownCode` | `ie_X` (WORD), `ie_EventAddress` (APTR), `ie_Prev1DownCode`, `ie_Prev1DownQual` (UBYTE) | union | position / pointer / dead-key history |
| $0C | `ie_Y`, `ie_Prev2DownCode` | `ie_Y` (WORD), `ie_Prev2DownCode`, `ie_Prev2DownQual` (UBYTE) | | |
| $0E | `ie_TimeStamp` | `ie_TimeStamp` | `struct timeval` | event time (`tv_secs`, `tv_micro`) |
| $16 | `ie_SIZEOF` | `sizeof(struct InputEvent)` = 22 | | |

In C, `ie_X`, `ie_Y`, `ie_EventAddress` and `ie_PrevNDown*` are macros for the `ie_position` union.

### IECLASS_ (ie_Class)

| Value | Name | Value | Name |
|---|---|---|---|
| $00 | `IECLASS_NULL` (ignore) | $0B | `IECLASS_CLOSEWINDOW` |
| $01 | `IECLASS_RAWKEY` | $0C | `IECLASS_SIZEWINDOW` |
| $02 | `IECLASS_RAWMOUSE` | $0D | `IECLASS_REFRESHWINDOW` |
| $03 | `IECLASS_EVENT` (private console event) | $0E | `IECLASS_NEWPREFS` |
| $04 | `IECLASS_POINTERPOS` | $0F | `IECLASS_DISKREMOVED` |
| $06 | `IECLASS_TIMER` | $10 | `IECLASS_DISKINSERTED` |
| $07 | `IECLASS_GADGETDOWN` | $11 | `IECLASS_ACTIVEWINDOW` |
| $08 | `IECLASS_GADGETUP` | $12 | `IECLASS_INACTIVEWINDOW` |
| $09 | `IECLASS_REQUESTER` | $13 | `IECLASS_NEWPOINTERPOS` (V36) |
| $0A | `IECLASS_MENULIST` | $14 | `IECLASS_MENUHELP` (V36) |
| | | $15 | `IECLASS_CHANGEWINDOW` (V36) = `IECLASS_MAX` |

$05 is unused. `IECLASS_NEWPOINTERPOS` sub-classes: `IESUBCLASS_COMPATIBLE` 0 (like POINTERPOS),
`IESUBCLASS_PIXEL` 1 (`ie_EventAddress` -> `struct IEPointerPixel`: screen + pixel position),
`IESUBCLASS_TABLET` 2 (`struct IEPointerTablet`), `IESUBCLASS_NEWTABLET` 3 (`struct IENewTablet`).

### IECODE_ (ie_Code)

| Class | Values |
|---|---|
| RAWKEY | key code $00-$77 (`IECODE_KEY_CODE_FIRST`..`_LAST`); $78-$7F keyboard communication codes (`IECODE_COMM_CODE_FIRST`..`_LAST`); `IECODE_UP_PREFIX` $80 ORed in when the key is released |
| RAWMOUSE | `IECODE_LBUTTON` $68, `IECODE_RBUTTON` $69, `IECODE_MBUTTON` $6A (each ORed with $80 on release), `IECODE_NOBUTTON` $FF = movement only |
| EVENT (V36) | `IECODE_NEWACTIVE` 1, `IECODE_NEWSIZE` 2, `IECODE_REFRESH` 3 |
| REQUESTER | `IECODE_REQSET` 1 (first requester opened), `IECODE_REQCLEAR` 0 (last one closed) |

The include also defines character ranges for an "ANSI" class (`IECODE_C0_FIRST` $00 ..
`IECODE_LATIN1_LAST` $FF) but no `IECLASS_ANSI` constant.

For RAWMOUSE, `ie_X`/`ie_Y` are movement deltas when `IEQUALIFIER_RELATIVEMOUSE` is set.

### IEQUALIFIER_ (ie_Qualifier)

| Bit | Name | Value | Bit | Name | Value |
|---|---|---|---|---|---|
| 0 | `IEQUALIFIER_LSHIFT` | $0001 | 8 | `IEQUALIFIER_NUMERICPAD` | $0100 |
| 1 | `IEQUALIFIER_RSHIFT` | $0002 | 9 | `IEQUALIFIER_REPEAT` | $0200 |
| 2 | `IEQUALIFIER_CAPSLOCK` | $0004 | 10 | `IEQUALIFIER_INTERRUPT` | $0400 |
| 3 | `IEQUALIFIER_CONTROL` | $0008 | 11 | `IEQUALIFIER_MULTIBROADCAST` | $0800 |
| 4 | `IEQUALIFIER_LALT` | $0010 | 12 | `IEQUALIFIER_MIDBUTTON` | $1000 |
| 5 | `IEQUALIFIER_RALT` | $0020 | 13 | `IEQUALIFIER_RBUTTON` | $2000 |
| 6 | `IEQUALIFIER_LCOMMAND` (left Amiga) | $0040 | 14 | `IEQUALIFIER_LEFTBUTTON` | $4000 |
| 7 | `IEQUALIFIER_RCOMMAND` (right Amiga) | $0080 | 15 | `IEQUALIFIER_RELATIVEMOUSE` | $8000 |

Bit numbers are `IEQUALIFIERB_<name>` (e.g. `IEQUALIFIERB_REPEAT` = 9).

## Common mistakes

- Forgetting that OpenDevice returns 0 on success (the opposite of OpenLibrary).
- Removing the handler with a different Interrupt pointer, or freeing its memory before
  IND_REMHANDLER has returned.
- Exiting (or crashing out) without IND_REMHANDLER: input.device keeps calling code that has been
  unloaded, and the machine goes down on the next key press or mouse move.
- Doing slow work or DOS calls inside the handler.
- Mixing up `IEQUALIFIER_` bits (0-15 of `ie_Qualifier`) with lowlevel.library's `LLKF_` bits
  (16-23 of the GetKey result).

## Files

- [commands.md](commands.md) -- the eight IND_ commands.
- [functions.md](functions.md) -- PeekQualifier.

<!-- FUNCTION TABLE -->
<!-- Generated by tools/skills/build_indexes.py - do not edit by hand. -->

## Functions

| Function | LVO | Registers | Summary |
|---|---|---|---|
| [PeekQualifier](functions.md#peekqualifier) | -42 | none | Return input.device's current view of the qualifier keys and mouse buttons. |

Machine-readable: [../data/input.tsv](../data/input.tsv)
