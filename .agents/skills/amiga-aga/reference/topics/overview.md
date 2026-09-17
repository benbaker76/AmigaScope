# AGA overview

What the AA ("AGA", Advanced Graphics Architecture) chip set adds over OCS/ECS, which
machines have it, and a short A1200 system summary. Register details are in
[registers/aga.md](../registers/aga.md).

## The chips

| Chip | Replaces | Role on AGA |
|---|---|---|
| Alice (8374) | ECS Fat Agnus 8372 | chip bus/DMA controller, copper, blitter, beam counters. Still a 16-bit register data bus, but drives 32-bit and double-CAS (page mode) chip RAM fetches |
| Lisa | Denise | video: 8 planes, 256-entry 24-bit colour table, sprites, collisions, 24-bit digital RGB out (to an 8-bit triple DAC) |
| Paula | unchanged | audio, floppy, serial, pots, interrupts (the pre-ECS Paula) |

Identify them with LISAID (`$DFF07C` low byte $F8) and VPOSR (Alice IDs $22/$23 PAL,
$32/$33 NTSC). See [detection](detection.md).

## What AA adds

- **8 bitplanes in every resolution** (bandwidth permitting): 256 colours in lores,
  hires and superhires. 7 planes = 128 colours.
- **24-bit palette**: 256 entries of 8 bits per gun plus a genlock T bit, loaded through
  the 32 old COLOR addresses using BANK and LOCT in BPLCON3. See [palette](palette.md).
- **HAM8**: 8 planes, 2 control + 6 data bits, 64 base colours, any resolution. HAM6 and
  EHB also work in hires and superhires. KILLEHB gives true 64-colour 6-plane screens.
- **Dual playfield 4+4** in all resolutions, with a selectable PF2 colour offset (PF2OF).
- **35ns positioning**: playfield scroll (8 bits per playfield in BPLCON1), display
  window (DIWHIGH H1/H0) and sprite horizontal position (SPRxCTL SH1/SH0).
- **Fetch bandwidth**: FMODE selects 16/32/64-bit bitplane and sprite fetches (32-bit chip
  bus, double-CAS page mode). Needed for deep hires/superhires/productivity displays. See
  [FMODE and fetch](fmode-and-fetch.md).
- **Sprites**: resolution selectable independent of the screen (SPRES), separate 16-colour
  banks for even and odd sprites (BPLCON4), sprites in the border (BRDSPRT), attached
  sprites in every mode, 32/64-bit sprite fetch. See [sprites](sprites.md).
- **Colour index mask**: BPLCON4 BPLAM XORs the 8-bit bitplane colour index (one copper
  MOVE swaps colour maps).
- **Collision** for planes 7 and 8 (CLXCON2).
- **Scan doubling** in hardware (FMODE BSCAN2/SSCAN2) so 15kHz screens can be shown on
  31kHz monitors (DblPAL/DblNTSC modes).
- **Genlock** (inherited from ECS Denise, extended): ZD from any bitplane (ZDBPEN/ZDBPSEL),
  per-colour transparency (ZDCTEN + T bit), 14MHz clock on ZD (ZDCLKEN), opaque border
  (BRDNTRAN), blanked border (BRDRBLNK).
- **28MHz clock input** for cleaner hires/superhires pixels.
- **Reset input** clears BPLCON3, BPLCON4, CLXCON2, DIWHIGH and FMODE.

The AA mode tables list the bandwidth each display needs: lores up to 8 planes and
dual playfield need 1x; hires 5-8 planes and superhires 3-4 planes need 2x; superhires
5-8 planes and 640x480 productivity above 4 planes need 4x.

## Machines

| Machine | CPU | Notes |
|---|---|---|
| A1200 | 68EC020 | 2MB chip RAM, Kickstart 3.0 in the AA spec, IDE + PCMCIA via Gayle |
| A4000 | 68030 or 68040 (A4000/030, A4000/040) | 32-bit motherboard fast RAM (RandyAGA: $07C00000-$07FFFFFF) |
| CD32 | 68EC020 (unverified) | AGA console; not covered by the source documents |

The A1200 ships Kickstart 3.0 (graphics.library V39); the A4000 and CD32 ship 3.x ROMs
too (unverified), so the OS AGA API ([OS level](os-level.md)) is there. The reverse is
not true: Kickstart 3.x also runs on OCS/ECS machines.

## A1200 system summary (Commodore functional spec, rev 1.6, 1992)

- **CPU**: 68EC020, 14.32MHz (NTSC) / 14.18MHz (PAL); 24-bit address space, 32-bit data
  path. Optional 68881/68882 FPU.
- **Chip RAM**: 2MB (organised 256K x 32 bits); early spec text mentions 1MB plus an A1201
  expansion. No fast RAM on the motherboard.
- **ROM**: 512K Kickstart 3.0 mask ROM (128K x 32); 1MB and 2MB ROMs supported.
- **Storage**: internal 3.5" 880K floppy; internal 2.5" IDE hard disk (A1200HD).
- **AAGayle**: A600 Gayle derivative: IDE and PCMCIA (PC Card 2.0, 68-pin) control.
- **Budgie**: data path between the 32-bit CPU bus and the 32-bit chip RAM bus, RAS/CAS
  decode for 2 banks of chip RAM, 14MHz CPU clock from 7MHz XNOR CDAC, 28MHz/genlock mux.
- **Video out**: 23-pin analogue RGB, composite, RF. A Bt101-class triple 8-bit DAC
  replaces the old video hybrid.
- **Keyboard MPU**: 68HC05C4A (replaces the 6500/1).
- **Expansion**: 150-pin CPU/trapdoor edge connector, A1201 memory/RTC header.

| Address range | Use |
|---|---|
| $000000-$1FFFFF | chip RAM (ROM overlay at reset) |
| $200000-$5FFFFF | expansion (Zorro II space) |
| $600000-$9FFFFF | PCMCIA common memory (if a card is present) |
| $A00000-$A1FFFF | PCMCIA attribute memory |
| $A20000-$A3FFFF | PCMCIA I/O |
| $BF0000-$BFFFFF | 8520 CIAs |
| $DA0000-$DA3FFF | IDE drive |
| $DA8000-$DAFFFF | PCMCIA and IDE configuration registers |
| $DC0000-$DCFFFF | real-time clock |
| $DF0000-$DFFFFF | custom chip registers |
| $E00000-$E7FFFF | system ROM, first half of a 1MB ROM |
| $E80000-$EFFFFF | autoconfig space |
| $F00000-$F7FFFF | flash ROM space |
| $F80000-$FFFFFF | system ROM |

## Common mistakes

- Treating "Kickstart 3.x" or "68020" as "AGA": test the chips ([detection](detection.md)).
- Assuming the OS left OCS values in the new registers: it did not (see
  [fixing software](fixing-software.md)).
- Assuming more bandwidth is free: deep hires/superhires displays need FMODE and aligned
  bitplanes, and a machine must support the fetch mode (check the display database).
