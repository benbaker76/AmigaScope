# Amiga hardware overview (OCS/ECS)

The chips, clocks, memory types and register access rules behind every bare-metal program.

This page is the map. Each subsystem has its own guide: [copper](copper.md),
[playfields](playfields.md), [sprites](sprites.md), [audio](audio.md),
[blitter](blitter.md), [interrupts and DMA](interrupts-and-dma.md),
[CIAs and I/O](cia-and-io.md), [taking over the system](system-takeover.md),
[ECS](ecs.md), [memory map](memory-map.md), [Zorro/AUTOCONFIG](zorro-autoconfig.md).
AGA (A1200/A4000: Alice, Lisa, FMODE, 24-bit palette) is covered by the amiga-aga skill.

## The machine at a glance

| Part | Job | Where you talk to it |
|---|---|---|
| 680x0 CPU | 68000 in A500/A1000/A2000, 68030 in A3000; 68010-68060 via accelerators | -- |
| **Agnus** | DMA arbiter, copper, blitter, beam counters, chip RAM addressing | `$DFF000` block |
| **Denise** | bitplane serialiser, sprites, colour table, collision detection, mouse counters | `$DFF000` block |
| **Paula** | 4 audio DACs, floppy MFM/GCR controller, UART, pot/button port, interrupt controller | `$DFF000` block |
| **8520 CIA-A** | keyboard (serial register), fire buttons, power LED/audio filter, ROM overlay, disk status inputs, parallel data, 2 timers, TOD (vsync) | `$BFE001` (odd bytes), IRQ -> level 2 |
| **8520 CIA-B** | serial handshake lines, parallel status, floppy motor/select/step/side, 2 timers, TOD (hsync) | `$BFD000` (even bytes), IRQ -> level 6 |
| Gary | bus glue / address decoding on A500/A2000 (unverified: not described in the HRM) | not programmable |

Agnus revisions: 8361 (NTSC) / 8367 (PAL) original, 512K chip RAM; Fat Agnus 8370/8371,
512K chip plus 512K "slow" RAM at `$C00000`; ECS Fat Agnus 8372/8372A, 1 MB chip RAM (2 MB
on the A3000) and a single chip that can generate PAL or NTSC. ECS Denise is the 8373
(Hires Denise). See [ecs.md](ecs.md) for detection.

## Clocks and timing

| Quantity | NTSC | PAL |
|---|---|---|
| Master crystal | 28.63636 MHz | 28.37516 MHz |
| CPU clock (7M) | 7.15909 MHz | 7.09379 MHz |
| Colour clock (= audio/serial clock constant) | 3,579,545 Hz | 3,546,895 Hz |
| One colour clock (one DMA memory cycle) | 279.365 ns | 281.937 ns |
| CIA "E" clock (timer tick) | 715,909 Hz | 709,379 Hz |
| Lines per field (interlace alternates) | 262 / 263 | 312 / 313 |
| Nominal visible lines | 200 | 256 |
| Field rate | ~60 Hz | ~50 Hz |

One lores pixel = half a colour clock (140 ns); one hires pixel = 70 ns. The horizontal beam
counter (VHPOSR low byte) counts colour clocks, `$00`-`$E2`. Colour clocks per line: 227 on
PAL; NTSC alternates 227 and 228 (long line). Details in
[interrupts-and-dma.md](interrupts-and-dma.md#frame-and-beam-timing).

## Memory types

| Type | Address (classic) | Who can reach it | Allocate with |
|---|---|---|---|
| **Chip RAM** | `$000000` up to `$07FFFF`/`$0FFFFF`/`$1FFFFF` | CPU and all custom-chip DMA | `MEMF_CHIP`, vasm `section x,data_c` / `bss_c` / `code_c` |
| Slow ("pseudo-fast", trapdoor/ranger) RAM | `$C00000`-`$D7FFFF` | CPU only, but arbitrated by the same logic as chip RAM | whatever exec gives you (unverified: it is added as fast-type memory) |
| Fast RAM | Zorro II `$200000`-`$9FFFFF`, 32-bit boards/motherboard | CPU only, no contention | `MEMF_FAST` or just `MEMF_PUBLIC` |
| ROM | `$F80000` (512K, V36+) or `$FC0000` (256K, V1.x) | CPU | never call it directly |

**Anything a custom chip touches must be in chip RAM:** bitplanes, copper lists, sprite
data (including the null sprite), audio samples, every blitter source, mask and destination,
disk DMA buffers. A wrong allocation works on an unexpanded A500 (where all RAM is chip)
and fails silently on any machine with fast RAM. The custom chips read garbage (or write over
chip RAM) when handed a fast-RAM address.

In a vasm program use chip sections for such data:

```asm
        section gfx,data_c              ; copper lists, sprites, samples, bob images
coplist:
        dc.w    $ffff,$fffe
        section planes,bss_c            ; uninitialised chip RAM (bitplanes)
plane1: ds.b    40*256
        section code,code               ; code may live in fast RAM
```

For dynamic allocation: `AllocMem(size, MEMF_CHIP!MEMF_CLEAR)` (exec LVO -198); free with the
same size. Ask for `MEMF_CHIP` only when the chips need it.

## DMA in one paragraph

The custom chips fetch their own data straight from chip RAM ("direct memory access"). Agnus
hands out memory cycles per scan line: floppy, audio, sprite and bitplane fetches have fixed
slots and always win; the copper comes next; the blitter and the CPU get what is left. The CPU
is only blocked while it accesses chip RAM or chip-arbitrated memory (chip registers, slow
RAM) -- ROM and fast RAM are never slowed down. Every channel is switched by
[DMACON](../registers/dma-beam.md#dmacon). Full detail: [interrupts-and-dma.md](interrupts-and-dma.md).

## PAL vs NTSC

| | NTSC | PAL |
|---|---|---|
| Standard DIWSTRT / DIWSTOP | `$2C81` / `$F4C1` | `$2C81` / `$2CC1` |
| Standard lores screen | 320x200 | 320x256 |
| Audio period = clock / rate | 3579545 / rate | 3546895 / rate |
| Serial SERPER = clock / baud - 1 | 3579545 / baud - 1 | 3546895 / baud - 1 |
| Last beam line reachable by an 8-bit copper WAIT without the wrap trick | 255 of 262 | 255 of 312 |

Detect the video standard from the OS before you take over the machine:

```asm
        include "exec/execbase.i"
        include "graphics/gfxbase.i"
        move.l  4.w,a6
        cmp.b   #50,VBlankFrequency(a6)   ; 50 = PAL, 60 = NTSC
        beq.s   .pal
        ; or, with a6 = GfxBase:
        ; btst  #PALn,gb_DisplayFlags+1(a6)   ; PAL = 4, NTSC = 1
```

An ECS Agnus can be switched between the two with BEAMCON0 -- see [ecs.md](ecs.md).

## Register access rules

The custom chips live at `$DFF000`. Offsets come from `include "hardware/custom.i"`; load the
base once (`lea $dff000,a6`) and address registers as `offset(a6)`. The copper uses the bare
offsets.

**Name mapping.** The NDK include uses lowercase names and folds register families into one
base label. The HRM names map like this:

| HRM register | `hardware/custom.i` expression |
|---|---|
| BPLxPTH / BPLxPTL (x = 1-6) | `bplpt+(x-1)*4` / `bplpt+(x-1)*4+2` |
| SPRxPTH / SPRxPTL (x = 0-7) | `sprpt+x*4` / `sprpt+x*4+2` |
| SPRxPOS / CTL / DATA / DATB | `spr+x*8+sd_pos` / `+sd_ctl` / `+sd_dataa` / `+sd_dataB` |
| COLORxx (xx = 00-31) | `color+xx*2` |
| AUDxLCH / LEN / PER / VOL / DAT | `aud0+ac_ptr` / `ac_len` / `ac_per` / `ac_vol` / `ac_dat` (also `aud1`..`aud3`) |
| COP1LCH / COP1LCL | `cop1lc` / `cop1lc+2` (COP2 likewise) |
| BLTxPTH / BLTxPTL | `bltapt`, `bltbpt`, `bltcpt`, `bltdpt` (+2 for the low word) |
| POTGOR (formerly POTINP) | `potinp` |
| BLTCON0L | `bltcon0l` (= `$05B`, byte access) |

**Access rules (all binding):**

- Every custom register is **either read-only or write-only.** Never read a write-only
  register (the value is meaningless and a read of a strobe address can trigger it); never
  write a read-only one. Pairs: DMACON/DMACONR, INTENA/INTENAR, INTREQ/INTREQR, ADKCON/ADKCONR,
  VPOSW/VPOSR, VHPOSW/VHPOSR, POTGO/POTGOR, SERDAT/SERDATR.
- Keep a RAM shadow of write-only values you need later (colours, BPLCON0, ...).
- **Unused bits:** write 0, and mask them off when reading. Future chips use them.
- **Set/clear registers** (DMACON, INTENA, INTREQ, ADKCON): bit 15 = 1 sets the 1-bits you
  write, bit 15 = 0 clears them; 0-bits are untouched. `$7FFF` clears everything.
- **Strobes** (COPJMP1, COPJMP2, STRxxx): trigger by writing any value with `MOVE`.
- **Never `CLR` a hardware register.** On a 68000, `CLR` reads before it writes (double strobe);
  use `move.w d0,copjmp1(a6)` or `move.w #0,...`. Check that your assembler does not
  optimise `move #0` into `clr` (vasm: do not pass `-opt-clr`).
- **Pointers** (BPLxPT, SPRxPT, COPxLC, BLTxPT, AUDxLC, DSKPT): write the pair with one
  `move.l` to the high word; bit 0 must be 0; the address must be chip RAM.
- **CIA registers are bytes.** Use byte access at the documented addresses only
  (CIA-A `$BFEr01`, CIA-B `$BFDr00`).
- **Never use `TAS`** on the Amiga: its indivisible read-modify-write cycle collides with DMA.
- Do not assume power-on or OS-left values in any register; set up everything you depend on.

## General development guidelines (HRM chapter 1)

- The only fixed address in the system is `$4` (ExecBase). Never call ROM code by address;
  never depend on where libraries, structures or copper lists live.
- Direct hardware access is only allowed when you own the hardware: either you took over the
  machine ([system-takeover.md](system-takeover.md)) or the owning library/device/resource
  granted it (graphics.library for copper/playfield/sprites/blitter, audio.device,
  trackdisk.device/disk.resource, serial.device/misc.resource, cia.resource,
  potgo.resource, input.device/keyboard.device).
- Since Kickstart 2.0 the OS uses the CIAs differently from 1.3: with the OS alive, get CIA
  interrupts through `cia.resource` (AddICRVector/RemICRVector, AbleICR/SetICR), never by
  poking ICR.
- No software delay loops: CPU speed varies by an order of magnitude. Use `WaitTOF`, `Delay`,
  timer.device, the beam counter or a CIA timer.
- 68010+: interrupt/trap vectors are relative to the VBR (may be in fast RAM); exception stack
  frames differ (68000: 6 bytes, 68010+: at least 8 with a format word); `MOVE SR,<ea>` is
  privileged (use exec `GetCC`).
- 68020+: all 32 address bits are decoded -- never store data in a pointer's top byte, never
  use signed arithmetic on addresses. Instruction caches do not see memory writes: after
  loading or modifying code call `CacheClearU` (exec LVO -636).
- Library calls need the base in A6 and trash D0/D1/A0/A1; test results explicitly, do not
  rely on condition codes after a call.
- Test on several CPUs, memory configurations and chipset revisions.

## Common mistakes

- Bitplanes, samples, copper lists or blitter masks in a plain `data`/`bss` section: they end
  up in fast RAM on an expanded machine. Use `data_c`/`bss_c` or `MEMF_CHIP`.
- `clr.w copjmp1(a6)` or `clr.w bltamod(a6)`: double access on a 68000. Use `move.w`.
- Reading a write-only register (e.g. `move.w dmacon(a6),d0`) instead of its `...R` twin.
- Writing a new value to DMACON/INTENA without bit 15 and wondering why nothing turned on.
- Writing `$DFF100` with a byte instead of a word (all custom registers are words, except
  BLTCON0L).
- Assuming `$6C` is the level-3 vector: on 68010+ it is `VBR+$6C`.
- Hard-coding PAL values (DIWSTOP `$2CC1`, audio clock 3546895) on an NTSC machine.
