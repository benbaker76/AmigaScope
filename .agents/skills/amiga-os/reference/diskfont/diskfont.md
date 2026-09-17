# diskfont.library: fonts

A program normally needs two calls here: **OpenDiskFont** to get a `struct TextFont` (then graphics
SetFont/CloseFont) and sometimes **AvailFonts** to list what can be opened. **NewScaledDiskFont** builds
a scaled copy of a font you already hold. **NewFontContents**/**DisposeFontContents** are for tools that
rewrite `.font` contents files. **GetDiskFontCtrl**/**SetDiskFontCtrlA** (V45) belong to the font
preferences editor. See [index](index.md) for how this relates to graphics OpenFont.

## OpenDiskFont
`struct TextFont * OpenDiskFont(struct TextAttr *textAttr)` — LVO -30 (-$1E)
Registers: textAttr=A0; result in D0

Find a font in memory or load it from FONTS:, returning a TextFont for SetFont.

- **textAttr** — `struct TextAttr` (or `TTextAttr`): `ta_Name` with the `.font` suffix, `ta_YSize`,
  `ta_Style` (`FSF_`), `ta_Flags` (`FPF_`; set `FPF_DESIGNED` to refuse scaled sizes).
- **Result** — `struct TextFont *`, or NULL if no such font can be found or loaded. Release it with
  graphics.library CloseFont().

If a matching font is already in memory it is reused, not reloaded from disk. V36+: when the requested
size does not exist as a designed font and `FPF_DESIGNED` is clear, a scaled font is built
automatically. V37 read outline fonts itself; V38+ uses bullet.library for them.

### Example
```c
struct TextAttr ta     = { (STRPTR)"helvetica.font", 13, FS_NORMAL, FPF_DISKFONT | FPF_DESIGNED };
struct TextAttr topaz8 = { (STRPTR)"topaz.font", 8, FS_NORMAL, FPF_ROMFONT };

struct TextFont *tf = OpenDiskFont(&ta);
if (!tf)
    tf = OpenFont(&topaz8);            /* fallback: ROM font, always present */
if (tf) {
    SetFont(win->RPort, tf);
    Move(win->RPort, 20, 40);
    Text(win->RPort, (CONST_STRPTR)"Hello", 5);
    /* ... before CloseFont, make sure no RastPort still uses tf ... */
    CloseFont(tf);
}
```

```asm
        include "exec/types.i"
        include "graphics/text.i"
        include "lvo/diskfont_lib.i"
        include "lvo/graphics_lib.i"

        move.l  DiskfontBase,a6
        lea     tattr(pc),a0
        jsr     _LVOOpenDiskFont(a6)
        move.l  d0,d7                   ; TextFont * (keep in non-scratch reg)
        beq     .nofont
        move.l  GfxBase,a6
        move.l  rastport,a1             ; SetFont: rp=A1, font=A0
        move.l  d7,a0
        jsr     _LVOSetFont(a6)
        ...
        move.l  d7,a1                   ; CloseFont: font=A1
        jsr     _LVOCloseFont(a6)
...
tattr:  dc.l    fontname                ; ta_Name
        dc.w    13                      ; ta_YSize
        dc.b    FS_NORMAL,FPF_DISKFONT  ; ta_Style, ta_Flags
fontname:
        dc.b    "helvetica.font",0
        even
```

### Gotchas
- Does DOS I/O: call it from a process, not from a plain task or an interrupt, and not while
  your window has `IDCMP_*VERIFY` classes active.
- Font file name parts longer than 30 characters are not handled well.
- Scaled fonts can be ugly. Check `tf->tf_YSize` and `tf->tf_Flags & FPF_DESIGNED` if the exact
  size matters, or set `FPF_DESIGNED` in the request.
- Before CloseFont(), switch every RastPort that uses the font back to another font (e.g. the
  screen font).
- V39+: to find the loaded font again with graphics OpenFont(), pass the very same TextAttr/TTextAttr.
- Intuition does not call this for you. Open screen fonts (`SA_Font`) yourself before OpenScreen
  and keep them open while the screen is up.

**See also:** [AvailFonts](#availfonts), [NewScaledDiskFont](#newscaleddiskfont), graphics.library OpenFont, graphics.library SetFont, graphics.library CloseFont

## AvailFonts
`LONG AvailFonts(STRPTR buffer, LONG bufBytes, LONG flags)` — LVO -36 (-$24)
Registers: buffer=A0, bufBytes=D0, flags=D1; result in D0

Fill a buffer with a list of the fonts in memory and/or on disk.

- **buffer** — memory for a `struct AvailFontsHeader` (`UWORD afh_NumEntries`) followed by that many
  `struct AvailFonts` (`UWORD af_Type`, `struct TextAttr af_Attr`), or `struct TAvailFonts` with
  `AFF_TAGGED`. The name strings live inside the same buffer. The prototype types it as `STRPTR`:
  cast.
- **bufBytes** — size of the buffer.
- **flags** — any of `AFF_MEMORY` ($0001, fonts in memory), `AFF_DISK` ($0002, fonts in FONTS:),
  `AFF_SCALED` ($0004, also list non-designed memory fonts), `AFF_BITMAP` ($0008, skip outline fonts),
  `AFF_TAGGED` ($10000, return TAvailFonts).
- **Result** — 0 on success. Otherwise the number of **extra** bytes needed: enlarge the buffer by
  that much and call again.

### Example
```c
LONG size = 1024, shortage;
struct AvailFontsHeader *afh;

for (;;) {
    afh = AllocVec(size, MEMF_ANY);
    if (!afh) break;
    shortage = AvailFonts((STRPTR)afh, size, AFF_MEMORY | AFF_DISK);
    if (shortage == 0) break;
    FreeVec(afh);
    size += shortage;
}
if (afh) {
    struct AvailFonts *af = (struct AvailFonts *)(afh + 1);
    for (UWORD i = 0; i < afh->afh_NumEntries; i++, af++) {
        /* af->af_Attr.ta_Name, af->af_Attr.ta_YSize, af->af_Type (AFF_MEMORY/AFF_DISK/...) */
    }
    FreeVec(afh);
}
```

### Gotchas
- A font found both in memory and on disk appears twice, once per `af_Type`.
- A disk entry only proves that the `.font` contents file lists it. The actual font file is not
  checked, so OpenDiskFont() can still fail.
- The TextAttr names point into your buffer. Copy what you need before freeing it.
- Scanning FONTS: is slow on floppies. Keep the result instead of calling it repeatedly.

**See also:** [OpenDiskFont](#opendiskfont), graphics.library OpenFont

## NewScaledDiskFont
`struct DiskFont * NewScaledDiskFont(struct TextFont *sourceFont, struct TextAttr *destTextAttr)` — LVO -54 (-$36)
Registers: sourceFont=A0, destTextAttr=A1; result in D0

Build a new font scaled from an open font to the size in a TextAttr.

- **sourceFont** — an open `struct TextFont` to scale from.
- **destTextAttr** — wanted attributes (`TextAttr` or `TTextAttr`), mainly `ta_YSize`.
- **Result** — pointer to a `struct DiskFontHeader` (the prototype says `struct DiskFont *`, a type
  that does not exist: cast it), or NULL. The font itself is `&dfh->dfh_TF`.

Since V36.

### Gotchas
- diskfont.library does not manage the result, and CloseFont() is not the way to free it. Free it
  with graphics StripFont(`&dfh->dfh_TF`) and then dos UnLoadSeg() on the segment in `dfh->dfh_Segment`.
  UnLoadSeg also frees the DiskFontHeader. Treating `dfh_Segment` as the BPTR for UnLoadSeg is unverified.
- May use the blitter. Glyphs that draw wholly outside their advance cell cannot be scaled.
- Prefer OpenDiskFont(), which scales on demand (V36+) and lets CloseFont() manage the font. Use this
  call only when you need a private scaled copy.

**See also:** [OpenDiskFont](#opendiskfont), graphics.library StripFont, dos.library UnLoadSeg

## NewFontContents
`struct FontContentsHeader * NewFontContents(BPTR fontsLock, STRPTR fontName)` — LVO -42 (-$2A)
Registers: fontsLock=A0, fontName=A1; result in D0

Build a FontContents array describing every size in a font's directory.

- **fontsLock** — dos.library Lock (BPTR) on the directory holding `<name>.font` and the `<name>/`
  directory, normally `FONTS:`.
- **fontName** — font name **with** the `.font` suffix (at most `MAXFONTNAME` = 32 bytes including
  `.font` and the NUL).
- **Result** — `struct FontContentsHeader *` (`fch_FileID` = `FCH_ID` $0F00 with `struct FontContents`
  entries, `TFCH_ID` $0F02 with `struct TFontContents`, or `OFCH_ID` $0F03 for outline fonts, then
  `fch_NumEntries` entries), or NULL: no `.font` suffix, name too long, DOS error, or no memory.

Since V34.

### Gotchas
- For font installers/editors that rewrite the `.font` contents file, not for applications.
- Free only with [DisposeFontContents](#disposefontcontents).

**See also:** [DisposeFontContents](#disposefontcontents), dos.library Lock

## DisposeFontContents
`VOID DisposeFontContents(struct FontContentsHeader *fontContentsHeader)` — LVO -48 (-$30)
Registers: fontContentsHeader=A1; no result

Free the FontContents array returned by NewFontContents.

- **fontContentsHeader** — pointer from [NewFontContents](#newfontcontents). **Passed in A1.**

Since V34.

### Gotchas
- Any other pointer crashes the machine.

**See also:** [NewFontContents](#newfontcontents)

## GetDiskFontCtrl
`LONG GetDiskFontCtrl(LONG tagid)` — LVO -60 (-$3C)
Registers: tagid=D0; result in D0

Read one of diskfont.library's global settings (DPI, cache, AvailFonts sorting).

- **tagid** — one `DFCTRL_` tag (diskfont/diskfonttag.h, `DFCTRL_BASE` = `TAG_USER + 0x0B000000`):
  `DFCTRL_XDPI`, `DFCTRL_YDPI` (device DPI, default 72), `DFCTRL_XDOTP`, `DFCTRL_YDOTP` (dot size,
  default 100), `DFCTRL_SYMSET` (unused), `DFCTRL_CACHE` (BOOL AvailFonts cache),
  `DFCTRL_SORTMODE` (`DFCTRL_SORT_OFF` 0, `DFCTRL_SORT_ASC` 1, `DFCTRL_SORT_DES` -1).
- **Result** — current value. Undefined for an unknown tag.

Since V45.

### Gotchas
- Meant only for the font preferences editor. Not semaphore protected, so concurrent Get/Set calls
  can give inconsistent values (no crash).
- In the NDK 3.9 headers `DFCTRL_SYMSET` and `DFCTRL_YDOTP` share the value `DFCTRL_BASE + 4`, so
  asking for one returns the other.

**See also:** [SetDiskFontCtrlA](#setdiskfontctrla)

## SetDiskFontCtrlA
`VOID SetDiskFontCtrlA(struct TagItem *taglist)` — LVO -66 (-$42)
Registers: taglist=A0; no result

Change diskfont.library's global settings from a tag list (font prefs editor only).

- **taglist** — `DFCTRL_` tags with new values (see [GetDiskFontCtrl](#getdiskfontctrl)), ended by
  `TAG_DONE`.

The varargs form is `SetDiskFontCtrl(tag, value, ..., TAG_DONE)` (inline macro with the Bartman
headers). Since V45.

### Gotchas
- Applications must not call it, and in particular must not toggle `DFCTRL_CACHE`: that choice
  belongs to the user through Font preferences.
- Not semaphore protected.

**See also:** [GetDiskFontCtrl](#getdiskfontctrl)
