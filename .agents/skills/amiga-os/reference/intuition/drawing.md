# intuition.library: drawing Intuition imagery

Intuition has three simple rendering records, all of which chain. `struct Border` is a polyline
(`Count` XY pairs drawn with Move/Draw, `NextBorder`). `struct Image` is planar bitmap data with
`PlanePick`/`PlaneOnOff` plane mapping and `NextImage`. `struct IntuiText` is a string with pens,
draw mode, an optional `TextAttr` and `NextText`. All three render into any RastPort. A window's
`RPort` is layered, so drawing is clipped to the window. A screen's RastPort is not clipped, so
you must stay inside it. Keep `Image.ImageData` in chip RAM (unverified; standard RKM rule). A
BOOPSI image object is also a `struct Image`, so DrawImage, DrawImageState, EraseImage and
PointInImage work on imageclass objects too.

## DrawBorder
`VOID DrawBorder(struct RastPort *rp, CONST struct Border *border, LONG leftOffset, LONG topOffset)` — LVO -108 (-$6C)
Registers: rp=A0, border=A1, leftOffset=D0, topOffset=D1; no result

Draw a Border (and every Border linked through NextBorder) into a RastPort.

- **rp** — destination RastPort, usually `win->RPort`.
- **border** — first Border: `LeftEdge`, `TopEdge`, `FrontPen`, `BackPen`, `DrawMode`,
  `Count` (number of XY pairs, BYTE), `XY` (WORD pairs relative to LeftEdge/TopEdge),
  `NextBorder`.
- **leftOffset, topOffset** — added to every coordinate.

### Example
```asm
        include "intuition/intuition.i"
        include "graphics/rastport.i"
        include "lvo/intuition_lib.i"

        move.l  IntuitionBase,a6
        move.l  win,a0
        move.l  wd_RPort(a0),a0         ; rp
        lea     box,a1                  ; border
        moveq   #20,d0                  ; leftOffset
        moveq   #30,d1                  ; topOffset
        jsr     _LVODrawBorder(a6)

        section data,data
box:    dc.w    0,0                     ; bd_LeftEdge, bd_TopEdge
        dc.b    2,0,RP_JAM1,5           ; FrontPen, BackPen, DrawMode, Count
        dc.l    boxxy,0                 ; bd_XY, bd_NextBorder
boxxy:  dc.w    0,0, 99,0, 99,49, 0,49, 0,0
```

### Gotchas
- It changes the RastPort's pens and draw mode (it sets them from the Border). Set them again
  before your own drawing.
- `Count` is the number of points, not the number of lines. A closed box needs 5.

**See also:** [DrawImage](#drawimage), [PrintIText](#printitext), graphics.library Draw

## DrawImage
`VOID DrawImage(struct RastPort *rp, struct Image *image, LONG leftOffset, LONG topOffset)` — LVO -114 (-$72)
Registers: rp=A0, image=A1, leftOffset=D0, topOffset=D1; no result

Draw an Image (and every Image linked through NextImage) into a RastPort.

- **rp** — destination RastPort. A layered window RastPort clips; a screen RastPort does not.
- **image** — Image: `LeftEdge`, `TopEdge`, `Width`, `Height`, `Depth`, `ImageData` (for each
  plane, rows of word-aligned bits), `PlanePick` (planes that receive data), `PlaneOnOff`
  (value for the planes not picked), `NextImage`.
- **leftOffset, topOffset** — added to the image's LeftEdge/TopEdge.

`PlanePick` = 0 with `PlaneOnOff` = pen draws a solid rectangle in that colour, with no data.

### Example
```c
#include <proto/intuition.h>
#include <intuition/intuition.h>

/* 16x8, 2 planes, planes in sequence, one word per row; kept in chip RAM
   (Bartman gcc: .MEMF_CHIP section, as in the template's copper list) */
static UWORD arrowData[] __attribute__((section(".MEMF_CHIP"))) = {
    0x0180, 0x03C0, 0x07E0, 0x0FF0, 0x0180, 0x0180, 0x0180, 0x0180,  /* plane 0 */
    0x0000, 0x0180, 0x03C0, 0x07E0, 0x0000, 0x0000, 0x0000, 0x0000   /* plane 1 */
};
static struct Image arrow = {
    0, 0, 16, 8, 2, arrowData,
    0x03, 0x00,        /* PlanePick: data -> planes 0,1; PlaneOnOff: others 0 */
    NULL
};

DrawImage(win->RPort, &arrow, win->BorderLeft + 10, win->BorderTop + 10);
```
In vasm, put the plane data in a `section imgdata,data_c` section.

### Gotchas
- There must be at least as many planes of data as there are 1-bits in `PlanePick`; Intuition
  relies on that count.
- Rows are padded to 16 bits: a 20-pixel-wide image uses 2 words per row.
- Pass a screen RastPort only if the whole image fits inside it, because there is no clipping
  there.

**See also:** [DrawImageState](#drawimagestate), [EraseImage](#eraseimage),
[DrawBorder](#drawborder)

## DrawImageState
`VOID DrawImageState(struct RastPort *rp, struct Image *image, LONG leftOffset, LONG topOffset, ULONG state, CONST struct DrawInfo *drawInfo)` — LVO -618 (-$26A)
Registers: rp=A0, image=A1, leftOffset=D0, topOffset=D1, state=D2, drawInfo=A2; no result

Draw an image in a visual state (normal, selected, disabled...), mainly for BOOPSI images.

- **rp** — destination RastPort.
- **image** — standard Image or imageclass object.
- **leftOffset, topOffset** — position offsets in pixels.
- **state** — `IDS_NORMAL` (0), `IDS_SELECTED` (1), `IDS_DISABLED` (2), `IDS_BUSY` (3),
  `IDS_INDETERMINATE` (4), `IDS_INACTIVENORMAL` (5), `IDS_INACTIVESELECTED` (6),
  `IDS_INACTIVEDISABLED` (7), `IDS_SELECTEDDISABLED` (8) (`intuition/imageclass.h`). A traditional
  Image understands only `IDS_NORMAL`.
- **drawInfo** — from GetScreenDrawInfo. It supplies pens and resolution. Some classes require it,
  so pass it whenever you have one.

Since V36.

### Example
```c
#include <intuition/imageclass.h>

struct DrawInfo *dri = GetScreenDrawInfo(win->WScreen);
struct Image *frame = (struct Image *)NewObject(NULL, (CONST_STRPTR)FRAMEICLASS,
    IA_Width, 120, IA_Height, 24,
    IA_FrameType, FRAME_BUTTON,      /* V39+ */
    IA_Recessed, TRUE,
    TAG_DONE);
if (frame) {
    DrawImageState(win->RPort, frame, win->BorderLeft + 8, win->BorderTop + 8,
                   IDS_NORMAL, dri);
    DisposeObject(frame);
}
FreeScreenDrawInfo(win->WScreen, dri);
```

### Gotchas
- Each image class documents which states it supports. `IDS_BUSY` and `IDS_INDETERMINATE` were
  reserved for future use.
- The DrawInfo is valid only between GetScreenDrawInfo and FreeScreenDrawInfo, and only while the
  screen is open.

**See also:** [DrawImage](#drawimage), [GetScreenDrawInfo](screens.md#getscreendrawinfo),
[NewObjectA](boopsi.md#newobjecta)

## EraseImage
`VOID EraseImage(struct RastPort *rp, struct Image *image, LONG leftOffset, LONG topOffset)` — LVO -630 (-$276)
Registers: rp=A0, image=A1, leftOffset=D0, topOffset=D1; no result

Erase the area an image occupies, using the layer's backfill.

- **rp** — RastPort to erase in.
- **image** — standard Image or imageclass object.
- **leftOffset, topOffset** — same offsets you drew it with.

For a standard Image this is graphics.library EraseRect over its LeftEdge/TopEdge/Width/Height
box, which clears with the layer backfill hook if there is one. Image classes may do something
else.

Since V36.

**See also:** [DrawImage](#drawimage), graphics.library EraseRect

## PointInImage
`BOOL PointInImage(ULONG point, struct Image *image)` — LVO -624 (-$270)
Registers: point=D0, image=A0; result in D0

Test whether a point lies inside an image (its box, or a class-defined shape).

- **point** — X in the high word and Y in the low word of one longword:
  `((ULONG)x << 16) | (UWORD)y`. Use the same coordinates as the image's LeftEdge/TopEdge.
- **image** — standard Image or imageclass object. `NULL` returns TRUE.
- **Result** — TRUE if the point is inside. A standard Image checks its box; image classes can do
  real shape tests, which replaces `BOOLMASK`.

Since V36.

### Gotchas
- The NDK prototype takes a ULONG, not a `struct Point`, so pack X and Y yourself.
- Only the first image is tested; NextImage is ignored.

**See also:** [DrawImage](#drawimage), [NewObjectA](boopsi.md#newobjecta)

## PrintIText
`VOID PrintIText(struct RastPort *rp, CONST struct IntuiText *iText, LONG left, LONG top)` — LVO -216 (-$D8)
Registers: rp=A0, iText=A1, left=D0, top=D1; no result

Render an IntuiText chain into a RastPort at an offset.

- **rp** — destination RastPort (the window's RastPort clips).
- **iText** — IntuiText: `FrontPen`, `BackPen`, `DrawMode` (`JAM1`, `JAM2`, ...), `LeftEdge`,
  `TopEdge`, `ITextFont` (`struct TextAttr *` or `NULL`), `IText` (NUL-terminated),
  `NextText`.
- **left, top** — added to each IntuiText's LeftEdge/TopEdge.

If `ITextFont` is `NULL`, the RastPort's font is used; if that is also `NULL`, the system default
font is used.

### Example
```c
struct IntuiText it = { 1, 0, JAM2, 0, 0, NULL, (UBYTE *)"Hello", NULL };
LONG w;

it.ITextFont = win->WScreen->Font;           /* measure and draw with the same font */
w = IntuiTextLength(&it);
PrintIText(win->RPort, &it,
           win->BorderLeft + (win->Width - win->BorderLeft - win->BorderRight - w) / 2,
           win->BorderTop + 4);
```

### Gotchas
- It changes the RastPort's pens and draw mode, like DrawBorder.
- The position is the top-left of the text, not the baseline as with graphics Move/Text
  (unverified).
- In assembler, IntuiText has a pad byte after `it_DrawMode`
  (`dc.b front,back,mode,0` then `dc.w left,top`).
- A disk font named in `ITextFont` must already be in memory (OpenDiskFont it and keep it open).
  Intuition does not call OpenDiskFont; the autodoc says so for OpenScreen, assumed here
  (unverified).

**See also:** [IntuiTextLength](#intuitextlength), [DrawBorder](#drawborder),
[OpenDiskFont](../diskfont/diskfont.md#opendiskfont), graphics.library Text

## IntuiTextLength
`LONG IntuiTextLength(CONST struct IntuiText *iText)` — LVO -330 (-$14A)
Registers: iText=A0; result in D0

Return the pixel width of an IntuiText's string (the first IntuiText only).

- **iText** — IntuiText whose `IText` is measured with `ITextFont`.
- **Result** — width in pixels.

### Gotchas
- If `ITextFont` is `NULL`, it measures in the system default font, not in the font of the
  RastPort you will print to (there is no RastPort argument). Set `ITextFont` to the target font,
  for example `win->WScreen->Font`, before you measure.
- Only this IntuiText's string is measured; NextText entries are not included.

**See also:** [PrintIText](#printitext), [OpenScreenTagList](screens.md#openscreentaglist)
