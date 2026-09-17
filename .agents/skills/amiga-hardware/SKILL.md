---
name: amiga-hardware
description: Program the Amiga OCS/ECS custom chips (Agnus, Denise, Paula) and 8520 CIAs directly - copper lists, bitplanes and scrolling, hardware sprites, blitter, Paula audio, interrupts and DMA, keyboard/joystick/mouse, floppy control, memory map, taking over and restoring the system. Use whenever writing, reviewing or debugging code that touches $DFFxxx or $BFxxxx registers, or reasoning about beam timing and chip RAM. Never guess a register bit - look it up here.
---

# Amiga custom chips and CIAs (OCS/ECS)

Register-exact reference for bare-metal Amiga programming, distilled from the Amiga
Hardware Reference Manual (3rd ed.) and checked against the NDK 3.9 `hardware/*.i`
includes. AGA machines (A1200/A4000/CD32) add registers and bits: see the amiga-aga
skill (the OCS/ECS rules here still apply there).

## Hard rules

- **Chip RAM or nothing.** Copper lists, bitplanes, sprite data (including the null
  sprite), audio samples, blitter sources/masks/destinations and disk buffers must be in
  chip RAM at even addresses: vasm `section name,data_c` / `bss_c`, or
  `AllocMem(size, MEMF_CHIP)`.
- **Registers are read-only or write-only.** Never read a write-only register, and never
  `clr`/`bset`/`bclr`/`bchg` one (the 68000 reads first). Keep shadow copies. Strobes
  (COPJMP1/2) fire on any access: `move.w d0,copjmp1(a6)`, never `clr.w`. Keep unused
  bits 0.
- **Set/clear registers** (DMACON, INTENA, INTREQ, ADKCON): bit 15 = 1 sets the written
  1-bits, 0 clears them. `$7FFF` clears everything. Restore a saved value with
  `$7FFF` then `saved!$8000` (mask DMACONR with `$07FF` first).
- **NDK names are lowercase and grouped** (`include "hardware/custom.i"`): `bplpt+n*4`,
  `sprpt+n*4`, `spr+n*8+sd_pos`, `color+n*2`, `aud0+ac_per`, `cop1lc`, `dmacon`. There are
  no `BPL1PTH`/`COLOR00` labels in the NDK; custom base `$DFF000` is usually in A6/A5.
- **Colours are 12-bit `$0RGB`** on OCS/ECS; BPLCON0 is written whole and should always
  include the COLOR bit (`$0200`).
- **Copper:** lists end with `$FFFF,$FFFE`; to pass PAL line 255 wait for `$FFDF,$FFFE`
  first; start a list by writing COP1LC then strobing COPJMP1 before enabling copper DMA;
  reload bitplane and sprite pointers every frame from the list. The copper can never write
  below `$040` and needs COPCON CDANG for `$040`-`$07E`.
- **Blitter:** load every register, write BLTSIZE (height<<6 | width in words) LAST, then
  wait for DMACONR BBUSY (bit 14) to clear, testing it twice (the first read after the
  start can be stale). With the OS alive use OwnBlitter/WaitBlit/DisownBlitter.
- **Interrupts:** clear the cause (e.g. read the CIA ICR once - it clears all flags), then
  clear the handled INTREQ bits (without bit 15) just before `RTE`. Vectors live at
  VBR+offset on 68010+ (level 3 = VBR+`$6C`): read VBR via `Supervisor` + `movec`.
- **Audio:** signed 8-bit samples, AUDxLEN in WORDS, period = 3546895 (PAL) or 3579545
  (NTSC) / sample rate, practical minimum period 124, volume 0-64. Channels loop until
  stopped. 0/3 share one stereo side and 1/2 the other - sources disagree on which is left.
- **Display window defaults** (PAL lores 320x256): DIWSTRT `$2C81`, DIWSTOP `$2CC1`,
  DDFSTRT `$38`, DDFSTOP `$D0`. An earlier DDFSTRT steals sprite DMA slots and kills the
  highest-numbered sprites.
- **CIAs are byte-wide:** CIA-A at `$BFE001` (odd addresses, level 2 PORTS), CIA-B at
  `$BFD000` (level 6 EXTER), registers `$100` apart. Fire buttons are CIA-A PRA bits 6/7
  (0 = pressed). In `cia.i`, `CIAB_`/`CIAF_` mean bit/flag, not CIA-B.
- **ECS-only registers** (`$1C0`-`$1E4`, BLTCON0L, BLTSIZV/BLTSIZH, DENISEID) don't exist
  on OCS: detect first (VPOSR Agnus ID, DENISEID, `GfxBase->ChipRevBits0`). OS-friendly
  code never writes BEAMCON0.
- **Never invent.** If a register, bit or timing value is not in `reference/`, say so.
  Statements marked `(unverified)` could not be checked against a local source - verify on
  the target (AmigaScope's `dma_profile.py`, `copper_disasm.py` and gdb memory reads make
  that measurable).

## How to look things up

- A register by name or address: `reference/index.md` (registers by address, with
  width, chipset, access, and a link to the entry), then `reference/registers/<file>.md`
  (audio, blitter, cia, copper, disk, dma-beam, ecs, input-serial, interrupts, playfield,
  sprites). Machine-readable table: `reference/data/registers.tsv`.
- How to do something: `reference/topics/` - `copper.md`, `playfields.md` (DIW/DDF
  formulas, scrolling, dual playfield, EHB/HAM, interlace), `sprites.md`, `blitter.md`
  (minterms, cookie-cut, fill, line mode), `audio.md`, `interrupts-and-dma.md` (levels,
  handlers, beam timing, DMA arbitration), `cia-and-io.md` (timers, keyboard, joystick,
  mouse, serial, floppy lines), `system-takeover.md` (bare-metal start/exit sequence),
  `memory-map.md`, `overview.md`, `ecs.md`, `zorro-autoconfig.md`.
- Where the sources disagree and how that was resolved: `reference/errata.md`. What the
  reference was distilled from: `reference/SOURCE.md`.
- AGA registers and bits: the amiga-aga skill. OS calls (LoadView, WaitTOF, OwnBlitter,
  AddIntServer, AllocMem...): the amiga-os skill. Instruction semantics and vasm
  directives: the m68k-asm skill. Observing the chips on a running target: the
  amigascope-workflow skill.
