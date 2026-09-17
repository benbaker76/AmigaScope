# exec.library: device I/O

Devices are driven by messages. Create a reply port ([CreateMsgPort](signals-and-messages.md#createmsgport)),
a request of the device's size ([CreateIORequest](#createiorequest)), open the unit with
[OpenDevice](libraries-devices-resources.md#opendevice), fill in the command fields, then run it
synchronously ([DoIO](#doio)) or asynchronously ([SendIO](#sendio) + Wait + [WaitIO](#waitio)).
Tear down in reverse: finish/abort pending requests, CloseDevice, DeleteIORequest, DeleteMsgPort.

Request layout (C `struct IORequest` / `struct IOStdReq`, asm labels from exec/io.i):

| Offset | asm | C | Meaning |
|---|---|---|---|
| $00 | (MN_SIZE = $14) | `io_Message` | Message header; `LN_TYPE` $08, `MN_REPLYPORT` $0E, `MN_LENGTH` $12 |
| $14 | `IO_DEVICE` | `io_Device` | set by OpenDevice |
| $18 | `IO_UNIT` | `io_Unit` | set by OpenDevice (driver private) |
| $1C | `IO_COMMAND` | `io_Command` | UWORD command |
| $1E | `IO_FLAGS` | `io_Flags` | `IOF_QUICK` (bit 0) |
| $1F | `IO_ERROR` | `io_Error` | BYTE, 0 = OK |
| $20 | `IO_ACTUAL` | `io_Actual` | IOStdReq: bytes actually transferred |
| $24 | `IO_LENGTH` | `io_Length` | IOStdReq: bytes requested |
| $28 | `IO_DATA` | `io_Data` | IOStdReq: buffer |
| $2C | `IO_OFFSET` | `io_Offset` | IOStdReq: seek offset |

`IO_SIZE` = $20, `IOSTD_SIZE` = $30. Standard commands: `CMD_INVALID` 0, `CMD_RESET` 1,
`CMD_READ` 2, `CMD_WRITE` 3, `CMD_UPDATE` 4, `CMD_CLEAR` 5, `CMD_STOP` 6, `CMD_START` 7,
`CMD_FLUSH` 8; device-specific ones start at `CMD_NONSTD` 9. Generic errors (exec/errors.h):
`IOERR_OPENFAIL` -1, `IOERR_ABORTED` -2, `IOERR_NOCMD` -3, `IOERR_BADLENGTH` -4,
`IOERR_BADADDRESS` -5, `IOERR_UNITBUSY` -6, `IOERR_SELFTEST` -7.

Exec tracks completion in `LN_TYPE`: `NT_MESSAGE` (5) while the device owns the request,
`NT_REPLYMSG` (7) once replied. `IOF_QUICK` asks the device to finish inside the call without
queuing (DoIO always sets it; SendIO clears it).

**BeginIO** (amiga.lib) calls the device's BeginIO vector (-30, `DEV_BEGINIO`) directly with
your own `io_Flags`. The exec/io.i `BEGINIO` macro does it in asm (A1 = request). Bartman builds
do not link amiga.lib, but `#include <inline/alib.h>` supplies `BeginIO()` (and `NewList()`)
as inline macros (`<proto/alib.h>` fails to compile with Bartman's GCC: `__stdargs` is undefined).

```asm
; asm equivalent of BEGINIO: A1 = request
        move.l  a6,-(sp)
        move.l  IO_DEVICE(a1),a6
        jsr     DEV_BEGINIO(a6)         ; -30
        move.l  (sp)+,a6
```

## CreateIORequest
`APTR CreateIORequest(CONST struct MsgPort *port, ULONG size)` — LVO -654 (-$28E)
Registers: port=A0, size=D0; result in D0

Allocate and initialise an I/O request of a given size tied to a reply port.

- **port** — reply port (normally from CreateMsgPort). NULL makes the call fail.
- **size** — full size of the request the device expects: `sizeof(struct IOStdReq)`
  (`IOSTD_SIZE`), `sizeof(struct timerequest)` (`IOTV_SIZE`), `sizeof(struct IOExtTD)`
  (`IOTD_SIZE`), ... At least `sizeof(struct Message)`.
- **Result** — pointer to the request (declared APTR: cast it), or NULL if out of memory.

Since V36.

### Example
```c
#include <proto/exec.h>
#include <exec/io.h>

struct MsgPort *port = CreateMsgPort();
struct IOStdReq *ior = NULL;

if (port)
    ior = (struct IOStdReq *)CreateIORequest(port, sizeof(struct IOStdReq));
if (ior == NULL)
    goto cleanup;
```

### Gotchas
- Size too small for the device = memory corruption when the device writes its extra fields.
- Pre-V36 systems: use amiga.lib CreateExtIO/CreateStdIO instead (not linked in Bartman builds).

**See also:** [DeleteIORequest](#deleteiorequest), [CreateMsgPort](signals-and-messages.md#createmsgport), [OpenDevice](libraries-devices-resources.md#opendevice)

## DeleteIORequest
`VOID DeleteIORequest(APTR iorequest)` — LVO -660 (-$294)
Registers: iorequest=A0; no result

Free a request made by CreateIORequest.

- **iorequest** — the request, or NULL (no action). The size to free is read from `mn_Length`.

Since V36.

### Gotchas
- The request must be idle and its device closed first ([CloseDevice](libraries-devices-resources.md#closedevice)).
- Do not overwrite `io_Message.mn_Length`, and never pass a request you allocated another way.
- Delete the reply port only after the request ([DeleteMsgPort](signals-and-messages.md#deletemsgport)).

**See also:** [CreateIORequest](#createiorequest), [CloseDevice](libraries-devices-resources.md#closedevice)

## DoIO
`BYTE DoIO(struct IORequest *ioRequest)` — LVO -456 (-$1C8)
Registers: ioRequest=A1; result in D0

Send a request to its device and wait until it has completed.

- **ioRequest** — request opened with OpenDevice and filled in (`io_Command`, data fields).
- **Result** — sign-extended copy of `io_Error`: 0 = success. Most commands need this checked;
  details (e.g. `io_Actual`) are in the request.

DoIO sets `io_Flags` to `IOF_QUICK`, calls the device, and if the device did not finish at once
waits for the reply and removes it from the port. The request is free again on return.

### Example
```asm
; read the boot block of DF0: -- ioreq opened on trackdisk.device unit 0
        include "exec/io.i"
        include "devices/trackdisk.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        move.l  ioreq,a1
        move.w  #CMD_READ,IO_COMMAND(a1)
        move.l  #bootbuf,IO_DATA(a1)
        move.l  #2*TD_SECTOR,IO_LENGTH(a1)
        clr.l   IO_OFFSET(a1)           ; byte offset 0
        jsr     _LVODoIO(a6)
        tst.l   d0                      ; sign-extended io_Error
        bne     .readerror
        move.l  ioreq,a1
        move.w  #TD_MOTOR,IO_COMMAND(a1)
        clr.l   IO_LENGTH(a1)           ; 0 = motor off
        jsr     _LVODoIO(a6)

        section buffers,bss_c
bootbuf:
        ds.b    2*TD_SECTOR
```

### Gotchas
- Blocks the calling task: not from interrupts, and not for commands that may never finish
  (use SendIO + Wait with a timeout instead).
- Never start a request that is still active or still sitting on the reply port
  (`LN_TYPE` = `NT_MESSAGE` or `NT_REPLYMSG` unfetched).
- The result is only a BYTE sign-extended to 32 bits; compare against `IOERR_` values as signed.

**See also:** [SendIO](#sendio), [WaitIO](#waitio), [CheckIO](#checkio), [AbortIO](#abortio)

## SendIO
`VOID SendIO(struct IORequest *ioRequest)` — LVO -462 (-$1CE)
Registers: ioRequest=A1; no result

Start a request asynchronously; the device replies to the request's port when done.

- **ioRequest** — opened and filled-in request (IOStdReq or device-specific extension).

`io_Flags` is cleared before the device is called. Wait for the port signal (or anything else)
and collect the request with [WaitIO](#waitio) or [GetMsg](signals-and-messages.md#getmsg).

### Example
```c
#include <proto/exec.h>
#include <devices/timer.h>
#include <dos/dos.h>

/* tr: timerequest opened on UNIT_VBLANK, port = its reply port */
ULONG portsig = 1UL << port->mp_SigBit;
ULONG sigs;

tr->tr_node.io_Command = TR_ADDREQUEST;
tr->tr_time.tv_secs    = 5;
tr->tr_time.tv_micro   = 0;
SendIO((struct IORequest *)tr);

sigs = Wait(portsig | SIGBREAKF_CTRL_C);
if (sigs & SIGBREAKF_CTRL_C) {
    if (!CheckIO((struct IORequest *)tr))
        AbortIO((struct IORequest *)tr);
}
WaitIO((struct IORequest *)tr);         /* always collect it, aborted or not */
```

### Gotchas
- Every SendIO must be matched by collecting the reply (WaitIO or GetMsg) before the request is
  reused, closed or freed.
- One request can only be in flight once; use a second request for parallel commands.

**See also:** [DoIO](#doio), [CheckIO](#checkio), [WaitIO](#waitio), [AbortIO](#abortio)

## CheckIO
`struct IORequest * CheckIO(struct IORequest *ioRequest)` — LVO -468 (-$1D4)
Registers: ioRequest=A1; result in D0

Test whether a request has completed, without waiting or dequeuing it.

- **ioRequest** — request previously sent with SendIO/BeginIO.
- **Result** — NULL while the I/O is still in progress; otherwise the request pointer.

### Example
```asm
        move.l  4.w,a6
        move.l  timereq,a1
        jsr     _LVOCheckIO(a6)
        tst.l   d0
        beq     .stillbusy
        move.l  timereq,a1
        jsr     _LVOWaitIO(a6)          ; completed: remove it from the port
```

### Gotchas
- A completed request stays queued on the reply port: follow with WaitIO to remove it.
  Removing it with Remove() yourself would need Disable/Enable.
- Do not busy-loop on CheckIO; Wait on the port signal or use WaitIO.
- On a request never sent whose `LN_TYPE` is `NT_MESSAGE` it can hang: leave a fresh request's
  type at 0 (`NT_UNKNOWN`).
- Old V37-era docs describe a BOOL result; the result is really `struct IORequest *`.

**See also:** [WaitIO](#waitio), [SendIO](#sendio), [AbortIO](#abortio)

## WaitIO
`BYTE WaitIO(struct IORequest *ioRequest)` — LVO -474 (-$1DA)
Registers: ioRequest=A1; result in D0

Wait until a request completes, then remove it from its reply port.

- **ioRequest** — request sent with SendIO/BeginIO (or already completed).
- **Result** — sign-extended `io_Error`: 0 = success.

Returns at once if the request has already finished.

### Gotchas
- If the request was already done, no Wait() happens and the port's signal bit may stay set:
  expect a spurious wake-up on your next Wait, and always loop on GetMsg/CheckIO.
- Hangs forever if the device never replies: for timeouts Wait on the port signal plus a timer
  or break signal, then [AbortIO](#abortio) + WaitIO.
- Only for requests that were actually sent; not from interrupts.

**See also:** [CheckIO](#checkio), [AbortIO](#abortio), [DoIO](#doio), [SendIO](#sendio)

## AbortIO
`VOID AbortIO(struct IORequest *ioRequest)` — LVO -480 (-$1E0)
Registers: ioRequest=A1; no result

Ask the device to cancel a request that is in progress.

- **ioRequest** — request that has been sent at least once; may be active or already finished.

The device may or may not honour it. An aborted request is replied early, typically with
`io_Error` = `IOERR_ABORTED` (-2). Nothing happens if it had already completed.

### Example
```c
/* cancel a pending timer request safely */
if (!CheckIO((struct IORequest *)tr))
    AbortIO((struct IORequest *)tr);
WaitIO((struct IORequest *)tr);         /* request is now idle and reusable */
```

### Gotchas
- AbortIO neither waits nor dequeues: you MUST still WaitIO (or GetMsg the reply) before
  reusing, closing or freeing the request.
- Do not call it on a fresh request that was never sent.

**See also:** [WaitIO](#waitio), [CheckIO](#checkio), [SendIO](#sendio), [CloseDevice](libraries-devices-resources.md#closedevice)
