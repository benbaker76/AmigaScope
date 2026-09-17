# vasm directives: sections and origin

Motorola-syntax vasm (`vasmm68k_mot`). Behaviour below was checked against the vasm
manual and by assembling test files with the vasm 1.9 bundled with amiga-debug and the
1.8k bundled with vscode-amiga-assembly, in default mode (no `-devpac`/`-phxass`).
Directive names are case-insensitive; section names and symbols are case-sensitive.

Hunk facts used below (NDK `dos/doshunks.i`): `HUNK_CODE` $3E9, `HUNK_DATA` $3EA,
`HUNK_BSS` $3EB; memory flags live in the top bits of each hunk size: `HUNKB_CHIP` 30,
`HUNKB_FAST` 31 (both set = an extra longword of attributes follows).

## SECTION
`section <name>[,<type>][,<memtype>]`

Start a section, or switch back to one with the same name, type and memory attribute.

- **name** — free text. vlink merges sections with the same name and type across objects.
- **type** — `code` (or `text`), `data`, `bss`. Omitted = a code section called `<name>`.
  Append `_c` (chip), `_f` (fast) or `_p` to the type instead of giving `memtype`.
- **memtype** — `chip`, `fast` or a 32-bit number. Only the hunk output modules use it:
  chip sets bit 30 of the hunk size, fast bit 31, other values are written as extended
  attributes. `-Felf` ignores it.

### Example
```asm
        section main,code               ; any RAM
start:  lea     copper,a0               ; absolute: copper is in another hunk
        move.l  a0,$dff080              ; COP1LC
        rts

        section gfx,data_c              ; chip RAM: the Copper must see it
copper: dc.w    $0180,$0000
        dc.w    $ffff,$fffe

        section vars,bss                ; zeroed, only its size is stored
frame:  ds.l    1
```

### Gotchas
- Reopening needs the SAME name, type and memory: after `section gfx,data_c`, a later
  `section gfx,data` or bare `section gfx` silently starts a second section (tested).
- Anything the custom chips read (copper lists, bitplanes, sprite/audio data, blitter
  buffers) must be in a `_c`/`chip` section or in `AllocMem(MEMF_CHIP)` memory.
- PC-relative references cannot cross sections in hunk format. `lea copper(pc),a0` to
  another section fails (vasm `-Fhunkexe` error 3005, vlink "Error 32 ... R_PC") unless
  vlink `-mrel` merges the two, which drags the code into chip RAM. Write the absolute
  form; vasm converts it to PC-relative by itself when the target is in the same section.
- A label name that is also a register name (`d2`, `a0`, `sp`) is parsed as the register:
  `lea d2(pc),a0` means `(d2,pc)`. Never name labels after registers.
- Bartman's gcc/elf2hunk flow (`-Felf`): the memory argument is lost. Name the section
  `.MEMF_CHIP` or `.<name>.MEMF_CHIP` (`.MEMF_FAST` for fast); elf2hunk makes it a chip
  hunk (tested). NOT `.data.MEMF_CHIP`: the linker folds `.data.*` into `.data` and the
  flag is lost (tested).

**See also:** [CODE_C](#code_c), [DATA_C](#data_c), [BSS_C](#bss_c), [ORG](#org),
[program structure](../topics/amiga-program-structure.md), [vasm and vlink](../topics/vasm-vlink.md)

## CODE
`code`

Switch to vasm's default code section (manual: same as `section code,code`).

The section name actually emitted differs by version: `.text` in vasm 1.9, `CODE` in 1.8k
(tested). Use an explicit `section <name>,code` when objects must merge by name in vlink.

**See also:** [SECTION](#section), [CSEG](#cseg), [TEXT](#text), [CODE_C](#code_c)

## CODE_C
`code_c`

Switch to a code section loaded into chip RAM.

Same as `section code_c,code,chip` (manual). Code rarely needs chip RAM; use it only for
code the custom chips must read (practically never) or for fixed-size tricks.

**See also:** [SECTION](#section), [CODE_F](#code_f), [DATA_C](#data_c)

## CODE_F
`code_f`

Switch to a code section that must load into fast RAM.

Same as `section code_f,code,fast`. The program will not load at all on a machine without
fast RAM (an A500 with chip RAM only), so prefer plain `code`.

**See also:** [SECTION](#section), [CODE_C](#code_c)

## CSEG
`cseg` · rejected with `-devpac`

Switch to the default code section; a synonym of CODE for other assemblers.

**See also:** [CODE](#code), [TEXT](#text)

## TEXT
`text`

Switch to the default code section; a synonym of CODE.

**See also:** [CODE](#code), [CSEG](#cseg)

## DATA
`data`

Switch to vasm's default initialised-data section (manual: `section data,data`).

Emitted name is `.data` in vasm 1.9, `DATA` in 1.8k (tested).

**See also:** [SECTION](#section), [DATA_C](#data_c), [DSEG](#dseg), [BSS](#bss)

## DATA_C
`data_c`

Switch to an initialised-data section loaded into chip RAM.

Same as `section data_c,data,chip` (manual). The home for copper lists, bitplane images,
sprite and audio data assembled into the program.

### Example
```asm
        data_c
logo:   incbin  "gfx/logo.raw"          ; raw bitplane data the chips will read
logo_end:
        even
```

### Gotchas
- vasm 1.9 names this section `data.MEMF_CHIP`, not `data_c` (tested); a later explicit
  `section data_c,data,chip` in the same file therefore opens a different section.

**See also:** [SECTION](#section), [BSS_C](#bss_c), [INCBIN](data.md#incbin)

## DATA_F
`data_f`

Switch to an initialised-data section that must load into fast RAM.

Same as `section data_f,data,fast`. Fails to load on chip-only machines.

**See also:** [SECTION](#section), [DATA_C](#data_c)

## DSEG
`dseg`

Switch to the default data section; a synonym of DATA (from the vasm manual, not prb28).

**See also:** [DATA](#data)

## BSS
`bss`

Switch to vasm's default uninitialised section (manual: `section bss,bss`).

Only `ds`/`dcb`-style space belongs here; the file stores the size, the loader provides
zeroed memory. Emitted name is `.bss` in vasm 1.9, `BSS` in 1.8k (tested).

### Gotchas
- vasm error 3019: Kickstart 1.x cannot zero BSS sections larger than 256K; clear big
  buffers yourself or allocate them with `AllocMem(...,MEMF_CLEAR)` when targeting 1.x.

**See also:** [SECTION](#section), [BSS_C](#bss_c), [DS](data.md#ds)

## BSS_C
`bss_c`

Switch to an uninitialised section loaded into chip RAM.

Same as `section bss_c,bss,chip`. Typical use: screen buffers and copper lists built at run
time.

### Example
```asm
        bss_c
screen: ds.b    320/8*256*5             ; 5 lores bitplanes
```

**See also:** [SECTION](#section), [DATA_C](#data_c)

## BSS_F
`bss_f`

Switch to an uninitialised section that must load into fast RAM.

Same as `section bss_f,bss,fast`. Fails to load on chip-only machines.

**See also:** [SECTION](#section), [BSS](#bss)

## ORG
`org <expression>`

Assemble the following code for a fixed absolute address.

- **expression** — the run address of the following block.

Inside a relocatable section the bytes stay in place in the hunk; only the labels get
absolute values and no relocations are generated (tested). With `-Fbin` it sets the load
origin. Any new `section` directive returns to relocatable mode (in `-devpac` mode the
previous section stays absolute).

### Example
```asm
        section main,code
start:  lea     payload,a0              ; where the bytes sit in the hunk
        lea     $70000,a1               ; where they must run
        move.w  #pl_end-pl_start-1,d0
.copy:  move.b  (a0)+,(a1)+
        dbf     d0,.copy
        jmp     pl_start                ; absolute $70000
payload:
        org     $70000
pl_start:
        move.w  #$0f00,$dff180
        bra.s   pl_start
pl_end:
```

### Gotchas
- Nothing copies the block for you; jumping to an ORG label before copying crashes.
- The optimizer still runs inside the block (`jmp` to a near label becomes `bra`).

**See also:** [RORG](#rorg), [SECTION](#section), [vasm and vlink](../topics/vasm-vlink.md)

## RORG
`rorg <expression>[,<fill>]`

Move the program counter to an offset from the start of the current section.

- **expression** — new section offset; must not be lower than the current one.
- **fill** — byte used for the gap, default 0.

### Example
```asm
        section boot,data
        dc.b    'D','O','S',0
        rorg    12,$ff                  ; pad to offset 12 with $ff
entry:  dc.b    0
```

**See also:** [ORG](#org), [CNOP](data.md#cnop), [DCB](data.md#dcb)

## OFFSET
`offset [<expression>]`

Open a dummy section whose labels become structure offsets and emit no bytes.

- **expression** — start offset (constant). Omitted: continue from where the previous
  offset block ended, or 0.

Leave it with any `section`/`code`/`data`/`bss` directive.

### Example
```asm
        offset  0
ob_x:   ds.w    1                       ; 0
ob_y:   ds.w    1                       ; 2
ob_img: ds.l    1                       ; 4
ob_SIZEOF:                              ; 8
        section main,code
        move.w  ob_x(a0),d0
```

### Gotchas
- No automatic alignment in default mode: `ds.b 1` followed by `ds.w 1` gives offsets 0
  and 1 (tested). Pad by hand, or assemble with `-align`/`-devpac`.

**See also:** [RS](structures.md#rs), [SO](structures.md#so),
[structure macros](../topics/macros-and-structures.md)

## PUSHSECTION
`pushsection`

Save the current section on vasm's section stack.

Pair with POPSECTION to drop a few lines into another section from inside a macro or an
include file without knowing which section the caller was in.

### Example
```asm
CHIPWORD macro                          ; emit a word into chip data, leave pointer in a0
        pushsection
        section gfx,data_c
.w\@:   dc.w    \1
        popsection
        lea     .w\@,a0
        endm
```

### Gotchas
- Rejected in `-devpac` mode.

**See also:** [POPSECTION](#popsection), [SECTION](#section)

## POPSECTION
`popsection`

Return to the section most recently saved with PUSHSECTION.

Rejected in `-devpac` mode.

**See also:** [PUSHSECTION](#pushsection)
