# dos.library: file notification and record locking

**Notification**: fill a `struct NotifyRequest`, `StartNotify()` it, and the filesystem sends
you a message or a signal whenever the file or directory changes (for files: after the
writer closes it); `EndNotify()` stops it. Support is optional per filesystem (RAM: and the
V37+ ROM filesystem do, network filesystems usually do not), so treat it as a bonus, never a
requirement.

**Record locking**: advisory byte-range locks on an open file handle. They only affect other
callers of `LockRecord()`/`LockRecords()`; plain `Read()`/`Write()` ignore them. All six calls
are V36+ (record locking crashed on the disk filesystem before V37, see below).

`struct NotifyRequest` (`dos/notify.h`):

| Field | Use |
|---|---|
| `nr_Name` | name of the file or directory to watch |
| `nr_FullName` | set by DOS -- do not touch |
| `nr_UserData` | free for the application |
| `nr_Flags` | `NRF_SEND_MESSAGE` (1) or `NRF_SEND_SIGNAL` (2), plus `NRF_WAIT_REPLY` (8), `NRF_NOTIFY_INITIAL` (16) |
| `nr_stuff.nr_Msg.nr_Port` | reply-capable MsgPort for NRF_SEND_MESSAGE |
| `nr_stuff.nr_Signal.nr_Task`, `.nr_SignalNum` | task and signal bit number for NRF_SEND_SIGNAL |
| `nr_Reserved[4]` | must be 0 |
| `nr_MsgCount`, `nr_Handler` | handler-private |

`NRF_MAGIC` (0x80000000) and the `NR_HANDLER_FLAGS` bits (0xffff0000) belong to the handler.
Messages are `struct NotifyMessage`: `nm_ExecMessage`, `nm_Class` (`NOTIFY_CLASS`
0x40000000), `nm_Code` (`NOTIFY_CODE` 0x1234), `nm_NReq` (your request, read-only),
`nm_DoNotTouch`, `nm_DoNotTouch2`.

## StartNotify
`BOOL StartNotify(struct NotifyRequest *notify)` — LVO -888 (-$378)
Registers: notify=D1; result in D0

Ask the filesystem to report changes to a file or directory.

- **notify** — filled-in `struct NotifyRequest` (zero it first). Stays in use until
  EndNotify: keep it in memory and do not modify it.
- **Result** — non-zero on success, 0 if the request could not be posted (e.g. filesystem
  without notification support).

Since V36.

### Example
```c
#include <dos/notify.h>

struct NotifyRequest nr = { 0 };
BYTE sig = AllocSignal(-1);
if (sig != -1) {
    nr.nr_Name  = (UBYTE *)"ENV:MyGameConfig";
    nr.nr_Flags = NRF_SEND_SIGNAL;
    nr.nr_stuff.nr_Signal.nr_Task      = FindTask(NULL);
    nr.nr_stuff.nr_Signal.nr_SignalNum = sig;
    if (StartNotify(&nr)) {
        ULONG got = Wait((1UL << sig) | SIGBREAKF_CTRL_C);
        if (got & (1UL << sig))
            PutStr("config changed\n");
    }
    EndNotify(&nr);                  /* safe even if StartNotify failed */
    FreeSignal(sig);
}
```

### Gotchas
- Files are reported after the writer closes them, not on every Write.
- With `NRF_SEND_MESSAGE` you must `ReplyMsg()` every NotifyMessage.
- `NRF_WAIT_REPLY` (hold further messages until the last one is replied) and
  `NRF_NOTIFY_INITIAL` (report once immediately if the object exists) are header names only in
  the local sources -- behaviour described here is unverified.
- V36 ROM filesystem accepted requests but never notified (RAM: did); fixed in V37.

**See also:** [EndNotify](#endnotify)

## EndNotify
`VOID EndNotify(struct NotifyRequest *notify)` — LVO -894 (-$37E)
Registers: notify=D1; no result

Cancel a notification request.

- **notify** — the request passed to StartNotify.

For `NRF_SEND_MESSAGE` requests it also removes and replies any notification messages for this
request still queued at your port.

Since V36.

### Gotchas
- Safe to call when StartNotify failed, so a cleanup path can call it unconditionally (after
  the request has been zeroed and filled).
- Call it before freeing the NotifyRequest, the port, or the signal.

**See also:** [StartNotify](#startnotify)

## LockRecord
`BOOL LockRecord(BPTR fh, ULONG offset, ULONG length, ULONG mode, ULONG timeout)` — LVO -270 (-$10E)
Registers: fh=D1, offset=D2, length=D3, mode=D4, timeout=D5; result in D0

Lock a byte range of an open file, shared or exclusive, waiting up to a timeout.

- **fh** — file handle; the lock belongs to this handle.
- **offset** — first byte of the range.
- **length** — bytes in the range.
- **mode** — `REC_EXCLUSIVE` (0), `REC_EXCLUSIVE_IMMED` (1), `REC_SHARED` (2),
  `REC_SHARED_IMMED` (3) from `dos/record.h`; the `_IMMED` modes ignore the timeout.
- **timeout** — ticks (1/50 s) to wait for the range; 0 is allowed.
- **Result** — non-zero on success, 0 on failure (IoErr set).

Since V36.

### Example
```c
#include <dos/record.h>

if (LockRecord(fh, 1024, 256, REC_EXCLUSIVE, 5 * TICKS_PER_SECOND)) {
    /* ... update bytes 1024-1279 ... */
    UnLockRecord(fh, 1024, 256);
} else {
    PrintFault(IoErr(), "record busy");
}
```

### Gotchas
- Cooperative only; a handle can take several locks on the same range and each needs its own
  UnLockRecord.
- V36 (2.0-2.02): worked only on RAM:, and crashed the disk filesystem. Require V37.
- Related codes in `dos/dos.h`: `ERROR_RECORD_NOT_LOCKED` (240), `ERROR_LOCK_COLLISION` (241),
  `ERROR_LOCK_TIMEOUT` (242), `ERROR_UNLOCK_ERROR` (243).
- The NDK prototype returns BOOL; the V37 autodoc showed ULONG. Test for non-zero.

**See also:** [UnLockRecord](#unlockrecord), [LockRecords](#lockrecords),
[UnLockRecords](#unlockrecords)

## UnLockRecord
`BOOL UnLockRecord(BPTR fh, ULONG offset, ULONG length)` — LVO -282 (-$11A)
Registers: fh=D1, offset=D2, length=D3; result in D0

Release a record lock taken with LockRecord().

- **fh** — the SAME file handle used for LockRecord.
- **offset**, **length** — exactly the values used to lock it.
- **Result** — non-zero on success.

Since V36.

### Gotchas
- Every LockRecord needs a matching UnLockRecord.

**See also:** [LockRecord](#lockrecord), [LockRecords](#lockrecords),
[UnLockRecords](#unlockrecords)

## LockRecords
`BOOL LockRecords(struct RecordLock *recArray, ULONG timeout)` — LVO -276 (-$114)
Registers: recArray=D1, timeout=D2; result in D0

Lock several records described by a RecordLock array.

- **recArray** — array of `struct RecordLock` { `rec_FH`, `rec_Offset`, `rec_Length`,
  `rec_Mode` } ended by an entry whose `rec_FH` is 0.
- **timeout** — ticks to wait, applied to EACH record attempt; 0 is allowed.
- **Result** — non-zero if all were locked.

Since V36.

### Gotchas
- Always lock sets of records in the same order everywhere to avoid deadlocks.
- Do not change the array while the records are locked; release them with UnLockRecords on
  the same array.
- Same V36 disk-filesystem bug as LockRecord.

**See also:** [UnLockRecords](#unlockrecords), [LockRecord](#lockrecord),
[UnLockRecord](#unlockrecord)

## UnLockRecords
`BOOL UnLockRecords(struct RecordLock *recArray)` — LVO -288 (-$120)
Registers: recArray=D1; result in D0

Release all record locks taken with LockRecords().

- **recArray** — the same array passed to LockRecords.
- **Result** — non-zero on success.

Since V36.

**See also:** [LockRecords](#lockrecords), [LockRecord](#lockrecord),
[UnLockRecord](#unlockrecord)
