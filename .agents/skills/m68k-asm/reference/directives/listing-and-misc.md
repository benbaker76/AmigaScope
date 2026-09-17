# vasm directives: messages, listing, options and CPU control

Listing directives only matter when a listing is requested with `-L <file>`. OPT, MACHINE
and the small-data directives come from vasm's M68k CPU module and are available in the
mot syntax only.

## FAIL
`fail <message>`

Stop with an error (error 20) showing the message; no output file is written.

### Example
```asm
        ifgt    BPLSIZE*PLANES-512*1024
        fail    bitplanes do not fit in 512K chip RAM
        endc
```

**See also:** [PRINTT](#printt), [IFGT](conditional.md#ifgt), [ASSERT](#assert)

## PRINTT
`printt <string>[,<string>...]` · rejected with `-devpac` and `-phxass`

Print text to stdout during assembly, one line per string; quotes are optional.

**See also:** [PRINTV](#printv), [ECHO](#echo)

## PRINTV
`printv <expression>[,<expression>...]` · rejected with `-devpac` and `-phxass`

Print each value as hex, decimal, ASCII and binary on its own line.

Output shape (tested): `$26 38 "...&" %00000000000000000000000000100110`. The quickest
way to check a structure offset or a size calculation.

### Example
```asm
        include "graphics/gfxbase.i"
        printv  gb_copinit              ; $26 38 ...
```

**See also:** [PRINTT](#printt), [ECHO](#echo)

## ECHO
`echo <"string"|exp>[,<"string"|exp>...]` · rejected with `-devpac`

Print strings and expression values on one line.

`echo "size:",BPLSIZE` prints `size:10240` (tested with 1.9).

**See also:** [PRINTT](#printt), [PRINTV](#printv)

## SHOWOFFSET
`showoffset [<text>]` · vasm 1.9 only (unknown in 1.8k)

Print the current section offset, preceded by the optional text (PhxAss compatibility).

**See also:** [PRINTV](#printv)

## ASSERT
`assert <expression>[,<message>]` · not available in vasm 1.8k/1.9

Error when the expression is false; only in newer vasm, not in the bundled builds.

Use `ifeq <expression>` + `fail <message>` + `endc` instead.

**See also:** [FAIL](#fail)

## COMMENT
`comment <anything>`

Ignore the rest of the line.

A `HEAD=<exp>` inside it passes TOS header flags to the Atari TOS output module; irrelevant
on the Amiga.

**See also:** [REM](#rem)

## REM
`rem` · rejected with `-devpac`

Ignore every following line until EREM (block comment).

### Example
```asm
        rem
        old copper effect, kept for reference
        move.w  #$0f00,$dff180
        erem
```

**See also:** [EREM](#erem), [END](include-and-output.md#end)

## EREM
`erem`

End a REM block; assembly continues on the next line.

**See also:** [REM](#rem)

## CARGS
`cargs [#<offset>,]<symbol>[.<size>][,<symbol>[.<size>]...]`

Define stack-argument offsets: first symbol = offset, each next = previous + its size.

- **offset** — default 4 (skips the return address at `0(sp)`).
- **size** — `.l` = 4; `.w`, `.b` or none = 2.

### Example
```asm
        cargs   #4,arg_buf.l,arg_len.l  ; arg_buf = 4, arg_len = 8
FillBuf:                                ; FillBuf(buf, len) with stacked longs
        move.l  arg_buf(sp),a0
        move.l  arg_len(sp),d0
        ; ...
        rts
```

### Gotchas
- Offsets are relative to SP at entry. After `movem.l ...,-(sp)` or `link`, add the saved
  bytes (a second `cargs #4+12,...` for three saved longs).

**See also:** [FO](structures.md#fo), [RS](structures.md#rs)

## OPT
`opt <option>[,<option>...]`

Set Devpac-style assembler options from inside the source.

| Option | Meaning (default in native vasm mode) |
|---|---|
| `o+` / `o-` | all optimizations on / off (on; off with `-devpac`) |
| `o1`..`o12` | single optimizations: 1 branch size, 2 displacements, 3 abs to short, 4 `move.l` to `moveq`, 5 `addq`/`subq`, 7 `bra.b` to next line into 2-byte NOP, 8/9 020 displacements, 10 `add #,An` to `lea`, 11 `lea` to `addq`, 12 `.l #,An` to `.w` |
| `a+` / `a-` | absolute to PC-relative (on) |
| `ow+` | print every optimization (off; `-showopt` is the same) |
| `c+` / `c-` | case-sensitive symbols (on) |
| `d+` / `d-` | debug symbols in the output (on; off with `-devpac`) |
| `x+` | hunk objects: drop local symbols (like `-nosym`, tested) |
| `p+` | position-independence check: error on every relocation |
| `t+` / `w+` | type/size checks, warnings (on) |
| `p=<cpu>[/<fpu>]` | select CPU, e.g. `opt p=68020` or `p=68030/68882` |
| `og`, `of` | vasm generic safe / float-constant optimizations (on) |
| `oc od oj ol om on op oq os ot ox oz` | vasm optional optimizations: CLR, DIV, bra-to-jmp, LSL, MOVEM, small data, PEA, MOVEQ+NEG, speed, ST, MUL, size (off) |

Devpac3 words also work: `autopc`, `case`, `chkpc`, `debug`, `symtab`, `type`, `warn`,
`xdebug` and their `no...` forms. Unknown letters give warning 2032 (tested).

### Example
```asm
        opt     o-                      ; exact instruction sizes from here on
        move.l  #1,d0                   ; stays a 6-byte MOVE (tested)
        opt     o+
```

### Gotchas
- Default (non-Devpac) vasm rewrites instructions: `move.l #1,d0` to `moveq`, `clr.l d0`
  to `moveq #0`, `bra` to `bra.s`, `jsr label` to `bsr`, same-section absolute labels to
  `(pc)` (tested). Code that counts bytes, patches itself, or uses fixed-size jump tables
  needs `opt o-` or the `-no-opt` command-line switch.
- With a CPU above 68000 vasm also turns `move #0,<ea>` into `clr <ea>` (tested with
  `-m68020`). On a 68000 it does not by default, because CLR reads the address first
  (vasm manual). Keep 68000 builds on `-m68000`.
- In `-devpac` mode `opt o+`/`o-` only toggle `og` and `of`.

**See also:** [MACHINE](#machine), [vasm and vlink](../topics/vasm-vlink.md)

## MACHINE
`machine <cpu>` · `mc68000` `mc68010` `mc68020` `mc68030` `mc68040` `mc68060` `ac68080` `cpu32`

Switch the instruction set for the following code.

- **cpu** — `68000 68010 68020 68030 68040 68060 68080 68851 68881 68882 cpu32` (or a
  ColdFire model).

Same effect as `-m680x0` on the command line or `opt p=<cpu>` (both tested). The
default CPU is 68000: 020+ instructions and addressing modes are errors until enabled.

### Example
```asm
        machine 68020
        move.l  (a0,d0.w*4),a1          ; scaled index: 020+ only
        machine 68000
```

### Gotchas
- Selecting a higher CPU lets the optimizer emit 020+ forms (32-bit branches, CLR on
  hardware registers). Only switch for code that really checks the CPU first.

**See also:** [OPT](#opt), [FPU](#fpu)

## FPU
`fpu <cpID>`

Enable 68881/68882 FPU instructions with coprocessor ID `cpID` (1 for 68040/060 FPUs).

`fpu 0` disables FPU code generation again. The `-m68881`/`-m68882` options do the same.

**See also:** [MACHINE](#machine)

## NEAR
`near [<An>]` · `near code`

Enable small-data mode: references into the `__MERGED` section become `(offset,An)`.

The base-relative rewrite only happens with `-sd` (or `opt on+`; automatic with
`-phxass`). vlink merges all base-relative sections and provides `_LinkerDB` at section
start + $7FFE. `near code` instead turns JMP/JSR to external labels into 16-bit PC-relative
calls.

### Example
```asm
        near    a4
        section code,code
start:  initnear                        ; lea _LinkerDB,a4
        addq.w  #1,counter              ; -> addq.w #1,counter(a4) with -sd
        rts
        section __MERGED,data
counter: dc.w   0
```

### Gotchas
- A4 must hold `_LinkerDB` in every routine that touches small data, including interrupt
  handlers and callbacks entered from the OS.

**See also:** [FAR](#far), [INITNEAR](#initnear), [BASEREG](#basereg), [NREF](symbols.md#nref)

## FAR
`far`

Switch small-data (and `near code`) mode off; references are absolute again.

**See also:** [NEAR](#near)

## INITNEAR
`initnear`

Emit `lea _LinkerDB,An` for the current NEAR base register (vlink resolves it).

Error 2060 if no NEAR mode is active (tested).

**See also:** [NEAR](#near)

## BASEREG
`basereg <expression>,<An>`

Access labels as offsets from a base address you have loaded into An yourself.

vasm subtracts `expression` from every `(label,An)` displacement until ENDB. Works without
a linker, handy for a variables block addressed through A5 in a demo.

### Example
```asm
start:  lea     vars,a5
        basereg vars,a5
        move.w  v_lives(a5),d0          ; assembled as 2(a5)
        endb    a5
        rts
vars:   dc.w    0
v_lives: dc.w   3
```

**See also:** [ENDB](#endb), [NEAR](#near)

## ENDB
`endb <An>`

End a BASEREG block for that register.

**See also:** [BASEREG](#basereg)

## LOCAL
`local` · not available in vasm 1.8k/1.9

Start a new block of local labels; only in newer vasm, not in the bundled builds.

Use [INLINE](symbols.md#inline) / [EINLINE](symbols.md#einline) or a new global label.

**See also:** [Local labels](symbols.md#local-labels)

## LIST
`list`

Resume writing lines to the listing file (only with `-L <file>`).

**See also:** [NOLIST](#nolist)

## NOLIST
`nolist`

Leave this and the following lines out of the listing file.

Useful around big include files.

**See also:** [LIST](#list)

## PAGE
`page`

Start a new listing page; not implemented in vasm.

**See also:** [NOPAGE](#nopage), [PLEN](#plen)

## NOPAGE
`nopage`

Never emit form feeds in the listing file.

**See also:** [PAGE](#page)

## LLEN
`llen <len>`

Set the listing line length; has no effect (warning 1012, tested).

`-Lbpl=<n>` sets bytes per listing line instead.

**See also:** [PLEN](#plen)

## PLEN
`plen <len>`

Set the listing page length; accepted and ignored.

**See also:** [LLEN](#llen), [PAGE](#page)

## SPC
`spc <lines>`

Insert blank lines in the listing; has no effect (warning 1012, tested).

**See also:** [PAGE](#page)
