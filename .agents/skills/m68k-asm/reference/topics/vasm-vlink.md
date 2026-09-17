# vasm and vlink: assembling and linking Amiga code

Two build flows exist around AmigaScope. Pick the one the project already uses.

| Flow | Assemble | Link | Result |
|---|---|---|---|
| vscode-amiga-assembly (prb28) | `vasmm68k_mot -m68000 -Fhunk -linedebug` | `vlink -bamigahunk -Bstatic` | AmigaDOS hunk executable |
| Bartman amiga-debug (C + asm) | `vasmm68k_mot -m68000 -Felf ... -dwarf=3 -x` | `m68k-amiga-elf-gcc ... -Wl,--emit-relocs` then `elf2hunk` | ELF for gdb + hunk exe to run |
| single file, no linker | `vasmm68k_mot -m68000 -x -Fhunkexe` | none | hunk executable |

Bundled binaries: vasm 1.9 in `bartmanabyss.amiga-debug-1.8.2/bin/<os>/vasmm68k_mot`;
vasm 1.8k and vlink 0.16h in `prb28.amiga-assembly-1.8.13/resources/bin/<os>/`. The vasm
manual in the source set is newer (2025): features such as `elif`, `assert`, `local`,
`rseven`, `rept n,sym` and the `-opt-<devpac option>` switch are missing from both bundled
builds (tested). The 1.9 build also emitted zeros for float constants in tests.

## Hunk format vs ELF

AmigaDOS `LoadSeg` only loads **hunk** files (NDK `dos/doshunks.i`):

```text
HUNK_HEADER $3F3   no resident libs, hunk count, first/last, one size per hunk
                   (size in longwords; bit 30 = HUNKF_CHIP, bit 31 = HUNKF_FAST,
                    both set = one more longword of memory attributes follows)
HUNK_CODE $3E9 | HUNK_DATA $3EA | HUNK_BSS $3EB   contents (BSS: size only)
HUNK_RELOC32 $3EC    offsets to patch with the load address of hunk N
HUNK_SYMBOL $3F0     optional names, HUNK_DEBUG $3F1 optional (e.g. LINE info)
HUNK_END $3F2        after every hunk
Objects (-Fhunk) start with HUNK_UNIT $3E7 / HUNK_NAME $3E8 and carry HUNK_EXT.
```

Each section becomes one hunk, loaded anywhere in RAM of the requested type and
relocated. Relocation variants matter for old Kickstarts:

| Type | Written by | Loader |
|---|---|---|
| `HUNK_RELOC32` $3EC | vlink default, `vasm -Fhunkexe -kick1hunks` | all |
| `HUNK_DREL32` $3F7 used as short RELOC32 | `vasm -Fhunkexe` default, `vlink -Rshort` (tested) | V37 (2.04)+ per doshunks.i |
| `HUNK_RELRELOC32` $3FD | 32-bit PC-relative between hunks (`bsr.l`, `dr.l`) | V39+ per doshunks.i |

**ELF** is what gcc, ld and gdb use. vasm `-Felf` writes ELF relocatable objects with
`R_68K_*` relocations; AmigaOS cannot load ELF, so Bartman's flow converts the linked
ELF with `elf2hunk`. The ELF stays on the host for gdb and AmigaScope's symbol tools.

## vasm output formats

| Option | Use |
|---|---|
| `-Fhunk` | hunk object for vlink. Undefined symbols become imports. |
| `-Fhunkexe` | executable without a linker. Everything must resolve; no common symbols; only 32-bit absolute/relative relocations. |
| `-Felf` | ELF object for `m68k-amiga-elf-gcc`/`ld`. Section memory attributes are ignored. |
| `-Fbin` | raw bytes from the ORG address (bootblocks, code copied to fixed addresses). Two sections at the same origin: error 3001. |
| `-Ftest` | readable dump with every symbol value (vscode-amiga-assembly uses it to read EQUs). |

Hunk-module options: `-linedebug` (SAS/C LINE debug hunk), `-dbg-local` / `-dbg-globloc`
(local labels into the symbol hunk), `-kick1hunks` (Kickstart 1.x hunk types only),
`-databss` (`-Fhunkexe`: drop trailing zero words from the file; OS 2.0+ loader),
`-hunkpad=<code>` (code hunk padding, default NOP $4E71).

## Command-line options that matter

| Option | Effect |
|---|---|
| `-o <file>` | output name (blank required; default `a.out`) |
| `-I<path>` | include path; searched after work dir and main-source dir, before `incdir` |
| `-D<name>[=<value>]` | define a symbol (value 1 if omitted) |
| `-m68000` | CPU (default). Also `-m68010 -m68020 -m68030 -m68040 -m68060 -m68020up -m68080` |
| `-m68881` / `-m68882` / `-no-fpu` | allow FPU instructions / refuse them |
| `-x` | undefined symbols are errors. Without it they silently become imports (tested). |
| `-quiet` | no banner/statistics |
| `-L <file>` | listing file (`-Lall`, `-Lns`, `-Lni`, `-Lbpl=<n>` tune it) |
| `-nosym` | keep only symbols needed for linking; with `-linedebug` it also dropped the LINE hunk (tested) |
| `-linedebug` | source-line debug hunk for hunk debuggers (vscode-amiga-assembly default) |
| `-dwarf[=3]` | DWARF sections for gdb (Bartman: `-dwarf=3`) |
| `-no-opt` | disable every optimization, including `opt` lines in the source |
| `-showopt` / `-showcrit` | print every optimization / only those with side effects |
| `-devpac` / `-phxass` | compatibility modes (below) |
| `-align` | auto-align data and RS/SO/FO to even |
| `-esc` / `-spaces` | C escapes in strings / blanks allowed inside operands |
| `-nowarn=<n>` / `-w` / `-wfail` | silence one warning / all / make warnings fail the build |
| `-maxerrors=<n>` | error limit (default 5, 0 = none) |
| `-depend=make` / `-dependall=make`, `-depfile <f>` | Makefile dependencies |
| `-pic` | error on every relocation (position-independent check) |
| `-nocompdir`, `-ignore-mult-inc` | include-search tweaks |

Bartman's template uses: `-m68000 -Felf -opt-fconst -nowarn=62 -dwarf=3 -quiet -x -I.
-I$(SDKDIR)` (warning 62 = "imported symbol was not referenced", triggered by NDK
includes). The vscode example workspace: `-m68000 -Fhunk -linedebug`; the extension adds
`-o build/<name>.o <file>`.

## Optimization and cycle-exact code

Native vasm mode (no `-devpac`/`-phxass`) optimizes by default (manual, all tested):

- absolute label in the same section -> `(label,pc)`; `jmp`/`jsr` to a near label ->
  `bra`/`bsr`
- branches without size -> smallest fit (`bra.s`); `(0,An)` -> `(An)`; abs.L -> abs.W
- `move.l #x,Dn` -> `moveq`; `clr.l Dn` -> `moveq #0`; `add #1..8` -> `addq`; `lea (d,An),An`
  -> `addq`/`subq`
- float constants to the smallest precision

Explicit size extensions protect branches and displacements (`bra.w`, `(0.w,a0)` stay;
`-opt-allbra` overrides) but not instruction rewrites (`move.l #1,d0` still becomes
`moveq`). For code whose size or timing must be exact (self-modifying code, fixed jump
tables, cycle-counted loops):

```sh
vasmm68k_mot -m68000 -Fhunk -no-opt -x -o fx.o fx.s     # whole file
```
```asm
        opt     o-                      ; only this part
        ; ...
        opt     o+
```

Off by default because they change flags or bus access (enable only on purpose):
`-opt-clr` (CLR on 68000 reads before writing: never on hardware registers), `-opt-lsl`
(V flag), `-opt-mul`, `-opt-div` (flags), `-opt-movem`, `-opt-pea`, `-opt-st` (flags),
`-opt-nmoveq` (N flag), `-opt-speed`, `-opt-size`, `-opt-brajmp`, `-opt-jbra` (020+).
Selecting `-m68010` or higher enables the MOVE #0 -> CLR rewrite automatically (tested with
`-m68020`).

## Compatibility modes

- **`-devpac`** — only Devpac directives (rejected in tests: `align`, `blk`, `cseg`, `db`,
  `dw`, `dl`, `dr`, `dx`, `echo`, `elseif`, `global`, `if1`, `if2`, `ifp1`, `ifmacrod`,
  `inline`, `msource`, `nref`, `odd`, `printt`, `printv`, `public`, `pushsection`, `rem`,
  `weak`, `clrso`, `setso`, `clrfo`, `setfo`); data and RS/SO/FO auto-aligned; ALL
  optimizations off with warnings; no debug symbols (`opt d+` to enable); `cnop` pads with
  zeros; 35 macro arguments. Option order matters: `-devpac` after `-opt-...` switches can
  cancel them.
- **`-phxass`** — C escapes, case-insensitive macro names, blanks in operands, `-sd` and
  `-opt-allbra` on, output name derived from the input.
- New code: stay in native mode and always pass `-x`.

## vlink for hunk executables

```sh
vlink -bamigahunk -Bstatic -o uae/dh0/game build/main.o build/gfx.o build/sound.o
```

| Option | Effect |
|---|---|
| `-b amigahunk` | output format (the default target of the bundled build, `vlink -v`) |
| `-Bstatic` | no shared-library lookup (used by the extension) |
| `-o <file>` | output (default `a.out`) |
| `-L<dir>` / `-l<name>` | library search; amigahunk libraries are named `<name>.lib` |
| `-s` / `-S` | strip all symbols / only debug symbols |
| `-x` / `-X` | discard local symbols / those starting with L, l or `.` |
| `-M[<file>]` | section/symbol map |
| `-k` | keep input section order (default: all code, then data, then bss) |
| `-sc` / `-sd` / `-mtype` / `-mall` | merge all code / all data+bss / by type / everything |
| `-mrel` | merge sections that PC-relative references connect |
| `-hunkattr <sec>=<value>` | override memory flags: `-hunkattr gfx=2` puts section gfx in chip RAM (tested) |
| `-kick1` | Kickstart 1.x safe: no short relocs, no data-bss, no 32-bit PC-relative relocs |
| `-Rshort` | short relocation hunks (needs 2.04) |
| `-Z` | keep trailing zero bytes in the file instead of making them data-bss |
| `-gc-all` / `-gc-empty` | drop unreferenced / empty sections |
| `-wfail` | warnings fail the link |

Rules (manual, tested):
- Sections with the same name and type are merged across objects; different names stay
  separate hunks.
- A 16-bit PC-relative reference (`lea x(pc)`, `bsr.w`) between different output sections
  is "Error 32 ... Unsupported relocation type R_PC" (32-bit ones become
  `HUNK_RELRELOC32`, V39+). Use absolute references, give the sections the same name, or
  `-mrel`.
- AmigaDOS starts the program at the first byte of the first hunk (standard behaviour, not
  spelled out in the local sources); vlink puts code sections first and keeps object order,
  so pass the startup object first. vscode-amiga-assembly does this with its
  `entrypoint` setting.
- vbcc builds link the same way: its `vc` config calls
  `vlink -x -Bstatic -Cvbcc -nostdlib ... startup.o <objects> -lvc`, so vasm `-Fhunk`
  objects can join a vbcc link.

## Bartman's ELF flow and the R_68K_PC32 repair

```make
VASMFLAGS = -m68000 -Felf -opt-fconst -nowarn=62 -dwarf=3 -quiet -x -I. -I$(SDKDIR)
LDFLAGS   = -Wl,--emit-relocs,--gc-sections,-Ttext=0,-Map=$(OUT).map
# vasmm68k_mot $(VASMFLAGS) -dependall=make -depfile obj/x.d -o obj/x.o x.asm
# m68k-amiga-elf-gcc $(CCFLAGS) $(LDFLAGS) $(objects) -o out/a.elf
# elf2hunk out/a.elf out/a.exe
```

- Name code sections `.text.<something>` (Bartman's `depacker_doynax_vasm.asm` uses
  `section .text.depacker_doynax_vasm,code`): the linker script gathers `.text.*` into
  `.text`, `--gc-sections` can drop them individually, and AmigaScope's
  `cpu_flamegraph.py`/`size_profile.py` resolve assembler labels by the `.text` section.
- Chip data: name the ELF section `.MEMF_CHIP` or `.<name>.MEMF_CHIP` (`.MEMF_FAST` for
  fast) and elf2hunk makes it a chip hunk (tested). `.data.MEMF_CHIP` does not work: the
  default linker script merges `.data.*` into `.data` first (tested).
- `--emit-relocs` keeps the relocations in the linked ELF so elf2hunk can write
  `HUNK_RELOC32`.
- gcc C symbols have no underscore prefix (`foo`), asm names must match exactly.

**Why AmigaScope repairs PC32 relocations.** `R_68K_PC32` is a 32-bit PC-relative
relocation (`bsr.l`/`bra.l` on 020+, `dr.l`, some gcc output). Inside one section the
linker has already resolved it; nothing must change at load time. The elf2hunk bundled
with amiga-debug 1.8.1 still writes these offsets into `HUNK_RELOC32`, so `LoadSeg` adds
the hunk's load address to a PC-relative displacement and the branch jumps into garbage.

- `python3 fix_hunk_relocs.py <elf> <hunk> [out]` — collects every `R_68K_PC32` offset
  from the ELF's RELA sections that target allocatable sections, then rewrites the hunk
  file with those offsets removed from same-hunk `HUNK_RELOC32` entries (in place if no
  output name). Prints how many it removed.
- `python3 analyze_pc32.py <elf>` — lists sections, counts `R_68K_PC32` relocations and
  splits them into same-section and cross-section ones. Cross-section PC32 is a real
  problem: elf2hunk reports "R_68K_PC32 relocation referring to another section
  unsupported".

Run the fix after every `elf2hunk` when the ELF contains PC32 relocations, so the ELF you
debug and the hunk that runs agree.

## Common mistakes

- **No `-x`**: a misspelt label or `_LVO` name assembles fine as an import and fails at
  link time (or as error 3009 with `-Fhunkexe`).
- **`lea label(pc)` across sections**: fine in ELF, fails in hunk output.
- **Assuming data alignment**: native vasm never pads `dc.w` after odd bytes; add `even`.
- **Optimizer surprises in timed code**: use `-no-opt` or `opt o-`.
- **`-m68020` for an A500 build**: 020-only instructions are no longer rejected and the
  optimizer may emit 32-bit branches/displacements and CLR on hardware registers.
- **Kickstart 1.3 targets**: use `-kick1hunks` with `-Fhunkexe` and `-kick1` with vlink,
  avoid `dx`/`-databss`, keep BSS hunks under 256K (vasm error 3019).
- **Float constants with the bundled vasm 1.9**: verify, or write IEEE hex.
- **Relative include paths from a nested include**: they are resolved from the work or
  main-source directory, not from the including file.

**See also:** [SECTION](../directives/sections.md#section), [OPT](../directives/listing-and-misc.md#opt),
[INCLUDE](../directives/include-and-output.md#include),
[program structure](amiga-program-structure.md), [library calls](library-calls.md)
