# Sources (not redistributed)

The instruction, directive and topic entries were distilled (rewritten, not copied) from the
documents below. No verbatim source documents are included for copyright reasons; syntax
lines, mnemonics and option names are reproduced exactly.

- **Motorola M68000 Family Programmer's Reference Manual** (M68000PM/AD) - integer
  instructions 68000-68040, FPU instructions; used from a markdown conversion that contains
  only the instruction sections.
- **m68k-instructions-documentation** by prb28 (github.com/prb28/m68k-instructions-documentation)
  - `instructions/` (68000/68010 pages), `directives/` (from the vasm Motorola-syntax
  manual) and a 68000 instruction reference with application notes; errors found are listed
  in `errata.md`.
- **vasm manual** (Volker Barthelmann and Frank Wille, 2025 edition), **vlink manual** and
  **vbcc manual** (sun.hasenbraten.de) - general options, the Motorola syntax module
  directives, hunk/ELF output modules, the M68k CPU module and optimisations, linker options.
- **NDK 3.9 assembler includes** (`exec/types.i`, `exec/libraries.i`, `lvo/*_lib.i`,
  `graphics/gfxbase.i`, `dos/dosextens.i`, `workbench/startup.i`, `exec/alerts.i`).
- **vscode-amiga-assembly** example workspace and extension settings (prb28) and
  **amiga-debug** (Bartman) templates - real vasm/vlink/gcc invocations.
- **AmigaScope** `fix_hunk_relocs.py` / `analyze_pc32.py` - the elf2hunk PC32 relocation bug.

Verification: examples were assembled with the two bundled toolchains - vasm 1.9 from
amiga-debug 1.8.2 and vasm 1.8k + vlink 0.16h from amiga-assembly 1.8.13 - and opcodes read
back with m68k-amiga-elf-objdump; selected instruction semantics (division overflow, shift
counts, MOVEM sign extension, bit-field offsets, 64-bit MULS.L/DIVUL) were executed in a
68k emulator. 68060-specific facts are not covered by the Motorola manual and are marked.
