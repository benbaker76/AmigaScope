# Instructions for AI assistants working on Amiga code

AmigaScope's Amiga knowledge lives in agent skills under `.agents/skills/`. If your runtime
does not auto-discover that directory, read the matching `SKILL.md` before writing,
reviewing or debugging Amiga code, then follow its "How to look things up" section into
`reference/`.

| Task | Read |
|---|---|
| Debugging, inspecting or profiling a running target with this repo | `.agents/skills/amigascope-workflow/SKILL.md` |
| Anything touching `$DFFxxx` custom-chip or `$BFxxxx` CIA registers (OCS/ECS) | `.agents/skills/amiga-hardware/SKILL.md` |
| AGA machines (A1200, A4000, CD32): BPLCON3/4, FMODE, 24-bit colour, 8 planes | `.agents/skills/amiga-aga/SKILL.md` (only when the target is AGA) |
| 68k assembler, instruction semantics, vasm directives and options | `.agents/skills/m68k-asm/SKILL.md` |
| OS calls (exec, dos, graphics, intuition, diskfont, utility, layers, lowlevel), timer/input/audio devices, cia/potgo resources | `.agents/skills/amiga-os/SKILL.md` |
| AHI audio | `.agents/skills/amiga-ahi/SKILL.md` (only when the program targets AHI) |

Rules that apply to all of them:

- Use the bundled reference instead of memory; never invent register bits, LVOs, flags,
  tags or directive syntax. If something is not in the reference, say so.
- Facts marked `(unverified)` could not be checked against a local source - verify them on
  the target (AmigaScope's gdb harness, copper disassembler and DMA profiler make that
  possible) before relying on them.
- Source disagreements and their resolutions are in each skill's `reference/errata.md`;
  never "fix" the reference back toward a source that the errata overrides.
