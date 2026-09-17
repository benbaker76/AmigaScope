# Sources (not redistributed)

The register entries and topic guides were distilled (rewritten, not copied) from the
documents below. No verbatim source documents are included for copyright reasons.

- **"Specification for the Advanced Amiga (AA) Chip Set"** (Commodore), as re-typed in the
  1993 AmigaGuide `AGA.guide` (Fireflash/Sponge of C18, TFA) - treated as the AA
  specification.
- **Solo's AGA register documentation** (coders' page PDF) - the same register text with
  per-register tables.
- **RandyAGA - "Programming AGA hardware"** (Randy of Comax, V2.5) - detection routine,
  palette and copper practice; several bit orders in it are reversed (see `errata.md`).
- **A1200/A1200HD Advanced Amiga 1200 System Functional Specification**, Rev 1.6
  (Commodore-Amiga, 1992) - system summary, memory map, Gayle/Budgie/IDE/PCMCIA.
- **"Action's guide to AGA fixing software!"** (web page capture) - causes of AGA
  incompatibility.
- **m68k-instructions-documentation** by prb28 - AGA register pages.
- **NDK 3.9 includes** (`hardware/custom.i`, `graphics/gfxbase.h`, `modeid.h`,
  `displayinfo.h`, `view.h`) - offsets, ChipRevBits0 flags and mode IDs.
- **AmigaScope's DMA profiler measurements** (`docs/TOOLKIT.md`) - sprite DMA slot positions
  and fetch-start steal, labelled as measured.

A "Mysterious Ways - How to Code the Amiga - AGA Chipset" capture was also present but
contained only a database error page; nothing was used from it.
