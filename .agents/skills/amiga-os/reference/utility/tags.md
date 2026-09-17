# utility.library: tag lists

Functions for code that RECEIVES tag lists (your own tag-based API, a BOOPSI dispatcher, a hook)
or needs to edit or copy one. Look single tags up with [GetTagData](#gettagdata) /
[FindTagItem](#findtagitem), iterate with [NextTagItem](#nexttagitem), turn boolean tags into
flags with [PackBoolTags](#packbooltags) or whole structures with
[PackStructureTags](#packstructuretags), and edit lists in place with the Filter/Map/Apply calls.
Layout of `struct TagItem`, the control tags and how to BUILD lists: [taglists topic](../topics/taglists.md).

Rules shared by every call here:

- A tag array ends at `TAG_DONE` (0). `TAG_IGNORE` (1) skips one item, `TAG_SKIP` (3) skips the item
  plus `ti_Data` more, `TAG_MORE` (2) continues at the array in `ti_Data`. NextTagItem is documented
  to honour all four; the other scanning calls are built on the same walk (the autodocs imply it
  without spelling it out for each, unverified).
- "Removing" a tag never shrinks the array: its `ti_Tag` is overwritten with `TAG_IGNORE`. Those
  calls modify the caller's array, so never pass one in read-only memory (or a list someone else
  still reads).
- Filter arrays for [TagInArray](#taginarray) and [FilterTagItems](#filtertagitems) are plain
  `Tag` (ULONG) arrays ended by `TAG_DONE`, NOT TagItem pairs.
- Constants (utility/tagitem.h and .i): `TAGFILTER_AND` 0, `TAGFILTER_NOT` 1,
  `MAP_REMOVE_NOT_FOUND` 0, `MAP_KEEP_NOT_FOUND` 1.

## FindTagItem
`struct TagItem * FindTagItem(Tag tagVal, CONST struct TagItem *tagList)` — LVO -30 (-$1E)
Registers: tagVal=D0, tagList=A0; result in D0

Return a pointer to the first item of a tag list whose ti_Tag matches.

- **tagVal** — tag to look for.
- **tagList** — list to scan; may be NULL (result NULL).
- **Result** — pointer to the matching `struct TagItem` inside the caller's list, or NULL.

Since V36.

Use it instead of [GetTagData](#gettagdata) when a present tag with data 0 must be told apart
from an absent tag, or when you want to change `ti_Data` in place.

### Example
```asm
; a2 = tag list passed to us: honour MYT_Lives only if present (0 is legal)
        include "utility/tagitem.i"
        include "lvo/utility_lib.i"

MYT_Lives equ TAG_USER+$4003

        move.l  _UtilityBase,a6
        move.l  #MYT_Lives,d0
        move.l  a2,a0
        jsr     _LVOFindTagItem(a6)
        tst.l   d0
        beq.s   .default                ; tag absent
        move.l  d0,a0
        move.l  ti_Data(a0),lives
```

**See also:** [GetTagData](#gettagdata), [NextTagItem](#nexttagitem), [PackBoolTags](#packbooltags)

## GetTagData
`ULONG GetTagData(Tag tagValue, ULONG defaultVal, CONST struct TagItem *tagList)` — LVO -36 (-$24)
Registers: tagValue=D0, defaultVal=D1, tagList=A0; result in D0

Return the ti_Data of the first matching tag, or a default when the tag is absent.

- **tagValue** — tag to look for.
- **defaultVal** — returned unchanged when the tag is not in the list.
- **tagList** — list to scan.
- **Result** — `ti_Data` of the first match, else `defaultVal`. Pointers come back as ULONG: cast.

Since V36.

### Example
```c
#include <proto/utility.h>
#include <utility/tagitem.h>

#define MYT_Dummy (TAG_USER + 0x4000)
#define MYT_Speed (MYT_Dummy + 1)           /* UWORD, default 4 */
#define MYT_Name  (MYT_Dummy + 2)           /* CONST_STRPTR, default "player" */
#define MYT_Lives (MYT_Dummy + 3)           /* ULONG, 0 is a legal value */

struct Player { UWORD speed; CONST_STRPTR name; ULONG lives; };

extern struct UtilityBase *UtilityBase;

void PlayerSetup(struct Player *p, const struct TagItem *tags)
{
    struct TagItem *ti;

    p->speed = (UWORD)GetTagData(MYT_Speed, 4, tags);
    p->name  = (CONST_STRPTR)GetTagData(MYT_Name, (ULONG)"player", tags);
    if ((ti = FindTagItem(MYT_Lives, tags)) != NULL)
        p->lives = ti->ti_Data;
}
```

### Gotchas
- Only the FIRST occurrence counts; duplicates later in the list are ignored (compare
  [PackBoolTags](#packbooltags), where the last one wins).
- Pass the default already converted to ULONG: `(ULONG)"text"`, not a pointer.

**See also:** [FindTagItem](#findtagitem), [NextTagItem](#nexttagitem), [PackBoolTags](#packbooltags)

## NextTagItem
`struct TagItem * NextTagItem(struct TagItem **tagListPtr)` — LVO -48 (-$30)
Registers: tagListPtr=A0; result in D0

Return the next item of a tag list to process, following TAG_MORE/IGNORE/SKIP.

- **tagListPtr** — address of your own `struct TagItem *` state variable, initialised to the list
  start. The call advances it.
- **Result** — next user item, or NULL at the end of the list (and of every chained array).

Since V36.

### Example
```asm
; a2 = tag list; count MYT_Speed items (asm: the state variable lives on the stack)
        include "utility/tagitem.i"
        include "lvo/utility_lib.i"

MYT_Speed equ TAG_USER+$4001

        move.l  _UtilityBase,a6
        moveq   #0,d2                   ; counter (preserved by the call)
        move.l  a2,-(sp)                ; state = list start
.loop:  move.l  sp,a0                   ; a0 -> state
        jsr     _LVONextTagItem(a6)
        tst.l   d0
        beq.s   .done
        move.l  d0,a0
        cmp.l   #MYT_Speed,ti_Tag(a0)
        bne.s   .loop
        addq.l  #1,d2
        bra.s   .loop
.done:  addq.l  #4,sp                   ; drop the state
```

```c
#include <proto/utility.h>
#include <utility/tagitem.h>

extern struct UtilityBase *UtilityBase;

/* Bartman gcc 15: NextTagItem(&state) fails with -Wincompatible-pointer-types inside the
   inline macro. A typedef keeps the macro's volatile on the outer pointer and compiles clean. */
typedef struct TagItem **TagState;
#define NextTag(sp) LP1(0x30, struct TagItem *, NextTagItem, TagState, sp, a0, , UtilityBase)

ULONG CountTags(struct TagItem *tags)
{
    struct TagItem *state = tags, *ti;
    ULONG n = 0;

    while ((ti = NextTag(&state)) != NULL)
        n++;
    return n;
}
```

### Gotchas
- Use the RETURNED pointer, never the state variable's value (autodoc warning).
- Bartman gcc: the stock macro works too if you wrap the loop in
  `#pragma GCC diagnostic ignored "-Wincompatible-pointer-types"` (push/pop) or build with
  `-Wno-error=incompatible-pointer-types`.

**See also:** [FindTagItem](#findtagitem), [GetTagData](#gettagdata), [taglists topic](../topics/taglists.md)

## TagInArray
`BOOL TagInArray(Tag tagValue, CONST Tag *tagArray)` — LVO -90 (-$5A)
Registers: tagValue=D0, tagArray=A0; result in D0

Test whether a tag value occurs in a TAG_DONE-terminated array of Tag values.

- **tagValue** — tag to look for.
- **tagArray** — `Tag` (ULONG) array ended by `TAG_DONE`; not TagItems.
- **Result** — TRUE if found (BOOL: test the low word).

Since V36.

**See also:** [FilterTagItems](#filtertagitems)

## PackBoolTags
`ULONG PackBoolTags(ULONG initialFlags, CONST struct TagItem *tagList, CONST struct TagItem *boolMap)` — LVO -42 (-$2A)
Registers: initialFlags=D0, tagList=A0, boolMap=A1; result in D0

Build a flag longword from boolean tags using a tag-to-bitmask map.

- **initialFlags** — starting flag value.
- **tagList** — list containing boolean tags (only zero / non-zero of `ti_Data` matters).
- **boolMap** — tag list pairing each boolean tag with the bit mask it controls
  (`{ MYT_Fast, 0x0001 }, ... , { TAG_DONE, 0 }`).
- **Result** — `initialFlags` with the mask bits of every mapped tag set (data non-zero) or cleared
  (data zero). Tags not in `boolMap` are ignored.

Since V36.

### Example
```c
#include <proto/utility.h>
#include <utility/tagitem.h>

#define MYT_Fast   (TAG_USER + 0x4101)
#define MYT_Shield (TAG_USER + 0x4102)
#define PF_FAST    0x0001
#define PF_SHIELD  0x0002

extern struct UtilityBase *UtilityBase;

static const struct TagItem flagMap[] = {
    { MYT_Fast,   PF_FAST },
    { MYT_Shield, PF_SHIELD },
    { TAG_DONE,   0 }
};

ULONG PlayerFlags(ULONG current, const struct TagItem *tags)
{
    /* MYT_Fast,TRUE sets PF_FAST; MYT_Shield,FALSE clears PF_SHIELD */
    return PackBoolTags(current, tags, flagMap);
}
```

### Gotchas
- A tag that appears several times: the LAST one wins.
- The autodoc example's stated result (0x80005 from 0x800002) is a typo; the real value is 0x800005.

**See also:** [GetTagData](#gettagdata), [PackStructureTags](#packstructuretags)

## FilterTagItems
`ULONG FilterTagItems(struct TagItem *tagList, CONST Tag *filterArray, ULONG logic)` — LVO -96 (-$60)
Registers: tagList=A0, filterArray=A1, logic=D0; result in D0

Turn tags in (or not in) a Tag array into TAG_IGNORE, in place.

- **tagList** — list to filter; modified.
- **filterArray** — `Tag` array ended by `TAG_DONE` (as for [TagInArray](#taginarray)).
- **logic** — `TAGFILTER_AND` (0): keep only the tags in the array; `TAGFILTER_NOT` (1): drop the
  tags in the array, keep the rest.
- **Result** — number of valid items left.

Since V36.

### Example
```c
#include <proto/utility.h>
#include <utility/tagitem.h>

#define MYT_Left  (TAG_USER + 0x4201)
#define MYT_Top   (TAG_USER + 0x4202)

extern struct UtilityBase *UtilityBase;

static const Tag posTags[] = { MYT_Left, MYT_Top, TAG_DONE };

/* hand only the position tags of a caller's list to a sub-object */
void PassPosition(const struct TagItem *tags, void (*setpos)(struct TagItem *))
{
    struct TagItem *copy = CloneTagItems(tags);     /* never filter the caller's list */

    if (copy) {
        FilterTagItems(copy, posTags, TAGFILTER_AND);
        setpos(copy);
        FreeTagItems(copy);
    }
}
```

**See also:** [TagInArray](#taginarray), [CloneTagItems](#clonetagitems), [MapTags](#maptags)

## FilterTagChanges
`VOID FilterTagChanges(struct TagItem *changeList, struct TagItem *originalList, ULONG apply)` — LVO -54 (-$36)
Registers: changeList=A0, originalList=A1, apply=D0; no result

Drop entries of a change list that match the current values, optionally applying the rest.

- **changeList** — new attribute values; an item whose tag is in `originalList` with identical
  data becomes `TAG_IGNORE`. Items not present in `originalList` are left alone. May be NULL.
- **originalList** — current attribute values; may be NULL.
- **apply** — non-zero: copy the differing data values into `originalList`; 0: leave it unchanged.

Since V36.

Typical use: an OM_SET-style handler that only wants to react (and redraw) for attributes that
really changed.

**See also:** [ApplyTagChanges](#applytagchanges), [FilterTagItems](#filtertagitems)

## ApplyTagChanges
`VOID ApplyTagChanges(struct TagItem *list, CONST struct TagItem *changeList)` — LVO -186 (-$BA)
Registers: list=A0, changeList=A1; no result

Copy ti_Data from a change list into the matching tags of another list.

- **list** — list to update; only tags already present are changed. May be NULL.
- **changeList** — new values; tags not in `list` are ignored. May be NULL.

Since V39.

**See also:** [FilterTagChanges](#filtertagchanges), [RefreshTagItemClones](#refreshtagitemclones)

## MapTags
`VOID MapTags(struct TagItem *tagList, CONST struct TagItem *mapList, ULONG mapType)` — LVO -60 (-$3C)
Registers: tagList=A0, mapList=A1, mapType=D0; no result

Rename the tags of a list in place using (old tag, new tag) pairs.

- **tagList** — list whose `ti_Tag` values are rewritten; `ti_Data` is untouched.
- **mapList** — pairs `{ oldTag, newTag }` ended by `TAG_DONE`; not modified. May be NULL.
- **mapType** — `MAP_KEEP_NOT_FOUND` (1): tags without a mapping stay as they are;
  `MAP_REMOVE_NOT_FOUND` (0): they become `TAG_IGNORE`.

Since V36.

Mapping a tag to `TAG_DONE` produces `TAG_IGNORE` instead, so a map cannot truncate the list.
Filter with `MAP_REMOVE_NOT_FOUND` and identity pairs, or remove selected tags with
`MAP_KEEP_NOT_FOUND` and pairs `{ tag, TAG_IGNORE }`. Used for BOOPSI interconnection maps
(ICA_MAP).

### Gotchas
- Before V39 `mapType` is ignored and the call always behaves as `MAP_KEEP_NOT_FOUND`.

**See also:** [FilterTagItems](#filtertagitems), [ApplyTagChanges](#applytagchanges)

## AllocateTagItems
`struct TagItem * AllocateTagItems(ULONG numTags)` — LVO -66 (-$42)
Registers: numTags=D0; result in D0

Allocate an array of TagItem slots, freed later with FreeTagItems.

- **numTags** — number of usable slots. Count the terminating `TAG_DONE` as one of them.
- **Result** — pointer to the slots, or NULL if out of memory.

Since V36.

### Gotchas
- The autodoc says to read an allocated list with [NextTagItem](#nexttagitem) because the library
  may use `TAG_MORE`/`TAG_IGNORE` in it. Whether the slots come back zeroed is not documented:
  write your own `TAG_DONE` after the last item you fill.
- Free only with [FreeTagItems](#freetagitems), never FreeMem/FreeVec.

**See also:** [FreeTagItems](#freetagitems), [CloneTagItems](#clonetagitems)

## CloneTagItems
`struct TagItem * CloneTagItems(CONST struct TagItem *tagList)` — LVO -72 (-$48)
Registers: tagList=A0; result in D0

Allocate a copy of a tag list that FindTagItem sees exactly like the original.

- **tagList** — list to copy; NULL gives an empty list.
- **Result** — new list (free with [FreeTagItems](#freetagitems)), or NULL if out of memory.

Since V36.

Order is kept, so lookups on the clone return the same values as on the original. Use a clone
whenever you must filter or map a list that belongs to your caller (example under
[FilterTagItems](#filtertagitems)), or when you need the values after the call returns (the
caller's array may be on its stack).

**See also:** [FreeTagItems](#freetagitems), [RefreshTagItemClones](#refreshtagitemclones), [AllocateTagItems](#allocatetagitems)

## RefreshTagItemClones
`VOID RefreshTagItemClones(struct TagItem *clone, CONST struct TagItem *original)` — LVO -84 (-$54)
Registers: clone=A0, original=A1; no result

Reset a clone made by CloneTagItems back to the original's values.

- **clone** — result of `CloneTagItems(original)` that you have since filtered or edited.
- **original** — the SAME list it was cloned from, unchanged since.

Since V36.

### Gotchas
- Only valid for that exact pair; if `original` changed in any way, free the clone and clone again.

**See also:** [CloneTagItems](#clonetagitems), [ApplyTagChanges](#applytagchanges)

## FreeTagItems
`VOID FreeTagItems(struct TagItem *tagList)` — LVO -78 (-$4E)
Registers: tagList=A0; no result

Free a list from AllocateTagItems or CloneTagItems.

- **tagList** — list to free, or NULL (no action).

Since V36.

**See also:** [AllocateTagItems](#allocatetagitems), [CloneTagItems](#clonetagitems)

## PackStructureTags
`ULONG PackStructureTags(APTR pack, CONST ULONG *packTable, CONST struct TagItem *tagList)` — LVO -210 (-$D2)
Registers: pack=A0, packTable=A1, tagList=A2; result in D0

Store the tag values found in a list into structure fields described by a pack table.

- **pack** — structure to fill.
- **packTable** — ULONG table built with the utility/pack.h macros (below).
- **tagList** — list to read; each table entry does a FindTagItem, absent tags leave the field alone.
- **Result** — number of tag items packed.

Since V39.

Pack table (utility/pack.h): first long = base tag (`PACK_STARTTABLE(base)`), then one long per
field, `PACK_NEWOFFSET(base)` (-1, new base) to switch base, `PACK_ENDTABLE` (0) at the end. An
entry holds the tag's offset from the base (10 bits, 0-1023), the field offset (13 bits, below
8192), the size/sign and the direction:

- `PACK_ENTRY(base, tag, structname, field, control)` for BYTE/WORD/LONG fields;
  `PACK_BYTEBIT`, `PACK_WORDBIT`, `PACK_LONGBIT(base, tag, structname, field, control, flagmask)`
  for a boolean tag mapped to one flag bit (`structname` is the tag name without `struct`).
- Size: `PKCTRL_UBYTE` $00000000, `PKCTRL_UWORD` $08000000, `PKCTRL_ULONG` $10000000,
  `PKCTRL_BYTE` $80000000, `PKCTRL_WORD` $88000000, `PKCTRL_LONG` $90000000, `PKCTRL_BIT`
  $18000000, `PKCTRL_FLIPBIT` $98000000 (inverted boolean).
- Direction: `PKCTRL_PACKUNPACK` 0, `PKCTRL_PACKONLY` $40000000, `PKCTRL_UNPACKONLY` $20000000.
- asm: utility/pack.i only defines `PSTB_`/`PSTF_` `SIGNED` 31, `UNPACK` 30, `PACK` 29, `EXISTS`
  26; build the entries by hand from the bit layout in pack.h.

### Example
```c
#include <proto/utility.h>
#include <utility/tagitem.h>
#include <utility/pack.h>

#define MYT_Dummy  (TAG_USER + 0x4300)
#define MYT_X      (MYT_Dummy + 1)
#define MYT_Y      (MYT_Dummy + 2)
#define MYT_Hidden (MYT_Dummy + 3)

#define SPRF_HIDDEN 0x0001

struct Sprite { WORD x, y; UWORD flags; };

extern struct UtilityBase *UtilityBase;

static const ULONG spritePack[] = {
    PACK_STARTTABLE(MYT_Dummy),
    PACK_ENTRY(MYT_Dummy, MYT_X, Sprite, x, PKCTRL_WORD | PKCTRL_PACKUNPACK),
    PACK_ENTRY(MYT_Dummy, MYT_Y, Sprite, y, PKCTRL_WORD | PKCTRL_PACKUNPACK),
    PACK_WORDBIT(MYT_Dummy, MYT_Hidden, Sprite, flags, PKCTRL_BIT | PKCTRL_PACKUNPACK, SPRF_HIDDEN),
    PACK_ENDTABLE
};

void SpriteSet(struct Sprite *s, const struct TagItem *tags)
{
    PackStructureTags(s, spritePack, tags);
}

void SpriteGetX(const struct Sprite *s, LONG *x)
{
    struct TagItem query[] = { { MYT_X, (ULONG)x }, { TAG_DONE, 0 } };

    UnpackStructureTags((APTR)s, spritePack, query);    /* *x = s->x */
}
```

### Gotchas
- Tags further than 1023 from the base need a `PACK_NEWOFFSET` entry; fields beyond offset 8191
  cannot be described.

**See also:** [UnpackStructureTags](#unpackstructuretags), [FindTagItem](#findtagitem), [PackBoolTags](#packbooltags)

## UnpackStructureTags
`ULONG UnpackStructureTags(CONST APTR pack, CONST ULONG *packTable, struct TagItem *tagList)` — LVO -216 (-$D8)
Registers: pack=A0, packTable=A1, tagList=A2; result in D0

Copy structure fields out to the LONGs that a tag list's ti_Data values point at.

- **pack** — structure to read.
- **packTable** — the same table format as [PackStructureTags](#packstructuretags).
- **tagList** — query list: each tag found gets the field value written to `*(LONG *)ti_Data`.
- **Result** — number of tag items unpacked.

Since V39.

### Gotchas
- Every `ti_Data` must point to a full LONG, even for BYTE/WORD fields and bits.

**See also:** [PackStructureTags](#packstructuretags)
