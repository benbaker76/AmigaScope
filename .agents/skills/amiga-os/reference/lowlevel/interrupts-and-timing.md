# lowlevel.library: vertical-blank and timer interrupts, elapsed time

[AddVBlankInt](#addvblankint) runs a routine every vertical blank; [AddTimerInt](#addtimerint) grabs a
free CIA timer for a routine, which [StartTimerInt](#starttimerint) arms (one-shot or repeating, up to
90 ms) and [StopTimerInt](#stoptimerint) halts. Every Add has a matching Rem that must run before the
program exits. All routines follow the
[routine contract](index.md#interrupt-routines-addkbint-addtimerint-addvblankint): A1 = data,
preserve D2-D7/A2-A4, return D0 = 0. [ElapsedTime](#elapsedtime) measures intervals from the E-clock
without any interrupt.

## AddVBlankInt
`APTR AddVBlankInt(CONST APTR intRoutine, CONST APTR intData)` — LVO -108 (-$6C)
Registers: intRoutine=A0, intData=A1; result in D0

Install a routine that is called on every vertical-blank interrupt.

- **intRoutine** — code called with A1 = `intData`, A5 = routine address; must preserve D2-D7 and
  A2-A4 and return D0 = 0.
- **intData** — value passed in A1.
- **Result** — handle for [RemVBlankInt](#remvblankint), or NULL if it could not be added.

Since V40.

### Example
```asm
        include "lvo/lowlevel_lib.i"

        move.l  _LowLevelBase,a6
        lea     FrameTick(pc),a0
        lea     framecount,a1
        jsr     _LVOAddVBlankInt(a6)
        move.l  d0,vbhandle
        beq     .novblank               ; already taken by another program
        ; ... main loop reads framecount ...
        move.l  vbhandle,a1
        jsr     _LVORemVBlankInt(a6)

FrameTick:                              ; A1 = framecount
        addq.l  #1,(a1)
        moveq   #0,d0                   ; required
        rts

        section bss,bss
vbhandle:       ds.l    1
framecount:     ds.l    1
```

### Gotchas
- Only ONE routine can be added system-wide: always check for NULL. For shared, prioritised
  vertical-blank code use exec [AddIntServer](../exec/interrupts.md#addintserver) with `INTB_VERTB`.
- Must be removed with [RemVBlankInt](#remvblankint) before exit (unless you reboot).
- Interrupt context: no blocking calls; keep it short.

**See also:** [RemVBlankInt](#remvblankint), [AddTimerInt](#addtimerint)

## RemVBlankInt
`VOID RemVBlankInt(APTR intHandle)` — LVO -114 (-$72)
Registers: intHandle=A1; no result

Remove the vertical-blank routine added with AddVBlankInt.

- **intHandle** — handle from [AddVBlankInt](#addvblankint); NULL does nothing.

Since V40.

**See also:** [AddVBlankInt](#addvblankint)

## AddTimerInt
`APTR AddTimerInt(CONST APTR intRoutine, CONST APTR intData)` — LVO -78 (-$4E)
Registers: intRoutine=A0, intData=A1; result in D0

Allocate an unused CIA timer and attach a routine to its interrupt, initially stopped.

- **intRoutine** — code called on each timer interrupt with A1 = `intData`, A5 = routine address;
  preserve D2-D7/A2-A4, return D0 = 0.
- **intData** — value passed in A1.
- **Result** — handle for StartTimerInt/StopTimerInt/RemTimerInt, or NULL if no timer was free.

The timer is taken through cia.resource from whichever CIA timer is unallocated, so which one you get
can differ between runs. Nothing runs until [StartTimerInt](#starttimerint).

Since V40.

### Example
```asm
        include "lvo/lowlevel_lib.i"

        move.l  _LowLevelBase,a6
        lea     PlayerTick(pc),a0
        move.l  #songdata,a1
        jsr     _LVOAddTimerInt(a6)
        move.l  d0,tihandle
        beq     .notimer                ; all CIA timers in use
        move.l  d0,a1
        move.l  #20000,d0               ; 20000 us = 50 Hz
        moveq   #1,d1                   ; continuous
        jsr     _LVOStartTimerInt(a6)
        ; ... music plays ...
        move.l  tihandle,a1
        jsr     _LVOStopTimerInt(a6)
        move.l  tihandle,a1
        jsr     _LVORemTimerInt(a6)

PlayerTick:                             ; A1 = songdata
        ; ... advance the replay routine ...
        moveq   #0,d0
        rts

        section bss,bss
tihandle:       ds.l    1
songdata:       ds.l    1
```

### Gotchas
- One timer per AddTimerInt: call it once, and RemTimerInt before calling it again.
- The routine runs at CIA interrupt level (level 6 if the timer is on CIA-B): keep it very short.
- A NULL result is normal on a busy system (timer.device, other replay routines hold timers):
  handle it, e.g. fall back to [AddVBlankInt](#addvblankint).
- The autodoc text names the start call "StartIntTimer"; the function is StartTimerInt.

**See also:** [StartTimerInt](#starttimerint), [StopTimerInt](#stoptimerint), [RemTimerInt](#remtimerint), cia.resource [AddICRVector](../cia/cia.md#addicrvector)

## StartTimerInt
`VOID StartTimerInt(APTR intHandle, ULONG timeInterval, LONG continuous)` — LVO -96 (-$60)
Registers: intHandle=A1, timeInterval=D0, continuous=D1; no result

Start the stopped CIA timer of an AddTimerInt handle with a given interval.

- **intHandle** — handle from [AddTimerInt](#addtimerint).
- **timeInterval** — microseconds between interrupts, at most **90000**; larger values give
  unpredictable results.
- **continuous** — FALSE (0) for a single interrupt, TRUE for repeated interrupts.

The limit comes from the 16-bit CIA counter: 65535 E-clock ticks are about 92 ms (PAL 709379 Hz,
NTSC 715909 Hz). For longer periods count several interrupts.

Since V40.

### Gotchas
- `continuous` is a BOOL in the autodoc and SFD (LONG in the clib prototype): pass 0 or 1 in D1.
- Resolution is one E-clock tick (about 1.4 us); the interval is not exact.

**See also:** [StopTimerInt](#stoptimerint), [AddTimerInt](#addtimerint), [RemTimerInt](#remtimerint)

## StopTimerInt
`VOID StopTimerInt(APTR intHandle)` — LVO -90 (-$5A)
Registers: intHandle=A1; no result

Stop the timer of an AddTimerInt handle, typically a continuous one.

- **intHandle** — handle from [AddTimerInt](#addtimerint).

Since V40.

**See also:** [StartTimerInt](#starttimerint), [RemTimerInt](#remtimerint)

## RemTimerInt
`VOID RemTimerInt(APTR intHandle)` — LVO -84 (-$54)
Registers: intHandle=A1; no result

Detach the timer routine and give its CIA timer back.

- **intHandle** — handle from [AddTimerInt](#addtimerint); NULL does nothing.

Since V40.

### Gotchas
- Every successful AddTimerInt needs a RemTimerInt before the program exits.

**See also:** [AddTimerInt](#addtimerint), [StopTimerInt](#stoptimerint)

## ElapsedTime
`ULONG ElapsedTime(struct EClockVal *context)` — LVO -102 (-$66)
Registers: context=A0; result in D0

Return the time since the last call with this context, as 16.16 fixed-point seconds.

- **context** — `struct EClockVal` (`ev_hi`, `ev_lo`; devices/timer.h). Zero it before the first
  call and reuse the same structure afterwards: it holds the previous E-clock reading.
- **Result** — upper 16 bits = whole seconds, lower 16 bits = fraction of a second (1/65536 s,
  about 15 us per step). Saturates at the maximum (the autodoc says "about 16 hours").

Built on timer.device ReadEClock. Precision is about 20 us, accuracy only about 200 us.

Since V40.

### Example
```c
#include <proto/lowlevel.h>
#include <devices/timer.h>

extern struct Library *LowLevelBase;

static struct EClockVal frameclock;     /* zero-initialised */

void FrameTimerInit(void)
{
    ElapsedTime(&frameclock);           /* first result is meaningless */
}

ULONG FrameMillis(void)
{
    ULONG t = ElapsedTime(&frameclock);         /* 16.16 seconds */
    return (t >> 16) * 1000 + (((t & 0xFFFF) * 1000) >> 16);
}
```

### Gotchas
- The FIRST call's result is garbage: prime the context once and ignore it.
- Use a separate EClockVal for each independent measurement.

**See also:** timer.device ReadEClock, [StartTimerInt](#starttimerint)
