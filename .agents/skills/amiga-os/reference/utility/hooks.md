# utility.library: hooks

A Hook is the OS's standard callback record: a code pointer plus private data, entered with
fixed registers. BOOPSI class dispatchers (`cl_Dispatcher`), layer and screen backfill hooks
(`WA_BackFill`, `SA_BackFill`, [InstallLayerHook](../layers/clipping.md#installlayerhook)),
string-gadget edit hooks (`StringExtend.EditHook`), ReAction gadget and realtime.library
callbacks are all Hooks. You fill in the
structure; the OS (or [CallHookPkt](#callhookpkt)) jumps to `h_Entry`.

`struct Hook` (utility/hooks.h, asm utility/hooks.i; offsets checked with gcc and vasm):

| Offset | asm | C | Meaning |
|---|---|---|---|
| $00 | (MLN_SIZE = 8) | `h_MinNode` | MinNode, so hooks can be kept in lists |
| $08 | `h_Entry` | `h_Entry` | code the caller jumps to (register convention below) |
| $0C | `h_SubEntry` | `h_SubEntry` | free for the entry code: usually the real C function |
| $10 | `h_Data` | `h_Data` | owner-specific data pointer |
| $14 | `h_SIZEOF` | `sizeof(struct Hook)` = 20 | |

`typedef unsigned long (*HOOKFUNC)();` is provided for casting function pointers into
`h_Entry`/`h_SubEntry`.

## Hook calling convention

| Register | On entry | On exit |
|---|---|---|
| A0 | the `struct Hook *` itself (read `h_Data`/`h_SubEntry` through it) | scratch |
| A2 | "object": context-specific (BOOPSI object, RastPort for backfill hooks, ...) | preserve |
| A1 | "message": context-specific parameter packet (not an exec Message) | scratch |
| D0 | undefined | result (meaning defined by the caller) |
| D1 | -- | scratch |
| D2-D7, A2-A6 | -- | preserve |

- The C-style order is `(hook, object, message)` = A0, A2, A1: the register order is NOT
  alphabetical. Mixing up A1 and A2 is the classic hook bug.
- A6 is not defined on entry: load the library bases you need yourself.
- Hooks are often called on another task (window and gadget operations run on Intuition's
  input.device task): keep them short, don't call dos.library, don't Wait, assume a small stack.
- The per-use message layouts are documented by the caller: BOOPSI messages start with a ULONG
  MethodID (see the intuition boopsi reference); layer backfill messages are described at
  [InstallLayerHook](../layers/clipping.md#installlayerhook).

## Writing a hook in asm

Point `h_Entry` at the routine; it receives the registers directly.

```asm
        include "exec/types.i"
        include "utility/hooks.i"
        include "lvo/utility_lib.i"

; hook: h_Data -> ULONG counter; message = ULONG MethodID, ULONG Amount
; returns the new total in D0
CountHook:
        move.l  h_Data(a0),a0           ; A0 = counter
        move.l  4(a1),d0                ; message->Amount
        add.l   (a0),d0
        move.l  d0,(a0)
        rts

; set it up and call it through utility.library
DoCount:
        movem.l a2/a6,-(sp)
        lea     hook(pc),a0
        lea     CountHook(pc),a1
        move.l  a1,h_Entry(a0)
        lea     counter(pc),a1
        move.l  a1,h_Data(a0)
        lea     msg(pc),a1              ; A1 = message
        sub.l   a2,a2                   ; A2 = object (unused here)
        move.l  _UtilityBase,a6
        jsr     _LVOCallHookPkt(a6)     ; D0 = hook result
        movem.l (sp)+,a2/a6
        rts

hook:       dcb.b   h_SIZEOF,0
counter:    dc.l    0
msg:        dc.l    1,5
```

From asm you can also skip CallHookPkt: with A0/A1/A2 loaded, `move.l h_Entry(a0),-(sp)` then
`rts` (tail call) or `movea.l h_Entry(a0),a3` / `jsr (a3)` (A3 saved by you).

## Writing a hook in C (Bartman gcc)

gcc cannot receive arguments in A0/A2/A1, so `h_Entry` must be a small asm stub that pushes them
C-style and calls the C function kept in `h_SubEntry` (what amiga.lib `HookEntry` does; amiga.lib
is not linked in Bartman `-nostdlib` builds). A file-scope `__asm__` block keeps it in the C file:

```c
#include <proto/exec.h>
#include <proto/utility.h>
#include <utility/hooks.h>

struct UtilityBase *UtilityBase;

/* h_Entry stub: A0 = hook, A2 = object, A1 = message -> h_SubEntry(hook, object, message).
   GAS syntax with % register prefixes; D2-D7/A2-A6 are preserved by the C function. */
ULONG HookStub(void);
__asm__(
    "    .text\n"
    "    .even\n"
    "    .globl HookStub\n"
    "HookStub:\n"
    "    move.l %a1,-(%sp)\n"
    "    move.l %a2,-(%sp)\n"
    "    move.l %a0,-(%sp)\n"
    "    move.l 12(%a0),%a0\n"              /* h_SubEntry */
    "    jsr (%a0)\n"
    "    lea 12(%sp),%sp\n"
    "    rts\n");

void InitHook(struct Hook *hook, HOOKFUNC func, APTR data)
{
    hook->h_Entry    = (HOOKFUNC)HookStub;
    hook->h_SubEntry = func;
    hook->h_Data     = data;
}

struct CountMsg { ULONG MethodID; ULONG Amount; };

static ULONG CountFunc(struct Hook *hook, APTR object, struct CountMsg *msg)
{
    ULONG *counter = (ULONG *)hook->h_Data;

    (void)object;
    *counter += msg->Amount;
    return *counter;
}

ULONG Demo(void)
{
    static ULONG total;
    struct Hook hook;
    struct CountMsg msg = { 1, 5 };

    /* the (void (*)(void)) step silences -Wcast-function-type */
    InitHook(&hook, (HOOKFUNC)(void (*)(void))CountFunc, &total);
    return CallHookPkt(&hook, NULL, &msg);
}
```

The same `InitHook` works for any OS hook: `WA_BackFill`, `InstallLayerHook`, a BOOPSI
`cl_Dispatcher` (then `hook` is the class).

## Common mistakes

- Putting a plain C function straight into `h_Entry`: it reads its arguments from the stack and
  gets garbage.
- Swapping object and message: object is A2, message is A1.
- gcc 15 defaults to C23, where `ULONG (*h_Entry)()` means "no parameters": assigning a function
  with parameters without a `(HOOKFUNC)` cast is an error, and so is calling `hook->h_SubEntry(a, b, c)`
  directly. Cast, or call through CallHookPkt.
- A hook struct on the stack of a function that returns while the OS still holds it (backfill and
  class hooks must outlive the window/class).

## CallHookPkt
`ULONG CallHookPkt(struct Hook *hook, APTR object, APTR paramPacket)` — LVO -102 (-$66)
Registers: hook=A0, object=A2, paramPacket=A1; result in D0

Invoke a Hook: load the standard registers and jump to its h_Entry.

- **hook** — initialised `struct Hook` (`h_Entry` must be valid).
- **object** — context data for the hook (A2).
- **paramPacket** — pointer to the message (A1); its layout is defined by the hook's contract.
- **Result** — whatever the hook returned in D0.

Since V36.

The call is effectively a jump to `h_Entry`, so the hook runs on your task with your stack.
amiga.lib's varargs `CallHook(hook, object, MethodID, ...)` builds the message on the stack;
without amiga.lib fill a message struct and use CallHookPkt (example above).

### Gotchas
- Note the registers: object in A2, message in A1, the reverse of the C argument order.
- Hooks you call must follow the normal register rules (preserve D2-D7/A2-A6) unless their
  contract says otherwise (autodoc warning).

**See also:** [InstallLayerHook](../layers/clipping.md#installlayerhook), [DoHookClipRects](../layers/clipping.md#dohookcliprects), [calling convention topic](../topics/calling-convention.md)
