# timer.device: timing recipes

How to sleep, tick, measure and pace frames under the OS without busy-waiting. Every program
below is complete. Each was built with Bartman's m68k-amiga-elf-gcc using the amiga-debug
template flags (`-m68000 -Ofast -nostdlib`, linked with the template's support files), and each
runs from a CLI because it prints through dos.library.

## Choosing a timing method

| Need | Use | Why |
|---|---|---|
| Coarse sleep in a Process | dos [Delay](../dos/time.md#delay) | 50 ticks/s, one call |
| Sleep that Ctrl-C or other events can end | TR_ADDREQUEST with SendIO + Wait | see [Delay without busy-waiting](#delay-without-busy-waiting) |
| Regular ticks (music, logic, polling) | absolute deadlines on `UNIT_WAITECLOCK` | no drift, see [periodic ticks](#periodic-ticks-with-drift-correction) |
| Once a second or slower | `UNIT_WAITUNTIL` or `UNIT_VBLANK` | cheap and stable |
| Benchmark / profile code | [ReadEClock](functions.md#readeclock) | about 0.7 MHz counter, see [measuring](#measuring-elapsed-time-with-readeclock) |
| Once per displayed frame | graphics [WaitTOF](../graphics/blitter-and-timing.md#waittof) | locked to the vertical blank, see [frame pacing](#frame-pacing-for-games) |

A software delay loop (`for (i = 0; i < 100000; i++);`), polling `VHPOSR`, or calling
GetSysTime/CheckIO in a loop burns CPU that other tasks need, and it runs at different speeds on
every CPU. Always sleep in Wait (DoIO and WaitTOF do that for you).

## Delay without busy-waiting

A blocking DoIO of [TR_ADDREQUEST](commands.md#tr_addrequest) is the simplest sleep. When the
wait must end early on Ctrl-C, an IDCMP message or another port, SendIO the request and Wait on
the timer port's signal together with the others. If the timer is not the reason you woke up,
AbortIO it and always WaitIO.

```c
/* sleep.c -- wait without busy-waiting; Ctrl-C cuts the wait short */
#include <proto/exec.h>
#include <proto/dos.h>
#include <exec/execbase.h>
#include <devices/timer.h>
#include <dos/dos.h>

struct ExecBase   *SysBase;
struct DosLibrary *DOSBase;

/* TRUE = the full time elapsed, FALSE = interrupted by Ctrl-C */
static BOOL SleepBreakable(struct timerequest *tr, ULONG secs, ULONG micros)
{
    ULONG portsig = 1UL << tr->tr_node.io_Message.mn_ReplyPort->mp_SigBit;

    tr->tr_node.io_Command = TR_ADDREQUEST;
    tr->tr_time.tv_secs    = secs;
    tr->tr_time.tv_micro   = micros;            /* must be 0..999999 */
    SendIO((struct IORequest *)tr);

    for (;;) {
        ULONG sigs = Wait(portsig | SIGBREAKF_CTRL_C);
        if (CheckIO((struct IORequest *)tr))    /* replied: done (ignore stale signals) */
            break;
        if (sigs & SIGBREAKF_CTRL_C) {
            AbortIO((struct IORequest *)tr);
            break;
        }
    }
    WaitIO((struct IORequest *)tr);             /* ALWAYS collect it, aborted or not */
    return tr->tr_node.io_Error == 0;           /* IOERR_ABORTED after AbortIO */
}

int main(void)
{
    struct MsgPort     *port;
    struct timerequest *tr = NULL;
    int rc = RETURN_FAIL;

    SysBase = *((struct ExecBase **)4UL);
    DOSBase = (struct DosLibrary *)OpenLibrary((CONST_STRPTR)"dos.library", 37);
    if (!DOSBase)
        return rc;

    port = CreateMsgPort();
    if (port)
        tr = (struct timerequest *)CreateIORequest(port, sizeof(struct timerequest));
    if (tr && OpenDevice((CONST_STRPTR)TIMERNAME, UNIT_VBLANK, (struct IORequest *)tr, 0) == 0) {
        PutStr((CONST_STRPTR)"Sleeping 5 s (Ctrl-C aborts)\n");
        rc = SleepBreakable(tr, 5, 0) ? RETURN_OK : RETURN_WARN;
        CloseDevice((struct IORequest *)tr);    /* request is idle here */
    }
    DeleteIORequest(tr);                        /* NULL-safe */
    DeleteMsgPort(port);                        /* NULL-safe */
    CloseLibrary((struct Library *)DOSBase);
    return rc;
}
```

- The `CheckIO` test makes the loop ignore a stale port signal left over from an earlier
  request.
- For an IDCMP timeout add `1UL << win->UserPort->mp_SigBit` to the Wait mask and handle the
  window messages the same way.
- `UNIT_VBLANK` is right for seconds-long waits. For waits under about half a second open
  `UNIT_MICROHZ` instead: VBLANK resolution is one vertical-blank interval.

## Periodic ticks with drift correction

Re-sending a relative 20 ms request after each tick drifts: every period also includes your
work time and the scheduling delay before the next SendIO. Schedule against **absolute
deadlines** instead, computed as the previous deadline plus one period (never "now + period"):

- `UNIT_WAITECLOCK` replies when ReadEClock reaches the `EClockVal` in `tr_time`: precise, and no
  other program can set the E-clock.
- The period in E-clock ticks is rarely an integer (709379 / 50 = 14187.58). Carry the remainder
  so the long-term rate is exact.
- When the program falls behind (disk I/O, a higher-priority task), skip the missed deadlines
  rather than firing a burst of late ticks.

```c
/* ticker.c -- drift-free 50 Hz ticks with UNIT_WAITECLOCK absolute deadlines */
#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/timer.h>
#include <exec/execbase.h>
#include <devices/timer.h>
#include <dos/dos.h>

struct ExecBase   *SysBase;
struct DosLibrary *DOSBase;
struct Device     *TimerBase;                   /* name used by <proto/timer.h> */

/* 64-bit E-clock helpers in plain 32-bit C (the template links no 64-bit libgcc helpers) */
static void EClockAdd(struct EClockVal *v, ULONG ticks)
{
    ULONG lo = v->ev_lo + ticks;
    if (lo < v->ev_lo)                          /* carry into the high longword */
        v->ev_hi++;
    v->ev_lo = lo;
}

static BOOL EClockBefore(const struct EClockVal *a, const struct EClockVal *b)
{
    return a->ev_hi < b->ev_hi || (a->ev_hi == b->ev_hi && a->ev_lo < b->ev_lo);
}

struct Ticker {
    struct timerequest *tr;                     /* opened on UNIT_WAITECLOCK */
    struct EClockVal    next;                   /* absolute deadline of the next tick */
    ULONG               hz, step, frac, acc;
};

static void TickerAdvance(struct Ticker *t)
{
    ULONG s = t->step;
    t->acc += t->frac;                          /* carry the fractional E-clock tick */
    if (t->acc >= t->hz) {
        t->acc -= t->hz;
        s++;
    }
    EClockAdd(&t->next, s);
}

static void TickerStart(struct Ticker *t, ULONG hz)
{
    ULONG freq = ReadEClock(&t->next);          /* first deadline = now + one period */
    t->hz   = hz;
    t->step = freq / hz;
    t->frac = freq % hz;
    t->acc  = 0;
    TickerAdvance(t);
}

static void TickerArm(struct Ticker *t)
{
    struct EClockVal *ev = (struct EClockVal *)&t->tr->tr_time;  /* same 8 bytes */
    t->tr->tr_node.io_Command = TR_ADDREQUEST;
    ev->ev_hi = t->next.ev_hi;
    ev->ev_lo = t->next.ev_lo;
    SendIO((struct IORequest *)t->tr);
}

/* after the reply: step the deadline, skipping periods already missed; returns skips */
static ULONG TickerNext(struct Ticker *t)
{
    struct EClockVal now;
    ULONG skipped = 0;

    ReadEClock(&now);
    TickerAdvance(t);
    while (EClockBefore(&t->next, &now)) {
        TickerAdvance(t);
        skipped++;
    }
    return skipped;
}

int main(void)
{
    struct MsgPort *port;
    struct Ticker   t;
    ULONG ticks = 0, skipped = 0;
    int rc = RETURN_FAIL;

    SysBase = *((struct ExecBase **)4UL);
    if (SysBase->LibNode.lib_Version < 36)      /* UNIT_WAITECLOCK / ReadEClock need V36 */
        return rc;
    DOSBase = (struct DosLibrary *)OpenLibrary((CONST_STRPTR)"dos.library", 37);
    if (!DOSBase)
        return rc;

    t.tr = NULL;
    port = CreateMsgPort();
    if (port)
        t.tr = (struct timerequest *)CreateIORequest(port, sizeof(struct timerequest));
    if (t.tr && OpenDevice((CONST_STRPTR)TIMERNAME, UNIT_WAITECLOCK, (struct IORequest *)t.tr, 0) == 0) {
        ULONG portsig = 1UL << port->mp_SigBit;

        TimerBase = t.tr->tr_node.io_Device;
        TickerStart(&t, 50);
        while (ticks < 250) {                   /* 5 seconds */
            ULONG sigs;
            TickerArm(&t);
            sigs = Wait(portsig | SIGBREAKF_CTRL_C);
            if (sigs & SIGBREAKF_CTRL_C) {
                if (!CheckIO((struct IORequest *)t.tr))
                    AbortIO((struct IORequest *)t.tr);
                WaitIO((struct IORequest *)t.tr);
                break;
            }
            WaitIO((struct IORequest *)t.tr);   /* collect before re-arming */
            ticks++;
            /* ... periodic work here ... */
            skipped += TickerNext(&t);
        }
        Printf((CONST_STRPTR)"%ld ticks, %ld skipped\n", (LONG)ticks, (LONG)skipped);
        rc = RETURN_OK;
        CloseDevice((struct IORequest *)t.tr);
        TimerBase = NULL;
    }
    DeleteIORequest(t.tr);
    DeleteMsgPort(port);
    CloseLibrary((struct Library *)DOSBase);
    return rc;
}
```

For once-a-second events (a clock display, polling a file), `UNIT_WAITUNTIL` with system time is
cheaper. It has VBLANK resolution, and it jumps when someone sets the clock: a clock set forward
makes the deadline already due, and a clock set back makes the wait long.

```c
/* once-per-second tick aligned to whole seconds -- tr opened on UNIT_WAITUNTIL */
struct timeval next, one;

one.tv_secs  = 1;
one.tv_micro = 0;
GetSysTime(&next);
next.tv_micro = 0;
for (;;) {
    AddTime(&next, &one);
    tr->tr_node.io_Command = TR_ADDREQUEST;
    tr->tr_time = next;                         /* absolute system time */
    DoIO((struct IORequest *)tr);               /* or SendIO + Wait with Ctrl-C */
    UpdateClockDisplay();
}
```

## Measuring elapsed time with ReadEClock

[ReadEClock](functions.md#readeclock) returns the 64-bit E-clock count and the count rate
(709379 Hz PAL, 715909 Hz NTSC). Take two samples and subtract. GetSysTime also works, but it
jumps if another program sets the clock.

Bartman's template links no libgcc. `unsigned long long` multiplication or division fails with
undefined `__muldi3`/`__udivdi3`, so the conversion below uses only 32-bit arithmetic, which the
template's support code provides. It is exact to the microsecond.

```c
/* elapsed.c -- time a piece of code with ReadEClock */
#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/graphics.h>
#include <proto/timer.h>
#include <exec/execbase.h>
#include <graphics/gfxbase.h>
#include <devices/timer.h>
#include <dos/dos.h>

struct ExecBase   *SysBase;
struct DosLibrary *DOSBase;
struct GfxBase    *GfxBase;
struct Device     *TimerBase;

/* end - start as a timeval, using 32-bit maths only.
   Valid while the difference is below 2^32 E-clock ticks (about 100 minutes). */
static void EClockElapsed(const struct EClockVal *start, const struct EClockVal *end,
                          ULONG freq, struct timeval *out)
{
    ULONG ticks = end->ev_lo - start->ev_lo;    /* low longword of the 64-bit difference */
    ULONG rem   = ticks % freq;                 /* < freq (~0.7 MHz), so rem * 1000 fits */
    ULONG ms    = rem * 1000 / freq;
    ULONG r2    = rem * 1000 % freq;

    out->tv_secs  = ticks / freq;
    out->tv_micro = ms * 1000 + r2 * 1000 / freq;
}

int main(void)
{
    struct MsgPort     *port = NULL;
    struct timerequest *tr = NULL;
    struct EClockVal    t0, t1;
    struct timeval      dt;
    ULONG freq;
    int   i, rc = RETURN_FAIL;

    SysBase = *((struct ExecBase **)4UL);
    DOSBase = (struct DosLibrary *)OpenLibrary((CONST_STRPTR)"dos.library", 37);
    GfxBase = (struct GfxBase *)OpenLibrary((CONST_STRPTR)"graphics.library", 37);
    if (DOSBase && GfxBase && (port = CreateMsgPort()) != NULL)
        tr = (struct timerequest *)CreateIORequest(port, sizeof(struct timerequest));
    if (tr && OpenDevice((CONST_STRPTR)TIMERNAME, UNIT_ECLOCK, (struct IORequest *)tr, 0) == 0) {
        TimerBase = tr->tr_node.io_Device;      /* any unit gives the same base */

        freq = ReadEClock(&t0);
        for (i = 0; i < 50; i++)                /* the code being measured */
            WaitTOF();
        ReadEClock(&t1);

        EClockElapsed(&t0, &t1, freq, &dt);
        Printf((CONST_STRPTR)"50 x WaitTOF: %ld.%06ld s (E-clock %ld Hz)\n",
               (LONG)dt.tv_secs, (LONG)dt.tv_micro, (LONG)freq);
        rc = RETURN_OK;

        CloseDevice((struct IORequest *)tr);    /* TimerBase is invalid from here on */
        TimerBase = NULL;
    }
    DeleteIORequest(tr);
    DeleteMsgPort(port);
    CloseLibrary((struct Library *)GfxBase);
    CloseLibrary((struct Library *)DOSBase);
    return rc;
}
```

- Taking only the low longword is right for intervals below 2^32 ticks (about 100 minutes). For
  longer spans borrow into `ev_hi`, or use GetSysTime + [SubTime](functions.md#subtime).
- `rem * 1000` cannot overflow while the rate is below 4294967 Hz. The E-clock runs at about
  0.7 MHz.
- ReadEClock itself costs time. To time a very short piece of code, run it N times between the
  two samples and divide.

## Frame pacing for games

| Method | Locked to the display | Rate | When a frame takes too long |
|---|---|---|---|
| graphics WaitTOF | yes (after the vertical blank) | 50 Hz PAL, 60 Hz NTSC | waits for the next blank: 50 fps drops straight to 25 |
| `UNIT_WAITECLOCK` deadlines | no | any | skip or catch up as you choose |
| `UNIT_VBLANK` requests | no (power-supply strobe) | multiples of a blank interval | coarse; not a frame clock |
| VERTB server or copper interrupt | yes | display rate | bare-metal / interrupt code, see the amiga-hardware skill |

- **Render with WaitTOF.** Drawing, scrolling or swapping buffers right after it keeps the display
  change inside the blanking period.
- **Game logic must not assume 50 Hz.** A WaitTOF-locked game runs 20% faster on a 60 Hz NTSC
  display, and slows down whenever a frame is missed. Either scale movement by
  `(GfxBase->DisplayFlags & PAL)`, or run the logic in fixed steps from an E-clock accumulator as
  below. That keeps game speed the same on both displays and through dropped frames.
- Cap the catch-up. After a long stall (disk loading, a requester) drop the backlog instead of
  running hundreds of logic steps in one frame.
- Timer requests are not beam-synchronous. Pacing rendering with them tears or judders, so keep
  them for logic, music and non-display work.

```c
/* pacing.c -- fixed 50 Hz game logic, rendering synced with WaitTOF (50 or 60 Hz display) */
#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/graphics.h>
#include <proto/timer.h>
#include <exec/execbase.h>
#include <graphics/gfxbase.h>
#include <devices/timer.h>
#include <dos/dos.h>

#define LOGIC_HZ     50
#define MAX_CATCHUP  4                          /* logic steps allowed per displayed frame */

struct ExecBase   *SysBase;
struct DosLibrary *DOSBase;
struct GfxBase    *GfxBase;
struct Device     *TimerBase;

static ULONG logicSteps, framesDrawn;

static void UpdateGame(void) { logicSteps++; }  /* move objects by one fixed step */
static void DrawGame(void)   { framesDrawn++; } /* render the current state */

static void GameLoop(ULONG seconds)
{
    struct EClockVal last, now;
    ULONG freq = ReadEClock(&last);
    ULONG step = freq / LOGIC_HZ;               /* E-clock ticks per logic step */
    ULONG acc  = 0;

    while (logicSteps < seconds * LOGIC_HZ) {
        ULONG n = 0;

        if (SetSignal(0, SIGBREAKF_CTRL_C) & SIGBREAKF_CTRL_C)
            break;
        WaitTOF();                              /* one displayed frame */
        ReadEClock(&now);
        acc += now.ev_lo - last.ev_lo;          /* 32-bit delta: fine for gaps < ~100 min */
        last = now;

        while (acc >= step && n < MAX_CATCHUP) {
            UpdateGame();
            acc -= step;
            n++;
        }
        if (n == MAX_CATCHUP && acc >= step)    /* long stall (disk access...): drop the backlog */
            acc = 0;
        DrawGame();
    }
}

int main(void)
{
    struct MsgPort     *port = NULL;
    struct timerequest *tr = NULL;
    int rc = RETURN_FAIL;

    SysBase = *((struct ExecBase **)4UL);
    DOSBase = (struct DosLibrary *)OpenLibrary((CONST_STRPTR)"dos.library", 37);
    GfxBase = (struct GfxBase *)OpenLibrary((CONST_STRPTR)"graphics.library", 37);
    if (DOSBase && GfxBase && (port = CreateMsgPort()) != NULL)
        tr = (struct timerequest *)CreateIORequest(port, sizeof(struct timerequest));
    if (tr && OpenDevice((CONST_STRPTR)TIMERNAME, UNIT_ECLOCK, (struct IORequest *)tr, 0) == 0) {
        TimerBase = tr->tr_node.io_Device;
        GameLoop(5);
        Printf((CONST_STRPTR)"%s display: %ld frames drawn, %ld logic steps\n",
               (ULONG)((GfxBase->DisplayFlags & PAL) ? "PAL" : "NTSC"),
               (LONG)framesDrawn, (LONG)logicSteps);
        rc = RETURN_OK;
        CloseDevice((struct IORequest *)tr);
        TimerBase = NULL;
    }
    DeleteIORequest(tr);
    DeleteMsgPort(port);
    CloseLibrary((struct Library *)GfxBase);
    CloseLibrary((struct Library *)DOSBase);
    return rc;
}
```

`freq / LOGIC_HZ` truncates (709379 / 50 loses 0.58 ticks per step, 0.004%). That is fine for
game logic; carry the remainder as in the ticker above if exact long-term timing matters.

With the OS switched off (your own interrupt vectors, `INTF_VERTB` disabled), neither WaitTOF
nor timer.device runs: count VERTB interrupts or program the CIA timers yourself (amiga-hardware
skill).

## Common mistakes

- Sending a timer request that is still pending, or replied but not yet collected. Use one
  request per concurrent wait.
- AbortIO without the following WaitIO, then reusing, closing or freeing the request.
- Forgetting to reload `tr_time`: it comes back zeroed, so the next send returns at once.
- `tv_micro` of 1000000 or more: timevals must be normalised.
- Reading [CmpTime](functions.md#cmptime) like strcmp. It returns -1 when the first time is the
  LATER one.
- Periodic ticks from relative requests (drift), or firing every missed tick after a stall.
- `UNIT_VBLANK` for sub-frame precision, or any timer unit for display sync.
- Calling timer functions without TimerBase, or after CloseDevice made it invalid.
- `unsigned long long` maths on E-clock values in a Bartman template build (undefined
  `__udivdi3`).
- dos Delay from a plain exec Task or interrupt, or timer DoIO/WaitIO inside interrupt code.

**See also:** [timer.device intro](index.md), [TR_ADDREQUEST](commands.md#tr_addrequest), [AbortIO](commands.md#abortio), [ReadEClock](functions.md#readeclock), [GetSysTime](functions.md#getsystime)
