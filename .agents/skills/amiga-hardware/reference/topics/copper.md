# Copper: display coprocessor

How to encode, build, start and time copper lists (HRM chapter 2).

The copper is a tiny processor inside Agnus. It runs a list of 16-bit instruction pairs from
chip RAM, waits for beam positions and writes values into custom registers. Everything that
must happen at a screen position (palette splits, bitplane/sprite pointer reloads, mode
changes, raster interrupts) belongs in a copper list.

Registers: [COP1LCH, COP1LCL](../registers/copper.md#cop1lch-cop1lcl),
[COP2LCH, COP2LCL](../registers/copper.md#cop2lch-cop2lcl),
[COPJMP1](../registers/copper.md#copjmp1), [COPJMP2](../registers/copper.md#copjmp2),
[COPCON](../registers/copper.md#copcon), [COPINS](../registers/copper.md#copins),
[DMACON](../registers/dma-beam.md#dmacon).

## How the copper runs

- Its program counter is loaded from COP1LC when COPJMP1 is strobed, from COP2LC when COPJMP2
  is strobed, and **automatically from COP1LC at the start of every vertical blank**. A list
  therefore replays every field without CPU help.
- It fetches only from **chip RAM** and only runs while `DMAF_COPPER` and `DMAF_MASTER` are
  set in DMACON.
- It only uses odd memory cycles, so it never collides with the fixed-slot DMA channels; it
  has priority over the blitter and the CPU. While WAITing it is completely off the bus.
- There is no stop instruction: a list ends with a WAIT that can never be satisfied.

## Instruction encoding

Every instruction is two words (IR1, IR2). IR1 bit 0 separates MOVE from WAIT/SKIP; IR2
bit 0 separates WAIT from SKIP.

**MOVE** -- write a value into a register:

| Word | Bits | Meaning |
|---|---|---|
| IR1 | 15-9 | 0 |
| IR1 | 8-1 | register address / 2 (DA8-DA1) |
| IR1 | 0 | 0 |
| IR2 | 15-0 | data to write |

Because bit 0 is 0 and the address is even, IR1 is simply the register offset:
`dc.w color+$00,$0f00` (COLOR00 = `$180`).

**WAIT** -- wait until the beam counter is >= the position (on the enabled bits):

| Word | Bits | Meaning |
|---|---|---|
| IR1 | 15-8 | VP: vertical position V7-V0 |
| IR1 | 7-1 | HP: horizontal position H8-H2 (colour clocks, bit 0 ignored) |
| IR1 | 0 | 1 |
| IR2 | 15 | BFD: 1 = normal; 0 = also wait for the blitter to finish |
| IR2 | 14-8 | VE: compare enables for V6-V0 (V7 always compared) |
| IR2 | 7-1 | HE: compare enables for H8-H2 |
| IR2 | 0 | 0 (WAIT) |

**SKIP** -- identical to WAIT except IR2 bit 0 = 1: if the beam is already >= the position,
skip the next instruction.

So `WAIT(vp,hp)` = `dc.w (vp<<8)!(hp&$FE)!1,$FFFE`. Examples:

```asm
        dc.w    $9601,$fffe     ; wait for line 150 ($96), hpos 0
        dc.w    $9601,$ff00     ; wait for line 150, ignore horizontal
        dc.w    $6401,$ff01     ; SKIP next instruction if line >= 100
        dc.w    $ffff,$fffe     ; end of list: VP=$FF, HP=$FE can never happen
```

Handy vasm macros (names chosen to avoid graphics.library's CWAIT/CMOVE/CEND):

```asm
COPMOVE macro                   ; COPMOVE register,value
        dc.w    \1,\2
        endm
COPWAIT macro                   ; COPWAIT line,hpos  (line uses its low 8 bits)
        dc.w    ((((\1)&$ff)<<8)!((\2)&$fe)!1),$fffe
        endm
COPEND  macro
        dc.w    $ffff,$fffe
        endm
```

## Beam positions the copper can see

- **Horizontal:** `$00`-`$E2` colour clocks; bit 0 is not compared, so there are 113 usable
  positions, each 4 lores / 8 hires pixels wide. Horizontal blanking is about `$0F`-`$35`.
  A standard `DIWSTRT` of `$81` (lores pixels) is about HP `$40`.
- **Vertical:** VP holds only 8 bits, but a PAL field has 312 lines (NTSC 262). Line 256 looks
  like line 0 to the comparator. Because WAIT tests ">=", `dc.w $2c01,$fffe` placed after line
  255 would be true immediately. The fix: first wait for the end of line 255, then use the low
  byte of the real line:

```asm
        dc.w    $ffdf,$fffe     ; wait for line 255, hpos $DE (end of that line)
        dc.w    $2c01,$fffe     ; now means line $12C = 300
        dc.w    color+$00,$000f
```

- The copper cannot wait past the end of a field: VP=`$FF` HP=`$FE` never occurs, so the list
  stalls there until the next vertical-blank restart. That is exactly the end-of-list idiom.
- Do not try "VP=$20, HP=$FE" as an end marker: as soon as the line exceeds `$20` the ">="
  test succeeds.
- Lists must be sorted in beam order. An out-of-order WAIT is already satisfied and falls
  straight through (the following MOVEs execute immediately).

## Register write restrictions (copper danger)

- Offsets `$080` and up: always writable by the copper.
- Offsets `$040`-`$07E` (the blitter, among others): only while COPCON bit 1 (CDANG) is 1.
- Offsets below `$040`: never write them from the copper. COPCON (`$02E`) itself is in this
  range, so the CPU must set CDANG.
- CDANG is cleared at reset. The HRM describes ECS as relaxing these limits; lists that stay
  inside the rules above work on every chipset (see the errata).

## Starting a list

Point COP1LC at the list, strobe COPJMP1 so the copper starts there right now, then enable
copper DMA. Do it in this order (HRM: initialise a location register and strobe it before
copper DMA is turned on).

```asm
        include "hardware/custom.i"
        include "hardware/dmabits.i"

        lea     $dff000,a6
        move.l  #coplist,cop1lc(a6)             ; long write fills COP1LCH + COP1LCL
        move.w  d0,copjmp1(a6)                  ; strobe: any value, MOVE not CLR
        move.w  #DMAF_SETCLR!DMAF_MASTER!DMAF_COPPER!DMAF_RASTER,dmacon(a6)
```

To stop: install a list that only contains `$FFFF,$FFFE`, or clear `DMAF_COPPER`. With the OS
running, graphics.library rewrites COP1LC every vertical blank -- take the display over first
([system-takeover.md](system-takeover.md)).

## Building a list in chip RAM

Static lists go in a chip data section; values known only at run time (bitplane addresses)
are patched into it.

```asm
        section code,code
        ; a6 = $dff000, copper DMA off or list not yet installed
Install:
        lea     plane1,a0               ; chip RAM (bss_c below)
        move.l  a0,d0
        lea     cop_bpl1,a1             ; the two value words of the pointer MOVEs
        swap    d0
        move.w  d0,2(a1)                ; BPL1PTH value
        swap    d0
        move.w  d0,6(a1)                ; BPL1PTL value
        move.l  #coplist,cop1lc(a6)
        move.w  d0,copjmp1(a6)
        move.w  #DMAF_SETCLR!DMAF_MASTER!DMAF_COPPER!DMAF_RASTER,dmacon(a6)
        rts

        section copper,data_c
coplist:
        dc.w    diwstrt,$2c81,diwstop,$2cc1     ; PAL 320x256
        dc.w    ddfstrt,$0038,ddfstop,$00d0
        dc.w    bplcon0,$1200                   ; 1 lores plane (+COLOR bit)
        dc.w    bplcon1,$0000,bplcon2,$0024
        dc.w    bpl1mod,$0000
cop_bpl1:
        dc.w    bplpt+$00,$0000                 ; patched
        dc.w    bplpt+$02,$0000                 ; patched
        dc.w    color+$00,$0000,color+$02,$0fff
        dc.w    $9601,$fffe                     ; line 150
        dc.w    color+$00,$0f00                 ; background turns red
        dc.w    $ffdf,$fffe                     ; cross line 255
        dc.w    $2c01,$fffe                     ; line 300
        dc.w    color+$00,$0000
        dc.w    $ffff,$fffe

        section planes,bss_c
plane1: ds.b    40*256
```

Generating a list at run time (e.g. one colour per line) is just writing words into a chip
RAM buffer. Remember the line-255 crossing:

```asm
; a0 -> chip RAM buffer (>= 256*8+8 bytes). Blue ramp on COLOR00, lines $2C-$12B.
BuildGradient:
        move.w  #$2c,d0                 ; current line
        move.w  #256-1,d7
.line   cmp.w   #$100,d0
        bne.s   .same
        move.w  #$ffdf,(a0)+            ; entering line 256+: wrap wait
        move.w  #$fffe,(a0)+
.same   move.w  d0,d1
        lsl.w   #8,d1                   ; VP = low 8 bits of the line
        addq.w  #1,d1                   ; HP = 0, WAIT marker bit
        move.w  d1,(a0)+
        move.w  #$fffe,(a0)+
        move.w  #color+$00,(a0)+
        move.w  d0,d2
        and.w   #$000f,d2
        move.w  d2,(a0)+
        addq.w  #1,d0
        dbf     d7,.line
        move.w  #$ffff,(a0)+
        move.w  #$fffe,(a0)+
        rts
```

## Compare masks and the unmaskable V7

IR2 bits 14-1 choose which beam bits take part in the ">=" test; a 0 bit makes that bit
compare true. Bit 15 is BFD, so **V7 can never be masked**. A mask such as "every 16 lines"
(`VE` = `$0F`) stops working once the line reaches `$80`: the unmaskable V7 makes every
comparison true. The HRM solves this with two loops, one for lines < `$80` and one that
waits for `%1xxx1111` patterns, switching between them with SKIP and COPJMP1/COPJMP2. Most
programs simply emit one WAIT per wanted line.

## Jumps and split lists

COP2LC is a free second pointer. The copper may write COP1LC/COP2LC (`$080`-`$086`) and strobe
COPJMP1/COPJMP2 (`$088`/`$08A`) itself, so a list can jump:

```asm
coplist:
        dc.w    color+$00,$0000
cop_jmp:
        dc.w    cop2lc,$0000,cop2lc+2,$0000     ; patched with the address of part 2
        dc.w    copjmp2,$0000                   ; jump
```

The copper restarts from COP1LC at every vertical blank, so a list that writes COP1LC changes
where the **next** field starts. The copper never returns from a jump; there is no subroutine call.
A `dc.w cop2lc,hi,cop2lc+2,lo` pair cannot hold a relocatable address in hunk format -- patch
the words at run time.

## Copper interrupts

Setting INTREQ bit 4 (COPER) from the copper raises a level-3 interrupt at a beam position
(INTREQ `$09C` is copper-writable):

```asm
        dc.w    $f001,$fffe                     ; line 240
        dc.w    intreq,$8010                    ; INTF_SETCLR!INTF_COPER
```

The CPU handler must acknowledge COPER in INTREQ and INTENA must have
`INTF_INTEN!INTF_COPER` set. See [interrupts-and-dma.md](interrupts-and-dma.md#level-3-handler).

## Interlace

An interlaced frame is two fields: the long field (VPOSR bit 15 LOF = 1) shows one set of
lines, the short field the other. Bitplane pointers must differ by one stored row between
the fields, so you need **two copper lists** (identical except for the pointer values) and
must start the right one each field:

```asm
; in the level-3 VERTB handler (a6 = $dff000)
        tst.w   vposr(a6)               ; bit 15 = LOF (read-only VPOSR)
        bmi.s   .long
        move.l  #coplist_short,cop1lc(a6)
        bra.s   .go
.long   move.l  #coplist_long,cop1lc(a6)
.go     move.w  d0,copjmp1(a6)          ; restart now, still inside vertical blank
```

HRM convention: the long field (LOF = 1) shows the rows starting at the plane start, the short
field starts one row later. BPLCON0 must have LACE (bit 2) set in both lists. See
[playfields.md](playfields.md#interlace).

## Copper and the blitter

- Set CDANG from the CPU (`move.w #$0002,copcon(a6)`), then MOVEs to `$040`-`$07E` work;
  writing BLTSIZE last starts a blit at a beam position.
- Never change blitter registers while a blit runs. A WAIT with IR2 bit 15 (BFD) = 0 also
  waits for the blitter-finished flag:

```asm
        dc.w    $4001,$7ffe             ; wait for line $40 AND blitter done
```

- Clear COPCON again before handing the machine back.

## Timing

- A MOVE costs 4 memory-cycle times (the copper only gets odd cycles) = 8 lores pixels.
  Several MOVEs after one WAIT therefore land 8 lores pixels apart on the line; that is the
  finest colour-change granularity without extra WAITs.
- A WAIT costs 3 cycles (6 cycle times) because the copper needs an extra cycle to wake up.
- Change bitplane/sprite pointers and display registers before the first display line
  (between line 0 and DIWSTRT), or at a line where nothing is being fetched.
- The copper can be delayed only by itself: DMA slots for disk/audio/sprites/bitplanes use
  other cycles, and it outranks the blitter and the CPU.

## Common mistakes

- Copper list in fast RAM (plain `data` section): nothing or garbage is displayed.
- Forgetting `$FFFF,$FFFE`: the copper runs off into random memory and writes registers.
- Using `$2C01` for line 300 without a preceding `$FFDF,$FFFE` wait: executes immediately.
- Enabling copper DMA before loading COP1LC and strobing COPJMP1.
- `clr.w copjmp1(a6)` (68000 reads first) -- use `move.w d0,copjmp1(a6)`.
- MOVEs to blitter registers without CDANG, or to offsets below `$040` at all: silently
  ignored (and a sign of a broken list).
- Changing a list the copper is currently executing: build a new list and swap COP1LC during
  vertical blank, or patch only words the copper has already passed.
- With the OS alive, writing COP1LC directly: graphics.library overwrites it next vertical
  blank.
- Expecting a masked WAIT such as `$0F01,$8F00` to keep firing every 16 lines past line 127
  (V7 is not maskable, so from line `$80` on it is always true).
