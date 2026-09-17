# 68000 instructions: BCD arithmetic

Notation (sizes, CCR symbols, mode names) as in [data movement](data-movement.md).

BCD bytes hold two decimal digits, one per nibble (`$59` = 59). All three instructions are
byte-only, include X in the operation, set C and X on a decimal carry/borrow, leave N and V
undefined, and only CLEAR Z (never set it). Before a chain set X=0 and Z=1, e.g.
`move #$04,ccr`; after the chain Z=1 means the whole number was zero. Digits other than 0-9
give meaningless results. Typical Amiga use: score and timer counters printed as digits.

PACK/UNPK (68020+) convert between BCD and ASCII: see [68020+ instructions](cpu-68020-plus.md).

## ABCD
`ABCD Dy,Dx` / `ABCD -(Ay),-(Ax)` · B · 68000

Add source, destination and X in decimal, storing the result in the destination.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | U | * | U | * |

Modes: data register to data register, or predecrement to predecrement only.

### Example
```asm
        ; score += bonus, both 3-byte BCD numbers stored most significant byte first
        lea     score+3(pc),a0          ; one past the last (least significant) byte
        lea     bonus+3(pc),a1
        moveq   #3-1,d0
        move    #$04,ccr                ; X=0, Z=1 (after MOVEQ, which would change Z)
.add    abcd    -(a1),-(a0)
        dbf     d0,.add                 ; DBF keeps X for the next byte
        rts
score   dc.b    $00,$12,$99             ; 001299
bonus   dc.b    $00,$00,$05             ; + 5 = 001304
```

### Gotchas
- Work from the least significant byte (highest address) with `-(An)`.
- Anything between the ABCDs that changes X (ADD, shifts, ...) breaks the carry chain;
  MOVEQ, MOVE and DBcc leave X alone.

**See also:** SBCD, NBCD, [ADDX](arithmetic.md#addx), [DBcc](program-control.md#dbcc)

## SBCD
`SBCD Dx,Dy` / `SBCD -(Ax),-(Ay)` · B · 68000

Subtract source and X from destination in decimal (dst - src - X -> dst).

| X | N | Z | V | C |
|---|---|---|---|---|
| * | U | * | U | * |

Modes: data register to data register, or predecrement to predecrement only.

### Example
```asm
        move.b  timer(pc),d0            ; two-digit BCD countdown
        moveq   #1,d1
        andi    #$ef,ccr                ; X = 0
        sbcd    d1,d0                   ; $10 -> $09
        bcs.s   .expired                ; borrow: went below 00
        lea     timer(pc),a0
        move.b  d0,(a0)
.expired
        rts
timer   dc.b    $10
        even
```

### Gotchas
- Operand order is source,destination like SUB; the borrow from a byte is carried to the
  next (more significant) byte in X.

**See also:** ABCD, NBCD, [SUBX](arithmetic.md#subx)

## NBCD
`NBCD <ea>` · B · 68000

Subtract the operand and X from zero in decimal (ten's complement if X=0, nine's if X=1).

| X | N | Z | V | C |
|---|---|---|---|---|
| * | U | * | U | * |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        moveq   #$25,d2
        andi    #$ef,ccr                ; X = 0
        nbcd    d2                      ; d2.b = $75 (100 - 25), C = X = 1
```

### Gotchas
- A non-zero operand always produces a borrow (C=X=1), which the next NBCD of a chain uses.

**See also:** ABCD, SBCD, [NEGX](arithmetic.md#negx)
