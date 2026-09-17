# lowlevel.library: keyboard

Three ways to see the keyboard without an Intuition window: poll the last key and the qualifiers
([GetKey](#getkey)), ask whether particular keys are held down right now ([QueryKeys](#querykeys)),
or run a routine on every keyboard interrupt ([AddKBInt](#addkbint) / [RemKBInt](#remkbint)). All of
them work on raw key codes, whatever window or screen is active. Handy raw codes: ESC $45, space $40,
Return $44, cursor up $4C / down $4D / right $4E / left $4F, F1-F10 $50-$59; bit 7 set
(`IECODE_UP_PREFIX` $80) marks a release in event streams.

## GetKey
`ULONG GetKey(VOID)` — LVO -48 (-$30)
Registers: none; result in D0

Return the last non-qualifier key pressed and the qualifier keys currently held.

- **Result** — low word: raw key code, or $00FF when no key is pressed. Upper word: qualifier bits.

| Bit | Name (`LLKB_` / `LLKF_`) | Key |
|---|---|---|
| 16 | `LLKB_LSHIFT` / $00010000 | left Shift |
| 17 | `LLKB_RSHIFT` / $00020000 | right Shift |
| 18 | `LLKB_CAPSLOCK` / $00040000 | Caps Lock |
| 19 | `LLKB_CONTROL` / $00080000 | Ctrl |
| 20 | `LLKB_LALT` / $00100000 | left Alt |
| 21 | `LLKB_RALT` / $00200000 | right Alt |
| 22 | `LLKB_LAMIGA` / $00400000 | left Amiga |
| 23 | `LLKB_RAMIGA` / $00800000 | right Amiga |

Safe to call from an interrupt.

Since V40.

### Example
```asm
        include "libraries/lowlevel.i"
        include "lvo/lowlevel_lib.i"

        move.l  _LowLevelBase,a6
        jsr     _LVOGetKey(a6)
        cmp.w   #$45,d0                 ; low word: ESC?
        bne.s   .noesc
        btst    #LLKB_LSHIFT,d0         ; with left Shift held?
        bne     .quit
.noesc:
```

### Gotchas
- Only one non-qualifier key is reported. For several simultaneous keys (e.g. diagonals on
  cursor keys) use [QueryKeys](#querykeys).
- Compare the low WORD, not the whole long: the qualifier bits are in the same value.

**See also:** [QueryKeys](#querykeys), [AddKBInt](#addkbint), input.device [PeekQualifier](../input/functions.md#peekqualifier)

## QueryKeys
`VOID QueryKeys(struct KeyQuery *queryArray, ULONG arraySize)` — LVO -54 (-$36)
Registers: queryArray=A0, arraySize=D1; no result

Report for each raw key code in an array whether that key is held down now.

- **queryArray** — array of `struct KeyQuery` { `UWORD kq_KeyCode`; `BOOL kq_Pressed` } (4 bytes
  each; asm `kq_KeyCode` 0, `kq_Pressed` 2, `KeyQuery_SIZEOF` 4). Fill in the codes; the call
  sets `kq_Pressed` to TRUE (down) or FALSE.
- **arraySize** — number of entries. The SFD and autodoc type it as UBYTE: at most 255.

May be called from interrupts; keep the array short there.

Since V40.

### Example
```c
#include <proto/lowlevel.h>
#include <libraries/lowlevel.h>

extern struct Library *LowLevelBase;

static struct KeyQuery keys[] = {
    { 0x4C, FALSE }, { 0x4D, FALSE },   /* up, down */
    { 0x4F, FALSE }, { 0x4E, FALSE },   /* left, right */
    { 0x40, FALSE },                    /* space = fire */
};

void ReadCursorKeys(WORD *dx, WORD *dy, BOOL *fire)
{
    QueryKeys(keys, sizeof(keys) / sizeof(keys[0]));
    *dy = (WORD)(keys[1].kq_Pressed ? 1 : 0) - (WORD)(keys[0].kq_Pressed ? 1 : 0);
    *dx = (WORD)(keys[3].kq_Pressed ? 1 : 0) - (WORD)(keys[2].kq_Pressed ? 1 : 0);
    *fire = keys[4].kq_Pressed;
}
```

### Gotchas
- `kq_Pressed` is a 16-bit BOOL: in asm test it with `tst.w`, not `tst.b` or `tst.l`.
- Codes are raw key codes without the $80 release bit.

**See also:** [GetKey](#getkey)

## AddKBInt
`APTR AddKBInt(CONST APTR intRoutine, CONST APTR intData)` — LVO -60 (-$3C)
Registers: intRoutine=A0, intData=A1; result in D0

Install a routine that runs inside the keyboard interrupt for every key received.

- **intRoutine** — code called with D0 = raw key code, A1 = `intData`, A5 = routine address. It
  must preserve D2-D7 and A2-A4 and return with **D0 = 0** (see the
  [routine contract](index.md#interrupt-routines-addkbint-addtimerint-addvblankint)).
- **intData** — any long value handed to the routine in A1 (point it at a structure if you need
  more).
- **Result** — handle for [RemKBInt](#remkbint), or NULL if it could not be installed.

Keyboard handshaking is still done by the system, error codes from the keyboard are filtered out, and
the routine is not called for a keyboard reset.

Since V40.

### Example
```asm
        include "lvo/lowlevel_lib.i"

        move.l  _LowLevelBase,a6
        lea     KeyRoutine(pc),a0
        lea     keystate,a1             ; intData
        jsr     _LVOAddKBInt(a6)
        move.l  d0,kbhandle
        beq     .nokbint                ; someone else owns it
        ; ... game runs ...
        move.l  kbhandle,a1
        jsr     _LVORemKBInt(a6)

; D0 = raw key code, A1 = keystate (128 flags, one per key)
KeyRoutine:
        moveq   #$7f,d1
        and.b   d0,d1                   ; key number
        tst.b   d0
        smi     d0                      ; $FF if release bit set
        not.b   d0                      ; $FF = down, $00 = up
        move.b  d0,(a1,d1.w)
        moveq   #0,d0                   ; required
        rts

        section bss,bss
kbhandle:       ds.l    1
keystate:       ds.b    128
```

### Gotchas
- Only ONE keyboard routine can exist system-wide: a NULL result means another program has it.
- Whether the routine also runs for key releases (codes with bit 7 set) is not stated by the
  autodoc; the example handles both (unverified).
- You MUST call [RemKBInt](#remkbint) before exiting unless the program ends in a reboot.
- Runs in interrupt context: no blocking calls, keep it short.

**See also:** [RemKBInt](#remkbint), [GetKey](#getkey), [QueryKeys](#querykeys)

## RemKBInt
`VOID RemKBInt(APTR intHandle)` — LVO -66 (-$42)
Registers: intHandle=A1; no result

Remove the keyboard routine installed with AddKBInt.

- **intHandle** — handle from [AddKBInt](#addkbint); NULL is allowed and does nothing.

Since V40.

**See also:** [AddKBInt](#addkbint)
