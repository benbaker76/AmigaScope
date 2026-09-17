# graphics.library: copper list macros

C convenience macros from graphics/gfxmacros.h for building
[user copper lists](user-copper-lists.md). They are not library calls and have no LVO: in
assembler call [UCopperListInit](user-copper-lists.md#ucopperlistinit),
[CWait](user-copper-lists.md#cwait), [CMove](user-copper-lists.md#cmove) and
[CBump](user-copper-lists.md#cbump) directly. The NDK 3.9 versions wrap CMOVE/CWAIT/CEND in
`do { ... } while (0)`, so those are statements (not expressions); define
`OLD_GRAPHICS_GFXMACROS_H` before the include only if old code needs the brace/semicolon forms.

## CINIT

Macro (graphics/gfxmacros.h) — not a library call; expands to UCopperListInit(c,n).

`cl = CINIT(ucl, n)`

- **ucl** — a zeroed `struct UCopList` you allocated yourself (`MEMF_PUBLIC|MEMF_CLEAR`).
- **n** — number of copper instructions (CMOVE, CWAIT and CEND each count one).
- **Result** — the first `struct CopList` block, not the UCopList; 0 on failure.

### Example
```c
#define COLOR00 (*(UWORD *)0xdff180)     /* lvalue for CMOVE's &a */

/* red/green split at line 100 of a screen */
BOOL split_colours(struct Screen *scr)
{
    struct UCopList *ucl = AllocMem(sizeof(struct UCopList), MEMF_PUBLIC | MEMF_CLEAR);
    if (!ucl)
        return FALSE;
    if (!CINIT(ucl, 5)) {                /* 2 waits + 2 moves + CEND */
        FreeMem(ucl, sizeof(struct UCopList));
        return FALSE;
    }
    CWAIT(ucl, 0, 0);
    CMOVE(ucl, COLOR00, 0x0800);
    CWAIT(ucl, 100, 0);
    CMOVE(ucl, COLOR00, 0x0080);
    CEND(ucl);

    Forbid();
    scr->ViewPort.UCopIns = ucl;
    Permit();
    RethinkDisplay();
    return TRUE;
}
```

### Gotchas
- `CINIT(NULL, n)` does not allocate a UCopList; allocate it yourself.
- Before V36 the includes wrapped CINIT in braces, so its result could not be used; the
  NDK 3.9 form is a plain expression.
- The system frees the list later (FreeVPortCopLists); do not FreeMem an attached UCopList.

**See also:** [UCopperListInit](user-copper-lists.md#ucopperlistinit), [CMOVE](#cmove),
[CWAIT](#cwait), [CEND](#cend)

## CMOVE

Macro (graphics/gfxmacros.h) — not a library call; expands to CMove(c,&a,v) + CBump(c).

`CMOVE(ucl, reg, value)`

- **ucl** — the UCopList.
- **reg** — the register as an lvalue; the macro takes its address (`&reg`), e.g.
  `custom.color[0]` with an `extern struct Custom custom;` object, or
  `(*(UWORD *)0xdff180)`.
- **value** — 16-bit value.

### Gotchas
- `ucl` is evaluated twice (CMove and CBump): no side effects in the argument.
- hardware/custom.h does NOT declare `custom` (only a comment). Bartman's amiga-debug template
  has `volatile struct Custom *custom` (a pointer), so `CMOVE(ucl, custom.color[0], v)` does not
  compile there; write `CMove(ucl, (APTR)&custom->color[0], v); CBump(ucl);`. Linking against a
  library that provides a `custom` object at `$DFF000` is (unverified) for gcc toolchains.
- Bartman's custom.h fields are `volatile`: CMOVE on them makes gcc warn about the discarded
  qualifier; use the cast form above or a plain `UWORD` lvalue as in the CINIT example.
- A statement (`do ... while (0)`), not an expression.

**See also:** [CMove](user-copper-lists.md#cmove), [CWAIT](#cwait), [CINIT](#cinit)

## CWAIT

Macro (graphics/gfxmacros.h) — not a library call; expands to CWait(c,v,h) + CBump(c).

`CWAIT(ucl, v, h)`

- **ucl** — the UCopList.
- **v** — line relative to the top of the ViewPort.
- **h** — horizontal position, at most 222.

### Gotchas
- `ucl` is evaluated twice.
- Waits must be issued in increasing Y,X order.
- A statement, not an expression.

**See also:** [CWait](user-copper-lists.md#cwait), [CMOVE](#cmove), [CEND](#cend)

## CEND

Macro (graphics/gfxmacros.h) — not a library call; expands to CWAIT(c,10000,255).

`CEND(ucl)`

- **ucl** — the UCopList to terminate. 10000 is the magic end-of-list line graphics looks for.

### Gotchas
- Every user copper list must end with it (MrgCop relies on terminated, sorted lists), and it
  uses one instruction slot: include it in CINIT's n.
- In assembler: `CWait(ucl,10000,255)` then `CBump(ucl)`.

**See also:** [CWAIT](#cwait), [CINIT](#cinit), [MrgCop](views-and-viewports.md#mrgcop)
