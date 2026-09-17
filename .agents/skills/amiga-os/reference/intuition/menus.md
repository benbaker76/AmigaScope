# intuition.library: menus

A menu strip is a linked list of `struct Menu` headers, each with a chain of `struct MenuItem`
(and optional sub-item chains). Attach it to a window with SetMenuStrip, detach it with
ClearMenuStrip before changing it or closing the window. Selections arrive as `IDCMP_MENUPICK`
with a packed menu number in `IntuiMessage->Code`. Hand-positioning Menu/MenuItem structures is
tedious; the usual way to build and lay out a strip is gadtools.library CreateMenus + LayoutMenus
(freed with FreeMenus).

## Menu numbers

A menu number is a UWORD packing three indexes (all counted from 0). Macros from
intuition/intuition.h (exact definitions):

```c
#define MENUNUM(n) (n & 0x1F)                   /* bits 0-4:   menu     */
#define ITEMNUM(n) ((n >> 5) & 0x003F)          /* bits 5-10:  item     */
#define SUBNUM(n) ((n >> 11) & 0x001F)          /* bits 11-15: sub-item */

#define SHIFTMENU(n) (n & 0x1F)
#define SHIFTITEM(n) ((n & 0x3F) << 5)
#define SHIFTSUB(n) ((n & 0x1F) << 11)
#define FULLMENUNUM( menu, item, sub )  \
        ( SHIFTSUB(sub) | SHIFTITEM(item) | SHIFTMENU(menu) )
```

| Constant | Value | Meaning |
|---|---|---|
| `NOMENU` | $001F | no menu in the menu field |
| `NOITEM` | $003F | no item in the item field |
| `NOSUB` | $001F | no sub-item in the sub field |
| `MENUNULL` | $FFFF | no selection at all |

Maximum 31 menus, 63 items per menu, 31 sub-items per item (the all-ones value of each field is
reserved for NOMENU/NOITEM/NOSUB).

The user can select several items in one menu session (drag-select or extended selection).
`Code` holds the first; each item's `NextSelect` holds the number of the next one, ending with
`MENUNULL`:

```c
case IDCMP_MENUPICK:
{
    UWORD code = menuCode;      /* imsg->Code, copied before ReplyMsg */
    while (code != MENUNULL)
    {
        struct MenuItem *item = ItemAddress(win->MenuStrip, code);
        if (item == NULL)
            break;
        switch (MENUNUM(code))
        {
        case 0:                             /* Project */
            if (ITEMNUM(code) == 3)         /* Quit */
                done = TRUE;
            break;
        case 1:                             /* Options */
            if (ITEMNUM(code) == 0)
                sound = (item->Flags & CHECKED) != 0;
            break;
        }
        code = item->NextSelect;
    }
    break;
}
```

Rules:
- Never follow `NextSelect` for `IDCMP_MENUHELP`; its Code may name a menu header (item field
  `NOITEM`), an item that has sub-items, or be `MENUNULL`, and help is also reported for ghosted
  items.
- The macros do not parenthesize `n`: pass a plain variable, not an expression like `a | b`.
- Read `CHECKED` from the item after the pick; Intuition has already toggled it.

## SetMenuStrip
`BOOL SetMenuStrip(struct Window *window, struct Menu *menu)` — LVO -264 (-$108)
Registers: window=A0, menu=A1; result in D0

Attach a menu strip to a window and precompute its layout.

- **window** — the window.
- **menu** — first `struct Menu` of the strip. Every menu needs at least one item.
- **Result** — always TRUE (the call waits until it is safe to proceed).

### Example
```c
/* proto/gadtools.h; window opened with WA_NewLookMenus, TRUE */
struct Menu *strip = CreateMenus(newMenus, TAG_DONE);
APTR vi = GetVisualInfo(win->WScreen, TAG_DONE);
if (strip && vi && LayoutMenus(strip, vi, GTMN_NewLookMenus, TRUE, TAG_DONE))
{
    SetMenuStrip(win, strip);
    /* ... event loop ... */
    ClearMenuStrip(win);            /* before CloseWindow */
}
if (strip) FreeMenus(strip);
if (vi) FreeVisualInfo(vi);
```

### Gotchas
- Always pair with [ClearMenuStrip](#clearmenustrip): before changing any Menu/MenuItem data,
  before attaching a different strip, and before CloseWindow.
- The strip is not copied; keep it allocated while attached.
- Windows opened with `WFLG_RMBTRAP` never show menus.
- With `WFLG_NEWLOOKMENUS`/`WA_NewLookMenus`, render item imagery in the DrawInfo bar pens
  (`BARDETAILPEN`, `BARBLOCKPEN`).

**See also:** [ClearMenuStrip](#clearmenustrip), [ResetMenuStrip](#resetmenustrip),
[ItemAddress](#itemaddress), [Menu numbers](#menu-numbers), gadtools.library CreateMenus,
gadtools.library LayoutMenus

## ClearMenuStrip
`VOID ClearMenuStrip(struct Window *window)` — LVO -54 (-$36)
Registers: window=A0; no result

Detach the menu strip from a window.

- **window** — the window; waits (Wait()) if any menu is currently in use.

### Gotchas
- Required before modifying strip data, before SetMenuStrip with another strip, and before
  CloseWindow.
- Blocks until the user finishes a menu session: do not call it while holding locks the input
  task needs.

**See also:** [SetMenuStrip](#setmenustrip), [ResetMenuStrip](#resetmenustrip),
[CloseWindow](windows.md#closewindow)

## ResetMenuStrip
`BOOL ResetMenuStrip(struct Window *window, struct Menu *menu)` — LVO -702 (-$2BE)
Registers: window=A0, menu=A1; result in D0

Re-attach a previously set, unchanged menu strip without recomputing its layout.

- **window** — the window.
- **menu** — the same strip that was passed to SetMenuStrip earlier.
- **Result** — always TRUE.

Since V36.

### Example
```c
ClearMenuStrip(win);
item->Flags ^= CHECKED;             /* only CHECKED / ITEMENABLED may change */
ResetMenuStrip(win, strip);
```

### Gotchas
- Only legal if nothing but `CHECKED` and the enable flags (`ITEMENABLED` on items, `MENUENABLED`
  on Menu headers) changed since SetMenuStrip. Any other change (text, positions, items added)
  needs SetMenuStrip.
- On V34 and earlier use SetMenuStrip.

**See also:** [SetMenuStrip](#setmenustrip), [ClearMenuStrip](#clearmenustrip)

## OnMenu
`VOID OnMenu(struct Window *window, ULONG menuNumber)` — LVO -192 (-$C0)
Registers: window=A0, menuNumber=D0; no result

Enable a whole menu, an item, or a sub-item.

- **window** — window the strip is attached to.
- **menuNumber** — packed number selecting what to enable. An item field of `NOITEM` selects the
  whole menu; a sub field of `NOSUB` selects the item (unverified: rule from the RKM, not in the
  local autodoc). Build with `FULLMENUNUM(menu, item, sub)`.

Sets `ITEMENABLED` (or `MENUENABLED`) and redraws as needed.

### Example
```c
OffMenu(win, FULLMENUNUM(1, NOITEM, NOSUB));     /* ghost the whole "Edit" menu */
OnMenu(win, FULLMENUNUM(0, 2, NOSUB));           /* enable item 2 of menu 0 */
```

**See also:** [OffMenu](#offmenu), [ResetMenuStrip](#resetmenustrip), [Menu numbers](#menu-numbers)

## OffMenu
`VOID OffMenu(struct Window *window, ULONG menuNumber)` — LVO -180 (-$B4)
Registers: window=A0, menuNumber=D0; no result

Disable (ghost) a whole menu, an item, or a sub-item.

- **window** — window the strip is attached to.
- **menuNumber** — packed number, same encoding as [OnMenu](#onmenu).

Clears `ITEMENABLED` (or `MENUENABLED`). Ghosted items cannot be picked but still produce
`IDCMP_MENUHELP` reports.

**See also:** [OnMenu](#onmenu), [ResetMenuStrip](#resetmenustrip), [Menu numbers](#menu-numbers)

## ItemAddress
`struct MenuItem * ItemAddress(CONST struct Menu *menuStrip, ULONG menuNumber)` — LVO -144 (-$90)
Registers: menuStrip=A0, menuNumber=D0; result in D0

Return the MenuItem (or sub-item) addressed by a packed menu number.

- **menuStrip** — first Menu of the strip (e.g. `window->MenuStrip`).
- **menuNumber** — number from `IDCMP_MENUPICK` Code or `NextSelect`; must contain valid menu
  and item fields (sub field optional).
- **Result** — `struct MenuItem *` of the item or sub-item; NULL when `menuNumber` is `MENUNULL`.

### Gotchas
- Arguments must be well-formed: an invalid number (e.g. a MENUHELP code with `NOITEM`) can
  yield a bogus pointer. Check `MENUNUM`/`ITEMNUM` against NOMENU/NOITEM first when the number did
  not come from MENUPICK.
- Use it to walk multi-selections via `NextSelect` (see [Menu numbers](#menu-numbers)).

**See also:** [Menu numbers](#menu-numbers), [SetMenuStrip](#setmenustrip)

## LendMenus
`VOID LendMenus(struct Window *fromwindow, struct Window *towindow)` — LVO -804 (-$324)
Registers: fromwindow=A0, towindow=A1; no result

Make menu button presses in one window show another window's menu strip.

- **fromwindow** — window whose menu actions are redirected.
- **towindow** — window whose strip (and screen) is used; NULL stops lending.

Intended for attached screens: e.g. a small control-panel screen attached to a full-size parent
lends its menu button to the parent screen's window.

Since V39.

### Gotchas
- Current behaviour temporarily activates `towindow`; do not rely on that staying the same.

**See also:** [SetMenuStrip](#setmenustrip), [ClearMenuStrip](#clearmenustrip),
[OpenScreenTagList](screens.md#openscreentaglist) (`SA_Parent`, `SA_FrontChild`)
