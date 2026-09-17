# input.device: functions

input.device has one library-style function in its device base (bias 42). Call it with A6 =
`InputBase`, the `io_Device` of a request opened on input.device (see [opening](index.md#opening)).
D0, D1, A0, A1 are scratch as for any library call.

## PeekQualifier
`UWORD PeekQualifier(VOID)` — LVO -42 (-$2A)
Registers: none; result in D0

Return input.device's current view of the qualifier keys and mouse buttons.

- **Result** — UWORD of `IEQUALIFIER_` bits: `LSHIFT` $0001, `RSHIFT` $0002, `CAPSLOCK` $0004,
  `CONTROL` $0008, `LALT` $0010, `RALT` $0020, `LCOMMAND` $0040, `RCOMMAND` $0080, `MIDBUTTON` $1000,
  `RBUTTON` $2000, `LEFTBUTTON` $4000 (full table in [IEQUALIFIER_](index.md#iequalifier_-ie_qualifier)).

It is a snapshot of the state the device has processed so far, not a direct hardware read.

Since V36.

### Example
```asm
        include "exec/io.i"
        include "devices/inputevent.i"
        include "lvo/input_lib.i"

; A1 = IOStdReq opened on input.device
        move.l  a6,-(sp)
        move.l  IO_DEVICE(a1),a6        ; InputBase
        jsr     _LVOPeekQualifier(a6)
        move.l  (sp)+,a6
        btst    #IEQUALIFIERB_LSHIFT,d0
        bne.s   .shifted
```

```c
#include <proto/input.h>
#include <devices/inputevent.h>

extern struct Device *InputBase;        /* = ior->io_Device after OpenDevice */

BOOL ShiftHeld(void)
{
    return (BOOL)((PeekQualifier() & (IEQUALIFIER_LSHIFT | IEQUALIFIER_RSHIFT)) != 0);
}
```

### Gotchas
- input.device must be opened first; there is no OpenLibrary for it. The base stays valid until
  CloseDevice.
- V36+ only: on 1.3 the LVO is not there.
- Only the low word of D0 is defined: test with `btst`/`tst.w`.

**See also:** [struct InputEvent](index.md#struct-inputevent), lowlevel.library [GetKey](../lowlevel/keyboard.md#getkey)
