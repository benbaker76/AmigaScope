# lowlevel.library: joy ports

[ReadJoyPort](#readjoyport) returns one ULONG describing the controller in a port and its state;
[SetJoyPortAttrsA](#setjoyportattrsa) stops the auto-detection and forces a controller type. Port 0
is the mouse port, port 1 the joystick port; the calls accept 0-3, but stock machines have only
ports 0 and 1.

## ReadJoyPort
`ULONG ReadJoyPort(ULONG port)` — LVO -30 (-$1E)
Registers: port=D0; result in D0

Detect what is plugged into a joy port and return its current buttons and position.

- **port** — 0 (mouse port) to 3.
- **Result** — type nibble plus state bits, below. `JP_TYPE_NOTAVAIL` means the resources could not
  be obtained or another task is inside ReadJoyPort at the same moment.

Test the type nibble first: the low bits mean directions for joysticks and pads but mouse
counters for a mouse.

| Bits | Name (`JPB_` bit / `JPF_` or mask value) | Game controller (CD32 pad) | Joystick | Mouse |
|---|---|---|---|---|
| 31-28 | `JP_TYPE_MASK` $F0000000 | type | type | type |
| 23 | `JPB_BUTTON_BLUE` / $00800000 | blue (Stop) | second button | right button |
| 22 | `JPB_BUTTON_RED` / $00400000 | red (Select) | fire | left button |
| 21 | `JPB_BUTTON_YELLOW` / $00200000 | yellow (Repeat) | -- | -- |
| 20 | `JPB_BUTTON_GREEN` / $00100000 | green (Shuffle) | -- | -- |
| 19 | `JPB_BUTTON_FORWARD` / $00080000 | charcoal Forward | -- | -- |
| 18 | `JPB_BUTTON_REVERSE` / $00040000 | charcoal Reverse | -- | -- |
| 17 | `JPB_BUTTON_PLAY` / $00020000 | grey Play/Pause | -- | middle button |
| 15-8 | `JP_MVERT_MASK` $0000FF00 | -- | -- | vertical counter |
| 7-0 | `JP_MHORZ_MASK` $000000FF | -- | -- | horizontal counter |
| 3 | `JPB_JOY_UP` / $00000008 | up | up | (counter bit) |
| 2 | `JPB_JOY_DOWN` / $00000004 | down | down | (counter bit) |
| 1 | `JPB_JOY_LEFT` / $00000002 | left | left | (counter bit) |
| 0 | `JPB_JOY_RIGHT` / $00000001 | right | right | (counter bit) |

Type values (`result & JP_TYPE_MASK`): `JP_TYPE_NOTAVAIL` $00000000 (port could not be read),
`JP_TYPE_GAMECTLR` $10000000, `JP_TYPE_MOUSE` $20000000, `JP_TYPE_JOYSTK` $30000000,
`JP_TYPE_UNKNOWN` $40000000. Group masks: `JP_BUTTON_MASK` $00FE0000, `JP_DIRECTION_MASK` $0000000F,
`JP_MOUSE_MASK` $0000FFFF. Buttons are valid for every type except `JP_TYPE_NOTAVAIL`; directions only
for game controllers and joysticks. A bit is 1 while pressed.

`libraries/lowlevel.h` keeps obsolete aliases for old sources: `JPF_BTN1`..`JPF_BTN7` (= BLUE, RED,
YELLOW, GREEN, FORWARD, REVERSE, PLAY) and `JPF_UP`/`JPF_DOWN`/`JPF_LEFT`/`JPF_RIGHT`. Use the long names.

Detection: a CD32 pad is recognised on the first read (it is clocked); telling a mouse from a
joystick takes several reads and some movement. Force the type with
[SetJoyPortAttrsA](#setjoyportattrsa) when you know what the game needs.

Since V40.

### Example
```c
#include <proto/exec.h>
#include <proto/graphics.h>
#include <proto/lowlevel.h>
#include <libraries/lowlevel.h>

struct Library *LowLevelBase;

/* one read per frame; returns when fire or Play is pressed */
void JoyLoop(void)
{
    UBYTE lastx = 0, lasty = 0;
    BOOL first = TRUE;

    for (;;) {
        ULONG st;

        WaitTOF();
        st = ReadJoyPort(1);
        switch (st & JP_TYPE_MASK) {
        case JP_TYPE_GAMECTLR:
        case JP_TYPE_JOYSTK:
            if (st & JPF_JOY_LEFT)  { /* move left */ }
            if (st & JPF_JOY_RIGHT) { /* move right */ }
            if (st & (JPF_BUTTON_RED | JPF_BUTTON_PLAY))
                return;
            break;
        case JP_TYPE_MOUSE: {
            UBYTE x = st & JP_MHORZ_MASK, y = (st & JP_MVERT_MASK) >> 8;
            if (!first) {
                BYTE dx = (BYTE)(x - lastx), dy = (BYTE)(y - lasty);  /* 8-bit wrap */
                (void)dx; (void)dy;
            }
            lastx = x; lasty = y; first = FALSE;
            break;
        }
        default:                        /* NOTAVAIL / UNKNOWN: nothing usable this frame */
            break;
        }
    }
}
```

### Gotchas
- The FIRST call for each port must come from a task or process (it allocates system
  resources); after a successful first call it may be used in interrupts.
- Single-threaded: a second task calling it at the same time gets `JP_TYPE_NOTAVAIL`.
- Never test `JPF_JOY_*` without checking the type: on a mouse, bits 0-3 are counter bits.
- Mouse values are free-running 8-bit counters, not positions: subtract the previous reading as
  a signed byte.
- It returns at once and does not wait for a change; call it once per frame (WaitTOF), not in a
  tight loop.
- The mouse port is also read by input.device: pads and joysticks belong in port 1. The NDK 3.9
  lowlevel release notes (V45) state that the V40 library could not allocate a CD32 pad in port 0
  (unverified).
- Auto-sensing can misread very small mouse movements as joystick movement and makes every read
  slower: games should force the type.

**See also:** [SetJoyPortAttrsA](#setjoyportattrsa), [SystemControlA](system.md#systemcontrola) (`SCON_AddCreateKeys`), graphics [WaitTOF](../graphics/blitter-and-timing.md#waittof)

## SetJoyPortAttrsA
`BOOL SetJoyPortAttrsA(ULONG portNumber, CONST struct TagItem *tagList)` — LVO -132 (-$84)
Registers: portNumber=D0, tagList=A1; result in D0

Force a port's controller type or reset the port and release what ReadJoyPort allocated.

- **portNumber** — 0-3.
- **tagList** — tags below; NULL does nothing and returns TRUE. Varargs form:
  `SetJoyPortAttrs(portNumber, tag, data, ..., TAG_END)`.
- **Result** — TRUE on success, FALSE on failure.

| Tag | Value | ti_Data |
|---|---|---|
| `SJA_Type` | $80C00101 | `SJA_TYPE_AUTOSENSE` (0, default), `SJA_TYPE_GAMECTLR` (1), `SJA_TYPE_MOUSE` (2), `SJA_TYPE_JOYSTK` (3) |
| `SJA_Reinitialize` | $80C00102 | ignored; frees the port's resources (the include says potgo bits) and returns it to auto-sense |

With a forced type, ReadJoyPort reads the port only as that controller and skips detection.

Since V40.27.

### Example
```c
#include <proto/exec.h>
#include <proto/lowlevel.h>
#include <libraries/lowlevel.h>

extern struct Library *LowLevelBase;

static BOOL HasJoyAttrs(void)
{
    return (BOOL)(LowLevelBase->lib_Version > 40 ||
                  (LowLevelBase->lib_Version == 40 && LowLevelBase->lib_Revision >= 27));
}

void GameStart(void)
{
    if (HasJoyAttrs())
        SetJoyPortAttrs(1, SJA_Type, SJA_TYPE_GAMECTLR, TAG_END);   /* CD32 pad in port 1 */
}

void GameEnd(void)
{
    if (HasJoyAttrs())
        SetJoyPortAttrs(1, SJA_Reinitialize, 0, TAG_END);         /* auto-sense, free bits */
}
```

```asm
        include "libraries/lowlevel.i"
        include "lvo/lowlevel_lib.i"

        move.l  _LowLevelBase,a6
        moveq   #1,d0                   ; port 1
        lea     joytags(pc),a1          ; tags in A1
        jsr     _LVOSetJoyPortAttrsA(a6)
        tst.w   d0                      ; BOOL
        beq     .failed
        ; ...
joytags:
        dc.l    SJA_Type,SJA_TYPE_JOYSTK
        dc.l    TAG_DONE
```

### Gotchas
- Only lowlevel.library 40.27 and later implement it: check `lib_Version`/`lib_Revision` as above.
- A forced type is global state: return the port to auto-sense (`SJA_Reinitialize`, or `SJA_Type`
  with `SJA_TYPE_AUTOSENSE`) before your program exits.
- Tag list in A1, port in D0.

**See also:** [ReadJoyPort](#readjoyport)
