# Condition codes

The low byte of the status register (the CCR) holds five flags that almost every data
instruction updates and that Bcc, DBcc, Scc and TRAPcc test. Getting a branch right means
knowing (1) what the previous instruction did to each flag, (2) which way round CMP
subtracts, and (3) whether the values are signed or unsigned.

## The CCR bits

| Bit | Flag | Set when | Main users |
|---|---|---|---|
| 4 | X extend | copy of C after arithmetic and shifts; left alone by most other instructions | ADDX, SUBX, NEGX, ABCD, SBCD, NBCD, ROXL, ROXR |
| 3 | N negative | most significant bit of the result is 1 | MI/PL, signed tests |
| 2 | Z zero | result is zero | EQ/NE, all "or equal" tests |
| 1 | V overflow | result does not fit the SIGNED range of the operand size | VS/VC, signed tests |
| 0 | C carry | unsigned carry out of (or borrow into) the operand | CS/CC, unsigned tests |

Bits 7-5 of the CCR read as 0. Set or clear flags directly with `move #x,ccr`,
`ori #x,ccr`, `andi #x,ccr`, `eori #x,ccr` (masks: X $10, N $08, Z $04, V $02, C $01).

## The 16 conditions

| cc | Code | True when | Meaning |
|---|---|---|---|
| T | $0 | always | DBcc/Scc/TRAPcc only (BRA uses this code) |
| F | $1 | never | DBcc/Scc/TRAPcc only (BSR uses this code) |
| HI | $2 | C=0 and Z=0 | unsigned higher |
| LS | $3 | C=1 or Z=1 | unsigned lower or same |
| CC = HS | $4 | C=0 | carry clear / unsigned higher or same |
| CS = LO | $5 | C=1 | carry set / unsigned lower |
| NE | $6 | Z=0 | not equal, non-zero |
| EQ | $7 | Z=1 | equal, zero |
| VC | $8 | V=0 | no signed overflow |
| VS | $9 | V=1 | signed overflow |
| PL | $A | N=0 | plus (MSB clear) |
| MI | $B | N=1 | minus (MSB set) |
| GE | $C | N=V | signed greater or equal |
| LT | $D | N<>V | signed less |
| GT | $E | Z=0 and N=V | signed greater |
| LE | $F | Z=1 or N<>V | signed less or equal |

`BHS`/`BLO`, `SHS`/`SLO`, `DBHS`/`DBLO` are vasm aliases for the CC/CS forms (same opcode).
There is no `BT`/`BF`. `DBRA` = `DBF`.

## CMP operand order and signed vs unsigned

`cmp <src>,<dst>` sets the flags for **dst - src** (dst is the second operand, the one on the
right). Read `cmp #10,d0` + `blt` as "branch if d0 < 10". The same holds for CMPA, CMPI,
CMPM (`cmpm (a0)+,(a1)+` tests (a1) - (a0)) and for SUB.

| After `cmp src,dst` branch if | Unsigned values (addresses, sizes, counters) | Signed values |
|---|---|---|
| dst > src | BHI | BGT |
| dst >= src | BHS (= BCC) | BGE |
| dst < src | BLO (= BCS) | BLT |
| dst <= src | BLS | BLE |
| dst = src | BEQ | BEQ |
| dst <> src | BNE | BNE |

After TST (which clears V and C), testing against zero: BMI / BPL for the sign, BEQ / BNE for
zero, BGT (> 0) and BLE (<= 0) for signed values.

```asm
        cmp.w   #320,d0                 ; d0.w - 320
        bhs.s   .off                    ; unsigned: also catches negative x (>= $8000)
        cmpa.l  a1,a0                   ; a0 - a1
        blo.s   .below                  ; addresses: always unsigned
        moveq   #-1,d2
        cmp.l   #1,d2                   ; -1 - 1
        blt.s   .neg                    ; signed: taken (-1 < 1)
        rts                             ; (a BHI here would ALSO be taken: $FFFFFFFF > 1)
.off
.below
.neg    rts
```

## What each instruction does to the flags

| Instructions | X | N, Z | V | C |
|---|---|---|---|---|
| ADD, ADDI, ADDQ, SUB, SUBI, SUBQ, NEG (data/memory operands) | = C | result | overflow | carry/borrow |
| ADDX, SUBX, NEGX | = C | N result; Z cleared if non-zero, else unchanged | overflow | carry/borrow |
| ABCD, SBCD, NBCD | = C | N undefined; Z cleared if non-zero, else unchanged | undefined | decimal carry/borrow |
| CMP, CMPA, CMPI, CMPM, CAS | unchanged | result | overflow | borrow |
| MOVE, MOVEQ, TST, CLR, AND(I), OR(I), EOR(I), NOT, EXT, EXTB, SWAP, TAS | unchanged | result | 0 | 0 |
| MULS, MULU (16-bit), bit-field BFxxx | unchanged | result | 0 | 0 |
| MULS.L, MULU.L | unchanged | result | overflow (32-bit form) | 0 |
| DIVS, DIVU (all forms) | unchanged | quotient (undefined on overflow) | overflow | 0 |
| ASL | last bit out | result | MSB changed at any step | last bit out |
| ASR, LSL, LSR | last bit out | result | 0 | last bit out |
| ROL, ROR | unchanged | result | 0 | last bit out |
| ROXL, ROXR | last bit out | result | 0 | last bit out |
| BTST, BSET, BCLR, BCHG | unchanged | Z = NOT old bit, N unchanged | unchanged | unchanged |
| CHK | unchanged | N defined only when trapping; Z undefined | undefined | undefined |
| CHK2, CMP2 | unchanged | N undefined; Z = equals a bound | undefined | out of range |
| MOVE to CCR/SR, ANDI/ORI/EORI to CCR/SR, RTR, RTE, STOP | loaded | loaded | loaded | loaded |

Shift/rotate with a zero register count: C = 0 (ROXL/ROXR: C = X), X unchanged.

**No flags changed at all:** MOVEA (and `move ...,An`), ADDA, SUBA, ADDQ/SUBQ to An, LEA,
PEA, EXG, MOVEM, LINK, UNLK, MOVEP, MOVE from SR/CCR, MOVE USP, MOVEC, MOVES, PACK, UNPK,
MOVE16, Bcc, BRA, BSR, DBcc, Scc, JMP, JSR, RTS, RTD, NOP, TRAP, TRAPV, TRAPcc.

SWAP does set flags (N and Z from all 32 bits, V=C=0), unlike EXG.

## Multi-precision chains

ADDX/SUBX/NEGX and the BCD instructions carry X from one part to the next and only ever
clear Z, so the final Z covers the whole number:

```asm
        ; 64-bit subtract d0:d1 -= d2:d3 with a valid 64-bit Z result
        move    #$04,ccr                ; X=0, Z=1
        subx.l  d3,d1                   ; low halves (X=0: plain subtract, Z only cleared)
        subx.l  d2,d0                   ; high halves minus the borrow
        beq.s   .zero                   ; taken only if BOTH halves are 0
        moveq   #1,d4
.zero   rts
```

Starting the chain with SUB (or ADD) instead would set Z from the low half alone and the
final Z would ignore it being non-zero; start with X=0, Z=1 and use the X form throughout.

## Common mistakes

- Reversed CMP operands: `cmp d0,d1` tests d1 - d0, so `bgt` means d1 > d0.
- Signed branches on unsigned data: `bgt`/`blt` on addresses, buffer lengths or `$FF`
  bytes. Use BHI/BHS/BLO/BLS.
- Testing flags that were never set: after MOVEA, MOVEM, LEA, ADDQ/SUBQ to An, EXG or a
  library call, add `tst`/`move.l An,Dn` first. A MOVEM restore between the test and the
  branch is harmless because it does not touch the CCR.
- Redundant TST after MOVE/MOVEQ/AND/arithmetic into the same data: the flags are already set.
- BTST polarity: Z=1 means the bit is CLEAR, so `beq` = bit clear.
- DBcc's condition is an exit test, the opposite of Bcc's branch test.
- Branching on N/Z after DIVS/DIVU without checking V first.
- Assuming X is clear: MOVE, CMP and logic instructions leave the old X in place; start
  ADDX/ROXL chains with `andi #$ef,ccr` or `move #$04,ccr`.
- ASL on signed data sets V on sign change; LSL never does, so `bvs` after LSL is dead code.
- vasm's default optimiser may rewrite `move.l #200,d0` as `moveq` + `add.w`, which changes
  X and C. Do not rely on X or C after a MOVE of a constant (see
  [optimisation](optimisation.md)).

**See also:** [Bcc](../instructions/program-control.md#bcc),
[DBcc](../instructions/program-control.md#dbcc), [CMP](../instructions/arithmetic.md#cmp),
[TST](../instructions/arithmetic.md#tst), [ADDX](../instructions/arithmetic.md#addx)
