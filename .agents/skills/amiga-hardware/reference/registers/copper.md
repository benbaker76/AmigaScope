# Custom chips: Copper registers

The Copper is the Agnus coprocessor that executes a list of MOVE / WAIT / SKIP
instructions in chip RAM, synchronised to the video beam. Its list address lives in
COP1LC / COP2LC; a strobe (COPJMP1/2) loads it into the Copper program counter. At the
start of every vertical blank the Copper restarts from COP1LC automatically.

## COPCON
`$DFF02E` · write · Agnus · OCS (ECS widens CDANG) · copper danger

Copper danger bit: lets the Copper write the protected low register range.

| Bit | Name | Meaning |
|---|---|---|
| 15-2 | -- | unused, write 0 |
| 1 | CDANG | 1 = Copper may write the protected range (below) |
| 0 | -- | unused, write 0 |

Registers the Copper may write:

| Chip | CDANG = 0 | CDANG = 1 |
|---|---|---|
| OCS Agnus | `$080` and up | `$040` and up (adds blitter registers) |
| ECS Agnus, AGA Alice | `$080` and up | every register |

NDK: `copcon` (custom.i); no flag constants; C `custom->copcon`.

### Example
```asm
        move.w  #2,copcon(a6)                   ; allow Copper MOVEs to blitter registers
```

### Gotchas
- Cleared at power-on and normally left 0 by the OS.
- A Copper list that starts blits must WAIT with the blitter-finished bit (BFD = 0) before
  the next blit; see COPINS.

**See also:** COPINS, [BLTCON0](blitter.md#bltcon0), [BLTSIZE](blitter.md#bltsize)

## COP1LCH, COP1LCL
`$DFF080` / `$DFF082` · write · Agnus · OCS (high word: 3 address bits OCS, 5 ECS) · pointer pair: one `move.l`

Address of the first Copper list; reloaded into the Copper PC at every vertical blank.

| Register | Bits | Meaning |
|---|---|---|
| COP1LCH | 15-3 (15-5 ECS) | unused, 0 |
| COP1LCH | 2-0 (4-0 ECS) | high address bits |
| COP1LCL | 15-1 | low address bits |
| COP1LCL | 0 | must be 0 (word-aligned address) |

NDK: `cop1lc` (custom.i: one longword label, no separate H/L labels); C `custom->cop1lc`.

### Example
```asm
        lea     $dff000,a6
        move.l  #MyCopper,cop1lc(a6)            ; both words in one write
        move.w  d0,copjmp1(a6)                  ; strobe: start it now
        move.w  #DMAF_SETCLR!DMAF_MASTER!DMAF_COPPER!DMAF_RASTER,dmacon(a6)

        section copper,data_c                   ; chip RAM
MyCopper:
        dc.w    color+0,$0000
        dc.w    $8001,$fffe                     ; WAIT line $80
        dc.w    color+0,$0f00
        dc.w    $ffff,$fffe                     ; end of list
```

### Gotchas
- The list must be in chip RAM (`data_c` / `MEMF_CHIP`) at an even address.
- While graphics.library owns the display it rewrites COP1LC during every vertical blank,
  replacing your list. Take the display over first, and on exit restore the system list
  with `move.l gb_copinit(a6),cop1lc(a5)` (GfxBase in a6, custom base in a5).
- Load COP1LC and strobe COPJMP1 before enabling COPEN.
- End every list with `$FFFF,$FFFE`: that WAIT never matches, so the Copper idles until
  the next vertical blank restart.

**See also:** COP2LCH, COP2LCL, COPJMP1, COPINS, [DMACON](dma-beam.md#dmacon), [Copper topic](../topics/copper.md)

## COP2LCH, COP2LCL
`$DFF084` / `$DFF086` · write · Agnus · OCS (high word: 3 address bits OCS, 5 ECS) · pointer pair: one `move.l`

Address of the second Copper list; used only when COPJMP2 is strobed.

Bit layout as COP1LCH/COP1LCL. Unlike COP1LC it is never used automatically.

NDK: `cop2lc` (custom.i, longword label); C `custom->cop2lc`.

### Example
```asm
; inside a Copper list: jump to List2 (written as two word MOVEs)
        dc.w    cop2lc,0                        ; high word, patched at run time
        dc.w    cop2lc+2,0                      ; low word, patched at run time
        dc.w    copjmp2,0                       ; strobe: continue at List2
```

### Gotchas
- A Copper list cannot MOVE a longword: write the high word at `cop2lc` and the low word
  at `cop2lc+2`.
- Typical uses: split a long list, or give interlaced long/short fields separate lists
  (switch COP1LC in a vertical blank handler checking VPOSR LOF).

**See also:** COP1LCH, COP1LCL, COPJMP2

## COPJMP1
`$DFF088` · strobe · Agnus · OCS

Strobe: restart the Copper at the address held in COP1LC.

NDK: `copjmp1` (custom.i); C `custom->copjmp1`.

### Example
```asm
        move.w  d0,copjmp1(a6)                  ; value is ignored
```

### Gotchas
- The access itself is the command; the HRM's own examples trigger it with a read
  (`move.w copjmp1(a6),d0`).
- Never use `clr.w`: on a 68000 it reads then writes (two strobes), on 68020+ it writes
  once, so the behaviour differs between CPUs.
- The Copper may strobe it itself (a MOVE to `copjmp1`) to loop back to COP1LC.

**See also:** COPJMP2, COP1LCH, COP1LCL

## COPJMP2
`$DFF08A` · strobe · Agnus · OCS

Strobe: restart the Copper at the address held in COP2LC.

NDK: `copjmp2` (custom.i); C `custom->copjmp2`.

### Gotchas
- Same strobe rules as COPJMP1 (`move.w`, never `clr.w`).
- COP2LC must hold a valid chip-RAM list before the strobe.

**See also:** COPJMP1, COP2LCH, COP2LCL

## COPINS
`$DFF08C` · DMA-only (Copper internal) · Agnus · OCS · never accessed by the CPU

Copper instruction fetch identifier; also documents the MOVE/WAIT/SKIP encoding.

| Bit | MOVE word 1 | MOVE word 2 | WAIT word 1 | WAIT word 2 | SKIP word 1 | SKIP word 2 |
|---|---|---|---|---|---|---|
| 15 | 0 | RD15 | VP7 | BFD | VP7 | BFD |
| 14-9 | 0 | RD14-RD9 | VP6-VP1 | VE6-VE1 | VP6-VP1 | VE6-VE1 |
| 8 | DA8 | RD8 | VP0 | VE0 | VP0 | VE0 |
| 7-1 | DA7-DA1 | RD7-RD1 | HP8-HP2 | HE8-HE2 | HP8-HP2 | HE8-HE2 |
| 0 | 0 | RD0 | 1 | 0 | 1 | 1 |

- **DA** register offset (e.g. `$180` = COLOR00); **RD** 16-bit data to store.
- **VP / HP** beam position to reach: VP = V7-V0, HP = H8-H2 (same units as VHPOSR).
- **VE / HE** compare-enable masks (1 = compare this bit); V7 is always compared.
- **BFD** blitter-finished disable: 1 = ignore the blitter; 0 = also wait for blit done.
- WAIT continues once the beam is at or past the position; SKIP skips the next MOVE if it is.

NDK: `copins` (custom.i); no instruction constants in hardware/*.i (user Copper lists
built through the OS use `CINIT` / `CMOVE` / `CWAIT` / `CEND` from graphics/gfxmacros.h).

### Example
```asm
        dc.w    color+0,$0f00                   ; MOVE: COLOR00 = red
        dc.w    $9601,$ff00                     ; WAIT line $96, ignore horizontal
        dc.w    $6407,$fffe                     ; WAIT line $64, horizontal $06
        dc.w    $ffdf,$fffe                     ; WAIT end of line $FF (PAL: go past 255)
        dc.w    $2c01,$fffe                     ; ... then line $12C
        dc.w    $01fe,$0000                     ; MOVE to $1FE (null register) = no-op
        dc.w    $ffff,$fffe                     ; end of list
```

### Gotchas
- The vertical compare is only 8 bits: line 256 compares as 0. To reach PAL lines 256+,
  first WAIT for `$FFDF,$FFFE` (end of line 255), then wait for the low 8 bits.
- Horizontal WAIT resolution is 2 colour clocks (4 lores pixels); the largest horizontal
  position is `$E2`.
- Keep BFD = 1 (second word `$FFFE`, `$FF00`, ...) unless you really wait for the blitter;
  with BFD = 0 the WAIT also needs the blitter-finished flag.
- MOVE word 1 must be even and at least `$080` (or `$040` / `$000` with COPCON CDANG).
- The Copper cannot write a longword: split pointers into two MOVEs (`bplpt+0`, `bplpt+2`).

**See also:** COPCON, COP1LCH, COP1LCL, [VHPOSR](dma-beam.md#vhposr), [INTREQ](interrupts.md#intreq), [Copper topic](../topics/copper.md)
