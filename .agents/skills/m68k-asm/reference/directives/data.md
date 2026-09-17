# vasm directives: data, space and alignment

Size qualifiers used below: `.b` 8 bit, `.w` 16, `.l` 32, `.q` 64, `.s` IEEE single (32),
`.d` IEEE double (64), `.x` IEEE extended (96), `.p` packed decimal (96).

**Alignment rule (default mode, tested):** instructions are auto-aligned to even addresses
(warning 51), data is NOT. A `dc.w`, `dc.l`, `ds.w`, `dcb.w` after an odd number of bytes
lands on an odd address. `-align` or `-devpac` turn on data alignment (warning 58). Put
`even` after every odd-length string, `dc.b` table or `incbin`.

## DC
`dc.<size> <exp>[,<exp>...]` · `dc <exp>` = `dc.w`

Store integer, string or float constants into the current section.

- **size** — `b w l q s d x p`. Missing size means `.w`.
- **exp** — numbers (`$` hex, `%` binary, `@` octal), labels, expressions, or quoted
  strings. In `dc.b` a string emits one byte per character; in `dc.w`/`dc.l` a quoted
  constant is packed big-endian (`dc.l 'ABCD'` = `$41424344`).
- Quotes: `"..."` or `'...'`; double the quote to embed it (`'it''s'`).

### Example
```asm
        section data,data
title:  dc.b    "SCORE ",0
        even
palette:
        dc.w    $000,$fff,$f00,$0f0     ; 12-bit RGB words
table:  dc.l    routine0,routine1       ; relocated 32-bit pointers
```

### Gotchas
- Backslash is a normal character by default: `"a\n"` is 3 bytes. Only `-esc` (or
  `-phxass`) enables C escapes. Write `10` for LF, `13` for CR.
- Float constants: the vasm 1.9 build bundled with amiga-debug 1.8.2 emitted zeros for
  `dc.s/dc.d/dc.x` and `fequ` (tested); the 1.8k build was correct and rejects `dc.p`.
  When in doubt, write floats as hex longwords.
- A 32-bit pointer to a label needs a relocation; that is fine in hunk and ELF output, but
  errors with `-pic`.

**See also:** [DCB](#dcb), [DS](#ds), [DR](#dr), [EVEN](#even), [INCBIN](#incbin)

## DCB
`dcb.<size> <count>[,<fill>]`

Emit `count` elements filled with `fill` (default 0).

- **size** — `b w l q s d x`; for `s/d/x` the fill may be a float constant.

### Example
```asm
sintab: dcb.w   256,0                   ; 256 zero words
stars:  dcb.b   64,$ff
```

**See also:** [BLK](#blk), [DS](#ds), [DC](#dc)

## BLK
`blk.<size> <count>[,<fill>]` · rejected with `-devpac`

Same as `dcb.<size> <count>,<fill>`, for sources from other assemblers.

**See also:** [DCB](#dcb)

## DS
`ds.<size> <count>`

Reserve `count` elements of space, zero-filled.

- **size** — `b w l q s d x`.
- In a BSS section nothing is stored in the file; in code/data sections zeros are emitted
  (the fill can be changed with the vasm option `-uspc=<value>`).

### Example
```asm
        section vars,bss
lives:  ds.w    1
buffer: ds.b    1024
bufend:
```

### Gotchas
- `ds.w 0` / `ds.l 0` do NOT align in default mode (tested); they do with `-devpac`
  (Devpac idiom, used e.g. by NDK `exec/macros.i`). Use `even` or `cnop 0,4` instead.

**See also:** [DCB](#dcb), [DX](#dx), [BSS](sections.md#bss), [RS](structures.md#rs)

## DX
`dx.<size> <count>` · rejected with `-devpac`

Reserve zeroed space that vasm tries to keep out of the file (data-bss part of a section).

When `dx` space is at the END of a code or data section, `-Fhunkexe` writes the full
size in the hunk header but stores only the initialised part (tested). If initialised
data follows, it behaves like `dcb.<size> <count>,0`.

### Gotchas
- Truncated sections need the OS 2.0+ loader (vasm manual, `-databss`); do not use for
  Kickstart 1.x targets (vlink `-kick1` or `-Z` avoids data-bss when linking).

**See also:** [DS](#ds), [vasm and vlink](../topics/vasm-vlink.md)

## DR
`dr.<b|w|l> <exp>[,<exp>...]` · rejected with `-devpac` and `-phxass`

Store `exp - address_of_this_element` for each operand.

### Example
```asm
rel:    dr.w    target0,target1         ; each value relative to its own word
```

### Gotchas
- For a normal jump table relative to the table start use `dc.w label-table`:
  ```asm
          add.w   d0,d0
          move.w  .tab(pc,d0.w),d0
          jmp     .tab(pc,d0.w)
  .tab:   dc.w    h0-.tab,h1-.tab
  ```
- `dr.l` to a symbol in another section or file needs a 32-bit PC-relative relocation:
  `HUNK_RELRELOC32` ($3FD) in hunk executables (tested), which NDK `dos/doshunks.i` marks
  as new for V39 and which `-kick1hunks` rejects; `R_68K_PC32` with `-Felf`,
  which elf2hunk cannot convert across sections.

**See also:** [DC](#dc), [vasm and vlink](../topics/vasm-vlink.md)

## DB
`db <exp>[,<exp>...]` · rejected with `-devpac` and `-phxass`

Same as `dc.b`, for ArgAsm/BAsm/Macro68/ProAsm sources.

**See also:** [DC](#dc), [DW](#dw), [DL](#dl)

## DW
`dw <exp>[,<exp>...]` · rejected with `-devpac` and `-phxass`

Same as `dc.w`, for ArgAsm/BAsm/Macro68/ProAsm sources.

**See also:** [DC](#dc), [DB](#db)

## DL
`dl <exp>[,<exp>...]` · rejected with `-devpac` and `-phxass`

Same as `dc.l`, for ArgAsm/BAsm/Macro68/ProAsm sources.

**See also:** [DC](#dc), [DB](#db)

## EVEN
`even`

Pad with one zero byte if the address is odd (same as `cnop 0,2`).

Use after every odd-length `dc.b`, string or `incbin` that is followed by words, longs or
code. A label on its own line before an auto-aligned instruction keeps the ODD address
(tested), so `bsr`/`jmp` to it would jump into the pad byte.

### Example
```asm
name:   dc.b    "graphics.library",0    ; 17 bytes
        even
next:   moveq   #0,d0
```

**See also:** [ODD](#odd), [CNOP](#cnop), [ALIGN](#align)

## ODD
`odd` · rejected with `-devpac`

Align to an odd address (same as `cnop 1,2`).

### Gotchas
- Known vasm bug: on an address that is already odd it still inserts 2 bytes (tested).

**See also:** [EVEN](#even), [CNOP](#cnop)

## ALIGN
`align <bits>` · rejected with `-devpac` and `-phxass`

Pad with zero bytes until the low `bits` bits of the address are zero.

`align 1` = word boundary, `align 2` = longword boundary, `align 3` = 8 bytes. Pads with
zeros even in code sections (tested).

**See also:** [CNOP](#cnop), [EVEN](#even)

## CNOP
`cnop <offset>,<alignment>`

Pad to a multiple of `alignment`, then add `offset` more padding bytes.

- In code sections the padding is NOP words ($4E71, change with `-cnop=<code>`); in data
  sections and in `-devpac` mode it is zero bytes.

### Example
```asm
        cnop    0,4                     ; longword-align a table
lvotab: dc.l    0,0,0
```

### Gotchas
- In code sections (default mode) a non-zero `offset` is filled with `offset` NOP WORDS,
  i.e. twice the bytes asked for (tested on 1.8k and 1.9). Use only `cnop 0,n` in code.

**See also:** [EVEN](#even), [ALIGN](#align), [RORG](sections.md#rorg)

## INCBIN
`incbin <file>[,<offset>[,<length>]]`

Insert the raw bytes of a file at this position.

- **offset** — bytes to skip at the start of the file.
- **length** — maximum bytes to read.
- Search order: current directory, main source directory, `-I` paths, `incdir` paths.
  Relative paths are NOT resolved against the directory of an included file.

### Example
```asm
        section gfx,data_c
module: incbin  "music/tune.p61"
        even
pic:    incbin  "gfx/title.bin",8,320/8*256*5   ; skip 8-byte header, take 5 planes
        even
```

### Gotchas
- Graphics, samples and music the custom chips play directly must go into a `_c`
  section.
- The file size is whatever it is: follow with `even` before any word data or code.

**See also:** [INCLUDE](include-and-output.md#include), [INCDIR](include-and-output.md#incdir),
[DATA_C](sections.md#data_c)
