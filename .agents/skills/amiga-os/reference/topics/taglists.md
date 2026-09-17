# Tag lists

From V36 on, most OS calls that need many optional parameters take a *tag list*: an array
of (tag, data) longword pairs ended by `TAG_DONE`. They are used by OpenWindowTagList,
OpenScreenTagList, BestModeIDA, CreateNewProc, SystemTagList, AllocDosObject, BOOPSI and
AHI. None of these exist on 1.3 (V34) or earlier.

## TagItem

`#include <utility/tagitem.h>` / `include "utility/tagitem.i"`

| Off | asm | C | Type | Meaning |
|---|---|---|---|---|
| $00 | `ti_Tag` | `ti_Tag` | `Tag` (ULONG) | what the item is |
| $04 | `ti_Data` | `ti_Data` | `ULONG` | value. Pointers, BOOLs and small ints all go in as ULONG |
| $08 | `ti_SIZEOF` | `sizeof(struct TagItem)` = 8 | | |

System control tags (bit 31 clear, values 0-3):

| Tag | Value | Meaning |
|---|---|---|
| `TAG_DONE` | 0 | end of the array (`ti_Data` unused) |
| `TAG_END` | 0 | synonym for `TAG_DONE` |
| `TAG_IGNORE` | 1 | skip this one item |
| `TAG_MORE` | 2 | `ti_Data` points to another tag array. The current array ends here |
| `TAG_SKIP` | 3 | skip this item and the next `ti_Data` items |

`TAG_USER` = `$80000000`. Every application or library tag has bit 31 set. Libraries build
their tags from a base, e.g. `WA_Dummy` = `TAG_USER + 99`, `WA_Left` = `WA_Dummy + 1`
(intuition/intuition.h), and `SA_Dummy` = `TAG_USER + 32` (intuition/screens.h). Pick your own
private tags from `TAG_USER` + some offset, never from 0-3.

## Naming convention

Only one form of each call has an LVO: the one taking a `struct TagItem *`. The other form is
a varargs stub that builds the array on the stack and calls it.

| Real function (pointer to array) | Varargs stub | Pattern |
|---|---|---|
| `OpenWindowTagList(nw, tags)` | `OpenWindowTags(nw, tag1, ...)` | `...TagList` / `...Tags` |
| `OpenScreenTagList(ns, tags)` | `OpenScreenTags(ns, tag1, ...)` | |
| `SystemTagList(cmd, tags)` = `System` | `SystemTags(cmd, tag1, ...)` | alias shares the LVO |
| `CreateNewProcTagList(tags)` = `CreateNewProc` | `CreateNewProcTags(tag1, ...)` | alias |
| `AllocDosObjectTagList(type, tags)` = `AllocDosObject` | `AllocDosObjectTags(type, tag1, ...)` | alias |
| `VideoControl(cm, tags)` | `VideoControlTags(cm, tag1, ...)` | irregular: no suffix on the real one |
| `BestModeIDA(tags)` | `BestModeID(tag1, ...)` | `...A` / plain name |
| `ObtainBestPenA(cm, r, g, b, tags)` | `ObtainBestPen(cm, r, g, b, tag1, ...)` | |
| `NewObjectA(cl, id, tags)` | `NewObject(cl, id, tag1, ...)` | |

Rules of thumb:
- **asm**: always call the `TagList`/`A`/alias function (`jsr _LVOOpenWindowTagList(a6)`).
  The stubs have no `_LVO` symbol.
- **C with Bartman's GCC**: both forms work. The stub is an inline macro in `inline/*.h` that
  declares a local `ULONG` array (unless `NO_INLINE_STDARG` is defined). amiga.lib, which
  holds the classic stubs, is not linked in `-nostdlib` builds and isn't needed for this.
- `...Args` (EasyRequestArgs, RawDoFmt data streams) is a different convention: a packed
  argument array, not TagItems.

## Building tag lists in asm

Static list: `dc.l` pairs. Everything is a longword, including BOOLs and small numbers.

```asm
        include "exec/types.i"
        include "utility/tagitem.i"
        include "intuition/intuition.i"
        include "lvo/intuition_lib.i"

        move.l  _IntuitionBase,a6
        sub.l   a0,a0                   ; no NewWindow
        lea     wintags(pc),a1
        jsr     _LVOOpenWindowTagList(a6)
        move.l  d0,_window
        beq     .nowindow
        ...

wintags:
        dc.l    WA_Width,320
        dc.l    WA_Height,200
        dc.l    WA_Title,wintitle       ; pointer as ti_Data
        dc.l    WA_Activate,1           ; BOOL is still a long
        dc.l    TAG_DONE
wintitle:
        dc.b    "Demo",0
        even
```

Dynamic list on the stack: push the pairs in reverse, point A1 at SP, and pop afterwards.

```asm
        ; d2 = width, d3 = height (both preserved across the call)
        clr.l   -(sp)                   ; TAG_DONE
        move.l  d3,-(sp)
        move.l  #WA_Height,-(sp)
        move.l  d2,-(sp)
        move.l  #WA_Width,-(sp)
        move.l  sp,a1                   ; a1 -> tag array
        sub.l   a0,a0
        move.l  _IntuitionBase,a6
        jsr     _LVOOpenWindowTagList(a6)
        lea     5*4(sp),sp              ; drop the array (lea keeps the flags alone)
        tst.l   d0
        beq     .nowindow
```

To switch an item off at run time, overwrite its tag with `TAG_IGNORE`. To append a
caller-supplied list, end yours with `dc.l TAG_MORE,othertags`.

## Building tag lists in C

```c
#include <proto/intuition.h>
#include <intuition/intuition.h>
#include <utility/tagitem.h>

static const char title[] = "Demo";

/* 1. varargs stub: every pointer needs an explicit (ULONG) cast */
struct Window *w = OpenWindowTags(NULL,
    WA_Width,    320,
    WA_Height,   200,
    WA_Title,    (ULONG)title,
    WA_Activate, TRUE,
    TAG_DONE);

/* 2. explicit array, with a slot patched at run time and a chained extension */
static struct TagItem extra[] = {
    { WA_CloseGadget, TRUE },
    { TAG_DONE,       0 }
};
static struct TagItem tags[] = {
    { WA_Width,   320 },
    { WA_Height,  200 },
    { TAG_IGNORE, 0 },                  /* becomes WA_Title below if we have one */
    { TAG_MORE,   (ULONG)extra }        /* TAG_MORE ends this array */
};

struct Window *OpenIt(const char *maybeTitle)
{
    if (maybeTitle) {
        tags[2].ti_Tag  = WA_Title;
        tags[2].ti_Data = (ULONG)maybeTitle;
    }
    return OpenWindowTagList(NULL, tags);   /* check for NULL! */
}
```

Conditional items in a varargs call: `cond ? WA_Title : TAG_IGNORE, (ULONG)title`.

## Reading tag lists (utility.library)

If your own function or hook accepts tags, parse them with utility.library (V36+, open
`"utility.library"`, base `UtilityBase`). Don't walk the array with `ti++`: that breaks on
`TAG_MORE`, `TAG_IGNORE` and `TAG_SKIP`.

- FindTagItem, GetTagData -- look up one tag, with a default.
- NextTagItem -- iterate, honouring the control tags.
- PackBoolTags -- turn boolean tags into a flag word.
- FilterTagItems, FilterTagChanges, MapTags, TagInArray -- filter and remap.
- AllocateTagItems, CloneTagItems, FreeTagItems, RefreshTagItemClones -- copies.
- ApplyTagChanges, PackStructureTags, UnpackStructureTags -- V39.

(All V36 unless marked. See the utility autodocs.)

Bartman GCC 15 gotcha: the `inline/utility.h` NextTagItem macro fails to compile
(`-Wincompatible-pointer-types`: `volatile struct TagItem **`). Either add
`-Wno-error=incompatible-pointer-types` for that file, or use a small walker with the same
semantics:

```c
#include <utility/tagitem.h>

/* Same contract as utility.library NextTagItem: returns next user item or NULL. */
struct TagItem *NextTag(struct TagItem **state)
{
    struct TagItem *ti = *state;

    while (ti != NULL) {
        switch (ti->ti_Tag) {
        case TAG_DONE:   ti = NULL; break;
        case TAG_MORE:   ti = (struct TagItem *)ti->ti_Data; continue;
        case TAG_IGNORE: ti++; continue;
        case TAG_SKIP:   ti += ti->ti_Data + 1; continue;
        default:         *state = ti + 1; return ti;
        }
    }
    *state = NULL;
    return NULL;
}

ULONG SumWidths(struct TagItem *tags)
{
    struct TagItem *state = tags, *ti;
    ULONG sum = 0;

    while ((ti = NextTag(&state)) != NULL)
        if (ti->ti_Tag == WA_Width)
            sum += ti->ti_Data;
    return sum;
}
```

## Common mistakes

- Forgetting `TAG_DONE`. The library then reads garbage pairs until it crashes.
- Passing a pointer as `ti_Data` in a varargs stub without `(ULONG)`. Bartman's GCC 15
  rejects it ("makes integer from pointer without a cast").
- Using `dc.w` for a tag or data item, or an odd-aligned tag array in asm. Every field is a
  32-bit long.
- Calling `...Tags` from asm. There is no LVO: call the `...TagList` or `...A` function.
- Walking a tag array with `ti++` instead of NextTagItem, which misses `TAG_MORE` chains.
- Handing a stack-built tag array to something that keeps the pointer after the call returns.
  Only calls that consume the tags during the call are safe with a stack array.
- Calling tag-based functions on Kickstart 1.3 (V34). They don't exist. Check the library
  version first.
- Private tags below `TAG_USER`: values 0-3 are the control tags above.

**See also:** [calling convention](calling-convention.md),
[opening libraries](opening-libraries.md), [structures](structures.md)
