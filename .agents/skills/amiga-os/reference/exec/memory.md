# exec.library: memory

Exec owns every free byte in the machine. AllocMem/FreeMem are the base pair (you remember
the size); AllocVec/FreeVec (V36) remember it for you; pools (V39) carve many small blocks
out of big "puddles" and drop them all with one DeletePool. Allocate/Deallocate manage a
private MemHeader you own, AllocEntry/FreeEntry grab a whole MemList at once, and
AddMemHandler lets you give memory back when an allocation is about to fail.
Flag table, chip-RAM rules and lifetime rules: [memory rules](../topics/memory-rules.md).

## AllocMem
`APTR AllocMem(ULONG byteSize, ULONG requirements)` — LVO -198 (-$C6)
Registers: byteSize=D0, requirements=D1; result in D0

Allocate a block of memory that satisfies the given attribute flags.

- **byteSize** — bytes wanted; rounded up internally to a multiple of `MEM_BLOCKSIZE` (8).
- **requirements** — `MEMF_` flags ORed together.
  Requirements (the region must have them): `MEMF_CHIP` ($2, reachable by the custom chips),
  `MEMF_FAST` ($4, non-chip only), `MEMF_PUBLIC` ($1, never mapped or swapped away),
  `MEMF_LOCAL` ($100, survives a CPU RESET), `MEMF_24BITDMA` ($200, inside the Zorro-II
  24-bit DMA range), `MEMF_KICK` ($400, usable before KickTags run, V39).
  `MEMF_ANY` (0) takes the best memory available, fast RAM first.
  Options (applied to whatever block you get): `MEMF_CLEAR` ($10000, zero-filled),
  `MEMF_REVERSE` ($40000, V36, take it from the top of the region),
  `MEMF_NO_EXPUNGE` ($80000000, V39, do not flush libraries/handlers if it fails).
- **Result** — address of a longword-aligned block, or 0 when nothing fits.

### Example
```asm
        include "exec/memory.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6                  ; ExecBase
        move.l  #(320*256)/8,d0         ; one 320x256 bitplane
        move.l  #MEMF_CHIP!MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        move.l  d0,plane0               ; keep it (and its size) for FreeMem
        beq     .nomem                  ; 0 = no memory
```

### Gotchas
- Test EVERY result; any allocation can fail once memory is full or fragmented.
- Not callable from interrupts. Allocate what interrupt code needs beforehand.
- Anything the custom chips read (bitplanes, copper lists, sprites, audio, blitter data)
  needs `MEMF_CHIP`.
- `MEMF_FAST` fails outright on a chip-only machine and may not be combined with
  `MEMF_CHIP`; use `MEMF_ANY` when either kind will do.
- Only `MEMF_CLEAR` zeroes the block. `MEMF_REVERSE` is buggy before V39;
  `MEMF_NO_EXPUNGE` is ignored before V39; `MEMF_LOCAL`/`MEMF_24BITDMA` may not exist
  before V36 (the call then fails).
- A DOS process gets `pr_Result2` = `ERROR_NO_FREE_STORE` (103) when it fails.
- A corrupt free list raises `AN_MemCorrupt` (autodoc prints $01000005, alerts.h defines
  0x81000005).

**See also:** [FreeMem](#freemem), [AllocVec](#allocvec), [AvailMem](#availmem),
[CreatePool](#createpool), [TypeOfMem](#typeofmem)

## FreeMem
`VOID FreeMem(APTR memoryBlock, ULONG byteSize)` — LVO -210 (-$D2)
Registers: memoryBlock=A1, byteSize=D0; no result

Give a block obtained with AllocMem (or AllocAbs) back to the system.

- **memoryBlock** — the address AllocMem returned.
- **byteSize** — the same size you asked for; it is rounded the same way as on allocation.

### Example
```c
#include <proto/exec.h>
#include <exec/memory.h>

#define WORK_SIZE 4096

UBYTE *work = AllocMem(WORK_SIZE, MEMF_ANY);
if (work != NULL)
{
    /* ... use work ... */
    FreeMem(work, WORK_SIZE);
    work = NULL;                        /* never touch it again */
}
```

### Gotchas
- Freeing the same block twice raises `AN_FreeTwice` ($01000009); a bad pointer usually
  gives `AN_MemCorrupt` or `AN_BadFreeAddr` ($0100000F).
- The size MUST match. Freeing only part of a block is legal for exec but unwise.
- Never FreeMem an AllocVec or AllocPooled block.
- NULL is not documented as safe here (unlike FreeVec): test the pointer first.
- Same interrupt restriction as AllocMem (unverified).

**See also:** [AllocMem](#allocmem), [FreeVec](#freevec), [AllocAbs](#allocabs)

## AllocVec
`APTR AllocVec(ULONG byteSize, ULONG requirements)` — LVO -684 (-$2AC)
Registers: byteSize=D0, requirements=D1; result in D0

Allocate memory like AllocMem, but let exec remember the size for FreeVec.

- **byteSize** — bytes wanted.
- **requirements** — the same `MEMF_` flags as [AllocMem](#allocmem).
- **Result** — block address, or 0 on failure.

Since V36.

### Example
```c
#include <proto/exec.h>
#include <exec/memory.h>

UWORD *copper = AllocVec(256 * sizeof(UWORD), MEMF_CHIP | MEMF_CLEAR);
if (copper == NULL)
    return FALSE;
/* ... build and use the copper list ... */
FreeVec(copper);                        /* no size needed */
```

### Gotchas
- Release ONLY with FreeVec; FreeMem on an AllocVec block corrupts the free list.
- The size is kept in hidden bytes in front of the block: never read or rely on them.
- Not in Kickstart 1.x (V33/V34): use AllocMem and store the size yourself there.
- Not callable from interrupts, like AllocMem.

**See also:** [FreeVec](#freevec), [AllocMem](#allocmem)

## FreeVec
`VOID FreeVec(APTR memoryBlock)` — LVO -690 (-$2B2)
Registers: memoryBlock=A1; no result

Release a block obtained with AllocVec.

- **memoryBlock** — the AllocVec result, or NULL (then nothing happens).

Since V36.

### Gotchas
- Only for AllocVec memory. Double frees raise `AN_FreeTwice` ($01000009).
- The NULL shortcut makes cleanup code simple: `FreeVec(p); p = NULL;` in any order.

**See also:** [AllocVec](#allocvec), [FreeMem](#freemem)

## AvailMem
`ULONG AvailMem(ULONG requirements)` — LVO -216 (-$D8)
Registers: requirements=D1; result in D0

Return how much free memory of a given kind exists, or the largest free block.

- **requirements** — `MEMF_` attribute flags as for AllocMem (`MEMF_CHIP`, `MEMF_FAST`,
  `MEMF_ANY`, ...). Add `MEMF_LARGEST` ($20000) to get the biggest single free block, or
  `MEMF_TOTAL` ($80000) for the total size of matching memory (V39+, unverified).
- **Result** — free bytes (or largest block / total) in D0.

### Example
```asm
        include "exec/memory.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        move.l  #MEMF_CHIP!MEMF_LARGEST,d1      ; argument goes in D1, not D0
        jsr     _LVOAvailMem(a6)
        cmp.l   #CHIP_NEEDED,d0
        blo     .notenough              ; fragmentation: one block won't fit
```

### Gotchas
- A snapshot only: other tasks may allocate before you do. Just call AllocMem and test.
- The argument is in D1.
- `MEMF_LARGEST` walks the free lists and is slow; from V36 it also checks list
  consistency and alerts with `AN_MemoryInsane` ($0100000C) on a mismatch.

**See also:** [AllocMem](#allocmem), [TypeOfMem](#typeofmem)

## TypeOfMem
`ULONG TypeOfMem(CONST APTR address)` — LVO -534 (-$216)
Registers: address=A1; result in D0

Return the memory attribute flags of the RAM region containing an address.

- **address** — any address.
- **Result** — the region's `MEMF_` attributes (e.g. `MEMF_CHIP`, `MEMF_FAST`,
  `MEMF_PUBLIC`), or 0 when the address is not in a known RAM region (ROM, custom chips,
  I/O, or the MemHeader at the very start of a region).

### Example
```asm
        include "exec/memory.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        move.l  sample_ptr,a1
        jsr     _LVOTypeOfMem(a6)
        btst    #MEMB_CHIP,d0           ; can Paula DMA reach it?
        beq     .copy_to_chip           ; no: copy it into MEMF_CHIP memory first
```

### Gotchas
- Typical use: verify a buffer (loaded file, static data from a non-chip hunk) is chip RAM
  before handing it to the custom chips.
- 0 does not mean "free", it means "not RAM exec knows about".

**See also:** [AllocMem](#allocmem), [AvailMem](#availmem)

## CopyMem
`VOID CopyMem(CONST APTR source, APTR dest, ULONG size)` — LVO -624 (-$270)
Registers: source=A0, dest=A1, size=D0; no result

Copy bytes between two memory areas with any alignment.

- **source** — start of the data to copy (A0).
- **dest** — destination (A1).
- **size** — number of bytes; 0 copies nothing.

### Example
```asm
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        lea     level_template,a0       ; source
        move.l  level_buf,a1            ; destination
        move.l  #LEVEL_SIZE,d0
        jsr     _LVOCopyMem(a6)
```

### Gotchas
- Argument order is source, dest -- the reverse of C `memcpy(dest, src, n)`.
- Overlapping areas are not supported; write your own backwards copy for that case.
- The implementation varies between ROMs (it may even use DMA); don't depend on how it
  copies, only that it does.

**See also:** [CopyMemQuick](#copymemquick)

## CopyMemQuick
`VOID CopyMemQuick(CONST APTR source, APTR dest, ULONG size)` — LVO -630 (-$276)
Registers: source=A0, dest=A1, size=D0; no result

Copy longword-aligned data whose size is a multiple of four bytes, as fast as possible.

- **source** — longword-aligned source address.
- **dest** — longword-aligned destination address.
- **size** — byte count, evenly divisible by 4; 0 copies nothing.

### Gotchas
- Violating the alignment or size rule is undefined; use CopyMem when unsure.
  (AllocMem/AllocVec/AllocPooled results are always longword-aligned.)
- Overlapping copies are not supported.

**See also:** [CopyMem](#copymem)

## CreatePool
`APTR CreatePool(ULONG requirements, ULONG puddleSize, ULONG threshSize)` — LVO -696 (-$2B8)
Registers: requirements=D0, puddleSize=D1, threshSize=D2; result in D0

Create a private memory pool that hands out small blocks from large shared puddles.

- **requirements** — `MEMF_` flags used for every puddle (e.g. `MEMF_ANY`, `MEMF_CHIP`).
  `MEMF_CLEAR` also makes AllocPooled return zeroed blocks (unverified).
- **puddleSize** — size of each puddle allocated from the system.
- **threshSize** — requests larger than this get a puddle of their own; must be
  <= puddleSize or CreatePool fails.
- **Result** — opaque pool handle, or NULL on failure (returned in D0).

Since V39.

### Example
```c
#include <proto/exec.h>
#include <exec/memory.h>

struct Particle { WORD x, y, dx, dy; };

APTR pool = CreatePool(MEMF_ANY, 8192, 1024);
if (pool != NULL)
{
    struct Particle *p = AllocPooled(pool, sizeof(struct Particle));
    if (p != NULL)
    {
        /* ... */
        FreePooled(pool, p, sizeof(struct Particle));   /* optional */
    }
    DeletePool(pool);                   /* frees everything still allocated */
}
```

### Gotchas
- V39+ only. For older systems amiga.lib has LibCreatePool/LibAllocPooled/LibFreePooled/
  LibDeletePool (V33+, calls exec on V39) -- but Bartman's `-nostdlib` builds don't link
  amiga.lib.
- A pool has no locking. If several tasks share it, protect it with a SignalSemaphore;
  Forbid is explicitly not a valid protection.

**See also:** [DeletePool](#deletepool), [AllocPooled](#allocpooled),
[FreePooled](#freepooled)

## DeletePool
`VOID DeletePool(APTR poolHeader)` — LVO -702 (-$2BE)
Registers: poolHeader=A0; no result

Free every puddle of a pool, and with it all its allocations, then the pool itself.

- **poolHeader** — handle from CreatePool.

Since V39.

### Gotchas
- Every pointer obtained from the pool is dead afterwards; no FreePooled calls are needed
  first.

**See also:** [CreatePool](#createpool), [AllocPooled](#allocpooled),
[FreePooled](#freepooled)

## AllocPooled
`APTR AllocPooled(APTR poolHeader, ULONG memSize)` — LVO -708 (-$2C4)
Registers: poolHeader=A0, memSize=D0; result in D0

Allocate a block from a pool created with CreatePool.

- **poolHeader** — handle from CreatePool.
- **memSize** — bytes wanted.
- **Result** — longword-aligned block, or NULL.

Since V39.

### Example
```asm
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        move.l  pool,a0                 ; poolHeader
        moveq   #24,d0                  ; memSize
        jsr     _LVOAllocPooled(a6)
        tst.l   d0
        beq     .nomem
        move.l  d0,a2                   ; new node
```

### Gotchas
- The pool does not record block sizes: remember them for FreePooled. To get AllocVec
  style tracking, allocate 4 extra bytes, store the size in the first longword and return
  the address after it.
- No arbitration: guard a shared pool with a semaphore. AllocPooled may break a Forbid.

**See also:** [FreePooled](#freepooled), [CreatePool](#createpool),
[DeletePool](#deletepool)

## FreePooled
`VOID FreePooled(APTR poolHeader, APTR memory, ULONG memSize)` — LVO -714 (-$2CA)
Registers: poolHeader=A0, memory=A1, memSize=D0; no result

Return one AllocPooled block to its pool.

- **poolHeader** — the pool the block came from.
- **memory** — the AllocPooled result.
- **memSize** — EXACTLY the size passed to AllocPooled.

Since V39.

### Gotchas
- Only AllocPooled memory from that same pool. Wrong size or pool corrupts the pool.
- Optional: DeletePool frees everything at once.
- Same semaphore rule as AllocPooled; it may break a Forbid.

**See also:** [AllocPooled](#allocpooled), [DeletePool](#deletepool)

## AllocAbs
`APTR AllocAbs(ULONG byteSize, APTR location)` — LVO -204 (-$CC)
Registers: byteSize=D0, location=A1; result in D0

Allocate memory at a specific absolute address, if that range is still free.

- **byteSize** — bytes wanted; rounded up to the block size.
- **location** — address the block must cover.
- **Result** — pointer to a block that contains the whole requested range (it may start
  slightly lower because of rounding), or NULL if any part is in use or not RAM.

### Gotchas
- Exec relinks its free list while carving the block out, so the first 8 bytes of the
  range may be overwritten: data preloaded there cannot be trusted.
- Use it to claim a fixed range (reset-proof RAM disks, code/data assembled with `org`)
  BEFORE writing to it; NULL means someone owns that memory.
- Free it with FreeMem. A corrupt free list raises `AN_MemCorrupt`.

**See also:** [AllocMem](#allocmem), [FreeMem](#freemem)

## AllocEntry
`struct MemList * AllocEntry(struct MemList *entry)` — LVO -222 (-$DE)
Registers: entry=A0; result in D0

Allocate every region described by a MemList in one call.

- **entry** — a `struct MemList` whose `ml_NumEntries` entries each hold the `MEMF_`
  requirements in `me_Reqs` and the size in `me_Length`.
- **Result** — a NEW MemList (allocated by exec) with `me_Addr`/`me_Length` filled in.
  On failure bit 31 of D0 is set and the other bits are the requirements of the entry
  that could not be satisfied.

### Example
```asm
        include "exec/memory.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        lea     wanted,a0
        jsr     _LVOAllocEntry(a6)
        btst    #31,d0                  ; NOT a normal 0 = failure test
        bne     .nomem
        move.l  d0,a2                   ; allocated MemList
        move.l  ML_ME+ME_ADDR(a2),planes        ; entry 0
        move.l  ML_ME+ME_SIZE+ME_ADDR(a2),work  ; entry 1
        ; ... later: move.l a2,a0 / jsr _LVOFreeEntry(a6)

wanted:
        ds.b    LN_SIZE                 ; list node, unused here
        dc.w    2                       ; ML_NUMENTRIES
        dc.l    MEMF_CHIP!MEMF_CLEAR,40*256*3   ; ME_REQS, ME_LENGTH
        dc.l    MEMF_ANY,8192
```

### Gotchas
- The result is never 0 on failure: test bit 31.
- In C, `sizeof(struct MemList)` already includes the first MemEntry; asm `ML_SIZE`
  does not include any.
- Before V1.3 SetPatch a failure could leave the earlier entries allocated.
- AddHead the result onto your task's `tc_MemEntry` list to have RemTask free it.

**See also:** [FreeEntry](#freeentry), [AllocMem](#allocmem), [RemTask](tasks.md#remtask)

## FreeEntry
`VOID FreeEntry(struct MemList *entry)` — LVO -228 (-$E4)
Registers: entry=A0; no result

Free all regions of a MemList returned by AllocEntry.

- **entry** — the MemList AllocEntry returned (not your request template).

**See also:** [AllocEntry](#allocentry)

## Allocate
`APTR Allocate(struct MemHeader *freeList, ULONG byteSize)` — LVO -186 (-$BA)
Registers: freeList=A0, byteSize=D0; result in D0

Allocate a block from a private MemHeader free list that you manage yourself.

- **freeList** — your `struct MemHeader`, set up with `mh_Node.ln_Type = NT_MEMORY`,
  `mh_First` -> first `struct MemChunk` (`mc_Next`, `mc_Bytes`), `mh_Lower`, `mh_Upper`
  (end + 1) and `mh_Free`.
- **byteSize** — bytes wanted; rounded up to a multiple of `MEM_BLOCKSIZE` (8).
- **Result** — the first free chunk that fits, or 0.

### Example
```c
#include <proto/exec.h>
#include <exec/memory.h>
#include <exec/nodes.h>

#define ARENA_SIZE 16384                /* multiple of MEM_BLOCKSIZE */

static struct MemHeader arena;

BOOL ArenaInit(void)
{
    struct MemChunk *mc = AllocMem(ARENA_SIZE, MEMF_ANY);
    if (mc == NULL)
        return FALSE;
    mc->mc_Next  = NULL;
    mc->mc_Bytes = ARENA_SIZE;
    arena.mh_Node.ln_Type = NT_MEMORY;
    arena.mh_First = mc;
    arena.mh_Lower = mc;
    arena.mh_Upper = (APTR)((UBYTE *)mc + ARENA_SIZE);
    arena.mh_Free  = ARENA_SIZE;
    return TRUE;
}
/* p = Allocate(&arena, 100); ... Deallocate(&arena, p, 100); */
/* at exit: FreeMem(arena.mh_Lower, ARENA_SIZE); */
```

### Gotchas
- No arbitration at all: only the owner may call it, or wrap it in a semaphore.
- The region handed to the header must itself come from somewhere (AllocMem, static BSS).
- A corrupt chunk list raises `AN_MemCorrupt`.

**See also:** [Deallocate](#deallocate), [AllocMem](#allocmem)

## Deallocate
`VOID Deallocate(struct MemHeader *freeList, APTR memoryBlock, ULONG byteSize)` — LVO -192 (-$C0)
Registers: freeList=A0, memoryBlock=A1, byteSize=D0; no result

Return a block (or part of one) to a private MemHeader free list.

- **freeList** — the MemHeader the block belongs to.
- **memoryBlock** — start address; rounded down to a `MEM_BLOCKSIZE` boundary.
- **byteSize** — bytes to free, rounded up to the block size; 0 does nothing.

### Gotchas
- Freeing a sub-range of a bigger block is allowed if it lines up on 8-byte boundaries;
  the rounding can surprise you otherwise.
- It can add a brand-new region to the header, but `mh_Lower`/`mh_Upper` are then no
  longer accurate.
- No arbitration.

**See also:** [Allocate](#allocate)

## AddMemList
`VOID AddMemList(ULONG size, ULONG attributes, LONG pri, APTR base, CONST_STRPTR name)` — LVO -618 (-$26A)
Registers: size=D0, attributes=D1, pri=D2, base=A0, name=A1; no result

Add a new region of RAM to the system free memory pool.

- **size** — bytes in the region.
- **attributes** — its `MEMF_` flags (e.g. `MEMF_FAST!MEMF_PUBLIC`).
- **pri** — search priority; higher is searched first. Chip RAM is -10, 16-bit expansion
  RAM is 0.
- **base** — first address of the region; a MemHeader is written at its start.
- **name** — region name, or NULL. Not copied: it must stay valid forever.

### Gotchas
- Never pass `MEMF_KICK`; exec sets it itself when the region qualifies.
- There is no call to remove the region again.
- The start of the region is consumed by the MemHeader (TypeOfMem returns 0 there).

**See also:** [AllocMem](#allocmem), [TypeOfMem](#typeofmem)

## AddMemHandler
`VOID AddMemHandler(struct Interrupt *memhand)` — LVO -774 (-$306)
Registers: memhand=A1; no result

Install a low-memory handler that exec calls when an allocation is about to fail.

- **memhand** — a fully initialised `struct Interrupt`:
  `is_Node.ln_Pri` (order: positive runs before library expunges, negative after; RAMLIB
  is a handler at 0), `is_Node.ln_Name` (always fill it), `is_Data`, `is_Code`.

Handler entry: A0 = `struct MemHandlerData *` (read-only: `memh_RequestSize`,
`memh_RequestFlags`, `memh_Flags` with `MEMHF_RECYCLE` = 0 on the first call for this
failure, 1 on a repeat), A1 = `is_Data`, A6 = ExecBase. Return in D0:
`MEM_DID_NOTHING` (0), `MEM_TRY_AGAIN` (1, freed some -- retry the allocation) or
`MEM_ALL_DONE` (-1, freed all you can).

Since V39.

### Example
```asm
        include "exec/memory.i"
        include "exec/interrupts.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        lea     lowmem_int,a1
        jsr     _LVOAddMemHandler(a6)   ; may run before this returns
        ; ... at exit: lea lowmem_int,a1 / jsr _LVORemMemHandler(a6)

lowmem_code:                            ; a0=MemHandlerData a1=is_Data a6=ExecBase
        moveq   #MEM_DID_NOTHING,d0
        move.l  cache_ptr,d1
        beq.s   .done                   ; nothing cached
        clr.l   cache_ptr
        move.l  d1,a1
        move.l  #CACHE_SIZE,d0
        jsr     _LVOFreeMem(a6)
        moveq   #MEM_TRY_AGAIN,d0       ; freed something: retry
.done:  rts

        section data,data
lowmem_int:
        dc.l    0,0                     ; LN_SUCC, LN_PRED
        dc.b    NT_INTERRUPT,10         ; LN_TYPE, LN_PRI (before expunges)
        dc.l    lowmem_name             ; LN_NAME
        dc.l    0                       ; IS_DATA
        dc.l    lowmem_code             ; IS_CODE
lowmem_name:
        dc.b    "mygame cache",0
```

### Gotchas
- The handler runs inside the failing allocation under Forbid: never Wait, call DOS or do
  anything that breaks the Forbid.
- It can be called before AddMemHandler returns: set up everything first.
- Adding a handler from inside a handler is undefined.
- Preserve D2-D7/A2-A6 as in any callback (unverified).
- Allocations made with `MEMF_NO_EXPUNGE` do not call handlers.

**See also:** [RemMemHandler](#remmemhandler), [AllocMem](#allocmem)

## RemMemHandler
`VOID RemMemHandler(struct Interrupt *memhand)` — LVO -780 (-$30C)
Registers: memhand=A1; no result

Remove a low-memory handler installed with AddMemHandler.

- **memhand** — the same `struct Interrupt` passed to AddMemHandler.

Since V39.

### Gotchas
- The handler may still be entered until this call returns: keep its code and data valid
  until then.
- It may be called from inside the handler itself; a handler removing itself must return
  `MEM_ALL_DONE`.

**See also:** [AddMemHandler](#addmemhandler)
