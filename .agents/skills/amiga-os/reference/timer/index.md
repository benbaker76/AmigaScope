# timer.device

The OS time base: it wakes a task after a delay or at an absolute time, keeps the system clock,
and offers five library-style calls (timeval arithmetic, system time, E-clock) through its device
base. Device name `"timer.device"` (`TIMERNAME`), request `struct timerequest` (`devices/timer.h`,
`devices/timer.i`), function base `TimerBase` (`struct Device *`). There is no library to open:
you open a unit with exec [OpenDevice](../exec/libraries-devices-resources.md#opendevice) and take
the base from the request.

## Units

The unit number passed to OpenDevice picks the time source and how `tr_time` is read.

| Unit | Value | `tr_time` holds | Source, resolution, accuracy | Use for |
|---|---|---|---|---|
| `UNIT_MICROHZ` | 0 | `timeval`, relative delay | 8520 CIA timer; precision about 2 microseconds, accuracy of the master clock, but drifts as system load rises | short, precise delays |
| `UNIT_VBLANK` | 1 | `timeval`, relative delay | power-supply 50/60 Hz strobe (E-clock where there is none); very stable and cheap, resolution one vertical-blank interval | waits of about 1/2 s and longer |
| `UNIT_ECLOCK` | 2 | `EClockVal`, relative count of E-clock ticks | same as `UNIT_MICROHZ` | precise delays in E-clock units |
| `UNIT_WAITUNTIL` | 3 | `timeval`, absolute system time | same as `UNIT_VBLANK` | alarms at a clock time |
| `UNIT_WAITECLOCK` | 4 | `EClockVal`, absolute E-clock value | same as `UNIT_ECLOCK` | drift-free periodic ticks |

- The absolute units reply once the system time (GetSysTime) or E-clock (ReadEClock) is
  greater than or equal to the value in the request.
- `UNIT_VBLANK` is a stable 50/60 Hz time base. It is **not** locked to the video beam: use
  graphics WaitTOF for display sync.
- Units 2-4 need V36 (unverified: the autodoc gives no version).
- Kickstart 1.2/1.3 mishandled very short requests: other pending requests could finish at
  the wrong time, which also made dos `Delay(0)` and `WaitForChar(fh, 0)` unreliable.

## Opening the device and getting TimerBase

```c
#include <proto/exec.h>
#include <proto/timer.h>
#include <devices/timer.h>

struct ExecBase *SysBase;
struct Device   *TimerBase;                 /* exact name used by the <proto/timer.h> inlines */

static struct MsgPort     *timerPort;
static struct timerequest *timerReq;

BOOL TimerOpen(ULONG unit)
{
    timerPort = CreateMsgPort();
    if (timerPort)
        timerReq = (struct timerequest *)CreateIORequest(timerPort, sizeof(struct timerequest));
    if (!timerReq)
        return FALSE;
    if (OpenDevice((CONST_STRPTR)TIMERNAME, unit, (struct IORequest *)timerReq, 0) != 0)
        return FALSE;                       /* 0 = success, unlike OpenLibrary */
    TimerBase = timerReq->tr_node.io_Device;
    return TRUE;
}

void TimerClose(void)                       /* every request must be idle first */
{
    if (TimerBase)
        CloseDevice((struct IORequest *)timerReq);
    TimerBase = NULL;
    DeleteIORequest(timerReq);              /* NULL-safe */
    DeleteMsgPort(timerPort);
    timerReq  = NULL;
    timerPort = NULL;
}
```

```asm
        include "exec/io.i"
        include "devices/timer.i"
        include "lvo/exec_lib.i"
        include "lvo/timer_lib.i"

; after OpenDevice returned 0 for the request in timereq
        move.l  timereq,a1
        move.l  IO_DEVICE(a1),_TimerBase

        move.l  a6,-(sp)
        move.l  _TimerBase,a6           ; A6 = TimerBase for the timer functions
        lea     now,a0
        jsr     _LVOGetSysTime(a6)
        move.l  (sp)+,a6
```

- Every unit gives the same `io_Device`. TimerBase stays valid only while that request is open:
  keep it open for as long as you call the functions, and close it last.
- Register convention: A6 = TimerBase, arguments in A0/A1, result in D0, D0/D1 scratch.
  AddTime, SubTime and CmpTime leave A0 and A1 unchanged. GetSysTime and ReadEClock leave A0
  unchanged (all per the autodocs).
- All five functions, the three commands and AbortIO on a timer request may be called from
  interrupt code. Open the device and fetch TimerBase from task context first.
- C: `#include <proto/timer.h>` and define the global `struct Device *TimerBase`. asm:
  `include "lvo/timer_lib.i"` and `jsr _LVOxxx(a6)`.

## timeval and EClockVal

| Structure | Fields (asm offset) | Size | Meaning |
|---|---|---|---|
| `struct timeval` | `tv_secs` (`TV_SECS` 0), `tv_micro` (`TV_MICRO` 4) | `TV_SIZE` 8 | seconds + microseconds; `tv_micro` must stay normalised to 0..999999 |
| `struct EClockVal` | `ev_hi` (`EV_HI` 0), `ev_lo` (`EV_LO` 4) | `EV_SIZE` 8 | 64-bit count of E-clock ticks, high longword first |
| `struct timerequest` | `tr_node` (IORequest, 0), `tr_time` (`IOTV_TIME` $20) | `IOTV_SIZE` $28 | the request for every unit |

- The E-clock rate is returned by ReadEClock (ExecBase also has `ex_EClockFrequency`). It is the
  8520 count rate: 709379 Hz PAL, 715909 Hz NTSC (HRM). Always use the returned value.
- `UNIT_ECLOCK` and `UNIT_WAITECLOCK` reuse the same 8 bytes of `tr_time` as an EClockVal:
  `struct EClockVal *ev = (struct EClockVal *)&tr->tr_time;` (`ev_hi` overlays `tv_secs`).
- System time starts at 0 at power-on unless TR_SETSYSTIME sets it. It rises monotonically and
  never returns the same value twice, except after someone sets it backwards. Boot normally sets
  it from the battery clock as seconds since 1-Jan-1978, the epoch of dos DateStamp and utility
  Amiga2Date (unverified).
- Bartman's `sys-include/devices/timer.h` wraps the fields in anonymous unions, adding
  `tv_sec`/`tv_usec` aliases (guarded by `_TIMEVAL_DEFINED`). The NDK 3.9 header has only
  `tv_secs`/`tv_micro`: use those. Because of the unions, `struct timeval t = { 1, 0 };` warns
  under `-Wall` (`-Wmissing-braces`): assign the fields by name instead.
- CmpTime has an **inverted sign**: `CmpTime(a, b)` is -1 when `a` is later than `b`, +1 when
  `a` is earlier, 0 when equal (the autodoc's BUGS section says older docs had it wrong).
  `CmpTime(&now, &deadline) <= 0` means the deadline has been reached.

## Request rules

- **One request, one pending wait.** Never SendIO/BeginIO/DoIO a request that is still pending,
  or that has completed but has not been collected with WaitIO/GetMsg: that corrupts the timer's
  queue. For several simultaneous timers create more requests and copy the opened one into them
  (`*tr2 = *tr1` copies `io_Device`, `io_Unit` and the reply port; common practice, unverified in
  these autodocs).
- **Cancel = AbortIO then WaitIO**: `if (!CheckIO(r)) AbortIO(r); WaitIO(r);`. AbortIO does not
  dequeue the reply. After WaitIO the request is idle and `io_Error` is `IOERR_ABORTED` (-2) if it
  was cut short.
- Reload `tr_time` before every TR_ADDREQUEST: the device zeroes it on completion (before 2.0 it
  was documented as junk).
- Blocking wait: DoIO. A wait you can combine with Ctrl-C, IDCMP or other ports: SendIO + Wait
  on `1 << port->mp_SigBit` + WaitIO. See [timing recipes](timing-recipes.md).
- Before CloseDevice every request on the unit must be back: abort and collect anything pending.

## Alternatives

- dos [Delay](../dos/time.md#delay)`(ticks)`: 50 ticks per second, Process only, fine for coarse sleeps.
- graphics [WaitTOF](../graphics/blitter-and-timing.md#waittof)`()`: wakes after each vertical blank. Use it for display-synchronous frame
  loops (see [frame pacing](timing-recipes.md#frame-pacing-for-games)).
- With the OS switched off (interrupts taken over), timer.device stops working: use a VERTB
  counter or the CIA timers directly (see cia.resource and the amiga-hardware skill).

## Version landmarks

- **1.x** -- `UNIT_MICROHZ`, `UNIT_VBLANK`, TR_ADDREQUEST, TR_GETSYSTIME, TR_SETSYSTIME, AddTime,
  SubTime, CmpTime (the autodocs give no version for these; unverified). Very short requests are
  unreliable (see Units).
- **V36 (2.0)** -- GetSysTime and ReadEClock (autodoc). `UNIT_ECLOCK`, `UNIT_WAITUNTIL` and
  `UNIT_WAITECLOCK` (unverified). TR_ADDREQUEST returns `tr_time` zeroed.

## Files

- [functions.md](functions.md) -- the 5 functions: AddTime, SubTime, CmpTime, GetSysTime,
  ReadEClock.
- [commands.md](commands.md) -- device commands TR_ADDREQUEST, TR_GETSYSTIME, TR_SETSYSTIME, and
  AbortIO on a timer request.
- [timing-recipes.md](timing-recipes.md) -- guide: sleeping without busy-waiting, periodic ticks
  with drift correction, measuring elapsed time, frame pacing vs WaitTOF.

<!-- FUNCTION TABLE -->
<!-- Generated by tools/skills/build_indexes.py - do not edit by hand. -->

## Functions

| Function | LVO | Registers | Summary |
|---|---|---|---|
| [AddTime](functions.md#addtime) | -42 | dest=A0, src=A1 | Add one timeval to another in place: dest = dest + src. |
| [CmpTime](functions.md#cmptime) | -54 | dest=A0, src=A1 | Compare two timevals; note the result is -1 when the FIRST argument is the later time. |
| [GetSysTime](functions.md#getsystime) | -66 | dest=A0 | Read the current system time into a timeval. |
| [ReadEClock](functions.md#readeclock) | -60 | dest=A0 | Read the 64-bit E-clock counter; returns the counter rate in ticks per second. |
| [SubTime](functions.md#subtime) | -48 | dest=A0, src=A1 | Subtract one timeval from another in place: dest = dest - src. |

Machine-readable: [../data/timer.tsv](../data/timer.tsv)
