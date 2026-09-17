# Addressing modes

Every 680x0 operand is either implied by the opcode (MOVEQ data, quick counts) or an
*effective address* (EA) encoded as a 3-bit mode plus a 3-bit register field, followed by 0-2
extension words (more on 68020+). Which EAs an instruction accepts is fixed by the CPU, not
the assembler: vasm rejects illegal combinations with "instruction not supported on selected
architecture" or "illegal operand types". The per-instruction lists are in the
[instruction files](../instructions/data-movement.md); this page explains the modes, the
categories those lists refer to, and the traps.

## The 68000 modes

| Mode | vasm syntax (both forms accepted) | Mode:Reg | Ext. words | Effective address |
|---|---|---|---|---|
| Data register direct | `d3` | 000:n | 0 | the register itself |
| Address register direct | `a3` | 001:n | 0 | the register itself |
| Address register indirect | `(a3)` | 010:n | 0 | a3 |
| Postincrement | `(a3)+` | 011:n | 0 | a3, then a3 += operand size |
| Predecrement | `-(a3)` | 100:n | 0 | a3 -= operand size, then a3 |
| Displacement | `(16,a3)` or `16(a3)` | 101:n | 1 | a3 + sign-extended 16-bit d |
| Index | `(8,a3,d0.w)` or `8(a3,d0.w)` | 110:n | 1 | a3 + index + sign-extended 8-bit d |
| Absolute short | `$1234.w`, `4.w` | 111:000 | 1 | sign-extended 16-bit address |
| Absolute long | `$dff000`, `label` | 111:001 | 2 | 32-bit address |
| PC displacement | `(label,pc)` or `label(pc)` | 111:010 | 1 | PC + sign-extended 16-bit d |
| PC index | `(label,pc,d0.w)` or `label(pc,d0.w)` | 111:011 | 1 | PC + index + sign-extended 8-bit d |
| Immediate | `#value` | 111:100 | 1 (B, W) or 2 (L) | the value (a byte uses the low byte of a word) |

Details that decide correctness:

- **Step size** of `(An)+` / `-(An)` is 1, 2 or 4 for B, W, L. With A7 a byte step is 2, so
  the stack stays word-aligned.
- **Index register** `Xi` is any Dn or An with `.w` (low word, sign-extended; the vasm default
  when no size is given) or `.l` (all 32 bits). `(a0,d0)` therefore means `(a0,d0.w)`.
- **Displacement ranges**: `(d,An)` and `(d,PC)` take -32768..32767; the index modes only
  -128..127 (vasm: "displacement out of range" on a 68000 target).
- **PC-relative base** is the address of the extension word holding the displacement (for
  `move.w label(pc),d0` that is the opcode address + 2). The assembler computes it; just
  write `label(pc)`.
- **Brief extension word** (index modes): bit 15 = 0 Dn / 1 An, bits 14-12 = register,
  bit 11 = 0 `.w` / 1 `.l`, bits 10-9 = scale (68020+, 00 on the 68000), bit 8 = 0,
  bits 7-0 = displacement. Example: `lea 8(a0,d0.w),a1` = `$43F0 $0008`;
  `lea (8,a0,d0.l*4),a1` (68020+) = `$43F0 $0C08`.

## Absolute short addresses

An abs.W operand is a 16-bit value sign-extended to 32 bits, so it reaches only
`$00000000-$00007FFF` and `$FFFF8000-$FFFFFFFF`, saving 2 bytes over abs.L.

```asm
        move.l  4.w,a6                  ; ExecBase: 4 bytes instead of 6
        move.l  $6c.w,d0                ; level-3 autovector on a 68000 (VBR = 0)
        move.w  $dff006,d0              ; custom chips and CIAs always need abs.L...
        lea     $dff000,a6              ; ...or better, a base register
        move.w  $006(a6),d1             ; VHPOSR through the base, 4 bytes
```

- vasm rejects `$8000.w` ("absolute short address out of range"); `$ffff8000.w` is legal.
- Unsized absolute addresses: vasm chooses abs.W automatically when the value fits the
  sign-extended range (with optimisation on), abs.L otherwise.

## Mode categories

Instruction descriptions (Motorola's and the entries in this skill) name groups of modes:

| Mode | data | memory | control | alterable |
|---|---|---|---|---|
| Dn | yes | - | - | yes |
| An | - | - | - | yes |
| (An) | yes | yes | yes | yes |
| (An)+ | yes | yes | - | yes |
| -(An) | yes | yes | - | yes |
| (d,An) | yes | yes | yes | yes |
| (d,An,Xi) | yes | yes | yes | yes |
| abs.W | yes | yes | yes | yes |
| abs.L | yes | yes | yes | yes |
| (d,PC) | yes | yes | yes | - |
| (d,PC,Xi) | yes | yes | yes | - |
| #imm | yes | yes | - | - |

Combined names are intersections: *data alterable* = data AND alterable (Dn, (An), (An)+,
-(An), (d,An), (d,An,Xi), abs.W, abs.L); *memory alterable* = the same without Dn;
*control alterable* = (An), (d,An), (d,An,Xi), abs.W, abs.L.

Why: *control* modes name an address without a size (usable by LEA, PEA, JMP, JSR);
*alterable* modes can be written, so PC-relative and immediate operands never can.

## Which instruction families accept which modes

Y = accepted, W = word/long only, 2 = 68020+ only, - = never.

| Instruction (operand) | Dn | An | (An) | (An)+ | -(An) | (d,An) | (d,An,Xi) | abs | (d,PC) | (d,PC,Xi) | #imm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MOVE source; ADD/SUB/CMP `<ea>,Dn` | Y | W | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| MOVEA, ADDA, SUBA, CMPA source | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| AND/OR `<ea>,Dn`, MULx, DIVx, CHK, MOVE to CCR/SR, BTST Dn,`<ea>` | Y | - | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| BTST #n,`<ea>` | Y | - | Y | Y | Y | Y | Y | Y | Y | Y | - |
| MOVE dest, ADDI/SUBI/ANDI/ORI/EORI, EOR, CLR, NEG(X), NOT, Scc, TAS, NBCD, BSET/BCLR/BCHG | Y | - | Y | Y | Y | Y | Y | Y | - | - | - |
| TST | Y | 2 | Y | Y | Y | Y | Y | Y | 2 | 2 | 2 |
| CMPI destination | Y | - | Y | Y | Y | Y | Y | Y | 2 | 2 | - |
| ADDQ, SUBQ | Y | W | Y | Y | Y | Y | Y | Y | - | - | - |
| ADD/SUB/AND/OR `Dn,<ea>`, shifts/rotates on memory | - | - | Y | Y | Y | Y | Y | Y | - | - | - |
| LEA, PEA, JMP, JSR | - | - | Y | - | - | Y | Y | Y | Y | Y | - |
| MOVEM registers -> memory | - | - | Y | - | Y | Y | Y | Y | - | - | - |
| MOVEM memory -> registers | - | - | Y | Y | - | Y | Y | Y | Y | Y | - |

Register-only operands: MOVEQ, EXG, SWAP, EXT, shifts with a count, DBcc counter, LINK/UNLK.
Fixed modes: ADDX/SUBX/ABCD/SBCD (Dn,Dn or -(An),-(An)), CMPM ((An)+,(An)+),
MOVEP ((d,An) only).

## PC-relative addressing

`label(pc)` makes code position-independent and 2 bytes shorter than an abs.L reference
(no relocation entry either). Rules:

- Never a destination (not alterable, on any CPU): `move.w d0,counter(pc)` is illegal.
  Load the address and write through it.
- `(d,PC)` reaches +-32 KB; `(d,PC,Xi)` only -128..+127 bytes, so PC-indexed jump tables must
  sit right after the instruction.
- TST and CMPI accept PC-relative operands only on 68020+.

```asm
        lea     counter(pc),a0          ; position-independent address
        addq.w  #1,(a0)                 ; write through a register
        move.w  counter(pc),d0          ; reading PC-relative is fine
        rts
counter dc.w    0
```

## 68020+ extensions

On 68020, 68030, 68040, 68060 (including the A1200's 68EC020) the index modes gain a scale
factor and a full extension-word format, available wherever `(d,An,Xi)` / `(d,PC,Xi)` is:

| Form | vasm syntax | Effective address |
|---|---|---|
| Scaled index | `(d8,An,Xn.w*s)`, s = 1, 2, 4, 8 | An + Xn*s + d8 |
| Base displacement | `(bd,An,Xn*s)`, bd 16 or 32 bits | An + Xn*s + bd |
| Memory indirect, postindexed | `([bd,An],Xn*s,od)` | (longword at An + bd) + Xn*s + od |
| Memory indirect, preindexed | `([bd,An,Xn*s],od)` | (longword at An + bd + Xn*s) + od |

PC may replace An in each form; any of bd, An, Xn, od may be omitted.

```asm
        ; 68020+ only
        move.w  (table,pc,d0.w*2),d1    ; word table indexed without "add d0,d0"
        move.l  (8,a0,d1.l*4),d2        ; array of longs
        lea     ([4,a0],d0.l*2,8),a1    ; a1 = (a0+4 pointer) + d0*2 + 8
table   dc.w    0,1,2,3
```

- Selecting `-m68020` lets vasm silently use these forms (for example it turns
  `(-129,a0,d0)` into a full-format index); build 68000 code with `-m68000` so such operands
  are rejected instead of producing code that crashes an A500.
- Memory-indirect modes cost extra memory reads; use them for clarity, not speed.

## Common mistakes

- Writing through PC-relative operands, or expecting `tst label(pc)` / `cmpi #x,label(pc)` to
  assemble for a 68000.
- `(a0,d0)` with a large or unsigned index: the default `.w` sign-extends, so d0.w = $8000
  indexes 32768 bytes BELOW a0. Use `d0.l` with a clean 32-bit value.
- `movea.w #$8000,a0` / abs.W `$8000.w`: word addresses and values are sign-extended.
  `lea $8000,a0` or `move.l #$8000,a0` give `$00008000`.
- Clearing an address register with `clr`: CLR does not accept An (`suba.l a0,a0`).
- `movem.l d0-d1,(sp)+` or `movem.l -(sp),d0-d1`: save only to `-(An)`/control modes,
  restore only from `(An)+`/control modes.
- Out-of-range index displacements in jump tables placed far from the `jmp (tab,pc,d0.w)`.
- Using 68020 scaled or memory-indirect modes in code that must run on a 68000.

**See also:** [condition codes](condition-codes.md), [cpu models](cpu-models.md),
[LEA](../instructions/data-movement.md#lea), [JMP](../instructions/program-control.md#jmp),
[MOVEM](../instructions/data-movement.md#movem)
