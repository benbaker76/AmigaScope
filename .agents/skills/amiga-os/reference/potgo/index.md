# potgo.resource

POTGO (`$DFF034`, write-only) controls the four "pot" pins of the two controller ports -- pin 5 and
pin 9 of each -- that carry the right and middle mouse buttons, the second and third joystick fire
buttons, analog paddles and the CD32 pad's serial data. One word holds the settings for all four
pins, so every writer must preserve the other users' bits. potgo.resource keeps that shared copy:
you allocate the bits you need, change them only through WritePotgo, and free them when done.
Register-level details (POTGO, POTGOR/POTINP, POT0DAT, POT1DAT): see the amiga-hardware skill.

## Opening

- Name `"potgo.resource"` (`POTGONAME` in `resources/potgo.h`; asm macro in `resources/potgo.i`).
- Get the base with exec [OpenResource](../exec/libraries-devices-resources.md#openresource); never
  OpenLibrary/CloseLibrary.
- C: global **`struct Library *PotgoBase`** (the name `<proto/potgo.h>` expects), `#include <proto/potgo.h>`.
  asm: A6 = the base, `include "lvo/potgo_lib.i"`; the LVOs start at -6.
- Calls follow the usual rule: D0, D1, A0, A1 scratch, arguments in D0/D1.

## POTGO bits as the resource names them

There are no NDK constants for these bits: define your own.

| Bit | Name | Mask | Pin | Meaning |
|---|---|---|---|---|
| 15 | OUTRY | $8000 | right port (1), pin 9 | 1 = pin is an output |
| 14 | DATRY | $4000 | right port (1), pin 9 | output level / input read back in POTINP |
| 13 | OUTRX | $2000 | right port (1), pin 5 | 1 = output |
| 12 | DATRX | $1000 | right port (1), pin 5 | data |
| 11 | OUTLY | $0800 | left port (0), pin 9 | 1 = output |
| 10 | DATLY | $0400 | left port (0), pin 9 (right mouse button) | data |
| 9 | OUTLX | $0200 | left port (0), pin 5 | 1 = output |
| 8 | DATLX | $0100 | left port (0), pin 5 (middle mouse button) | data |
| 7-1 | -- | | | write 0 (POTINP returns chip ID bits here) |
| 0 | START | $0001 | all input pins | discharge the pot capacitors and restart the POTxDAT counters |

Pin levels are read back from POTINP (`potinp` $016 in `hardware/custom.i`, also called POTGOR):
the same bit positions, 0 = pin pulled low (button pressed). Reading is always harmless.

## The allocation protocol

1. `granted = AllocPotBits(want)`. `want` holds the DATxx bit of every pin you use, the OUTxx bit
   as well if you will only drive that pin as an output, and START if you need to trigger pot
   counting on your input pins (allocate START together with those DATxx bits, with their OUTxx bits
   clear).
2. `granted` contains the START and DATxx bits you actually got (OUTxx bits in it mean nothing).
   Check `(granted & needed) == needed`, where `needed` is only the START/DATxx part of `want`; if
   not, `FreePotBits(granted)` and do without.
3. Drive pins with `WritePotgo(word, mask)`, where `mask` contains only bits you were granted
   (including their OUTxx partners). The resource merges your bits into the saved high byte, so
   other users' pin settings survive. START is never saved: it is written only by the call that
   sets it.
4. `FreePotBits(granted)` when finished.

A request fails for bits already allocated, for any bit while someone holds START, and for START
while someone holds input bits. To change an allocation that involves START, free everything you
hold and allocate again.

## Reading extra fire buttons

A button connects its pin to ground. Configure the pin as an output driven high (OUTxx = 1,
DATxx = 1): the pull-up keeps it at 1 until the button shorts it to 0. Then test the DATxx bit in
POTINP. The lines have large capacitors: allow up to about 300 us after changing the pin (Hardware
Reference Manual) before trusting the level.

| Button | Allocate and write | Read |
|---|---|---|
| joystick port (1), 2nd fire (pin 9) | `$C000` | POTINP bit 14 |
| joystick port (1), 3rd fire (pin 5) | `$3000` | POTINP bit 12 |
| mouse port (0), right button (pin 9) | `$0C00` | POTINP bit 10 |
| mouse port (0), middle button (pin 5) | `$0300` | POTINP bit 8 |

The mouse port's right button is normally handled by input.device, which holds those bits (unverified):
read the level from POTINP without allocating, or use lowlevel.library
[ReadJoyPort](../lowlevel/joyport.md#readjoyport) (`JPF_BUTTON_BLUE` = second button / right button,
`JPF_BUTTON_PLAY` = middle button).

## CD32 game controller

The CD32 pad sends its seven buttons serially (unverified summary, not in the NDK sources): the
computer drives pin 5 low through POTGO to switch the pad into shift mode, clocks it with pin 6 (the
normal fire line, CIA-A PRA bit 6/7 made an output through DDRA) and reads each button bit on pin 9
through POTINP. lowlevel.library's [ReadJoyPort](../lowlevel/joyport.md#readjoyport) does all of
this, allocating the potgo bits itself (`SJA_Reinitialize` frees them). Use it; if you write your
own reader under the OS, first allocate DATxx and OUTxx for both pins 5 and 9 of that port. No
resource arbitrates the CIA-A DDRA fire-line bit: change it under Disable and restore it afterwards.

## Why not poke POTGO directly

- POTGO is write-only: a raw `move.w #$ff00,$dff034` replaces the settings of all four pins at once
  and cannot preserve bits you cannot read, so other users' pin configuration (the mouse port's
  right button, lowlevel.library's pad reading) is silently overwritten.
- Writing START from one program restarts every pot counter, corrupting another program's analog
  reading.
- The resource merges and remembers the high byte for all users; only through WritePotgo do your
  settings and theirs coexist.
- A bare-metal game that has taken over the machine (no input.device running) may write POTGO
  directly: see the amiga-hardware skill.

## Files

- [potgo.md](potgo.md) -- AllocPotBits, WritePotgo, FreePotBits.

<!-- FUNCTION TABLE -->
<!-- Generated by tools/skills/build_indexes.py - do not edit by hand. -->

## Functions

| Function | LVO | Registers | Summary |
|---|---|---|---|
| [AllocPotBits](potgo.md#allocpotbits) | -6 | bits=D0 | Reserve bits of the shared POTGO register for your program. |
| [FreePotBits](potgo.md#freepotbits) | -12 | bits=D0 | Give back POTGO bits obtained with AllocPotBits. |
| [WritePotgo](potgo.md#writepotgo) | -18 | word=D0, mask=D1 | Set or clear your allocated POTGO bits, keeping every other user's settings. |

Machine-readable: [../data/potgo.tsv](../data/potgo.tsv)
