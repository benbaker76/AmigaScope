# intuition.library: gadgets

Intuition has three kinds of gadgets: traditional `struct Gadget` records you fill in yourself
(Boolean, proportional, string), BOOPSI gadgets made with `NewObjectA()` (see
[boopsi.md](boopsi.md)), and gadtools.library gadgets, which are built on the same lists. All of
them live on the window's `FirstGadget` list and are added with AddGList. Never edit a gadget while
it is attached: remove it, change it, add it back at the same position, then refresh it
(`RemoveGList -> modify -> AddGList -> RefreshGList`). BOOPSI gadgets are the exception: change
them with SetGadgetAttrsA, which does its own locking and redraw.

## AddGadget
`UWORD AddGadget(struct Window *window, struct Gadget *gadget, ULONG position)` — LVO -42 (-$2A)
Registers: window=A0, gadget=A1, position=D0; result in D0

Link one gadget into a window's gadget list at a given position, without drawing it.

- **window** — window whose `FirstGadget` list gets the gadget. Gadgets cannot be added to a
  screen (use a backdrop window instead).
- **gadget** — the gadget. Only this one is added; its `NextGadget` is overwritten.
- **position** — 0 = head of the list, n = after the n-th gadget. A value bigger than the list
  length appends. Pass `(UWORD)~0` (-1) to append.
- **Result** — position where the gadget was actually inserted.

### Gotchas
- Nothing is drawn. Call RefreshGList afterwards.
- The system gadgets (close, drag, depth, size) sit at the front of the list so that they win hit
  tests. If you insert at position 0 and your gadget overlaps them, yours is hit first.
- -1 as the position only goes wrong for the 65536th gadget, because the position is a UWORD.

**See also:** [AddGList](#addglist), [RemoveGadget](#removegadget), [RefreshGList](#refreshglist)

## AddGList
`UWORD AddGList(struct Window *window, struct Gadget *gadget, ULONG position, LONG numGad, struct Requester *requester)` — LVO -438 (-$1B6)
Registers: window=A0, gadget=A1, position=D0, numGad=D1, requester=A2; result in D0

Link a chain of gadgets into a window or requester gadget list in one call.

- **window** — target window. For requester gadgets, the window the requester appears in.
- **gadget** — first gadget of a chain linked through `NextGadget`.
- **position** — list position, as for AddGadget. `(UWORD)~0` appends.
- **numGad** — how many gadgets of the chain to add. -1 adds up to the `NULL` link.
- **requester** — used only if the first gadget has `GTYP_REQGADGET` set in `GadgetType`.
  Otherwise pass `NULL`.
- **Result** — position of the first added gadget.

### Example
```c
#include <proto/intuition.h>
#include <intuition/intuition.h>
#include <graphics/rastport.h>       /* JAM1 */

static WORD okXY[] = { 0,0, 79,0, 79,13, 0,13, 0,0 };
static struct Border okBorder = { 0, 0, 1, 0, JAM1, 5, okXY, NULL };
static struct IntuiText okText = { 1, 0, JAM1, 32, 3, NULL, (UBYTE *)"OK", NULL };
static struct Gadget okGad = {
    NULL, 20, 30, 80, 14,                 /* NextGadget, Left, Top, Width, Height */
    GFLG_GADGHCOMP, GACT_RELVERIFY, GTYP_BOOLGADGET,
    (APTR)&okBorder, NULL, &okText,       /* GadgetRender, SelectRender, GadgetText */
    0, NULL, 1, NULL                      /* MutualExclude, SpecialInfo, GadgetID, UserData */
};

void add_ok(struct Window *win)
{
    AddGList(win, &okGad, (UWORD)~0, 1, NULL);
    RefreshGList(&okGad, win, NULL, 1);
    /* IDCMP_GADGETUP: ((struct Gadget *)imsg->IAddress)->GadgetID == 1 */
}
```

### Gotchas
- The `NextGadget` of the numGad-th (last added) gadget is overwritten to link it into the
  window list. Adding 3 of a 5-gadget chain cuts your chain after the third gadget.
- Set or clear `GTYP_REQGADGET` the same way on every gadget in the chain.
- `LeftEdge`/`TopEdge` are measured from the window's outer corner, so allow for
  `win->BorderLeft` and `win->BorderTop` (or use `GFLG_RELRIGHT`/`GFLG_RELBOTTOM`).
- Adding does not draw anything. Always follow with RefreshGList.

**See also:** [AddGadget](#addgadget), [RemoveGList](#removeglist), [RefreshGList](#refreshglist),
[OpenWindowTagList](windows.md#openwindowtaglist)

## RemoveGadget
`UWORD RemoveGadget(struct Window *window, struct Gadget *gadget)` — LVO -228 (-$E4)
Registers: window=A0, gadget=A1; result in D0

Unlink one gadget from a window, or from a requester in that window.

- **window** — window containing the gadget, or containing the requester that holds it.
- **gadget** — gadget to remove. Its `GTYP_REQGADGET` bit says which list to search.
- **Result** — the gadget's former ordinal position, or -1 (`$FFFF`) if it was not found or the
  list is empty.

### Gotchas
- The result is a UWORD, so failure reads as 65535 in C unless you compare with `(UWORD)~0`. The
  65535th gadget also returns -1.
- V37+: if the gadget is active, the call waits until the user releases the mouse button.

**See also:** [RemoveGList](#removeglist), [AddGadget](#addgadget)

## RemoveGList
`UWORD RemoveGList(struct Window *remPtr, struct Gadget *gadget, LONG numGad)` — LVO -444 (-$1BC)
Registers: remPtr=A0, gadget=A1, numGad=D0; result in D0

Unlink a run of gadgets from a window or requester gadget list.

- **remPtr** — window containing the gadgets, or containing their requester.
- **gadget** — first gadget to remove. If `GTYP_REQGADGET` is set, the requester list is used.
- **numGad** — number of gadgets to remove. -1 removes everything to the end of the list.
- **Result** — former position of the first removed gadget, or -1 (`$FFFF`) on failure.

### Example
```c
/* toggle a Boolean gadget's selected look the approved way */
UWORD pos = RemoveGList(win, &toggleGad, 1);
if (pos != (UWORD)~0) {
    toggleGad.Flags ^= GFLG_SELECTED;
    AddGList(win, &toggleGad, pos, 1, NULL);
    RefreshGList(&toggleGad, win, NULL, 1);
}
```

### Gotchas
- V36+: the last removed gadget's `NextGadget` is set to `NULL` (V34 and older left it linked).
- V37+: waits for the mouse button to be released if one of the gadgets is active.

**See also:** [RemoveGadget](#removegadget), [AddGList](#addglist)

## RefreshGadgets
`VOID RefreshGadgets(struct Gadget *gadgets, struct Window *window, struct Requester *requester)` — LVO -222 (-$DE)
Registers: gadgets=A0, window=A1, requester=A2; no result

Redraw every gadget from the given one to the end of its list.

- **gadgets** — first gadget to redraw. Pass `win->FirstGadget` to redraw all of them.
- **window** — window containing the gadgets or their requester.
- **requester** — requester holding the gadgets. Only used for `GTYP_REQGADGET` gadgets.

### Gotchas
- Only pass gadgets Intuition has already processed (added with AddGList or OpenWindow). Never
  build or relink the list by hand.
- Prefer RefreshGList with a count so that you do not redraw (and flicker) the whole tail.
- Do not call it between BeginRefresh and EndRefresh (deadlock risk).

**See also:** [RefreshGList](#refreshglist), [AddGList](#addglist),
[BeginRefresh](windows.md#beginrefresh)

## RefreshGList
`VOID RefreshGList(struct Gadget *gadgets, struct Window *window, struct Requester *requester, LONG numGad)` — LVO -432 (-$1B0)
Registers: gadgets=A0, window=A1, requester=A2, numGad=D0; no result

Redraw up to numGad gadgets, starting with the given one.

- **gadgets** — first gadget to redraw.
- **window** — window containing the gadgets or their requester.
- **requester** — requester for `GTYP_REQGADGET` gadgets, otherwise `NULL`.
- **numGad** — maximum number to redraw. -1 = to the end of the list. -2 = the same, but if the
  first gadget is a requester gadget, every gadget in that requester is redrawn (V1.1 behaviour).

### Gotchas
- Required after AddGadget, AddGList or any imagery or flag change. Adding a gadget never draws
  it.
- Intuition has already repaired gadgets and borders by the time `IDCMP_REFRESHWINDOW` arrives.
  Do not call this inside BeginRefresh/EndRefresh.

**See also:** [RefreshGadgets](#refreshgadgets), [AddGList](#addglist),
[NewModifyProp](#newmodifyprop)

## OnGadget
`VOID OnGadget(struct Gadget *gadget, struct Window *window, struct Requester *requester)` — LVO -186 (-$BA)
Registers: gadget=A0, window=A1, requester=A2; no result

Enable a gadget: clear `GFLG_DISABLED`, remove the ghosting and allow selection.

- **gadget** — gadget already attached to the window or requester.
- **window** — window containing the gadget or its requester.
- **requester** — requester for `GTYP_REQGADGET` gadgets, otherwise `NULL`.

### Gotchas
- For compatibility it redraws every gadget from this one to the end of the window list (every
  gadget of a requester). For a selective update, remove the gadget, clear `GFLG_DISABLED`, add it
  back and call `RefreshGList(..., 1)`.
- Traditional gadgets drawn as a Border plus IntuiText keep the ghost pattern inside, because
  nothing clears the interior. Either use an Image that covers the whole select box, or remove
  the gadget, EraseRect its box, clear the flag, add it back and refresh.

**See also:** [OffGadget](#offgadget), [RefreshGList](#refreshglist)

## OffGadget
`VOID OffGadget(struct Gadget *gadget, struct Window *window, struct Requester *requester)` — LVO -174 (-$AE)
Registers: gadget=A0, window=A1, requester=A2; no result

Disable a gadget: set `GFLG_DISABLED`, ghost its imagery and block selection.

- **gadget** — gadget already attached to the window or requester.
- **window** — window containing the gadget or its requester.
- **requester** — requester for `GTYP_REQGADGET` gadgets, otherwise `NULL`.

### Gotchas
- Redraws from this gadget to the end of the list, like OnGadget. Use the remove / flag / add /
  RefreshGList sequence to limit flicker.
- Do not try to activate a disabled gadget with ActivateGadget.

**See also:** [OnGadget](#ongadget), [AddGadget](#addgadget), [RefreshGadgets](#refreshgadgets)

## ActivateGadget
`BOOL ActivateGadget(struct Gadget *gadgets, struct Window *window, struct Requester *requester)` — LVO -462 (-$1CE)
Registers: gadgets=A0, window=A1, requester=A2; result in D0

Make a string or custom gadget active so the user can type without clicking it first.

- **gadgets** — the string or custom gadget to activate (enabled and attached).
- **window** — window containing the gadget. For a requester gadget, the window holding the
  requester.
- **requester** — requester for `GTYP_REQGADGET` gadgets, otherwise `NULL`.
- **Result** — TRUE if a string gadget was activated, FALSE if the conditions were not met.

### Example
```c
case IDCMP_ACTIVEWINDOW:          /* window really is active now */
    ActivateGadget(&nameGad, win, NULL);
    break;
```

### Gotchas
- The window must already be active. `WFLG_ACTIVATE` may not have taken effect when OpenWindow
  returns, even after a delay. Wait for `IDCMP_ACTIVEWINDOW`.
- Fails if another gadget (including a system gadget) is in use, if the right mouse button is
  held down, or if the gadget's requester is not active (track it with `IDCMP_REQSET` and
  `IDCMP_REQCLEAR`).
- For custom (BOOPSI) gadgets the result is not reliable: it does not return FALSE when the gadget
  refuses to go active.

**See also:** [SetGadgetAttrsA](#setgadgetattrsa), [ActivateWindow](windows.md#activatewindow)

## ModifyProp
`VOID ModifyProp(struct Gadget *gadget, struct Window *window, struct Requester *requester, ULONG flags, ULONG horizPot, ULONG vertPot, ULONG horizBody, ULONG vertBody)` — LVO -156 (-$9C)
Registers: gadget=A0, window=A1, requester=A2, flags=D0, horizPot=D1, vertPot=D2, horizBody=D3, vertBody=D4; no result

Set a proportional gadget's PropInfo values and redraw it (and every gadget after it).

- **gadget** — `GTYP_PROPGADGET` gadget whose `SpecialInfo` points to a `struct PropInfo`.
- **window** — window containing the gadget or its requester.
- **requester** — requester for `GTYP_REQGADGET` gadgets, otherwise `NULL`.
- **flags** — stored in `PropInfo.Flags`: `AUTOKNOB` (0x0001), `FREEHORIZ` (0x0002), `FREEVERT`
  (0x0004), `PROPBORDERLESS` (0x0008), `PROPNEWLOOK` (0x0010). `KNOBHIT` (0x0100) is set by
  Intuition.
- **horizPot, vertPot** — knob position, 0 to `MAXPOT` (0xFFFF), as a fraction of the travel.
- **horizBody, vertBody** — visible fraction, 0 to `MAXBODY` (0xFFFF). Use `MAXBODY` when
  everything fits. Body also sets the page step when the user clicks the container.

PropInfo fields maintained by Intuition (read only): `CWidth`, `CHeight`, `HPotRes`, `VPotRes`,
`LeftBorder`, `TopBorder`.

### Gotchas
- `flags` replaces `PropInfo.Flags` completely. Pass the current value (`pi->Flags`), or you lose
  `AUTOKNOB`/`FREEVERT`.
- Redraws every gadget from the prop gadget to the end of the list (V36+: full redraws). Use
  NewModifyProp with numGad = 1.
- Do not poke the PropInfo fields directly while the gadget is attached.

**See also:** [NewModifyProp](#newmodifyprop)

## NewModifyProp
`VOID NewModifyProp(struct Gadget *gadget, struct Window *window, struct Requester *requester, ULONG flags, ULONG horizPot, ULONG vertPot, ULONG horizBody, ULONG vertBody, LONG numGad)` — LVO -468 (-$1D4)
Registers: gadget=A0, window=A1, requester=A2, flags=D0, horizPot=D1, vertPot=D2, horizBody=D3, vertBody=D4, numGad=D5; no result

Same as ModifyProp, but redraws only numGad gadgets; with 1 it moves the knob smoothly.

- **gadget, window, requester, flags, horizPot, vertPot, horizBody, vertBody** — as for
  [ModifyProp](#modifyprop).
- **numGad** — gadgets to redraw, starting with this one. -1 = to the end of the list (same as
  ModifyProp). V36+: 1 does an incremental knob-only update with no flashing.

### Example
```c
/* vertical scroller showing lines top..top+vis-1 of total */
void set_scroller(struct Gadget *g, struct Window *w, ULONG top, ULONG vis, ULONG total)
{
    struct PropInfo *pi = (struct PropInfo *)g->SpecialInfo;
    ULONG body = MAXBODY, pot = 0;
    if (total > vis) {
        body = (MAXBODY * vis) / total;
        pot  = (MAXPOT * top) / (total - vis);
    }
    NewModifyProp(g, w, NULL, pi->Flags, 0, pot, MAXBODY, body, 1);
}
/* read back: top = (pi->VertPot * (total - vis) + MAXPOT / 2) / MAXPOT; */
```

### Gotchas
- As with ModifyProp, pass the existing `pi->Flags`.
- Keep `total` below 65536 in the arithmetic above, or scale first (0xFFFF x total must fit in
  32 bits).

**See also:** [ModifyProp](#modifyprop), [RefreshGList](#refreshglist)

## SetGadgetAttrsA
`ULONG SetGadgetAttrsA(struct Gadget *gadget, struct Window *window, struct Requester *requester, CONST struct TagItem *tagList)` — LVO -660 (-$294)
Registers: gadget=A0, window=A1, requester=A2, tagList=A3; result in D0

Set attributes on a BOOPSI gadget that is (or may be) attached, with locking and redraw.

- **gadget** — BOOPSI gadget object (cast `Object *`/APTR to `struct Gadget *`).
- **window** — window the gadget was added to with AddGList/AddGadget, or `NULL`.
- **requester** — requester containing the gadget (REQGADGET), otherwise `NULL`.
- **tagList** — attribute/value pairs (`GA_Disabled`, `PGA_Top`, `STRINGA_LongVal`, ...),
  terminated by `TAG_DONE`.
- **Result** — class-defined. Usually non-zero if the change needs the imagery redrawn.

Varargs form `SetGadgetAttrs(gadget, window, requester, Tag1, ...)` (amiga.lib stub; an inline
macro in the Bartman headers). Sends `OM_SET` with a GadgetInfo built from window/requester.
With both window and requester `NULL` it behaves like SetAttrsA.

Since V36.

### Example
```c
#include <intuition/gadgetclass.h>

/* scroller made with NewObject(NULL, "propgclass", ...) and added to win */
SetGadgetAttrs((struct Gadget *)propObj, win, NULL,
               PGA_Top,     top,
               PGA_Visible, visible,
               PGA_Total,   total,
               TAG_DONE);
```

### Gotchas
- Use this, not SetAttrsA, for gadgets already in a window. SetAttrsA passes no GadgetInfo, so
  the gadget cannot draw itself and there is no arbitration with the input task.
- Before V39 the locking against Intuition's input task was inadequate: the gadget dispatcher had
  to be re-entrant.

**See also:** [SetAttrsA](boopsi.md#setattrsa), [NewObjectA](boopsi.md#newobjecta),
[GetAttr](boopsi.md#getattr), [DoGadgetMethodA](#dogadgetmethoda)

## DoGadgetMethodA
`ULONG DoGadgetMethodA(struct Gadget *gad, struct Window *win, struct Requester *req, Msg message)` — LVO -810 (-$32A)
Registers: gad=A0, win=A1, req=A2, message=A3; result in D0

Invoke any method on a BOOPSI gadget with a GadgetInfo filled in from window/requester.

- **gad** — BOOPSI gadget object.
- **win** — window the gadget belongs to (from AddGList), or `NULL`.
- **req** — requester for REQGADGETs, otherwise `NULL`.
- **message** — method message (`Msg`) starting with `ULONG MethodID`. Leave the GadgetInfo slot
  `NULL`; Intuition fills it in.
- **Result** — method-specific.

The GadgetInfo goes in the 2nd longword of the message (`gpr_GInfo`, `gpl_GInfo`, ...), except
for `OM_NEW`, `OM_SET`, `OM_NOTIFY` and `OM_UPDATE`, where it is the 3rd (`ops_GInfo`,
`opu_GInfo`). Varargs form `DoGadgetMethod(gad, win, req, MethodID, ...)` (amiga.lib stub; an
inline macro in the Bartman headers).

Since V39.

### Example
```c
#include <intuition/gadgetclass.h>

struct gpLayout gpl = { GM_LAYOUT, NULL, FALSE };   /* GInfo filled in by Intuition */
DoGadgetMethodA((struct Gadget *)obj, win, NULL, (Msg)&gpl);
```

### Gotchas
- V39+ only. On V36-V38 use amiga.lib DoMethodA (no GadgetInfo).
- If you define new gadget methods, put the GadgetInfo pointer in the second longword of the
  message, or this call will overwrite your data.

**See also:** [SetGadgetAttrsA](#setgadgetattrsa), [NewObjectA](boopsi.md#newobjecta),
[MakeClass](boopsi.md#makeclass)
