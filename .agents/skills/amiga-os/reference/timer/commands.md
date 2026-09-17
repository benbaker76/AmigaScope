# timer.device: commands

Commands go in `io_Command` of a `struct timerequest` opened on a unit (see
[units](index.md#units)) and are run with exec DoIO (blocking) or SendIO (asynchronous, then Wait
and WaitIO). Values come from `devices/timer.h`: `TR_ADDREQUEST` = `CMD_NONSTD` (9),
`TR_GETSYSTIME` = 10, `TR_SETSYSTIME` = 11. The standard exec commands (CMD_READ, CMD_WRITE...)
are not listed in the timer autodocs. The autodocs allow all three commands, and AbortIO, from
interrupt code; never use anything that waits there (DoIO, WaitIO).

## TR_ADDREQUEST
`io_Command` = `TR_ADDREQUEST` (9) · timer.device · request: `struct timerequest`

Wait for a time interval, or until an absolute time, then reply the request.

- **In:** `io_Command` = `TR_ADDREQUEST`; `tr_time` as the unit expects it: relative `timeval`
  (`UNIT_MICROHZ`, `UNIT_VBLANK`), relative E-clock ticks as an `EClockVal` (`UNIT_ECLOCK`),
  absolute system time (`UNIT_WAITUNTIL`) or absolute E-clock value (`UNIT_WAITECLOCK`).
  `mn_ReplyPort` set (CreateIORequest does it); `io_Device`/`io_Unit` from OpenDevice.
  `IOF_QUICK` is allowed but ignored: the reply always goes through the port.
- **Out:** `tr_time` zeroed (from 2.0; documented as junk before). `io_Error` = 0 when the time
  ran out, `IOERR_ABORTED` (-2) when cut short with [AbortIO](#abortio).

### Example
```c
/* blocking sleep of 250 ms (tr opened on UNIT_MICROHZ) */
tr->tr_node.io_Command = TR_ADDREQUEST;
tr->tr_time.tv_secs    = 0;
tr->tr_time.tv_micro   = 250000;
DoIO((struct IORequest *)tr);

/* UNIT_ECLOCK: the same field holds E-clock ticks */
struct EClockVal *ev = (struct EClockVal *)&tr->tr_time;
ev->ev_hi = 0;
ev->ev_lo = freq / 100;                         /* 10 ms; freq from ReadEClock() */
DoIO((struct IORequest *)tr);
```

```asm
; sleep 250 ms -- timereq opened on UNIT_MICROHZ
        move.l  4.w,a6
        move.l  timereq,a1
        move.w  #TR_ADDREQUEST,IO_COMMAND(a1)
        clr.l   IOTV_TIME+TV_SECS(a1)
        move.l  #250000,IOTV_TIME+TV_MICRO(a1)
        jsr     _LVODoIO(a6)
```

A breakable wait (SendIO + Wait with Ctrl-C) is in
[timing recipes](timing-recipes.md#delay-without-busy-waiting).

### Gotchas
- A request can hold only one pending wait. Sending it again before it is back (replied AND
  collected) corrupts the device's list. Use one request per concurrent timer.
- Reload `tr_time` before every send: it comes back zeroed.
- Keep `tv_micro` in 0..999999: 1.5 s is `tv_secs` = 1, `tv_micro` = 500000.
- `UNIT_VBLANK` resolution is one vertical-blank interval: short waits there are coarse. Use
  `UNIT_MICROHZ`/`UNIT_ECLOCK` below about half a second.
- Absolute units (`UNIT_WAITUNTIL`, `UNIT_WAITECLOCK`) reply as soon as the time has been reached,
  so a deadline already in the past returns at once.
- Kickstart 1.2/1.3: very short requests could make other timer requests finish inaccurately.

**See also:** [AbortIO](#abortio), [ReadEClock](functions.md#readeclock), [GetSysTime](functions.md#getsystime), [SendIO](../exec/io.md#sendio), [timing recipes](timing-recipes.md)

## TR_GETSYSTIME
`io_Command` = `TR_GETSYSTIME` (10) · timer.device · request: `struct timerequest`

Read the system time through a device request.

- **In:** `io_Command` = `TR_GETSYSTIME`; reply port, device and unit as usual; `IOF_QUICK`
  allowed (DoIO then completes without a reply message).
- **Out:** `tr_time` = current system time (`timeval`); `io_Error` = 0.

The system time starts at 0 at power-on unless it was set with [TR_SETSYSTIME](#tr_setsystime);
it only rises and is unique per read unless someone sets it backwards.

### Example
```asm
        move.l  4.w,a6
        move.l  timereq,a1
        move.w  #TR_GETSYSTIME,IO_COMMAND(a1)
        jsr     _LVODoIO(a6)
        move.l  timereq,a1
        move.l  IOTV_TIME+TV_SECS(a1),d0       ; seconds
        move.l  IOTV_TIME+TV_MICRO(a1),d1      ; microseconds
```

### Gotchas
- On V36+ [GetSysTime](functions.md#getsystime) gives the same value without an I/O round trip.
- It overwrites `tr_time`: never send it on a request that is pending, and reload `tr_time`
  before reusing the request for TR_ADDREQUEST.
- The autodoc names no particular unit; any opened unit is normally used (unverified).

**See also:** [TR_SETSYSTIME](#tr_setsystime), [GetSysTime](functions.md#getsystime)

## TR_SETSYSTIME
`io_Command` = `TR_SETSYSTIME` (11) · timer.device · request: `struct timerequest`

Set the system time.

- **In:** `io_Command` = `TR_SETSYSTIME`; `tr_time` = the new system time (normalised
  `timeval`); `IOF_QUICK` allowed.
- **Out:** `tr_time` contains junk; `io_Error` = 0 on success.

### Example
```c
/* set the system clock to secs seconds after 1-Jan-1978 */
tr->tr_node.io_Command = TR_SETSYSTIME;
tr->tr_time.tv_secs    = secs;
tr->tr_time.tv_micro   = 0;
if (DoIO((struct IORequest *)tr) != 0)
    PutStr((CONST_STRPTR)"could not set the time\n");
```

### Gotchas
- Setting the time forward from boot-time zero is safe. Setting it **backwards** breaks the
  "only rises, never repeats" promise that other programs rely on (UNIT_WAITUNTIL alarms,
  GetSysTime interval measurement, unique time stamps). Leave it to clock-setting tools.
- The autodoc's request table for this command wrongly lists `io_Command TR_GETSYSTIME`: use
  `TR_SETSYSTIME` (11).
- It sets only the running system time. The battery-backed clock is a separate resource
  (unverified).

**See also:** [TR_GETSYSTIME](#tr_getsystime), [GetSysTime](functions.md#getsystime)

## AbortIO
`` exec `AbortIO()` on a pending timer request · timer.device · request: `struct timerequest` ``

Cancel a pending TR_ADDREQUEST so it is replied at once with `IOERR_ABORTED`.

- **In:** A1 = the request (exec.library AbortIO, LVO -480, A6 = SysBase). It must have been
  sent at least once.
- **Out:** D0 = 0 if the timer removed the request (and `io_Error` = `IOERR_ABORTED`), -1 if it
  was not pending (already finished). The reply is still on your port either way.

It runs in the caller's context and may be called from interrupts.

### Example
```c
/* cancel safely, whatever state the request is in */
if (!CheckIO((struct IORequest *)tr))
    AbortIO((struct IORequest *)tr);
WaitIO((struct IORequest *)tr);                 /* ALWAYS: removes the reply */
if (tr->tr_node.io_Error == IOERR_ABORTED)
    PutStr((CONST_STRPTR)"timer cancelled\n");
```

```asm
        move.l  4.w,a6
        move.l  timereq,a1
        jsr     _LVOAbortIO(a6)         ; D0 = 0 aborted, -1 not pending
        move.l  timereq,a1
        jsr     _LVOWaitIO(a6)          ; collect the reply in both cases
```

### Gotchas
- AbortIO never removes the reply from the port. Skip the WaitIO and the next send of the same
  request, CloseDevice or DeleteIORequest works on a request still linked into the port.
- The NDK 3.9 exec prototype is `VOID AbortIO()`, so C cannot see the D0 result documented by
  the timer autodoc: test `io_Error` after WaitIO instead (`IOERR_ABORTED` needs `<exec/errors.h>`).
- Do not call it on a request that was never sent.

**See also:** [TR_ADDREQUEST](#tr_addrequest), [exec AbortIO](../exec/io.md#abortio), [WaitIO](../exec/io.md#waitio), [CheckIO](../exec/io.md#checkio)
