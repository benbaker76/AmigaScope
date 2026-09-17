# timer.device: functions

Five library-style calls through TimerBase, the `io_Device` of any opened timer request (see
[opening](index.md#opening-the-device-and-getting-timerbase)). GetSysTime reads the system clock
as a `timeval`; AddTime, SubTime and CmpTime do arithmetic on timevals; ReadEClock reads the
64-bit E-clock counter for fine interval timing. All five may be called from interrupts. None of
them waits: for sleeping use [TR_ADDREQUEST](commands.md#tr_addrequest).

## GetSysTime
`VOID GetSysTime(struct timeval *dest)` — LVO -66 (-$42)
Registers: dest=A0; no result

Read the current system time into a timeval.

- **dest** — timeval to fill with seconds and microseconds of system time.
- **Result** — none; A0 is preserved.

Since V36.

The value rises monotonically and is unique per call unless the time is set backwards. It is
cheaper than a [TR_GETSYSTIME](commands.md#tr_getsystime) request.

### Example
```c
#include <proto/timer.h>
#include <proto/dos.h>

struct timeval start, now;

GetSysTime(&start);
/* ... work ... */
GetSysTime(&now);
SubTime(&now, &start);                          /* now = elapsed time */
Printf((CONST_STRPTR)"took %ld.%06ld s\n", (LONG)now.tv_secs, (LONG)now.tv_micro);
```

### Gotchas
- V36+. On 1.x send TR_GETSYSTIME instead.
- Another program can move the clock with TR_SETSYSTIME (clock setters, network time tools), so
  intervals measured with it can jump. [ReadEClock](#readeclock) has no setter and suits
  benchmarks and frame timing better.

**See also:** [TR_GETSYSTIME](commands.md#tr_getsystime), [TR_SETSYSTIME](commands.md#tr_setsystime), [SubTime](#subtime), [ReadEClock](#readeclock)

## AddTime
`VOID AddTime(struct timeval *dest, CONST struct timeval *src)` — LVO -42 (-$2A)
Registers: dest=A0, src=A1; no result

Add one timeval to another in place: dest = dest + src.

- **dest** — first operand, overwritten with the sum.
- **src** — amount to add; not modified.
- **Result** — none; A0 and A1 are preserved.

### Example
```c
/* absolute deadline one and a half seconds from now */
struct timeval deadline, period;

period.tv_secs  = 1;                            /* assign by name: see the Bartman */
period.tv_micro = 500000;                       /* timeval note in index.md */
GetSysTime(&deadline);
AddTime(&deadline, &period);
```

```asm
        move.l  _TimerBase,a6
        lea     deadline,a0
        lea     period,a1
        jsr     _LVOAddTime(a6)         ; deadline += period; A0/A1 unchanged
```

### Gotchas
- Both timevals must be normalised (`tv_micro` 0..999999): `tv_secs` = 0, `tv_micro` = 1500000
  is not 1.5 seconds.

**See also:** [SubTime](#subtime), [CmpTime](#cmptime)

## SubTime
`VOID SubTime(struct timeval *dest, CONST struct timeval *src)` — LVO -48 (-$30)
Registers: dest=A0, src=A1; no result

Subtract one timeval from another in place: dest = dest - src.

- **dest** — minuend, overwritten with the difference.
- **src** — amount to subtract; not modified.
- **Result** — none; A0 and A1 are preserved.

### Example
```c
/* how long until the deadline? (only if it is still in the future) */
struct timeval now, left;

GetSysTime(&now);
if (CmpTime(&deadline, &now) < 0) {             /* deadline later than now */
    left = deadline;
    SubTime(&left, &now);
}
```

### Gotchas
- The fields are ULONG, so there are no negative timevals. When `src` is later than `dest` the
  result is meaningless. Compare with [CmpTime](#cmptime) first when that can happen.
- Inputs must be normalised, as for AddTime.

**See also:** [AddTime](#addtime), [CmpTime](#cmptime)

## CmpTime
`LONG CmpTime(CONST struct timeval *dest, CONST struct timeval *src)` — LVO -54 (-$36)
Registers: dest=A0, src=A1; result in D0

Compare two timevals; note the result is -1 when the FIRST argument is the later time.

- **dest**, **src** — the timevals to compare; neither is modified.
- **Result** — `0` equal; `-1` when dest is later (more time) than src; `+1` when dest is
  earlier (less time) than src. A0 and A1 are preserved.

### Example
```c
struct timeval now;

GetSysTime(&now);
if (CmpTime(&now, &deadline) <= 0)              /* now >= deadline */
    FireAlarm();
```

```asm
        move.l  _TimerBase,a6
        lea     now,a0
        lea     deadline,a1
        jsr     _LVOCmpTime(a6)
        tst.l   d0
        ble     .due                    ; now later than or equal to deadline
```

### Gotchas
- The sign is the reverse of strcmp/memcmp. The autodoc's BUGS section says older versions of
  the document described it the other way round, while the code never changed. Code written
  from those docs is inverted.
- For a sort comparator in "ascending time" order, negate the result.

**See also:** [AddTime](#addtime), [SubTime](#subtime)

## ReadEClock
`ULONG ReadEClock(struct EClockVal *dest)` — LVO -60 (-$3C)
Registers: dest=A0; result in D0

Read the 64-bit E-clock counter; returns the counter rate in ticks per second.

- **dest** — EClockVal to fill: `ev_hi` = upper 32 bits, `ev_lo` = lower 32 bits of the count.
- **Result** — E-clock frequency in ticks per second (709379 on PAL and 715909 on NTSC machines
  per the HRM CIA chapter; use the returned value). A0 is preserved.

Since V36.

Very low overhead and meant for timing short intervals. `UNIT_WAITECLOCK` requests compare against
this same counter.

### Example
```c
struct EClockVal t0, t1;
ULONG freq, ticks;

freq = ReadEClock(&t0);
DoTheWork();
ReadEClock(&t1);
ticks = t1.ev_lo - t0.ev_lo;                    /* exact while the interval < 2^32 ticks */
/* ms ~= ticks / (freq / 1000), within 0.2%; exact 32-bit maths: timing-recipes.md */
```

```asm
        move.l  a6,-(sp)
        move.l  _TimerBase,a6
        lea     start,a0
        jsr     _LVOReadEClock(a6)      ; D0 = ticks per second, A0 unchanged
        move.l  d0,efreq
        ;       ... measured code ...
        lea     stop,a0
        jsr     _LVOReadEClock(a6)
        move.l  (sp)+,a6
        move.l  stop+EV_LO,d0
        sub.l   start+EV_LO,d0          ; D0 = elapsed ticks

        section vars,bss
efreq:  ds.l    1
start:  ds.b    EV_SIZE
stop:   ds.b    EV_SIZE
```

### Gotchas
- V36+.
- It is a 64-bit value. Subtracting only `ev_lo` is correct while the interval is below 2^32
  ticks (about 100 minutes). For longer spans do the borrow into `ev_hi`.
- Bartman's template links no libgcc: `unsigned long long` multiply/divide leaves undefined
  `__muldi3`/`__udivdi3` at link time. Convert ticks with 32-bit steps (see
  [measuring elapsed time](timing-recipes.md#measuring-elapsed-time-with-readeclock)).

**See also:** [GetSysTime](#getsystime), [TR_ADDREQUEST](commands.md#tr_addrequest), [timing recipes](timing-recipes.md)
