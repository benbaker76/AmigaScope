# exec.library: libraries, devices and resources

Exec keeps three named system lists: `LibList`, `DeviceList` and `ResourceList` (all in ExecBase).
Programs open libraries with OpenLibrary and close them with CloseLibrary; devices are opened
*through an IORequest* with OpenDevice/CloseDevice (see [io.md](io.md)); resources are fetched
with OpenResource and never closed. The rest of this file (MakeLibrary, InitStruct, Add*/Rem*,
ROMTags, SetFunction) is for code that builds, patches or flushes such modules.
Walkthrough: [opening libraries topic](../topics/opening-libraries.md); call mechanics:
[calling convention topic](../topics/calling-convention.md).

## OpenLibrary
`struct Library * OpenLibrary(CONST_STRPTR libName, ULONG version)` — LVO -552 (-$228)
Registers: libName=A1, version=D0; result in D0

Open a library by name and minimum version and return its base.

- **libName** — exact, case-sensitive exec name (`"graphics.library"`); a path such as
  `"MyDisk:libs/my.library"` is also accepted and loads that file.
- **version** — minimum `lib_Version` you accept. 0 means any version: almost always wrong.
- **Result** — library base (cast to the right base type), or 0 if the library is missing,
  too old or could not be loaded. ALWAYS test it.

### Example
```c
#include <proto/exec.h>
#include <graphics/gfxbase.h>

struct GfxBase *GfxBase;

GfxBase = (struct GfxBase *)OpenLibrary((CONST_STRPTR)"graphics.library", 39);
if (GfxBase == NULL)
    return 20;                      /* needs V39 (Release 3) */
/* ... */
CloseLibrary((struct Library *)GfxBase);
```

```asm
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        lea     gfxname(pc),a1
        moveq   #39,d0                  ; minimum version
        jsr     _LVOOpenLibrary(a6)
        move.l  d0,_GfxBase
        beq     .nogfx                  ; 0 = failed
        ; ...
        move.l  _GfxBase,a1
        jsr     _LVOCloseLibrary(a6)
.nogfx:
        ; ...
gfxname:
        dc.b    "graphics.library",0
        even
```

### Gotchas
- Exec list names are case-sensitive but AmigaDOS file names are not: a wrongly cased name
  can load a second copy from disk. Copy the name from the include (`GRAPHICSNAME`, `DOSNAME`).
- Disk-based libraries need DOS running. Before V36 only Processes could trigger a disk load;
  from V36 plain Tasks may call it, but DOS requesters can still appear.
- It may load from disk and Wait(): never call from an interrupt or inside Disable().
- To require a minimum *revision* too, compare `lib_Version`/`lib_Revision` after the open.
- Every successful open must be matched by exactly one CloseLibrary.
- A disk library whose ROMTag version differs from its `lib_Version` may fail to load on V36.

**See also:** [CloseLibrary](#closelibrary), [OldOpenLibrary](#oldopenlibrary), [OpenDevice](#opendevice), [OpenResource](#openresource), [FindResident](#findresident)

## CloseLibrary
`VOID CloseLibrary(struct Library *library)` — LVO -414 (-$19E)
Registers: library=A1; no result

Release a library opened with OpenLibrary.

- **library** — base returned by OpenLibrary. NULL is allowed from V36 on (does nothing).

### Example
```asm
        move.l  4.w,a6
        move.l  _DOSBase,a1             ; may be 0 on V36+
        jsr     _LVOCloseLibrary(a6)
        clr.l   _DOSBase                ; never use the old base again
```

### Gotchas
- After the close the base and every function in it are off-limits: the library may be
  expunged at any time. Clear your base variable.
- NULL is only accepted from V36 on: guard the call when targeting Kickstart 1.x.
- Close exactly as often as you opened; an extra close corrupts `lib_OpenCnt`.

**See also:** [OpenLibrary](#openlibrary), [RemLibrary](#remlibrary)

## OldOpenLibrary
`struct Library * OldOpenLibrary(CONST_STRPTR libName)` — LVO -408 (-$198)
Registers: libName=A1; result in D0

Obsolete: open a library without any version check.

- **libName** — library name.
- **Result** — base or 0; identical to `OpenLibrary(libName, 0)`.

Kept only for binaries built for the 1.0 system. New code must call
[OpenLibrary](#openlibrary) with a real minimum version.

**See also:** [OpenLibrary](#openlibrary), [CloseLibrary](#closelibrary)

## OpenDevice
`BYTE OpenDevice(CONST_STRPTR devName, ULONG unit, struct IORequest *ioRequest, ULONG flags)` — LVO -444 (-$1BC)
Registers: devName=A0, unit=D0, ioRequest=A1, flags=D1; result in D0

Open a device unit and initialise an IORequest for talking to it.

- **devName** — exact exec name (`"timer.device"`, `TIMERNAME`); a path to a device file works too.
- **unit** — device-specific unit number (e.g. `UNIT_MICROHZ`, `UNIT_VBLANK` for timer.device;
  drive number for trackdisk.device); 0 when the device has no units.
- **ioRequest** — request of the size the device expects (`struct timerequest`,
  `struct IOExtTD`, ...), normally from [CreateIORequest](io.md#createiorequest) with a valid reply
  port. On success exec fills `io_Device` and `io_Unit`.
- **flags** — device-specific open flags, usually 0.
- **Result** — sign-extended `io_Error`: **0 = success**, otherwise an error such as
  `IOERR_OPENFAIL` (-1) or `IOERR_UNITBUSY` (-6) from exec/errors.h.

### Example
```c
#include <proto/exec.h>
#include <devices/timer.h>

struct MsgPort *port = CreateMsgPort();
struct timerequest *tr = NULL;
BOOL open = FALSE;

if (port)
    tr = (struct timerequest *)CreateIORequest(port, sizeof(struct timerequest));
if (tr)
    open = (OpenDevice((CONST_STRPTR)TIMERNAME, UNIT_VBLANK, (struct IORequest *)tr, 0) == 0);

if (open) {
    tr->tr_node.io_Command = TR_ADDREQUEST;   /* sleep 1 second */
    tr->tr_time.tv_secs    = 1;
    tr->tr_time.tv_micro   = 0;
    DoIO((struct IORequest *)tr);
    CloseDevice((struct IORequest *)tr);
}
DeleteIORequest((struct IORequest *)tr);      /* NULL-safe */
DeleteMsgPort(port);                          /* NULL-safe */
```

### Gotchas
- The result logic is the opposite of OpenLibrary: 0 means OK. `if (OpenDevice(...))` is the
  *failure* branch.
- On failure `io_Device` is not valid: do not send I/O through that request. CloseDevice on a
  failed or zeroed request is safe only from V36 on; before V36 skip it.
- Names are case-sensitive exec list names; devices on disk need DOS running (Tasks could not
  trigger disk loads before V36; turning DOS requesters off needs a Process).
- To run several requests in parallel on one open unit, the usual technique is to allocate more
  requests and copy `io_Device` and `io_Unit` from the opened one (unverified).
- Never call from an interrupt.

**See also:** [CloseDevice](#closedevice), [CreateIORequest](io.md#createiorequest), [DoIO](io.md#doio), [SendIO](io.md#sendio), [AbortIO](io.md#abortio)

## CloseDevice
`VOID CloseDevice(struct IORequest *ioRequest)` — LVO -450 (-$1C2)
Registers: ioRequest=A1; no result

End access to a device unit opened with OpenDevice.

- **ioRequest** — the request that was passed to OpenDevice. From V36 a zeroed request or one
  whose OpenDevice failed is accepted and ignored.

### Example
```asm
        move.l  4.w,a6
        move.l  timereq,a1
        jsr     _LVOCloseDevice(a6)
        move.l  timereq,a0
        jsr     _LVODeleteIORequest(a6)
```

### Gotchas
- Every request sent on this unit must be back first: [AbortIO](io.md#abortio) +
  [WaitIO](io.md#waitio) anything still pending, or the device may reply into freed memory.
- After closing, the request memory may be reused for another OpenDevice or freed.
- Pre-V36: only call it for requests that really opened.

**See also:** [OpenDevice](#opendevice), [DeleteIORequest](io.md#deleteiorequest), [AbortIO](io.md#abortio)

## OpenResource
`APTR OpenResource(CONST_STRPTR resName)` — LVO -498 (-$1F2)
Registers: resName=A1; result in D0

Look up a resource by name and return its base; there is no matching close.

- **resName** — exact name, e.g. `"ciaa.resource"` / `"ciab.resource"` (`CIAANAME`, `CIABNAME`
  in resources/cia.h), `"disk.resource"`, `"potgo.resource"`.
- **Result** — resource base, or 0 if no such resource is in `ResourceList`.

### Example
```asm
        include "lvo/exec_lib.i"
        include "lvo/cia_lib.i"

        move.l  4.w,a6
        lea     ciabname(pc),a1
        jsr     _LVOOpenResource(a6)
        move.l  d0,_CiabBase
        beq     .nocia
        move.l  d0,a6                   ; resource functions take A6 = resource base
        moveq   #0,d0                   ; mask 0 = only read
        jsr     _LVOAbleICR(a6)         ; D0 = current CIA-B interrupt enable mask
        move.l  4.w,a6
        ; ...
ciabname:
        dc.b    "ciab.resource",0
        even
```

### Gotchas
- Resources are never closed and never counted: nothing stops two programs using the same one.
  Use the resource's own allocation calls (cia AddICRVector, disk.resource AllocUnit,
  potgo.resource AllocPotBits, misc.resource AllocMiscResource).
- A resource's jump table need not start at -30: cia.resource functions begin at -6
  (`_LVOAddICRVector` = -6) because resources have no Open/Close/Expunge vectors.
- The two CIA resources share one function table layout, so the base in A6 selects the chip.

**See also:** [AddResource](#addresource), [RemResource](#remresource), [OpenLibrary](#openlibrary)

## SetFunction
`APTR SetFunction(struct Library *library, LONG funcOffset, ULONG (*CONST newFunction)())` — LVO -420 (-$1A4)
Registers: library=A1, funcOffset=A0, newFunction=D0; result in D0

Replace one jump-table vector of a library and return the previous function pointer.

- **library** — base of the library (or device) to patch.
- **funcOffset** — the LVO (negative, e.g. `_LVOOpenLibrary` = -552). Only the low word of
  A0 is used (`A0.W`).
- **newFunction** — address of your replacement; it is entered with the same registers the
  original would get (A6 = library base).
- **Result** — old function address. Save it to chain to the original and to undo the patch.

### Example
```asm
; count OpenLibrary calls, then continue into the original
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        jsr     _LVOForbid(a6)          ; nobody may call us before oldOpen is stored
        move.l  a6,a1                   ; library = exec itself
        move.l  #_LVOOpenLibrary,a0     ; offset (low word used)
        move.l  #MyOpenLibrary,d0
        jsr     _LVOSetFunction(a6)
        move.l  d0,oldOpen
        jsr     _LVOPermit(a6)
        ; ...

MyOpenLibrary:
        addq.l  #1,openCount
        move.l  oldOpen,-(sp)           ; jump to original, all registers intact
        rts

oldOpen:        dc.l    0
openCount:      dc.l    0
```
Undo: Forbid, `SetFunction(lib, offset, oldOpen)`, check that the returned pointer is
`MyOpenLibrary`, Permit.

### Gotchas
- Bracket install/remove with Forbid/Permit so the saved old pointer is valid before the
  first call arrives. If the function can be called from interrupts, you must arbitrate
  (Disable) yourself.
- Removal is only safe if the vector still points at *your* code: if someone patched after
  you, putting your old pointer back unhooks them. Then leave the patch (and its code)
  in memory.
- Exec keeps the library checksum valid and flushes the CPU instruction cache for you.
- Does not work on non-standard jump tables such as pre-V36 dos.library: there Forbid, save
  the 6 original bytes, write the new vector, [SumLibrary](#sumlibrary), Permit.
- Patch code must stay loaded for as long as the patch is installed.

**See also:** [SumLibrary](#sumlibrary), [MakeFunctions](#makefunctions), [CacheClearU](system.md#cacheclearu)

## SumLibrary
`VOID SumLibrary(struct Library *library)` — LVO -426 (-$1AA)
Registers: library=A1; no result

Recompute (or verify) the checksum over a library's jump table.

- **library** — base of the library to sum.

If the stored `lib_Sum` does not match and `LIBF_CHANGED` is not set in `lib_Flags`, exec
raises an Alert. Only libraries with `LIBF_SUMUSED` are summed.

### Gotchas
- Needed only after writing jump-table bytes by hand (the pre-V36 dos.library case);
  [SetFunction](#setfunction) and [AddLibrary](#addlibrary) already sum.
- A mismatch without `LIBF_CHANGED` halts the machine with an alert.

**See also:** [SetFunction](#setfunction), [AddLibrary](#addlibrary)

## MakeLibrary
`struct Library * MakeLibrary(CONST APTR funcInit, CONST APTR structInit, ULONG (*CONST libInit)(), ULONG dataSize, ULONG segList)` — LVO -84 (-$54)
Registers: funcInit=A0, structInit=A1, libInit=A2, dataSize=D0, segList=D1; result in D0

Allocate and build a library or device base: jump table, initialised data and init call.

- **funcInit** — vector list: absolute function pointers terminated by a -1 longword; or a
  -1 word followed by word displacements (relative to funcInit) terminated by a -1 word.
  Order: Open, Close, Expunge, Reserved (must return 0), then your functions (-30, -36, ...).
- **structInit** — [InitStruct](#initstruct) table used to fill the base, or NULL.
- **libInit** — optional routine called before return with D0 = library base,
  A0 = segList, A6 = ExecBase; must return the base in D0, or 0 after freeing the memory
  itself (size from `lib_NegSize` + `lib_PosSize`).
- **dataSize** — size of the positive part, at least `sizeof(struct Library)` (`LIB_SIZE`).
- **segList** — DOS segment list of the loaded code (passed on to libInit), or 0 for ROM/RAM code.
- **Result** — the library base (the address between jump table and data, not the start of
  the allocation), or 0 if out of memory.

### Example
```asm
        include "exec/types.i"
        include "exec/nodes.i"
        include "exec/libraries.i"
        include "exec/initializers.i"
        include "lvo/exec_lib.i"

        move.l  4.w,a6
        lea     vectors(pc),a0
        lea     inittab(pc),a1
        suba.l  a2,a2                   ; no init routine
        moveq   #LIB_SIZE,d0            ; no private data
        moveq   #0,d1                   ; no segList
        jsr     _LVOMakeLibrary(a6)
        tst.l   d0
        beq     .nomem
        move.l  d0,a1
        jsr     _LVOAddLibrary(a6)      ; now OpenLibrary("my.library") finds it
        ; ...

vectors:
        dc.l    LibOpen,LibClose,LibExpunge,LibNull
        dc.l    MyFunc                  ; LVO -30
        dc.l    -1
inittab:
        INITBYTE LN_TYPE,NT_LIBRARY
        INITLONG LN_NAME,libname
        INITBYTE LIB_FLAGS,LIBF_SUMUSED!LIBF_CHANGED
        INITWORD LIB_VERSION,1
        INITWORD LIB_REVISION,0
        dc.w    0                       ; end of table

LibOpen:                                ; A6 = library base
        addq.w  #1,LIB_OPENCNT(a6)
        move.l  a6,d0
        rts
LibClose:
        subq.w  #1,LIB_OPENCNT(a6)
        moveq   #0,d0
        rts
LibExpunge:                             ; refuse to unload
LibNull:
        moveq   #0,d0
        rts
MyFunc:
        moveq   #42,d0
        rts

libname:
        dc.b    "my.library",0
        even
```

### Gotchas
- From V36 the base is longword aligned and `lib_PosSize`/`lib_NegSize` reflect that.
- The instruction cache is flushed after the table is built.
- MakeLibrary does not add the library to the system: call [AddLibrary](#addlibrary) /
  [AddDevice](#adddevice) (or use a ROMTag with `RTF_AUTOINIT`, see [InitResident](#initresident)).

**See also:** [InitStruct](#initstruct), [MakeFunctions](#makefunctions), [AddLibrary](#addlibrary), [InitResident](#initresident)

## MakeFunctions
`VOID MakeFunctions(APTR target, CONST APTR functionArray, CONST APTR funcDispBase)` — LVO -90 (-$5A)
Registers: target=A0, functionArray=A1, funcDispBase=A2; no result

Build a jump table of 6-byte vectors below a given address.

- **target** — address the table ends at (normally the library base); vectors are written at
  target-6, target-12, ...
- **functionArray** — function pointers terminated by -1 (longword) when funcDispBase is 0,
  otherwise signed word displacements terminated by a -1 word.
- **funcDispBase** — base the word displacements are relative to, or 0 for absolute pointers.

Used internally by [MakeLibrary](#makelibrary); call it yourself to build or rebuild a table in
memory you allocated. The instruction cache is flushed afterwards.

### Gotchas
- The autodoc documents a result in D0 (table size in bytes, for `lib_NegSize`), but the NDK
  prototype is VOID: read D0 directly in asm if you need it.
- Does not update the library checksum: [SumLibrary](#sumlibrary) if the library is live.

**See also:** [MakeLibrary](#makelibrary), [SetFunction](#setfunction)

## InitStruct
`VOID InitStruct(CONST APTR initTable, APTR memory, ULONG size)` — LVO -78 (-$4E)
Registers: initTable=A1, memory=A2, size=D0; no result

Clear a memory block and fill it from a compact byte-coded initialisation table.

- **initTable** — command stream; build it with the `INITBYTE`, `INITWORD`, `INITLONG` and
  `INITSTRUCT` macros from exec/initializers.i. Ends with a zero command byte (`dc.w 0`).
  Must be at an even address unless only byte data is used.
- **memory** — block to initialise; even address if size is non-zero.
- **size** — bytes to clear first (must be even); 0 = do not clear.

Each command byte is `ddssnnnn`: `dd` = destination (00 next, 01 next repeated, 10 byte
offset follows, 11 24-bit offset follows), `ss` = source size (00 long, 01 word, 10 byte,
11 illegal -> alert), `nnnn` = count-1 or repeat-1. Offsets are relative to memory.

### Example
```asm
        include "exec/initializers.i"

        move.l  4.w,a6
        lea     mytab(pc),a1
        lea     mystruct,a2
        moveq   #20,d0                  ; clear 20 bytes first
        jsr     _LVOInitStruct(a6)

mytab:
        INITWORD 4,$1234                ; UWORD at offset 4
        INITLONG 6,$DEADBEEF            ; ULONG at offset 6
        INITBYTE 10,$7F                 ; UBYTE at offset 10
        dc.w    0
```

### Gotchas
- Command `%00000000` ends the table: to copy one long without an offset use `%00010001`.
- 24-bit absolute pointers in the data are not supported; use longs.

**See also:** [MakeLibrary](#makelibrary), [InitResident](#initresident)

## AddLibrary
`VOID AddLibrary(struct Library *library)` — LVO -396 (-$18C)
Registers: library=A1; no result

Link a ready library into the system library list so OpenLibrary can find it.

- **library** — fully initialised base (usually from [MakeLibrary](#makelibrary)); `LN_NAME` set,
  `LN_TYPE` = `NT_LIBRARY`.

The library is enqueued on `SysBase->LibList` and its jump table checksummed. It must accept
Open calls immediately.

**See also:** [RemLibrary](#remlibrary), [MakeLibrary](#makelibrary), [OpenLibrary](#openlibrary)

## RemLibrary
`VOID RemLibrary(struct Library *library)` — LVO -402 (-$192)
Registers: library=A1; no result

Ask a library to expunge itself by calling its Expunge vector.

- **library** — base of the library to flush.

The library decides: an open or busy library normally refuses (and may set `LIBF_DELEXP` to
expunge on its last close). Applications rarely need this.

### Example
```c
#include <proto/exec.h>
#include <exec/execbase.h>

/* try to flush an unused disk library from RAM */
void FlushLib(CONST_STRPTR name)
{
    struct Library *lib;

    Forbid();
    lib = (struct Library *)FindName(&SysBase->LibList, name);
    if (lib)
        RemLibrary(lib);
    Permit();
}
```

### Gotchas
- Walk `LibList` and call it under Forbid so the node cannot vanish in between.
- Never RemLibrary a library you still have open.

**See also:** [AddLibrary](#addlibrary), [CloseLibrary](#closelibrary), [FindName](lists.md#findname)

## AddDevice
`VOID AddDevice(struct Device *device)` — LVO -432 (-$1B0)
Registers: device=A1; no result

Link a ready device into the system device list so OpenDevice can find it.

- **device** — fully initialised device base (a `struct Library` with `NT_DEVICE`), usually
  built with [MakeLibrary](#makelibrary) whose vectors include BeginIO (-30) and AbortIO (-36).

**See also:** [RemDevice](#remdevice), [OpenDevice](#opendevice), [MakeLibrary](#makelibrary)

## RemDevice
`VOID RemDevice(struct Device *device)` — LVO -438 (-$1B6)
Registers: device=A1; no result

Ask a device to expunge itself by calling its Expunge vector.

- **device** — base of the device to flush (find it in `SysBase->DeviceList` with
  [FindName](lists.md#findname) under Forbid).

The device may refuse while it is open or busy; not normally used by applications.

**See also:** [AddDevice](#adddevice), [RemLibrary](#remlibrary), [CloseDevice](#closedevice)

## AddResource
`VOID AddResource(APTR resource)` — LVO -486 (-$1E6)
Registers: resource=A1; no result

Link a resource into the system resource list so OpenResource can find it.

- **resource** — structure that begins with a named Node (`LN_SIZE`) and should begin with a
  full `struct Library` (`LIB_SIZE`); must be usable immediately.

**See also:** [RemResource](#remresource), [OpenResource](#openresource)

## RemResource
`VOID RemResource(APTR resource)` — LVO -492 (-$1EC)
Registers: resource=A1; no result

Unlink a resource from the system resource list.

- **resource** — resource node previously added.

### Gotchas
- There is no open count for resources: make sure no one can still be using it.

**See also:** [AddResource](#addresource)

## FindResident
`struct Resident * FindResident(CONST_STRPTR name)` — LVO -96 (-$60)
Registers: name=A1; result in D0

Find a resident module (ROMTag) by name in exec's module array.

- **name** — module name, e.g. `"graphics.library"`.
- **Result** — `struct Resident *`, or 0 if no such module.

Useful to learn what the ROM (or KickTag list) contains without opening anything: `rt_Version`
(UBYTE), `rt_Type` (`NT_LIBRARY`, `NT_DEVICE`, `NT_RESOURCE`...), `rt_IdString`.

### Example
```c
#include <proto/exec.h>
#include <exec/resident.h>

struct Resident *rt = FindResident((CONST_STRPTR)"graphics.library");
UBYTE romGfxVersion = rt ? rt->rt_Version : 0;
```

**See also:** [InitResident](#initresident), [InitCode](#initcode), [SumKickData](#sumkickdata)

## InitResident
`APTR InitResident(CONST struct Resident *resident, ULONG segList)` — LVO -102 (-$66)
Registers: resident=A1, segList=D1; result in D0

Initialise one ROMTag, including RTF_AUTOINIT library/device/resource creation.

- **resident** — pointer to a `struct Resident` (`rt_MatchWord` = `RTC_MATCHWORD` $4AFC,
  `rt_MatchTag` pointing to itself).
- **segList** — segment list of disk-loaded code (the library keeps it for expunge), or 0 for
  ROM modules.
- **Result** — whatever the init code returned (normally the new base), or 0 on failure.

Without `RTF_AUTOINIT` exec jumps to `rt_Init` with D0 = 0, A0 = segList, A6 = ExecBase.
With `RTF_AUTOINIT` (`rt_Flags` bit 7) `rt_Init` points to four longs used for
[MakeLibrary](#makelibrary): base data size, vector table, InitStruct table, init routine (or 0).
The init routine gets D0 = base, A0 = segList, A6 = ExecBase and returns the base, or frees
the base memory and returns 0.

### Example
```asm
        include "exec/resident.i"
        include "exec/nodes.i"

start:
        moveq   #-1,d0                  ; run from the Shell: fail harmlessly
        rts

romtag:
        dc.w    RTC_MATCHWORD           ; $4AFC
        dc.l    romtag                  ; rt_MatchTag
        dc.l    endcode                 ; rt_EndSkip
        dc.b    RTF_AUTOINIT            ; rt_Flags
        dc.b    1                       ; rt_Version
        dc.b    NT_LIBRARY              ; rt_Type
        dc.b    0                       ; rt_Pri
        dc.l    libname                 ; rt_Name
        dc.l    idstring                ; rt_IdString
        dc.l    autoinit                ; rt_Init
autoinit:                               ; vectors/inittab as in MakeLibrary
        dc.l    LIB_SIZE,vectors,inittab,0
```

### Gotchas
- A disk library or device must carry its ROMTag in the first code hunk; the file should start
  with `moveq #-1,d0` / `rts` so running it does nothing.
- Keep `rt_Version` equal to the library's `lib_Version` (V36 may refuse a mismatch).

**See also:** [FindResident](#findresident), [MakeLibrary](#makelibrary), [InitCode](#initcode)

## InitCode
`VOID InitCode(ULONG startClass, ULONG version)` — LVO -72 (-$48)
Registers: startClass=D0, version=D1; no result

Internal: initialise every resident module of one start class (boot-time use only).

- **startClass** — `RTF_COLDSTART` (bit 0), `RTF_SINGLETASK` (bit 1, V36), `RTF_AFTERDOS`
  (bit 2, V36).
- **version** — minimum module version to initialise.

Calls [InitResident](#initresident) with segList 0 for each matching module in `ResModules`, in
priority order. Applications have no use for it.

**See also:** [InitResident](#initresident), [FindResident](#findresident)

## SumKickData
`ULONG SumKickData(VOID)` — LVO -612 (-$264)
Registers: none; result in D0

Compute the checksum that validates ExecBase's KickMemPtr/KickTagPtr module lists.

- **Result** — value to store in `SysBase->KickCheckSum`.

Exec checks three ExecBase fields at every reset: `KickMemPtr` (`$222`, chain of MemLists to
AllocAbs), `KickTagPtr` (`$226`, ROMTag pointer array; an entry with bit 31 set links to the
next array after clearing that bit) and `KickCheckSum` (`$22A`). A wrong sum makes exec ignore
both lists; a failed AllocAbs makes it ignore the tags.

### Gotchas
- Heavy magic that survives warm resets. ROMTags, MemLists and arrays must live in chip RAM or
  $C00000-$D80000 memory, because expansion RAM is not configured yet at that point.
- After writing `KickCheckSum` call [CacheClearU](system.md#cacheclearu) so copyback caches
  push the write to memory.
- Changing existing ROM modules this way is extremely easy to get wrong.

**See also:** [FindResident](#findresident), [InitResident](#initresident), [AllocAbs](memory.md#allocabs), [CacheClearU](system.md#cacheclearu)
