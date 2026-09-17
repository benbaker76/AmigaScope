# exec.library: signals and messages

Signals are the 32 per-task wake-up bits behind every exec wait. The low 16 are reserved
for the system (`SYS_SIGALLOC` = $FFFF): `SIGB_ABORT` 0, `SIGB_CHILD` 1, `SIGB_BLIT` /
`SIGB_SINGLE` 4, `SIGB_INTUITION` 5, `SIGB_NET` 7, `SIGB_DOS` 8 (exec/tasks.h), and
dos/dos.h's break signals `SIGBREAKB_CTRL_C`..`SIGBREAKB_CTRL_F` = 12..15
(`SIGBREAKF_CTRL_C` = $1000). Bits 16-31 are handed out by AllocSignal. A task sleeps in
Wait() until any bit of its mask arrives through Signal().

Messages ride on signals: PutMsg queues a `struct Message` on a `struct MsgPort` and
performs the port's arrival action from `mp_Flags` -- `PA_SIGNAL` (signal
`mp_SigTask` with bit `mp_SigBit`), `PA_SOFTINT` (Cause the interrupt in `mp_SoftInt`)
or `PA_IGNORE`. The receiver GetMsg's it (type `NT_MESSAGE` while queued), works on the
shared memory (nothing is copied) and ReplyMsg's it back to `mn_ReplyPort`, where it
arrives as `NT_REPLYMSG`. The sender must not touch or free the message until it is
replied. Structures: [structures topic](../topics/structures.md).

## AllocSignal
`BYTE AllocSignal(LONG signalNum)` — LVO -330 (-$14A)
Registers: signalNum=D0; result in D0

Allocate a signal bit in the current task, either a specific one or any free one.

- **signalNum** — wanted bit 0..31, or -1 for "any free user bit".
- **Result** — the allocated bit number (signed byte), or -1 if taken / none free. The
  bit is cleared before return. Its mask is `1L << result`.

### Example
```c
#include <proto/exec.h>

struct Task *waiter;        /* set by the waiting task: FindTask(NULL) */
ULONG readyMask;

/* waiting task */
BYTE bit = AllocSignal(-1);
if (bit == -1)
    return FALSE;
waiter = FindTask(NULL);
readyMask = 1UL << bit;
Wait(readyMask);            /* sleeps until another task/interrupt signals */
FreeSignal(bit);

/* elsewhere (another task or an interrupt server) */
Signal(waiter, readyMask);
```

### Gotchas
- The result is a BYTE: in asm test it with `tst.b d0` / `bmi`, not `tst.l d0`.
- A signal belongs to the task that allocated it; only that task may Wait on or free it.
- Not from exception handlers (tc_ExceptCode).
- At least 16 user signals exist, but ports, timers and libraries take some; always
  handle -1.

**See also:** [FreeSignal](#freesignal), [Wait](#wait), [Signal](#signal)

## FreeSignal
`VOID FreeSignal(LONG signalNum)` — LVO -336 (-$150)
Registers: signalNum=D0; no result

Give a signal bit allocated with AllocSignal back to the current task's pool.

- **signalNum** — the bit (0..31) to free. V37+: -1 is ignored, so freeing a failed
  allocation result is harmless.

### Gotchas
- Must be called by the task that allocated the bit, never from exception code.
- Do not free bits owned by message ports you did not create (CreateMsgPort /
  DeleteMsgPort manage their own bit).

**See also:** [AllocSignal](#allocsignal)

## Wait
`ULONG Wait(ULONG signalSet)` — LVO -318 (-$13E)
Registers: signalSet=D0; result in D0

Sleep until at least one of the given signals is set; return and clear the ones received.

- **signalSet** — mask of signal bits to wait for.
- **Result** — mask of the requested signals that were set; those bits are cleared,
  bits outside `signalSet` stay pending.

Returns immediately if a requested signal was already set before the call.

### Example
```c
#include <proto/exec.h>
#include <dos/dos.h>

struct MsgPort *port = CreateMsgPort();
if (port) {
    ULONG portMask = 1UL << port->mp_SigBit;
    BOOL running = TRUE;

    while (running) {
        ULONG sigs = Wait(portMask | SIGBREAKF_CTRL_C);
        struct Message *msg;

        while ((msg = GetMsg(port)) != NULL) {    /* drain: 1 signal, n messages */
            /* ... handle msg ... */
            ReplyMsg(msg);
        }
        if (sigs & SIGBREAKF_CTRL_C)
            running = FALSE;
    }
    DeleteMsgPort(port);
}
```

### Gotchas
- Never from interrupts or supervisor mode.
- Wait breaks an active Forbid or Disable for as long as the task sleeps.
- One signal can stand for several messages, and a signal can arrive with no message:
  always loop GetMsg until it returns NULL.

**See also:** [Signal](#signal), [SetSignal](#setsignal), [WaitPort](#waitport)

## Signal
`VOID Signal(struct Task *task, ULONG signalSet)` — LVO -324 (-$144)
Registers: task=A1, signalSet=D0; no result

Set signal bits in a task, waking it if it is waiting for any of them.

- **task** — the task to signal.
- **signalSet** — bits to set. If the task is not waiting for them they stay pending.

Safe to call from interrupt code; this is how an interrupt server hands work to a task.

### Gotchas
- The task pointer must be valid: a task that already exited cannot be signalled safely.
  Have the task clear the shared pointer (under Disable if an interrupt uses it) before
  it quits.
- Only signal bits the target actually allocated (or agreed, like SIGBREAKF_CTRL_C).

**See also:** [Wait](#wait), [SetSignal](#setsignal), [AllocSignal](#allocsignal)

## SetSignal
`ULONG SetSignal(ULONG newSignals, ULONG signalSet)` — LVO -306 (-$132)
Registers: newSignals=D0, signalSet=D1; result in D0

Read, set or clear the current task's received signals without waiting.

- **newSignals** — new values for the bits selected by `signalSet`.
- **signalSet** — bits to change; 0 = just read.
- **Result** — all received signals as they were before the call.

### Example
```c
#include <proto/exec.h>
#include <dos/dos.h>

/* poll for CTRL-C in a busy loop and clear it in the same call */
if (SetSignal(0L, SIGBREAKF_CTRL_C) & SIGBREAKF_CTRL_C)
    goto user_break;
```

```asm
        include "dos/dos.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        moveq   #0,d0                   ; newSignals
        move.l  #SIGBREAKF_CTRL_C,d1    ; signalSet
        jsr     _LVOSetSignal(a6)
        btst    #SIGBREAKB_CTRL_C,d0
        bne     .user_break
```

### Gotchas
- Reading is safe; setting bits by hand (instead of Signal) is rarely correct.
- Clearing a port's signal while messages are queued makes a later Wait sleep with
  work pending: drain the port with GetMsg instead.

**See also:** [Wait](#wait), [Signal](#signal)

## SetExcept
`ULONG SetExcept(ULONG newSignals, ULONG signalSet)` — LVO -312 (-$138)
Registers: newSignals=D0, signalSet=D1; result in D0

Choose which of the current task's signals trigger its exception handler.

- **newSignals** — new values for the bits selected by `signalSet`.
- **signalSet** — bits to change; SetExcept(0,0) just reads.
- **Result** — previous exception mask.

When a selected signal arrives, exec calls `tc_ExceptCode` with D0 = the signals that
fired (already removed from the exception mask), A1 = `tc_ExceptData`, A6 = SysBase. The
handler returns in D0 the signals to re-arm, normally the same D0 it received. A signal
that was already pending when enabled fires at once.

### Gotchas
- Set `tc_ExceptCode`/`tc_ExceptData` before enabling any bits.
- The handler interrupts the task at an arbitrary point: no AllocSignal/FreeSignal
  (and no AllocTrap/FreeTrap) there, and keep it as careful as interrupt code.

**See also:** [Signal](#signal), [SetSignal](#setsignal)

## CreateMsgPort
`struct MsgPort * CreateMsgPort(VOID)` — LVO -666 (-$29A)
Registers: none; result in D0

Allocate a private message port that signals the calling task when messages arrive.

- **Result** — a ready `struct MsgPort` (list initialised, a signal bit allocated,
  `PA_SIGNAL`, `mp_SigTask` = caller), or NULL if memory or signals ran out.

Since V36.

### Example
```asm
        include "exec/ports.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        jsr     _LVOCreateMsgPort(a6)
        move.l  d0,replyport
        beq     .noport
        ; signal mask for Wait():
        move.l  d0,a0
        moveq   #0,d1
        move.b  MP_SIGBIT(a0),d1
        moveq   #0,d0
        bset    d1,d0                   ; d0 = 1 << mp_SigBit
        move.l  d0,portmask
```

### Gotchas
- Free it only with [DeleteMsgPort](#deletemsgport) (never FreeMem), from the same task
  (the signal bit belongs to it).
- To make it public set `ln_Name` and `ln_Pri`, then [AddPort](#addport); RemPort before
  deleting.
- V33/V34 have no CreateMsgPort. amiga.lib CreatePort is the old replacement, but
  amiga.lib is not linked in Bartman `-nostdlib` builds: build the port by hand (see
  [AddPort](#addport)).

**See also:** [DeleteMsgPort](#deletemsgport), [AddPort](#addport), [WaitPort](#waitport)

## DeleteMsgPort
`VOID DeleteMsgPort(struct MsgPort *port)` — LVO -672 (-$2A0)
Registers: port=A0; no result

Free a port made by CreateMsgPort, including its signal bit.

- **port** — the port, or NULL (does nothing).

Since V36.

### Gotchas
- Every message sent to the port must already be taken off and replied.
- A public port must be [RemPort](#remport)'d first.
- Only for CreateMsgPort ports; hand-built ports are cleaned up by the code that built
  them.

**See also:** [CreateMsgPort](#createmsgport), [RemPort](#remport), [GetMsg](#getmsg)

## AddPort
`VOID AddPort(struct MsgPort *port)` — LVO -354 (-$162)
Registers: port=A1; no result

Put a named message port on the system's public port list so FindPort can find it.

- **port** — a port with `ln_Name` (not copied -- must stay valid) and `ln_Pri` set.
  AddPort initialises the port's message list itself.

Use priority 0 when nobody searches for it, at least 1 when others do, and 50-100 for
ports looked up very often (they sit ahead of the many idle ports).

### Example
```asm
        include "exec/ports.i"
        include "lvo/exec_lib.i"

; out: d0 = public port or 0
MakePublicPort:
        move.l  4.w,a6
        jsr     _LVOCreateMsgPort(a6)
        tst.l   d0
        beq.s   .fail
        move.l  d0,a1
        move.l  #PortName,LN_NAME(a1)
        move.b  #1,LN_PRI(a1)
        move.l  d0,-(sp)
        jsr     _LVOAddPort(a6)         ; a1 = port
        move.l  (sp)+,d0
.fail:  rts

PortName:
        dc.b    "MYGAME.CTRL",0
        even
```

A hand-built port (e.g. on KS 1.3) needs, before use: `LN_TYPE` = `NT_MSGPORT`,
`MP_FLAGS` = `PA_SIGNAL`, `MP_SIGBIT` from AllocSignal, `MP_SIGTASK` = FindTask(NULL) and
an initialised list: `lea MP_MSGLIST(a1),a0` + `NEWLIST a0` (exec/lists.i).

### Gotchas
- Never AddPort a port that is already in use (active port).
- Remove it with [RemPort](#remport) before freeing its memory.
- A zeroed MsgPort is not usable until its `mp_MsgList` is a valid empty list.

**See also:** [RemPort](#remport), [FindPort](#findport), [CreateMsgPort](#createmsgport)

## RemPort
`VOID RemPort(struct MsgPort *port)` — LVO -360 (-$168)
Registers: port=A1; no result

Take a public port off the system port list; name lookups stop finding it.

- **port** — a port previously added with AddPort.

### Gotchas
- Shutdown order: RemPort, then GetMsg/ReplyMsg everything still queued, then delete
  the port. A sender that found the port just before RemPort may still deliver one.

**See also:** [AddPort](#addport), [FindPort](#findport), [DeleteMsgPort](#deletemsgport)

## FindPort
`struct MsgPort * FindPort(CONST_STRPTR name)` — LVO -390 (-$186)
Registers: name=A1; result in D0

Look up a public message port by name.

- **name** — port name (exact, case-sensitive).
- **Result** — first port with that name, or 0.

### Example
```c
#include <proto/exec.h>

/* send msg to a named port; FALSE if the port does not exist */
BOOL SendToPort(CONST_STRPTR name, struct Message *msg)
{
    struct MsgPort *port;

    Forbid();                       /* the port must not vanish between Find and Put */
    port = FindPort(name);
    if (port)
        PutMsg(port, msg);
    Permit();
    return port != NULL;
}
```

### Gotchas
- Must be inside Forbid/Permit, and the pointer is only trustworthy until Permit.
  Do the PutMsg inside the same Forbid.

**See also:** [AddPort](#addport), [PutMsg](#putmsg)

## PutMsg
`VOID PutMsg(struct MsgPort *port, struct Message *message)` — LVO -366 (-$16E)
Registers: port=A0, message=A1; no result

Queue a message on a port and perform the port's arrival action (signal or softint).

- **port** — destination port.
- **message** — the message; set `mn_ReplyPort` (where the reply goes, or NULL) and
  `mn_Length` (total size including `struct Message`). PutMsg sets `LN_TYPE` to
  `NT_MESSAGE`.

### Example
```c
#include <proto/exec.h>
#include <exec/ports.h>

struct GameMsg {
    struct Message gm_Msg;
    LONG           gm_Command;
    LONG           gm_Result;
};

LONG Transact(struct MsgPort *server, struct MsgPort *reply, LONG cmd)
{
    struct GameMsg gm;

    gm.gm_Msg.mn_Node.ln_Type = NT_MESSAGE;
    gm.gm_Msg.mn_ReplyPort    = reply;
    gm.gm_Msg.mn_Length       = sizeof(gm);
    gm.gm_Command             = cmd;

    PutMsg(server, &gm.gm_Msg);
    while (GetMsg(reply) != &gm.gm_Msg)   /* stack message: wait for THIS reply */
        WaitPort(reply);
    return gm.gm_Result;
}
```

### Gotchas
- A message can be on one port at a time; do not reuse, free or let it go out of scope
  (stack messages!) before the reply arrives.
- Message memory is shared, not copied: anything the receiver reads must stay valid
  and, if another task or interrupt touches it, be `MEMF_PUBLIC`.

**See also:** [GetMsg](#getmsg), [ReplyMsg](#replymsg), [WaitPort](#waitport),
[FindPort](#findport)

## GetMsg
`struct Message * GetMsg(struct MsgPort *port)` — LVO -372 (-$174)
Registers: port=A0; result in D0

Remove and return the first message queued on a port, or 0 if the port is empty.

- **port** — port to read.
- **Result** — the message (now owned by you until replied), or 0. Never waits.

### Gotchas
- Always loop until 0: several messages may arrive per signal, and the signal may be
  set with nothing queued.
- Only one task may wait on a given port.
- Receiving a message does not free it for the sender: [ReplyMsg](#replymsg) it (unless
  the protocol says otherwise).

**See also:** [WaitPort](#waitport), [Wait](#wait), [PutMsg](#putmsg), [ReplyMsg](#replymsg)

## ReplyMsg
`VOID ReplyMsg(struct Message *message)` — LVO -378 (-$17A)
Registers: message=A1; no result

Return a received message to its sender's reply port.

- **message** — the message; it is put on `mn_ReplyPort` with type `NT_REPLYMSG`. If
  `mn_ReplyPort` is NULL the type becomes `NT_FREEMSG` and nothing is queued.

Callable from interrupts.

### Gotchas
- After ReplyMsg the message belongs to the sender again: do not read or write it.
- Reply every message you GetMsg (Intuition, Workbench startup and device messages
  included) or the sender may wait forever.

**See also:** [GetMsg](#getmsg), [PutMsg](#putmsg)

## WaitPort
`struct Message * WaitPort(struct MsgPort *port)` — LVO -384 (-$180)
Registers: port=A0; result in D0

Sleep until a port has a message; return the first one without removing it.

- **port** — the port to wait on (its `mp_SigTask` must be the calling task).
- **Result** — pointer to the first queued message; it is still on the port.

### Example
```asm
        include "lvo/exec_lib.i"

        move.l  4.w,a6
.wait:  move.l  replyport,a0
        jsr     _LVOWaitPort(a6)
.next:  move.l  replyport,a0
        jsr     _LVOGetMsg(a6)          ; really take it off
        tst.l   d0
        beq.s   .wait                   ; queue empty again
        move.l  d0,a1
        ; ... handle message in a1 ...
        jsr     _LVOReplyMsg(a6)
        bra.s   .next
```

### Gotchas
- Always follow with a GetMsg loop; WaitPort itself removes nothing.
- To wait on several ports (or ports plus CTRL-C) OR their signal masks into one
  [Wait](#wait) instead.
- If a message is already queued it returns at once and the port's signal bit may stay
  set, so a later Wait can wake up with the port empty. Plan for it.

**See also:** [GetMsg](#getmsg), [Wait](#wait)
