# vasm directives: conditional assembly

vasm reads the source ONCE. A condition can only use symbols defined above it; a forward
reference in `if`/`ifeq`... is error 31 "expression must be constant", and `ifd`/`ifnd`
treat a symbol defined further down as undefined (tested).

Expressions accept C and assembler operators: `= == <> != < > <= >= && || ! ~ & | ^`
(vasm manual). Blocks nest; close every block with `endif` or `endc`.
Never put a label on the same line as `if`, `else` or `endif` (manual: undefined behaviour).
Inside a false block unknown mnemonics are skipped silently, so a typo there is not caught.

## IF
`if <expression>`

Assemble the block if the expression is non-zero.

### Example
```asm
DEBUG   equ     1
        if DEBUG&&(PLANES>4)
        move.w  #$0f00,$dff180          ; red border marker
        endif
```

**See also:** [ELSE](#else), [ENDIF, ENDC](#endif-endc), [IFNE](#ifne), [IIF](#iif)

## IFEQ
`ifeq <expression>`

Assemble the block if the expression is zero.

**See also:** [IFNE](#ifne), [IF](#if)

## IFNE
`ifne <expression>`

Assemble the block if the expression is non-zero (same as IF).

**See also:** [IFEQ](#ifeq), [IF](#if)

## IFGT
`ifgt <expression>`

Assemble the block if the expression is greater than zero.

### Example
```asm
CALLLIB macro
        ifgt    NARG-1                  ; NDK exec/libraries.i uses this guard
        fail    too many arguments
        endc
        jsr     \1(a6)
        endm
```

**See also:** [IFGE](#ifge), [IFLT](#iflt), [NARG](macros-repeat.md#narg)

## IFGE
`ifge <expression>`

Assemble the block if the expression is zero or greater.

**See also:** [IFGT](#ifgt), [IFLE](#ifle)

## IFLT
`iflt <expression>`

Assemble the block if the expression is less than zero.

**See also:** [IFLE](#ifle), [IFGT](#ifgt)

## IFLE
`ifle <expression>`

Assemble the block if the expression is zero or less.

**See also:** [IFLT](#iflt), [IFGE](#ifge)

## IFB
`ifb <operand>`

Assemble the block if the operand field is empty (a comment is allowed).

Mostly used in macros to test for an omitted argument.

### Example
```asm
WAITLINE macro                          ; WAITLINE [line]
        ifb     \1
        move.w  #$138,d0                ; default line
        else
        move.w  #\1,d0
        endif
        bsr     WaitRaster
        endm
```

**See also:** [IFNB](#ifnb), [IFC](#ifc), [MACRO](macros-repeat.md#macro)

## IFNB
`ifnb <operand>`

Assemble the block if the operand field is not empty.

**See also:** [IFB](#ifb)

## IFC
`ifc <string1>,<string2>`

Assemble the block if the two strings are identical.

Comparison is case-sensitive (`'abc','ABC'` does not match, tested). Strings may be quoted
or bare. The NDK idiom `ifc '\1',''` tests for an empty macro argument.

**See also:** [IFNC](#ifnc), [IFB](#ifb)

## IFNC
`ifnc <string1>,<string2>`

Assemble the block if the two strings differ.

### Example
```asm
SETREG  macro                           ; SETREG value,register  (d0 = default)
        ifnc    '\2',''
        move.l  #\1,\2
        else
        move.l  #\1,d0
        endc
        endm
```

**See also:** [IFC](#ifc)

## IFD
`ifd <symbol>`

Assemble the block if the symbol is defined at this point of the source.

Include guards in the NDK use the opposite form (`IFND EXEC_TYPES_I` / `EXEC_TYPES_I SET 1`).
Symbols given with `-D` count as defined.

### Example
```asm
        ifd     DEBUG                   ; vasm -DDEBUG ...
        bsr     DumpRegs
        endc
```

**See also:** [IFND](#ifnd), [EQU](symbols.md#equ)

## IFND
`ifnd <symbol>`

Assemble the block if the symbol is not (yet) defined.

### Example
```asm
        ifnd    MYLIB_I
MYLIB_I set     1
        ; ... include-file body ...
        endc
```

**See also:** [IFD](#ifd), [INCLUDE](include-and-output.md#include)

## IFMACROD
`ifmacrod <macro>` · rejected with `-devpac` and `-phxass`

Assemble the block if a macro of that name is defined.

Despite the manual's wording ("following line") it opens a normal block closed by
`endc` (tested). Macro names are case-sensitive.

**See also:** [IFMACROND](#ifmacrond), [MACRO](macros-repeat.md#macro)

## IFMACROND
`ifmacrond <macro>` · rejected with `-devpac` and `-phxass`

Assemble the block if no macro of that name is defined.

**See also:** [IFMACROD](#ifmacrod)

## IF1, IFP1
`if1` · `ifp1` · rejected with `-devpac`

Pass-1 test kept for old sources; always true in vasm (warning 1026).

**See also:** [IF2](#if2)

## IF2
`if2` · rejected with `-devpac`

Pass-2 test kept for old sources; always false in vasm (warning 1027).

Code inside `if2` blocks from two-pass assemblers is silently dropped.

**See also:** [IF1, IFP1](#if1-ifp1)

## ELSE
`else`

Switch to the opposite branch of the current conditional block.

**See also:** [IF](#if), [ELSEIF](#elseif), [ENDIF, ENDC](#endif-endc)

## ELSEIF
`elseif` · rejected with `-devpac`

Same as ELSE; any operand is IGNORED (vasm manual, tested).

### Gotchas
- It is not an else-if. With `M equ 1`, `if M=1 / elseif M=2 / else / endif` assembles
  BOTH the `if` block and the `else` block, because `elseif` and `else` each flip the
  branch (tested). Nest `if` inside `else` instead.

**See also:** [ELSE](#else), [ELIF](#elif)

## ELIF
`elif <expression>` · not available in vasm 1.8k/1.9

A real else-if in newer vasm (manual); the bundled 1.8k and 1.9 builds do not know it.

On the bundled builds it is an unknown mnemonic, silently skipped inside a false block
(tested). Use nested `else` / `if` / `endif`.

**See also:** [ELSEIF](#elseif), [ELSE](#else)

## ENDIF, ENDC
`endif` · `endc`

Close the innermost conditional block (the two names are identical).

**See also:** [IF](#if), [ELSE](#else)

## IIF
`[<label>] iif <expression> <statement>`

Assemble a single statement if the expression is non-zero; no `endc` is used.

- **statement** — one instruction or directive; it cannot carry its own label, but a label
  may precede `iif` (it receives the statement's value, or the PC if false).

### Example
```asm
        iif DEBUG move.w #$f00,$dff180
PAL     equ     1
LINES   iif PAL equ 256
```

### Gotchas
- With `-spaces`, `foo iif 1 + 1 = 42` misparses `= 42` as part of the condition.

**See also:** [IF](#if)
