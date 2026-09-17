# exec.library: semaphores

A `struct SignalSemaphore` (exec/semaphores.h, `SS_SIZE` = $2E) is a task-level lock:
`ss_Link` (Node: name/pri for public semaphores), `ss_NestCount`, `ss_WaitQueue` (MinList of
waiters), `ss_MultipleLink` (used by ObtainSemaphoreList), `ss_Owner` (Task holding the
exclusive lock) and `ss_QueueCount`. Zero it, InitSemaphore it (or AddSemaphore it to make it
public), then bracket every access with an Obtain/Release pair. Locks nest per task and can be
exclusive (one owner) or shared (many readers). Unlike Forbid(), only tasks that want the same
lock are held up. Obtaining may Wait(), so none of these calls belong in interrupt code.

## InitSemaphore
`VOID InitSemaphore(struct SignalSemaphore *sigSem)` — LVO -558 (-$22E)
Registers: sigSem=A0; no result

Prepare a zeroed SignalSemaphore for use as a private lock.

- **sigSem** — the semaphore structure. All fields must be zero before the call (allocate
  with `MEMF_CLEAR` or use static storage). Nothing is allocated; list headers and counters
  are set up in place.

After this the address may be handed to any number of tasks.

### Example
```c
#include <proto/exec.h>
#include <exec/semaphores.h>

static struct SignalSemaphore listLock;     /* static = zeroed */
static struct MinList sharedList;

void SetupShared(void)
{
    InitSemaphore(&listLock);
    sharedList.mlh_Head     = (struct MinNode *)&sharedList.mlh_Tail;
    sharedList.mlh_Tail     = NULL;
    sharedList.mlh_TailPred = (struct MinNode *)&sharedList.mlh_Head;
}

void AddItem(struct MinNode *n)
{
    ObtainSemaphore(&listLock);
    AddTail((struct List *)&sharedList, (struct Node *)n);
    ReleaseSemaphore(&listLock);
}
```

### Gotchas
- Do not InitSemaphore a semaphore that is in use or already added with AddSemaphore.
- A non-zero structure (stack garbage, reused memory) gives undefined locking behaviour.

**See also:** [ObtainSemaphore](semaphores.md#obtainsemaphore),
[ObtainSemaphoreShared](semaphores.md#obtainsemaphoreshared),
[AttemptSemaphore](semaphores.md#attemptsemaphore),
[ReleaseSemaphore](semaphores.md#releasesemaphore), [AddSemaphore](semaphores.md#addsemaphore),
[Procure](semaphores.md#procure)

## ObtainSemaphore
`VOID ObtainSemaphore(struct SignalSemaphore *sigSem)` — LVO -564 (-$234)
Registers: sigSem=A0; no result

Take an exclusive lock, sleeping until no other task holds the semaphore.

- **sigSem** — an initialized SignalSemaphore.

If the calling task already owns the lock, the call returns at once and bumps the nest
count; each Obtain needs exactly one ReleaseSemaphore. Waiting tasks queue up and are woken
in turn.

### Example
```asm
        include "exec/semaphores.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        lea     mylock,a0               ; initialized SignalSemaphore
        jsr     _LVOObtainSemaphore(a6)
        ; ... touch the protected data ...
        lea     mylock,a0
        jsr     _LVOReleaseSemaphore(a6)
```

### Gotchas
- Preserves all registers from V37 on; before V37 it could destroy A0.
- May Wait(): never call from an interrupt, a software interrupt or supervisor code. Inside
  a Forbid() the wait breaks the Forbid while the task sleeps.
- Holding a shared lock and then asking for the exclusive lock on the same semaphore
  deadlocks the task.
- Two tasks taking two semaphores in opposite order deadlock; use a fixed order or
  ObtainSemaphoreList.

**See also:** [ReleaseSemaphore](semaphores.md#releasesemaphore),
[ObtainSemaphoreShared](semaphores.md#obtainsemaphoreshared),
[AttemptSemaphore](semaphores.md#attemptsemaphore),
[ObtainSemaphoreList](semaphores.md#obtainsemaphorelist), [Procure](semaphores.md#procure)

## ObtainSemaphoreShared
`VOID ObtainSemaphoreShared(struct SignalSemaphore *sigSem)` — LVO -678 (-$2A6)
Registers: sigSem=A0; no result

Take a shared (read) lock, sleeping while another task holds it exclusively.

- **sigSem** — an initialized SignalSemaphore. Any semaphore works, including ones set up by
  pre-V36 code.

Any number of tasks may hold shared locks together; an exclusive locker waits until all of
them release, and shared lockers wait while an exclusive lock is held. Shared locks nest and
are released with ReleaseSemaphore (there is no separate shared release call).

Since V36.

### Example
```c
ObtainSemaphoreShared(&listLock);            /* many readers at once */
for (n = sharedList.mlh_Head; n->mln_Succ; n = n->mln_Succ)
    count++;
ReleaseSemaphore(&listLock);
```

### Gotchas
- Preserves all registers from V37 on.
- A task that holds a shared lock must not ask for the exclusive lock on the same semaphore.
- Before V39, calling this while already holding the exclusive lock deadlocks. V39+ just
  nests the lock. Portable pattern: try AttemptSemaphoreShared, then AttemptSemaphore, and
  only then block in ObtainSemaphoreShared; release once either way.
- Not available on Kickstart 1.x (LVO -678 does not exist there).

**See also:** [ReleaseSemaphore](semaphores.md#releasesemaphore),
[AttemptSemaphoreShared](semaphores.md#attemptsemaphoreshared),
[ObtainSemaphore](semaphores.md#obtainsemaphore)

## AttemptSemaphore
`ULONG AttemptSemaphore(struct SignalSemaphore *sigSem)` — LVO -576 (-$240)
Registers: sigSem=A0; result in D0

Try to take an exclusive lock without sleeping.

- **sigSem** — an initialized SignalSemaphore.
- **Result** — non-zero (TRUE) if the lock was taken (or nested for the current owner);
  0 if another task holds it. Release a successful lock with ReleaseSemaphore.

### Example
```c
if (AttemptSemaphore(&listLock)) {
    UpdateCache();                           /* got it without waiting */
    ReleaseSemaphore(&listLock);
} else {
    pending = TRUE;                          /* busy: try again next frame */
}
```

### Gotchas
- Unlike ObtainSemaphore, this call does not preserve registers (normal scratch rules).
- The autodoc declares the result LONG; the NDK prototype says ULONG. Test for zero only.

**See also:** [ObtainSemaphore](semaphores.md#obtainsemaphore),
[AttemptSemaphoreShared](semaphores.md#attemptsemaphoreshared),
[ReleaseSemaphore](semaphores.md#releasesemaphore)

## AttemptSemaphoreShared
`ULONG AttemptSemaphoreShared(struct SignalSemaphore *sigSem)` — LVO -720 (-$2D0)
Registers: sigSem=A0; result in D0

Try to take a shared lock without sleeping.

- **sigSem** — an initialized SignalSemaphore.
- **Result** — non-zero if the shared lock was granted; 0 if another task holds the lock
  exclusively.

Since V37.

### Gotchas
- Does not preserve registers.
- From V39 on it also succeeds when the caller already owns the exclusive lock. Before V39 it
  fails in that case: fall back to AttemptSemaphore if you may already be the owner.

**See also:** [ObtainSemaphoreShared](semaphores.md#obtainsemaphoreshared),
[AttemptSemaphore](semaphores.md#attemptsemaphore),
[ReleaseSemaphore](semaphores.md#releasesemaphore)

## ReleaseSemaphore
`VOID ReleaseSemaphore(struct SignalSemaphore *sigSem)` — LVO -570 (-$23A)
Registers: sigSem=A0; no result

Undo one exclusive or shared lock and wake the next waiter when the count reaches zero.

- **sigSem** — a semaphore the current task has locked (by ObtainSemaphore,
  ObtainSemaphoreShared, AttemptSemaphore or AttemptSemaphoreShared).

The lock only becomes free to other tasks when releases match obtains.

### Gotchas
- Guaranteed to preserve all registers.
- Releasing more often than you obtained, or from a task that does not hold the lock,
  corrupts the semaphore state.
- V39/V40 bug: if the same task has several Procure() bids and an ObtainSemaphore() pending
  on one semaphore, `ss_NestCount` can be bumped twice.

**See also:** [ObtainSemaphore](semaphores.md#obtainsemaphore),
[ObtainSemaphoreShared](semaphores.md#obtainsemaphoreshared),
[InitSemaphore](semaphores.md#initsemaphore)

## AddSemaphore
`VOID AddSemaphore(struct SignalSemaphore *sigSem)` — LVO -600 (-$258)
Registers: sigSem=A1; no result

Initialize a named semaphore and publish it on the system semaphore list.

- **sigSem** — the semaphore with `ss_Link.ln_Name` and `ss_Link.ln_Pri` already filled in
  (the rest zero). The call initializes it itself, so no InitSemaphore is needed. The name
  string is referenced, not copied: keep it valid while the semaphore is public.

Other tasks locate it with FindSemaphore. Use InitSemaphore instead if nobody else should
find it.

### Example
```c
static struct SignalSemaphore pubSem;

pubSem.ss_Link.ln_Name = "mygame.state";
pubSem.ss_Link.ln_Pri  = 0;
AddSemaphore(&pubSem);
/* ... */
RemSemaphore(&pubSem);                       /* before the memory goes away */
```

### Gotchas
- Broken before V36. On 1.x do it by hand: set `ss_Link.ln_Type = NT_SIGNALSEM`, call
  InitSemaphore, then Enqueue the node on `SysBase->SemaphoreList` between Forbid() and
  Permit().
- A semaphore that sits in a list used with ObtainSemaphoreList cannot also be public: both
  uses need the `ss_Link` node.
- Always RemSemaphore before freeing the structure.

**See also:** [RemSemaphore](semaphores.md#remsemaphore),
[FindSemaphore](semaphores.md#findsemaphore), [InitSemaphore](semaphores.md#initsemaphore)

## RemSemaphore
`VOID RemSemaphore(struct SignalSemaphore *sigSem)` — LVO -606 (-$25E)
Registers: sigSem=A1; no result

Take a public semaphore off the system list so FindSemaphore no longer finds it.

- **sigSem** — a semaphore previously added with AddSemaphore.

### Gotchas
- Removing it does not stop tasks that already looked it up. Before freeing, a common
  pattern is Forbid(), RemSemaphore(), ObtainSemaphore(), ReleaseSemaphore(), Permit(), so
  current holders finish first (unverified).

**See also:** [AddSemaphore](semaphores.md#addsemaphore),
[FindSemaphore](semaphores.md#findsemaphore)

## FindSemaphore
`struct SignalSemaphore * FindSemaphore(STRPTR name)` — LVO -594 (-$252)
Registers: name=A1; result in D0

Look up a public signal semaphore by name.

- **name** — NUL-terminated name, matched case-sensitively against `ss_Link.ln_Name`.
- **Result** — the first matching SignalSemaphore, or 0 if none is on the list.

### Example
```c
struct SignalSemaphore *s;

Forbid();
s = FindSemaphore((STRPTR)"mygame.state");
if (s)
    ObtainSemaphore(s);                      /* locked before Permit: cannot vanish */
Permit();
if (s) {
    /* ... use the data it protects ... */
    ReleaseSemaphore(s);
}
```

### Gotchas
- The list is not arbitrated: call inside Forbid()/Permit(), and lock the semaphore before
  Permit() or the owner may remove it under you.

**See also:** [AddSemaphore](semaphores.md#addsemaphore),
[RemSemaphore](semaphores.md#remsemaphore), [ObtainSemaphore](semaphores.md#obtainsemaphore)

## ObtainSemaphoreList
`VOID ObtainSemaphoreList(struct List *sigSem)` — LVO -582 (-$246)
Registers: sigSem=A0; no result

Lock every signal semaphore on a list at once, without order-dependent deadlocks.

- **sigSem** — a `struct List` whose nodes are SignalSemaphores linked through `ss_Link`.

All locks are exclusive. Release them with ReleaseSemaphoreList.

### Gotchas
- Only one task at a time may lock the whole list: guard the call with a higher-level lock
  (for example another semaphore) that everyone takes first.
- Deadlock is possible if some other task ObtainSemaphore()s more than one member of the list
  individually; take the higher-level lock before locking several members.
- The list itself is not arbitrated, and its members cannot also be public (AddSemaphore uses
  the same node).

**See also:** [ReleaseSemaphoreList](semaphores.md#releasesemaphorelist),
[ObtainSemaphore](semaphores.md#obtainsemaphore), [AddSemaphore](semaphores.md#addsemaphore)

## ReleaseSemaphoreList
`VOID ReleaseSemaphoreList(struct List *sigSem)` — LVO -588 (-$24C)
Registers: sigSem=A0; no result

Release every semaphore on a list locked with ObtainSemaphoreList.

- **sigSem** — the same list passed to ObtainSemaphoreList.

### Gotchas
- Releasing a list you did not lock breaks every semaphore on it.

**See also:** [ObtainSemaphoreList](semaphores.md#obtainsemaphorelist),
[ReleaseSemaphore](semaphores.md#releasesemaphore)

## Procure
`ULONG Procure(struct SignalSemaphore *sigSem, struct SemaphoreMessage *bidMsg)` — LVO -540 (-$21C)
Registers: sigSem=A0, bidMsg=A1; result in D0

Post an asynchronous bid for a semaphore; the bid message is replied once you own it.

- **sigSem** — the SignalSemaphore wanted.
- **bidMsg** — a `struct SemaphoreMessage` (`ssm_Message`, `ssm_Semaphore`; asm
  `SSM_SEMAPHORE` = $14, `SSM_SIZEOF` = $18):
  - `ssm_Message.mn_ReplyPort` — a valid MsgPort; the reply arrives there.
  - `ssm_Message.mn_Node.ln_Name` — not a string: `(char *)SM_SHARED` (1) for a shared
    lock, `(char *)SM_EXCLUSIVE` (0) for exclusive. No other values.
  - `ssm_Semaphore` — on reply, points at the semaphore obtained; NULL means the bid was
    cancelled by Vacate.
- **Result** — the prototype declares ULONG; the V39 autodoc documents no result. Ignore it.

Lets a task wait on several semaphores (and other signals) at once and keep working until the
reply shows up. Give the lock back with Vacate.

Since V39.

### Example
```c
struct SemaphoreMessage bid = {0};
struct MsgPort *port = CreateMsgPort();

bid.ssm_Message.mn_ReplyPort    = port;
bid.ssm_Message.mn_Node.ln_Name = (char *)SM_EXCLUSIVE;
Procure(sem, &bid);
/* ... Wait() on port signal plus other signals ... */
if (GetMsg(port) == &bid.ssm_Message && bid.ssm_Semaphore) {
    /* we own sem now */
    Vacate(sem, &bid);
}
```

### Gotchas
- Before V39 the same LVO worked on the old, broken message-port `struct Semaphore` with a
  different interface; the SignalSemaphore behaviour exists only from V39.
- `SM_SHARED`/`SM_EXCLUSIVE` are defined in exec/semaphores.h only (not in semaphores.i): use
  1/0 in asm.
- Do not free or reuse the message while the bid is pending: Vacate it first.

**See also:** [Vacate](semaphores.md#vacate), [ObtainSemaphore](semaphores.md#obtainsemaphore),
[ObtainSemaphoreShared](semaphores.md#obtainsemaphoreshared),
[CreateMsgPort](signals-and-messages.md#createmsgport)

## Vacate
`VOID Vacate(struct SignalSemaphore *sigSem, struct SemaphoreMessage *bidMsg)` — LVO -546 (-$222)
Registers: sigSem=A0, bidMsg=A1; no result

Cancel a pending Procure() bid, or release a semaphore that the bid obtained.

- **sigSem** — the semaphore the bid was made for.
- **bidMsg** — the SemaphoreMessage given to Procure. Its `ssm_Semaphore` is cleared. If the
  bid is still waiting it is replied (with `ssm_Semaphore` NULL); if it was already granted,
  the lock is released.

Since V39.

### Gotchas
- Pre-V39 Vacate belonged to the old message semaphores and took a single argument; do not
  use Procure/Vacate below V39.
- After cancelling a pending bid, still collect the reply from your port before reusing the
  message.

**See also:** [Procure](semaphores.md#procure), [ReleaseSemaphore](semaphores.md#releasesemaphore)
