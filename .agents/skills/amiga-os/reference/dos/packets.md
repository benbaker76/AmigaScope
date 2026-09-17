# dos.library: packets

Filesystem calls are carried out by sending a `struct DosPacket` to a handler process's MsgPort;
these functions let you do that directly (custom actions, asynchronous I/O, writing handlers).
A packet travels behind an exec Message: `struct StandardPacket { struct Message sp_Msg; struct
DosPacket sp_Pkt; }`. `AllocDosObject(DOS_STDPKT, NULL)` allocates and links one and returns a
pointer to its `sp_Pkt` -- free it with `FreeDosObject(DOS_STDPKT, pkt)`.

| DosPacket field | Use |
|---|---|
| `dp_Link` | the exec Message carrying the packet |
| `dp_Port` | reply port; must be filled in for every send (SendPkt takes it as `replyport`) |
| `dp_Type` (`dp_Action`) | `ACTION_xxx` code |
| `dp_Res1` (`dp_Status`) | primary result -- what the dos function would return |
| `dp_Res2` (`dp_Status2`) | secondary result -- what IoErr() would return |
| `dp_Arg1`..`dp_Arg7` | action-specific arguments (`dp_BufAddr` = `dp_Arg1`) |

Where the handler port comes from: [GetDeviceProc](dos-list.md#getdeviceproc) `dvp_Port`
(preferred), [DeviceProc](dos-list.md#deviceproc), `fl_Task` of a `struct FileLock`
(`BADDR(lock)`), `fh_Type` of a `struct FileHandle` (`BADDR(fh)`), or `dol_Task` of a DosList
entry. Lock and file handle arguments are BPTRs, strings for handlers are BSTRs (V36 Format()
failed because it passed a C string) -- see [BPTR and BSTR](concepts.md#bptr-and-bstr).

## Action codes

From dos/dosextens.h (asm: dos/dosextens.i); version notes follow the header's comments.
Argument layouts are not documented in the NDK autodocs; prefer the dos function when one
exists.

**File handle I/O**

| Name | Value | Notes |
|---|---|---|
| `ACTION_FINDUPDATE` | 1004 | same number as `MODE_READWRITE` |
| `ACTION_FINDINPUT` | 1005 | same number as `MODE_OLDFILE` |
| `ACTION_FINDOUTPUT` | 1006 | same number as `MODE_NEWFILE` |
| `ACTION_READ` | `'R'` (82) | |
| `ACTION_WRITE` | `'W'` (87) | Res1 = actual length written |
| `ACTION_SEEK` | 1008 | |
| `ACTION_END` | 1007 | |
| `ACTION_SET_FILE_SIZE` | 1022 | FFS only in 1.3 |
| `ACTION_READ_RETURN` | 1001 | |
| `ACTION_WRITE_RETURN` | 1002 | |
| `ACTION_WAIT_CHAR` | 20 | |
| `ACTION_SCREEN_MODE` | 994 | sent by [SetMode](files.md#setmode) |

**Locks and objects**

| Name | Value | Notes |
|---|---|---|
| `ACTION_LOCATE_OBJECT` | 8 | |
| `ACTION_FREE_LOCK` | 15 | |
| `ACTION_COPY_DIR` | 19 | |
| `ACTION_PARENT` | 29 | |
| `ACTION_EXAMINE_OBJECT` | 23 | |
| `ACTION_EXAMINE_NEXT` | 24 | |
| `ACTION_DELETE_OBJECT` | 16 | |
| `ACTION_RENAME_OBJECT` | 17 | |
| `ACTION_CREATE_DIR` | 22 | |
| `ACTION_SET_PROTECT` | 21 | |
| `ACTION_SET_COMMENT` | 28 | |
| `ACTION_SET_DATE` | 34 | |

**Volume and disk**

| Name | Value | Notes |
|---|---|---|
| `ACTION_NIL` / `ACTION_STARTUP` | 0 | |
| `ACTION_GET_BLOCK` | 2 | obsolete |
| `ACTION_SET_MAP` | 4 | |
| `ACTION_DIE` | 5 | |
| `ACTION_EVENT` | 6 | |
| `ACTION_CURRENT_VOLUME` | 7 | |
| `ACTION_RENAME_DISK` | 9 | |
| `ACTION_MORE_CACHE` | 18 | |
| `ACTION_DISK_INFO` | 25 | |
| `ACTION_INFO` | 26 | |
| `ACTION_FLUSH` | 27 | |
| `ACTION_TIMER` | 30 | |
| `ACTION_INHIBIT` | 31 | sent by [Inhibit](dos-list.md#inhibit) |
| `ACTION_DISK_TYPE` | 32 | |
| `ACTION_DISK_CHANGE` | 33 | |
| `ACTION_WRITE_PROTECT` | 1023 | FFS only in 1.3 |
| `ACTION_SERIALIZE_DISK` | 4200 | no arguments; new volume date; may fail on V37 ROM FS |

**New in 2.0**

| Name | Value | Notes |
|---|---|---|
| `ACTION_SAME_LOCK` | 40 | |
| `ACTION_CHANGE_SIGNAL` | 995 | |
| `ACTION_FORMAT` | 1020 | used by [Format](dos-list.md#format); printed arg docs often wrong |
| `ACTION_MAKE_LINK` | 1021 | |
| `ACTION_READ_LINK` | 1024 | |
| `ACTION_FH_FROM_LOCK` | 1026 | |
| `ACTION_IS_FILESYSTEM` | 1027 | also answered by port-handler/queue-handler |
| `ACTION_CHANGE_MODE` | 1028 | |
| `ACTION_COPY_DIR_FH` | 1030 | |
| `ACTION_PARENT_FH` | 1031 | |
| `ACTION_EXAMINE_ALL` | 1033 | |
| `ACTION_EXAMINE_FH` | 1034 | |
| `ACTION_EXAMINE_ALL_END` | 1035 | V39 |
| `ACTION_SET_OWNER` | 1036 | V39 |

**Record locks and notification** (in the 2.0 block of the header)

| Name | Value | Notes |
|---|---|---|
| `ACTION_LOCK_RECORD` | 2008 | |
| `ACTION_FREE_RECORD` | 2009 | |
| `ACTION_ADD_NOTIFY` | 4097 | |
| `ACTION_REMOVE_NOTIFY` | 4098 | |

## DoPkt
`LONG DoPkt(struct MsgPort *port, LONG action, LONG arg1, LONG arg2, LONG arg3, LONG arg4, LONG arg5)` — LVO -240 (-$F0)
Registers: port=D1, action=D2, arg1=D3, arg2=D4, arg3=D5, arg4=D6, arg5=D7; result in D0

Send a packet to a handler and wait for the reply (synchronous).

- **port** — the handler process's MsgPort (see intro).
- **action** — `ACTION_xxx` code ([action codes](#action-codes)).
- **arg1..arg5** — `dp_Arg1`..`dp_Arg5`; meaning depends on the action. Locks and file handles
  as BPTRs.
- **Result** — `dp_Res1`, or FALSE if the packet could not be sent/received. `dp_Res2` is
  returned in D1 AND via IoErr().

Aliases `DoPkt0(port, action)` .. `DoPkt4(port, action, a1, a2, a3, a4)` share the LVO and just
load fewer argument registers.

Since V36.

### Example
```c
#include <proto/dos.h>
#include <dos/dosextens.h>

/* Ask DF0:'s filesystem to re-date its volume (dosextens.h: no arguments) */
struct DevProc *dvp = GetDeviceProc("DF0:", NULL);
if (dvp) {
    if (!DoPkt0(dvp->dvp_Port, ACTION_SERIALIZE_DISK))   /* 0 = failed (unverified) */
        PrintFault(IoErr(), "serialize");   /* Res2 comes back via IoErr() */
    FreeDeviceProc(dvp);
}
```

### Gotchas
- Only 5 arguments: for `dp_Arg6`/`dp_Arg7` build the packet yourself and use SendPkt/WaitPkt.
- Replies arrive on your `pr_MsgPort` and `pr_PktWait` is called. Callable from a plain task
  only from V37 (it then allocates a temporary port); in V36 it fails from tasks -- use
  AllocDosObject + PutMsg + WaitPort/GetMsg or start a process.
- Res1 meaning is per action (`ACTION_WRITE`: length written); the V37 ROM filesystem may
  reject `ACTION_SERIALIZE_DISK` (dosextens.h).

**See also:** [SendPkt](#sendpkt), [WaitPkt](#waitpkt), [AbortPkt](#abortpkt),
[AllocDosObject](objects.md#allocdosobject), [GetDeviceProc](dos-list.md#getdeviceproc)

## SendPkt
`VOID SendPkt(struct DosPacket *dp, struct MsgPort *port, struct MsgPort *replyport)` — LVO -246 (-$F6)
Registers: dp=D1, port=D2, replyport=D3; no result

Send an initialised packet to a handler and return immediately (asynchronous).

- **dp** — packet with its message attached (use `AllocDosObject(DOS_STDPKT, NULL)`); set
  `dp_Type` and the arguments first.
- **port** — handler MsgPort.
- **replyport** — where the reply goes; use your `pr_MsgPort` if you will collect it with
  WaitPkt, or any port of your own.

Since V36.

### Example
```c
#include <proto/exec.h>
#include <proto/dos.h>
#include <dos/dosextens.h>

/* Start an action on a handler, do other work, then collect the reply */
LONG AsyncAction(struct MsgPort *port, LONG action, LONG arg1)
{
    struct Process *me = (struct Process *)FindTask(NULL);
    struct DosPacket *pkt = AllocDosObject(DOS_STDPKT, NULL);
    LONG res1;

    if (!pkt)
        return DOSFALSE;
    pkt->dp_Type = action;
    pkt->dp_Arg1 = arg1;                   /* BPTR for locks/file handles */
    SendPkt(pkt, port, &me->pr_MsgPort);

    /* ... other work here (no DOS I/O -- see gotchas) ... */

    pkt = WaitPkt();                       /* the only packet we have outstanding */
    res1 = pkt->dp_Res1;
    SetIoErr(pkt->dp_Res2);
    FreeDosObject(DOS_STDPKT, pkt);
    return res1;
}
```

### Gotchas
- Callable from a task, but WaitPkt needs a process; from a task use your own port and
  WaitPort/GetMsg. The packet pointer is in the message's `mn_Node.ln_Name`:
  `pkt = (struct DosPacket *)msg->mn_Node.ln_Name;`.
- Don't reuse or free the packet until it has come back, even after AbortPkt.
- With several packets outstanding, check which one WaitPkt returned.
- DoPkt, and so ordinary dos calls, also take replies on `pr_MsgPort`. If you do DOS I/O while
  a reply is pending, send with a private reply port instead (unverified).

**See also:** [WaitPkt](#waitpkt), [DoPkt](#dopkt), [AbortPkt](#abortpkt), [FreeDosObject](objects.md#freedosobject)

## WaitPkt
`struct DosPacket * WaitPkt(VOID)` — LVO -252 (-$FC)
Registers: none; result in D0

Wait for a packet to arrive at the process's pr_MsgPort and return it, already removed.

- **Result** — the packet (taken from the message's `ln_Name`). The message is assumed to be
  a DOS packet.

Since V36.

### Gotchas
- Calls `pr_PktWait` if one is installed.
- NOT guaranteed to clear the port's signal bit; don't rely on the signal state afterwards.
- Returns whatever packet arrives first -- a handler's incoming request or a reply to your
  SendPkt; check `dp_Type`/the pointer.

**See also:** [SendPkt](#sendpkt), [DoPkt](#dopkt), [ReplyPkt](#replypkt)

## ReplyPkt
`VOID ReplyPkt(struct DosPacket *dp, LONG res1, LONG res2)` — LVO -258 (-$102)
Registers: dp=D1, res1=D2, res2=D3; no result

Return a packet to its sender with both result fields set (handler side).

- **dp** — the packet received (e.g. from WaitPkt).
- **res1** — stored in `dp_Res1` (the function's return value).
- **res2** — stored in `dp_Res2` (the sender's IoErr() value).

Also writes your `pr_MsgPort` into `dp_Port`, so the receiver can ReplyPkt it straight back
("ping-pong" between two processes).

Since V36.

### Example
```c
/* Minimal handler loop */
for (;;) {
    struct DosPacket *pkt = WaitPkt();
    switch (pkt->dp_Type) {
    case ACTION_IS_FILESYSTEM:
        ReplyPkt(pkt, DOSFALSE, 0);        /* a stream handler, not a filesystem */
        break;
    default:
        ReplyPkt(pkt, DOSFALSE, ERROR_ACTION_NOT_KNOWN);
        break;
    }
}
```
The reply values above follow common handler practice (unverified).

### Gotchas
- Reply every packet exactly once; the sender (or dos call) blocks until you do.

**See also:** [WaitPkt](#waitpkt), [SendPkt](#sendpkt), [DoPkt](#dopkt), [IoErr](errors.md#ioerr)

## AbortPkt
`VOID AbortPkt(struct MsgPort *port, struct DosPacket *pkt)` — LVO -264 (-$108)
Registers: port=D1, pkt=D2; no result

Ask a handler to abort a packet sent with SendPkt; currently does nothing.

- **port** — port the packet was sent to.
- **pkt** — the packet to abort.

Since V36.

### Gotchas
- As of V37 it is a no-op; no handler is obliged to honour it anyway, and the action may
  have completed partly or fully. You must still wait for the packet to come back before
  reusing or freeing it.

**See also:** [SendPkt](#sendpkt), [WaitPkt](#waitpkt), [DoPkt](#dopkt)
