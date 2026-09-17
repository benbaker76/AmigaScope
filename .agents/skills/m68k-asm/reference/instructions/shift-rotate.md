# 68000 instructions: shifts and rotates

Notation (sizes, CCR symbols, mode names) as in [data movement](data-movement.md).

Every shift/rotate has three forms with the same rules:

| Form | Syntax | Sizes | Count |
|---|---|---|---|
| Immediate count | `LSL #<1-8>,Dy` | B/W/L | 1..8 in the opcode |
| Register count | `LSL Dx,Dy` | B/W/L | Dx modulo 64 (0..63) |
| Memory | `LSL <ea>` | W only | always 1 |

Memory form modes: memory alterable -- (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

| Family | Bit shifted in | Last bit out goes to | V | Zero count |
|---|---|---|---|---|
| ASL | 0 | C and X | set if the sign bit changed at any step | X kept, C=0 |
| ASR | copy of the sign bit | C and X | 0 | X kept, C=0 |
| LSL / LSR | 0 | C and X | 0 | X kept, C=0 |
| ROL / ROR | bit shifted out | C only (X kept) | 0 | C=0 |
| ROXL / ROXR | old X | C and X | 0 | X kept, C=X |

N and Z always follow the result.

## ASL, ASR
`ASL Dx,Dy` / `ASL #<data>,Dy` / `ASL <ea>` (ASR alike) · B/W/L (memory: W) · 68000

Arithmetic shift: left fills with zeros and flags sign changes, right keeps the sign bit.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

Modes: register forms on Dy; memory form (W, 1 bit) on (An), (An)+, -(An), (d,An),
(d,An,Xi), abs.W, abs.L.

### Example
```asm
        asr.w   #4,d0                   ; signed d0.w / 16, rounded towards -infinity
        asl.l   #2,d1                   ; signed d1 * 4
        bvs.s   .overflow               ; V: result no longer fits the signed range
        rts
.overflow
        moveq   #-1,d1
        rts
```

### Gotchas
- ASL and LSL produce the same bits; only V differs (ASL sets it on a sign change, LSL
  always clears it).
- `asr` of a negative odd number rounds down (-1 asr 1 = -1), unlike DIVS which truncates
  towards zero (-1/2 = 0).
- Immediate count max 8: `asl.l #9,d0` is an error; use two shifts or a register count.
- The memory form shifts a WORD by exactly one bit; `asl #2,(a0)` and `asl.l (a0)` do not
  exist.

**See also:** LSL, LSR, [MULS, MULU](arithmetic.md#muls-mulu), [DIVS, DIVU](arithmetic.md#divs-divu)

## LSL, LSR
`LSL Dx,Dy` / `LSL #<data>,Dy` / `LSL <ea>` (LSR alike) · B/W/L (memory: W) · 68000

Logical shift: zeros come in, the last bit shifted out goes to C and X.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | 0 | * |

Modes: register forms on Dy; memory form (W, 1 bit) on (An), (An)+, -(An), (d,An),
(d,An,Xi), abs.W, abs.L.

### Example
```asm
        ; d0.w = y*320 without MULU: y*256 + y*64
        move.w  d0,d1
        lsl.w   #8,d0                   ; y*256
        lsl.w   #6,d1                   ; y*64
        add.w   d1,d0
        lsr.w   #3,d2                   ; unsigned d2.w / 8
        moveq   #12,d3
        lsl.l   d3,d4                   ; count > 8 needs a register
```

### Gotchas
- Register count is modulo 64, not modulo the operand size: `lsl.l d1,d0` with d1 = 32
  gives 0; with d1 = 64 nothing is shifted.
- Only the low 6 bits of the count register matter; its other bits are ignored.
- LSR on a signed negative value is not division: use ASR.

**See also:** ASL, ASR, ROL, ROR, [optimisation](../topics/optimisation.md)

## ROL, ROR
`ROL Dx,Dy` / `ROL #<data>,Dy` / `ROL <ea>` (ROR alike) · B/W/L (memory: W) · 68000

Rotate without X: bits leaving one end re-enter at the other; C gets the last bit moved.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | * |

Modes: register forms on Dy; memory form (W, 1 bit) on (An), (An)+, -(An), (d,An),
(d,An,Xi), abs.W, abs.L.

### Example
```asm
        move.b  $bfec01,d0              ; CIA-A SDR: raw keyboard byte
        not.b   d0
        ror.b   #1,d0                   ; bit 0 (up/down flag) moves to bit 7
        rol.w   #4,d1                   ; rotate a nibble through a word
```

### Gotchas
- X is untouched, so ROL/ROR cannot carry into a multi-precision chain; use ROXL/ROXR.
- `rol.l #8,d0` four times restores the value; SWAP is a cheaper 16-bit rotation of a long
  (but clears C where ROR sets it).

**See also:** ROXL, ROXR, [SWAP](data-movement.md#swap)

## ROXL, ROXR
`ROXL Dx,Dy` / `ROXL #<data>,Dy` / `ROXL <ea>` (ROXR alike) · B/W/L (memory: W) · 68000

Rotate through X: operand and X form a 9/17/33-bit ring; C and X get the last bit out.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | 0 | * |

Modes: register forms on Dy; memory form (W, 1 bit) on (An), (An)+, -(An), (d,An),
(d,An,Xi), abs.W, abs.L.

### Example
```asm
        ; 64-bit shift right of d0:d1 (high:low) by one bit
        lsr.l   #1,d0                   ; high half, bit 0 -> X
        roxr.l  #1,d1                   ; X enters bit 31 of the low half
```

### Gotchas
- Initialise X first (`andi #$ef,ccr` clears it, `ori #$10,ccr` sets it) when not following
  a shift.
- With a zero register count C is set to X and X is unchanged.

**See also:** LSL, LSR, [ADDX](arithmetic.md#addx), [ANDI to CCR](logic.md#andi-to-ccr)
