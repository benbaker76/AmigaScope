# 680x0 instructions: traps, exceptions and supervisor control

Notation (sizes, CCR symbols, mode names) as in [data movement](data-movement.md).
Instructions marked "supervisor only" raise a privilege violation (vector 8) in user mode.
Under AmigaOS user code reaches supervisor mode through exec `Supervisor()` (function in A5,
ends with RTE) or `SuperState()`; bare-metal code usually already runs in supervisor mode.

Exception vectors (vector address = VBR + 4 x number; VBR is always 0 on a 68000). Numbers
match exec's `ACPU_` alert codes in `exec/alerts.i`:

| No. | Offset | Cause |
|---|---|---|
| 2 | $08 | bus error / access fault |
| 3 | $0C | address error |
| 4 | $10 | illegal instruction, ILLEGAL, BKPT |
| 5 | $14 | integer divide by zero |
| 6 | $18 | CHK, CHK2 |
| 7 | $1C | TRAPV, TRAPcc, cpTRAPcc |
| 8 | $20 | privilege violation |
| 9 | $24 | trace |
| 10 | $28 | line A ($Axxx opcodes) |
| 11 | $2C | line F ($Fxxx opcodes: FPU/MMU instructions without the hardware) |
| 14 | $38 | format error (bad RTE frame) |
| 24 | $60 | spurious interrupt |
| 25-31 | $64-$7C | autovector interrupt levels 1-7 |
| 32-47 | $80-$BC | TRAP #0 - #15 |

Stack frame on entry: 68000 = SR (word) at 0(sp), PC (long) at 2(sp), 6 bytes (bus/address
error frames are larger). 68010+ = the same plus a format/vector-offset word at 6(sp); the
normal four-word frame (format $0, 8 bytes) is used for TRAP and interrupts, other exceptions
push other formats. Always leave with RTE and never build frames by hand.

## TRAP
`TRAP #<vector>` · 68000

Enter supervisor mode through exception vector 32 + n (n = 0..15).

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Stacked PC = the instruction after the TRAP.

### Example
```asm
        ; bare metal, 68000 only (VBR = 0): run Super in supervisor mode
        move.l  #Super,$80.w            ; vector 32 = TRAP #0
        trap    #0
        rts
Super   move    #$2700,sr               ; now allowed
        rte
```

### Gotchas
- On 68010+ the vector table may have been moved: install at VBR+$80, reading VBR with
  `movec vbr,d0` inside exec `Supervisor()` (see MOVEC).
- In an OS task exec routes traps to the task's `tc_TrapCode`; do not overwrite vectors in
  system-friendly programs.
- `trap #16` is out of range (vasm error).

**See also:** TRAPV, RTE, [TRAPcc](cpu-68020-plus.md#trapcc), MOVEC

## TRAPV
`TRAPV` · 68000

Take the TRAPV exception (vector 7) if V is set; otherwise do nothing.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

### Example
```asm
        add.w   d1,d0
        trapv                           ; signed overflow -> vector 7
```

**See also:** TRAP, [TRAPcc](cpu-68020-plus.md#trapcc), [Bcc](program-control.md#bcc)

## CHK
`CHK <ea>,Dn` · W (L on 68020+) · 68000

Trap (vector 6) if Dn is negative or greater than the signed upper bound at `<ea>`.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | * | U | U | U |

N = 1 if Dn < 0, N = 0 if Dn > bound, undefined otherwise.
Source modes: data -- Dn, (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L, (d,PC),
(d,PC,Xi), #imm.

### Example
```asm
        chk     #99,d0                  ; index must be 0..99 (word compare)
        move.b  (a0,d0.w),d1
```

### Gotchas
- Word form compares only Dn.w, signed. The trap handler, not your code, deals with the
  failure: rarely useful outside debugging.

**See also:** [CHK2](cpu-68020-plus.md#chk2-cmp2), TRAPV

## ILLEGAL
`ILLEGAL` · 68000

Force an illegal-instruction exception (vector 4) with the reserved opcode $4AFC.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

### Example
```asm
        tst.l   d0
        bne.s   .ok
        illegal                         ; "cannot happen": stop here in the debugger
.ok     rts
```

### Gotchas
- Under AmigaOS an unhandled illegal instruction ends in a software-failure requester / guru
  ($80000004). Other undefined opcodes may become real instructions on later CPUs; $4AFC
  never will.

**See also:** BKPT, TRAP

## RESET
`RESET` · 68000 · supervisor only

Pulse the RESET line for external devices; the CPU continues with the next instruction.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

### Example
```asm
        ; do not write your own reboot code: exec ColdReboot() (V36+) is the supported way
        reset
```

### Gotchas
- On the Amiga RESET makes all RAM and AutoConfig boards disappear and maps the ROM at
  address 0, while the CPU keeps executing at the next address, which is now likely gone.
  Only the exact ColdReboot sequence works on every model.

**See also:** STOP

## STOP
`STOP #<data>` · 68000 · supervisor only

Load SR with the immediate word and halt until an interrupt, trace or reset exception.

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

CCR is set from the immediate data.

### Example
```asm
        stop    #$2000                  ; supervisor, mask 0: sleep until any interrupt
```

### Gotchas
- Keep bit 13 (S) set in the data. Only an interrupt above the new mask wakes the CPU:
  after `stop #$2700` the normal Amiga interrupts (levels 1-6) cannot.
- Never in OS code: exec's task scheduler already idles the CPU.

**See also:** [MOVE to SR](data-movement.md#move-to-sr), RTE

## RTE
`RTE` · 68000 · supervisor only

Return from an exception: restore SR and PC from the stack (and discard the 68010+ frame).

| X | N | Z | V | C |
|---|---|---|---|---|
| * | * | * | * | * |

68000: pops SR (word) and PC (long). 68010+: also reads the format word at 6(sp) and removes
the whole frame of that format.

### Example
```asm
        include "hardware/custom.i"
        include "hardware/intbits.i"
Level3  movem.l d0-d7/a0-a6,-(sp)       ; bare-metal level-3 autovector ($6C) handler
        lea     $dff000,a6
        ; ... per-frame work ...
        move.w  #INTF_VERTB,intreq(a6)  ; acknowledge just before returning
        movem.l (sp)+,d0-d7/a0-a6
        rte
```

### Gotchas
- Pushing a PC and SR by hand and executing RTE works only on a 68000; on 68010+ the missing
  format word makes RTE misbehave. Use RTR or `move (sp)+,sr` + RTS instead.
- Exec interrupt servers (`AddIntServer()`) are called like subroutines by exec and return
  with RTS (VERTB servers with Z set); only code installed directly in a vector uses RTE.

**See also:** TRAP, [RTR](program-control.md#rtr), [cpu models](../topics/cpu-models.md)

## MOVEC
`MOVEC Rc,Rn` / `MOVEC Rn,Rc` · L · 68010+ · supervisor only

Copy a CPU control register to or from a general register (always 32 bits).

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

| Code | Name | Register | CPUs |
|---|---|---|---|
| $000 | SFC | source function code | 68010, 020, 030, 040 |
| $001 | DFC | destination function code | 68010, 020, 030, 040 |
| $800 | USP | user stack pointer | 68010, 020, 030, 040 |
| $801 | VBR | vector base register | 68010, 020, 030, 040 |
| $002 | CACR | cache control | 68020, 030, 040 |
| $802 | CAAR | cache address | 68020, 030 only |
| $803 | MSP | master stack pointer | 68020, 030, 040 |
| $804 | ISP | interrupt stack pointer | 68020, 030, 040 |
| $003 | TC | MMU translation control | 68040, 68LC040 |
| $004-$007 | ITT0, ITT1, DTT0, DTT1 | transparent translation | 68040, 68LC040 (IACR0/1, DACR0/1 on 68EC040) |
| $805 | MMUSR | MMU status | 68040, 68LC040 |
| $806 | URP | user root pointer | 68040, 68LC040 |
| $807 | SRP | supervisor root pointer | 68040, 68LC040 |
| $808 | PCR | processor configuration | 68060 (unverified) |
| $008 | BUSCR | bus control | 68060 (unverified) |

Any other code raises an illegal-instruction exception. The 68030 MMU registers (TC, TT0,
TT1, CRP, SRP, MMUSR) are reached with PMOVE, not MOVEC.

### Example
```asm
        include "exec/execbase.i"
        include "lvo/exec_lib.i"
        moveq   #0,d0                   ; VBR is 0 on a 68000
        move.l  4.w,a6
        btst    #AFB_68010,AttnFlags+1(a6)
        beq.s   .done
        lea     GetVBR(pc),a5
        jsr     _LVOSupervisor(a6)      ; runs GetVBR in supervisor mode
.done   rts
GetVBR  movec   vbr,d0                  ; 68010+
        rte
```

### Gotchas
- A 68000 has none of these registers: check `AttnFlags` (AFB_68010 is also set on
  68020+) before executing MOVEC, or it takes an illegal-instruction exception.
- CACR bit layouts differ between CPUs; prefer exec `CacheControl()`/`CacheClearU()`.
- vasm accepts MOVEC only with a 68010+ CPU selected (e.g. `-m68010`); that does not stop the
  rest of the program running on a 68000.

**See also:** [MOVE USP](data-movement.md#move-usp), MOVES, CINV, CPUSH, [cpu models](../topics/cpu-models.md)

## MOVES
`MOVES Rn,<ea>` / `MOVES <ea>,Rn` · B/W/L · 68010+ · supervisor only

Move data to or from memory in the address space selected by DFC (write) or SFC (read).

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Modes: memory alterable -- (An), (An)+, -(An), (d,An), (d,An,Xi), abs.W, abs.L. Into An the
value is sign-extended; into Dn only the low B/W/L part changes.

### Example
```asm
        moves.l (a0),d0                 ; 68010+: read through SFC
```

### Gotchas
- Meant for MMU/operating-system code that separates address spaces; ordinary Amiga code has
  no use for it.

**See also:** MOVEC

## BKPT
`BKPT #<data>` · 68010+ (and 68EC000)

Run a breakpoint-acknowledge cycle (number 0-7), then take the illegal-instruction trap.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

### Example
```asm
        bkpt    #0                      ; 68010+: ends in vector 4 unless hardware intervenes
```

### Gotchas
- A plain 68000 just takes the illegal-instruction exception. On 68020/030 external
  hardware may supply an instruction to execute instead; the 68040 always traps.
- For software breakpoints ILLEGAL is the portable choice.

**See also:** ILLEGAL

## RTD
`RTD #<displacement>` · 68010+

Return from a subroutine and add a signed 16-bit value to SP to drop stacked arguments.

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Operation: (SP) -> PC; SP + 4 + d -> SP.

### Example
```asm
        move.l  d1,-(sp)                ; 68010+: two stacked arguments
        move.l  d0,-(sp)
        bsr.s   Callee
        rts
Callee  move.l  4(sp),d2                ; first argument
        rtd     #8                      ; return and pop both arguments
```

### Gotchas
- Not on the 68000. Only callee-cleans conventions use it; AmigaOS and gcc code pass
  arguments in registers or clean the stack in the caller.

**See also:** [RTS](program-control.md#rts), [LINK](data-movement.md#link)

## CINV, CPUSH
`CINVL <caches>,(An)` / `CINVP <caches>,(An)` / `CINVA <caches>` · `CPUSHL`, `CPUSHP`,
`CPUSHA` alike · 68040 · supervisor only

Invalidate cache entries (CINV), or write pending data-cache lines out first (CPUSH).

| X | N | Z | V | C |
|---|---|---|---|---|
| - | - | - | - | - |

Scope: `L` = the line matching the address in An, `P` = its page, `A` = all.
`<caches>` in vasm: `ic` instruction, `dc` data, `bc` both.
Encoding `$F4 %ccpssrrr`: cc 01 = data, 10 = instruction, 11 = both; p 0 = CINV, 1 = CPUSH;
ss 01/10/11 = line/page/all; rrr = An. `cpusha ic` = $F4B8, `cpusha bc` = $F4F8.

### Example
```asm
        cpusha  bc                      ; 68040: flush both caches after patching code
```

### Gotchas
- Discarding dirty data-cache lines with CINV loses writes; use CPUSH when data may be pending.
- Only after checking `AFB_68040` in `AttnFlags`; OS code should call exec `CacheClearU()`.

**See also:** MOVEC, [cpu models](../topics/cpu-models.md)
