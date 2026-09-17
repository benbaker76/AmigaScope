# graphics.library: text and fonts

A font is a `struct TextFont` on the system font list; you get one with [OpenFont](#openfont)
(fonts already in memory: ROM `topaz.font` or fonts loaded earlier) or diskfont.library
OpenDiskFont (loads from `FONTS:`), describe the request with a `struct TextAttr`, attach it to a
RastPort with [SetFont](#setfont) and render with [Move](drawing.md#move) +
[Text](#text). Text is drawn with its BASELINE on the current pen position `cp_y`; measure first
with [TextLength](#textlength) / [TextExtent](#textextent) / [TextFit](#textfit). Pens and draw mode
come from the RastPort ([rastport basics](concepts.md#rastport-basics)). Every OpenFont needs a
matching [CloseFont](#closefont). Style and flag bits (graphics/text.h, text.i):
`FS_NORMAL` 0, `FSF_UNDERLINED` $01, `FSF_BOLD` $02, `FSF_ITALIC` $04, `FSF_EXTENDED` $08,
`FSF_COLORFONT` $40, `FSF_TAGGED` $80; `FPF_ROMFONT` $01, `FPF_DISKFONT` $02, `FPF_REVPATH` $04,
`FPF_TALLDOT` $08, `FPF_WIDEDOT` $10, `FPF_PROPORTIONAL` $20, `FPF_DESIGNED` $40, `FPF_REMOVED` $80
(asm: same names from BITDEF, plus `FSB_`/`FPB_` bit numbers).

## OpenFont
`struct TextFont * OpenFont(struct TextAttr *textAttr)` — LVO -72 (-$48)
Registers: textAttr=A0; result in D0

Find and open the best matching font that is already in memory.

- **textAttr** — `struct TextAttr`: `ta_Name` ("topaz.font"), `ta_YSize` (pixel height),
  `ta_Style` (`FSF_` bits), `ta_Flags` (`FPF_` bits); or a `struct TTextAttr` (same plus
  `tta_Tags`, with `FSF_TAGGED` set in the style). asm: `ta_Name`, `ta_YSize`, `ta_Style`,
  `ta_Flags`, `ta_SIZEOF` / `tta_Tags`, `tta_SIZEOF`.
- **Result** — TextFont pointer, or NULL if no font of that name is in memory. If the name
  matches but size/style do not, the nearest font is returned: check `tf_YSize`.

### Example
```c
/* print a label with ROM topaz 8, top-left corner at (x,y) */
BOOL draw_label(struct RastPort *rp, WORD x, WORD y, CONST_STRPTR msg)
{
    struct TextAttr ta = { (STRPTR)"topaz.font", 8, FS_NORMAL, FPF_ROMFONT };
    struct TextFont *old = rp->Font;
    struct TextFont *font = OpenFont(&ta);
    ULONG len = 0;

    while (msg[len])
        len++;
    if (!font)
        return FALSE;
    SetFont(rp, font);
    SetAPen(rp, 1);
    SetDrMd(rp, JAM1);
    Move(rp, x, y + rp->TxBaseline);      /* Text() draws on the baseline */
    Text(rp, msg, len);                   /* count = characters */
    SetFont(rp, old);                     /* never leave a closed font in rp */
    CloseFont(font);
    return TRUE;
}
```

### Gotchas
- Only searches the in-memory font list. Fonts in `FONTS:` need diskfont.library OpenDiskFont
  (which adds them to the list); OpenFont then finds them too.
- From V39 pass OpenFont the same TextAttr/TTextAttr that was used for OpenDiskFont; before V39
  any font with the same Y size matched regardless of DPI/dot size.
- Every successful OpenFont must be balanced by exactly one [CloseFont](#closefont).
- Without `FPF_DESIGNED` in `ta_Flags`, V36+ may give you a font scaled from another size.

**See also:** [CloseFont](#closefont), [SetFont](#setfont), [AskFont](#askfont),
[WeighTAMatch](#weightamatch), diskfont OpenDiskFont

## CloseFont
`VOID CloseFont(struct TextFont *textFont)` — LVO -78 (-$4E)
Registers: textFont=A1; no result

Release a font obtained with OpenFont or OpenDiskFont.

- **textFont** — pointer returned by [OpenFont](#openfont) or diskfont OpenDiskFont.

### Gotchas
- Remove it from every RastPort first ([SetFont](#setfont) another font): after CloseFont the
  memory of a disk font may be freed once nobody uses it.
- Close each font exactly once per successful open.

**See also:** [OpenFont](#openfont), diskfont OpenDiskFont

## SetFont
`LONG SetFont(struct RastPort *rp, CONST struct TextFont *textFont)` — LVO -66 (-$42)
Registers: rp=A1, textFont=A0; result in D0

Make a font the current font of a RastPort and reset its soft styles.

- **rp** — RastPort to change (sets `Font`, `TxHeight`, `TxWidth`, `TxBaseline`, ...).
- **textFont** — font from [OpenFont](#openfont) or OpenDiskFont.
- **Result** — see Gotchas; do not rely on it.

### Gotchas
- NDK 3.9 prototype returns `LONG`; the autodoc documents `void`. Ignore D0.
- Do not call `SetFont(rp, NULL)`: text calls on a NULL font crash and some releases touch low
  memory. Leave a valid font in the RastPort instead.
- Any previous [SetSoftStyle](#setsoftstyle) effect is cleared.
- V36+: SetFont on a font you built in your own code (not OpenFont()ed) allocates a 24-byte
  extension that is never freed unless you call [StripFont](#stripfont) on it.
- V36+ silently patches fonts with only one of `tf_CharSpace`/`tf_CharKern` set, or with no
  spacing tables and a `tf_CharLoc` width larger than `tf_XSize`.

**See also:** [OpenFont](#openfont), [StripFont](#stripfont), [AskFont](#askfont)

## AskFont
`VOID AskFont(struct RastPort *rp, struct TextAttr *textAttr)` — LVO -474 (-$1DA)
Registers: rp=A1, textAttr=A0; no result

Fill a TextAttr with the name, size, style and flags of a RastPort's current font.

- **rp** — RastPort to query.
- **textAttr** — plain `struct TextAttr` to fill (a TTextAttr's tags are not filled in).

**See also:** [OpenFont](#openfont), [SetFont](#setfont)

## Text
`LONG Text(struct RastPort *rp, CONST_STRPTR string, ULONG count)` — LVO -60 (-$3C)
Registers: rp=A1, string=A0, count=D0; result in D0

Render a run of characters at the current pen position and advance cp_x.

- **rp** — RastPort with a valid font; uses FgPen/BgPen, DrawMode, soft style.
- **string** — characters to draw; no control codes are interpreted (no newline handling).
- **count** — number of characters (only the low 16 bits are used); 0 draws nothing.
- **Result** — see Gotchas; do not rely on it.

### Example
```asm
; a1 = RastPort, a0 = 0-terminated string, d0/d1 = x/y of the TOP-left corner
PrintAt:
        movem.l a2-a3/a6,-(sp)
        move.l  _GfxBase,a6
        move.l  a0,a2                   ; keep string
        move.l  a1,a3                   ; keep RastPort
        add.w   rp_TxBaseline(a3),d1    ; Text draws on the baseline
        jsr     _LVOMove(a6)            ; a1 = rp, d0/d1 = x/y
        move.l  a2,a0
        moveq   #-1,d0
.len:   addq.l  #1,d0                   ; d0 = strlen
        tst.b   (a0)+
        bne.s   .len
        move.l  a2,a0                   ; string
        move.l  a3,a1                   ; rp
        jsr     _LVOText(a6)            ; d0 = character count
        movem.l (sp)+,a2-a3/a6
        rts
```

### Gotchas
- The y of [Move](drawing.md#move) is the baseline: `Move(rp, x, y + rp->TxBaseline)` puts the
  top of the characters at y.
- After the call `cp_x` is advanced by the text width (clipped to the RastPort edge if the text
  runs past it, so it is not always old x + [TextLength](#textlength)); `cp_y` is unchanged.
- NDK 3.9 prototype returns `LONG`; the autodoc documents `void`.
- JAM1 draws only the glyph pixels; JAM2 also fills the character cells with BgPen.
- May use the blitter. Reversing text direction through `TxSpacing` is not supported.
- V34 and earlier: strings wider than 1008 pixels were cut, and trailing characters extending
  right of the start/end positions could be clipped.

**See also:** [TextLength](#textlength), [TextExtent](#textextent), [Move](drawing.md#move),
[SetFont](#setfont), [SetABPenDrMd](rastport-attrs.md#setabpendrmd)

## TextLength
`WORD TextLength(struct RastPort *rp, CONST_STRPTR string, ULONG count)` — LVO -54 (-$36)
Registers: rp=A1, string=A0, count=D0; result in D0

Return how many pixels cp_x would advance if the string were drawn with Text.

- **rp** — RastPort whose font, style and `TxSpacing` are used.
- **string** — characters to measure.
- **count** — number of characters; 0 gives 0.
- **Result** — width in pixels (WORD). Excludes negative kerning before the first character and
  any clipping.

### Example
```c
/* centre a string horizontally inside [left,right] on baseline y */
void centre_text(struct RastPort *rp, WORD left, WORD right, WORD y,
                 CONST_STRPTR s, ULONG n)
{
    WORD w = TextLength(rp, s, n);
    Move(rp, left + ((right - left + 1) - w) / 2, y);
    Text(rp, s, n);
}
```

### Gotchas
- Before V36 only the low word of D0 was valid (not sign-extended): asm code should use the
  word (`ext.l` if it needs a long).
- A total width that overflows 16 bits is computed wrongly.
- For the real pixel box (italic overhang, kerning) use [TextExtent](#textextent).

**See also:** [TextExtent](#textextent), [TextFit](#textfit), [Text](#text)

## TextExtent
`WORD TextExtent(struct RastPort *rp, CONST_STRPTR string, LONG count, struct TextExtent *textExtent)` — LVO -690 (-$2B2)
Registers: rp=A1, string=A0, count=D0, textExtent=A2; result in D0

Compute the advance and the bounding box a string would render into.

- **rp** — RastPort with the font/style.
- **string**, **count** — characters and their number (0 = empty).
- **textExtent** — `struct TextExtent` to fill: `te_Width` (same as [TextLength](#textlength)),
  `te_Height` (= `tf_YSize`), `te_Extent` (a `struct Rectangle` relative to the current
  position on the baseline): `MinX` left offset (often 0), `MinY` = -`tf_Baseline`, `MaxX` right
  edge (often `te_Width`-1), `MaxY` = `tf_YSize` - `tf_Baseline` - 1. asm: `te_Width`,
  `te_Height`, `te_Extent` (8 bytes MinX,MinY,MaxX,MaxY), `te_SIZEOF`.
- **Result** — NDK 3.9 prototype says `WORD`; the autodoc documents no return value. Use the
  structure.

Since V36.

### Gotchas
- `te_Extent` coordinates are relative to the baseline pen position, so `MinY` is negative.
- The autodoc describes `MaxX` as "the left side"; it is the right edge of the box.

**See also:** [TextLength](#textlength), [TextFit](#textfit), [FontExtent](#fontextent)

## TextFit
`ULONG TextFit(struct RastPort *rp, CONST_STRPTR string, ULONG strLen, CONST struct TextExtent *textExtent, CONST struct TextExtent *constrainingExtent, LONG strDirection, ULONG constrainingBitWidth, ULONG constrainingBitHeight)` — LVO -696 (-$2B8)
Registers: rp=A1, string=A0, strLen=D0, textExtent=A2, constrainingExtent=A3, strDirection=D1, constrainingBitWidth=D2, constrainingBitHeight=D3; result in D0

Count how many characters of a string fit into a given pixel box.

- **rp** — RastPort with the font/style.
- **string** — start of the string, or its LAST character when `strDirection` is -1.
- **strLen** — number of characters available (0 = none).
- **textExtent** — receives the extent of the characters that fit.
- **constrainingExtent** — NULL, or a TextExtent box (relative to the pen position) the text
  must stay inside; must include x = 0.
- **strDirection** — 1 = fit from the start forwards, -1 = fit backwards from the end. No other
  value is valid.
- **constrainingBitWidth**, **constrainingBitHeight** — box size in pixels, 0..32767.
- **Result** — number of characters that fit (0 with an empty extent if none, or if the
  RastPort's `TxSpacing` reverses the text path).

Since V36.

### Example
```c
/* how many chars of s fit into a gadget 100 pixels wide */
ULONG chars_that_fit(struct RastPort *rp, CONST_STRPTR s, ULONG len)
{
    struct TextExtent te;
    ULONG w = 100;
    if (((struct GfxBase *)GfxBase)->LibNode.lib_Version < 39 &&
        (rp->Font->tf_Flags & FPF_PROPORTIONAL))
        w++;                              /* V37 bug: one char too few */
    return TextFit(rp, s, len, &te, NULL, 1, w, rp->TxHeight);
}
```

### Gotchas
- V37: returns one character too few for proportional fonts; pass `constrainingBitWidth + 1`
  as a workaround there. Fixed in V39.
- For a right-aligned fit pass a pointer to the last character and `strDirection` -1.

**See also:** [TextExtent](#textextent), [TextLength](#textlength), [Text](#text)

## FontExtent
`VOID FontExtent(CONST struct TextFont *font, struct TextExtent *fontExtent)` — LVO -762 (-$2FA)
Registers: font=A0, fontExtent=A1; no result

Fill a TextExtent with the maximum character box of a font (no RastPort needed).

- **font** — the TextFont to measure.
- **fontExtent** — TextExtent to fill with the bounding extent over all characters.

Since V36.

### Gotchas
- Uses the plain font: soft styles (bold/italic from [SetSoftStyle](#setsoftstyle)) and
  `TxSpacing` are not included, unlike [TextExtent](#textextent).
- `te_Width` is negative only for `FPF_REVPATH` fonts.

**See also:** [TextExtent](#textextent)

## AskSoftStyle
`ULONG AskSoftStyle(struct RastPort *rp)` — LVO -84 (-$54)
Registers: rp=A1; result in D0

Return the style bits that can be generated algorithmically for the current font.

- **rp** — RastPort whose font is examined.
- **Result** — mask of `FSF_` bits that [SetSoftStyle](#setsoftstyle) may change (style bits
  built into the font are excluded; undefined bits are returned set).

**See also:** [SetSoftStyle](#setsoftstyle)

## SetSoftStyle
`ULONG SetSoftStyle(struct RastPort *rp, ULONG style, ULONG enable)` — LVO -90 (-$5A)
Registers: rp=A1, style=D0, enable=D1; result in D0

Turn algorithmic bold/italic/underline on or off for a RastPort's current font.

- **rp** — RastPort to change.
- **style** — new `FSF_` bits (`FSF_BOLD`, `FSF_ITALIC`, `FSF_UNDERLINED`, ...).
- **enable** — which bits of `style` to apply; pass `AskSoftStyle(rp)` (bits outside that mask
  are ignored).
- **Result** — the resulting total style (font's intrinsic style plus soft style).

### Example
```c
void bold_on(struct RastPort *rp)
{
    SetSoftStyle(rp, FSF_BOLD, AskSoftStyle(rp));
}
```

### Gotchas
- A bit that the font already has intrinsically cannot be switched off; check the result.
- [SetFont](#setfont) resets the soft style.

**See also:** [AskSoftStyle](#asksoftstyle), [SetFont](#setfont)

## AddFont
`VOID AddFont(struct TextFont *textFont)` — LVO -480 (-$1E0)
Registers: textFont=A1; no result

Add a TextFont you built or loaded yourself to the public system font list.

- **textFont** — complete TextFont (name in `tf_Message.mn_Node.ln_Name`) in public memory.

### Gotchas
- The font structure and its data must stay valid until it has been successfully removed with
  [RemFont](#remfont) and no longer has users.
- Sets `tf_Accessors` to 0.

**See also:** [RemFont](#remfont), [OpenFont](#openfont)

## RemFont
`VOID RemFont(struct TextFont *textFont)` — LVO -486 (-$1E6)
Registers: textFont=A1; no result

Remove a font from the system list so no new OpenFont finds it.

- **textFont** — font previously added with [AddFont](#addfont).

### Gotchas
- Programs that already opened the font keep their pointer: do not free the font while
  `tf_Accessors` is non-zero.
- The extension flag `TE0F_NOREMFONT` (`tfe_Flags0`, text.h) marks fonts that refuse RemFont.

**See also:** [AddFont](#addfont)

## ExtendFont
`ULONG ExtendFont(struct TextFont *font, CONST struct TagItem *fontTags)` — LVO -816 (-$330)
Registers: font=A0, fontTags=A1; result in D0

Make sure a font has its tf_Extension (TextFontExtension) built.

- **font** — the TextFont.
- **fontTags** — NULL for defaults, or a tag list; the only defined tag is `TA_DeviceDPI`
  (`1|TAG_USER`, data = X DPI in the high word, Y DPI in the low word).
- **Result** — 1 if the font is extended, 0 on failure.

Since V36. The varargs form `ExtendFontTags(font, tag, ...)` exists from V39 (missing from
amiga.lib before V39).

**See also:** [StripFont](#stripfont), [SetFont](#setfont)

## StripFont
`VOID StripFont(struct TextFont *font)` — LVO -822 (-$336)
Registers: font=A0; no result

Remove the tf_Extension that V36+ graphics attached to a font.

- **font** — TextFont whose extension should be freed.

Since V36.

### Gotchas
- Call it on fonts that live in your own code/data (never OpenFont()ed) after using them with
  [SetFont](#setfont), otherwise 24 bytes leak.

**See also:** [ExtendFont](#extendfont), [SetFont](#setfont)

## ClearEOL
`VOID ClearEOL(struct RastPort *rp)` — LVO -42 (-$2A)
Registers: rp=A1; no result

Clear from the pen position to the right edge, one text line high.

- **rp** — RastPort; the cleared strip is `TxHeight` high and positioned from the baseline so a
  line of text at the pen position would fall inside it.

Cleared pixels get colour 0, or BgPen when the draw mode is JAM2.

### Gotchas
- The autodoc says BgPen is used when "DrawMode is 2"; `JAM2` is 1 and `COMPLEMENT` is 2. Expect
  BgPen with JAM2 (unverified).
- May use the blitter.

**See also:** [ClearScreen](#clearscreen), [Text](#text), [SetRast](drawing.md#setrast)

## ClearScreen
`VOID ClearScreen(struct RastPort *rp)` — LVO -48 (-$30)
Registers: rp=A1; no result

Clear from the pen position to the end of the line, then everything below it.

- **rp** — RastPort; does a [ClearEOL](#cleareol), then clears the full width from below that
  strip to the bottom.

Cleared pixels get colour 0, or BgPen when the draw mode is JAM2 (same caveat as ClearEOL).

### Gotchas
- May use the blitter. To clear the whole RastPort use [SetRast](drawing.md#setrast) or
  [EraseRect](drawing.md#eraserect).

**See also:** [ClearEOL](#cleareol), [SetRast](drawing.md#setrast)

## WeighTAMatch

Private since V39 -- font-matching metric used internally by OpenFont and OpenDiskFont.

It returned how well a TextAttr matches a candidate font (up to `MAXFONTMATCHWEIGHT`, 32767, for
a perfect match; 0 = unsuitable). Public in graphics.library V36-V37, declared system private
from V39: NDK 3.9 has no prototype or `_LVO` symbol for it and the fd file lists its slot as
`graphicsPrivate6`. Do not call it; let [OpenFont](#openfont) / diskfont OpenDiskFont choose.

**See also:** [OpenFont](#openfont)
