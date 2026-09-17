# 68000 instructions: arithmetic and compare

Notation (sizes, CCR symbols, mode names) as in [data movement](data-movement.md). For which
condition to branch on after these instructions see
[condition codes](../topics/condition-codes.md). 68020+ long multiply/divide forms are in
[68020+ instructions](cpu-68020-plus.md).

## ADD
`ADD <ea>,Dn` / `ADD Dn,<ea>` · B/W/L · 68000

Add source to destination; X and C receive the carry, V the signed overflow.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

`<ea>,Dn` source modes: all -- Dn, An (W/L only), (An), (An)+, -(An), (d,An), (d,An,Xi),
abs.W, abs.L, (d,PC), (d,PC,Xi), #imm.
`Dn,<ea>` destination modes: memory alterable -- (An), (An)+, -(An), (d,An), (d,An,Xi),
abs.W, abs.L.

### Example
```asm
        add.w   d1,d0                   ; d0.w += d1.w
        add.l   d0,(a0)                 ; add a register into memory
        add.w   (a1)+,d2                ; accumulate a table of words
```

### Gotchas
- One operand must be a data register: memory-to-memory ADD does not exist.
- `add ...,An` assembles as ADDA (no flags); `add #n,<ea>` as ADDI/ADDQ.
- C/X = unsigned carry, V = signed overflow: branch with the matching condition.

**See also:** ADDA, ADDI, ADDQ, ADDX, SUB

## ADDA
`ADDA <ea>,An` · W/L · 68000

Add to an address register; a word source is sign-extended and the CCR is not changed.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Source modes: all -- Dn, An, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC),
(d,PC,Xi), #imm.

### Example
```asm
        adda.w  d0,a0                   ; a0 += sign-extended d0.w
        adda.l  #320*40,a1              ; skip 40 lines of a 320-wide buffer
```

### Gotchas
- The whole 32-bit register changes even for `.w`; `adda.w d0,a0` with d0.w = $8000
  SUBTRACTS 32768. Zero-extend into a long and use `adda.l` for unsigned word offsets.
- `adda.w d0,a0` is the same as `lea (a0,d0.w),a0`.

**See also:** ADD, SUBA, [LEA](data-movement.md#lea)

## ADDI
`ADDI #<data>,<ea>` · B/W/L · 68000

Add an immediate value (same size as the operation) to a data register or memory.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        addi.w  #320,(a0)               ; move an object 320 pixels
        addi.l  #$10000,d3              ; 16.16 fixed point: +1.0
```

### Gotchas
- Not for address registers (use ADDA / ADDQ / LEA).
- For 1..8 use ADDQ (2 bytes instead of 4-6); vasm substitutes it automatically.

**See also:** ADD, ADDQ, SUBI

## ADDQ
`ADDQ #<data>,<ea>` · B/W/L · 68000

Add an immediate value 1-8 to the destination.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

Destination modes: alterable -- Dn, An (W/L only; flags unaffected), (An), (An)+, -(An),
(d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        addq.w  #1,d0                   ; counter
        addq.l  #4,a0                   ; step a pointer, flags untouched
        addq.b  #2,(a1)                 ; memory byte += 2
```

### Gotchas
- Range 1..8 only (8 is encoded as 0); `addq #9` is an error.
- On An the full 32 bits change and NO flags are set, whatever the size; `addq.b` on An is
  illegal.
- On data registers and memory it changes X like ADD (only the An form leaves the CCR).

**See also:** SUBQ, ADDI, [LEA](data-movement.md#lea)

## ADDX
`ADDX Dy,Dx` / `ADDX -(Ay),-(Ax)` · B/W/L · 68000

Add source plus the X bit to destination, for multi-precision addition.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

Z is cleared if the result is non-zero and left unchanged otherwise, so a chain ends with Z=1
only if every part was zero (set Z before the chain).

### Example
```asm
        ; 64-bit add: d0:d1 += d2:d3 (high:low)
        add.l   d3,d1                   ; low halves, X = carry
        addx.l  d2,d0                   ; high halves + carry
```

### Gotchas
- Only register-register or predecrement memory-memory; process multi-byte numbers from the
  least significant end (high address) downwards with `-(An)`.
- Start a chain with X=0 and Z=1 (`move #$04,ccr`) when the Z result matters.

**See also:** ADD, SUBX, [ABCD](bcd.md#abcd), [ROXL, ROXR](shift-rotate.md#roxl-roxr)

## SUB
`SUB <ea>,Dn` / `SUB Dn,<ea>` · B/W/L · 68000

Subtract source from destination (dst - src -> dst); X and C receive the borrow.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

`<ea>,Dn` source modes: all -- Dn, An (W/L only), (An), (An)+, -(An), (d,An), (d,An,Xi),
abs.W, abs.L, (d,PC), (d,PC,Xi), #imm.
`Dn,<ea>` destination modes: memory alterable -- (An), (An)+, -(An), (d,An), (d,An,Xi),
abs.W, abs.L.

### Example
```asm
        sub.w   d1,d0                   ; d0.w = d0.w - d1.w
        bcs.s   .under                  ; unsigned: borrow means d1 > d0
        sub.l   d0,(a0)                 ; memory -= d0
.under  rts
```

### Gotchas
- Operand order is source,destination: `sub d1,d0` computes d0-d1.
- `sub.l An,An` assembles as SUBA and is the standard way to clear an address register.

**See also:** SUBA, SUBI, SUBQ, SUBX, CMP

## SUBA
`SUBA <ea>,An` · W/L · 68000

Subtract from an address register; a word source is sign-extended and no flags change.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Source modes: all -- Dn, An, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC),
(d,PC,Xi), #imm.

### Example
```asm
        suba.l  a0,a0                   ; a0 = 0 (CLR cannot address An)
        suba.w  #16,sp                  ; reserve 16 bytes of stack
```

### Gotchas
- Same sign-extension trap as ADDA: `suba.w d0,a0` with d0.w >= $8000 adds.

**See also:** ADDA, SUB, [CLR](data-movement.md#clr)

## SUBI
`SUBI #<data>,<ea>` · B/W/L · 68000

Subtract an immediate value (same size as the operation) from a data register or memory.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        subi.w  #10,lives               ; absolute memory
lives   dc.w    3
```

### Gotchas
- For 1..8 use SUBQ; vasm substitutes it automatically.

**See also:** SUB, SUBQ, CMPI

## SUBQ
`SUBQ #<data>,<ea>` · B/W/L · 68000

Subtract an immediate value 1-8 from the destination.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

Destination modes: alterable -- Dn, An (W/L only; flags unaffected), (An), (An)+, -(An),
(d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        subq.w  #1,d7                   ; count down...
        bne.s   .more                   ; ...loop while not zero
        subq.l  #2,a0                   ; pointer back one word, flags untouched
.more   rts
```

### Gotchas
- Range 1..8. On An: whole register, no flags.
- `subq.w #1,Dn` + `bne` loops Dn times; DBF loops Dn+1 times and tests -1, not 0.

**See also:** ADDQ, SUBI, [DBcc](program-control.md#dbcc)

## SUBX
`SUBX Dx,Dy` / `SUBX -(Ax),-(Ay)` · B/W/L · 68000

Subtract source and the X bit from destination, for multi-precision subtraction.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

Z is cleared if the result is non-zero and unchanged otherwise.

### Example
```asm
        ; 64-bit subtract: d0:d1 -= d2:d3 (high:low)
        sub.l   d3,d1
        subx.l  d2,d0
```

### Gotchas
- Same operand-mode restrictions and Z behaviour as ADDX.

**See also:** SUB, ADDX, NEGX, [SBCD](bcd.md#sbcd)

## MULS, MULU
`MULS <ea>,Dn` / `MULU <ea>,Dn` · W (16 x 16 -> 32) · 68000

Multiply the low words of source and Dn (signed or unsigned) into a full 32-bit Dn.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

Source modes: data -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC),
(d,PC,Xi), #imm.

### Example
```asm
        move.w  y,d1
        mulu    #320,d1                 ; d1.l = y*320, all 32 bits valid
        moveq   #0,d2
        move.w  x,d2
        add.l   d2,d1                   ; pixel offset = y*320 + x (can exceed 65535)
y       dc.w    199
x       dc.w    5
```

### Gotchas
- The upper word of Dn is ignored on input and overwritten by the product
  (`$FFFF * $FFFF = $FFFE0001` with MULU).
- Pick MULS for signed words (MULU of -1 gives 65535 * x).
- The `.l` forms (32 x 32) need a 68020+: see [MULS.L, MULU.L](cpu-68020-plus.md#mulsl-mulul).
- On a 68000 multiplication is slow compared with shifts and adds; see
  [optimisation](../topics/optimisation.md).

**See also:** DIVS, DIVU, [ASL, ASR](shift-rotate.md#asl-asr)

## DIVS, DIVU
`DIVS <ea>,Dn` / `DIVU <ea>,Dn` · W (32 / 16) · 68000

Divide 32-bit Dn by a 16-bit source: quotient in the low word, remainder in the high.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | * | 0 |

Source modes: data -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC),
(d,PC,Xi), #imm.
N and Z follow the quotient; they are undefined after an overflow.

### Example
```asm
        ; write the decimal digits of d1.l (< 655360) backwards before (a0)
.digit  divu    #10,d1                  ; d1 = remainder:quotient
        swap    d1                      ; low word = remainder
        add.b   #'0',d1
        move.b  d1,-(a0)
        clr.w   d1                      ; drop the digit
        swap    d1                      ; d1.l = quotient, Z from all 32 bits
        bne.s   .digit
```

### Gotchas
- Overflow: if the quotient does not fit (DIVU: > $FFFF, i.e. the high word of the dividend
  >= divisor; DIVS: outside -32768..32767) V is set and Dn is left UNCHANGED. Check `bvs`.
- Divide by zero raises exception vector 5 (exec alert `ACPU_DivZero`); test the divisor.
- Prepare the dividend as a full longword: `moveq #0,d1` + `move.w x,d1` for DIVU,
  `ext.l d1` for DIVS.
- The remainder stays in the high word: `ext.l` / `andi.l #$ffff` before using the quotient
  as a longword.
- DIVS truncates towards zero; the remainder has the sign of the dividend (-7/2 = -3 r -1).
- The 32/32 and 64/32 forms need a 68020+: see [DIVS.L, DIVU.L](cpu-68020-plus.md#divsl-divul).

**See also:** MULS, MULU, [SWAP](data-movement.md#swap), [ASL, ASR](shift-rotate.md#asl-asr)

## NEG
`NEG <ea>` · B/W/L · 68000

Replace the operand with its two's complement (0 - operand).

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

C (and X) are set unless the result is zero. V is set when negating the most negative value
($80, $8000, $80000000), which stays unchanged.

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        tst.w   d0
        bpl.s   .pos
        neg.w   d0                      ; absolute value of a word
.pos    rts
```

### Gotchas
- NEG is arithmetic (`$E7` -> `$19`); NOT is bitwise (`$E7` -> `$18`).

**See also:** NEGX, [NOT](logic.md#not), [Scc](program-control.md#scc)

## NEGX
`NEGX <ea>` · B/W/L · 68000

Subtract the operand and the X bit from zero, for multi-precision negation.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

Z is cleared if the result is non-zero and unchanged otherwise.
Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        ; 64-bit negate of d0:d1 (high:low)
        neg.l   d1                      ; X = 1 unless the low half was 0
        negx.l  d0
```

### Gotchas
- Always start the chain with NEG (or an explicit X) on the least significant part.

**See also:** NEG, SUBX

## EXT
`EXT.W Dn` / `EXT.L Dn` · W/L · 68000

Sign-extend a byte to a word (EXT.W) or a word to a long (EXT.L) in a data register.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

### Example
```asm
        move.b  (a0),d0
        ext.w   d0                      ; byte -> word
        ext.l   d0                      ; word -> long (68000 has no EXTB)
```

### Gotchas
- `EXT.W` leaves bits 31-16 alone: `$12345678` -> `$12340078`.
- Zero-extension is not EXT: `moveq #0,d0` then `move.b (a0),d0`.
- Byte to long in one step is `extb.l` (68020+ only).

**See also:** [EXTB](cpu-68020-plus.md#extb), [DIVS, DIVU](#divs-divu), [MOVEQ](data-movement.md#moveq)

## CMP
`CMP <ea>,Dn` · B/W/L · 68000

Set the flags for Dn - source without storing the result.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | * | * |

Source modes: all -- Dn, An (W/L only), (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L,
(d,PC), (d,PC,Xi), #imm.

### Example
```asm
        cmp.w   #320,d0                 ; d0.w - 320
        bge.s   .offright               ; signed: d0 >= 320
        cmp.l   d1,d0                   ; d0 - d1
        bhi.s   .above                  ; unsigned: d0 > d1
        moveq   #0,d0
.offright
.above  rts
```

### Gotchas
- Reads "compare destination with source": `cmp d1,d0` then `bgt` branches if d0 > d1.
- X is not changed (SUB would change it).
- `cmp #n,<ea>` with a non-register destination is CMPI; vasm turns `cmp #0` into TST.

**See also:** CMPA, CMPI, CMPM, TST, [condition codes](../topics/condition-codes.md)

## CMPA
`CMPA <ea>,An` · W/L · 68000

Set the flags for An - source using all 32 bits; a word source is sign-extended first.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | * | * |

Source modes: all -- Dn, An, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC),
(d,PC,Xi), #imm.

### Example
```asm
        lea     buffer(pc),a0
        lea     bufend(pc),a1
.clear  clr.b   (a0)+
        cmpa.l  a1,a0
        blo.s   .clear                  ; addresses are unsigned: BLO/BHS/BHI/BLS
buffer  ds.b    64
bufend
```

### Gotchas
- Compare addresses with unsigned conditions; above $80000000 a signed test is wrong.
- `cmpa.w #0,a0` is a legal 68000 way to test a pointer for NULL (`tst.l a0` needs 68020+).

**See also:** CMP, TST, [MOVEA](data-movement.md#movea)

## CMPI
`CMPI #<data>,<ea>` · B/W/L · 68000

Set the flags for destination - immediate data without changing the destination.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | * | * |

Destination modes: Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L; 68020+ also
(d,PC), (d,PC,Xi).

### Example
```asm
        cmpi.b  #$ff,(a0)               ; end-of-table marker?
        beq.s   .end
        cmpi.b  #200,$dff006            ; VHPOSR high byte = vertical position
.end    rts
```

### Gotchas
- PC-relative operands only on 68020+ (vasm `-m68000` rejects them).
- Not for An: use CMPA.

**See also:** CMP, TST

## CMPM
`CMPM (Ay)+,(Ax)+` · B/W/L · 68000

Compare two memory operands addressed by postincrement (flags for (Ax) - (Ay)).

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | * | * |

### Example
```asm
        moveq   #16-1,d0
.cmp    cmpm.b  (a0)+,(a1)+
        dbne    d0,.cmp                 ; stop at first difference or after 16 bytes
        bne.s   .differ                 ; DBcc keeps the flags of the last CMPM
        moveq   #0,d0                   ; blocks are equal
.differ rts
```

### Gotchas
- Both operands must be `(An)+`; order is source,destination.

**See also:** CMP, [DBcc](program-control.md#dbcc)

## TST
`TST <ea>` · B/W/L · 68000

Set N and Z from the operand and clear V and C.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

Operand modes (68000/68010): data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi),
abs.W, abs.L. 68020+ also: An (W/L), #imm, (d,PC), (d,PC,Xi).

### Example
```asm
        tst.l   d0
        beq.s   .failed                 ; e.g. AllocMem returned 0
        tst.b   (a0)+                   ; end of C string?
.failed rts
```

### Gotchas
- Redundant after MOVE/MOVEQ/arithmetic into the same data (they already set N and Z).
  Required after MOVEA, MOVEM, LEA, ADDQ/SUBQ to An, and on D0 after a library call.
- `tst.l a0` and `tst label(pc)` are 68020+ only.

**See also:** CMP, [BTST](bit.md#btst), [condition codes](../topics/condition-codes.md)
