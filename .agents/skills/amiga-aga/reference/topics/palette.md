# AGA palette: 24-bit colour and 256 entries

Lisa has 256 colour entries of 8 bits per gun, but only the 32 OCS addresses
`COLOR00-COLOR31` ($DFF180-$DFF1BE). BPLCON3 picks which 32 entries they reach (BANK) and
which half of each gun a write loads (LOCT). Registers: [COLORxx](../registers/aga.md#colorxx),
[BPLCON3](../registers/aga.md#bplcon3).

## One 24-bit colour: two writes

For entry n = BANK*32 + xx and colour $RRGGBB:

1. BPLCON3 = BANK<<13 | $0C00 (LOCT=0). Write `$0RGB` of the **high** nibbles to COLORxx.
   Lisa also copies them into the low nibbles (so 12-bit code still works).
2. BPLCON3 = BANK<<13 | $0E00 (LOCT=1). Write `$0RGB` of the **low** nibbles to COLORxx.
3. Restore BPLCON3 (normally $0C00).

| Step | BPLCON3 | COLORxx data | Result |
|---|---|---|---|
| high | BANK<<13 + $0C00 | `$0RGB` from R7-4, G7-4, B7-4 | $RRGGBB with low nibble = high nibble |
| low | BANK<<13 + $0E00 | `$0rgb` from R3-0, G3-0, B3-0 | exact $RRGGBB |

`$0C00` keeps PF2OF at the OCS value 011; if your display uses another PF2OF or the
border bits, OR those in instead. Bit 15 of the LOCT=0 word is the genlock T bit.

```asm
; copper: entry 37 (bank 1, register 5) = $A0C8FF
        dc.w    bplcon3,$2c00       ; BANK=001, LOCT=0
        dc.w    color+5*2,$0acf     ; high: R=A G=C B=F
        dc.w    bplcon3,$2e00       ; BANK=001, LOCT=1
        dc.w    color+5*2,$008f     ; low:  R=0 G=8 B=F
        dc.w    bplcon3,$0c00
```

## Splitting $00RRGGBB into the two words

```asm
; Split24 -- d0.l = $00RRGGBB (preserved)
;            -> d1.w = $0RGB high nibbles, d2.w = $0RGB low nibbles
; trashes d3-d4
Split24:
        lsl.l   #8,d0               ; $RRGGBB00
        moveq   #0,d1
        moveq   #0,d2
        moveq   #3-1,d4
.comp   rol.l   #8,d0               ; next gun (R, G, B) into the low byte
        moveq   #$0f,d3
        and.b   d0,d3
        lsl.w   #4,d2
        or.w    d3,d2               ; low nibble
        moveq   #0,d3
        move.b  d0,d3
        lsr.b   #4,d3
        lsl.w   #4,d1
        or.w    d3,d1               ; high nibble
        dbf     d4,.comp
        rts                         ; three ROLs restored d0 = $00RRGGBB
```

## Loading all 256 colours from the copper

Per bank: one BPLCON3 MOVE + 32 high MOVEs, one BPLCON3 MOVE + 32 low MOVEs. 8 banks =
528 MOVEs, plus a final BPLCON3 = 529 MOVEs = 1058 words (2116 bytes). The AA spec gives a
copper instruction 4 memory cycles (4 colour clocks), about 56 per scanline, so the load
takes roughly 10 lines: put it at the top of the list, before the first WAIT into the
display window.

```asm
        include "hardware/custom.i"
; CopPal256 -- a0 = 256 x ULONG $00RRGGBB, a1 = copper write pointer
; out: a1 advanced by 2116 bytes. Other registers preserved.
CopPal256:
        movem.l d0-d7/a0/a2-a3,-(sp)
        moveq   #0,d7               ; bank 0-7
.bank   move.w  d7,d6
        lsl.w   #8,d6
        lsl.w   #5,d6               ; BANK2-0 -> bits 15-13
        ori.w   #$0c00,d6           ; PF2OF=011
        moveq   #0,d5               ; pass 0 = high nibbles, 1 = low
.pass   bclr    #9,d6               ; LOCT=0
        tst.w   d5
        beq.s   .hi
        bset    #9,d6               ; LOCT=1
.hi     move.w  #bplcon3,(a1)+
        move.w  d6,(a1)+
        movea.l a0,a2
        lea     color.w,a3          ; a3 = register offset $180
.col    move.l  (a2)+,d0
        bsr     Split24
        move.w  a3,(a1)+
        tst.w   d5
        bne.s   .lo
        move.w  d1,(a1)+
        bra.s   .next
.lo     move.w  d2,(a1)+
.next   addq.w  #2,a3
        cmpa.w  #color+32*2,a3
        bne.s   .col
        addq.w  #1,d5
        cmpi.w  #2,d5
        bne.s   .pass
        lea     32*4(a0),a0         ; next 32 source colours
        addq.w  #1,d7
        cmpi.w  #8,d7
        bne.s   .bank
        move.w  #bplcon3,(a1)+
        move.w  #$0c00,(a1)+        ; leave bank 0, LOCT=0
        movem.l (sp)+,d0-d7/a0/a2-a3
        rts
```

Block layout (offsets from the block start, handy for patching): bank b starts at
`b*264`; the high data word of entry n is at `(n>>5)*264 + 6 + (n&31)*4`, the low data word
at that offset + 132.

## Fading

- 12-bit OCS fades have 16 steps; with 24 bits you get 256. Scale each gun:
  `gun * level >> 8` for level 0-256.
- Rebuild both words for every entry and patch them into the copper block during the
  vertical blank. Never write BPLCON3/COLOR from an interrupt while the copper list also
  writes BPLCON3: the two fight over BANK/LOCT.

```asm
; Fade24 -- d0.l = $00RRGGBB, d1.w = level 0-256 -> d0.l = faded colour. Trashes d2-d4.
Fade24:
        lsl.l   #8,d0               ; $RRGGBB00
        moveq   #0,d4
        moveq   #3-1,d3
.gun    rol.l   #8,d0
        moveq   #0,d2
        move.b  d0,d2
        mulu.w  d1,d2               ; gun * level
        lsr.l   #8,d2
        lsl.l   #8,d4
        or.b    d2,d4
        dbf     d3,.gun
        move.l  d4,d0
        rts

; per frame, for n = 0-255 with a3 -> copper palette block, a4 -> source table:
;   move.l (a4)+,d0 / bsr Fade24 / bsr Split24 / poke d1, d2 at the offsets above
```

## OS way: LoadRGB32 table format (V39)

On an OS screen never poke COLOR registers: use graphics.library `LoadRGB32(vp, table)`,
`SetRGB32(vp, n, r, g, b)`, `SetRGB32CM(cm, n, r, g, b)` and `GetRGB32(cm, first, count,
table)`, or intuition's `SA_Colors32` tag (it takes the same table). Full entries: see the
amiga-os skill.

Table (all ULONG, big-endian):

| Item | Content |
|---|---|
| header | `(count<<16)+first`: high word = number of colours, low word = first pen |
| per colour | R, G, B, each 32 bits left-justified |
| ... | more header + colour runs may follow (sparse loads) |
| end | a 0 ULONG (a header with count 0) |

Left-justified means the 8-bit gun fills the top byte; repeat it to fill the word, as
RandyAGA advises: `$1F` -> `$1F1F1F1F`, 4-bit `$3` -> `$33333333`.

```asm
Colors32:
        dc.w    3,0                     ; 3 colours starting at pen 0
        dc.l    $00000000,$00000000,$00000000   ; black
        dc.l    $ffffffff,$ffffffff,$ffffffff   ; white
        dc.l    $a0a0a0a0,$c8c8c8c8,$ffffffff   ; $A0C8FF
        dc.w    1,200                   ; 1 colour at pen 200
        dc.l    $12121212,$34343434,$56565656
        dc.l    0                       ; terminator
```

```c
/* 256-colour table: 1 + 256*3 + 1 ULONGs */
static ULONG pal32[1 + 256 * 3 + 1];

void build_pal32(const ULONG *rgb24)          /* 256 x 0x00RRGGBB */
{
    ULONG *p = pal32;
    *p++ = (256UL << 16) | 0;
    for (int i = 0; i < 256; i++) {
        ULONG c = rgb24[i];
        *p++ = ((c >> 16) & 0xff) * 0x01010101UL;
        *p++ = ((c >> 8) & 0xff) * 0x01010101UL;
        *p++ = (c & 0xff) * 0x01010101UL;
    }
    *p = 0;
}
/* LoadRGB32(&screen->ViewPort, pal32); */
```

## Common mistakes

- Writing the low nibbles first: the following LOCT=0 write overwrites them.
- Leaving BANK or LOCT set: every later COLORxx write (yours, a music or fade routine, a
  copper list split) goes to the wrong entries or nibbles.
- Forgetting PF2OF when composing BPLCON3 from scratch: `bplcon3,BANK<<13` alone sets PF2OF
  to 0 and moves dual-playfield colours.
- Treating COLORxx as readable: it is write-only. RDRAM (BPLCON2) turns writes into
  reads, but the sources give no usable read-back procedure. Keep a shadow palette.
- LoadRGB32 components right-justified (`$000000FF`): that is almost black. Left-justify.
- Loaders capped at 32 colours: base the limit on the ViewPort's `ColorMap->Count`
  (RandyAGA), not on 32.

**See also:** [COLORxx](../registers/aga.md#colorxx), [BPLCON3](../registers/aga.md#bplcon3), [OS level](os-level.md)
