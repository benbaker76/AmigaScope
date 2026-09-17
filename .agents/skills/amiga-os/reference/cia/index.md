# cia.resource (ciaa.resource, ciab.resource)

The two 8520 CIAs are shared by the OS (keyboard, timer.device, disk index, parallel port) and by
programs. cia.resource arbitrates their five interrupt sources per chip: owning an interrupt bit
with [AddICRVector](cia.md#addicrvector) is also how you claim the matching hardware (a timer, the
serial register, the FLAG input). Register-level details of the chips: see the amiga-hardware skill.

## Two resources, one interface

| Resource | Name macro (`resources/cia.h` / `cia.i`) | Chip | CPU interrupt |
|---|---|---|---|
| `"ciaa.resource"` | `CIAANAME` | CIA-A at `$BFE001` | level 2 (INTB_PORTS) |
| `"ciab.resource"` | `CIABNAME` | CIA-B at `$BFD000` | level 6 (INTB_EXTER) |

- Get a base with exec [OpenResource](../exec/libraries-devices-resources.md#openresource); never
  OpenLibrary/CloseLibrary, and there is nothing to close. The asm name macros expand to a
  `dc.b 'ciaa.resource',0` line.
- Both resources have the same function table; the base in **A6** selects the chip. The LVOs start at
  -6 (resources have no Open/Close/Expunge vectors): `include "lvo/cia_lib.i"`.
- C: the prototypes take the resource base as an explicit first argument (there is no global base
  name): `AddICRVector(CiabBase, CIAICRB_TA, &myInt)`. Include `<proto/cia.h>`.
- The resource base has no public fields (`resources/ciabase.h`).
- Interrupt bit names and control-register bits are in `hardware/cia.h` / `hardware/cia.i`.

## ICR bits and who uses them

| Bit | `CIAICRB_` / `CIAICRF_` | Source | CIA-A (`ciaa.resource`) | CIA-B (`ciab.resource`) |
|---|---|---|---|---|
| 0 | `TA` / $01 | timer A underflow | used by the system (unverified) | normally free (unverified) |
| 1 | `TB` / $02 | timer B underflow | used by the system (unverified) | normally free (unverified) |
| 2 | `ALRM` / $04 | TOD alarm | TOD counts 50/60 Hz ticks; the OS timekeeping uses it (unverified) | TOD counts horizontal sync pulses (graphics, unverified) |
| 3 | `SP` / $08 | serial register full/empty | keyboard data (SP = KDAT, CNT = KCLK) | serial register unused; SP/CNT pins double as parallel BUSY/POUT |
| 4 | `FLG` / $10 | FLAG pin edge | parallel port ACK | disk INDEX pulse (disk.resource) |
| 7 | `IR` / `SETCLR` $80 | read: any interrupt; write: set/clear | | |

Sources: the 8520 appendix and interface chapter of the Hardware Reference Manual (TOD inputs, SP =
keyboard, INDEX on the CIA-B FLAG at level 6) and the timer.device autodoc (UNIT_MICROHZ runs on the
8520 timers). Which CIA-A/CIA-B timers a given Kickstart's timer.device takes is not stated in these
sources, and other programs (music replay routines, lowlevel.library
[AddTimerInt](../lowlevel/interrupts-and-timing.md#addtimerint)) grab timers too: never hardcode a
timer; ask the resource.

## Claiming a timer safely

1. `OpenResource` both `"ciaa.resource"` and `"ciab.resource"`. Any of the four timers will do (the
   autodoc says to try them until one succeeds). CIA-B timers are the ones usually free (unverified),
   but CIA-B interrupts at level 6 and blocks lower levels while your handler runs.
2. Disable, then `AddICRVector(base, CIAICRB_TA, &int)`. D0 = 0: you own timer A. Non-zero: D0 is
   the current owner's `struct Interrupt` -- try `CIAICRB_TB`, then the other CIA. If all four fail,
   exit cleanly.
3. Only AFTER owning the bit, program the timer: stop it in its control register (`CIACRAF_START` /
   `CIACRBF_START` = 0), set the latch (low byte, then high byte), choose continuous or one-shot, then
   start it. Change only your timer's bits in CRA/CRB (read-modify-write): CRA bit 6
   (`CIACRAF_SPMODE`) is the serial-port direction the CIA-A keyboard line depends on, CRA bit 7
   (`CIACRAF_TODIN`) and CRB bit 7 (`CIACRBF_ALARM`) belong to the TOD owner.
4. Enable. AddICRVector already enabled the interrupt; clear a stale flag with
   [SetICR](cia.md#seticr) and gate it with [AbleICR](cia.md#ableicr) if needed.
5. On exit: stop the timer, [RemICRVector](cia.md#remicrvector) (it also disables the bit).

Ticks: the timers count the E clock, 709379 Hz (PAL) / 715909 Hz (NTSC), available as
`SysBase->ex_EClockFrequency` (asm `ex_EClockFrequency(a6)`). For a rate in Hz,
`latch = EClockFrequency / rate` (50 Hz PAL: 14187); the 16-bit latch limits rates to 11 Hz and up.

The handler is a `struct Interrupt` (`is_Code`, `is_Data`, `ln_Name`; `ln_Type` = `NT_INTERRUPT`).
It runs in interrupt context with A1 = `is_Data`; the cia.resource autodocs do not list registers
(unverified): write it like an exec interrupt server (D0/D1/A0/A1/A5/A6 scratch, preserve the rest,
no blocking calls). The resource itself reads the ICR and calls the owner of each pending bit, so the
handler does not acknowledge anything (unverified).

## Rules

- Never read a CIA ICR yourself while the OS runs: reading clears every pending flag, and the
  system's handlers lose their interrupts. Use [SetICR](cia.md#seticr) with mask 0 to sample.
- Never write the ICR mask directly: use [AbleICR](cia.md#ableicr).
- Never assume a timer or port bit is free. Changing hardware state before owning it is forbidden.
- Bare-metal code that has disabled the OS (INTENA off, own level-2/6 vectors) talks to the
  registers directly instead: see the amiga-hardware skill.

## Files

- [cia.md](cia.md) -- AddICRVector, RemICRVector, AbleICR, SetICR.

<!-- FUNCTION TABLE -->
<!-- Generated by tools/skills/build_indexes.py - do not edit by hand. -->

## Functions

| Function | LVO | Registers | Summary |
|---|---|---|---|
| [AbleICR](cia.md#ableicr) | -18 | resource=A6, mask=D0 | Enable or disable CIA interrupt sources and return the previous enable mask. |
| [AddICRVector](cia.md#addicrvector) | -6 | resource=A6, iCRBit=D0, interrupt=A1 | Claim one CIA interrupt bit for a handler; fails with the owner if the bit is taken. |
| [RemICRVector](cia.md#remicrvector) | -12 | resource=A6, iCRBit=D0, interrupt=A1 | Release a CIA interrupt bit claimed with AddICRVector and disable its interrupt. |
| [SetICR](cia.md#seticr) | -24 | resource=A6, mask=D0 | Clear, cause or sample pending CIA interrupt flags without reading the ICR yourself. |

Machine-readable: [../data/cia.tsv](../data/cia.tsv)
