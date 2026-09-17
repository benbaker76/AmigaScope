# 680x0 CPU models on the Amiga

Amiga code written and tested on an A500 (68000) often crashes on an A1200, A4000 or an
accelerated machine. Almost every failure comes from a short list of CPU differences:
privileged SR access, the vector base register, exception stack frames, 32-bit addressing,
caches and prefetch, and instructions that later CPUs dropped or emulate. This page lists
them with the portable way to write each thing.

## Which machine has which CPU

| Machine | CPU | Clock | Address decoding |
|---|---|---|---|
| A1000, A500, A2000 | 68000 | 7.16 MHz NTSC / 7.09 MHz PAL | 24-bit |
| A500+, A600 | 68000 (unverified) | as A500 | 24-bit |
| A3000 | 68030 | 16 or 25 MHz | 32-bit |
| A1200 | 68EC020 | 14.32 MHz NTSC / 14.18 MHz PAL | 24-bit |
| A4000 | 68030 (A4000/030) or 68040 (A4000/040) | - | 32-bit (unverified for the 030 model) |
| CD32 | 68EC020 (unverified) | - | 24-bit |
| Accelerator boards | 68020, 68030, 68040, 68060 | - | 32-bit for non-EC CPUs |

Detect at run time from exec's `AttnFlags` (`exec/execbase.i`), not by timing or opcode
probing:

| Bit | Name | Meaning |
|---|---|---|
| 0 | `AFB_68010` | 68010 or better (also set for 68020+) |
| 1 | `AFB_68020` | 68020 or better (also set for 68030) |
| 2 | `AFB_68030` | 68030 or better (also set for 68040) |
| 3 | `AFB_68040` | 68040 |
| 4 | `AFB_68881` | 68881 FPU (also set for 68882) |
| 5 | `AFB_68882` | 68882 FPU |
| 6 | `AFB_FPU40` | working 68040 FPU |

The NDK 3.9 include defines no 68060 bit.

```asm
        include "exec/execbase.i"
        move.l  4.w,a6
        move.w  AttnFlags(a6),d7        ; keep a copy for later checks
        btst    #AFB_68020,d7
        beq.s   .plain68k               ; 68000/68010 code path
        lea     Blit020(pc),a0          ; 68020+ code path
        bra.s   .chosen
.plain68k
        lea     Blit000(pc),a0
.chosen rts
```

## Differences that matter

| Behaviour | 68000 | 68010 | 68EC020 / 68020 | 68030 | 68040 | 68060 |
|---|---|---|---|---|---|---|
| `move sr,<ea>` in user mode | allowed | privilege violation | violation | violation | violation | violation |
| `move ccr,<ea>` | no | yes | yes | yes | yes | yes |
| Vector base | fixed at 0 | VBR | VBR | VBR | VBR | VBR |
| Exception frame | 6 bytes (SR, PC) | 8+ bytes with format word | 8+ | 8+ | 8+ | 8+ |
| Address bits decoded | 24 | 24 | 24 (EC) / 32 | 32 | 32 | 32 |
| Instruction cache | - | - | yes | yes (+ data cache) | yes | yes |
| `clr` on memory | reads first | - | single write | - | - | - |
| `movem` base register in `-(An)` list | stores initial value | initial | decremented | decremented | decremented | decremented |
| 68020 instructions (BFxxx, long MUL/DIV, ...) | no | no | yes | yes | yes | partly emulated (unverified) |
| MOVEP | yes | yes | yes | yes | yes | no |
| FPU | - | - | 68881/68882 chip | 68881/68882 chip | on-chip (not LC/EC), partly emulated | on-chip (not LC/EC) (unverified) |

"-" = not documented in the sources used here.

## Status register access

`move sr,<ea>` is legal in user mode only on the 68000. Everywhere else it traps, so a
program that "just saves the flags" dies on a 68010+ machine.

- Read the flags portably with exec `GetCC()` (condition codes in D0, other registers
  preserved). In 68010+-only code `move ccr,<ea>` also works.
- In supervisor code any `move sr,<ea>` is fine on every CPU.
- Load only sane SR values (`$2000`, `$2700`, ...). Bits that are unused on a 68000 are live
  on later CPUs (`move #$78ff,sr` is a recorded crash).

```asm
        include "lvo/exec_lib.i"
        move.l  4.w,a6
        jsr     _LVOGetCC(a6)           ; d0.w = condition codes, any CPU, user mode
```

## Vector base register and exception frames

A 68010+ can move the exception vector table with VBR; do not assume the level-3 vector is
at `$6c`. Read VBR (68010+) in supervisor mode and add the offset.

```asm
        include "exec/execbase.i"
        include "lvo/exec_lib.i"
GetVBR  moveq   #0,d0                   ; 68000: table at 0
        move.l  4.w,a6
        btst    #AFB_68010,AttnFlags+1(a6)
        beq.s   .done
        lea     .super(pc),a5
        jsr     _LVOSupervisor(a6)      ; returns the d0 left by .super
.done   rts
.super  movec   vbr,d0                  ; 68010+ only (vasm -m68010 or higher)
        rte

InstallLevel3                           ; bare metal, interrupts disabled
        bsr.s   GetVBR
        movea.l d0,a0
        move.l  $6c(a0),OldLevel3       ; vector 27 = level-3 autovector
        move.l  #MyLevel3,$6c(a0)
        rts
MyLevel3
        rte
OldLevel3
        dc.l    0
```

Exception stack frames:

- 68000: SR (word) at 0(sp), return PC (long) at 2(sp) -- 6 bytes; bus/address error frames
  are longer.
- 68010-68060: SR, PC and a format/vector-offset word at 6(sp). TRAP #n and interrupts use
  the 8-byte format $0; other exceptions push CPU-specific formats.
- RTE on 68010+ reads the format word and pops the matching frame size. Pushing an SR and PC
  by hand and calling RTE therefore only works on a 68000; replace it with
  `move (sp)+,sr` + RTS (supervisor) or RTR (CCR only).
- A handler that inspects the stacked PC must use 2(sp) on every CPU and never assume the
  frame size.

## 24-bit and 32-bit addressing

The 68000, 68010 and 68EC020 (A1200) decode only the low 24 address bits: `jmp $ff004000`
runs code at `$004000`. The 68020, 68030, 68040 and 68060 use all 32 bits, so the same jump
crashes. Rules:

- Never store flags, counters or type bytes in the top 8 bits of a pointer or jump-table
  entry; mask them off before use if old data does (`andi.l #$00ffffff`).
- Treat addresses as unsigned: compare with BHI/BLO, never with BGT/BLT or signed math.
- Memory probing by writing and reading back is unreliable: on an A1200 without Fast RAM a
  write to `$200000` appears at `$000000` (the 2 MB Chip RAM is mirrored), so also check
  that address 0 did not change.

## Caches, prefetch and self-modifying code

- **Prefetch** (all CPUs): the CPU has already read the words after the current instruction.
  Code that patches the instruction immediately following it works on a 68000 and fails on a
  68060 even with caches off. Break the flow (BSR, TRAP, branch) between writing and
  executing.
- **Instruction cache** (68020, 68030, 68040, 68060): cached instructions are not updated
  when memory is written. After loading, relocating, decrunching, patching code or building
  jump tables of code, flush the caches. The 68030 adds a data cache (on an A4000 it is only
  enabled once SetPatch has run).
- Under the OS: exec `CacheClearU()` (V37+). `CacheControl()` changes cache settings and also
  clears the caches; its bits (`CACRF_EnableI`, `CACRF_ClearI`, `CACRF_EnableD`, ...) follow
  the 68030 CACR layout.
- Taken-over machine (supervisor mode): flush directly, choosing the method from AttnFlags.

```asm
        include "exec/execbase.i"
FlushCaches                             ; supervisor mode, d7 = AttnFlags read at startup
        btst    #AFB_68040,d7
        bne.s   .cpu040
        btst    #AFB_68020,d7
        beq.s   .done                   ; 68000/68010: nothing to flush
        movec   cacr,d0                 ; 68020/68030
        ori.w   #CACRF_ClearI,d0
        movec   d0,cacr
        bra.s   .done
.cpu040 cpusha  bc                      ; 68040: push data, invalidate both caches
.done   rts
```

- Timing loops (`dbf d0,*` delays) run many times faster with caches on; use CIA timers or
  raster position for delays such as the keyboard handshake.

## Missing and emulated instructions (68040, 68060)

- **68040**: every 68020 integer instruction except CALLM/RTM is in hardware. The on-chip FPU
  (not on 68LC040/68EC040) executes only a subset (FADD, FSUB, FMUL, FDIV, FCMP, FTST, FABS,
  FNEG, FSQRT, FMOVE, FMOVEM, FBcc, FScc, FDBcc, FTRAPcc, FSGLMUL, FSGLDIV, FNOP, FSAVE,
  FRESTORE); FSIN, FCOS, FETOX, FLOGN, FINT, FINTRZ, FMOVECR and the rest trap and are
  emulated by the support code (68040.library on the Amiga (unverified)). In `AttnFlags`,
  `AFB_FPU40` without `AFB_68881`/`AFB_68882` means the emulation is not loaded.
- **68060**: MOVEP no longer exists. CAS/CAS2, CHK2/CMP2, PACK/UNPK and the 64-bit
  MULx.L/DIVx.L forms are emulated by 68060 support code (68060.library) (unverified).
- Emulated instructions work but are very slow; keep them out of per-pixel or per-sample
  loops. See the availability table in [68020+ instructions](../instructions/cpu-68020-plus.md#availability-on-68030-68040-and-68060).
- The 68EC040 has access-control registers instead of the MMU's transparent-translation
  registers; the 68LC040 and 68EC040 have no FPU.

## Common mistakes

- `move sr,-(sp)` / `move sr,d0` in user-mode code (A500-only). Use `GetCC()`.
- Installing interrupt vectors at absolute `$64`-`$7c` without reading VBR.
- Faking an exception frame and returning with RTE.
- Data in the top byte of addresses; signed compares on addresses.
- Self-modifying or freshly loaded code executed without a cache flush; relying on prefetch.
- `clr` on write-triggered custom registers (read-then-write on a 68000): use `move.w #0,`.
- MOVEP in any code that may meet a 68060.
- 68020+ instructions or addressing modes without an `AttnFlags` check, or code meant for all
  machines assembled with `-m68020`.
- CPU delay loops for hardware timing.
- TAS / CAS on Chip RAM (the Amiga's DMA bus does not support the locked cycle).

**See also:** [MOVE from SR](../instructions/data-movement.md#move-from-sr),
[MOVEC](../instructions/system.md#movec), [RTE](../instructions/system.md#rte),
[CINV, CPUSH](../instructions/system.md#cinv-cpush),
[68020+ instructions](../instructions/cpu-68020-plus.md), [addressing modes](addressing-modes.md)
