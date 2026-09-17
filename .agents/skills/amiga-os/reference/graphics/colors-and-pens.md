# graphics.library: colours and pens

Every ViewPort shows the colours held in its `ColorMap` ([GetColorMap](#getcolormap),
`vp->ColorMap`). Two ways to change them: set values directly -- 4 bits per gun with
[SetRGB4](#setrgb4)/[LoadRGB4](#loadrgb4) (all versions), or 32-bit left-justified
fractions with [SetRGB32](#setrgb32)/[LoadRGB32](#loadrgb32) (V39, needed for AGA's 8 bits per
gun) -- or, on a screen you share with other programs, allocate pens through the V39 palette
sharing calls ([ObtainBestPenA](#obtainbestpena), [ObtainPen](#obtainpen),
[ReleasePen](#releasepen)). The `...CM` variants only write a ColorMap that is not (yet) shown.
See [32-bit colour values](concepts.md#32-bit-colour-values) and
[pen sharing](concepts.md#pen-sharing-vs-direct-colour-setting).

## GetColorMap
`struct ColorMap * GetColorMap(LONG entries)` — LVO -570 (-$23A)
Registers: entries=D0; result in D0

Allocate and initialise a ColorMap with the given number of entries.

- **entries** — number of colours (32 for OCS/ECS modes, up to 256 for AGA modes).
- **Result** — pointer to the ColorMap, or NULL if out of memory. Store it in `vp->ColorMap`
  before [MakeVPort](views-and-viewports.md#makevport).

### Example
```c
BOOL setup_colormap(struct ViewPort *vp, LONG ncolours)
{
    vp->ColorMap = GetColorMap(ncolours);
    return vp->ColorMap != NULL;
}
```

### Gotchas
- `ColorTable` inside the structure is private and hardware specific; read values with
  [GetRGB4](#getrgb4)/[GetRGB32](#getrgb32) and write with the `...CM` calls.
- Intuition screens already own a ColorMap (`screen->ViewPort.ColorMap`); never replace or free it.
- A hand-built ViewPort with `ColorMap` NULL gets default colours from MakeVPort, but the colour
  setting calls then have nowhere to store values.
- For palette sharing on a custom ViewPort, also call [AttachPalExtra](#attachpalextra).

**See also:** [FreeColorMap](#freecolormap), [SetRGB4](#setrgb4), [LoadRGB32](#loadrgb32),
[VideoControl](views-and-viewports.md#videocontrol)

## FreeColorMap
`VOID FreeColorMap(struct ColorMap *colorMap)` — LVO -576 (-$240)
Registers: colorMap=A0; no result

Free a ColorMap from GetColorMap, including any attached PalExtra.

- **colorMap** — ColorMap from [GetColorMap](#getcolormap); NULL is allowed from V39.

### Gotchas
- Free it only when its ViewPort is no longer displayed (after LoadView of another View and
  [FreeVPortCopLists](views-and-viewports.md#freevportcoplists)).
- NULL is only documented as safe from V39: test the pointer when targeting V37.
- Never free an Intuition screen's ColorMap.

**See also:** [GetColorMap](#getcolormap), [AttachPalExtra](#attachpalextra)

## SetRGB4
`VOID SetRGB4(struct ViewPort *vp, LONG index, ULONG red, ULONG green, ULONG blue)` — LVO -288 (-$120)
Registers: vp=A0, index=D0, red=D1, green=D2, blue=D3; no result

Set one colour of a ViewPort with 4-bit red, green and blue values.

- **vp** — ViewPort (e.g. `&screen->ViewPort`).
- **index** — colour number, 0-31.
- **red**, **green**, **blue** — 0-15 each.

The value is stored in the ViewPort's ColorMap (if any) and the display copper list is updated.

### Example
```asm
; colour 0 = dark blue on the ViewPort in a0
SetBackground:
        movem.l d2-d3/a6,-(sp)
        move.l  _GfxBase,a6
        moveq   #0,d0                   ; index
        moveq   #0,d1                   ; red
        moveq   #0,d2                   ; green
        moveq   #8,d3                   ; blue
        jsr     _LVOSetRGB4(a6)
        movem.l (sp)+,d2-d3/a6
        rts
```

### Gotchas
- Not callable from interrupts under V36+ (copper lists are semaphore protected).
- Only 4 bits per gun: on AGA use [SetRGB32](#setrgb32) for the full 24-bit palette.
- If the colour is not used by the ViewPort's mode/depth nothing visible happens.
- On a shared public screen, change only pens you obtained with `PEN_EXCLUSIVE`.

**See also:** [LoadRGB4](#loadrgb4), [GetRGB4](#getrgb4), [SetRGB4CM](#setrgb4cm), [SetRGB32](#setrgb32)

## SetRGB4CM
`VOID SetRGB4CM(struct ColorMap *colorMap, LONG index, ULONG red, ULONG green, ULONG blue)` — LVO -630 (-$276)
Registers: colorMap=A0, index=D0, red=D1, green=D2, blue=D3; no result

Store a 4-bit-per-gun colour in a ColorMap without touching the display.

- **colorMap** — the ColorMap.
- **index** — colour number, less than the number of entries (0-31 on classic displays).
- **red**, **green**, **blue** — 0-15 each.

### Gotchas
- Nothing changes on screen: use it to prepare a ColorMap before it is attached to a ViewPort
  and MakeVPort is called. For a visible ViewPort use [SetRGB4](#setrgb4).

**See also:** [SetRGB4](#setrgb4), [SetRGB32CM](#setrgb32cm), [GetColorMap](#getcolormap)

## LoadRGB4
`VOID LoadRGB4(struct ViewPort *vp, CONST UWORD *colors, LONG count)` — LVO -192 (-$C0)
Registers: vp=A0, colors=A1, count=D0; no result

Load count 4-bit colours ($0RGB words) into a ViewPort, starting at colour 0.

- **vp** — ViewPort to change.
- **colors** — array of UWORD `$0RGB` values (15 = full intensity per gun).
- **count** — number of entries to load, starting with colour 0.

### Example
```asm
; set a 16-colour OCS palette on the ViewPort in a0
LoadPal16:
        move.l  a6,-(sp)
        move.l  _GfxBase,a6
        lea     Pal16(pc),a1
        moveq   #16,d0
        jsr     _LVOLoadRGB4(a6)
        move.l  (sp)+,a6
        rts

Pal16:  dc.w    $000,$fff,$f00,$0f0,$00f,$ff0,$0ff,$f0f
        dc.w    $888,$444,$800,$080,$008,$880,$088,$808
```

### Gotchas
- Always starts at colour 0; to load a range elsewhere use [SetRGB4](#setrgb4) in a loop or
  [LoadRGB32](#loadrgb32).
- Not callable from interrupts under V36+.
- The ViewPort needs a ColorMap to keep the values (Intuition screens have one).

**See also:** [SetRGB4](#setrgb4), [GetRGB4](#getrgb4), [LoadRGB32](#loadrgb32)

## GetRGB4
`ULONG GetRGB4(struct ColorMap *colorMap, LONG entry)` — LVO -582 (-$246)
Registers: colorMap=A0, entry=D0; result in D0

Read one colour of a ColorMap as a 4-bit-per-gun $0RGB value.

- **colorMap** — the ColorMap (e.g. `screen->ViewPort.ColorMap`).
- **entry** — colour index.
- **Result** — UWORD `$0RGB` value (right-justified), or -1 if the entry is not valid.

### Gotchas
- Intuition `DisplayBeep()` temporarily changes colour 0; reading it during a beep gives the
  flash colour.
- On AGA the low 4 bits of each gun are lost; use [GetRGB32](#getrgb32).

**See also:** [SetRGB4](#setrgb4), [LoadRGB4](#loadrgb4), [GetRGB32](#getrgb32)

## SetRGB32
`VOID SetRGB32(struct ViewPort *vp, ULONG n, ULONG r, ULONG g, ULONG b)` — LVO -852 (-$354)
Registers: vp=A0, n=D0, r=D1, g=D2, b=D3; no result

Set one colour of a ViewPort with 32-bit left-justified red, green and blue values.

- **vp** — ViewPort.
- **n** — colour number.
- **r**, **g**, **b** — 32-bit fractions: `$FFFFFFFF` = full, `$80000000` about 50%, 0 = off.
  Convert an 8-bit value with `c * $01010101`, a 4-bit value with `c * $11111111`. Low bits the
  hardware cannot show are dropped (4 bits used on OCS/ECS, 8 on AGA).

Since V39.

### Example
```c
/* set pen n from 8-bit components */
void set_rgb8(struct ViewPort *vp, ULONG n, UBYTE r, UBYTE g, UBYTE b)
{
    SetRGB32(vp, n, r * 0x01010101UL, g * 0x01010101UL, b * 0x01010101UL);
}
```

### Gotchas
- Passing plain 0-255 values gives an almost black colour: the values must be left-justified.
- [LoadRGB32](#loadrgb32) is faster, even for a single colour; prefer it for fades.
- V39+ only; on V37 use [SetRGB4](#setrgb4).
- Stored in the ColorMap if there is one; unused colour numbers have no visible effect.

**See also:** [LoadRGB32](#loadrgb32), [SetRGB32CM](#setrgb32cm), [GetRGB32](#getrgb32)

## SetRGB32CM
`VOID SetRGB32CM(struct ColorMap *cm, ULONG n, ULONG r, ULONG g, ULONG b)` — LVO -996 (-$3E4)
Registers: cm=A0, n=D0, r=D1, g=D2, b=D3; no result

Store a 32-bit-per-gun colour in a ColorMap without touching the display.

- **cm** — the ColorMap.
- **n** — colour index; must be below the number of entries the ColorMap was allocated with.
- **r**, **g**, **b** — 32-bit left-justified fractions (see [SetRGB32](#setrgb32)).

Since V39.

### Gotchas
- Nothing is shown until the ColorMap is attached to a ViewPort that is (re)made; for a visible
  ViewPort use [SetRGB32](#setrgb32) or [LoadRGB32](#loadrgb32).
- The autodoc synopsis line wrongly reads `SetRGB4CM`; the function is SetRGB32CM.

**See also:** [SetRGB32](#setrgb32), [SetRGB4CM](#setrgb4cm), [GetRGB32](#getrgb32)

## LoadRGB32
`VOID LoadRGB32(struct ViewPort *vp, CONST ULONG *table)` — LVO -882 (-$372)
Registers: vp=A0, table=A1; no result

Load one or more ranges of colours from a table of 32-bit left-justified RGB triplets.

- **vp** — ViewPort to change.
- **table** — ULONG records, each: one UWORD count, one UWORD first colour, then `count` x 3
  ULONGs (red, green, blue, left-justified). A count of 0 ends the table. In C write the header
  as `(count << 16) | first`. NULL is ignored.

Since V39.

### Example
```asm
; a0 = ViewPort; set colours 0-2, then colour 17
LoadMyColours:
        move.l  a6,-(sp)
        move.l  _GfxBase,a6
        lea     Colours32(pc),a1
        jsr     _LVOLoadRGB32(a6)
        move.l  (sp)+,a6
        rts

Colours32:
        dc.w    3,0                             ; 3 colours starting at 0
        dc.l    $00000000,$00000000,$00000000   ; 0 black
        dc.l    $ffffffff,$ffffffff,$ffffffff   ; 1 white
        dc.l    $ff000000,$80000000,$00000000   ; 2 orange ($ff,$80,$00)
        dc.w    1,17                            ; 1 colour starting at 17
        dc.l    $00000000,$00000000,$ffffffff   ; 17 blue
        dc.l    0                               ; count 0 = end
```

```c
/* load count colours from an 8-bit RGB triplet array (e.g. an ILBM CMAP) */
BOOL load_cmap(struct ViewPort *vp, const UBYTE *rgb, UWORD first, UWORD count)
{
    ULONG *tab = AllocVec((count * 3 + 2) * sizeof(ULONG), MEMF_ANY);
    ULONG *p = tab;
    UWORD i;

    if (!tab)
        return FALSE;
    *p++ = ((ULONG)count << 16) | first;
    for (i = 0; i < count * 3; i++)
        *p++ = rgb[i] * 0x01010101UL;         /* 8 -> 32 bit left-justified */
    *p = 0;                                   /* terminator */
    LoadRGB32(vp, tab);
    FreeVec(tab);                             /* values are copied */
    return TRUE;
}
```

### Gotchas
- Forgetting the terminating count of 0 makes graphics read past the table.
- The autodoc's `1l<<16+0` only works because of `+0` (C precedence: `<<` binds weaker than
  `+`); always parenthesise `(count << 16) | first`.
- Components are 32-bit, not 8-bit: `$FF` means almost black, `$FF000000` means full.
- Fastest way to fade: rebuild the table and call LoadRGB32 once per frame after
  [WaitTOF](blitter-and-timing.md#waittof).
- V39+ only. On V37 use [LoadRGB4](#loadrgb4). Calling from interrupts is not documented as
  safe (LoadRGB4/SetRGB4 are explicitly unsafe); do not.

**See also:** [SetRGB32](#setrgb32), [GetRGB32](#getrgb32), [LoadRGB4](#loadrgb4),
[32-bit colour values](concepts.md#32-bit-colour-values)

## GetRGB32
`VOID GetRGB32(CONST struct ColorMap *cm, ULONG firstcolor, ULONG ncolors, ULONG *table)` — LVO -900 (-$384)
Registers: cm=A0, firstcolor=D0, ncolors=D1, table=A1; no result

Read a range of ColorMap entries as 32-bit left-justified RGB triplets.

- **cm** — the ColorMap.
- **firstcolor** — first entry to read.
- **ncolors** — number of entries.
- **table** — buffer of at least `ncolors * 3` ULONGs; filled with R, G, B per colour. Unlike
  LoadRGB32 there is NO count/first header and no terminator.

Since V39.

### Example
```c
/* save a screen palette so it can be restored with LoadRGB32 later */
ULONG *save_palette(struct ColorMap *cm, UWORD count)
{
    ULONG *tab = AllocVec((count * 3 + 2) * sizeof(ULONG), MEMF_CLEAR);
    if (tab) {
        tab[0] = (ULONG)count << 16;          /* LoadRGB32 header: count, first 0 */
        GetRGB32(cm, 0, count, tab + 1);
        /* tab[count*3+1] is already 0 = terminator */
    }
    return tab;
}
```

### Gotchas
- The autodoc NAME line says "Set a series of color registers"; it reads them.
- Values come back at full 32-bit width but only the bits the display holds are meaningful.

**See also:** [LoadRGB32](#loadrgb32), [SetRGB32CM](#setrgb32cm), [GetRGB4](#getrgb4)

## AttachPalExtra
`LONG AttachPalExtra(struct ColorMap *cm, struct ViewPort *vp)` — LVO -834 (-$342)
Registers: cm=A0, vp=A1; result in D0

Allocate and attach the palette-sharing structure (PalExtra) to a custom ColorMap.

- **cm** — ColorMap from [GetColorMap](#getcolormap).
- **vp** — the ViewPort it belongs to; its mode and depth decide which colours are sharable.
- **Result** — 0 on success, otherwise an error number (1 = out of memory).

Since V39.

### Gotchas
- Only for hand-built ViewPorts/ColorMaps: Intuition attaches one to every screen.
- Does nothing if the ColorMap already has a PalExtra. It is freed by
  [FreeColorMap](#freecolormap).
- Without a PalExtra [ObtainPen](#obtainpen) always fails and `FindColor(...,-1)` searches all
  colours.

**See also:** [ObtainPen](#obtainpen), [ObtainBestPenA](#obtainbestpena), [GetColorMap](#getcolormap)

## ObtainPen
`ULONG ObtainPen(struct ColorMap *cm, ULONG n, ULONG r, ULONG g, ULONG b, LONG f)` — LVO -954 (-$3BA)
Registers: cm=A0, n=D0, r=D1, g=D2, b=D3, f=D4; result in D0

Allocate a specific or any free palette entry, shared or exclusive, and set its colour.

- **cm** — ColorMap (with a PalExtra, e.g. `screen->ViewPort.ColorMap`).
- **n** — wanted pen number, or -1 for any free one.
- **r**, **g**, **b** — 32-bit left-justified colour to set.
- **f** — flags: `PENF_EXCLUSIVE` (1, private use -- you may change its colour later),
  `PENF_NO_SETCOLOR` (2, do not change the RGB value; mainly with exclusive pens). Old names
  `PEN_EXCLUSIVE`, `PEN_NO_SETCOLOR` (view.h/view.i) are the same values.
- **Result** — the pen number, or -1 if none is available. The C prototype returns ULONG:
  compare with `(ULONG)-1` or store in a LONG.

Since V39.

### Example
```c
/* get a private pen for colour cycling on a public screen */
LONG get_cycle_pen(struct Screen *scr)
{
    struct ColorMap *cm = scr->ViewPort.ColorMap;
    LONG pen = (LONG)ObtainPen(cm, -1, 0xFFFFFFFF, 0, 0, PENF_EXCLUSIVE);
    if (pen == -1)
        return -1;                     /* no free pen: degrade gracefully */
    SetRGB32(&scr->ViewPort, pen, 0, 0xFFFFFFFF, 0);   /* allowed: exclusive */
    return pen;                        /* ReleasePen(cm, pen) when done */
}
```

### Gotchas
- A shared (non-exclusive) pen must never be changed with SetRGB32: other programs use it too.
- Release with [ReleasePen](#releasepen) only after nothing on screen is drawn in that pen.
- For shared use of "some colour close to X" use [ObtainBestPenA](#obtainbestpena) instead.
- Always fails if the ColorMap has no PalExtra ([AttachPalExtra](#attachpalextra)).

**See also:** [ReleasePen](#releasepen), [ObtainBestPenA](#obtainbestpena), [AttachPalExtra](#attachpalextra)

## ObtainBestPenA
`LONG ObtainBestPenA(struct ColorMap *cm, ULONG r, ULONG g, ULONG b, CONST struct TagItem *tags)` — LVO -840 (-$348)
Registers: cm=A0, r=D1, g=D2, b=D3, tags=A1; result in D0

Find the closest sharable colour or allocate a new shared pen for it.

- **cm** — ColorMap with a PalExtra (every Intuition screen has one).
- **r**, **g**, **b** — wanted colour as 32-bit left-justified fractions.
- **tags** — `OBP_Precision` (`$84000000`): `PRECISION_EXACT` (-1), `PRECISION_IMAGE` (0,
  default), `PRECISION_ICON` (16), `PRECISION_GUI` (32). `OBP_FailIfBad` (`$84000001`): TRUE =
  return -1 instead of a poor match (default FALSE: fails only if no sharable colours exist).
- **Result** — pen number, or -1. Varargs form `ObtainBestPen(cm,r,g,b,tag,...)`.

Since V39.

### Example
```c
/* allocate an orange drawing pen on a window's screen */
LONG orange_pen(struct Window *win)
{
    struct ColorMap *cm = win->WScreen->ViewPort.ColorMap;
    LONG pen = ObtainBestPen(cm, 0xFFFFFFFF, 0x80000000, 0,
                             OBP_Precision, PRECISION_GUI,
                             TAG_DONE);
    if (pen != -1)
        SetAPen(win->RPort, pen);
    return pen;                /* ReleasePen(cm, pen) before closing, if != -1 */
}
```

### Gotchas
- Every successful call needs a matching [ReleasePen](#releasepen) (-1 is safe to release).
- Never change the RGB value of the returned pen.
- Precision values are tolerances: GUI accepts rough matches, IMAGE wants close ones.
- Tag list in asm: `dc.l OBP_Precision,PRECISION_ICON,TAG_DONE,0` pointed to by A1.

**See also:** [ObtainPen](#obtainpen), [ReleasePen](#releasepen), [FindColor](#findcolor)

## ReleasePen
`VOID ReleasePen(struct ColorMap *cm, ULONG n)` — LVO -948 (-$3B4)
Registers: cm=A0, n=D0; no result

Give back a pen obtained with ObtainPen or ObtainBestPenA.

- **cm** — the same ColorMap the pen came from.
- **n** — pen number; -1 is ignored, so the result of a failed obtain can be passed directly.

Works for shared and exclusive pens. When the last user releases a pen its colour may be
reassigned.

Since V39.

### Gotchas
- Release only pens you obtained, once each, and before the screen/window closes.
- Stop drawing in the pen (or redraw) first: another task may reuse the colour immediately.

**See also:** [ObtainPen](#obtainpen), [ObtainBestPenA](#obtainbestpena)

## FindColor
`LONG FindColor(struct ColorMap *cm, ULONG r, ULONG g, ULONG b, LONG maxcolor)` — LVO -1008 (-$3F0)
Registers: cm=A3, r=D1, g=D2, b=D3, maxcolor=D4; result in D0

Return the ColorMap entry closest to an RGB value without allocating anything.

- **cm** — ColorMap. Note the register: **A3**, not A0.
- **r**, **g**, **b** — 32-bit left-justified fractions.
- **maxcolor** — highest entry to search, or -1 to search only pens that can actually be
  rendered in (needs a PalExtra; without one -1 searches the whole map).
- **Result** — the best matching pen.

Since V39.

### Example
```asm
; d1-d3 = RGB (32-bit), a0 = Screen ViewPort ColorMap -> d0 = nearest pen
NearestPen:
        movem.l d4/a3/a6,-(sp)
        move.l  _GfxBase,a6
        move.l  a0,a3                   ; FindColor wants the ColorMap in A3
        moveq   #-1,d4                  ; only renderable pens
        jsr     _LVOFindColor(a6)
        movem.l (sp)+,d4/a3/a6
        rts
```

### Gotchas
- Do not [ReleasePen](#releasepen) the result: nothing was allocated.
- Ignores palette sharing: use it for private screens, internal colour matching, or as a
  fallback when [ObtainBestPenA](#obtainbestpena) finds no sharable pens.
- A3 is not a scratch register in the usual calling convention: save it around the call in asm.

**See also:** [ObtainBestPenA](#obtainbestpena), [GetColorMap](#getcolormap)
