# 68000 instructions: data movement

Notation used in every instruction file: `<ea>` = effective address; sizes B/W/L;
CCR table `*` = set from the result, `-` = unchanged, `0`/`1` = forced, `U` = undefined.
Mode names are those of [addressing modes](../topics/addressing-modes.md): Dn, An, (An),
(An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC), (d,PC,Xi), #imm. On 68020+ every
place that accepts (d,An,Xi) or (d,PC,Xi) also accepts the extended forms built on the same
base (`(bd,An,Xn*s)`, `([bd,An],Xn,od)` ...). vasm accepts both `(d,An)` and `d(An)`.

## MOVE
`MOVE <ea>,<ea>` · B/W/L · 68000

Copy the source operand to the destination and set N and Z from the value copied.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

Source modes: all -- Dn, An (W/L only), (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L,
(d,PC), (d,PC,Xi), #imm.
Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        move.l  (a0)+,(a1)+             ; copy a longword, advance both pointers
        move.w  d0,-(sp)                ; push a word
        move.b  (a2),d1                 ; only the low byte of d1 changes
        beq.s   .zero                   ; flags already reflect the byte moved
        addq.b  #1,d1
.zero   rts
```

### Gotchas
- Only the low byte/word of a data register is replaced by `.b`/`.w`; the upper bits stay.
- `move <ea>,An` is really MOVEA: sign-extends words and sets NO flags.
- The destination can never be PC-relative on any CPU; load the address with
  `lea label(pc),a0` and write through `(a0)`.
- A byte pushed or popped through A7 (`move.b d0,-(sp)`) moves SP by 2, keeping the stack
  word-aligned.
- `move #x,ccr` / `move #x,sr` / `move sr,<ea>` are separate instructions with their own
  entries below.

**See also:** MOVEA, MOVEQ, MOVEM, [CLR](#clr), [condition codes](../topics/condition-codes.md)

## MOVEA
`MOVEA <ea>,An` · W/L · 68000

Load an address register; a word source is sign-extended and no flags change.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Source modes: all -- Dn, An, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC),
(d,PC,Xi), #imm.

### Example
```asm
        movea.l 4.w,a6                  ; ExecBase
        move.l  (a0),a1                 ; vasm emits MOVEA for "move ...,An"
        move.l  a1,d0                   ; to test the pointer, move it to a Dn...
        beq.s   .null                   ; ...because MOVEA set no flags
        move.l  (a1),d1
.null   rts
```

### Gotchas
- `movea.w #$8000,a0` loads `$FFFF8000`, not `$00008000`. `lea $8000,a0` loads `$00008000`.
- No byte size. Flags are untouched: `move.l (a0),a1` then `beq` tests stale flags.
- `movea.l #imm,An` of a value in -32768..32767 is assembled by vasm as the shorter
  `movea.w` (same result because of the sign extension).

**See also:** LEA, MOVE, [ADDA](arithmetic.md#adda), [CMPA](arithmetic.md#cmpa)

## MOVEQ
`MOVEQ #<data>,Dn` · L · 68000

Load an 8-bit signed constant (-128..127) sign-extended into all 32 bits of Dn.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

Operands: immediate data in the opcode, destination Dn only. 2 bytes.

### Example
```asm
        moveq   #0,d0                   ; d0 = $00000000, Z=1
        moveq   #-1,d1                  ; d1 = $FFFFFFFF
        moveq   #127,d2                 ; largest positive value
```

### Gotchas
- Always a longword operation: `moveq #12,d0` clears bits 31-8, `move.b #12,d0` does not.
- `moveq #200,d0` is out of range: vasm warns and assembles -56 (`$FFFFFFC8`);
  `moveq #$ff,d0` gives -1. Use `move.l #200,d0` (vasm may still shorten it, see
  [optimisation](../topics/optimisation.md)).
- Only data registers; X is not touched, so it is safe inside ADDX/ROXL chains.

**See also:** MOVE, [CLR](#clr), [optimisation](../topics/optimisation.md)

## MOVEM
`MOVEM <list>,<ea>` / `MOVEM <ea>,<list>` · W/L · 68000

Save or restore a set of registers to or from consecutive memory in one instruction.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Register list: `d0-d7/a0-a6` style (ranges joined by `/`).
Registers -> memory: (An), -(An), (d,An), (d,An,Xi), abs.W, abs.L.
Memory -> registers: (An), (An)+, (d,An), (d,An,Xi), abs.W, abs.L, (d,PC), (d,PC,Xi).

Order: control modes and `(An)+` transfer D0..D7 then A0..A7 upward from the address;
`-(An)` stores A7..A0 then D7..D0 downward, so a `-(sp)` save and a `(sp)+` restore of the
same list match. Mask bit 0 = D0 ... bit 15 = A7, reversed (bit 0 = A7) for `-(An)`.

### Example
```asm
MySub   movem.l d2-d7/a2-a6,-(sp)       ; save the callee-saved registers
        ; ... body ...
        movem.l (sp)+,d2-d7/a2-a6       ; same list restores in the right order
        rts
```

### Gotchas
- Sets NO flags: you cannot `movem.l (sp)+,...` and then branch on a result; move the
  `tst` before the restore or re-test afterwards.
- `movem.w` sign-extends each word into the FULL 32 bits of data registers as well as
  address registers.
- Only `-(An)` for saving and `(An)+` for restoring; `movem d0-d1,(sp)+` is illegal.
- Base register inside a `-(An)` list: 68000/68010 store its initial value, 68020+ store the
  initial value minus the operand size (2 or 4). With `(An)+`, the loaded value is discarded in favour of the
  incremented address.
- For one register `move.l d0,-(sp)` is shorter (2 bytes vs 4) and sets flags; see
  [optimisation](../topics/optimisation.md).

**See also:** MOVE, LINK, [FMOVEM](cpu-68020-plus.md#fpu-68881-68882-68040-68060)

## MOVEP
`MOVEP Dx,(d,Ay)` / `MOVEP (d,Ay),Dx` · W/L · 68000 (not on 68060)

Move a word or long to/from every other byte of an 8-bit peripheral, high byte first.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Only `(d,Ay)` with a 16-bit displacement. A longword touches `d, d+2, d+4, d+6`.

### Example
```asm
        movep.w d0,(0,a0)               ; (a0) = high byte of d0.w, (2,a0) = low byte
```

### Gotchas
- Removed from the 68060: software using it crashes there. Replace with explicit
  `move.b` sequences. Nothing on the Amiga needs it (CIA registers are $100 apart).

**See also:** MOVE

## MOVE to CCR
`MOVE <ea>,CCR` · W · 68000

Load X N Z V C from bits 4-0 of a word operand; the system byte of SR is untouched.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

Source modes: data -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC),
(d,PC,Xi), #imm.

### Example
```asm
        move    #$04,ccr                ; X=0 N=0 Z=1 V=0 C=0 before an ABCD/ADDX chain
        move    #$10,ccr                ; X=1, N Z V C cleared
```

### Gotchas
- Word operation (`move.b d0,ccr` is rejected by vasm); ANDI/ORI/EORI to CCR are byte ops.
- Allowed in user mode on every CPU.

**See also:** [ANDI to CCR](logic.md#andi-to-ccr), [ORI to CCR](logic.md#ori-to-ccr), MOVE to SR

## MOVE to SR
`MOVE <ea>,SR` · W · 68000 · supervisor only

Load the whole status register: trace, supervisor, interrupt mask and condition codes.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

Source modes: data -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC),
(d,PC,Xi), #imm.

SR layout: bit 15 T (trace; T1 on 68020+), 13 S (supervisor), 10-8 interrupt mask,
4 X, 3 N, 2 Z, 1 V, 0 C. 68020+ also use bit 14 (T0) and bit 12 (M, master) (unverified).

### Example
```asm
        move    #$2700,sr               ; supervisor, all interrupt levels masked
        ; ... critical hardware setup ...
        move    #$2000,sr               ; supervisor, interrupts enabled
```

### Gotchas
- User mode: privilege violation exception (vector 8). Under the OS use
  `Disable()`/`Enable()` or `Supervisor()` instead.
- Clearing S switches A7 to the user stack pointer immediately.
- Write normal values ($2000, $2700...). Unused SR bits are ignored by a 68000 but are live
  on later CPUs: `move #$78ff,sr` is a known crash on 68020+ that works on an A500.

**See also:** MOVE from SR, [ORI to SR](logic.md#ori-to-sr), [ANDI to SR](logic.md#andi-to-sr),
[RTE](system.md#rte)

## MOVE from SR
`MOVE SR,<ea>` · W · 68000 (user mode) / 68010+ and 68EC000 supervisor only

Copy the status register to a word destination.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        move    sr,-(sp)                ; supervisor code: save SR (68000 or later)
        move    #$2700,sr
        ; ...
        move    (sp)+,sr
```

### Gotchas
- Privileged from the 68010 on: user-mode code that does `move sr,<ea>` works on an A500
  and crashes (privilege violation) on 68010+ machines. To read flags portably use
  `move ccr,<ea>` (68010+ only) or exec `GetCC()`.
- On the 68000 a memory destination is read before it is written.

**See also:** MOVE from CCR, MOVE to SR, [cpu models](../topics/cpu-models.md)

## MOVE from CCR
`MOVE CCR,<ea>` · W · 68010+

Copy the condition codes, zero-extended to a word, to the destination.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        move    ccr,-(sp)               ; 68010+: save flags in user mode
        ; ...
        rtr                             ; restore CCR and return
```

### Gotchas
- Does not exist on the plain 68000 (vasm `-m68000` rejects it). Code for every CPU should
  call exec `GetCC()`.

**See also:** MOVE from SR, [RTR](program-control.md#rtr)

## MOVE USP
`MOVE USP,An` / `MOVE An,USP` · L · 68000 · supervisor only

Read or set the user stack pointer from supervisor mode.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

### Example
```asm
        move    usp,a0                  ; inspect the interrupted task's stack
```

### Gotchas
- In user mode A7 IS the USP, so this is only meaningful in supervisor code. On 68010+ the
  same register is also reachable with `movec usp,Rn`.

**See also:** [MOVEC](system.md#movec), MOVE to SR

## LEA
`LEA <ea>,An` · L · 68000

Compute an effective address and load it into an address register without touching memory.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Source modes: control -- (An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC), (d,PC,Xi).

### Example
```asm
        lea     table(pc),a0            ; position-independent address of table
        lea     (-6,a0,d0.w),a1         ; a1 = a0 + sign-extended d0.w - 6
        lea     $dff000,a6              ; custom chip base (abs.L)
        lea     12(sp),sp               ; drop 3 longs from the stack, flags kept
table   dc.w    1,2,3
```

### Gotchas
- `lea (a0),a1` copies the pointer value; `move.l (a0),a1` loads the longword stored there.
- No `(An)+`, `-(An)`, Dn, An or #imm operands. No flags: test with a following `move.l
  An,Dn` or `cmpa`.
- `lea n(An),An` and `addq/subq` are interchangeable for small n (both leave flags); vasm
  rewrites `lea 8(a0),a0` to `addq.l #8,a0` by default.

**See also:** PEA, MOVEA, [addressing modes](../topics/addressing-modes.md)

## PEA
`PEA <ea>` · L · 68000

Compute an effective address and push it as a longword on the stack.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Source modes: control -- (An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC), (d,PC,Xi).

### Example
```asm
        pea     msg(pc)                 ; push the address of msg as an argument
        bsr.s   Print
        addq.l  #4,sp                   ; caller removes the argument
        rts
Print   movea.l 4(sp),a0                ; argument sits above the return address
        rts
msg     dc.b    "hi",0
        even
```

### Gotchas
- Equivalent to `lea <ea>,An` + `move.l An,-(sp)` without needing a spare register.
- `pea 4.w` pushes the value 4 (the address), not the longword stored at 4.

**See also:** LEA, [JSR](program-control.md#jsr)

## EXG
`EXG Rx,Ry` · L · 68000

Exchange the full 32-bit contents of two registers (data/data, address/address or mixed).

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

### Example
```asm
        exg     d0,a0                   ; process an address with data-register ops
        andi.l  #$00ffffff,d0
        exg     d0,a0
```

### Gotchas
- Flags unaffected, even when a data register is involved.

**See also:** SWAP, MOVE

## SWAP
`SWAP Dn` · W · 68000

Exchange the upper and lower 16-bit halves of a data register.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

N and Z are set from the whole 32-bit result.

### Example
```asm
        divu    #10,d0                  ; d0 = remainder:quotient
        swap    d0                      ; d0.w = remainder
```

### Gotchas
- Data registers only (`swap a0` is illegal). Unlike EXG, SWAP sets flags.

**See also:** EXG, [DIVS, DIVU](arithmetic.md#divs-divu), [EXT](arithmetic.md#ext)

## LINK
`LINK An,#<displacement>` · W (L on 68020+) · 68000

Push An, point An at the new stack top, then add a negative offset to SP for locals.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Operation: SP-4 -> SP; An -> (SP); SP -> An; SP + d -> SP.

### Example
```asm
Func    link    a5,#-16                 ; 16 bytes of locals at -16(a5)..-1(a5)
        move.l  d0,-4(a5)               ; a local
        move.l  8(a5),d1                ; first stacked argument (above return address)
        unlk    a5
        rts
```

### Gotchas
- The displacement must be negative to allocate; the word form is sign-extended (-32768
  minimum). `link.l` needs 68020+.
- Under AmigaOS never use A6 as the frame pointer in code that calls libraries (A6 is the
  library base); A5 is the usual choice.

**See also:** UNLK, [RTD](system.md#rtd)

## UNLK
`UNLK An` · 68000

Discard a LINK frame: SP = An, then pop the old An.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Operation: An -> SP; (SP) -> An; SP+4 -> SP.

### Example
```asm
        unlk    a5                      ; undo "link a5,#-n"
        rts
```

### Gotchas
- Restores SP from An, so anything still pushed below the frame is discarded too.

**See also:** LINK

## CLR
`CLR <ea>` · B/W/L · 68000

Set the operand to zero.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | 0 | 1 | 0 | 0 |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        clr.l   (a0)+                   ; zero a longword and advance
        moveq   #0,d0                   ; for a whole Dn prefer moveq (vasm does this for you)
        suba.l  a1,a1                   ; clear an address register (CLR cannot)
```

### Gotchas
- On the 68000 CLR reads the location before writing zero. Never `clr` a custom-chip or
  CIA register that reacts to access (strobes such as `COPJMP1`); use `move.w #0,<reg>`.
  The 68020 does a single write.
- `clr An` is illegal: use `suba.l An,An` (or `sub.l An,An`, which vasm assembles as SUBA).
- X is not changed.

**See also:** MOVEQ, [SUBA](arithmetic.md#suba), [optimisation](../topics/optimisation.md)
