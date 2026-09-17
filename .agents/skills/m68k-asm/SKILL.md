---
name: m68k-asm
description: Write, review or debug Motorola 680x0 assembler for the Amiga with vasm (Motorola/Devpac syntax) and vlink - every 68000 instruction plus 68010-68060 and FPU extensions, addressing modes, condition codes, vasm directives, hunk sections, startup code and library calls. Use whenever producing or reading .s/.asm/.i Amiga source, choosing an instruction or directive, interpreting flags, or fixing assemble/link errors. Never guess instruction semantics or directive syntax - look them up.
---

# 68k assembler (vasm) for the Amiga

Instruction reference distilled from the Motorola M68000 Family Programmer's Reference
Manual; directives and toolchain options from the vasm and vlink manuals. Examples were
assembled with the vasm builds bundled with the amiga-debug and amiga-assembly VS Code
extensions, and tricky semantics were checked in a 68k emulator.

## Hard rules

- **Flags:** MOVEA (`move ...,An`), MOVEM, LEA, PEA, EXG, and ADDQ/SUBQ/ADDA/SUBA on an
  address register set NO flags. MOVE/MOVEQ and arithmetic/logic into data set N and Z,
  so a following TST is redundant there - but required after library calls (test D0).
- **`cmp src,dst` tests dst - src.** Use BHI/BHS/BLO/BLS for addresses, sizes and
  counters; BGT/BGE/BLT/BLE only for signed values.
- **MOVEQ is -128..127, sign-extended to 32 bits.** `move.b`/`move.w` into Dn keep the
  upper bits.
- **DBcc** uses the low word only, exits when the counter reaches -1 (load n-1 for n
  iterations), treats cc as the EXIT condition and changes no flags.
- **DIVU/DIVS are 32/16:** quotient in the low word, remainder in the high word; overflow
  sets V and leaves Dn unchanged; divide by zero traps. MULU/MULS are 16x16 -> 32. Long
  forms are 68020+ (`divul`/`divsl` for 32/32 with remainder).
- **Bit ops:** on memory BTST/BSET/BCLR/BCHG use one byte (bit mod 8), on Dn the long (mod
  32); Z = 1 means the bit WAS 0. Memory shifts/rotates are word-sized, one bit.
- **CLR reads before writing on a 68000:** never `clr` custom/CIA registers
  (`move.w #0,reg`). `clr` can't address An: use `suba.l An,An`.
- **PC-relative operands are never writable;** `(d,An,Xi)`/`(d,PC,Xi)` displacements are
  8-bit; abs.W is sign-extended (`4.w` is fine, `$8000.w` is not `$8000`).
- **Privilege:** `move sr,<ea>` is privileged on 68010+ (use `move ccr,<ea>` or exec
  GetCC). Read VBR (MOVEC inside `Supervisor()`) before touching exception vectors.
- **Portability:** never store data in a pointer's top byte (68020+ decodes 32 bits); flush
  caches after writing or loading code (CacheClearU); assemble for all Amigas with
  `-m68000` and guard 68020+ code with `SysBase->AttnFlags`. MOVEP is gone on the 68060.
- **Always assemble with `-x`.** Without it vasm silently turns undefined symbols (typos,
  missing `lvo` includes) into externals that only fail at link time.
- **vasm's optimiser rewrites code by default** (`move.l #x,Dn` -> `moveq`, sometimes plus
  `add.w`, which changes X and C; `jsr` -> `bsr`; `bra` -> `bra.s`; absolute ->
  PC-relative). Use `-no-opt` or `opt o-` when size, timing or flags must be exact.
- **Native vasm never aligns data.** Put `even` after odd-length strings, `dc.b` tables and
  `incbin`; `ds.w 0` does not align.
- **Chip RAM is explicit:** copper lists, bitplanes, sprites, samples and blitter buffers go
  in `section name,data_c` / `bss_c`. In Bartman's ELF flow name the section `.MEMF_CHIP`
  or `.<x>.MEMF_CHIP`, never `.data.MEMF_CHIP`.
- **PC-relative references cannot cross sections in hunk output** (vlink Error 32): write
  the absolute form and let vasm optimise where possible.
- **`ELSEIF` is just `ELSE`** in the bundled vasm 1.8k/1.9 (its operand is ignored) and
  `ELIF` does not exist there: nest `if` inside `else`.
- **Library calls:** `move.l 4.w,a6` for exec; `jsr _LVOxxx(a6)` with
  `include "lvo/<lib>_lib.i"`; A6 = base, arguments in the documented registers, result in
  D0; D0/D1/A0/A1 are trashed. Don't name your own variables `GfxBase`/`ExecBase`: the NDK
  STRUCTURE macros define those as 0.
- **Startup/exit:** CLI start has A0 = argument string, D0 = length; return code in D0 with
  the entry SP. From Workbench (`pr_CLI` = 0) `WaitPort` + `GetMsg` the WBStartup message
  on `pr_MsgPort` first, and at exit `Forbid()` + `ReplyMsg()` without Permit.
- **Bartman ELF -> hunk:** amiga-debug's `elf2hunk` can turn same-section `R_68K_PC32` into
  `HUNK_RELOC32`, corrupting `bsr.l`/`bra.l` at load: run AmigaScope's
  `fix_hunk_relocs.py <elf> <hunk>` (diagnose with `analyze_pc32.py`).
- **Never invent.** If an instruction form or directive is not in `reference/`, say so.
  Toolchain behaviour that differs between vasm versions is called out per entry.

## How to look things up

- An instruction: `reference/index.md` (alphabetical), then
  `reference/instructions/<file>.md` - data-movement, arithmetic, logic, shift-rotate,
  bit, bcd, program-control, system (incl. exception vectors, MOVEC registers),
  cpu-68020-plus (bit fields, CAS, CHK2/CMP2, long MUL/DIV, 040/060 notes, FPU).
- A directive: `reference/index.md`, then `reference/directives/<file>.md` - sections,
  data, symbols, conditional, macros-repeat, structures (RS/SO/FO), include-and-output,
  listing-and-misc.
- Concepts: `reference/topics/addressing-modes.md`, `condition-codes.md`,
  `cpu-models.md`, `optimisation.md`, `vasm-vlink.md` (command-line options, output
  formats, hunk vs ELF), `amiga-program-structure.md` (hunks, startup, Workbench start),
  `library-calls.md`, `macros-and-structures.md` (NDK STRUCTURE macros).
- Errors in the printed/online sources and toolchain quirks: `reference/errata.md`;
  sources: `reference/SOURCE.md`.
- What a library function takes in which register: the amiga-os skill (and amiga-ahi for
  AHI). Custom chip registers: the amiga-hardware and amiga-aga skills. Debugging the
  assembled program on a live target: the amigascope-workflow skill.
