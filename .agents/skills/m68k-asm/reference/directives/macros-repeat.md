# vasm directives: macros and repetition

A macro must be defined before its first call (single pass: an earlier call is "unknown
mnemonic", tested). Macro names are case-sensitive in default mode (`-phxass` makes them
case-insensitive). IRP and IRPC do not exist in vasm's mot syntax (tested): use REPT with
SET counters, or a recursive macro.

## MACRO
`<name> macro` · `macro <name>`

Define a macro; the body runs until ENDM.

When the name is on the left it must start in column 1 and any operand of `macro` is
ignored. Call it like a mnemonic, with up to 9 comma-separated arguments.

| Code | Inserts |
|---|---|
| `\1` .. `\9` | arguments 1-9 (empty if not given) |
| `\a` .. `\z` | arguments 10-35; only with `-allmp`, `-devpac` or `-phxass` |
| `\0` | the size qualifier of the call (`PUSH.l` gives `l`) |
| `\@` | a unique id per call (`_000005`), for private labels |
| `\@!` `\@?` `\@@` | push id / push id below top / pull id (id stack for nested macros) |
| `\#` | number of arguments (same as NARG) |
| `\?n` | length in characters of argument n |
| `\.` `\+` `\-` | the argument selected by symbol `CARG`; `\+`/`\-` then step CARG |
| `\<sym>` | decimal value of absolute symbol `sym` |
| `\<$sym>` | hex value of `sym`, no `$` (the prb28 spelling `\$<sym>` fails, tested) |

An argument containing commas is passed inside `< >` (`GRP <1,2,3>` is one argument).

### Example
```asm
PUSH    macro                           ; PUSH.<size> <ea>
        move.\0 \1,-(sp)
        endm

COLOR   macro                           ; COLOR index,rgb  -> copper MOVE
        dc.w    $180+(\1)*2,\2
        endm

WAITVB  macro                           ; busy-wait for line \1 (private label)
.w\@:   move.l  $dff004,d0
        and.l   #$1ff00,d0
        cmp.l   #(\1)<<8,d0
        bne.s   .w\@
        endm

        PUSH.l  #1234
copper: COLOR   0,$000
        COLOR   1,$fff
        WAITVB  $138
```

### Gotchas
- A label on the same line as a macro call gets the address BEFORE any alignment the
  macro's first instruction needs; after odd data it is odd (tested). Put `even` first.
- Parameters are substituted even in commented-out lines inside the body; this can
  trigger `\@!`, `\@@`, `\+`, `\-` side effects (vasm manual known problem).
- Arguments are text: `\1*2` with argument `1+1` is `1+1*2` = 3. Parenthesise: `(\1)*2`.
- `-maxmacrecurs=<n>` limits recursion depth (default 1000).
- For source-level debugging inside macros see MSOURCE.

**See also:** [ENDM](#endm), [MEXIT](#mexit), [NARG](#narg), [IFB](conditional.md#ifb),
[IFC](conditional.md#ifc), [macros topic](../topics/macros-and-structures.md)

## ENDM
`endm`

End a macro definition.

**See also:** [MACRO](#macro), [MEXIT](#mexit)

## MEXIT
`mexit`

Leave the current macro expansion immediately.

It also discards every conditional block opened inside the macro, so it works as a break
out of nested `if` blocks. Outside a macro it is error 37.

### Example
```asm
SHIFT   macro                           ; SHIFT reg,count  (count 0 = nothing)
        ifeq    \2
        mexit
        endc
        lsl.w   #\2,\1
        endm
```

**See also:** [MACRO](#macro), [IF](conditional.md#if)

## NARG
`NARG` (symbol)

Number of arguments passed to the current macro; -1 outside any macro (tested).

`\#` inserts the same number as text.

### Example
```asm
LINKLIB macro                           ; shape of the NDK exec/libraries.i macro
        ifgt    NARG-2
        fail    LINKLIB takes 2 arguments
        endc
        move.l  a6,-(sp)
        move.l  \2,a6
        jsr     \1(a6)
        move.l  (sp)+,a6
        endm
```

**See also:** [MACRO](#macro), [IFGT](conditional.md#ifgt)

## REPT
`rept <count>`

Assemble the block up to ENDR `count` times.

- **count** — constant expression; negative counts as 0.
- Symbol `REPTN` holds the 0-based iteration of the innermost REPT, -1 outside.
  After a nested block ends, REPTN is the outer counter again (tested).

### Example
```asm
squares:                                ; 0,1,4,9 ... 225
        rept    16
        dc.w    REPTN*REPTN
        endr

bplptrs:                                ; copper BPLxPTH/L pairs for 5 planes
        rept    5
        dc.w    $e0+REPTN*4,0,$e2+REPTN*4,0
        endr
```

### Gotchas
- The newer manual's `rept <count>,<symbol>` form is not in vasm 1.8k/1.9: the symbol is
  treated as an undefined external (tested).
- Use SET symbols for anything REPTN cannot express.

**See also:** [ENDR](#endr), [SET](symbols.md#set)

## ENDR
`endr`

End a REPT block.

**See also:** [REPT](#rept)

## MSOURCE
`msource <on|off>` · rejected with `-devpac` and `-phxass`

Choose whether debug line info inside macros points at the macro body or at the call line.

Default on. Accepts `0`/`1`. Only has an effect with `-linedebug` hunk output (the
`-no-msrcdebug` option does the same globally).

**See also:** [MACRO](#macro), [vasm and vlink](../topics/vasm-vlink.md)
