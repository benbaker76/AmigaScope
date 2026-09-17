# lowlevel.library: system control and language

[SystemControlA](#systemcontrola) switches system behaviour for a game: exclusive CPU, no requesters,
CD-eject reboot policy, input.device shutdown, and rawkey events generated from joystick/pad
buttons. [GetLanguageSelection](#getlanguageselection) returns the language the user picked.

## SystemControlA
`ULONG SystemControlA(CONST struct TagItem *tagList)` — LVO -72 (-$48)
Registers: tagList=A1; result in D0

Apply system-control tags all-or-nothing; a non-zero result names a tag that failed.

- **tagList** — tags below. Varargs form: `SystemControl(tag, data, ..., TAG_END)`.
- **Result** — 0 when every tag was applied. Otherwise the tag value that failed (compare with the
  `SCON_` names); in that case NONE of the tags changed anything, though other tags might also have
  failed.

| Tag | Value | ti_Data | Nests | Notes |
|---|---|---|---|---|
| `SCON_TakeOverSys` | $80C00000 | BOOL | yes | TRUE: task switching off, the caller gets all CPU time except crucial interrupts. While the task is in Wait(), multitasking runs again until the signal arrives. Task-exclusive. |
| `SCON_KillReq` | $80C00001 | BOOL | yes (balance every TRUE with a FALSE) | TRUE: no system requesters for the program. |
| `SCON_CDReboot` | $80C00002 | `CDReboot_On` 1, `CDReboot_Off` 0, `CDReboot_Default` 2 | no | whether ejecting the CD reboots. Default is On on the CD32, Off on computers; restore `CDReboot_Default` on exit if you changed it. |
| `SCON_StopInput` | $80C00003 | BOOL | -- | TRUE: input.device stops using CPU and passing keyboard and port 0 events. Task-exclusive and NOT reversible. |
| `SCON_AddCreateKeys` | $80C00004 | unit 0 or 1 | yes | generate raw key events from the joystick/pad in that port (adds code to the vertical-blank chain per unit). |
| `SCON_RemCreateKeys` | $80C00005 | unit 0 or 1 | -- | stop generating them. |

A task-exclusive tag fails when another task already holds it TRUE.

Raw key codes produced by `SCON_AddCreateKeys` (libraries/lowlevel.h; port 1 adds $100, and the
include also lists port 2 and 3 codes with $200/$300):

| Control | Port 0 name | Code | Port 1 code |
|---|---|---|---|
| blue | `RAWKEY_PORT0_BUTTON_BLUE` | $72 | $172 |
| play | `RAWKEY_PORT0_BUTTON_PLAY` | $73 | $173 |
| reverse | `RAWKEY_PORT0_BUTTON_REVERSE` | $74 | $174 |
| forward | `RAWKEY_PORT0_BUTTON_FORWARD` | $75 | $175 |
| green | `RAWKEY_PORT0_BUTTON_GREEN` | $76 | $176 |
| yellow | `RAWKEY_PORT0_BUTTON_YELLOW` | $77 | $177 |
| red | `RAWKEY_PORT0_BUTTON_RED` | $78 | $178 |
| up | `RAWKEY_PORT0_JOY_UP` | $79 | $179 |
| down | `RAWKEY_PORT0_JOY_DOWN` | $7A | $17A |
| right | `RAWKEY_PORT0_JOY_RIGHT` | $7B | $17B |
| left | `RAWKEY_PORT0_JOY_LEFT` | $7C | $17C |

Since V40.

### Example
```c
#include <proto/lowlevel.h>
#include <libraries/lowlevel.h>

extern struct Library *LowLevelBase;

BOOL TakeOver(void)
{
    ULONG failed = SystemControl(SCON_TakeOverSys, TRUE,
                                 SCON_KillReq, TRUE,
                                 TAG_END);
    return (BOOL)(failed == 0);         /* on failure nothing was changed */
}

void GiveBack(void)
{
    SystemControl(SCON_KillReq, FALSE,
                  SCON_TakeOverSys, FALSE,
                  TAG_END);
}
```

```asm
        include "libraries/lowlevel.i"
        include "lvo/lowlevel_lib.i"

        move.l  _LowLevelBase,a6
        lea     takeover(pc),a1         ; tags in A1
        jsr     _LVOSystemControlA(a6)
        tst.l   d0
        bne     .failed                 ; D0 = the failing tag
        ; ...
takeover:
        dc.l    SCON_TakeOverSys,1
        dc.l    SCON_KillReq,1
        dc.l    TAG_DONE
```

### Gotchas
- It can fail: always check the result.
- `SCON_TakeOverSys` acts like Forbid for everyone else: load files and open everything first.
  Calls that need other tasks (DOS, device I/O) cannot complete except while you Wait().
- `SCON_KillReq` hides requesters such as "insert volume": only use it when no DOS call can raise
  one (all loading done, or only a CD with `CDReboot_On`, or saving through nonvolatile.library).
- Never use `SCON_StopInput` in a program that returns to Workbench: it cannot be undone.
- `SCON_AddCreateKeys` codes reach programs as raw key input events (IDCMP_RAWKEY in the active
  window; unverified). In an Intuition window the blue button counts as the menu button, so
  Intuition swallows most blue-button events: open the window with `WFLG_RMBTRAP` if you need them.
- The port 0 codes $78-$7C fall in the range input.device reserves for keyboard communication codes
  (`IECODE_COMM_CODE_FIRST` $78 .. `IECODE_COMM_CODE_LAST` $7F).
- Balance every nesting TRUE with a FALSE before exit, and undo `SCON_AddCreateKeys` with
  `SCON_RemCreateKeys`.

**See also:** [ReadJoyPort](joyport.md#readjoyport), graphics [WaitTOF](../graphics/blitter-and-timing.md#waittof), exec [Forbid](../exec/tasks.md#forbid)

## GetLanguageSelection
`UBYTE GetLanguageSelection(VOID)` — LVO -36 (-$24)
Registers: none; result in D0

Return the language the user has selected, or 0 if none has been chosen yet.

- **Result** — UBYTE language code:

| Value | Name | Value | Name |
|---|---|---|---|
| 0 | `LANG_UNKNOWN` | 10 | `LANG_NORWEGIAN` |
| 1 | `LANG_AMERICAN` (American English) | 11 | `LANG_FINNISH` |
| 2 | `LANG_ENGLISH` (British English) | 12 | `LANG_SWEDISH` |
| 3 | `LANG_GERMAN` | 13 | `LANG_JAPANESE` |
| 4 | `LANG_FRENCH` | 14 | `LANG_CHINESE` |
| 5 | `LANG_SPANISH` | 15 | `LANG_ARABIC` |
| 6 | `LANG_ITALIAN` | 16 | `LANG_GREEK` |
| 7 | `LANG_PORTUGUESE` | 17 | `LANG_HEBREW` |
| 8 | `LANG_DANISH` | 18 | `LANG_KOREAN` |
| 9 | `LANG_DUTCH` | | |

Since V40.

### Gotchas
- Only the low byte of D0 is defined (the autodoc synopsis says ULONG, the SFD/clib say UBYTE):
  `tst.b`/`cmp.b` in asm.
- Treat 0 as "use your default language". For locale-aware applications use locale.library instead.

**See also:** locale.library
