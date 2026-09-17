# 68000 instructions: single-bit operations

Notation (sizes, CCR symbols, mode names) as in [data movement](data-movement.md).
Bit fields (BFxxx) are 68020+: see [68020+ instructions](cpu-68020-plus.md).

Common rules for BTST, BSET, BCLR, BCHG:

- Destination Dn: the operation is on the longword, bit number modulo 32.
- Destination in memory: the operation is on ONE BYTE, bit number modulo 8.
- Bit number either immediate (`#n`, extension word) or dynamic (low bits of a data register).
- Only Z changes, and it reflects the bit BEFORE the operation: Z=1 if the bit was 0.
  So `beq` = "bit was clear", `bne` = "bit was set".

## BTST
`BTST Dn,<ea>` / `BTST #<data>,<ea>` · B (memory) / L (Dn) · 68000

Test one bit and report its old state in Z; the operand is not changed.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | * | - | - |

Destination modes: data -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC),
(d,PC,Xi); `#imm` only with the dynamic `BTST Dn,<ea>` form.

### Example
```asm
        include "hardware/cia.i"
        btst    #CIAB_GAMEPORT0,$bfe001 ; CIA-A PRA bit 6: port-0 fire / left mouse
        bne.s   .up                     ; bit set = button NOT pressed (active low)
        moveq   #1,d0                   ; pressed
.up     rts
```

### Gotchas
- Memory tests use modulo 8 silently: `btst #9,(a0)` tests bit 1 and vasm does not warn.
  To test bit 9 of a memory WORD, test bit 1 of the upper byte: `btst #1,(a0)`.
- Byte-wide on memory means the big-endian order matters: bit 15 of a word at (a0) is bit 7
  of the byte at (a0).
- Z is inverted with respect to the bit value.

**See also:** BSET, BCLR, BCHG, [TST](arithmetic.md#tst), [BFTST](cpu-68020-plus.md#bftst-bfset-bfclr-bfchg)

## BSET
`BSET Dn,<ea>` / `BSET #<data>,<ea>` · B (memory) / L (Dn) · 68000

Test a bit (old state to Z), then set it to 1.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | * | - | - |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        include "hardware/cia.i"
        bset    #CIAB_LED,$bfe001       ; CIA-A /LED: 1 = power LED dim
        bset    #7,flags                ; Z tells whether it was already set
        bne.s   .wasset
        moveq   #0,d0                   ; first time here
.wasset rts
flags   dc.b    0
        even
```

### Gotchas
- Same modulo-8 rule on memory: `bset #15,(a0)` sets bit 7 of the byte at (a0).
- Read-modify-write on memory: do not use on write-only hardware registers.

**See also:** BCLR, BCHG, BTST, [ORI](logic.md#ori)

## BCLR
`BCLR Dn,<ea>` / `BCLR #<data>,<ea>` · B (memory) / L (Dn) · 68000

Test a bit (old state to Z), then clear it to 0.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | * | - | - |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        include "hardware/cia.i"
        bclr    #CIAB_LED,$bfe001       ; CIA-A /LED: 0 = power LED bright
        bclr    d1,d0                   ; clear bit (d1 mod 32) of d0
```

### Gotchas
- Same modulo rules and Z polarity as BTST.

**See also:** BSET, BCHG, [ANDI](logic.md#andi)

## BCHG
`BCHG Dn,<ea>` / `BCHG #<data>,<ea>` · B (memory) / L (Dn) · 68000

Test a bit (old state to Z), then invert it.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | * | - | - |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        bchg    #0,frame                ; toggle every call
        beq.s   .even                   ; bit was 0 before the toggle
        addq.w  #1,d7                   ; odd frames only
.even   rts
frame   dc.b    0
        even
```

### Gotchas
- Same modulo rules and Z polarity as BTST.

**See also:** BSET, BCLR, [EORI](logic.md#eori)

## TAS
`TAS <ea>` · B · 68000

Test a byte (N, Z from its old value) and set its bit 7 in one indivisible bus cycle.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | * | 0 | 0 |

Destination modes: data alterable -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L.

### Example
```asm
        tas     d0                      ; register form is harmless
        bmi.s   .busy                   ; bit 7 was already set
        moveq   #1,d1                   ; we set it
.busy   rts
```

### Gotchas
- The Amiga does NOT support TAS on memory: its read-modify-write cycle clashes with the
  custom chips' DMA access to Chip RAM. Use BSET (single CPU) or exec semaphores instead.

**See also:** BSET, [TST](arithmetic.md#tst)
