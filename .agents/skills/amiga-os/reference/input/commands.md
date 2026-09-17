# input.device: commands

Send these with [DoIO](../exec/io.md#doio) on a request opened on `"input.device"` unit 0 (see
[opening](index.md#opening)). Handlers are added and removed with IND_ADDHANDLER/IND_REMHANDLER,
events are injected with IND_WRITEEVENT, and the remaining five change system-wide input settings
(key repeat and the mouse port), which affect every program: put back what you change.

## IND_ADDHANDLER
`io_Command` = `IND_ADDHANDLER` (9) · input.device · request: `struct IOStdReq`

Insert an input handler into the input stream at the priority in its Interrupt node.

- **In:** `io_Data` = `struct Interrupt *` with `is_Code` = handler, `is_Data` = its data (passed
  in A1), `is_Node.ln_Pri` = chain priority, `ln_Type` = `NT_INTERRUPT`, `ln_Name` = your name.
- **Out:** `io_Error` = 0.

The handler is called as `D0 = Handler(A0 = events, A1 = is_Data)` and must return the event list
for the next handler; rules in [input handlers](index.md#input-handlers). input.device keeps the
Interrupt structure until an IND_REMHANDLER for it has completed.

### Example
```c
#include <proto/exec.h>
#include <exec/interrupts.h>
#include <devices/input.h>

extern void KeyHandler(void);           /* asm below: A0 = events, A1 = keymap */
UBYTE keymap[128];                      /* $FF = key down, filled by the handler */

static struct Interrupt keyInt;

/* ior: IOStdReq opened on input.device */
void AddKeyHandler(struct IOStdReq *ior)
{
    keyInt.is_Node.ln_Type = NT_INTERRUPT;
    keyInt.is_Node.ln_Pri  = 100;       /* ahead of Intuition */
    keyInt.is_Node.ln_Name = (char *)"MyGame keys";
    keyInt.is_Data = keymap;
    keyInt.is_Code = (VOID (*)())KeyHandler;

    ior->io_Command = IND_ADDHANDLER;
    ior->io_Data    = &keyInt;
    DoIO((struct IORequest *)ior);
}

void RemKeyHandler(struct IOStdReq *ior)
{
    ior->io_Command = IND_REMHANDLER;
    ior->io_Data    = &keyInt;
    DoIO((struct IORequest *)ior);      /* keyInt/KeyHandler may go away only after this */
}
```

```asm
; keyhandler.asm -- records raw keys in the table at A1 and hides them from Intuition
        include "devices/inputevent.i"

        xdef    KeyHandler              ; ELF C symbols have no leading underscore
KeyHandler:
        move.l  a0,d0                   ; return the same list
        bra.s   .test
.loop:
        cmp.b   #IECLASS_RAWKEY,ie_Class(a0)
        bne.s   .next
        moveq   #$7f,d1
        and.w   ie_Code(a0),d1          ; key number without IECODE_UP_PREFIX
        tst.b   ie_Code+1(a0)           ; bit 7 set = released
        spl     (a1,d1.w)               ; $FF pressed, $00 released
        move.b  #IECLASS_NULL,ie_Class(a0)      ; nobody after us reacts to it
.next:
        move.l  ie_NextEvent(a0),a0
.test:
        cmpa.w  #0,a0
        bne.s   .loop
        rts
```

### Gotchas
- A priority above Intuition's (50, unverified) is needed to see or hide keys and mouse events
  before Intuition does.
- Hiding every RAWKEY also hides the keys a user needs to leave your program: provide your own exit
  key, and always remove the handler on every exit path.
- Keep `keyInt` and the handler code in memory until IND_REMHANDLER has returned.

**See also:** [IND_REMHANDLER](#ind_remhandler), [IND_WRITEEVENT](#ind_writeevent), [input handlers](index.md#input-handlers), [struct Interrupt](../topics/structures.md#interrupt)

## IND_REMHANDLER
`io_Command` = `IND_REMHANDLER` (10) · input.device · request: `struct IOStdReq`

Remove a handler previously added with IND_ADDHANDLER.

- **In:** `io_Data` = the same `struct Interrupt *` that was added.
- **Out:** `io_Error` = 0.

The autodoc marks it as not immediate: it is queued and replied later, never finished inside the call.

### Gotchas
- Use DoIO (or wait for the reply) and free or unload the handler only afterwards: until the reply
  arrives the handler may still be called.

**See also:** [IND_ADDHANDLER](#ind_addhandler)

## IND_WRITEEVENT
`io_Command` = `IND_WRITEEVENT` (11) · input.device · request: `struct IOStdReq`

Feed one input event into the input stream as if it came from a device.

- **In:** `io_Data` = `struct InputEvent *`, `io_Length` = `sizeof(struct InputEvent)` (22).
  Fill in `ie_Class`, `ie_SubClass`, `ie_Code`, `ie_Qualifier`, `ie_X`/`ie_Y` (or
  `ie_EventAddress`). `ie_NextEvent` is ignored: one event per request.
- **Out:** `io_Error` = 0. `ie_TimeStamp` is filled in by the device (V36+); the rest of the event
  structure is overwritten.

### Example
```c
#include <proto/exec.h>
#include <devices/input.h>
#include <devices/inputevent.h>

/* move the mouse pointer by (dx, dy) mickeys */
void NudgePointer(struct IOStdReq *ior, WORD dx, WORD dy)
{
    struct InputEvent ev = {0};

    ev.ie_Class     = IECLASS_RAWMOUSE;
    ev.ie_Code      = IECODE_NOBUTTON;
    ev.ie_Qualifier = IEQUALIFIER_RELATIVEMOUSE;
    ev.ie_X         = dx;
    ev.ie_Y         = dy;

    ior->io_Command = IND_WRITEEVENT;
    ior->io_Data    = &ev;
    ior->io_Length  = sizeof(struct InputEvent);
    DoIO((struct IORequest *)ior);
}
```

### Gotchas
- The event is destroyed by the call: fill it in again before every write.
- Chaining events through `ie_NextEvent` never worked, despite pre-V36 documentation.
- Before V36 the device did not set `ie_TimeStamp`; set it yourself if you target 1.3.
- The event passes through all handlers, including yours if it is installed.

**See also:** [IND_ADDHANDLER](#ind_addhandler), [struct InputEvent](index.md#struct-inputevent)

## IND_SETTHRESH
`io_Command` = `IND_SETTHRESH` (12) · input.device · request: `struct timerequest`

Set how long a key must be held before it starts repeating.

- **In:** `tr_time.tv_secs` and `tr_time.tv_micro` = the delay.
- **Out:** `io_Error` = 0. Always completes immediately.

Some keys never repeat (the shift keys, for example).

### Example
```c
#include <proto/exec.h>
#include <devices/input.h>
#include <devices/timer.h>

/* ior: IOStdReq-sized request opened on input.device, used as a timerequest */
void SetKeyRepeat(struct IORequest *ior, ULONG delayMicros, ULONG periodMicros)
{
    struct timerequest *tr = (struct timerequest *)ior;

    tr->tr_node.io_Command = IND_SETTHRESH;
    tr->tr_time.tv_secs    = delayMicros / 1000000;
    tr->tr_time.tv_micro   = delayMicros % 1000000;
    DoIO(ior);

    tr->tr_node.io_Command = IND_SETPERIOD;
    tr->tr_time.tv_secs    = periodMicros / 1000000;
    tr->tr_time.tv_micro   = periodMicros % 1000000;
    DoIO(ior);
}
```

### Gotchas
- The setting is global and there is no command to read it back. The user's values are in
  intuition's `struct Preferences` (`KeyRptDelay`, `KeyRptSpeed`) from GetPrefs: restore those on exit.
- Keep `tv_micro` below 1000000.

**See also:** [IND_SETPERIOD](#ind_setperiod), intuition [GetPrefs](../intuition/input-and-prefs.md#getprefs)

## IND_SETPERIOD
`io_Command` = `IND_SETPERIOD` (13) · input.device · request: `struct timerequest`

Set the interval between repeats of a held key.

- **In:** `tr_time.tv_secs` and `tr_time.tv_micro` = the repeat period.
- **Out:** `io_Error` = 0. Always completes immediately.

### Gotchas
- Global setting (Preferences `KeyRptSpeed`): restore it on exit. Example under
  [IND_SETTHRESH](#ind_setthresh).

**See also:** [IND_SETTHRESH](#ind_setthresh)

## IND_SETMPORT
`io_Command` = `IND_SETMPORT` (14) · input.device · request: `struct IOStdReq`

Choose which controller port input.device reads the mouse from.

- **In:** `io_Data` -> a BYTE: 0 = left port (port 0, the normal mouse port), 1 = right port;
  `io_Length` = 1.
- **Out:** `io_Error` = 0.

### Gotchas
- System-wide: the pointer moves with whatever is in the chosen port. Set it back to 0 before you exit.
- A BYTE, not a LONG: `io_Data` must point at a single byte holding 0 or 1.

**See also:** [IND_SETMTYPE](#ind_setmtype), [IND_SETMTRIG](#ind_setmtrig)

## IND_SETMTYPE
`io_Command` = `IND_SETMTYPE` (15) · input.device · request: `struct IOStdReq`

Tell input.device what kind of controller is on the mouse port.

- **In:** `io_Data` -> a BYTE controller type from `devices/gameport.h`: `GPCT_NOCONTROLLER` 0,
  `GPCT_MOUSE` 1, `GPCT_RELJOYSTICK` 2, `GPCT_ABSJOYSTICK` 3; `io_Length` = 1.
- **Out:** `io_Error` = 0.

### Gotchas
- `GPCT_ALLOCATED` (-1) is a value gameport.device reports, not one to set.
- Games that want to read the mouse port themselves have used `GPCT_NOCONTROLLER` to make
  input.device let go of it (unverified); restore `GPCT_MOUSE` on exit.

**See also:** [IND_SETMPORT](#ind_setmport), [ReadJoyPort](../lowlevel/joyport.md#readjoyport)

## IND_SETMTRIG
`io_Command` = `IND_SETMTRIG` (16) · input.device · request: `struct IOStdReq`

Set the conditions under which the mouse port produces a report.

- **In:** `io_Data` -> `struct GamePortTrigger` (`devices/gameport.h`), `io_Length` =
  `sizeof(struct GamePortTrigger)` (8):
  - `gpt_Keys` — `GPTF_DOWNKEYS` (1) report button presses, `GPTF_UPKEYS` (2) report releases.
  - `gpt_Timeout` — report after this many vertical blanks even without a change.
  - `gpt_XDelta`, `gpt_YDelta` — report when movement exceeds this distance on that axis.
- **Out:** `io_Error` = 0.

### Gotchas
- Same trigger format as gameport.device GPD_SETTRIGGER.
- The autodoc counts `gpt_Timeout` in 60ths of a second; on a PAL display vertical blanks come 50
  times per second.

**See also:** [IND_SETMPORT](#ind_setmport), [IND_SETMTYPE](#ind_setmtype)
