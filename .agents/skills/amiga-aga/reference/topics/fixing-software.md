# Fixing OCS/ECS software for AGA, and writing AGA-safe code

Why programs written for A500-class machines break on an A1200/A4000, and the rules that
keep new bare-metal code working on OCS, ECS and AGA. Distilled from RandyAGA's fix
report and Action's AGA-fixing guide; the chipset part comes first, the (more common)
CPU/system part after it.

## Chipset causes

AGA powers up ECS-compatible, but by the time a program starts, Workbench and
graphics.library have used the new registers. An OCS copper list never writes them, so it
inherits whatever the last screen left:

| Register left by the OS | Symptom in old code | Reset value |
|---|---|---|
| FMODE (bitplane/sprite fetch, scan doubling) | cut, sheared or doubled picture; garbage sprites | `fmode,$0000` |
| BPLCON3 (BANK, LOCT, PF2OF, SPRES, border bits) | wrong dual-playfield colours, palette writes land elsewhere, odd sprite size | `bplcon3,$0c00` |
| BPLCON4 (BPLAM, sprite bases) | swapped colours, sprites in wrong colours | `bplcon4,$0011` |
| BPLCON2 (KILLEHB) | EHB pictures in wrong colours | write it fully (bit 9 = 0) |
| DIWHIGH | window cut or shifted | write DIWSTRT/DIWSTOP (clears it) |
| BPL1MOD/BPL2MOD (scan-doubled screens) | skewed planes | write both |
| BEAMCON0 (DblPAL, productivity, multiscan) | wrong refresh / no sync on a TV | PAL `$0020`, NTSC `$0000` |

RandyAGA's minimum patch for an old copper list:

```asm
        dc.w    $01fc,$0000         ; FMODE: 16-bit fetch, no scan doubling
        dc.w    $0106,$0c00         ; BPLCON3: bank 0, LOCT 0, PF2OF 011, ECS sprites
        dc.w    $010c,$0011         ; BPLCON4: no colour mask, sprites on 16-31
        ; and make sure $108, $10A, $08E, $090 are written, or the Workbench values stay
```

Other chipset traps:

- **Scan-doubled Workbench**: an A1200 in DblPAL/productivity runs Workbench at ~27-31kHz,
  but a program's own copper list comes out at 15kHz. A monitor that cannot sync 15kHz
  shows nothing; only your own 31kHz timings fix that (BEAMCON0 variable beam, HTOTAL etc.,
  see the amiga-hardware skill).
- **Wrong AGA test**: `cmpi.b #$f8,$dff07c`, "bit 3 = AGA", or version checks. See
  [detection](detection.md). Demos that refused to run on an A4000 because of such tests
  were among RandyAGA's fixes.
- **Colour loaders capped at 32**: size loads from `ColorMap->Count` (RandyAGA).
- **Sprite pointers at address 0**: unused sprites showed whatever is at $0. Point them at
  zero data you own.
- **Colour burst bit**: Action notes some displays need BPLCON0 bit 9 (COLOR) set; old code
  writing `$4000` shows a corrupt display there. Use `$4200`.

## CPU and system causes (most "AGA" breakages)

None of these are chipset bugs; they show up because AGA machines have 68020+ CPUs,
Kickstart 3.x and 2MB chip RAM. Details for the CPU items are in the m68k-asm skill.

- **Blitter not waited for**: faster CPUs start a new blit before the last one ended.
  Test DMACONR bit 14 (BBUSY) twice before each blit, or call graphics `WaitBlit()`.
- **Upper address byte used as data**: 68020+/030/040/060 decode all 32 bits; address
  tables with flags in the top byte jump into nowhere. Mask with `$00FFFFFF` or remove.
- **Self-modifying code**: instruction caches (and on 68060 prefetch, even with caches
  off) run the old instruction. Flush with exec `CacheClearU()` (KS 2.0+) after patching.
- **Timing loops** (`dbf` delays for keyboard handshakes, loaders): far too short on
  faster CPUs. Use the beam position or a CIA timer; keyboard acknowledge needs >= 75us.
- **Interrupt acknowledged too early**: clear INTREQ just before `rte`, not first thing.
- **Stack frames**: 68010+ exception frames are 8 bytes and `rte` reads the format word; a
  hand-built 68000 `sr/pc` frame followed by `rte` crashes. Use `rtr`/`rts` or a TRAP.
- **VBR**: from 68010 the vector table may be moved into fast RAM (SetPatch does it);
  `$6c.w` is not the level 3 vector there. Read VBR in supervisor mode.
- **68040/060**: MMU/cache-disable code written for 68020/030 CACR bits crashes; 68060 has
  no `MOVEP`; strange `move #x,sr` values (Action: `$78ff`) crash non-68000 CPUs.
- **Chip RAM size**: a poke/compare at $200000 to find "fast RAM" mirrors to $0 on some
  2MB-chip machines. Compare against $0 as well, or ask exec.
- **Absolute addresses**: code loaded at $C00000 (A500 trapdoor RAM) fails where no RAM is
  mapped there (RandyAGA: A500+, A600 with 1MB chip). Use relocatable sections.
- **ROM peeks**: games reading Kickstart ROM contents or calling ROM addresses break with
  3.x ROMs; accelerator-detect probes (e.g. at $F00000) can hit real hardware.
- **Keyboard**: the A1200 keyboard controller is a 68HC05 (functional spec); RandyAGA
  reports a CIA caps-lock flashing trick resets the A1200.
- **`clr.w` on custom registers**: on the 68000 CLR reads before writing, strobing
  registers such as COPJMP1 twice. Use `move.w #0,...`.

## Writing AGA-safe bare-metal code

1. **Detect** Lisa properly; keep an OCS/ECS path unless you really need AGA
   ([detection](detection.md)).
2. **Own every display register** in your copper list header, AGA ones included -- only
   when AGA is present (or accept that the writes hit unused addresses on OCS; common
   practice, unverified on every revision):

```asm
        include "hardware/custom.i"
CopHeader:
        dc.w    fmode,$0000
        dc.w    bplcon3,$0c00       ; OR in BANK/LOCT only around palette loads
        dc.w    bplcon4,$0011
        dc.w    bplcon2,$0024
        dc.w    bplcon1,$0000
        dc.w    diwstrt,$2c81
        dc.w    diwstop,$2cc1
        dc.w    diwhigh,$2100       ; only after DIWSTRT/DIWSTOP
        dc.w    ddfstrt,$0038
        dc.w    ddfstop,$00d0
        dc.w    bpl1mod,$0000
        dc.w    bpl2mod,$0000
        dc.w    clxcon,$0000        ; also clears CLXCON2
```

3. **BEAMCON0** from the CPU at startup: `$0020` if `GfxBase->DisplayFlags` has `PAL`,
   else `$0000` ([BEAMCON0](../registers/aga.md#beamcon0)). The usual `LoadView(NULL)` +
   two `WaitTOF()` before taking over lets graphics drop the current screen's view first;
   whether it resets BEAMCON0 on every monitor driver is unverified, so write it yourself.
4. **Palette**: never assume 12 bits. Load high then low nibbles, restore BANK/LOCT, keep
   a 24-bit shadow copy ([palette](palette.md)).
5. **Fetch**: FMODE 0 for OCS-style displays; with 2x/4x align planes to 4/8 bytes and
   adjust DDFSTRT/modulo ([FMODE and fetch](fmode-and-fetch.md)).
6. **Unused bits = 0** in every AGA register (reserved for later chips).
7. **Restore** on exit: the OS copper list (`GfxBase->copinit` into COP1LC), the old view
   (`LoadView(GfxBase->ActiView)` saved at start), then `RethinkDisplay()` -- see the
   amiga-os skill. The OS rewrites its AGA registers from its own copper list.
8. **Test on the profiler** when something only goes wrong while running: sprite steals
   and blitter overruns are invisible in halted screenshots (see the amigascope-workflow
   skill).

## Common mistakes

- Adding only `fmode,0` and forgetting BPLCON3/BPLCON4.
- Writing BPLCON3 = 0 "to reset it": PF2OF becomes 000 and dual playfield colours move.
- Writing BPLCON4 = 0: sprites take colours 0-15.
- Blaming AGA for a blitter-wait, cache or VBR bug: test the program on an accelerated
  OCS machine first (Action's advice) -- if it fails there too, it is the CPU side.

**See also:** [detection](detection.md), [palette](palette.md), [FMODE and fetch](fmode-and-fetch.md), [overview](overview.md)
