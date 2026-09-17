# Calling convention: library bases, LVOs and registers

Every Amiga shared library, device and resource is reached through a *base pointer*. Functions
are called by jumping to a fixed negative offset (the LVO, Library Vector Offset) from that base,
with arguments in registers. Get one detail wrong (A6 not the base, wrong register, trusting the
condition codes) and the call silently does something else. This guide covers the rules, how
the NDK files encode them, and how to call from vasm and from Bartman's GCC.

## Library base and jump table

```text
            base-36  jmp <abs.l>   second function     (LVO -36)   \
            base-30  jmp <abs.l>   first function      (LVO -30)    |  jump table, 6 bytes
            base-24  jmp <abs.l>   reserved (Extfunc)  (LVO -24)    |  per slot, grows
            base-18  jmp <abs.l>   Expunge             (LVO -18)    |  downwards
            base-12  jmp <abs.l>   Close               (LVO -12)    |
            base-6   jmp <abs.l>   Open                (LVO -6)    /
  A6 ---->  base+0   struct Library (LIB_SIZE = $22 bytes), then the library's own data
```

- Each slot is 6 bytes (`LIB_VECTSIZE`): the opcode `$4EF9` (`jmp abs.l`) plus a 32-bit
  address. `lib_NegSize` is the table size, `lib_PosSize` the data size.
- The first four slots are the standard vectors: `LIB_OPEN` -6, `LIB_CLOSE` -12,
  `LIB_EXPUNGE` -18, `LIB_EXTFUNC` -24 (reserved, returns 0). Programs never call them directly;
  OpenLibrary/CloseLibrary/RemLibrary do.
- Devices add `DEV_BEGINIO` -30 and `DEV_ABORTIO` -36 (exec/io.i, exec/io.h).
- So an ordinary library's first public function is at -30 ("bias 30"), and function *n*
  (counting from 0, private slots included) sits at `-(30 + 6*n)`. exec: Supervisor -30,
  AllocMem -198, OpenLibrary -552.
- Resources have no Open/Close/Expunge: cia.resource starts at bias 6 (`AddICRVector` -6).
- `jsr -198(a6)` uses a 16-bit signed displacement; the GCC inline headers emit exactly that.

## Register rules

| Rule | Detail |
|---|---|
| A6 = base | Load the library base into A6 before EVERY call. The function uses A6 to find its data. |
| Arguments | In the registers listed in the entry's `Registers:` line / autodoc SYNOPSIS / fd file. Nothing on the stack. |
| Result | In D0 (32 bits). |
| Scratch | D0, D1, A0, A1 (and the condition codes) may be destroyed by any call. |
| Preserved | D2-D7, A2-A6 and SP survive the call. |
| Flags | Do not rely on N/Z after return: `tst.l d0` yourself. (FindName is documented to set Z, but testing costs nothing.) |

Exceptions and oddities worth remembering:

- Some calls are documented to preserve *all* registers: exec Forbid, Permit, Disable, Enable,
  GetCC, ReleaseSemaphore, ObtainSemaphore and ObtainSemaphoreShared (V37+).
- Odd argument registers: exec Alert takes D7, Supervisor takes A5, SetFunction uses only the
  low word of A0. dos.library takes most arguments in D1-D4 and reports errors via IoErr.
- BYTE/WORD results: only the low 8/16 bits are defined unless the doc promises sign extension
  (DoIO, WaitIO and OpenDevice do). Otherwise `tst.b d0` / `ext.w d0` / `ext.l d0` first.
  `D0-0:8` in an autodoc SYNOPSIS means "low 8 bits of D0".
- A few functions need a Process, not a plain Task (anything that can end up in dos.library),
  and most may not be called from interrupts. The entry says so.

## How the NDK encodes it

All of these files are generated from one description; they must agree.

- **`fd/<lib>_lib.fd`** (NDK 3.9 `Include/fd`): `##base _SysBase`, `##bias 30`, then one line per
  slot, `##private`/`##public` switch visibility (private slots still use an offset), `##end`.
  ```text
  ##base _SysBase
  ##bias 30
  Supervisor(userFunction)(a5)
  ##private
  execPrivate1()()
  ##public
  AllocMem(byteSize,requirements)(d0,d1)
  ```
  LVO = -(bias + 6 * n), n = index of the function line (comment and `##` lines not counted).
  Registers are separated by `,` or `/`.
- **`sfd/<lib>_lib.sfd`**: `==base`, `==basetype`, `==libname`, `==bias`, `==public`/`==private`,
  `==reserve n` (n unnamed slots), `==version n` (version marker for what follows), full C
  prototypes followed by `(d0,d1)`, and `==varargs` before an alternative prototype that shares
  the previous slot (e.g. `OpenWindowTags` after `OpenWindowTagList`).
- **`lvo/<lib>_lib.i`** (Bartman's sys-include; generated): `_LVOAllocMem EQU -198`. This is the
  file asm examples in this skill include.
- **NDK 3.9 `include_i/exec/exec_lib.i`** (and siblings): only `FUNCDEF AllocMem` lines in slot
  order. You must supply the macro:
  ```asm
  FUNCDEF     MACRO
  _LVO\1      EQU     FUNC_CNT
  FUNC_CNT    SET     FUNC_CNT-6
              ENDM
  FUNC_CNT    SET     -30                     ; LIB_USERDEF: skip the 4 standard vectors
              include "exec/exec_lib.i"       ; defines _LVOSupervisor = -30, ...
  ```
  This file names some private exec slots differently from the fd file (ChildFree..ChildWait
  at -738..-756 vs execPrivate10-13); the offsets are the same.
- **`clib/<lib>_protos.h`**: plain C prototypes, no register information.
- **`inline/<lib>.h`** (GCC, Bartman): one macro per function built from `inline/macros.h`
  (`LP2(0xc6, APTR, AllocMem, ULONG, byteSize, d0, ULONG, requirements, d1, , EXEC_BASE_NAME)`).
  It loads register variables, emits `jsr a6@(-0xc6:W)`, and tells GCC that d0/d1/a0/a1 and
  fp0/fp1 are clobbered. The base expression defaults to a global (`EXEC_BASE_NAME` = `SysBase`)
  and can be overridden by defining the macro before the include.
- **`proto/<lib>.h`**: the header you include. Bartman's version pulls in clib + inline and
  declares `extern struct ExecBase *SysBase;` (etc.).
- **`pragmas/<lib>_pragmas.h`** (SAS/C, shipped in NDK 3.9 `include_h/pragmas`, used by NDK's
  own `proto/*.h`; NOT present in Bartman's sys-include): `#pragma syscall AllocMem c6 1002`
  = offset hex, then argument registers as hex nibbles in reverse order (0-7 = d0-d7,
  8-f = a0-a7), result register, argument count. `syscall` is the SysBase-implied variant.

## Calling from assembler (vasm)

```asm
        include "exec/memory.i"
        include "lvo/exec_lib.i"
        include "lvo/graphics_lib.i"

        move.l  4.w,a6                  ; ExecBase from address 4
        lea     gfxname(pc),a1
        moveq   #39,d0
        jsr     _LVOOpenLibrary(a6)     ; A1 = name, D0 = version
        move.l  d0,gfxbase
        beq     .exit

        move.l  #320*256/8,d0
        move.l  #MEMF_CHIP!MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)        ; A6 still ExecBase: exec call
        move.l  d0,plane                ; D1/A0/A1 are garbage now
        beq     .closegfx

        move.l  gfxbase,a6              ; switch base before a graphics call
        jsr     _LVOWaitTOF(a6)
        move.l  4.w,a6                  ; and back before the next exec call

        move.l  plane,a1
        move.l  #320*256/8,d0
        jsr     _LVOFreeMem(a6)
.closegfx:
        move.l  gfxbase,a1
        jsr     _LVOCloseLibrary(a6)
.exit:
        rts

gfxname:
        dc.b    "graphics.library",0
        even
gfxbase:        dc.l    0
plane:          dc.l    0
```

- Keep values you need across a call in D2-D7/A2-A5, not D0/D1/A0/A1.
- If your own routine changes A6, save and restore it (`move.l a6,-(sp)` ... `move.l (sp)+,a6`)
  when callers expect it preserved.
- NDK macros: `CALLLIB _LVOx` (A6 already correct) and `LINKLIB _LVOx,base` (saves A6, loads
  base, calls, restores) from exec/libraries.i; `JSRLIB x` from exec/macros.i (adds the `_LVO`
  prefix and an XREF).

## Calling from C (Bartman m68k-amiga-elf-gcc)

```c
#include <proto/exec.h>
#include <proto/graphics.h>
#include <exec/execbase.h>
#include <graphics/gfxbase.h>

struct ExecBase *SysBase;               /* names are fixed by the inline headers */
struct GfxBase  *GfxBase;

int main(void)
{
    SysBase = *((struct ExecBase **)4UL);
    GfxBase = (struct GfxBase *)OpenLibrary((CONST_STRPTR)"graphics.library", 39);
    if (!GfxBase)
        return 20;
    WaitTOF();                          /* expands to jsr -270(a6) with A6 = GfxBase */
    CloseLibrary((struct Library *)GfxBase);
    return 0;
}
```

- Base variables must be globals named exactly `SysBase`, `DOSBase`, `GfxBase`, `IntuitionBase`,
  `DiskfontBase`, `UtilityBase` (or redefine `<LIB>_BASE_NAME` before including the proto).
  A NULL or stale base is not detected: the macro just jumps through it.
- The template links with `-nostdlib`: amiga.lib is not available. `#include <inline/alib.h>`
  gives only `BeginIO()` and `NewList()` as inline macros (`<proto/alib.h>` does not compile:
  its clib prototypes use the undefined `__stdargs`); other amiga.lib functions
  (CreatePort, CreateTask, CreateExtIO, LibCreatePool, sprintf, HookEntry, ...) will not link.
  Use the V36+ exec equivalents (CreateMsgPort, CreateIORequest, CreatePool) or write them.
- Cast string literals to `CONST_STRPTR` and library bases to `struct Library *` where the
  prototype wants it; GCC 14+ turns many implicit pointer conversions into errors.
- A function with no inline macro (private or newer than the headers) can be called with the
  `LPn`/`LPnNR` macros from `inline/macros.h` or an asm stub.

## Varargs and TagList forms

Functions that take a `struct TagItem *` have one real LVO, usually named `...TagList` or
`...A` (`OpenWindowTagList`, `AllocAudioA`). The `...Tags` / non-A name
(`OpenWindowTags(nw, tag, data, ..., TAG_DONE)`) is not a library function:

- With SAS/C-style toolchains it is a stub in amiga.lib that points A1 at the stacked arguments.
- With Bartman's GCC it is an inline macro that builds a `ULONG` array on the stack and calls the
  TagList function. Every `ti_Data` must be an integer: cast pointers, `(ULONG)ptr`.
- From asm always call the TagList/A function with a `dc.l tag,data,...,TAG_DONE` table.

Details and helpers: [taglists topic](taglists.md).

## Code the OS calls back

Interrupt servers, software interrupts, low-memory handlers, hooks, SetFunction patches and
RawDoFmt output procedures are entered with *registers*, not C stack arguments:

- Read the entry's register list (e.g. interrupt server: A1 = `is_Data`; hook: A0 = hook,
  A2 = object, A1 = message; RawDoFmt PutChProc: D0 = char, A3 = PutChData).
- Preserve D2-D7/A2-A6 unless the doc lists them as scratch; return values go in D0, and some
  callers test the Z flag (interrupt server chains), so end with `tst.l d0` or `moveq`.
- Bartman's template writes such entries in asm (its `KPutCharX`/`PutChar` callbacks for
  RawDoFmt are asm). A stub can push the registers and call ordinary C, whose stack-argument
  convention also treats D0/D1/A0/A1 as scratch:

```asm
; hook entry: A0 = hook, A2 = object, A1 = message -> ULONG HookFunc(hook, object, msg)
        xref    HookFunc                ; ELF C symbols have no leading underscore
        xdef    hookEntry
hookEntry:
        move.l  a1,-(sp)
        move.l  a2,-(sp)
        move.l  a0,-(sp)
        jsr     HookFunc
        lea     12(sp),sp               ; drop the 3 arguments
        tst.l   d0                      ; set Z from the result for callers that test it
        rts
```

## Common mistakes

- **A6 left pointing at the previous library** after calling graphics or dos: the next exec call
  jumps into the wrong jump table. Reload `move.l 4.w,a6` (or the right base) before each group.
- **Relying on D0/D1/A0/A1 surviving a call**, e.g. using A1 as a loop pointer across `jsr`.
- **Branching on flags straight after `jsr`** (`jsr _LVOAllocMem(a6)` / `beq`): add `tst.l d0`.
- **Treating a BYTE result as 32 bits** (AllocSignal, SetTaskPri) without `ext`/`tst.b`.
- **Using the fd/include parameter order instead of the register list** when writing asm; the
  order of arguments and registers often differs (`OpenLibrary`: name A1, version D0).
- **Hardcoding numeric LVOs** copied from memory instead of `_LVOxxx`; slots include private
  entries, so counting public functions gives wrong offsets.
- **Calling a function the running OS does not have**: the slot exists in the table only if the
  library version is high enough. Check `lib_Version` (see
  [opening libraries](opening-libraries.md)).
- **Calling `...Tags` varargs from asm** or expecting it in the jump table.
- **Writing a callback in plain C** and pointing the OS at it: its arguments arrive in registers
  the C function never reads.
- **Naming your own function or variable like an OS call** (`Insert`, `Remove`, `Wait`, `Signal`,
  `Debug`, ...) in C: the Bartman inline headers define every library function name as a
  function-like macro, so the name expands or fails to compile. Pick different names.
- **Missing casts in inline macros under GCC 14/15**: a pointer passed as a `...Tags` `ti_Data`
  needs `(ULONG)ptr`; inline macros with `**` parameters (NextTagItem, AVL_AddNode,
  AVL_RemNodeByAddress, AVL_RemNodeByKey) trip `-Wincompatible-pointer-types` errors (see
  [taglists](taglists.md)).

See also: [opening libraries](opening-libraries.md), [taglists](taglists.md),
[structures](structures.md), [SetFunction](../exec/libraries-devices-resources.md#setfunction),
[MakeLibrary](../exec/libraries-devices-resources.md#makelibrary)
