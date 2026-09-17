# 68000 instructions: program control

Notation (sizes, CCR symbols, mode names) as in [data movement](data-movement.md). None of
the branch, jump or loop instructions changes the CCR except RTR. The full condition table
with signed/unsigned guidance is in [condition codes](../topics/condition-codes.md).

Branch displacements are relative to the address of the branch instruction + 2. Size
suffixes in vasm: `.s` or `.b` = 8-bit displacement (2-byte instruction, -128..+127),
`.w` = 16-bit (4 bytes, -32768..+32767), `.l` = 32-bit (6 bytes, 68020+). Without a suffix
vasm picks the smallest size that reaches (with `-no-opt` it uses `.w`).

## Bcc
`Bcc <label>` · B/W (L on 68020+) · 68000

Branch to the label if condition cc is true, otherwise continue with the next instruction.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

| cc | Code | Branch when | Test |
|---|---|---|---|
| HI | $2 | unsigned higher | C=0 and Z=0 |
| LS | $3 | unsigned lower or same | C=1 or Z=1 |
| CC, HS | $4 | carry clear / unsigned higher or same | C=0 |
| CS, LO | $5 | carry set / unsigned lower | C=1 |
| NE | $6 | not equal / not zero | Z=0 |
| EQ | $7 | equal / zero | Z=1 |
| VC | $8 | no overflow | V=0 |
| VS | $9 | overflow | V=1 |
| PL | $A | plus (N clear) | N=0 |
| MI | $B | minus (N set) | N=1 |
| GE | $C | signed greater or equal | N=V |
| LT | $D | signed less | N<>V |
| GT | $E | signed greater | Z=0 and N=V |
| LE | $F | signed less or equal | Z=1 or N<>V |

Opcode `$6c dd` (c = code, dd = 8-bit displacement; `dd=$00` -> word follows; `dd=$FF` ->
long follows on 68020+).

### Example
```asm
        cmp.w   #200,d0                 ; d0.w - 200
        bhs.s   .clip                   ; unsigned d0 >= 200
        tst.l   d1
        bmi.s   .neg                    ; sign bit set
        rts
.clip   move.w  #199,d0
.neg    rts
```

### Gotchas
- There is no BT or BF: condition codes 0 and 1 are used by BRA and BSR.
- A short branch to the immediately following instruction cannot be encoded (displacement 0
  means "word follows"); vasm replaces `bra.s next` with a 2-byte no-op and warns.
- Do not force `.s` where the target may drift out of range; vasm reports
  "branch destination out of range".
- `.l` branches assemble only with a 68020+ CPU option and crash a 68000.

**See also:** BRA, DBcc, Scc, [CMP](arithmetic.md#cmp), [TST](arithmetic.md#tst)

## BRA
`BRA <label>` · B/W (L on 68020+) · 68000

Branch unconditionally (PC-relative, so position-independent).

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

### Example
```asm
.mainloop
        bsr.s   WaitVBL
        bra.s   .mainloop               ; 2 bytes
WaitVBL rts
```

### Gotchas
- Prefer BRA over `jmp label`: shorter, relocatable; vasm converts in-range `jmp label` to
  BRA by default.

**See also:** Bcc, BSR, JMP

## BSR
`BSR <label>` · B/W (L on 68020+) · 68000

Push the return address (longword) and branch to a subroutine PC-relatively.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Operation: SP-4 -> SP; PC -> (SP); PC + d -> PC.

### Example
```asm
        bsr.s   Clear                   ; 2 bytes, returns here
        bsr     Setup                   ; vasm picks .s or .w
        rts
Clear   moveq   #0,d0
        rts
Setup   rts
```

### Gotchas
- Same range rules as Bcc; for far or computed targets use JSR.

**See also:** JSR, RTS, BRA

## DBcc
`DBcc Dn,<label>` · W (16-bit displacement) · 68000

Loop primitive: if cc is false, decrement Dn.w and branch unless it became -1.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

cc = any Bcc condition plus T (never loops) and F (loop on count only). `DBRA` is accepted
for `DBF`.

Operation: if cc true -> fall through (Dn unchanged); else Dn.w - 1 -> Dn.w;
if Dn.w = -1 fall through, else branch.

### Example
```asm
        ; copy 64 bytes: counter starts at count-1, body runs count times
        moveq   #64-1,d7
.copy   move.b  (a0)+,(a1)+
        dbf     d7,.copy

        ; count may be 0: enter at the DBF, body runs exactly count times
        move.w  (a2),d6
        bra.s   .test
.clear  clr.b   (a3)+
.test   dbf     d6,.clear
        rts
```

### Gotchas
- A counter starting at n runs the body n+1 times (it stops at -1, not 0). Starting at 0
  runs it once; starting at $FFFF runs it 65536 times.
- Only the low word is used and changed; the upper word of Dn is left as it was, and after a
  full count Dn.w = $FFFF.
- The condition is an EXIT test ("decrement and branch until cc"): `dbeq d0,.loop` stops
  when Z=1. The flags seen are those of the last instruction before the DBcc.
- 16-bit displacement only (no `.s` form); the counter must be a data register.

**See also:** Bcc, [SUBQ](arithmetic.md#subq), [CMPM](arithmetic.md#cmpm), [optimisation](../topics/optimisation.md)

## Scc
`Scc <ea>` · B · 68000

Set a byte to $FF if condition cc is true, otherwise to $00.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

cc = any Bcc condition plus `ST` (always $FF) and `SF` (always $00).
Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        cmp.w   d1,d0
        sgt     d2                      ; d2.b = $FF if d0 > d1 (signed), else $00
        neg.b   d2                      ; $FF -> 1, $00 -> 0 (if a 0/1 value is wanted)
```

### Gotchas
- TRUE is $FF (-1), not 1. Only the low byte of a data register changes.
- On the 68000 a memory destination is read before it is written.

**See also:** Bcc, [NEG](arithmetic.md#neg)

## JMP
`JMP <ea>` · 68000

Continue execution at the effective address.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Modes: control -- (An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC), (d,PC,Xi).

### Example
```asm
        ; PC-relative jump table, d0.w = case number (0 or 1)
        add.w   d0,d0
        move.w  .table(pc,d0.w),d0
        jmp     .table(pc,d0.w)
.table  dc.w    .case0-.table
        dc.w    .case1-.table
.case0  moveq   #10,d1
        rts
.case1  moveq   #11,d1
        rts
```

### Gotchas
- `jmp label` (absolute) needs relocation and is not position-independent; `jmp (a0)` jumps
  TO a0, it does not read a pointer stored at (a0) (`move.l (a0),a0` first).
- `(d,PC,Xi)` has an 8-bit displacement: the table must start within -128..+127 bytes of the
  extension word, otherwise vasm reports "displacement out of range".
- On a 68000/68EC020 the top 8 address bits are ignored, on 68020/030/040/060 they are not:
  never store flags in the high byte of a jump address.

**See also:** JSR, BRA, [LEA](data-movement.md#lea), [cpu models](../topics/cpu-models.md)

## JSR
`JSR <ea>` · 68000

Push the return address and continue at the effective address.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Modes: control -- (An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC), (d,PC,Xi).

### Example
```asm
        include "exec/memory.i"
        include "lvo/exec_lib.i"
        move.l  4.w,a6                  ; ExecBase
        move.l  #1024,d0
        move.l  #MEMF_CHIP!MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)        ; library call: JSR through the base
        tst.l   d0
        beq.s   .nomem
        jsr     (a0)                    ; call a routine whose address is in a0
.nomem  rts
```

### Gotchas
- Library calls always use `jsr _LVOxxx(a6)`; the jump table entry is at a negative
  offset from the base.
- In-range `jsr label` is turned into BSR by vasm's default optimisation.

**See also:** BSR, RTS, JMP, [PEA](data-movement.md#pea)

## RTS
`RTS` · 68000

Pop a longword return address into the PC.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

### Example
```asm
Sub     movem.l d2/a2,-(sp)
        ; ...
        movem.l (sp)+,d2/a2             ; stack must be back where it was
        rts
```

### Gotchas
- Any unbalanced push/pop inside the routine makes RTS jump to garbage.
- `rts` does not restore flags; use RTR for that.

**See also:** RTR, BSR, JSR, [RTE](system.md#rte), [RTD](system.md#rtd)

## RTR
`RTR` · 68000

Pop a word into the CCR, then pop the return address into the PC.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

Operation: (SP) -> CCR; SP+2 -> SP; (SP) -> PC; SP+4 -> SP. The system byte of SR is not
changed.

### Example
```asm
Proc    move    ccr,-(sp)               ; 68010+ (user mode); on a plain 68000: move sr,-(sp)
        moveq   #0,d0                   ; body trashes the flags
        rtr                             ; caller gets its flags back
```

### Gotchas
- Needs a word pushed above the return address. `move sr,-(sp)` for this is privileged on
  68010+; `move ccr,-(sp)` does not exist on the 68000 (see
  [MOVE from SR](data-movement.md#move-from-sr)).

**See also:** RTS, [MOVE from CCR](data-movement.md#move-from-ccr)

## NOP
`NOP` · 68000

Do nothing (opcode $4E71), except let the PC advance.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

### Example
```asm
        nop                             ; 2-byte padding / patch space
```

### Gotchas
- Not a delay: timing loops of NOPs vary with CPU speed and caches. Use CIA timers or
  raster position.
- On later CPUs NOP waits for pending bus cycles, which makes it a pipeline synchroniser.

**See also:** BRA, [cpu models](../topics/cpu-models.md)
