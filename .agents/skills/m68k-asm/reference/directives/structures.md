# vasm directives: structure and stack-frame offsets

Three independent counters generate offset symbols without emitting bytes:
`__RS` (RS family, Devpac style), `__SO` (SO family) and `__FO` (FO family, counts DOWN
for LINK frames). Each can be read as a normal symbol. In default mode they spring into
existence at 0 when first used; `-devpac` predefines all three as 0.

**No alignment (default mode, tested):** `rs.w` after an odd count lands on an odd offset,
and `rs.w 0` does not align either. Only `-devpac`/`-align` align. Pad by hand so the
layout matches the C structure or the NDK include you mirror. For OS structures use the
NDK includes themselves (see the [structure macros topic](../topics/macros-and-structures.md)).

## RS
`<label> rs.<size> <count>`

Give `label` the current `__RS` value, then advance `__RS` by size x count.

- **size** — `b w l q s d x` (1, 2, 4, 8, 4, 8, 12 bytes). The manual also lists `p`,
  but 1.9 rejects `.p` here (error 1002, tested).
- `rs.b 0` (or any size with count 0) just names the current offset: use it for SIZEOF.

### Example
```asm
        rsreset
ob_x      rs.w  1                       ; 0
ob_y      rs.w  1                       ; 2
ob_flags  rs.b  1                       ; 4
          rs.b  1                       ; pad: keep the next field even
ob_image  rs.l  1                       ; 6
ob_SIZEOF rs.b  0                       ; 10

        section main,code
        move.w  ob_x(a0),d0
        lea     ob_SIZEOF(a0),a0        ; next object
        section objs,bss
objects: ds.b   ob_SIZEOF*32
```

### Gotchas
- Forgetting the pad byte after an odd `rs.b` shifts every following field by one and
  makes word/long fields odd offsets.

**See also:** [RSRESET](#rsreset), [RSSET](#rsset), [SO](#so), [OFFSET](sections.md#offset)

## RSRESET
`rsreset`

Set `__RS` to 0 before starting a new structure.

**See also:** [RS](#rs), [RSSET](#rsset)

## RSSET
`rsset <expression>`

Set `__RS` to a constant, e.g. to extend a structure after a known header size.

### Example
```asm
        rsset   34                      ; LIB_SIZE from exec/libraries.i
mylib_Flags rs.w 1                      ; 34
```

**See also:** [RS](#rs), [RSRESET](#rsreset)

## RSEVEN
`rseven` · not available in vasm 1.8k/1.9

Align `__RS` to an even value (newer vasm manual); unknown mnemonic on the bundled builds.

Use `rs.b 1` padding instead (tested).

**See also:** [RS](#rs)

## SO
`<label> so.<size> <count>`

Give `label` the current `__SO` value, then advance `__SO` by size x count.

Identical to RS but on its own counter, so two structures can be built interleaved.

### Example
```asm
        clrso
snd_ptr   so.l  1                       ; 0
snd_len   so.w  1                       ; 4
snd_per   so.w  1                       ; 6
snd_SIZE  so.b  0                       ; 8
```

**See also:** [CLRSO](#clrso), [SETSO](#setso), [RS](#rs)

## CLRSO
`clrso` · rejected with `-devpac`

Set `__SO` to 0.

**See also:** [SO](#so)

## SETSO
`setso <expression>` · rejected with `-devpac`

Set `__SO` to a constant expression.

**See also:** [SO](#so), [CLRSO](#clrso)

## FO
`<label> fo.<size> <count>`

Move `__FO` down by size x count, then give `label` the new (negative) value.

Built for LINK stack frames: locals sit at negative offsets from the frame pointer.

### Example
```asm
        clrfo
loc_x   fo.w    1                       ; -2
loc_ptr fo.l    1                       ; -6
FRAME   equ     __FO                    ; -6 (EQU keeps this value)

        section main,code
func:   link    a5,#FRAME
        move.w  d0,loc_x(a5)
        move.l  a0,loc_ptr(a5)
        ; ...
        unlk    a5
        rts
```

### Gotchas
- The vasm manual and prb28 page say the label gets the value BEFORE the decrement; both
  bundled builds (1.8k, 1.9) assign AFTER it (first `fo.l 1` = -4, tested). Check with
  `printv` if you port Devpac sources that rely on the other order.
- Keep `__FO` even (pad `fo.b` fields) or LINK leaves an odd stack pointer.

**See also:** [CLRFO](#clrfo), [SETFO](#setfo), [CARGS](listing-and-misc.md#cargs)

## CLRFO
`clrfo` · rejected with `-devpac`

Set `__FO` to 0.

**See also:** [FO](#fo)

## SETFO
`setfo <expression>` · rejected with `-devpac`

Set `__FO` to a constant expression, e.g. to leave room for saved registers.

**See also:** [FO](#fo), [CLRFO](#clrfo)
