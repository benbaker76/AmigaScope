# Sources (not redistributed)

The entries in `registers/` and the guides in `topics/` were distilled (rewritten, not
copied) from the documents below. No verbatim source documents are included for copyright
reasons; facts such as addresses, bit numbers and NDK symbol names are reproduced exactly.

- **Amiga Hardware Reference Manual, 3rd edition** (Commodore-Amiga, Addison-Wesley 1991) -
  chapters 1-8 and appendices A-K, used from an OCR'd e-book edition. OCR errors (O/0, S/5,
  scrambled tables) were resolved against the other sources; see `errata.md`.
- **NDK 3.9 hardware includes** (`hardware/custom.i`, `dmabits.i`, `intbits.i`,
  `adkbits.i`, `blit.i`, `cia.i` and their `.h` twins) - ground truth for register offsets
  and flag names. The same headers ship with the amiga-debug VS Code extension.
- **m68k-instructions-documentation** by prb28 (github.com/prb28/m68k-instructions-documentation),
  `hardware/` register pages scraped from the ADCD 2.1 Hardware Manual guide - clean bit
  tables; several copy-paste errors were corrected (see `errata.md`).
- **Solo's AGA register documentation** (coders' page PDF) and **RandyAGA** ("AGA doc V2.5",
  Randy of Comax) - practical register notes that also cover the OCS/ECS registers.
- **"Amiga System Memory Map"** (web page capture) - address ranges for `topics/memory-map.md`.
- **AmigaScope's own measurements** (`docs/TOOLKIT.md`, DMA profiler) - the sprite DMA slot
  positions versus DDFSTRT, labelled as measured.

Verification: the assembler examples in `topics/` were assembled with vasm (`vasmm68k_mot
-m68000`) against the NDK includes; register data in `data/registers.tsv` is cross-checked
against `hardware/custom.i` offsets and regenerated from the entries by
`tools/skills/build_indexes.py`.
