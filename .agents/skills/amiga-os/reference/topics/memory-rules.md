# Memory rules

Exec has no memory protection and no resource tracking: whatever a program allocates stays
allocated until it frees it (or the machine reboots), a stray write lands in someone else's
data, and the custom chips can only see part of the RAM. These rules keep programs -- from
OS-friendly tools to take-over demos -- from crashing on the next machine they run on.
Function details: [memory.md](../exec/memory.md).

## Chip RAM vs fast RAM

Agnus/Alice DMA can only reach **chip RAM**. Everything the custom chips read or write
directly must live there:

- bitplanes and anything shown on screen,
- copper lists,
- sprite data,
- audio sample data played by Paula,
- blitter sources, destinations and masks,
- trackdisk.device buffers before V36.

CPU-only data (game logic, tables, packed data, code) should go in **fast RAM** when
there is some: it is faster on accelerated machines and leaves the scarce chip RAM free.

- Dynamic: `AllocMem(size, MEMF_CHIP)` / `AllocVec(size, MEMF_CHIP)`; CPU-only data
  `MEMF_ANY` (fast first, falls back to chip).
- Static data in the executable: put it in a chip hunk. vasm: `section name,data_c` or
  `bss_c`; Bartman's gcc/elf2hunk flow: an ELF section whose name contains `.MEMF_CHIP`,
  e.g. `EMBED_CHIP` / `INCBIN_CHIP` from `support/gcc8_c_support.h`. See the m68k-asm skill.
- Unsure where a buffer ended up (loaded file, pointer from elsewhere)? Test it:
  `TypeOfMem(ptr) & MEMF_CHIP` ([TypeOfMem](../exec/memory.md#typeofmem)).
- Trapdoor "slow" RAM at $C00000 on an A500 is not chip RAM: code that only ever ran on a
  chip-only machine will break there, and on any machine with fast RAM.

## MEMF_ flags

From `exec/memory.h` / `exec/memory.i` (asm also gets `MEMB_` bit numbers via BITDEF).

| Flag | Bit | Value | Use |
|---|---|---|---|
| `MEMF_ANY` | -- | $0 | any memory, fast preferred |
| `MEMF_PUBLIC` | 0 | $1 | never mapped/swapped away: shared with other tasks or interrupts |
| `MEMF_CHIP` | 1 | $2 | reachable by custom-chip DMA |
| `MEMF_FAST` | 2 | $4 | non-chip only; FAILS on chip-only machines |
| `MEMF_LOCAL` | 8 | $100 | survives CPU RESET (set automatically from V36) |
| `MEMF_24BITDMA` | 9 | $200 | inside Zorro-II 24-bit DMA range (V36) |
| `MEMF_KICK` | 10 | $400 | usable for KickTags (V39); never pass to AddMemList |
| `MEMF_CLEAR` | 16 | $10000 | AllocMem option: zero the block |
| `MEMF_LARGEST` | 17 | $20000 | AvailMem: size of the largest free block |
| `MEMF_REVERSE` | 18 | $40000 | AllocMem option: take from the top (V36, buggy before V39) |
| `MEMF_TOTAL` | 19 | $80000 | AvailMem: total size of matching memory |
| `MEMF_NO_EXPUNGE` | 31 | $80000000 | AllocMem option: no expunge/low-memory handlers (V39) |

Sizes are rounded up to `MEM_BLOCKSIZE` (8); every block is longword-aligned.

## Pick one allocator per block and free it with its partner

| Allocate with | Free with | Size tracking | Available |
|---|---|---|---|
| [AllocMem](../exec/memory.md#allocmem) | [FreeMem](../exec/memory.md#freemem) | you pass the same size | all |
| [AllocVec](../exec/memory.md#allocvec) | [FreeVec](../exec/memory.md#freevec) (NULL ok) | exec | V36 |
| [AllocPooled](../exec/memory.md#allocpooled) | [FreePooled](../exec/memory.md#freepooled) or [DeletePool](../exec/memory.md#deletepool) | you pass the same size | V39 |
| [AllocEntry](../exec/memory.md#allocentry) | [FreeEntry](../exec/memory.md#freeentry) | in the MemList | all |
| [Allocate](../exec/memory.md#allocate) | [Deallocate](../exec/memory.md#deallocate) | you; private MemHeader | all |
| [AllocAbs](../exec/memory.md#allocabs) | [FreeMem](../exec/memory.md#freemem) | you | all |

- Never mix partners: FreeMem on an AllocVec block, or FreeVec on an AllocMem block,
  corrupts the free list and ends in an alert.
- Pools suit many small, similar allocations (particles, list nodes): one DeletePool frees
  everything. They have no locking -- guard a pool shared between tasks with a
  SignalSemaphore (Forbid is explicitly not enough). Pre-V39 replacements are the amiga.lib
  LibCreatePool family, which Bartman's `-nostdlib` builds do not link.

## Check every result; clear only when asked

- Every allocation may return 0, even a tiny one. Test before the first write.
- Memory is NOT zeroed unless you pass `MEMF_CLEAR`.
- AvailMem is only a snapshot; don't use it instead of testing the allocation.
  `MEMF_LARGEST` shows fragmentation: a big chip block can fail even with plenty of chip
  RAM free.

## Lifetime: free exactly once, in reverse order, after the hardware lets go

- Free everything you allocated before exiting; nobody else will.
- Free in reverse order of allocation, and set each pointer to NULL so a shared cleanup
  routine can run from any failure point.
- Never touch a block after freeing it: another task may own it the next instant.
- Stop the hardware first: restore the system copper list before freeing yours, stop audio
  DMA before freeing the sample, turn the display off before freeing its bitplanes.
- Double frees raise `AN_FreeTwice` ($01000009); a corrupted list raises `AN_MemCorrupt`
  (0x81000005 in alerts.h).
- A task's `tc_MemEntry` list (MemLists from AllocEntry) is freed by RemTask; nothing else is
  freed automatically.

## Interrupts and memory shared with other code

- AllocMem may not be called from interrupt code; treat FreeMem, AllocVec/FreeVec,
  AllocEntry and the pool calls the same (unverified for the free calls). Allocate all
  buffers an interrupt server needs before installing it, free them after removing it.
- Memory (data AND code) used by interrupts or by other tasks must be `MEMF_PUBLIC` or
  otherwise guaranteed never to be paged out.

## Walking system lists: Forbid and Disable

ExecBase's list headers (`LibList`, `DeviceList`, `ResourceList`, `PortList`,
`SemaphoreList`, `MemList`, `TaskReady`, `TaskWait`, `IntrList`) are private and change at any
moment. Prefer the lookup calls ([FindName](../exec/lists.md#findname),
[FindPort](../exec/signals-and-messages.md#findport),
[FindTask](../exec/tasks.md#findtask),
[FindSemaphore](../exec/semaphores.md#findsemaphore)) and follow these rules:

- Lists changed only by tasks (libraries, devices, resources, ports, semaphores): hold
  [Forbid](../exec/tasks.md#forbid) for the whole search AND for as long as you use what you
  found. FindPort and FindSemaphore require it; a FindTask result can also vanish.
- Lists changed from interrupts (the task ready/wait queues): only
  [Disable](../exec/tasks.md#disable) protects them (FindTask by name disables interrupts
  internally), and Disable must stay very short.
- The memory list: Forbid (unverified).
- Anything that waits (DOS calls, device I/O, printf, WaitPort) BREAKS a Forbid or Disable.
  Copy the data you need into your own variables, Permit, then print or act on the copy.
- Every Forbid needs exactly one Permit (they nest); same for Disable/Enable.

```c
#include <proto/exec.h>
#include <exec/execbase.h>

/* Read a library's version without opening it: copy under Forbid. */
UWORD PeekLibVersion(CONST_STRPTR name)
{
    struct Library *lib;
    UWORD ver = 0;

    Forbid();
    lib = (struct Library *)FindName(&SysBase->LibList, name);
    if (lib != NULL)
        ver = lib->lib_Version;         /* copy while the node is guaranteed alive */
    Permit();
    return ver;                         /* lib itself may be gone now */
}
```

```asm
        include "exec/execbase.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        moveq   #0,d2                   ; version, 0 = not loaded
        jsr     _LVOForbid(a6)          ; Forbid/Permit preserve all registers
        lea     LibList(a6),a0
        lea     gfxname(pc),a1
        jsr     _LVOFindName(a6)        ; D0 = node, Z set if none
        beq.s   .none
        move.l  d0,a0
        move.w  LIB_VERSION(a0),d2      ; copy it while forbidden
.none:  jsr     _LVOPermit(a6)
        rts

gfxname:
        dc.b    "graphics.library",0
        even
```

## Low-memory handlers

From V39 a program holding caches can register a handler with
[AddMemHandler](../exec/memory.md#addmemhandler); exec calls it (under Forbid) when an
allocation is about to fail, before (positive priority) or after (negative) libraries are
expunged. The handler frees what it can and returns `MEM_DID_NOTHING`, `MEM_TRY_AGAIN` or
`MEM_ALL_DONE`. Remove it with [RemMemHandler](../exec/memory.md#remmemhandler) before the
cache and the code go away. `MEMF_NO_EXPUNGE` allocations skip this machinery.

## Worked example: allocate and release a display's memory

C (AllocVec: V36+; use AllocMem and keep sizes for Kickstart 1.3):

```c
#include <proto/exec.h>
#include <exec/memory.h>

#define NPLANES      5
#define PLANE_SIZE   ((320 / 8) * 256)
#define COPPER_WORDS 512
#define WORK_SIZE    65536

static UBYTE *planes[NPLANES];
static UWORD *copper;
static APTR   work;

static void FreeDisplayMem(void)        /* safe from any failure point */
{
    int i;
    FreeVec(work);    work   = NULL;    /* reverse order; FreeVec(NULL) is fine */
    FreeVec(copper);  copper = NULL;
    for (i = NPLANES - 1; i >= 0; i--)
    {
        FreeVec(planes[i]);
        planes[i] = NULL;
    }
}

static BOOL AllocDisplayMem(void)
{
    int i;
    for (i = 0; i < NPLANES; i++)
        if ((planes[i] = AllocVec(PLANE_SIZE, MEMF_CHIP | MEMF_CLEAR)) == NULL)
            goto fail;
    if ((copper = AllocVec(COPPER_WORDS * sizeof(UWORD), MEMF_CHIP)) == NULL)
        goto fail;
    if ((work = AllocVec(WORK_SIZE, MEMF_ANY)) == NULL)    /* CPU only: fast if any */
        goto fail;
    return TRUE;
fail:
    FreeDisplayMem();
    return FALSE;
}
```

asm (AllocMem, works on every Kickstart):

```asm
        include "exec/memory.i"
        include "lvo/exec_lib.i"

NPLANES         equ     5
PLANES_SIZE     equ     (320/8)*256*NPLANES
WORK_SIZE       equ     65536

alloc_mem:                              ; out: d0 = 0 on failure
        move.l  4.w,a6
        move.l  #PLANES_SIZE,d0
        move.l  #MEMF_CHIP!MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        move.l  d0,planes
        beq.s   .fail
        move.l  #WORK_SIZE,d0
        moveq   #MEMF_ANY,d1
        jsr     _LVOAllocMem(a6)
        move.l  d0,work
        beq.s   .fail
        moveq   #1,d0
        rts
.fail:  bsr.s   free_mem
        moveq   #0,d0
        rts

free_mem:                               ; frees whatever was allocated
        move.l  4.w,a6
        move.l  work,d0
        beq.s   .nowork
        move.l  d0,a1
        move.l  #WORK_SIZE,d0           ; same size as allocated
        jsr     _LVOFreeMem(a6)
        clr.l   work
.nowork:
        move.l  planes,d0
        beq.s   .noplanes
        move.l  d0,a1
        move.l  #PLANES_SIZE,d0
        jsr     _LVOFreeMem(a6)
        clr.l   planes
.noplanes:
        rts

        section vars,bss
planes: ds.l    1
work:   ds.l    1
```

## Common mistakes

- Graphics, copper lists or samples in fast RAM: works on an unexpanded A500, shows garbage
  or silence on any machine with fast RAM. Use `MEMF_CHIP` or a `_c` hunk.
- Using `MEMF_FAST` to mean "don't care": it fails on chip-only machines. Use `MEMF_ANY`.
- Not testing for 0, or assuming AllocMem memory is zeroed.
- FreeMem with a different size than allocated; mixing AllocVec/FreeMem or AllocMem/FreeVec;
  FreePooled with the wrong size.
- Freeing a copper list, bitplane or sample while the hardware still uses it.
- Using a pointer after FreeMem, or freeing it twice.
- Calling AllocMem/FreeMem from an interrupt server.
- Walking `SysBase->LibList` (or using a FindPort/FindTask result) without Forbid, or doing
  DOS output inside the Forbid, which silently breaks it.
- CopyMem(dest, src, n): the exec order is source first.
- Sharing a pool between tasks without a semaphore.
- Trusting AvailMem instead of the allocation result.
