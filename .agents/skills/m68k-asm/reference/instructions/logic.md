# 68000 instructions: logic

Notation (sizes, CCR symbols, mode names) as in [data movement](data-movement.md).
All logical instructions leave X alone and clear V and C, except the CCR/SR forms, which
change exactly the bits selected by the immediate mask.

CCR bits for the `to CCR` / `to SR` forms: bit 4 X, 3 N, 2 Z, 1 V, 0 C. SR system byte:
bit 15 T, 13 S, 10-8 interrupt mask (see [MOVE to SR](data-movement.md#move-to-sr)).

## AND
`AND <ea>,Dn` / `AND Dn,<ea>` · B/W/L · 68000

Bitwise AND of source into destination (mask bits off).

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

`<ea>,Dn` source modes: data -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L,
(d,PC), (d,PC,Xi), #imm.
`Dn,<ea>` destination modes: memory alterable -- (An), (An)+, -(An), (d,An), (d,An,Xi),
abs.W, abs.L.

### Example
```asm
        and.w   (a0),d0                 ; d0.w &= word at (a0)
        and.b   d1,(a2)+                ; mask a memory byte with d1.b
```

### Gotchas
- Address registers can never be an operand: copy to a Dn (or `exg`) first.
- `and #imm,<ea>` is ANDI.

**See also:** ANDI, OR, EOR, [BCLR](bit.md#bclr)

## ANDI
`ANDI #<data>,<ea>` · B/W/L · 68000

AND an immediate mask (same size as the operation) into a data register or memory.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        andi.l  #$fffffff0,d1           ; round down to a multiple of 16
        andi.w  #$00ff,d0               ; keep the low byte, clear bits 15-8
        beq.s   .none                   ; Z from the masked result
        andi.b  #$7f,(a0)
.none   rts
```

### Gotchas
- To zero-extend a byte to a long in place, `andi.l #$ff,d0` works but costs 6 bytes;
  `moveq #0,d0` before loading the byte is shorter.

**See also:** AND, ANDI to CCR, ANDI to SR

## ANDI to CCR
`ANDI #<data>,CCR` · B · 68000

Clear the condition code bits whose mask bit is 0; the others are unchanged.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

### Example
```asm
        andi    #$ef,ccr                ; clear X before a ROXL/ADDX chain
        andi    #$fe,ccr                ; clear C (e.g. "no error" return)
```

### Gotchas
- Byte operation (`andi.w #x,ccr` is rejected); MOVE to CCR is the word form.

**See also:** ORI to CCR, EORI to CCR, [MOVE to CCR](data-movement.md#move-to-ccr)

## ANDI to SR
`ANDI #<data>,SR` · W · 68000 · supervisor only

AND a word mask into the whole status register (system byte and CCR).

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

### Example
```asm
        andi    #$f8ff,sr               ; interrupt mask -> 0, CCR kept
```

### Gotchas
- Privilege violation in user mode. Keep CCR bits set to 1 in the mask unless you mean to
  clear flags; clearing bit 13 drops to user mode.

**See also:** ORI to SR, [MOVE to SR](data-movement.md#move-to-sr)

## OR
`OR <ea>,Dn` / `OR Dn,<ea>` · B/W/L · 68000

Bitwise inclusive OR of source into destination (force bits on).

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

`<ea>,Dn` source modes: data -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L,
(d,PC), (d,PC,Xi), #imm.
`Dn,<ea>` destination modes: memory alterable -- (An), (An)+, -(An), (d,An), (d,An,Xi),
abs.W, abs.L.

### Example
```asm
        or.w    d1,d0
        or.l    d0,(a0)                 ; set bits of a memory longword
```

### Gotchas
- No address registers. `or.l d0,d0` is a cheap "test d0" but TST is clearer.

**See also:** ORI, AND, [BSET](bit.md#bset)

## ORI
`ORI #<data>,<ea>` · B/W/L · 68000

OR an immediate mask (same size as the operation) into a data register or memory.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        ori.w   #$8000,d0               ; set the SET/CLR bit of a DMACON/INTENA value
        ori.b   #%00000011,(a0)+
```

**See also:** OR, ORI to CCR, ORI to SR

## ORI to CCR
`ORI #<data>,CCR` · B · 68000

Set the condition code bits whose mask bit is 1; the others are unchanged.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

### Example
```asm
        ori     #$01,ccr                ; set C: signal an error to the caller
        rts
```

### Gotchas
- Byte operation. `ori #$04,ccr` sets Z (bit 2), `#$10` sets X.

**See also:** ANDI to CCR, [MOVE to CCR](data-movement.md#move-to-ccr)

## ORI to SR
`ORI #<data>,SR` · W · 68000 · supervisor only

OR a word mask into the whole status register.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

### Example
```asm
        move    sr,-(sp)                ; supervisor code: save the old mask
        ori     #$0700,sr               ; raise interrupt mask to 7
        ; ... critical section ...
        move    (sp)+,sr
```

### Gotchas
- Privilege violation in user mode; under the OS use `Disable()`/`Enable()`.
- Mask 7 blocks levels 1-6; level 7 is the NMI (exec treats it as a separate server chain).

**See also:** ANDI to SR, [MOVE from SR](data-movement.md#move-from-sr)

## EOR
`EOR Dn,<ea>` · B/W/L · 68000

Exclusive-OR a data register into the destination (toggle bits).

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        eor.w   d1,d0                   ; toggle the bits of d0 selected by d1
        eor.b   d2,(a0)                 ; XOR-plot into a memory byte
```

### Gotchas
- The SOURCE must be a data register: `eor.w (a0),d0` does not exist. Load the memory into a
  register first, or XOR into memory with `eor.w d0,(a0)`.

**See also:** EORI, [BCHG](bit.md#bchg), NOT

## EORI
`EORI #<data>,<ea>` · B/W/L · 68000

Exclusive-OR an immediate mask into a data register or memory.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        eori.b  #1,flag                 ; toggle a 0/1 flag byte
flag    dc.b    0
        even
```

**See also:** EOR, EORI to CCR, EORI to SR

## EORI to CCR
`EORI #<data>,CCR` · B · 68000

Invert the condition code bits whose mask bit is 1.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

### Example
```asm
        eori    #$04,ccr                ; invert Z
```

**See also:** ANDI to CCR, ORI to CCR

## EORI to SR
`EORI #<data>,SR` · W · 68000 · supervisor only

Invert the status register bits whose mask bit is 1.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

### Example
```asm
        eori    #$8000,sr               ; toggle the trace bit (debugger code)
```

### Gotchas
- Privilege violation in user mode.

**See also:** ANDI to SR, ORI to SR

## NOT
`NOT <ea>` · B/W/L · 68000

Replace the operand with its one's complement (invert every bit).

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        move.b  $bfec01,d0              ; CIA-A serial data (keyboard)
        not.b   d0                      ; keycodes arrive inverted
```

### Gotchas
- NOT is not negation: `not x` = `-x - 1`. Use NEG for two's complement.

**See also:** [NEG](arithmetic.md#neg), EOR, EORI
