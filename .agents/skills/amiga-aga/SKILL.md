---
name: amiga-aga
description: AGA (AA chipset - Alice, Lisa, Paula) programming for the A1200, A4000 and CD32 - 8 bitplanes, HAM8, 24-bit palettes via LOCT/BANK, BPLCON3/BPLCON4, FMODE fetch modes, AGA sprites, detection, and making software AGA-safe. Use ONLY when the target is an AGA machine (or code must detect/handle AGA); OCS/ECS machines do not have these registers.
---

# AGA chipset

## GATE - read first

These registers and bits exist only on AGA machines (A1200, A4000, CD32). On OCS/ECS they
are absent or mean something else. If the target chipset is not known, ask, detect it
(see `reference/topics/detection.md`), or stay with the amiga-hardware skill. Everything
in the amiga-hardware skill still applies on AGA; this skill adds the differences.

## Hard rules

- **Detect properly.** Read `$DFF07C` (LISAID) as a WORD, mask `$00FF`, re-read about 30
  times (an OCS Denise floats), OR `$F0`, compare with `$F8`. The OS way: graphics V39+ and
  `GfxBase->ChipRevBits0 & (GFXF_AA_ALICE|GFXF_AA_LISA)`. Never `cmpi.b #$f8,$dff07c`, never
  infer AGA from the Kickstart or CPU version.
- **Own every AGA register in a bare-metal copper list:** `fmode` = `$0000`, `bplcon3` =
  `$0C00`, `bplcon4` = `$0011`, a full `bplcon2`, DIWSTRT/DIWSTOP followed by `diwhigh`,
  and `bpl1mod`/`bpl2mod`. The power-on value of BPLCON3/BPLCON4 is 0, which is NOT the
  OCS-compatible setting, and the OS leaves FMODE and scan-doubling bits set.
- **8 planes = BPLCON0 bit 4 (BPU3) with bits 14-12 = 0** (`$0210` lores). `8<<12` is the
  HIRES bit. 7 planes = `$7200`. HAM8 = `$0A10`, with the control bits in planes 1-2
  (not 5-6 as in HAM6).
- **24-bit colour takes two writes per register:** BPLCON3 LOCT=0 and the high nibbles
  first (they are copied to the low nibbles), then LOCT=1 and the low nibbles. BPLCON3
  BANK (bits 15-13) selects which 32 of the 256 colours COLOR00-31 address. Restore
  `bplcon3,$0C00` afterwards. COLORxx is write-only: keep a shadow palette.
- **BPLCON1 on AGA holds two 8-bit scroll values in 35 ns steps with split bit fields**
  (see the entry); scroll range = one fetch unit.
- **FMODE != 0 requires fetch-aligned planes** (4 or 8-byte boundaries, row size a multiple
  of the fetch unit) and changes the DDFSTRT and modulo rules. Lores 8 planes needs only
  1x; hires with more than 4 planes 2x; superhires 3-4 planes 2x, 5-8 planes 4x.
- **Sprite DMA steal:** a bitplane fetch that starts at or before a sprite's DMA slot
  disables that sprite. Measured with AmigaScope's DMA profiler: sprite n's slots at
  recorder hpos `$19+4n` / `$1B+4n`; fetch start `$34` lost sprite 7, `$24` lost 3-7. Use
  low sprite numbers, keep DDFSTRT late, and check with `dma_profile.py parse` (STEAL line).
- **Border bits** (BRDRBLNK, BRDNTRAN, ZDCLKEN, BRDSPRT, EXTBLKEN) only work with ECSENA
  (BPLCON0 bit 0) set.
- **4+4 dual playfield:** set PF2OF = %100 (offset 16: `bplcon3,$1000`); the OCS value
  %011 (offset 8, part of `$0C00`) makes playfield 2 overlap playfield 1's colours 8-15.
  Move sprite colour bases with BPLCON4 if they then collide with 16-31.
- **The NDK has almost no AGA bit symbols** (only offsets: `bplcon3`, `bplcon4`,
  `clxcon2`, `diwhigh`, `fmode`, `deniseid`), and its ECS-era BPLCON3 names disagree with
  the AA spec for bits 1 and 5. Define your own EQUs using the AA document names.
- **OS programs never poke:** BestModeIDA + ModeNotAvailable, OpenScreenTags with
  SA_Depth 8 and SA_Colors32, AllocBitMap(BMF_DISPLAYABLE), LoadRGB32 with left-justified
  32-bit guns, ObtainBestPenA on shared screens (full entries in the amiga-os skill).
- **Most "AGA incompatibilities" are really CPU problems** (blitter not waited for,
  caches and self-modifying code, data in the top address byte, VBR, stack frames): test
  on an accelerated OCS machine before blaming the chipset.
- **Never invent.** Some wide-fetch DDFSTRT values and RandyAGA claims are derived, not
  documented, and are marked `(unverified)`.

## How to look things up

- Register bit tables: `reference/registers/aga.md` (BPLCON0-4, CLXCON2, FMODE, COLORxx,
  BPL7/8 pointers and data, BPLxMOD, SPRxPOS/CTL, DIWSTRT/STOP, DIWHIGH, HBSTRT/STOP,
  BEAMCON0, LISAID, VPOSR Alice IDs). Index with addresses: `reference/index.md`.
- Techniques: `reference/topics/` - `overview.md` (what AA adds, A1200 summary),
  `detection.md`, `palette.md` (24-bit loads, copper palettes, fades, LoadRGB32 tables),
  `bitplanes-and-modes.md` (7/8 planes, HAM8, EHB/KILLEHB, superhires, dual playfield,
  full 8-plane example), `fmode-and-fetch.md`, `sprites.md`, `fixing-software.md`,
  `os-level.md`.
- Source conflicts and resolutions: `reference/errata.md`; sources: `reference/SOURCE.md`.
- OCS/ECS behaviour of the same registers: the amiga-hardware skill. Graphics library
  calls: the amiga-os skill. Measuring fetch/sprite DMA on a live target: the
  amigascope-workflow skill.
