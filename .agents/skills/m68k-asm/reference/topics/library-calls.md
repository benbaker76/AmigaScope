# Calling AmigaOS libraries from assembler

Every OS function is reached through a library base pointer and a negative offset (LVO).
This page covers the mechanics; per-function register tables and semantics are in the
amiga-os skill.

## ExecBase and opening libraries

- Address `$4` holds the exec.library base, the only fixed OS address:
  `move.l 4.w,a6`.
- Every other library base comes from `OpenLibrary(name,version)`: name in A1, minimum
  version in D0, base (or 0) in D0. Close it with `CloseLibrary(base)` (A1) exactly once;
  since V36 passing 0 is safe (exec autodocs).
- `version` is the lowest library version you need. `LIBRARY_MINIMUM` in
  `exec/types.i` is 33; `INCLUDE_VERSION` (40) must NOT be used for OpenLibrary (comment in
  `exec/types.i`). V36 = OS 2.0 (HRM). `OldOpenLibrary(name)` = `OpenLibrary(name,0)`.
- Name strings: NDK macros `DOSNAME` (`dos/dos.i`) and `GRAPHICSNAME`
  (`graphics/gfxbase.i`) expand to `dc.b '<name>.library',0`; add `even` after them.
  Names are case-sensitive in exec's library list (OpenLibrary BUGS note).

```asm
        include "exec/types.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        lea     DosName(pc),a1
        moveq   #36,d0                  ; need V36+
        jsr     _LVOOpenLibrary(a6)
        move.l  d0,DOSBase              ; MOVE sets Z: test right here
        beq     NoDos
        ; ...
        move.l  DOSBase,a1
        jsr     _LVOCloseLibrary(a6)    ; a6 still ExecBase
        ; ...
DosName: dc.b   "dos.library",0
        even
```

## Calling convention

| Item | Rule |
|---|---|
| Base | A6 = library base when you `jsr`; exec's is `move.l 4.w,a6` |
| Call | `jsr _LVO<Function>(a6)`; offsets from `include "lvo/<lib>_lib.i"` |
| Arguments | in the registers the autodoc names (usually D0/D1/A0/A1, dos uses D1-D4) |
| Result | D0 |
| Trashed | D0, D1, A0, A1 |
| Preserved | D2-D7, A2-A6 |

- Offsets: each vector is 6 bytes (`LIB_VECTSIZE` 6) and exec reserves the first 4
  (`LIB_OPEN`, `LIB_CLOSE`, `LIB_EXPUNGE`, `LIB_EXTFUNC`), so the first public function
  is at -30 (`LIB_USERDEF`, `exec/libraries.i`; `_LVOSupervisor EQU -30`).
- Test results explicitly (`tst.l d0`, or a `move.l d0,<ea>` that sets Z/N) instead of
  trusting the flags a library returns.
- Keep loop counters, pointers and your own bases in D2-D7/A2-A5 across calls.
- A6 is preserved, so consecutive calls to the same library need no reload; switching
  libraries needs `move.l <Base>,a6` (or LINKLIB).

## From C prototype to registers

The autodoc synopsis puts the register under each argument, and the NDK inline headers
say the same in macro form:

```c
    library = OpenLibrary(libName, version)
    D0                    A1       D0
```
```c
/* inline/exec.h */
#define OpenLibrary(___libName, ___version) \
      LP2(0x228, struct Library *, OpenLibrary , CONST_STRPTR, ___libName, a1, ULONG, ___version, d0, \
      , EXEC_BASE_NAME)
```

`0x228` = 552, so `_LVOOpenLibrary EQU -552` in `lvo/exec_lib.i`. The result register is
always D0. Examples from the generated tables:

| Call | LVO | Registers |
|---|---|---|
| `AllocMem(byteSize, requirements)` | -198 | D0, D1 -> D0 |
| `FreeMem(memoryBlock, byteSize)` | -210 | A1, D0 |
| `PutStr(str)` (dos, V36) | -948 | D1 -> D0 |
| `Write(file, buffer, length)` (dos) | -48 | D1, D2, D3 -> D0 |
| `LoadView(view)` (graphics) | -222 | A1 |
| `WaitTOF()` (graphics) | -270 | none |

The full per-library tables are in the amiga-os skill.

## Worked example: graphics.library and GfxBase fields

```asm
        include "exec/types.i"
        include "graphics/gfxbase.i"    ; pulls in exec/libraries.i etc.
        include "lvo/exec_lib.i"
        include "lvo/graphics_lib.i"

        section code,code
TakeDisplay:
        move.l  4.w,a6
        lea     GfxName(pc),a1
        moveq   #33,d0
        jsr     _LVOOpenLibrary(a6)
        move.l  d0,_GfxBase
        beq.s   .fail
        move.l  d0,a6                   ; now calling graphics
        move.l  gb_ActiView(a6),OldView ; offset 34
        move.l  gb_copinit(a6),OldCop   ; offset 38: system copper list
        suba.l  a1,a1
        jsr     _LVOLoadView(a6)        ; LoadView(NULL): no View displayed
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOWaitTOF(a6)
        moveq   #-1,d0
.fail:  rts                             ; d0 = 0 if graphics did not open

RestoreDisplay:
        move.l  _GfxBase,a6
        move.l  OldView,a1
        jsr     _LVOLoadView(a6)
        jsr     _LVOWaitTOF(a6)
        move.l  OldCop,$dff080          ; COP1LC back to the system list
        move.l  a6,a1
        move.l  4.w,a6
        jsr     _LVOCloseLibrary(a6)
        rts

GfxName: GRAPHICSNAME                   ; dc.b 'graphics.library',0
        even

        section vars,bss
_GfxBase: ds.l  1                      ; NOT 'GfxBase': see gotcha below
OldView: ds.l   1
OldCop: ds.l    1
```

Per the LoadView autodoc, sprites and display DMA stay active after `LoadView(NULL)`;
switching those off is hardware work (see the amiga-hardware skill).

### Gotchas
- `STRUCTURE GfxBase,LIB_SIZE` in `graphics/gfxbase.i` defines the symbol `GfxBase` as the
  constant 0 (likewise `ExecBase` in `exec/execbase.i`, `DosLibrary` in
  `dos/dosextens.i`). A variable label `GfxBase:` is then error 75, and
  `move.l GfxBase,a6` without your own variable silently reads address 0 (tested). Name
  base variables `_GfxBase`, `GfxBasePtr`...

## Call macros in the NDK includes

Verified in NDK 3.9 `exec/libraries.i` and `exec/macros.i`, assembled with vasm:

| Macro | Include | Expands to |
|---|---|---|
| `CALLLIB _LVOx` | exec/libraries.i | `JSR _LVOx(A6)`; FAIL if more than 1 argument |
| `LINKLIB _LVOx,Base` | exec/libraries.i | `MOVE.L A6,-(SP)` / `MOVE.L Base,A6` / `JSR _LVOx(A6)` / `MOVE.L (SP)+,A6` |
| `JSRLIB Name` | exec/macros.i | `XREF _LVOName` + `jsr _LVOName(a6)` (name without `_LVO`) |
| `JMPLIB Name` | exec/macros.i | `XREF _LVOName` + `jmp _LVOName(a6)` |
| `CLEAR Dn` / `CLEARA An` | exec/macros.i | `moveq.l #0,Dn` / `suba.l An,An` |

```asm
        include "exec/types.i"
        include "exec/libraries.i"
        include "lvo/exec_lib.i"
        include "lvo/dos_lib.i"

        move.l  4.w,a6
        CALLLIB _LVOForbid
        LINKLIB _LVOOutput,DOSBase      ; DOSBase = the variable holding the base
        CALLLIB _LVOPermit
```

### Gotchas
- LINKLIB's second argument is used as a MOVE source: pass the memory location of the
  base (`DOSBase`), not `#DOSBase`. The result in D0 survives the A6 restore.
- There is no `CALLEXEC`, `CALLDOS`, `CALLGRAF` or `LIBCALL` macro in these NDK includes
  (searched). Write the `jsr _LVOx(a6)` directly or define your own macro.
- `exec/macros.i` PUSHM/POPM use `\*VALOF()`, which vasm does not support (tested).
- `exec/exec_lib.i` holds only `FUNCDEF` lines; include `lvo/exec_lib.i` instead.
- JSRLIB's `XREF` turns a missing `lvo` include into an import even with `-x`:
  `-Fhunk` assembles cleanly and only `-Fhunkexe` (error 3009) or the linker complains
  (tested).

## Common mistakes

- **A6 not reloaded** after calling another library: the next `jsr _LVO...(a6)` jumps into
  the wrong library's jump table.
- **Keeping a value in D0/D1/A0/A1 across a call.**
- **Using the result without testing for 0** (OpenLibrary, AllocMem, Open...).
- **Wrong argument registers**: OpenLibrary takes the name in A1 (not A0) and the version
  in D0; check every call against the autodoc register line.
- **Closing with the wrong A6**: CloseLibrary is an exec call, so A6 must be ExecBase
  while A1 holds the base being closed.
- **Mixing `lvo/dos_lib.i` with `dos/dos_lib.i`**: both define the same `_LVO` names
  (error 68).

**See also:** [program structure](amiga-program-structure.md),
[structure macros](macros-and-structures.md), [INCLUDE](../directives/include-and-output.md#include),
[MACRO](../directives/macros-repeat.md#macro)
