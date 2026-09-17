# Sources (not redistributed)

The function entries and guides were distilled (rewritten, not copied) from the documents
below. No verbatim source documents are included for copyright reasons.

- **NDK 3.9 Autodocs** (`exec.doc`, `dos.doc`, `graphics.doc`, `intuition.doc`,
  `diskfont.doc`, `utility.doc`, `layers.doc`, `lowlevel.doc`, `timer.doc`, `input.doc`,
  `audio.doc`, `cia.doc`, `potgo.doc`) - primary text source for every function and device
  command (synopsis, inputs, results, notes, bugs, versions).
- **NDK 3.9 SFD files and clib prototypes** (`Include/sfd/*_lib.sfd`,
  `include_h/clib/*_protos.h`) - the generated fact blocks (prototype, LVO, register
  assignment) and `data/*.tsv`, produced by `tools/skills/amiga_skill_data.py gen` and
  checked by `... check`. They agree exactly with the `lvo/*.i` and `inline/*.h` headers
  bundled with the amiga-debug extension.
- **NDK 3.9 C and assembler includes** (`include_h`, `include_i`) - structure fields, asm
  offsets, flag, tag and error-code names and values; **NDK 3.9 release notes** and
  **Examples**.
- **NDK 3.2R4 autodocs and release notes** (AmigaOS 3.2 NDK) - a later cross-check for
  utility.library and layers.library only, e.g. the SMult64/UMult64 result register order.
- **V37 (2.04) Autodocs** as markdown from prb28's m68k-instructions-documentation
  (scraped from the ADCD 2.1 "Includes and Autodocs" guide) - cross-check of wording,
  versions and older prototypes.
- **Bartman's amiga-debug** (VS Code extension 1.8.2) - `sys-include` headers and project
  template, used to compile the C examples.

Verification: C examples were compiled with m68k-amiga-elf-gcc 15.1 (`-fsyntax-only -Wall`
or full builds) against the NDK/Bartman headers and assembler examples assembled with vasm;
structure offsets in `topics/structures.md` and `graphics/concepts.md` were confirmed both
with `offsetof` and by resolving the `.i` labels in vasm. Toolchain traps found this way
are documented in the entries and `errata.md`.
