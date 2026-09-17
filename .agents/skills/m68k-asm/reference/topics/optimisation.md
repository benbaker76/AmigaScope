# Size and speed idioms

Classic 68000 idioms, each with the reason it is equivalent and what it saves. Byte counts
are instruction sizes from vasm output. Two rules before anything else: an idiom is only a
replacement if the flags it leaves are the ones the following code relies on, and vasm
already applies many of these rewrites itself (last section), so write clear code first and
check the listing when exact bytes matter.

## Loading constants

| Instead of | Write | Bytes | Why it is equivalent |
|---|---|---|---|
| `move.l #0,d0`, `clr.l d0` | `moveq #0,d0` | 6 / 2 -> 2 | MOVEQ loads all 32 bits; N=0 Z=1 V=0 C=0, X kept, like MOVE and CLR |
| `move.l #-5,d1` | `moveq #-5,d1` | 6 -> 2 | MOVEQ sign-extends its 8-bit value (-128..127 only) |
| `andi.l #$ff,d0` after loading a byte | `moveq #0,d0` then `move.b (a0),d0` | 2+6 -> 2+2 | the MOVE.B only replaces the low byte of an already-zero register |
| `move.l #0,a0` | `suba.l a0,a0` | 6 -> 2 | x - x = 0; SUBA touches no flags. CLR cannot address An |

Gotchas:
- `moveq` is not `move.b`/`move.w`: it overwrites the upper bytes.
- `clr.w d0` keeps the upper word; `moveq #0,d0` does not.
- Never replace `move.w #0,<hardware register>` by `clr`: on a 68000 CLR reads the register
  first, which can trigger strobe registers twice.

## Small additions and subtractions

| Instead of | Write | Bytes | Why |
|---|---|---|---|
| `addi.w #4,d0` | `addq.w #4,d0` | 4 -> 2 | ADDQ holds 1..8 in the opcode; same flags as ADDI |
| `adda.l #8,a0` | `addq.l #8,a0` | 6 -> 2 | neither changes the CCR on An |
| `adda.l #1000,a0` | `lea 1000(a0),a0` | 6 -> 4 | LEA of a 16-bit displacement; no flags either way |
| `lea (a0,d0.w),a0` | `adda.w d0,a0` | 4 -> 2 | both add sign-extended d0.w; no flags |

`addq`/`subq` on An change all 32 bits even with `.w`, so `.w` and `.l` are identical there.

## Flags you already have

MOVE, MOVEQ, arithmetic, logic and shifts set N and Z from their result; MOVE, MOVEQ and logic
also clear V and C exactly as TST does. So:

```asm
        move.l  (a0)+,d0                ; no "tst.l d0" needed
        beq.s   .end
        subq.w  #1,d7                   ; Z already says whether d7 hit 0
        bne.s   .more
        moveq   #-1,d0
.more
.end    rts
```

- `cmp #0,<ea>` = `tst <ea>` (2-4 bytes shorter; subtracting 0 never sets V or C).
- Instructions that do NOT set flags (TST required): MOVEA / `move ...,An`, MOVEM, LEA,
  ADDQ/SUBQ/ADDA/SUBA on An, EXG, library calls.

## Loops

```asm
        moveq   #100-1,d7               ; n-1: DBF runs the body n times
.loop   move.w  (a0)+,(a1)+
        dbf     d7,.loop
```

- `dbf dn,label` (4 bytes) replaces `subq.w #1,dn` + `bne.s label` (also 4 bytes); the gain is
  that DBcc leaves the flags from the body intact and can combine an exit condition
  (`dbeq`, `dbne` ...) with the count.
- The counter is 16-bit and ends at -1: load n-1, or enter at the DBF with n when n may be 0.
- Put the exit test in the DBcc instead of an extra Bcc inside the loop (`cmpm` + `dbne`).

## Pointer streaming instead of indexing

| Instead of | Write | Bytes |
|---|---|---|
| `move.l 0(a0,d1.w),0(a1,d1.w)` + `addq.w #4,d1` | `move.l (a0)+,(a1)+` | 6+2 -> 2 |

`(An)+` and `-(An)` read or write and step the pointer in the same instruction, with no
extension words and no index register to maintain.

## Shifts, adds and tables instead of MULU/DIVU

- Multiply by a power of two: `lsl.l #n,d0` (n = 1..8) works on all 32 bits, while MULU is
  only 16 x 16. `add.l d0,d0` doubles in 2 bytes with the same flags as `asl.l #1,d0`.
- Multiply by a constant: combine shifts and adds.

```asm
        ; d0.l = d0.l * 10
        add.l   d0,d0                   ; x*2
        move.l  d0,d1
        lsl.l   #2,d0                   ; x*8
        add.l   d1,d0                   ; x*8 + x*2
```

- Unsigned divide by 2^n: `lsr.l #n,d0`; remainder: `andi.l #(1<<n)-1,d0`. Signed values: ASR
  rounds towards minus infinity, DIVS towards zero; add (2^n)-1 to negative values first if
  DIVS semantics are needed.
- Repeated multiplies by the same small set of values (screen row offsets, sine scaling):
  precompute a table and index it (`add.w d0,d0` + `move.w table(pc,d0.w),d1`).
- On a 68000 MULU/MULS and especially DIVU/DIVS take many times longer than a shift or an add;
  published 68000 timings are roughly 38+2n clock periods for MULU (n = one bits in the
  source, up to 70) and up to about 140 for DIVU, against 6+2n for a register shift by n
  (unverified). On a 68020+ the difference is much smaller.
- A shift only reports the last bit shifted out (C, X) and, for ASL, a sign change (V); it
  does not tell you that higher bits were lost. Use the wider size when the result may grow.

## Branches, calls and addresses

| Instead of | Write | Bytes | Why |
|---|---|---|---|
| `bra.w`, `bne.w` to a near label | `bra.s`, `bne.s` | 4 -> 2 | 8-bit displacement reaches -128..+127 |
| `jsr Label` / `jmp Label` (abs.L) | `bsr Label` / `bra Label` | 6 -> 2 or 4 | PC-relative, no relocation |
| `move.l $00000004,a6` | `move.l 4.w,a6` | 6 -> 4 | abs.W is sign-extended, reaches $0-$7FFF |
| `move.w #x,$dff096` (abs.L) | `lea $dff000,a6` once, then `move.w #x,$096(a6)` | 8 -> 6 per access | 16-bit displacement instead of a 32-bit address |
| `lea Label,a0` (abs.L) | `lea Label(pc),a0` | 6 -> 4 | PC-relative |
| `rts` after `bsr Sub` at the end of a routine | `bra Sub` | 2+2 -> 2 | Sub's RTS returns to our caller (tail call) |

Leave branch sizes unspecified unless you need a fixed size: vasm picks `.s` when it reaches
and a forced `.s` that no longer reaches is an assembly error.

## MOVEM for one or two registers

| Registers | MOVEM | MOVE |
|---|---|---|
| 1 | `movem.l d0,-(sp)` = 4 bytes | `move.l d0,-(sp)` = 2 bytes |
| 2 | `movem.l d0-d1,-(sp)` = 4 bytes | two MOVEs = 4 bytes |
| 3+ | 4 bytes | 2 bytes each |

The catch: MOVE sets N and Z, MOVEM sets nothing. A restore between computing a result and
branching on it must stay MOVEM (exec's AddIntServer documentation warns about exactly this
MOVEM-to-MOVE rewrite breaking an interrupt server's Z return).

```asm
Server  movem.l d2,-(sp)                ; keep MOVEM: the flags below must survive
        moveq   #0,d2                   ; ... work that leaves Z set for "not mine" ...
        movem.l (sp)+,d2                ; restore without touching Z
        rts
```

## What vasm already does

With its default optimisations (no `-no-opt`), vasm 1.9 was observed to rewrite:

| Source | Emitted |
|---|---|
| `clr.l Dn`, `move.l #0,Dn` | `moveq #0,Dn` |
| `move.l #n,Dn`, n in -128..127 | `moveq #n,Dn` |
| `move.l #200,Dn` | `moveq #100,Dn` + `add.w Dn,Dn` (X and C now changed) |
| `move.l #$20000,Dn` | `moveq #2,Dn` + `swap Dn` |
| `addi`/`subi`/`add`/`sub #1..8` | `addq`/`subq` |
| `adda.l #1000,An` | `lea 1000(An),An` |
| `lea 8(An),An` | `addq.l #8,An`; `lea 0(An),An` is removed |
| `cmp #0`, `cmpi #0`, `or.l #0,Dn` | `tst` |
| `movea.l #100,An` | `movea.w #100,An` |
| `asl.l #1,Dn` | `add.l Dn,Dn` |
| `jsr`/`jmp label` in range | `bsr`/`bra`, shortest size |
| unsized branches | shortest size that reaches |
| abs.L address within $0000-$7FFF or $FFFF8000-$FFFFFFFF | abs.W |
| `sub.l An,An` | `suba.l An,An` |

Not rewritten (good): `move.w #0,<memory>` stays a MOVE (no CLR read), `movem` of one register
stays MOVEM, `mulu #4` stays MULU. `bra.s` to the next instruction becomes a 2-byte no-op with
a warning.

Use `-no-opt` (or check the listing) when code must be byte-exact, for example patch
tables, code copied or checksummed at run time, or when a MOVE of a constant must keep X/C.

## Common mistakes

- "Optimising" `move.w #0,$dff0xx` into `clr.w`: read-before-write on the 68000.
- Using `moveq` where only the low byte/word may change.
- Dropping a TST after MOVEA or MOVEM.
- Replacing a MOVEM restore by MOVE ahead of a flag test.
- DBF loops loaded with n instead of n-1, or with counts above 65535.
- Shifting signed values with LSR, or dividing negative numbers with ASR where DIVS rounding
  is expected.
- Forcing `.s` branches that go out of range as code grows.
- Assuming X or C after `move.l #constant,Dn` when vasm's optimiser is on.

**See also:** [condition codes](condition-codes.md), [addressing modes](addressing-modes.md),
[MOVEQ](../instructions/data-movement.md#moveq), [ADDQ](../instructions/arithmetic.md#addq),
[DBcc](../instructions/program-control.md#dbcc), [MOVEM](../instructions/data-movement.md#movem)
