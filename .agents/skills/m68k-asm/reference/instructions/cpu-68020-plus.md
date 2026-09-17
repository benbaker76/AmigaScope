# 68020+ instructions, extensions and FPU

Notation (sizes, CCR symbols, mode names) as in [data movement](data-movement.md). Everything
here crashes a 68000/68010 (illegal-instruction or line-F exception): check exec
`AttnFlags` (`AFB_68020`, set for 68030/68040 too) before running it, and assemble with a
matching vasm CPU option (`-m68020`, `-m68030`, `-m68040`, `-m68060`; add `-m68881` or
`-m68882` for coprocessor FPU code). The A1200 has a 68EC020, the A3000 a 68030, the A4000 a
68030 or 68040; accelerators add 68030/68040/68060 (see [cpu models](../topics/cpu-models.md)).

Mode groups used below: control = (An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC), (d,PC,Xi);
control alterable = the same without the PC-relative modes; plus the 68020 extended forms of
each (see [addressing modes](../topics/addressing-modes.md)).

## 68020 extensions to 68000 instructions
Branch, check, link and test instructions that gain wider operands on 68020+.

- `Bcc.L`, `BRA.L`, `BSR.L`: 32-bit displacement (8-bit field $FF + longword).
- `CHK.L <ea>,Dn`: longword bound (vector 6 as before).
- `LINK.L An,#<disp32>`: 32-bit displacement.
- `TST`: also An (W/L), #imm, (d,PC), (d,PC,Xi).
- `CMPI`: destination may be (d,PC), (d,PC,Xi).
- Addressing: scaled index `(d,An,Xn.L*4)`, 32-bit base displacement `(bd,An,Xn)`, memory
  indirect `([bd,An],Xn,od)` / `([bd,An,Xn],od)`, and the PC-relative versions, wherever the
  68000 accepted `(d,An,Xi)` / `(d,PC,Xi)`.
- MOVEC: CACR, CAAR, MSP, ISP (see [MOVEC](system.md#movec)).

### Example
```asm
        tst.l   a0                      ; 68020+: no need for "move.l a0,d0"
        move.l  (table,pc,d0.w*4),a1    ; 68020+: scaled index, no ADD needed
        bra.l   far                     ; 68020+: 32-bit branch
table   dc.l    0
```

**See also:** [Bcc](program-control.md#bcc), [LINK](data-movement.md#link), [TST](arithmetic.md#tst)

## BFTST, BFSET, BFCLR, BFCHG
`BFTST <ea>{offset:width}` / `BFSET` / `BFCLR` / `BFCHG` (same syntax) · 68020+

Test a bit field (N, Z), then leave it, set it, clear it or invert it.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

N = most significant bit of the field, Z = all field bits were zero (both from the value
before modification).

Offset: `#0-31` immediate, or a data register holding a signed 32-bit offset (so the field
can lie beyond the base byte). Width: 1-32 immediate, or a data register (modulo 32, 0 = 32).
Offset 0 is the MOST significant bit: bit 31 of Dn, or bit 7 of the first byte at `<ea>`.
BFTST modes: Dn or control. BFSET/BFCLR/BFCHG modes: Dn or control alterable.

### Example
```asm
        ; 68020+: allocation bitmap, bit offset in d1
        bftst   (a0){d1:1}              ; is this block used?
        bne.s   .used
        bfset   (a0){d1:1}              ; claim it
.used   rts
```

### Gotchas
- vasm syntax: offset and width in braces straight after the operand, `{d1:5}` or `{3:5}`.
- Bit numbering is the reverse of BTST (BTST bit 0 = LSB, bit field offset 0 = MSB).
- Only the bytes containing the field are read and written (up to 5 bytes).

**See also:** BFEXTU, BFEXTS, BFFFO, BFINS, [BTST](bit.md#btst)

## BFEXTU, BFEXTS
`BFEXTU <ea>{offset:width},Dn` / `BFEXTS <ea>{offset:width},Dn` · 68020+

Extract a bit field into Dn, zero-extended (BFEXTU) or sign-extended (BFEXTS) to 32 bits.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

Offset/width rules as for BFTST. Modes: Dn or control (PC-relative allowed).

### Example
```asm
        ; 68020+: read 5-bit codes from a packed bit stream
        moveq   #0,d1                   ; bit position
        bfextu  (a0){d1:5},d0           ; d0 = next 5 bits, 0..31
        addq.l  #5,d1
        bfexts  d2{4:4},d3              ; bits 27-24 of d2 as -8..7
```

### Gotchas
- `bfextu d0{4:4},d1` with d0 = $0F000000 gives $F (offset counts from the MSB).

**See also:** BFINS, BFFFO, [LSR](shift-rotate.md#lsl-lsr)

## BFFFO
`BFFFO <ea>{offset:width},Dn` · 68020+

Find the first 1 bit (from the MSB end) of a bit field and return its offset in Dn.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

Dn = field offset + position of the first set bit; if none is set, Dn = offset + width and
Z = 1. Modes: Dn or control.

### Example
```asm
        bfffo   d0{0:32},d1             ; 68020+: d1 = 31 - (highest set bit number)
        beq.s   .zero                   ; d0 was 0, d1 = 32
        moveq   #31,d2
        sub.l   d1,d2                   ; d2 = index of the highest set bit
.zero   rts
```

### Gotchas
- The result counts from the MSB, not the LSB; convert with `31 - n` for a bit number.

**See also:** BFTST, BFEXTU

## BFINS
`BFINS Dn,<ea>{offset:width}` · 68020+

Insert the low `width` bits of Dn into a bit field.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

N and Z describe the inserted value. Modes: Dn or control alterable.

### Example
```asm
        moveq   #$a,d0
        moveq   #4,d1
        bfins   d0,(a0){d1:4}           ; 68020+: $00000000 at (a0) becomes $0A000000
```

**See also:** BFEXTU, BFSET

## CAS, CAS2
`CAS Dc,Du,<ea>` · B/W/L / `CAS2 Dc1:Dc2,Du1:Du2,(Rn1):(Rn2)` · W/L · 68020+

Compare memory with Dc: if equal store Du there, else copy the memory value into Dc.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | * | * |

Flags as for CMP (memory - Dc). CAS2 updates two locations only if both compare equal.
CAS modes: memory alterable -- (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        cas.w   d0,d1,(a0)              ; 68020+: if (a0)=d0 then (a0)=d1 (Z=1) else d0=(a0)
```

### Gotchas
- Uses a locked read-modify-write cycle like TAS, which the Amiga's DMA architecture does not
  support on Chip RAM; single-CPU Amiga code has no need for it.
- Emulated in software on the 68060 (unverified).

**See also:** [TAS](bit.md#tas), [CMP](arithmetic.md#cmp)

## CHK2, CMP2
`CHK2 <ea>,Rn` / `CMP2 <ea>,Rn` · B/W/L · 68020+

Check Rn against a bounds pair at `<ea>`: CHK2 traps (vector 6), CMP2 only sets flags.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | U | * | U | * |

Z = Rn equals either bound; C = Rn out of range. The pair is stored lower bound first.
For signed ranges use the arithmetically smaller value as the lower bound, for unsigned the
logically smaller. Byte/word on a data register compare only the low part; on An the bounds
are sign-extended and all 32 bits compared. Modes: control.

### Example
```asm
        cmp2.w  bounds(pc),d0           ; 68020+: 16 <= d0.w <= 199 ?
        bcs.s   .out                    ; C = 1: out of range
        moveq   #0,d1
.out    rts
bounds  dc.w    16,199
```

### Gotchas
- Emulated in software on the 68060 (unverified).

**See also:** [CHK](system.md#chk), [CMP](arithmetic.md#cmp)

## MULS.L, MULU.L
`MULS.L <ea>,Dl` / `MULS.L <ea>,Dh:Dl` (MULU.L alike) · L · 68020+

Multiply 32 x 32 bits, keeping the low 32 bits in Dl or the full 64 bits in Dh:Dl.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | * | 0 |

V (32-bit result form only) = the high half was not the sign extension (MULS) / not zero
(MULU). Source modes: data -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L,
(d,PC), (d,PC,Xi), #imm.

### Example
```asm
        ; 68020+: 16.16 fixed-point multiply d0 = d0 * d1
        muls.l  d1,d2:d0                ; d2:d0 = 64-bit product
        clr.w   d0
        swap    d0                      ; d0 = product bits 31-16
        swap    d2
        clr.w   d2                      ; d2 = product bits 47-32, shifted up 16
        or.l    d2,d0                   ; d0 = bits 47-16 = 16.16 result
```

### Gotchas
- `Dh:Dl` with Dh = Dl gives undefined results.
- The 64-bit forms are emulated in software on the 68060 (unverified); the 32-bit result form
  is the fast one.

**See also:** DIVS.L, DIVU.L, [MULS, MULU](arithmetic.md#muls-mulu)

## DIVS.L, DIVU.L
`DIVU.L <ea>,Dq` (32/32) · `DIVU.L <ea>,Dr:Dq` (64/32) · `DIVUL.L <ea>,Dr:Dq` (32/32 with remainder) · DIVS alike · 68020+

Long division: quotient in Dq; remainder in Dr for the `Dr:Dq` forms.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | * | 0 |

Divide by zero -> vector 5. Overflow (quotient does not fit 32 bits) sets V and leaves the
operands unchanged; N and Z are then undefined. Source modes: data -- Dn, (An), (An)+,
-(An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC), (d,PC,Xi), #imm.

### Example
```asm
        divul.l d0,d2:d1                ; 68020+: d1 = d1/d0, d2 = remainder (32-bit dividend)
        moveq   #0,d5                   ; high half of a 64-bit dividend
        divu.l  d3,d5:d4                ; 68020+: d5:d4 / d3 -> d4 quotient, d5 remainder
```

### Gotchas
- `divu.l x,Dr:Dq` takes a 64-BIT dividend from Dr:Dq; garbage in Dr gives garbage or
  overflow. For "32/32 with remainder" write DIVUL/DIVSL.
- If Dr and Dq are the same register only the quotient is returned.
- DIVS remainder has the sign of the dividend.
- The 64/32 form is emulated in software on the 68060 (unverified).

**See also:** MULS.L, MULU.L, [DIVS, DIVU](arithmetic.md#divs-divu)

## EXTB
`EXTB.L Dn` · L · 68020+

Sign-extend the low byte of Dn to 32 bits in one step.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

### Example
```asm
        move.b  (a0)+,d0
        extb.l  d0                      ; 68020+: $80 -> $FFFFFF80
```

**See also:** [EXT](arithmetic.md#ext)

## PACK, UNPK
`PACK Dx,Dy,#<adj>` / `PACK -(Ax),-(Ay),#<adj>` · `UNPK` alike · 68020, 68030, 68040

Convert between one packed BCD byte and two unpacked digit bytes, with an adjustment.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

PACK (register form): add adj to the source word, then join its bits 11-8 and 3-0 into the
low byte of Dy (rest of Dy unchanged). UNPK (register form): spread the two digits of the
source byte into bits 11-8 and 3-0, add adj, store as the low word of Dy (high word
unchanged). The predecrement forms read/write bytes in memory. Adjustment for ASCII: `#$3030`.

### Example
```asm
        unpk    d0,d1,#$3030            ; 68020+: d0.b = $47 -> d1.w = "47" ($3437)
        move.w  #"49",d2
        pack    d2,d3,#0                ; 68020+: ASCII "49" -> d3.b = $49
```

### Gotchas
- PACK ignores the upper nibbles, so `#0` works for ASCII input (the adjustment is added
  first, then only the low nibbles are kept).
- Not on the CPU32; emulated in software on the 68060 (unverified).

**See also:** [ABCD](bcd.md#abcd)

## TRAPcc
`TRAPcc` / `TRAPcc.W #<data>` / `TRAPcc.L #<data>` · 68020+

Take the TRAPcc exception (vector 7) if cc is true; the operand is for the handler.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

cc = the Bcc conditions plus T and F. The stacked PC is the next instruction.

### Example
```asm
        cmp.l   d1,d0
        traphi                          ; 68020+: trap if d0 > d1 (unsigned)
```

### Gotchas
- `TRAPF` never traps: a 2-, 4- or 6-byte no-op.

**See also:** [TRAPV](system.md#trapv), [TRAP](system.md#trap)

## CALLM, RTM
`CALLM #<argcount>,<ea>` / `RTM Rn` · 68020 only

Call a module through a module descriptor and return from it (68020 modules).

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

CALLM modes: control. RTM sets the CCR from the saved module state.

### Gotchas
- Removed from the 68030 and later; never used by Amiga software. Do not emit.

**See also:** [JSR](program-control.md#jsr)

## MOVE16
`MOVE16 (Ax)+,(Ay)+` / `MOVE16 abs.L,(An)` / `abs.L,(An)+` / `(An),abs.L` / `(An)+,abs.L` · 68040+

Copy one 16-byte block ("line") between 16-byte-aligned addresses using burst transfers.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Postincrement registers advance by 16.

### Example
```asm
        ; 68040+: copy d7*16 bytes between 16-byte aligned buffers
        subq.w  #1,d7
.copy   move16  (a0)+,(a1)+
        dbf     d7,.copy
```

### Gotchas
- The low 4 bits of the addresses are ignored: both buffers MUST be aligned to 16 bytes or
  the wrong bytes are copied.
- Not on 68020/68030; present on the 68060 (unverified).

**See also:** [MOVE](data-movement.md#move), [optimisation](../topics/optimisation.md)

## Availability on 68030, 68040 and 68060
Which 68020 additions are missing or software-emulated on later CPUs.

| Instruction | 68020 | 68030 | 68040 | 68060 |
|---|---|---|---|---|
| BFxxx, EXTB, TRAPcc, LINK.L, long Bcc | yes | yes | yes | yes (unverified) |
| MULx.L / DIVx.L 32-bit forms | yes | yes | yes | yes (unverified) |
| MULx.L 64-bit, DIVx.L 64/32 | yes | yes | yes | software (unverified) |
| CAS, CAS2, CHK2, CMP2 | yes | yes | yes | software (unverified) |
| PACK, UNPK | yes | yes | yes | software (unverified) |
| CALLM, RTM | yes | no | no | no |
| MOVEP (68000 instruction) | yes | yes | yes | no |
| MOVE16, CINV, CPUSH | no | no | yes | yes (unverified) |
| FPU instructions | 68881/68882 chip | 68881/68882 chip | on-chip (not 68LC040/68EC040); part in software | on-chip (not LC/EC) (unverified) |

"Software" means the CPU traps and a support package emulates the instruction; on the Amiga
this is the CPU library installed at boot (68040.library / 68060.library) (unverified). Code
that must be fast on every CPU avoids the emulated instructions.

**See also:** [cpu models](../topics/cpu-models.md), [MOVEP](data-movement.md#movep)

## FPU (68881, 68882, 68040, 68060)
Floating-point instructions of the 68881/68882 and the on-chip 68040/68060 FPU.

Programmer's model: FP0-FP7 (80-bit extended, 12 bytes in memory), FPCR (control),
FPSR (status: condition codes, quotient, exceptions), FPIAR (instruction address).
Operand formats (size suffix): `.b` `.w` `.l` integer, `.s` single, `.d` double,
`.x` extended, `.p` packed decimal. All opcodes are line F ($Fxxx): without an FPU they
raise vector 11.

| Group | Mnemonics | Syntax |
|---|---|---|
| Dyadic | FADD FSUB FMUL FDIV FMOD FREM FSCALE FSGLDIV FSGLMUL FCMP | `Fop.<fmt> <ea>,FPn` / `Fop.X FPm,FPn` |
| Monadic | FABS FNEG FSQRT FINT FINTRZ FGETEXP FGETMAN FSIN FCOS FTAN FASIN FACOS FATAN FSINH FCOSH FTANH FATANH FETOX FETOXM1 FLOGN FLOGNP1 FLOG10 FLOG2 FTENTOX FTWOTOX | `Fop.<fmt> <ea>,FPn` / `Fop.X FPm,FPn` / `Fop.X FPn` |
| Sine and cosine | FSINCOS | `FSINCOS.<fmt> <ea>,FPc:FPs` |
| Test | FTST | `FTST.<fmt> <ea>` / `FTST.X FPm` |
| Move | FMOVE FMOVEM FMOVECR | see entries below |
| Conditional | FBcc FDBcc FScc FTRAPcc | `FBcc.W/.L <label>`, `FDBcc Dn,<label>`, `FScc.B <ea>`, `FTRAPcc[.W/.L #<data>]` |
| Other | FNOP; FSAVE FRESTORE (supervisor) | `FNOP`, `FSAVE <ea>`, `FRESTORE <ea>` |
| 68040 rounding | FSADD FDADD FSSUB FDSUB FSMUL FDMUL FSDIV FDDIV FSABS FDABS FSNEG FDNEG FSSQRT FDSQRT FSMOVE FDMOVE | as the base instruction; result rounded to single (FS) or double (FD) |

68040 hardware executes FABS FADD FBcc FCMP FDBcc FDIV FMOVE FMOVEM FMUL FNEG FNOP
FRESTORE FSAVE FScc FSQRT FSUB FSGLDIV FSGLMUL FTRAPcc FTST; all other FPU instructions
(including FMOVECR, FINT, FINTRZ and the transcendental functions) trap to software.

### Example
```asm
        ; FPU: uses only instructions the 68040 runs in hardware
        fmove.l d0,fp0                  ; integer -> extended
        fmul.s  scale(pc),fp0
        fmove.l fp0,d1                  ; rounded per FPCR
        rts
scale   dc.s    1.5
```

### Gotchas
- `AFB_FPU40` set without `AFB_68881`/`AFB_68882` in `AttnFlags` means the 68040 emulation
  code is not loaded: only the hardware subset above is available.
- vasm needs `-m68881`/`-m68882` (or a 68040/68060 CPU option) to accept FPU mnemonics.
- Keep the FPU context in mind in interrupt code: use FSAVE/FMOVEM to preserve it.

**See also:** FMOVE, FMOVEM, FMOVECR, FBcc, FSAVE, FRESTORE

## FMOVE
`FMOVE.<fmt> <ea>,FPn` / `FMOVE.<fmt> FPm,<ea>` / `FMOVE.X FPm,FPn` / `FMOVE.L <ea>,FPcr` / `FMOVE.L FPcr,<ea>` · 68881/68882/68040

Move a value to or from an FPU data register (converting it) or FPCR/FPSR/FPIAR.

CCR not affected. FPSR condition codes are set from the value moved (data-register forms).

FPcr = `fpcr`, `fpsr` or `fpiar` (32-bit transfer). Memory-to-memory FMOVE does not exist.
`FMOVE.P FPm,<ea>{#k}` / `{Dn}` gives the packed-decimal k-factor.

### Example
```asm
        fmove.l fpcr,d0                 ; FPU: read control register
        fmove.d (a0),fp1                ; double -> FP1
        fmove.s fp1,-(sp)               ; FP1 -> single on the stack
```

### Gotchas
- Converting to an integer format rounds with the FPCR rounding mode; FINTRZ first for C-style
  truncation.

**See also:** FMOVEM, FPU

## FMOVEM
`FMOVEM.X <list>,<ea>` / `FMOVEM.X <ea>,<list>` / `FMOVEM.L <crlist>,<ea>` · 68881/68882/68040

Save or restore several FP data registers (12 bytes each) or control registers in one go.

CCR not affected. FPSR unchanged (unless FPSR itself is in a control-register list).

Data-register list: `fp0-fp7` / `fp2/fp4`, or a Dn holding the mask. `-(An)` stores FP7..FP0
downward; control modes and `(An)+` transfer FP0..FP7 upward. Control-register list:
`fpcr/fpsr/fpiar` (always transferred in that order).

### Example
```asm
        fmovem.x fp2-fp7,-(sp)          ; FPU: save callee-saved FP registers
        fmovem.x (sp)+,fp2-fp7
        fmovem.l fpcr/fpsr,-(sp)
        fmovem.l (sp)+,fpcr/fpsr
```

### Gotchas
- The only way to move extended values without conversion and without touching FPSR.

**See also:** FMOVE, FSAVE, FRESTORE, [MOVEM](data-movement.md#movem)

## FMOVECR
`FMOVECR.X #<offset>,FPn` · 68881/68882 (68040: software)

Load a constant from the FPU's ROM into FPn.

| Offset | Constant | Offset | Constant |
|---|---|---|---|
| $00 | pi | $32 | 10^0 |
| $0B | log10(2) | $33 | 10^1 |
| $0C | e | $34 | 10^2 |
| $0D | log2(e) | $35 | 10^4 |
| $0E | log10(e) | $36 | 10^8 |
| $0F | 0.0 | $37 | 10^16 |
| $30 | ln(2) | $38-$3F | 10^32, 10^64, 10^128, 10^256, 10^512, 10^1024, 10^2048, 10^4096 |
| $31 | ln(10) | | |

### Example
```asm
        fmovecr #$00,fp0                ; FPU: fp0 = pi
```

### Gotchas
- Emulated (slow) on the 68040; other offsets are reserved and give 0.0 in the emulation.

**See also:** FMOVE, FPU

## FBcc
`FBcc.W <label>` / `FBcc.L <label>` · also `FDBcc Dn,<label>`, `FScc <ea>`, `FTRAPcc` · 68881/68882/68040

Branch (or loop, set a byte, trap) on one of 32 floating-point conditions from the FPSR.

| Code | cc | Code | cc | Code | cc | Code | cc |
|---|---|---|---|---|---|---|---|
| $00 | F | $08 | UN | $10 | SF | $18 | NGLE |
| $01 | EQ | $09 | UEQ | $11 | SEQ | $19 | NGL |
| $02 | OGT | $0A | UGT | $12 | GT | $1A | NLE |
| $03 | OGE | $0B | UGE | $13 | GE | $1B | NLT |
| $04 | OLT | $0C | ULT | $14 | LT | $1C | NGE |
| $05 | OLE | $0D | ULE | $15 | LE | $1D | NGT |
| $06 | OGL | $0E | NE | $16 | GL | $1E | SNE |
| $07 | OR | $0F | T | $17 | GLE | $1F | ST |

Codes as encoded by vasm. `O` tests are false when an operand is a NaN, `U` tests are true
then. The IEEE non-aware tests set the BSUN exception bit when a NaN is involved; these are
the $10-$1F group (unverified).

### Example
```asm
        fcmp.l  #0,fp0                  ; FPU: compare fp0 with 0
        fblt    .negative
        rts
.negative
        fneg    fp0
        rts
```

### Gotchas
- Displacement is word or long; there is no short FBcc. Integer Bcc tests the CPU CCR, not
  the FPU condition codes.

**See also:** FPU, [Bcc](program-control.md#bcc)

## FSAVE, FRESTORE
`FSAVE <ea>` / `FRESTORE <ea>` · 68881/68882/68040 · supervisor only

Save or restore the FPU's internal (user-invisible) state as a state frame.

State frame sizes: NULL 4 bytes (FPU unused since reset); IDLE 4 (68040), 28 (68881),
60 (68882); UNIMP 48 (68040 only); BUSY 96 (68040), 184 (68881), 216 (68882).
FSAVE modes: control alterable or -(An). FRESTORE modes: control or (An)+.

### Example
```asm
        fsave   -(sp)                   ; FPU, supervisor: context switch save
        tst.b   (sp)                    ; NULL frame: nothing else to save
        beq.s   .null
        fmovem.x fp0-fp7,-(sp)
        fmovem.l fpcr/fpsr/fpiar,-(sp)
.null                                   ; ... continue the context switch
```

### Gotchas
- Full save order: FSAVE first, then FMOVEM the registers; restore with FMOVEM first, then
  FRESTORE. A NULL frame restored with FRESTORE resets the FPU.

**See also:** FMOVEM, [cpu models](../topics/cpu-models.md)
