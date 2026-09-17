# vasm directives: symbols, linkage and local labels

Source-line rules (mot syntax): a label starts in column 1 or ends with `:`; a mnemonic or
directive must NOT start in column 1. Symbols are case-sensitive (`-nocase` changes that),
mnemonics and directives are not. Without `-spaces`, a blank inside the operand field
starts the comment: `dc.w 1 + 2` assembles `dc.w 1`.

## EQU
`<symbol> equ <expression>` · `<symbol> = <expression>`

Define a constant symbol; defining it a second time is an error.

- `=` is an exact synonym (also refuses redefinition, tested).
- The symbol may carry a colon: `PLANES: equ 5`.
- `-D<name>[=<value>]` on the command line defines one too (value defaults to 1).

### Example
```asm
WIDTH   equ     320
HEIGHT  =       256
PLANES  equ     5
BPLSIZE equ     WIDTH/8*HEIGHT
```

### Gotchas
- A symbol used in a conditional must already be defined at that line (vasm reads the
  source once): `if LATER` before `LATER equ 1` is error 31 "expression must be constant".
- A typo in an EQU name does not error: without `-x` every undefined symbol is silently
  imported as an external and only fails at link time (tested). Always assemble with `-x`.

**See also:** [SET](#set), [FEQU](#fequ), [EQUR](#equr), [IFD](conditional.md#ifd)

## SET
`<symbol> set <expression>`

Define a symbol that may be assigned again later.

A symbol created with `equ`/`=` cannot be `set`, and vice versa (both error 68, tested).
Use SET for assembly-time counters in macros and REPT blocks.

### Example
```asm
OFS     set     0
        rept    4
        dc.w    OFS
OFS     set     OFS+40
        endr                            ; 0,40,80,120
```

**See also:** [EQU](#equ), [REPT](macros-repeat.md#rept)

## FEQU
`<symbol> fequ.<s|d|x|p> <expression>`

Define a floating-point constant symbol (the size extension is ignored).

### Gotchas
- The vasm 1.9 build bundled with amiga-debug 1.8.2 evaluated float constants to 0 in
  tests; 1.8k was correct. Check the output or avoid floats in data.

**See also:** [EQU](#equ), [DC](data.md#dc)

## EQUR
`<symbol> equr <Rn>`

Give a data or address register an alias name.

The alias must be defined before its first use. Redefining it needs `-regsymredef`.

### Example
```asm
custom  equr    a5
        lea     $dff000,custom
        move.w  #$7fff,$96(custom)       ; DMACON
```

**See also:** [REG](#reg), [EQU](#equ)

## REG
`<symbol> reg <reglist>` · `<symbol> equrl <reglist>`

Name a register list for MOVEM.

- **reglist** — registers separated by `/`, ranges with `-` (`d2-d7/a2-a6`), or a 16-bit
  mask constant (d0 = bit 0 ... a7 = bit 15).

### Example
```asm
SAVED   reg     d2-d7/a2-a6
main:   movem.l SAVED,-(sp)
        ; ...
        movem.l (sp)+,SAVED
        rts
```

### Gotchas
- NDK `exec/macros.i` PUSHM/POPM (which build REG names with `\*VALOF`) do not assemble
  in vasm (tested); use a REG symbol directly.

**See also:** [EQUR](#equr), [FREG](#freg)

## FEQUR
`<symbol> fequr <FPn>` · vasm 1.9 (1.8k: error 2045)

Give an FPU register an alias name; define it before use.

**See also:** [FREG](#freg), [EQUR](#equr), [FPU](listing-and-misc.md#fpu)

## FREG
`<symbol> freg <fp-reglist>` · `<symbol> fequrl <fp-reglist>` · vasm 1.9 (1.8k: error 2067)

Name an FPU register list for FMOVEM (`fp0-fp7`, `fp2/fp4`, or an 8-bit mask).

**See also:** [FEQUR](#fequr), [REG](#reg)

## XDEF
`xdef <symbol>[,<symbol>...]`

Export symbols so other objects can reference them at link time.

Labels are local to the object unless exported. A label written with a double colon
(`name::`) is exported too. `global <symbol>` is also accepted by vasm 1.8k/1.9 (tested,
not in the manual; rejected in `-devpac`).

### Example
```asm
        xdef    InitGfx
InitGfx:
        moveq   #0,d0
        rts
VBlank::                                ; exported by the double colon
        rts
```

### Gotchas
- C symbol spelling depends on the compiler: m68k-amiga-elf-gcc (Bartman) emits the plain
  name (`foo`, tested with objdump), while Bartman's template names its vasm routine
  `_doynaxdepack_vasm` and calls it by that exact name. Check with `objdump -t` or
  `vlink -M` instead of guessing an underscore prefix.

**See also:** [XREF](#xref), [PUBLIC](#public), [WEAK](#weak)

## XREF
`xref <symbol>[,<symbol>...]`

Declare symbols that another object or library defines.

With `-Fhunk`/`-Felf` the references become relocations resolved by the linker.
`-Fhunkexe` has no linker step: any remaining external is error 3009 (tested).

### Gotchas
- vasm imports undefined symbols automatically unless `-x` is given, so XREF is
  documentation plus a guard; with `-x`, a symbol used but neither defined nor XREF'd is an
  error.

**See also:** [XDEF](#xdef), [NREF](#nref), [vasm and vlink](../topics/vasm-vlink.md)

## PUBLIC
`public <symbol>[,<symbol>...]` · rejected with `-devpac`

Mark symbols external: exported if defined in this file, imported otherwise.

**See also:** [XDEF](#xdef), [XREF](#xref)

## WEAK
`weak <symbol>[,<symbol>...]` · rejected with `-devpac` and `-phxass`

Export a symbol that any normal global definition of the same name overrides.

An undefined weak symbol evaluates to 0. The hunk output module does not support weak
symbols and treats them as global (vasm manual, warning 3011); ELF does.

**See also:** [XDEF](#xdef)

## COMM
`comm <symbol>,<size>`

Create a common (shared, linker-allocated) data block of `size` bytes.

Alignment is always 32 bits. `-Fhunkexe` does not allocate commons (vasm manual known
problem): link with vlink, or just use a BSS label with `xdef`.

**See also:** [XDEF](#xdef), [BSS](sections.md#bss)

## NREF
`nref <symbol>[,<symbol>...]`

Import a symbol that may be accessed base-relative (small data).

The manual lists it for `-phxass` mode only; vasm 1.9 also accepted it in default mode and
rejected it with `-devpac` (tested). Only relevant with the NEAR small-data model.

**See also:** [XREF](#xref)

## INLINE
`inline` · rejected with `-devpac`

Start a block whose local labels are isolated from those around it.

Handy in macros or included snippets that reuse local names like `.loop`.

### Example
```asm
fill:   moveq   #9,d0
.loop:  clr.b   (a0)+
        inline
        moveq   #3,d1
.loop:  clr.w   (a1)+                   ; separate .loop
        dbf     d1,.loop
        einline
        dbf     d0,.loop                ; the outer .loop again
        rts
```

**See also:** [EINLINE](#einline), [Local labels](#local-labels)

## EINLINE
`einline`

End an INLINE block; local labels from before the block are visible again.

**See also:** [INLINE](#inline)

## Local labels
`.name` · `name$`

A label starting with `.` or ending with `$` is local to its enclosing global labels.

- The same local name may be reused after the next global label.
- `global\local` reaches a local label of another scope (PhxAss style; not inside macros).
- EQU symbols with a `.` prefix are local as well.
- Local labels are not written to the hunk symbol table by default (`-dbg-local` adds them).

### Example
```asm
ClearScreen:
        move.w  #320/8*256-1,d0
.loop:  clr.b   (a0)+
        dbf     d0,.loop
        rts
CopyScreen:
        move.w  #320/8*256-1,d0
.loop:  move.b  (a0)+,(a1)+             ; different .loop
        dbf     d0,.loop
        rts
```

### Gotchas
- Referencing a local label from a different scope does not error without `-x`: vasm
  silently turns it into an external reference (tested). A global label placed between a
  local label and its `bra .x` does exactly this.
- A label ending in `.b`, `.w` or `.l` cannot be defined.

**See also:** [INLINE](#inline), [XDEF](#xdef)
