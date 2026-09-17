# Core exec structures

The exec structures you read and fill in most often, with exact C field names, asm labels
and offsets. All offsets are hex, from the start of the structure. They were checked against
the NDK 3.9 `include_i/exec/*.i` (resolved with vasm) and against Bartman's GCC `offsetof`,
and the two agree. The 68k ABI aligns fields to 2 bytes, so an `int` is never padded out to 4.

Use the labels, never raw numbers: `move.l LN_NAME(a0),a1`, `node->ln_Name`.
asm labels come from `include "exec/nodes.i"` and friends. Every `STRUCTURE` also defines a
`_SIZE` or `_SIZEOF` label.

## Node and MinNode

Every item on an exec list starts with one of these.

| Off | asm | C (`struct Node`) | Type | Meaning |
|---|---|---|---|---|
| $00 | `LN_SUCC` | `ln_Succ` | `struct Node *` | next node |
| $04 | `LN_PRED` | `ln_Pred` | `struct Node *` | previous node |
| $08 | `LN_TYPE` | `ln_Type` | `UBYTE` | `NT_` type |
| $09 | `LN_PRI` | `ln_Pri` | `BYTE` | priority (-128..127), used by Enqueue |
| $0A | `LN_NAME` | `ln_Name` | `char *` | NUL-terminated name, or NULL |
| $0E | `LN_SIZE` | `sizeof(struct Node)` = 14 | | word aligned |

`struct MinNode`: `mln_Succ` ($00, `MLN_SUCC`), `mln_Pred` ($04, `MLN_PRED`); `MLN_SIZE` = 8.
A MinNode has no type, priority or name, so it can't be used with Enqueue or FindName.

Node types (`LN_TYPE`, exec/nodes.h): `NT_UNKNOWN` 0, `NT_TASK` 1, `NT_INTERRUPT` 2,
`NT_DEVICE` 3, `NT_MSGPORT` 4, `NT_MESSAGE` 5, `NT_FREEMSG` 6, `NT_REPLYMSG` 7,
`NT_RESOURCE` 8, `NT_LIBRARY` 9, `NT_MEMORY` 10, `NT_SOFTINT` 11, `NT_FONT` 12,
`NT_PROCESS` 13, `NT_SEMAPHORE` 14, `NT_SIGNALSEM` 15, `NT_BOOTNODE` 16, `NT_KICKMEM` 17,
`NT_GRAPHICS` 18, `NT_DEATHMESSAGE` 19, `NT_USER` 254 (user types count down from here),
`NT_EXTENDED` 255.

## List and MinList

| Off | asm | C (`struct List`) | Type | Meaning |
|---|---|---|---|---|
| $00 | `LH_HEAD` | `lh_Head` | `struct Node *` | first node, or `&lh_Tail` when empty |
| $04 | `LH_TAIL` | `lh_Tail` | `struct Node *` | always NULL |
| $08 | `LH_TAILPRED` | `lh_TailPred` | `struct Node *` | last node, or the header itself when empty |
| $0C | `LH_TYPE` | `lh_Type` | `UBYTE` | `NT_` type of the members |
| $0D | `LH_pad` | `l_pad` | `UBYTE` | padding |
| $0E | `LH_SIZE` | `sizeof(struct List)` = 14 | | word aligned |

`struct MinList`: `mlh_Head` ($00, `MLH_HEAD`), `mlh_Tail` ($04, `MLH_TAIL`),
`mlh_TailPred` ($08, `MLH_TAILPRED`); `MLH_SIZE` = 12.

The header holds two overlapping fake nodes. `lh_Head`/`lh_Tail` form the head sentinel and
`lh_Tail`/`lh_TailPred` form the tail sentinel. The last real node's `ln_Succ` points at
`&lh_Tail`, whose own `ln_Succ` (= `lh_Tail`) is NULL. So:

- **Empty test:** `list->lh_TailPred == (struct Node *)list`. This is the `IsListEmpty(list)`
  macro in exec/lists.h. In asm, `cmp.l LH_TAILPRED(a0),a0` then `beq empty` (the TSTLIST
  and IFEMPTY macros).
  Equivalently, `lh_Head->ln_Succ == NULL`.
- **Iterate:** go on while the *current* node's `ln_Succ` is non-NULL. Don't test the node
  pointer for NULL: at the end it points at `&lh_Tail`, not NULL.
- **Initialise:** a zeroed List is NOT empty, it's corrupt. Set `lh_Head = &lh_Tail`,
  `lh_Tail = NULL`, `lh_TailPred = &lh_Head` (asm macro `NEWLIST` in exec/lists.i, V45
  [NewMinList](../exec/lists.md#newminlist). amiga.lib's NewList isn't linked in `-nostdlib`
  builds, but Bartman's `<inline/alib.h>` has an inline `NewList()` macro; `<proto/alib.h>`
  does not compile with GCC 15).

```c
#include <proto/exec.h>
#include <exec/execbase.h>

/* Count the libraries in memory. Read-only walk of a system list: Forbid. */
ULONG CountLibraries(void)
{
    struct Node *n;
    ULONG count = 0;

    Forbid();
    for (n = SysBase->LibList.lh_Head; n->ln_Succ != NULL; n = n->ln_Succ)
        count++;                 /* no DOS/printf in here: they Wait and break Forbid */
    Permit();
    return count;
}

void InitList(struct List *l, UBYTE type)
{
    l->lh_Head     = (struct Node *)&l->lh_Tail;
    l->lh_Tail     = NULL;
    l->lh_TailPred = (struct Node *)&l->lh_Head;
    l->lh_Type     = type;
}
```

```asm
        include "exec/types.i"
        include "exec/lists.i"
        include "exec/execbase.i"
        include "lvo/exec_lib.i"

; count libraries -> d2
CountLibs:
        move.l  a2,-(sp)
        move.l  4.w,a6
        moveq   #0,d2
        jsr     _LVOForbid(a6)
        move.l  LibList+LH_HEAD(a6),a2
.loop   move.l  LN_SUCC(a2),d0          ; NULL -> a2 is the tail sentinel
        beq.s   .done
        addq.l  #1,d2                   ; a2 = a real node here
        move.l  d0,a2
        bra.s   .loop
.done   jsr     _LVOPermit(a6)          ; Permit preserves all registers
        move.l  (sp)+,a2
        rts
```

## Library

Library bases (and devices, which add nothing, `DD_SIZE` = `LIB_SIZE`) start with a Node.
The jump table sits at negative offsets from the base.

| Off | asm | C (`struct Library`) | Type | Meaning |
|---|---|---|---|---|
| $00 | -- | `lib_Node` | `struct Node` | name in `ln_Name`, `NT_LIBRARY`/`NT_DEVICE` |
| $0E | `LIB_FLAGS` | `lib_Flags` | `UBYTE` | `LIBF_` flags |
| $0F | `LIB_pad` | `lib_pad` | `UBYTE` | |
| $10 | `LIB_NEGSIZE` | `lib_NegSize` | `UWORD` | bytes before the base (jump table) |
| $12 | `LIB_POSSIZE` | `lib_PosSize` | `UWORD` | bytes after the base |
| $14 | `LIB_VERSION` | `lib_Version` | `UWORD` | major version |
| $16 | `LIB_REVISION` | `lib_Revision` | `UWORD` | minor revision |
| $18 | `LIB_IDSTRING` | `lib_IdString` | `APTR` | ID string |
| $1C | `LIB_SUM` | `lib_Sum` | `ULONG` | checksum |
| $20 | `LIB_OPENCNT` | `lib_OpenCnt` | `UWORD` | current opens |
| $22 | `LIB_SIZE` | `sizeof(struct Library)` = 34 | | not a longword multiple |

`LIBF_SUMMING` 1, `LIBF_CHANGED` 2, `LIBF_SUMUSED` 4, `LIBF_DELEXP` 8. `LIBF_EXP0CNT` $10
exists only in the asm include. Jump table constants: `LIB_VECTSIZE` 6, `LIB_RESERVED` 4.
See [calling convention](calling-convention.md).

## Task

`struct Task` (asm `STRUCTURE TC_Struct,LN_SIZE`). Change fields through exec functions
wherever one exists.

| Off | asm | C | Type | Meaning |
|---|---|---|---|---|
| $00 | -- | `tc_Node` | `struct Node` | `ln_Type` = `NT_TASK` or `NT_PROCESS`; `ln_Pri` = priority; `ln_Name` |
| $0E | `TC_FLAGS` | `tc_Flags` | `UBYTE` | `TF_` flags |
| $0F | `TC_STATE` | `tc_State` | `UBYTE` | `TS_` state |
| $10 | `TC_IDNESTCNT` | `tc_IDNestCnt` | `BYTE` | Disable nesting (saved per task) |
| $11 | `TC_TDNESTCNT` | `tc_TDNestCnt` | `BYTE` | Forbid nesting (saved per task) |
| $12 | `TC_SIGALLOC` | `tc_SigAlloc` | `ULONG` | allocated signal bits |
| $16 | `TC_SIGWAIT` | `tc_SigWait` | `ULONG` | signals being waited for |
| $1A | `TC_SIGRECVD` | `tc_SigRecvd` | `ULONG` | signals received |
| $1E | `TC_SIGEXCEPT` | `tc_SigExcept` | `ULONG` | signals that raise exceptions |
| $22 | `tc_ETask` | `tc_TrapAlloc`, `tc_TrapAble` | asm `APTR` / C 2x`UWORD` | private (headers disagree) |
| $26 | `TC_EXCEPTDATA` | `tc_ExceptData` | `APTR` | exception handler data |
| $2A | `TC_EXCEPTCODE` | `tc_ExceptCode` | `APTR` | exception handler |
| $2E | `TC_TRAPDATA` | `tc_TrapData` | `APTR` | trap handler data |
| $32 | `TC_TRAPCODE` | `tc_TrapCode` | `APTR` | trap handler |
| $36 | `TC_SPREG` | `tc_SPReg` | `APTR` | saved stack pointer |
| $3A | `TC_SPLOWER` | `tc_SPLower` | `APTR` | stack lower bound |
| $3E | `TC_SPUPPER` | `tc_SPUpper` | `APTR` | stack upper bound + 2 |
| $42 | `TC_SWITCH` | `tc_Switch` | code ptr | called when losing the CPU (`TF_SWITCH`) |
| $46 | `TC_LAUNCH` | `tc_Launch` | code ptr | called when gaining the CPU (`TF_LAUNCH`) |
| $4A | `TC_MEMENTRY` | `tc_MemEntry` | `struct List` | MemLists freed by RemTask |
| $58 | `TC_Userdata` | `tc_UserData` | `APTR` | free for the task's own use |
| $5C | `TC_SIZE` | `sizeof(struct Task)` = 92 | | |

Note the asm spelling `TC_Userdata` against C `tc_UserData`.
States: `TS_INVALID` 0, `TS_ADDED` 1, `TS_RUN` 2, `TS_READY` 3, `TS_WAIT` 4, `TS_EXCEPT` 5,
`TS_REMOVED` 6.
Flags: `TF_PROCTIME` $01, `TF_ETASK` $08, `TF_STACKCHK` $10, `TF_EXCEPT` $20,
`TF_SWITCH` $40, `TF_LAUNCH` $80.
System signals: `SIGF_ABORT` $01, `SIGF_CHILD` $02, `SIGF_BLIT` = `SIGF_SINGLE` $10,
`SIGF_INTUITION` $20, `SIGF_NET` $80, `SIGF_DOS` $100. `SYS_SIGALLOC` $FFFF: the low 16
bits are reserved for the system.

Approximate stack size of a task: `(ULONG)tc_SPUpper - (ULONG)tc_SPLower`.

## Process (dos/dosextens.h)

A DOS process is a Task followed by a MsgPort and DOS fields. The asm labels
(dos/dosextens.i) have the same spelling as the C fields.

| Off | Field | Type | Meaning |
|---|---|---|---|
| $00 | `pr_Task` | `struct Task` | the embedded task (`NT_PROCESS`) |
| $5C | `pr_MsgPort` | `struct MsgPort` | process port. DOS BPTR process handles point here, not at $00 |
| $7E | `pr_Pad` | `WORD` | |
| $80 | `pr_SegList` | `BPTR` | segment array |
| $84 | `pr_StackSize` | `LONG` | stack size in bytes |
| $8C | `pr_TaskNum` | `LONG` | CLI number, 0 if not a CLI |
| $90 | `pr_StackBase` | `BPTR` | high end of stack |
| $94 | `pr_Result2` | `LONG` | secondary result = what dos.library IoErr returns |
| $98 | `pr_CurrentDir` | `BPTR` | current directory lock |
| $9C | `pr_CIS` | `BPTR` | CLI input stream |
| $A0 | `pr_COS` | `BPTR` | CLI output stream |
| $A4 | `pr_ConsoleTask` | `APTR` | console handler port |
| $A8 | `pr_FileSystemTask` | `APTR` | default filesystem port |
| $AC | `pr_CLI` | `BPTR` | CommandLineInterface, 0 when started from Workbench |
| $B8 | `pr_WindowPtr` | `APTR` | requester window. -1 = no DOS requesters |
| $BC | `pr_HomeDir` | `BPTR` | PROGDIR: lock (V36) |
| $C0 | `pr_Flags` | `LONG` | `PRF_` flags (V36) |
| $CC | `pr_Arguments` | `UBYTE *` | argument string (V36) |
| $D0 | `pr_LocalVars` | `struct MinList` | local shell variables (V36) |
| $E0 | `pr_CES` | `BPTR` | error stream, NULL = use `pr_COS` (V36) |
| $E4 | `pr_SIZEOF` | = 228 | |

```c
struct Task *me = FindTask(NULL);
if (me->tc_Node.ln_Type == NT_PROCESS) {
    struct Process *pr = (struct Process *)me;
    if (pr->pr_CLI == 0) {
        /* Workbench start: a WBStartup message waits on pr->pr_MsgPort.
           WaitPort + GetMsg it first; ReplyMsg it under Forbid at exit
           (standard startup practice). */
    }
}
```

AllocMem sets `pr_Result2` to `ERROR_NO_FREE_STORE` on failure when the caller is a process.

## Message and MsgPort

| Off | asm | C (`struct MsgPort`) | Type | Meaning |
|---|---|---|---|---|
| $00 | -- | `mp_Node` | `struct Node` | `NT_MSGPORT`; name/pri only for public ports |
| $0E | `MP_FLAGS` | `mp_Flags` | `UBYTE` | arrival action: `PA_SIGNAL` 0, `PA_SOFTINT` 1, `PA_IGNORE` 2 (mask `PF_ACTION` 3) |
| $0F | `MP_SIGBIT` | `mp_SigBit` | `UBYTE` | signal bit number (not a mask) |
| $10 | `MP_SIGTASK` | `mp_SigTask` | `APTR` | task to signal (`MP_SOFTINT`/`mp_SoftInt` alias: Interrupt) |
| $14 | `MP_MSGLIST` | `mp_MsgList` | `struct List` | queued messages; must be initialised |
| $22 | `MP_SIZE` | `sizeof(struct MsgPort)` = 34 | | |

Signal mask for Wait: `1L << port->mp_SigBit`.

| Off | asm | C (`struct Message`) | Type | Meaning |
|---|---|---|---|---|
| $00 | -- | `mn_Node` | `struct Node` | `NT_MESSAGE` while queued, `NT_REPLYMSG` after reply |
| $0E | `MN_REPLYPORT` | `mn_ReplyPort` | `struct MsgPort *` | where ReplyMsg sends it |
| $12 | `MN_LENGTH` | `mn_Length` | `UWORD` | total length including this header |
| $14 | `MN_SIZE` | `sizeof(struct Message)` = 20 | | |

## Interrupt

| Off | asm | C (`struct Interrupt`) | Type | Meaning |
|---|---|---|---|---|
| $00 | -- | `is_Node` | `struct Node` | `NT_INTERRUPT`, `ln_Pri` = chain position, `ln_Name` = owner name |
| $0E | `IS_DATA` | `is_Data` | `APTR` | passed in A1 |
| $12 | `IS_CODE` | `is_Code` | code ptr | entry point |
| $16 | `IS_SIZE` | `sizeof(struct Interrupt)` = 22 | | |

Also used for low-memory handlers and software interrupts. See
[interrupts](../exec/interrupts.md#addintserver).

## IORequest and IOStdReq

| Off | asm | C | Type | Meaning |
|---|---|---|---|---|
| $00 | -- | `io_Message` | `struct Message` | `mn_ReplyPort` must be your port |
| $14 | `IO_DEVICE` | `io_Device` | `struct Device *` | set by OpenDevice |
| $18 | `IO_UNIT` | `io_Unit` | `struct Unit *` | set by OpenDevice (private) |
| $1C | `IO_COMMAND` | `io_Command` | `UWORD` | `CMD_` or device command |
| $1E | `IO_FLAGS` | `io_Flags` | `UBYTE` | `IOF_QUICK` $01 |
| $1F | `IO_ERROR` | `io_Error` | `BYTE` | 0 = OK |
| $20 | `IO_SIZE` | `sizeof(struct IORequest)` = 32 | | |
| $20 | `IO_ACTUAL` | `io_Actual` | `ULONG` | bytes actually transferred (IOStdReq) |
| $24 | `IO_LENGTH` | `io_Length` | `ULONG` | bytes requested |
| $28 | `IO_DATA` | `io_Data` | `APTR` | buffer |
| $2C | `IO_OFFSET` | `io_Offset` | `ULONG` | seek offset for block devices |
| $30 | `IOSTD_SIZE` | `sizeof(struct IOStdReq)` = 48 | | |

Standard commands: `CMD_INVALID` 0, `CMD_RESET` 1, `CMD_READ` 2, `CMD_WRITE` 3, `CMD_UPDATE` 4,
`CMD_CLEAR` 5, `CMD_STOP` 6, `CMD_START` 7, `CMD_FLUSH` 8, `CMD_NONSTD` 9 (first
device-specific). Device vectors: `DEV_BEGINIO` -30, `DEV_ABORTIO` -36. See [io](../exec/io.md#doio).

## MemChunk, MemHeader, MemList

| Off | asm | C | Type | Meaning |
|---|---|---|---|---|
| $00 | `MC_NEXT` | `mc_Next` | `struct MemChunk *` | next free chunk |
| $04 | `MC_BYTES` | `mc_Bytes` | `ULONG` | size of this free chunk |
| $08 | `MC_SIZE` | = 8 | | |

| Off | asm | C (`struct MemHeader`) | Type | Meaning |
|---|---|---|---|---|
| $00 | -- | `mh_Node` | `struct Node` | `NT_MEMORY`, pri, region name |
| $0E | `MH_ATTRIBUTES` | `mh_Attributes` | `UWORD` | `MEMF_` bits of the region |
| $10 | `MH_FIRST` | `mh_First` | `struct MemChunk *` | first free chunk |
| $14 | `MH_LOWER` | `mh_Lower` | `APTR` | lower bound |
| $18 | `MH_UPPER` | `mh_Upper` | `APTR` | upper bound + 1 |
| $1C | `MH_FREE` | `mh_Free` | `ULONG` | free bytes |
| $20 | `MH_SIZE` | = 32 | | |

`struct MemEntry` (8 bytes): `me_Reqs`/`me_Addr` union at $00 (`ME_REQS`/`ME_ADDR`),
`me_Length` at $04 (`ME_LENGTH`).
`struct MemList`: `ml_Node` at $00, `ml_NumEntries` `UWORD` at $0E (`ML_NUMENTRIES`), and the
`ml_ME[]` array at $10 (`ML_ME`). In asm `ML_SIZE` = $10 excludes the entries. In C,
`sizeof(struct MemList)` = 24 includes the first MemEntry.
Allocation granularity: `MEM_BLOCKSIZE` 8 (`MEM_BLOCKMASK` 7). The system memory regions hang
off `ExecBase->MemList` and are private. Use [AvailMem](../exec/memory.md#availmem) and
[TypeOfMem](../exec/memory.md#typeofmem) to query them.

## SignalSemaphore

| Off | asm | C | Type | Meaning |
|---|---|---|---|---|
| $00 | -- | `ss_Link` | `struct Node` | name/pri for public semaphores |
| $0E | `SS_NESTCOUNT` | `ss_NestCount` | `WORD` | owner's nest count |
| $10 | `SS_WAITQUEUE` | `ss_WaitQueue` | `struct MinList` | waiters |
| $1C | `SS_MULTIPLELINK` | `ss_MultipleLink` | `struct SemaphoreRequest` | private |
| $28 | `SS_OWNER` | `ss_Owner` | `struct Task *` | exclusive owner, or NULL |
| $2C | `SS_QUEUECOUNT` | `ss_QueueCount` | `WORD` | -1 when free |
| $2E | `SS_SIZE` | = 46 | | |

The -1-when-free value of `ss_QueueCount` is standard knowledge (unverified). Test with
[AttemptSemaphore](../exec/semaphores.md#attemptsemaphore) rather than peeking at it.

## ExecBase: fields worth reading

`struct ExecBase` starts with `struct Library LibNode`. In asm the fields are plain labels
(`ThisTask(a6)`), and the library part is reached through `LIB_VERSION(a6)` etc.
Everything else in ExecBase is private.

| Off | asm / C | Type | Meaning |
|---|---|---|---|
| $14 | `LIB_VERSION` / `LibNode.lib_Version` | `UWORD` | exec version (V33..V45) |
| $16 | `LIB_REVISION` / `LibNode.lib_Revision` | `UWORD` | exec revision |
| $22 | `SoftVer` | `UWORD` | Kickstart release number (obsolete) |
| $2A | `ColdCapture` | `APTR` | reset capture vectors ($2A/$2E/$32 Cool/Warm): don't touch |
| $3E | `MaxLocMem` | `ULONG` | top of chip memory |
| $4E | `MaxExtMem` | `APTR` | top of extended memory, or NULL if none |
| $114 | `ThisTask` | `struct Task *` | running task. Readable; FindTask(NULL) is the API |
| $126 | `IDNestCnt` | `BYTE` | Disable nesting (-1 = enabled) |
| $127 | `TDNestCnt` | `BYTE` | Forbid nesting (-1 = task switching allowed) |
| $128 | `AttnFlags` | `UWORD` | CPU/FPU flags, see below |
| $17A | `LibList` | `struct List` | libraries (Forbid to walk) |
| $15E | `DeviceList` | `struct List` | devices |
| $150 | `ResourceList` | `struct List` | resources |
| $188 | `PortList` | `struct List` | public message ports |
| $196 | `TaskReady` | `struct List` | ready tasks (Disable to walk) |
| $1A4 | `TaskWait` | `struct List` | waiting tasks (Disable to walk) |
| $202 | `LastAlert` | `LONG[4]` | last alert; [3] = V39 alert timeout |
| $212 | `VBlankFrequency` | `UBYTE` | 50 or 60 |
| $213 | `PowerSupplyFrequency` | `UBYTE` | 50 or 60 |
| $214 | `SemaphoreList` | `struct List` | public semaphores |
| $222 | `KickMemPtr` | `APTR` | KickTag memory list (see SumKickData) |
| $226 | `KickTagPtr` | `APTR` | KickTag ROMTag array |
| $22A | `KickCheckSum` | `APTR` | SumKickData result |
| $238 | `ex_EClockFrequency` | `ULONG` | E clock Hz, 715909 NTSC / 709379 PAL (V36) |
| $268 | `ex_MemHandlers` | `struct MinList` | low-memory handlers (V39, private) |
| $278 | `SYSBASESIZE` | = 632 | |

The -1 idle values of `IDNestCnt`/`TDNestCnt` match the DISABLE/ENABLE macros in exec/ables.i,
which increment and decrement them around zero.
For PAL/NTSC decisions the graphics library's display flags are the usual source.
`VBlankFrequency` is the rough vertical-blank rate exec uses.

AttnFlags bits (execbase.h/.i): `AFF_68010` $01 (also set for 020+), `AFF_68020` $02
(also 030+), `AFF_68030` $04 (also 040+), `AFF_68040` $08 (also 060, per execbase.h),
`AFF_68881` $10 (also 68882), `AFF_68882` $20, `AFF_FPU40` $40 (68040 FPU, only valid with
`AFF_68040`), `AFF_68060` $80 (C header only: in asm use bit 7), `AFF_PRIVATE` $8000.
`AFB_` names give the bit numbers.

```c
if (SysBase->AttnFlags & AFF_68010) {
    /* 68010 or better: MOVEC/VBR exist, MOVE SR,<ea> is privileged */
}
```

```asm
        move.l  4.w,a6
        move.w  AttnFlags(a6),d0
        btst    #AFB_68020,d0
        beq.s   .no020                  ; 68000 or 68010
        btst    #7,d0                   ; AFB_68060 (not defined in execbase.i)
        bne.s   .is060
```

## Common mistakes

- Treating a zeroed List or MsgPort list as empty. It must be NEWLIST-initialised.
- Iterating with `for (n = head; n; n = n->ln_Succ)`. That runs one step past the end onto the
  tail sentinel. Test `n->ln_Succ`.
- Using `mp_SigBit` as a mask. It's a bit number: `1L << mp_SigBit`.
- Walking `LibList`/`PortList`/`SemaphoreList` without Forbid, or `TaskReady`/`TaskWait`
  without Disable. Keep the protected section short, and never call anything that Waits
  (DOS, printf) inside it.
- Casting a DOS process "handle" (from dos.library) straight to `struct Process *`. DOS hands
  out `&pr_MsgPort`, and the Process starts `sizeof(struct Task)` ($5C) earlier.
- Assuming `sizeof(struct MemList)` in C equals `ML_SIZE` in asm.
- Using `tc_TrapAlloc`/`tc_TrapAble` or `tc_ETask`. The headers disagree, so treat offset $22
  as private.

**See also:** [lists](../exec/lists.md#addtail), [tasks](../exec/tasks.md#findtask),
[messages](../exec/signals-and-messages.md#getmsg), [memory rules](memory-rules.md),
[calling convention](calling-convention.md)
