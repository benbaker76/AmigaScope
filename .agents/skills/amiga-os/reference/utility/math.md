# utility.library: 32/64-bit integer math

The 68000 and 68010 have only 16x16 multiply and 32/16 divide. These calls give 32x32 multiply,
32/32 divide with remainder, and 32x32 -> 64-bit multiply on every CPU, using the native
instructions where the library runs on a 68020+ (unverified which ROM builds do). They are
special among library calls:

- **A6 need not hold UtilityBase** -- jump through the table with any base register you like
  (autodoc NOTE). You still need the base address to find the table: `move.l _UtilityBase,a5` /
  `jsr _LVOUMult32(a5)` is legal.
- **All address registers are preserved**, A0 and A1 included (autodoc NOTE). D0 and D1 carry
  the results; D2-D7 are preserved like any call.
- Results: 32-bit multiply -> D0. Division -> quotient D0, **remainder D1**. 64-bit multiply ->
  **low 32 bits D0, high 32 bits D1** (see [SMult64](#smult64) for the old-ROM caveat).

C with Bartman's gcc: just write `a * b`, `a / b`, `a % b` -- the template's
`support/gcc8_a_support.s` provides `__mulsi3`, `__divsi3`, `__udivsi3`, `__modsi3`, `__umodsi3`.
The inline macros for SDivMod32/UDivMod32/SMult64/UMult64 return only D0, so the remainder or high
half is unreachable from C without an asm stub. These calls are mainly for 68000 asm.

## SMult32
`LONG SMult32(LONG arg1, LONG arg2)` — LVO -138 (-$8A)
Registers: arg1=D0, arg2=D1; result in D0

Multiply two signed 32-bit values, returning the low 32 bits.

- **arg1, arg2** — factors.
- **Result** — signed 32-bit product (overflow is not reported).

Since V36.

**See also:** [UMult32](#umult32), [SMult64](#smult64), [SDivMod32](#sdivmod32)

## UMult32
`ULONG UMult32(ULONG arg1, ULONG arg2)` — LVO -144 (-$90)
Registers: arg1=D0, arg2=D1; result in D0

Multiply two unsigned 32-bit values, returning the low 32 bits.

- **arg1, arg2** — factors.
- **Result** — unsigned 32-bit product (overflow is not reported).

Since V36.

### Example
```asm
; d2 = row, d3 = bytes per row (both may exceed 16 bits)
        include "lvo/utility_lib.i"

        move.l  _UtilityBase,a6
        move.l  d2,d0
        move.l  d3,d1
        jsr     _LVOUMult32(a6)         ; d0 = row * bpr; a0/a1 survive
        add.l   d0,a0                   ; a0 still holds the buffer base
```

**See also:** [SMult32](#smult32), [UMult64](#umult64), [UDivMod32](#udivmod32)

## SDivMod32
`LONG SDivMod32(LONG dividend, LONG divisor)` — LVO -150 (-$96)
Registers: dividend=D0, divisor=D1; result in D0

Divide signed 32-bit values: quotient in D0, remainder in D1.

- **dividend** — signed 32-bit dividend (D0).
- **divisor** — signed 32-bit divisor (D1).
- **Result** — D0 = signed quotient, **D1 = signed remainder**.

Since V36.

### Gotchas
- Division by zero is not documented: check the divisor yourself.

**See also:** [UDivMod32](#udivmod32), [SMult32](#smult32)

## UDivMod32
`ULONG UDivMod32(ULONG dividend, ULONG divisor)` — LVO -156 (-$9C)
Registers: dividend=D0, divisor=D1; result in D0

Divide unsigned 32-bit values: quotient in D0, remainder in D1.

- **dividend** — unsigned 32-bit dividend (D0).
- **divisor** — unsigned 32-bit divisor (D1).
- **Result** — D0 = unsigned quotient, **D1 = unsigned remainder**.

Since V36.

### Example
```asm
; convert a frame counter in d2 to seconds (d0) and leftover frames (d1), PAL
        include "lvo/utility_lib.i"

        move.l  _UtilityBase,a6
        move.l  d2,d0
        moveq   #50,d1
        jsr     _LVOUDivMod32(a6)       ; d0 = d2 / 50, d1 = d2 % 50
```

### Gotchas
- A 68000 `DIVU` would overflow here as soon as the quotient exceeds 16 bits; that is the case
  this call exists for.
- Division by zero is not documented: check the divisor yourself.

**See also:** [SDivMod32](#sdivmod32), [UMult32](#umult32)

## SMult64
`LONG SMult64(LONG arg1, LONG arg2)` — LVO -198 (-$C6)
Registers: arg1=D0, arg2=D1; result in D0

Multiply two signed 32-bit values into a signed 64-bit result split over D0 and D1.

- **arg1, arg2** — factors.
- **Result** — 64-bit product: low 32 bits in D0, high 32 bits in D1 (the NDK autodoc only writes
  `D0:D1`; the order comes from the utility.library 45.1 release notes in NDK 3.2).

Since V39.

### Gotchas
- NDK 3.2 release notes for utility.library 45.1 (AmigaOS 3.1.4) say the **68000 version** before
  that release returned the two halves in the wrong order. On V39/V40 ROMs running 68000 code do not
  trust which register holds the high half (unverified which ROMs are affected): multiply a known
  pair once at startup (e.g. `$10000 * $10000`: high = 1, low = 0) and swap if needed, or use your
  own routine.
- On a 68020+ you can use `MULS.L <ea>,Dh:Dl` directly instead.
- The C prototype returns only a LONG (D0).

**See also:** [UMult64](#umult64), [SMult32](#smult32)

## UMult64
`ULONG UMult64(ULONG arg1, ULONG arg2)` — LVO -204 (-$CC)
Registers: arg1=D0, arg2=D1; result in D0

Multiply two unsigned 32-bit values into an unsigned 64-bit result split over D0 and D1.

- **arg1, arg2** — factors.
- **Result** — 64-bit product: low 32 bits in D0, high 32 bits in D1 (see [SMult64](#smult64)).

Since V39.

### Example
```asm
; d0:d1 = d2 * d3 as a 64-bit value, with a one-time check of the register order
        include "lvo/utility_lib.i"

CheckMul64:
        move.l  _UtilityBase,a6
        move.l  #$10000,d0
        move.l  d0,d1
        jsr     _LVOUMult64(a6)         ; $1_0000_0000
        cmp.l   #1,d1
        seq     mul64_ok                ; $FF: low in D0, high in D1 (documented order)
        rts

Mul64:  move.l  _UtilityBase,a6
        move.l  d2,d0
        move.l  d3,d1
        jsr     _LVOUMult64(a6)
        tst.b   mul64_ok
        bne.s   .done
        exg     d0,d1                   ; old 68000 build: halves swapped
.done:  rts                             ; d0 = low, d1 = high

mul64_ok:       dc.b    0
                even
```

### Gotchas
- Same old-ROM register-order caveat as [SMult64](#smult64).
- On a 68020+ `MULU.L <ea>,Dh:Dl` does the same in one instruction.

**See also:** [SMult64](#smult64), [UMult32](#umult32)
