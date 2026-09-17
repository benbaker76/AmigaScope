# exec.library: tasks and CPU state

A Task is exec's unit of execution (`struct Task`, node type `NT_TASK`). A Process
(`struct Process`, `NT_PROCESS`) is a Task extended by dos.library; plain Tasks must not
call dos.library or anything that may call it -- create Processes with dos.library
CreateNewProc instead. The ready Task with the highest `ln_Pri` (signed byte) runs;
equal priorities time-slice. Forbid/Permit stop task switching, Disable/Enable also stop
interrupts; both nest through counters that are -1 when inactive (per task:
`tc_TDNestCnt`/`tc_IDNestCnt`; live copies: ExecBase `TDNestCnt` $127 / `IDNestCnt` $126).
Any Wait() -- including one hidden inside DOS or device I/O -- suspends the Forbid or
Disable until the task runs again. Supervisor/SuperState/UserState/SetSR/GetCC give
controlled access to the 680x0 supervisor state. Field offsets:
[structures topic](../topics/structures.md).

## FindTask
`struct Task * FindTask(CONST_STRPTR name)` — LVO -294 (-$126)
Registers: name=A1; result in D0

Return a pointer to the current task, or search all task lists for a named task.

- **name** — task name to look for, or NULL for "myself".
- **Result** — `struct Task *` (may really be a `struct Process`), or 0 if no task has
  that name.

### Example
```c
#include <proto/exec.h>
#include <dos/dosextens.h>

struct Task *me = FindTask(NULL);         /* fast, never fails */
BOOL fromShell = FALSE;

if (me->tc_Node.ln_Type == NT_PROCESS)
    fromShell = ((struct Process *)me)->pr_CLI != 0;
/* pr_CLI == 0 in a Process: started from Workbench -> a WBStartup message
   (workbench/startup.h) is waiting on pr_MsgPort and must be replied at exit */
```

### Gotchas
- FindTask(NULL) is cheap; a search by name is slow and keeps interrupts disabled for a
  long time. Cache the result of FindTask(NULL) instead of calling it repeatedly.
- A named task can exit at any moment: wrap the search and every use of the pointer in
  [Forbid](#forbid)/[Permit](#permit).
- Check `tc_Node.ln_Type == NT_PROCESS` before casting to `struct Process *`.
- Asm: the current task is also readable at `ThisTask(a6)` ($114), but calling
  FindTask(NULL) is the documented way.

**See also:** [SetTaskPri](#settaskpri), [AddTask](#addtask), [Forbid](#forbid)

## SetTaskPri
`BYTE SetTaskPri(struct Task *task, LONG priority)` — LVO -300 (-$12C)
Registers: task=A1, priority=D0; result in D0

Change a task's priority and return the old one; may reschedule immediately.

- **task** — task to change; FindTask(NULL) for the current one.
- **priority** — new priority, -128..127 (only the low byte is used, D0-0:8).
- **Result** — previous priority as a signed byte.

### Example
```asm
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        suba.l  a1,a1                   ; name = NULL
        jsr     _LVOFindTask(a6)
        move.l  d0,a1                   ; task = me
        moveq   #5,d0                   ; new priority
        jsr     _LVOSetTaskPri(a6)
        move.b  d0,oldpri               ; restore it before exiting
```

### Gotchas
- Result is a BYTE: use `move.b`/`ext.w`/`ext.l` in asm, never the full D0.
- A busy-looping task at a raised priority starves every lower-priority task (input
  handling, DOS, Workbench). Most programs stay at 0; restore the old value on exit.
- A context switch can happen before SetTaskPri returns.

**See also:** [FindTask](#findtask), [Forbid](#forbid)

## Forbid
`VOID Forbid(VOID)` — LVO -132 (-$84)
Registers: none; no result

Stop task rescheduling until the matching Permit; interrupts keep running.

Calls nest: each Forbid needs exactly one [Permit](#permit). All registers are preserved.

### Example
```c
#include <proto/exec.h>
#include <exec/execbase.h>

/* Count the libraries in memory; nothing that can Wait() inside the Forbid */
ULONG count = 0;
struct Node *n;

Forbid();
for (n = SysBase->LibList.lh_Head; n->ln_Succ != NULL; n = n->ln_Succ)
    count++;
Permit();
```

### Gotchas
- Wait() -- directly or inside DOS calls, DoIO, OpenLibrary of a disk library, printf to
  a console -- breaks the Forbid while the task sleeps. Copy what you need inside the
  Forbid, print it after Permit.
- Keep Forbid sections short; the whole machine's multitasking stops.
- Useless in interrupt code: interrupts always pre-empt tasks.
- Prefer a semaphore when only cooperating tasks need locking.
- exec/ables.i has `FORBID`/`PERMIT` macros (`FORBID` just bumps `TDNestCnt(a6)`; `PERMIT`
  still calls _LVOPermit). The function calls are the safe, portable choice.
- Game/demo takeover (Forbid + graphics.library LoadView, OwnBlitter, WaitTOF ...) is
  covered with the graphics.library functions.

**See also:** [Permit](#permit), [Disable](#disable),
[ObtainSemaphore](semaphores.md#obtainsemaphore)

## Permit
`VOID Permit(VOID)` — LVO -138 (-$8A)
Registers: none; no result

Undo one Forbid; task switching resumes when the nesting count drops back to -1.

All registers are preserved. Unbalanced calls corrupt `TDNestCnt` and either leave the
system single-tasking or re-enable switching too early.

### Gotchas
- Exactly one Permit per Forbid, on every exit path (including error paths).
- A pending reschedule happens inside Permit, so another task may run before it returns.

**See also:** [Forbid](#forbid), [Enable](#enable)

## Disable
`VOID Disable(VOID)` — LVO -120 (-$78)
Registers: none; no result

Block interrupt processing (and therefore task switching) until the matching Enable.

Disable implies Forbid. Calls nest; one [Enable](#enable) per Disable. All registers are
preserved. It may be called from interrupt code, where it locks out the higher levels.

### Example
```asm
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        jsr     _LVODisable(a6)
        move.l  (a2),d0                 ; tiny critical section shared with an
        addq.l  #1,d0                   ; interrupt server
        move.l  d0,(a2)
        jsr     _LVOEnable(a6)
```

### Gotchas
- Keep it under roughly 250 microseconds; longer blocks break serial I/O and other
  time-critical hardware.
- If only one interrupt source matters, mask just that source in INTENA instead
  (`move.w #INTF_PORTS,$dff09a` clears the PORTS enable; write it back with
  `INTF_SETCLR!INTF_PORTS`). See the amiga-hardware skill for INTENA.
- Wait() inside a Disable breaks it until the task is scheduled again.
- exec/ables.i defines a `DISABLE` macro (writes INTENA via an external `_intena` symbol and
  bumps `IDNestCnt`); the autodoc asks for the real function call instead.

**See also:** [Enable](#enable), [Forbid](#forbid), [SetSR](#setsr)

## Enable
`VOID Enable(VOID)` — LVO -126 (-$7E)
Registers: none; no result

Undo one Disable; interrupts are re-enabled when the nesting count returns to -1.

All registers are preserved.

### Gotchas
- Exactly one Enable per Disable. An extra Enable turns interrupts on while some other
  code still believes they are off.

**See also:** [Disable](#disable), [Permit](#permit)

## AddTask
`APTR AddTask(struct Task *task, CONST APTR initPC, CONST APTR finalPC)` — LVO -282 (-$11A)
Registers: task=A1, initPC=A2, finalPC=A3; result in D0

Start a task from a caller-built Task structure and stack.

- **task** — `struct Task`, all unused fields zero. Set `tc_Node.ln_Type = NT_TASK`,
  `ln_Pri`, `ln_Name`, `tc_SPLower` (stack base), `tc_SPUpper` (base + size) and
  `tc_SPReg` (initial SP, normally = `tc_SPUpper`; data may be preloaded above it).
- **initPC** — entry point. All registers start at zero.
- **finalPC** — address used as the outermost return address; NULL = exec's default
  finalizer, which removes the task.
- **Result** — V36+: the task pointer, or NULL on failure. Undefined before V36.

Memory lists linked into `tc_MemEntry` (from [AllocEntry](memory.md#allocentry)) are freed
automatically by [RemTask](#remtask), so the task can own its own structure and stack.

### Example
```c
#include <proto/exec.h>
#include <exec/memory.h>
#include <exec/tasks.h>

struct TaskMem {                    /* struct MemList with two MemEntry slots */
    struct Node     ml_Node;
    UWORD           ml_NumEntries;
    struct MemEntry ml_ME[2];
};

struct Task *SpawnTask(STRPTR name, BYTE pri, VOID (*code)(void), ULONG stackSize)
{
    struct TaskMem req = { .ml_NumEntries = 2, .ml_ME = {
        { { .meu_Reqs = MEMF_PUBLIC | MEMF_CLEAR }, sizeof(struct Task) },
        { { .meu_Reqs = MEMF_PUBLIC | MEMF_CLEAR }, stackSize } } };
    struct MemList *ml = AllocEntry((struct MemList *)&req);
    struct Task *tc;

    if ((ULONG)ml & 0x80000000UL)   /* bit 31 set = allocation failed */
        return NULL;
    tc = ml->ml_ME[0].me_Addr;
    tc->tc_Node.ln_Type = NT_TASK;
    tc->tc_Node.ln_Pri  = pri;
    tc->tc_Node.ln_Name = (char *)name;          /* not copied: keep it valid */
    tc->tc_SPLower = ml->ml_ME[1].me_Addr;
    tc->tc_SPUpper = (APTR)((ULONG)tc->tc_SPLower + stackSize);
    tc->tc_SPReg   = tc->tc_SPUpper;
    /* empty tc_MemEntry (NewList), then let RemTask free both blocks */
    tc->tc_MemEntry.lh_Head     = (struct Node *)&tc->tc_MemEntry.lh_Tail;
    tc->tc_MemEntry.lh_Tail     = NULL;
    tc->tc_MemEntry.lh_TailPred = (struct Node *)&tc->tc_MemEntry.lh_Head;
    AddHead(&tc->tc_MemEntry, &ml->ml_Node);

    if (AddTask(tc, (APTR)code, NULL) == NULL) { /* V36+ */
        FreeEntry(ml);
        return NULL;
    }
    return tc;                      /* may already be running */
}
```

### Gotchas
- A plain Task must not call dos.library (or OpenLibrary/OpenDevice of disk-based code
  that needs DOS); use dos.library CreateNewProc for anything that does file I/O.
- Stack: about 256 bytes is enough for exec-only code, 4K or more if other system code
  is called. C code usually needs more; never underestimate.
- The new task may run (and even finish) before AddTask returns if its priority is
  higher. Hand it data before AddTask (e.g. via `tc_UserData`), not after.
- amiga.lib CreateTask/DeleteTask do the above for you but amiga.lib is not linked in
  Bartman `-nostdlib` builds.
- `tc_MemEntry` must be a valid (possibly empty) list before you AddHead into it.

**See also:** [RemTask](#remtask), [FindTask](#findtask), [AllocEntry](memory.md#allocentry),
[StackSwap](#stackswap)

## RemTask
`VOID RemTask(struct Task *task)` — LVO -288 (-$120)
Registers: task=A1; no result

Remove a task from the system and free every MemList on its `tc_MemEntry` list.

- **task** — task to remove, or NULL to remove the calling task (does not return; the
  next ready task runs).

Release everything the task owns (signals, ports, libraries, memory not on
`tc_MemEntry`) before calling it.

### Gotchas
- Removing another task is dangerous: it may be holding a semaphore, be inside a library
  call or have messages outstanding. Signal it and let it RemTask(NULL) itself.
- Before V36, removing a CreateTask-made task other than yourself could crash; bracket
  the call with Forbid/Permit on old systems.
- Returning from the task's entry code with finalPC NULL ends in the same removal.

**See also:** [AddTask](#addtask), [AllocEntry](memory.md#allocentry), [Signal](signals-and-messages.md#signal)

## StackSwap
`VOID StackSwap(struct StackSwapStruct *newStack)` — LVO -732 (-$2DC)
Registers: newStack=A0; no result

Switch the current task to a caller-supplied stack; call again to switch back.

- **newStack** — `struct StackSwapStruct`: `stk_Lower` (lowest address), `stk_Upper`
  (lowest + size), `stk_Pointer` (SP to start with, normally `stk_Upper`). On return it
  holds the old stack values, so a second StackSwap with the same structure restores
  them.

Since V37.

### Example
```c
#include <proto/exec.h>
#include <exec/tasks.h>
#include <exec/memory.h>

#define BIG_STACK 32768

static struct StackSwapStruct sss;      /* static: SP-relative locals die on swap */
static APTR bigStack;
static LONG result;

__attribute__((noinline)) static LONG DeepWork(void) { /* ... */ return 0; }

LONG RunOnBigStack(void)
{
    bigStack = AllocMem(BIG_STACK, MEMF_PUBLIC);
    if (bigStack == NULL)
        return -1;
    sss.stk_Lower   = bigStack;
    sss.stk_Upper   = (ULONG)bigStack + BIG_STACK;
    sss.stk_Pointer = (APTR)sss.stk_Upper;
    StackSwap(&sss);
    result = DeepWork();                /* runs on the new stack */
    StackSwap(&sss);                    /* back on the original stack */
    FreeMem(bigStack, BIG_STACK);
    return result;
}
```

### Gotchas
- Nothing is copied to the new stack. Stack-relative data (C locals with
  `-fomit-frame-pointer`, saved registers) from before the swap is not reachable until
  you swap back: keep shared variables static and call a separate function between
  the two swaps.
- Always swap back before returning from the function that swapped, and before exit.
- Not available before V37.

**See also:** [AddTask](#addtask), [Supervisor](#supervisor)

## AllocTrap
`LONG AllocTrap(LONG trapNum)` — LVO -342 (-$156)
Registers: trapNum=D0; result in D0

Allocate one of the 68000 TRAP #0-#15 vectors for the current task.

- **trapNum** — wanted trap 0..15, or -1 for any free one.
- **Result** — allocated trap number, or -1 if taken / none free.

`TRAP #n` in this task then goes to the task's `tc_TrapCode` handler (a system default
unless you set one). On entry 0(SP) holds the exception vector number (32..47) as a
longword, followed by the CPU's exception frame. `tc_TrapData` is not used.

### Gotchas
- Affects only the calling task. Do not allocate or free traps from exception code.
- Never write the CPU vector table yourself (the VBR may have moved it on 68010+).
- `SYS_TRAPALLOC` ($8000) marks TRAP #15 as pre-allocated by the system.
- A custom `tc_TrapCode` must pop the vector-number longword before its RTE.

**See also:** [FreeTrap](#freetrap), [Supervisor](#supervisor)

## FreeTrap
`VOID FreeTrap(LONG trapNum)` — LVO -348 (-$15C)
Registers: trapNum=D0; no result

Release a trap number obtained with AllocTrap.

- **trapNum** — the trap number (0..15) to free.

### Gotchas
- Must run in the same task that allocated the trap, and not from exception code.

**See also:** [AllocTrap](#alloctrap)

## Supervisor
`ULONG Supervisor(ULONG (*CONST userFunction)())` — LVO -30 (-$1E)
Registers: userFunction=A5; result in D0

Run a short routine in supervisor mode; the routine must end with RTE.

- **userFunction** — address of the routine, passed in A5 (not A0/A1).
- **Result** — registers are neither saved nor changed by the call: whatever the routine
  leaves in D0 (or any register) is the result.

### Example
```asm
        include "exec/execbase.i"
        include "lvo/exec_lib.i"

; out: d0 = vector base register (0 on a 68000)
GetVBR:
        movem.l a5/a6,-(sp)
        moveq   #0,d0
        move.l  4.w,a6
        btst    #AFB_68010,AttnFlags+1(a6)      ; AttnFlags is a UWORD at $128
        beq.s   .done
        lea     .readvbr(pc),a5
        jsr     _LVOSupervisor(a6)
.done:  movem.l (sp)+,a5/a6
        rts
.readvbr:
        dc.w    $4e7a,$0801             ; movec vbr,d0 (68010+ only)
        rte
```

```c
/* Bartman template style: __attribute__((interrupt)) makes GCC end with RTE */
static __attribute__((interrupt)) void ReadVBR(void)
{
    __asm__ volatile(".short 0x4e7a, 0x0801");   /* movec.l vbr,d0 */
}

APTR vbr = NULL;
if (SysBase->AttnFlags & AFF_68010)
    vbr = (APTR)Supervisor((ULONG (*)())ReadVBR);
```

### Gotchas
- Same rules as interrupt code: no system calls inside, keep it short.
- A5 is overwritten by the call; save it if you use it (A5 is often a frame pointer).
- `movec` exists only on 68010+: test `AFF_68010` in `AttnFlags` first. The `dc.w`
  form assembles even with `-m68000`.

**See also:** [SuperState](#superstate), [UserState](#userstate), [SetSR](#setsr), [GetCC](#getcc)

## SuperState
`APTR SuperState(VOID)` — LVO -150 (-$96)
Registers: none; result in D0

Switch to supervisor mode but keep running on the task's user stack.

- **Result** — the system (supervisor) stack pointer to pass to
  [UserState](#userstate) later, or 0 if already in supervisor mode (then nothing
  changed).

### Gotchas
- All interrupts that arrive meanwhile (with nesting) use your user stack: it must be
  big enough for that.
- If the result is 0, do not call UserState.
- Prefer [Supervisor](#supervisor) for short privileged code.

**See also:** [UserState](#userstate), [Supervisor](#supervisor)

## UserState
`VOID UserState(APTR sysStack)` — LVO -156 (-$9C)
Registers: sysStack=D0; no result

Return from SuperState's supervisor mode to user mode on the user stack.

- **sysStack** — the value SuperState returned.

### Gotchas
- Only call it from supervisor mode entered via SuperState.
- Broken in V33/V34 Kickstart; SetPatch 1.31 fixes it.

**See also:** [SuperState](#superstate)

## SetSR
`ULONG SetSR(ULONG newSR, ULONG mask)` — LVO -144 (-$90)
Registers: newSR=D0, mask=D1; result in D0

Read and optionally change bits of the 680x0 status register.

- **newSR** — new values for the bits selected by mask.
- **mask** — bits to change; 0 changes nothing.
- **Result** — the complete SR before the change.

### Example
```c
ULONG oldSR = SetSR(0x0300, 0x0700);    /* IPL 3: masks levels 1-3 (VERTB, COPER...) */
/* ... */
SetSR(oldSR, 0x0700);                   /* restore the previous level */

UWORD sr = (UWORD)SetSR(0, 0);          /* just read it */
```

### Gotchas
- Raising the IPL has the same risks as [Disable](#disable); keep it very short.
- Changing the S or T bits this way is asking for trouble.

**See also:** [GetCC](#getcc), [Disable](#disable), [Supervisor](#supervisor)

## GetCC
`ULONG GetCC(VOID)` — LVO -528 (-$210)
Registers: none; result in D0

Return the CPU condition codes in a way that works on every 680x0.

- **Result** — the condition code bits (low byte of SR).

All registers except D0 are preserved; the function may be just code inside the jump
table.

### Gotchas
- `move sr,<ea>` is privileged on the 68010 and later (traps in user mode) and
  `move ccr,<ea>` does not exist on the 68000: use GetCC in code that must run on both.

**See also:** [SetSR](#setsr)
