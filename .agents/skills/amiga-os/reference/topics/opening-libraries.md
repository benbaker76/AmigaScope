# Opening libraries, devices and resources

Before a program can call any OS function it needs the right base pointer. exec.library is
always there (its base lives at address 4); every other library is opened by name with a minimum
version and closed again on exit, devices are opened through an I/O request, and resources are
looked up without ever being closed. This guide shows the correct sequence and the traps.
Call mechanics (A6, registers, LVOs): [calling convention](calling-convention.md).

## ExecBase from address 4

- Address 4 holds the ExecBase pointer (amiga.lib calls it `_AbsExecBase`). Load it with
  `move.l 4.w,a6`, or in C `SysBase = *((struct ExecBase **)4UL);` once at startup and keep it
  in `SysBase`.
- Exec is never opened or closed. Do not take its address from anywhere else (a copy in some
  structure, a hardcoded ROM address).
- Exec's own version: `SysBase->LibNode.lib_Version` / `lib_Revision` (asm: `LIB_VERSION(a6)` at
  $14 and `LIB_REVISION(a6)` at $16, both UWORD). Kickstart 3.1 ROMs report exec V40.
- Functions newer than the running exec do not exist in its jump table: check the version before
  calling anything marked `Since Vnn`.

## Version numbers

The NDK prototype headers group functions by version with these release names:

| Version | Release | Notes |
|---|---|---|
| 31 | 1.1 | |
| 33 | 1.2 | signal semaphores, AddMemList, CopyMem |
| 34 | 1.3 | |
| 36 | 2.0 | CreateMsgPort, CreateIORequest, AllocVec, TagList APIs, CloseLibrary(NULL) safe |
| 37 | 2.04 | |
| 38 | 2.1 | |
| 39 | 3.0 ("Release 3") | AGA graphics, exec memory pools, low-memory handlers |
| 40 | 3.1 | |
| 44 | 3.5 | |
| 45 | 3.9 | exec V45 (designed to be loadable into RAM): NewMinList, AVL trees |

Pass the lowest version that has every function (and every tag or flag) you use. Version 0
accepts anything, including a 1.x library missing half the calls you are about to make.

## OpenLibrary, check, CloseLibrary

1. Call [OpenLibrary](../exec/libraries-devices-resources.md#openlibrary) with the exact name
   (case-sensitive: `"graphics.library"`) and the minimum version.
2. Test the result for 0 and fail gracefully (error message, return code 20 from a CLI program).
3. Cast the base to the library's own structure (`struct GfxBase *`, `struct IntuitionBase *`,
   `struct DosLibrary *`) if you read its fields, and store it in the global the inline headers
   expect (`GfxBase`, `IntuitionBase`, `DOSBase`, ...).
4. If you also need a minimum *revision*, compare `lib_Version`/`lib_Revision` after the open.
5. On exit call [CloseLibrary](../exec/libraries-devices-resources.md#closelibrary) exactly once
   per successful open, in reverse order, then forget the pointer.

Revision check:

```c
static BOOL LibAtLeast(struct Library *lib, UWORD ver, UWORD rev)
{
    return lib->lib_Version > ver ||
           (lib->lib_Version == ver && lib->lib_Revision >= rev);
}
```

```asm
; A0 = library base. Branch to .tooold if older than V40.68 (example numbers)
        cmp.w   #40,LIB_VERSION(a0)
        bhi.s   .ok                     ; unsigned: UWORD fields
        blo.s   .tooold
        cmp.w   #68,LIB_REVISION(a0)
        blo.s   .tooold
.ok:
```

Rules:

- CloseLibrary(NULL) is harmless from V36 on. On 1.x only close what really opened.
- After CloseLibrary the base is dead: the library can be expunged and a later OpenLibrary may
  return a different address. Never cache a base across a close/reopen.
- OpenLibrary may load from disk and Wait(), so never call it from an interrupt, a software
  interrupt, a low-memory handler, or between Disable()/Enable().
- Disk-based libraries need DOS to be running (not from a bootblock or before DOS starts).
- [OldOpenLibrary](../exec/libraries-devices-resources.md#oldopenlibrary) is the 1.0 no-version
  call: never use it.

## Libraries, devices and resources compared

| | Library | Device | Resource |
|---|---|---|---|
| Open | OpenLibrary(name, version) | OpenDevice(name, unit, ioRequest, flags) | OpenResource(name) |
| Success | base != 0 | result == 0 (and `io_Error` 0) | base != 0 |
| Close | CloseLibrary(base) | CloseDevice(ioRequest) after all I/O is back | none |
| Handle you use | base in A6 | IORequest (DoIO/SendIO) | base in A6 |
| ExecBase list | `LibList` | `DeviceList` | `ResourceList` |

- Devices: create the reply port and a request of the device's size first, then OpenDevice.
  Note the inverted result: 0 means success. Full pattern in [device I/O](../exec/io.md) and
  [OpenDevice](../exec/libraries-devices-resources.md#opendevice).
- Resources: [OpenResource](../exec/libraries-devices-resources.md#openresource) returns a base
  whose functions you call with A6 = that base; there is no close and no open count.

## Startup and shutdown skeleton (C)

```c
#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/graphics.h>
#include <proto/intuition.h>
#include <exec/execbase.h>
#include <dos/dosextens.h>
#include <graphics/gfxbase.h>
#include <intuition/intuitionbase.h>

struct ExecBase      *SysBase;
struct DosLibrary    *DOSBase;
struct GfxBase       *GfxBase;
struct IntuitionBase *IntuitionBase;

static int Run(void)
{
    /* the program */
    return 0;
}

int main(void)
{
    int rc = 20;

    SysBase = *((struct ExecBase **)4UL);
    if (SysBase->LibNode.lib_Version < 39)      /* need Kickstart 3.0+ */
        return rc;

    DOSBase = (struct DosLibrary *)OpenLibrary((CONST_STRPTR)"dos.library", 39);
    if (!DOSBase)
        goto cleanup;
    GfxBase = (struct GfxBase *)OpenLibrary((CONST_STRPTR)"graphics.library", 39);
    if (!GfxBase)
        goto cleanup;
    IntuitionBase = (struct IntuitionBase *)OpenLibrary((CONST_STRPTR)"intuition.library", 39);
    if (!IntuitionBase)
        goto cleanup;

    rc = Run();

cleanup:                                        /* reverse order; NULL is fine on V36+ */
    CloseLibrary((struct Library *)IntuitionBase);
    CloseLibrary((struct Library *)GfxBase);
    CloseLibrary((struct Library *)DOSBase);
    IntuitionBase = NULL;
    GfxBase = NULL;
    DOSBase = NULL;
    return rc;
}
```

## Startup and shutdown skeleton (asm)

```asm
        include "exec/types.i"
        include "exec/libraries.i"
        include "lvo/exec_lib.i"

        section code,code
start:
        movem.l d2-d7/a2-a6,-(sp)
        moveq   #20,d7                  ; return code, survives library calls
        move.l  4.w,a6
        cmp.w   #39,LIB_VERSION(a6)     ; Kickstart 3.0+
        blo     .exit

        lea     dosname(pc),a1
        moveq   #39,d0
        jsr     _LVOOpenLibrary(a6)
        move.l  d0,DOSBase
        beq     .cleanup
        lea     gfxname(pc),a1
        moveq   #39,d0
        jsr     _LVOOpenLibrary(a6)
        move.l  d0,GfxBase
        beq     .cleanup
        lea     intname(pc),a1
        moveq   #39,d0
        jsr     _LVOOpenLibrary(a6)
        move.l  d0,IntuitionBase
        beq     .cleanup

        bsr     main                    ; returns its code in D0
        move.l  d0,d7

.cleanup:
        move.l  4.w,a6                  ; main may have left another base in A6
        move.l  IntuitionBase,a1        ; 0 is allowed on V36+
        jsr     _LVOCloseLibrary(a6)
        move.l  GfxBase,a1
        jsr     _LVOCloseLibrary(a6)
        move.l  DOSBase,a1
        jsr     _LVOCloseLibrary(a6)
.exit:
        move.l  d7,d0
        movem.l (sp)+,d2-d7/a2-a6
        rts

main:
        moveq   #0,d0
        rts

dosname:        dc.b    "dos.library",0
gfxname:        dc.b    "graphics.library",0
intname:        dc.b    "intuition.library",0
        even

        section vars,data
DOSBase:        dc.l    0
GfxBase:        dc.l    0
IntuitionBase:  dc.l    0
```

- Names stay in the code section so `lea name(pc),a1` is in range; the base variables are
  explicitly zero so the cleanup path can close all three unconditionally.
- A program started from Workbench must also fetch and reply its startup message (dos.library
  topic); the skeleton above is for CLI starts.

## Checking what the ROM contains

[FindResident](../exec/libraries-devices-resources.md#findresident) reports the ROMTag of a
module (with `rt_Version`) without opening it, and `SysBase->LibList` lists libraries already in
memory (walk it under Forbid). Libraries such as diskfont.library or asl.library normally come
from LIBS: on disk, so they need DOS and may fail on a bare boot disk (unverified for specific
ROM sets).

## Common mistakes

- **Version 0** in OpenLibrary: the call succeeds on an old system, then a missing function is
  called through a jump slot that does not exist.
- **Forgetting the cast** to `struct GfxBase *` / `struct IntuitionBase *` and then reading fields
  through `struct Library *`, or declaring the base with the wrong global name, so the inline
  header uses an unset `GfxBase`.
- **Treating OpenDevice like OpenLibrary**: `if (OpenDevice(...))` is the failure case.
- **Closing twice** or closing a library that failed to open on a 1.x system.
- **Using a base after CloseLibrary** (e.g. cleanup code that calls graphics after closing it).
- **Opening in an interrupt server or under Disable()**: OpenLibrary can load from disk and Wait.
- **Calling OpenLibrary("exec.library")** to get SysBase: read address 4 instead (and if you did
  open it, you must close it).
- **Using OldOpenLibrary**, or copying 1.x-era code that does.
- **Case-mismatched names** ("Graphics.library"): may load a second copy from disk or fail.
- **Leaving A6 on another library** before the cleanup CloseLibrary calls.

See also: [calling convention](calling-convention.md),
[libraries, devices and resources](../exec/libraries-devices-resources.md),
[device I/O](../exec/io.md), [structures](structures.md)
