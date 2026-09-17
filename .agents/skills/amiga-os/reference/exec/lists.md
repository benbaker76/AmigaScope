# exec.library: lists

Exec lists are doubly linked with two built-in sentinels: the header's `lh_Head`/`lh_Tail`
fields form a fake head node and `lh_Tail`/`lh_TailPred` a fake tail node, so no insert or
remove needs a NULL test. A `struct List` holds full `struct Node`s (type, priority, name --
needed by Enqueue and FindName); a `struct MinList` holds `struct MinNode`s (links only).
None of these calls arbitrate: lock your own shared lists, and Forbid (or Disable) around
system lists, see [memory rules](../topics/memory-rules.md). Field offsets:
[structures](../topics/structures.md).

**Initialise a header before first use**. amiga.lib's NewList isn't linked in Bartman
`-nostdlib` builds, but Bartman's `#include <inline/alib.h>` provides `NewList()` as an inline
macro. NewMinList needs V45. Or do it by hand:

```asm
        include "exec/lists.i"

        lea     mylist,a0
        NEWLIST a0                      ; must be an address register; a0 is preserved
        move.b  #NT_USER,LH_TYPE(a0)    ; optional list type
```

```c
struct List *l = &myList;
l->lh_Head     = (struct Node *)&l->lh_Tail;
l->lh_Tail     = NULL;
l->lh_TailPred = (struct Node *)&l->lh_Head;   /* == (struct Node *)l */
```

**Empty test**: `l->lh_TailPred == (struct Node *)l` (C macro `IsListEmpty(l)`, List only;
for a MinList compare `mlh_TailPred` with the header address). Asm: `TSTLIST a0` sets Z when
empty, or `IFEMPTY a0,.empty`.

**Walk a list, removing nodes as you go**: read the successor first; the loop ends when the
successor is NULL (the current "node" is then the tail sentinel).

```c
struct Node *n, *next;
for (n = l->lh_Head; (next = n->ln_Succ) != NULL; n = next)
{
    if (n->ln_Pri < 0)
    {
        Remove(n);                      /* safe: next was read first */
        FreeVec(n);
    }
}
```

```asm
        move.l  LH_HEAD(a2),a3          ; a2 = list header
.loop:  move.l  LN_SUCC(a3),d2          ; successor, read BEFORE using a3
        beq.s   .done                   ; a3 is the tail sentinel
        ; ... use a3, may Remove/free it ...
        move.l  d2,a3
        bra.s   .loop
.done:
```

## NewMinList
`VOID NewMinList(struct MinList *minlist)` — LVO -828 (-$33C)
Registers: minlist=A0; no result

Initialise a MinList header as an empty list.

- **minlist** — the `struct MinList` to prepare; its old contents are ignored.

Since V45.

Source: NDK 3.9 includes (no autodoc in the source set).

### Example
```c
#include <proto/exec.h>
#include <exec/lists.h>
#include <exec/execbase.h>

void InitMinList(struct MinList *ml)
{
    if (SysBase->LibNode.lib_Version >= 45)
        NewMinList(ml);
    else                                /* same result by hand, any exec */
    {
        ml->mlh_Head     = (struct MinNode *)&ml->mlh_Tail;
        ml->mlh_Tail     = NULL;
        ml->mlh_TailPred = (struct MinNode *)&ml->mlh_Head;
    }
}
```

### Gotchas
- Kickstart 3.1 ROMs carry exec V40: check `lib_Version` or just initialise the three
  pointers yourself (asm: `NEWLIST`), which works everywhere.

**See also:** [AddTail](#addtail), [RemHead](#remhead)

## AddHead
`VOID AddHead(struct List *list, struct Node *node)` — LVO -240 (-$F0)
Registers: list=A0, node=A1; no result

Insert a node at the front of a list.

- **list** — initialised list header.
- **node** — node to insert; must not currently be in any list.

### Gotchas
- No arbitration: the caller must own the list (Forbid for system lists).
- The `ADDHEAD` macro in exec/lists.i does the same inline but destroys A0 and D0.

**See also:** [AddTail](#addtail), [Enqueue](#enqueue), [Insert](#insert),
[RemHead](#remhead)

## AddTail
`VOID AddTail(struct List *list, struct Node *node)` — LVO -246 (-$F6)
Registers: list=A0, node=A1; no result

Append a node to the end of a list.

- **list** — initialised list header.
- **node** — node to append; must not currently be in any list.

### Example
```asm
        include "exec/lists.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        lea     eventq,a0               ; list
        move.l  a2,a1                   ; node to queue
        jsr     _LVOAddTail(a6)         ; FIFO: AddTail + RemHead
```

### Gotchas
- No arbitration: the caller must own the list.
- The `ADDTAIL` macro in exec/lists.i is the inline version; it destroys A0 and D0.

**See also:** [AddHead](#addhead), [RemHead](#remhead), [Enqueue](#enqueue)

## Insert
`VOID Insert(struct List *list, struct Node *node, struct Node *pred)` — LVO -234 (-$EA)
Registers: list=A0, node=A1, pred=A2; no result

Insert a node into a list directly after a given node.

- **list** — list header.
- **node** — node to insert.
- **pred** — node already in the list to insert after; 0 inserts at the head (AddHead is
  slightly faster for that).

### Gotchas
- `pred` must belong to `list`. No arbitration.

**See also:** [AddHead](#addhead), [AddTail](#addtail), [Enqueue](#enqueue),
[Remove](#remove)

## Enqueue
`VOID Enqueue(struct List *list, struct Node *node)` — LVO -270 (-$10E)
Registers: list=A0, node=A1; no result

Insert a node in priority order, behind any nodes of equal or higher priority.

- **list** — list header kept sorted by priority (highest `ln_Pri` at the head).
- **node** — full `struct Node` with `ln_Pri` set (-128..127).

### Example
```c
#include <proto/exec.h>
#include <exec/lists.h>

struct Job { struct Node node; ULONG id; };

void QueueJob(struct List *jobs, struct Job *j, BYTE pri)
{
    j->node.ln_Pri = pri;
    Enqueue(jobs, &j->node);            /* equal priorities stay FIFO */
}
```

### Gotchas
- Needs full Nodes; never Enqueue MinNodes (there is no `ln_Pri`).
- No arbitration.

**See also:** [AddHead](#addhead), [AddTail](#addtail), [Insert](#insert),
[RemHead](#remhead)

## Remove
`VOID Remove(struct Node *node)` — LVO -252 (-$FC)
Registers: node=A1; no result

Unlink a node from whatever list it is in.

- **node** — node currently in a list.

### Gotchas
- Never pass a node that is not in a list, or Remove the same node twice: the stale link
  pointers corrupt whatever list they point into.
- No arbitration; the `REMOVE` macro (exec/lists.i) is the inline form, destroying A0/A1.
- Read `ln_Succ` BEFORE removing when walking a list (see the loop at the top).

**See also:** [RemHead](#remhead), [RemTail](#remtail), [AddTail](#addtail)

## RemHead
`struct Node * RemHead(struct List *list)` — LVO -258 (-$102)
Registers: list=A0; result in D0

Unlink and return the first node of a list.

- **list** — list header.
- **Result** — the removed node, or 0 if the list was empty.

### Example
```asm
        include "lvo/exec_lib.i"

        move.l  4.w,a6
.drain: lea     eventq,a0
        jsr     _LVORemHead(a6)
        tst.l   d0
        beq.s   .empty                  ; queue drained
        move.l  d0,a2
        ; ... handle event node a2 ...
        bra.s   .drain
.empty:
```

### Gotchas
- No arbitration. The `REMHEAD` macro (exec/lists.i) is the inline form.

**See also:** [RemTail](#remtail), [AddTail](#addtail), [Remove](#remove)

## RemTail
`struct Node * RemTail(struct List *list)` — LVO -264 (-$108)
Registers: list=A0; result in D0

Unlink and return the last node of a list.

- **list** — list header.
- **Result** — the removed node, or 0 if the list was empty.

### Gotchas
- No arbitration. The `REMTAIL` macro (exec/lists.i) is the inline form.

**See also:** [RemHead](#remhead), [AddHead](#addhead), [Remove](#remove)

## FindName
`struct Node * FindName(struct List *list, CONST_STRPTR name)` — LVO -276 (-$114)
Registers: list=A0, name=A1; result in D0

Search a list for the next node whose name matches a string exactly.

- **list** — a list header to search from the first node, or a node to continue the search
  after (that node itself is skipped).
- **name** — NUL-terminated name.
- **Result** — matching node or 0; the Z flag is set from the result.

### Example
```c
#include <proto/exec.h>
#include <exec/lists.h>

ULONG CountNamed(struct List *l, CONST_STRPTR name)
{
    ULONG count = 0;
    struct Node *n = (struct Node *)l;

    while ((n = FindName((struct List *)n, name)) != NULL)
        count++;                        /* restart after each hit */
    return count;
}
```

### Gotchas
- The compare is case-sensitive.
- Needs full Nodes (MinNodes have no `ln_Name`).
- No arbitration: for system lists (`SysBase->LibList`, `DeviceList`, `PortList`...) hold a
  Forbid for the search AND for as long as you use the node.

**See also:** [Enqueue](#enqueue), [FindPort](signals-and-messages.md#findport),
[FindTask](tasks.md#findtask), [FindSemaphore](semaphores.md#findsemaphore)
