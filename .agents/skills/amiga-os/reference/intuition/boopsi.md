# intuition.library: BOOPSI objects and classes

BOOPSI (V36+) is Intuition's object system. Create an object from a public class (named by an ID
string such as `"propgclass"`) or from a private class (by `struct IClass *`) with NewObjectA.
Change it with SetAttrsA, or with SetGadgetAttrsA once it is in a window. Read it with GetAttr and
free it with DisposeObject. A gadget object is a `struct Gadget` and does nothing until AddGList
puts it in a window; remove it before you dispose of it. Objects talk to each other through
`ICA_TARGET` (target object, or `ICTARGET_IDCMP` for `IDCMP_IDCMPUPDATE` messages to the window)
and `ICA_MAP` (a tag list that renames attributes). Only class implementors need MakeClass,
AddClass, RemoveClass, FreeClass, NextObject, ObtainGIRPort, ReleaseGIRPort and GadgetMouse.

Built-in public classes (C macros in `intuition/classusr.h`, strings are the real IDs):
`ROOTCLASS` "rootclass", `IMAGECLASS` "imageclass", `FRAMEICLASS` "frameiclass", `SYSICLASS`
"sysiclass", `FILLRECTCLASS` "fillrectclass", `ITEXTICLASS` "itexticlass", `GADGETCLASS`
"gadgetclass", `PROPGCLASS` "propgclass", `STRGCLASS` "strgclass", `BUTTONGCLASS`
"buttongclass", `FRBUTTONCLASS` "frbuttonclass", `GROUPGCLASS` "groupgclass", `ICCLASS`
"icclass", `MODELCLASS` "modelclass", `POINTERCLASS` "pointerclass".
Methods (`classusr.h`): `OM_NEW` 0x101, `OM_DISPOSE` 0x102, `OM_SET` 0x103, `OM_GET` 0x104,
`OM_ADDTAIL` 0x105, `OM_REMOVE` 0x106, `OM_NOTIFY` 0x107, `OM_UPDATE` 0x108, `OM_ADDMEMBER`
0x109, `OM_REMMEMBER` 0x10A. Gadget methods `GM_HITTEST` 0 to `GM_KEYGOINACTIVE` 10 are in
`gadgetclass.h`, image methods `IM_DRAW` 0x202 and up in `imageclass.h`.

## NewObjectA
`APTR NewObjectA(struct IClass *classPtr, CONST_STRPTR classID, CONST struct TagItem *tagList)` — LVO -636 (-$27C)
Registers: classPtr=A0, classID=A1, tagList=A2; result in D0

Create a BOOPSI object from a class pointer or a public class ID, with initial attributes.

- **classPtr** — private class from MakeClass, or `NULL` to look the class up by classID.
- **classID** — public class name (`"propgclass"`, `BUTTONGCLASS`, ...). Only used when classPtr
  is `NULL`.
- **tagList** — create-time attributes, terminated by `TAG_DONE`. Each class documents which
  tags it accepts, which are required and which are create-time only.
- **Result** — the object (an APTR handle; for gadget classes it is a `struct Gadget *`), or
  `NULL` on failure. Free it with DisposeObject.

Varargs form `NewObject(classPtr, classID, Tag1, ...)`: a stub in amiga.lib, and an inline macro
in the Bartman `inline/intuition.h`. The macro packs every value as a ULONG, so cast pointer data
with `(ULONG)`. The call sends `OM_NEW` to the class.

Since V36.

### Example
```c
#include <proto/intuition.h>
#include <proto/utility.h>
#include <intuition/gadgetclass.h>
#include <intuition/icclass.h>

/* vertical scroller; window opened with IDCMP_IDCMPUPDATE in its IDCMP flags */
struct Gadget *prop = (struct Gadget *)NewObject(NULL, (CONST_STRPTR)PROPGCLASS,
    GA_ID,       1,
    GA_Left,     win->BorderLeft + 4,
    GA_Top,      win->BorderTop + 4,
    GA_Width,    16,
    GA_Height,   100,
    PGA_Freedom, FREEVERT,
    PGA_NewLook, TRUE,
    PGA_Total,   total,
    PGA_Visible, visible,
    PGA_Top,     0,
    ICA_TARGET,  ICTARGET_IDCMP,       /* report changes as IDCMP_IDCMPUPDATE */
    TAG_DONE);
if (prop) {
    AddGList(win, prop, (UWORD)~0, 1, NULL);
    RefreshGList(prop, win, NULL, 1);
}
/* in the IDCMP loop, before ReplyMsg():
   case IDCMP_IDCMPUPDATE:
       top = GetTagData(PGA_Top, top, (struct TagItem *)imsg->IAddress); */
/* cleanup, window still open: */
RemoveGList(win, prop, 1);
DisposeObject(prop);
```

### Gotchas
- A gadget object must be added with AddGList, and removed with RemoveGList before
  DisposeObject. You cannot link it into an open window with `GA_Previous`; that tag only chains
  gadgets at creation time.
- The `IAddress` tag list of an `IDCMP_IDCMPUPDATE` message belongs to Intuition. Read it before
  ReplyMsg.
- Which attributes a gadget broadcasts (here `PGA_Top`) is class-specific; the propgclass
  behaviour shown is not covered by the local headers (unverified).
- The `Object` and `Class` typedefs are used inconsistently in the headers. Treat object handles
  as APTR and class IDs as `UBYTE *`.

**See also:** [DisposeObject](#disposeobject), [SetAttrsA](#setattrsa), [GetAttr](#getattr),
[MakeClass](#makeclass), [SetGadgetAttrsA](gadgets.md#setgadgetattrsa),
[AddGList](gadgets.md#addglist)

## DisposeObject
`VOID DisposeObject(APTR object)` — LVO -642 (-$282)
Registers: object=A0; no result

Delete a BOOPSI object and its auxiliary data by sending it `OM_DISPOSE`.

- **object** — object from NewObjectA. `NULL` is allowed and does nothing.

Some classes own other objects and dispose of them too (check each class's documentation, so you
do not free the same object twice).

Since V36.

### Gotchas
- Remove gadget objects from their window (RemoveGList) first. Freeing an attached gadget leaves a
  dangling pointer in `win->FirstGadget`.
- After disposing of an object, do not keep it as the `ICA_TARGET` of another object.

**See also:** [NewObjectA](#newobjecta), [RemoveGList](gadgets.md#removeglist)

## SetAttrsA
`ULONG SetAttrsA(APTR object, CONST struct TagItem *tagList)` — LVO -648 (-$288)
Registers: object=A0, tagList=A1; result in D0

Set attributes of a BOOPSI object with no window context (`OM_SET`, `NULL` GadgetInfo).

- **object** — any BOOPSI object.
- **tagList** — attribute/value pairs, `TAG_DONE` terminated.
- **Result** — class-defined. For gadgets, usually non-zero if the imagery needs a redraw.

Varargs form `SetAttrs(object, Tag1, ...)` (amiga.lib stub, inline macro in the Bartman headers;
cast pointers to ULONG).

Since V36.

### Gotchas
- For a gadget already in a window or requester, use SetGadgetAttrsA. SetAttrsA gives it no
  GadgetInfo and no arbitration with the input task.
- If you use it on a gadget before adding it, and the result is non-zero, call RefreshGList after
  AddGList.

**See also:** [SetGadgetAttrsA](gadgets.md#setgadgetattrsa), [GetAttr](#getattr),
[NewObjectA](#newobjecta)

## GetAttr
`ULONG GetAttr(ULONG attrID, APTR object, ULONG *storagePtr)` — LVO -654 (-$28E)
Registers: attrID=D0, object=A0, storagePtr=A1; result in D0

Read one attribute of a BOOPSI object into a longword you supply (`OM_GET`).

- **attrID** — attribute tag, for example `PGA_Top`, `STRINGA_LongVal`, `GA_Disabled`.
- **object** — the object.
- **storagePtr** — address of a ULONG that receives the value (the same form as `ti_Data` for
  SetAttrs). Some classes return other types; check the class documentation.
- **Result** — 0 (FALSE) if the class does not support getting this attribute. Otherwise
  non-zero, and the value is in `*storagePtr`.

Since V36.

### Example
```c
ULONG top;
if (GetAttr(PGA_Top, (APTR)prop, &top)) {
    /* top is valid */
}
```

### Gotchas
- The argument order is attribute, object, storage (D0, A0, A1). It is easy to swap attrID and
  object.
- The value comes back through storagePtr, not the result. Many attributes cannot be read at all.

**See also:** [SetAttrsA](#setattrsa), [NewObjectA](#newobjecta)

## NextObject
`APTR NextObject(APTR objectPtrPtr)` — LVO -666 (-$29A)
Registers: objectPtrPtr=A0; result in D0

Walk the objects gathered on an Exec list with `OM_ADDMEMBER` (class implementors only).

- **objectPtrPtr** — address of an APTR you first set to the list's `lh_Head` (or `mlh_Head`).
  Pass the same address on every call.
- **Result** — next object, or `NULL` at the end. It is safe to remove and dispose of the returned
  object before the next call.

Since V36.

### Example
```c
/* OM_DISPOSE in a group-like class: dispose every member */
APTR state = data->members.mlh_Head;
Object *member;
while ((member = NextObject(&state))) {
    DoMethod(member, OM_REMOVE);        /* amiga.lib */
    DisposeObject(member);
}
```

**See also:** [DisposeObject](#disposeobject), [MakeClass](#makeclass)

## MakeClass
`struct IClass * MakeClass(CONST_STRPTR classID, CONST_STRPTR superClassID, CONST struct IClass *superClassPtr, ULONG instanceSize, ULONG flags)` — LVO -678 (-$2A6)
Registers: classID=A0, superClassID=A1, superClassPtr=A2, instanceSize=D0, flags=D1; result in D0

Create a public or private BOOPSI class (class implementors only).

- **classID** — `NULL` for a private class, or the public name. Public names must be unique and
  should be registered.
- **superClassID** — superclass name (for example `"gadgetclass"`), or `NULL` if the superclass
  is private.
- **superClassPtr** — private superclass pointer. Only used when superClassID is `NULL`. There
  must always be a superclass.
- **instanceSize** — bytes of per-object data this class adds on top of its superclass.
- **flags** — reserved, pass 0.
- **Result** — `struct IClass *`, or `NULL` (no memory, public superclass not found, or public
  name already in use).

After it succeeds: set `cl->cl_Dispatcher.h_Entry` (and `h_SubEntry`/`h_Data` if you use them),
set `cl_UserData` if needed, then call AddClass for a public class. The hook is called with
A0 = class (the hook is the first member of `struct IClass`), A2 = object (the true class for
`OM_NEW`) and A1 = message; the result goes in D0. Instance data is at
`INST_DATA(cl, obj)` = obj + `cl_InstOffset`.

Since V36.

### Example
```asm
        include "exec/types.i"
        include "utility/hooks.i"
        include "intuition/classes.i"
        include "intuition/classusr.i"
        include "lvo/intuition_lib.i"

MYDATA_SIZE equ 4

        move.l  IntuitionBase,a6
        sub.l   a0,a0                   ; private class
        lea     supername(pc),a1
        sub.l   a2,a2
        moveq   #MYDATA_SIZE,d0
        moveq   #0,d1
        jsr     _LVOMakeClass(a6)
        move.l  d0,myclass
        beq     .fail
        move.l  d0,a0
        lea     dispatch(pc),a1
        move.l  a1,h_Entry(a0)          ; cl_Dispatcher is at offset 0
        ; ... NewObjectA(myclass,...) as usual; FreeClass(myclass) on exit

; A0 = class, A2 = object, A1 = msg; D0 = result
dispatch:
        cmp.l   #OM_NEW,msg_MethodID(a1)
        bne.s   super                   ; everything else: superclass
        move.l  a0,-(sp)
        bsr.s   super                   ; D0 = new object or 0
        move.l  (sp)+,a0
        tst.l   d0
        beq.s   .done
        move.l  d0,a1
        moveq   #0,d1
        move.w  cl_InstOffset(a0),d1
        clr.l   0(a1,d1.l)              ; init our instance data
.done:  rts
super:  move.l  cl_Super(a0),a0         ; same as amiga.lib DoSuperMethodA
        move.l  h_Entry(a0),-(sp)
        rts

supername:
        dc.b    "gadgetclass",0
        even
```

### Gotchas
- amiga.lib provides `HookEntry` (register-to-C stub) and `DoSuperMethodA`/`DoMethodA`, with
  prototypes in `clib/alib_protos.h`. The NDK's amiga.lib is a hunk-format library, and the
  Bartman ELF toolchain ships no linkable copy (unverified). In C there you need your own register
  stub, and you do the superclass call as shown above.
- A dispatcher runs on the caller's task. For gadgets that is often the input.device task, so no
  DOS calls and nothing that blocks.
- Free a class with FreeClass, not FreeMem.

**See also:** [FreeClass](#freeclass), [AddClass](#addclass), [RemoveClass](#removeclass),
[NewObjectA](#newobjecta)

## AddClass
`VOID AddClass(struct IClass *classPtr)` — LVO -684 (-$2AC)
Registers: classPtr=A0; no result

Make a class created with a public name visible to NewObjectA by ID.

- **classPtr** — class from MakeClass, fully initialized (dispatcher set).

Since V36.

### Gotchas
- Call it only after the class is completely set up, because other tasks can use it at once.
- There is no real duplicate-name checking, so use only registered names.

**See also:** [MakeClass](#makeclass), [RemoveClass](#removeclass), [FreeClass](#freeclass)

## RemoveClass
`VOID RemoveClass(struct IClass *classPtr)` — LVO -708 (-$2C4)
Registers: classPtr=A0; no result

Take a public class off the public class list so that new objects cannot find it by name.

- **classPtr** — public class from MakeClass. `NULL`, or a class not in the list (or already
  removed), is harmless.

Existing objects of the class are not affected. Use FreeClass to actually free it.

Since V36.

**See also:** [AddClass](#addclass), [FreeClass](#freeclass)

## FreeClass
`BOOL FreeClass(struct IClass *classPtr)` — LVO -714 (-$2CA)
Registers: classPtr=A0; result in D0

Try to free a class made by MakeClass (class implementors only).

- **classPtr** — class to free.
- **Result** — TRUE if freed. FALSE if objects or subclasses still exist (`cl_ObjectCount` or
  `cl_SubclassCount` non-zero).

Since V36.

### Gotchas
- A public class is always removed from the public list (RemoveClass), even when the result is
  FALSE.
- On FALSE, keep the dispatcher code loaded (a class library must refuse to expunge).
- Free the data behind `cl_UserData` only after FreeClass returns TRUE.

**See also:** [MakeClass](#makeclass), [RemoveClass](#removeclass)

## ObtainGIRPort
`struct RastPort * ObtainGIRPort(struct GadgetInfo *gInfo)` — LVO -558 (-$22E)
Registers: gInfo=A0; result in D0

Get a RastPort for rendering from inside a custom gadget method (class implementors only).

- **gInfo** — the `struct GadgetInfo *` passed in the method message (for example `gpi_GInfo`,
  `ops_GInfo`).
- **Result** — RastPort to draw into, or `NULL` (then draw nothing). Always pair it with
  ReleaseGIRPort, which also accepts `NULL`.

Since V36.

### Gotchas
- Obtain and release it within the same method call. Never keep it between calls.
- `GM_RENDER` already passes a ready RastPort in `gpr_RPort`, so do not call this there.
- A `NULL` gInfo (for example `OM_SET` from SetAttrsA) means there is no window context and
  nothing to draw into.

**See also:** [ReleaseGIRPort](#releasegirport), [SetGadgetAttrsA](gadgets.md#setgadgetattrsa)

## ReleaseGIRPort
`VOID ReleaseGIRPort(struct RastPort *rp)` — LVO -564 (-$234)
Registers: rp=A0; no result

Release a RastPort obtained with ObtainGIRPort.

- **rp** — RastPort returned by ObtainGIRPort. `NULL` does nothing.

Since V36.

**See also:** [ObtainGIRPort](#obtaingirport)

## GadgetMouse
`VOID GadgetMouse(struct Gadget *gadget, struct GadgetInfo *gInfo, WORD *mousePoint)` — LVO -570 (-$23A)
Registers: gadget=A0, gInfo=A1, mousePoint=A2; no result

Obsolete: compute the mouse position relative to a custom gadget's top-left corner.

- **gadget** — the custom gadget.
- **gInfo** — GadgetInfo passed to the gadget method.
- **mousePoint** — address of two WORDs (a `struct Point`), filled with X and Y. The result
  accounts for `GFLG_RELRIGHT`/`GFLG_RELBOTTOM`.

Since V36.

### Gotchas
- Do not use it. `GM_GOACTIVE` and `GM_HANDLEINPUT` already carry the gadget-relative mouse
  position in `gpi_Mouse`, and `GM_HITTEST` carries it in `gpht_Mouse`.

**See also:** [ObtainGIRPort](#obtaingirport)
