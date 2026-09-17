# Taking over the system (and giving it back)

Bare-metal startup/exit sequence for games and demos, plus the OS-friendly alternative.

Direct hardware access is only legal once the OS no longer uses that hardware. A demo or game
therefore: blanks the OS display, locks the blitter, stops multitasking, saves the interrupt/
DMA/ADKCON state, installs its own copper list and interrupt vectors -- and restores all of it
in reverse order on exit so the Workbench comes back.

Registers: [INTENA](../registers/interrupts.md#intena), [INTENAR](../registers/interrupts.md#intenar),
[INTREQ](../registers/interrupts.md#intreq), [DMACON](../registers/dma-beam.md#dmacon),
[DMACONR](../registers/dma-beam.md#dmaconr), [ADKCON](../registers/audio.md#adkcon),
[ADKCONR](../registers/audio.md#adkconr), [COP1LCH, COP1LCL](../registers/copper.md#cop1lch-cop1lcl),
[COPJMP1](../registers/copper.md#copjmp1).

## The sequence

**Startup**

1. `OpenLibrary("graphics.library",0)` (exec LVO -552).
2. Save `gb_ActiView` (current View) and `gb_copinit` (the OS copper start-up list) from
   GfxBase (`graphics/gfxbase.i`; offsets `$22` and `$26`).
3. `LoadView(NULL)` (graphics LVO -222): the OS display disappears (its sprites keep running).
4. `WaitTOF()` twice (LVO -270): the change takes effect; two fields cover interlaced views.
5. `OwnBlitter()` (LVO -456), then `WaitBlit()` (LVO -228): the blitter is yours and idle.
6. `Forbid()` (exec LVO -132): no other task runs. (Interrupts are handled in the next steps.)
7. Get the VBR (68010+).
8. Save `INTENAR`, `DMACONR`, `ADKCONR`.
9. Disable: INTENA `$7FFF`, INTREQ `$7FFF`; at vertical blank DMACON `$7FFF`; clear audio
   modulation bits in ADKCON.
10. Install your vectors (`VBR+$6C`, ...), your copper list (COP1LC + COPJMP1), enable your DMA
    channels and interrupts.

**Exit** (reverse)

1. INTENA `$7FFF`, INTREQ `$7FFF`, DMACON `$7FFF`.
2. Restore the vectors.
3. COP1LC = saved `gb_copinit`, strobe COPJMP1.
4. Restore ADKCON, DMACON, INTENA: clear all (`$7FFF`), then write `saved ! $8000`.
5. `LoadView(saved ActiView)`, `WaitTOF()` twice (needs VERTB enabled again -- that is why
   INTENA comes first).
6. `WaitBlit()`, `DisownBlitter()` (LVO -462).
7. `Permit()` (exec LVO -138).
8. Optional: `RethinkDisplay()` (intuition LVO -390) to rebuild Intuition's screens.
9. `CloseLibrary` (exec LVO -414) for every library opened.

Between startup step 9 and exit step 1 no OS call that needs interrupts or task switching
works (DOS I/O, `WaitTOF`, `Delay`, ...). Load files before taking over.

## Find the VBR

On a 68010 or later the exception vectors live at `VBR + offset`; the VBR is only readable in
supervisor mode. `Supervisor()` (exec LVO -30, function pointer in **A5**) runs a routine
ending in `RTE` with full register access:

```asm
        move.l  4.w,a6
        moveq   #0,d0                   ; 68000: VBR = 0
        btst    #AFB_68010,AttnFlags+1(a6)      ; set for 68010 and later
        beq.s   .is68000
        lea     GetVBR(pc),a5
        jsr     _LVOSupervisor(a6)
.is68000
        move.l  d0,vbr
        ; ...
        cnop    0,4
GetVBR: dc.w    $4e7a,$0801             ; movec vbr,d0 (68010+ opcode; plain dc.w so a
        rte                             ; 68000-only assembler setting accepts it)
```

## Complete skeleton

```asm
        include "exec/execbase.i"
        include "graphics/gfxbase.i"
        include "hardware/custom.i"
        include "hardware/dmabits.i"
        include "hardware/intbits.i"
        include "hardware/cia.i"
        include "lvo/exec_lib.i"
        include "lvo/graphics_lib.i"
        include "lvo/intuition_lib.i"

        section code,code
Start:
        move.l  4.w,a6
        lea     gfxname(pc),a1
        moveq   #0,d0
        jsr     _LVOOpenLibrary(a6)
        move.l  d0,gfxbase
        beq     .nogfx
        lea     intname(pc),a1
        moveq   #0,d0
        jsr     _LVOOpenLibrary(a6)
        move.l  d0,intbase              ; only used for RethinkDisplay

        move.l  gfxbase,a6
        move.l  gb_ActiView(a6),oldview
        move.l  gb_copinit(a6),oldcopinit
        sub.l   a1,a1
        jsr     _LVOLoadView(a6)        ; LoadView(NULL)
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOOwnBlitter(a6)
        jsr     _LVOWaitBlit(a6)

        move.l  4.w,a6
        jsr     _LVOForbid(a6)

        moveq   #0,d0                   ; VBR
        btst    #AFB_68010,AttnFlags+1(a6)
        beq.s   .novbr
        lea     GetVBR(pc),a5
        jsr     _LVOSupervisor(a6)
.novbr  move.l  d0,vbr

        lea     $dff000,a5              ; a5 = custom from here on (a6 = library base)
        move.w  intenar(a5),oldintena
        move.w  dmaconr(a5),olddmacon
        move.w  adkconr(a5),oldadkcon
        move.w  #$7fff,intena(a5)       ; no interrupts
        move.w  #$7fff,intreq(a5)
        move.w  #$7fff,intreq(a5)
.vb     move.l  vposr(a5),d0            ; wait for line 0 so no sprite is cut mid-way
        and.l   #$0001ff00,d0
        bne.s   .vb
        move.w  #$7fff,dmacon(a5)       ; all DMA off
        move.w  #$00ff,adkcon(a5)       ; no audio modulation

        move.l  vbr,a0
        move.l  $6c(a0),oldlevel3
        move.l  #Level3,$6c(a0)
        move.l  #coplist,cop1lc(a5)
        move.w  d0,copjmp1(a5)          ; strobe (MOVE, never CLR)
        move.w  #DMAF_SETCLR!DMAF_MASTER!DMAF_RASTER!DMAF_COPPER!DMAF_BLITTER,dmacon(a5)
        move.w  #INTF_SETCLR!INTF_INTEN!INTF_VERTB,intena(a5)

        bsr     Main                    ; ----- your program -----

        lea     $dff000,a5
        move.w  #$7fff,intena(a5)
        move.w  #$7fff,intreq(a5)
        move.w  #$7fff,dmacon(a5)
        move.l  vbr,a0
        move.l  oldlevel3,$6c(a0)
        move.l  oldcopinit,cop1lc(a5)
        move.w  d0,copjmp1(a5)
        move.w  #$7fff,adkcon(a5)
        move.w  oldadkcon,d0
        or.w    #$8000,d0
        move.w  d0,adkcon(a5)
        move.w  olddmacon,d0
        or.w    #$8000,d0
        move.w  d0,dmacon(a5)
        move.w  oldintena,d0
        or.w    #$8000,d0
        move.w  d0,intena(a5)

        move.l  gfxbase,a6
        move.l  oldview,a1
        jsr     _LVOLoadView(a6)
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOWaitBlit(a6)
        jsr     _LVODisownBlitter(a6)
        move.l  4.w,a6
        jsr     _LVOPermit(a6)

        move.l  intbase,d0
        beq.s   .noint
        move.l  d0,a6
        jsr     _LVORethinkDisplay(a6)
        move.l  a6,a1
        move.l  4.w,a6
        jsr     _LVOCloseLibrary(a6)
.noint  move.l  gfxbase,a1
        move.l  4.w,a6
        jsr     _LVOCloseLibrary(a6)
.nogfx  moveq   #0,d0
        rts

; ----- program: run until the left mouse button is pressed
Main:
.loop   move.l  framecount,d0
.wait   cmp.l   framecount,d0           ; wait for the next VERTB
        beq.s   .wait
        ; per-frame work here
        btst    #CIAB_GAMEPORT0,$bfe001
        bne.s   .loop
        rts

; ----- level 3 interrupt
Level3:
        movem.l d0-d1/a0,-(sp)
        lea     $dff000,a0
        move.w  intreqr(a0),d0
        and.w   #INTF_VERTB!INTF_COPER!INTF_BLIT,d0
        btst    #INTB_VERTB,d0
        beq.s   .ack
        addq.l  #1,framecount
.ack    move.w  d0,intreq(a0)
        move.w  d0,intreq(a0)
        movem.l (sp)+,d0-d1/a0
        rte

        cnop    0,4
GetVBR: dc.w    $4e7a,$0801             ; movec vbr,d0
        rte

gfxname: dc.b   "graphics.library",0
intname: dc.b   "intuition.library",0
        even

        section copper,data_c
coplist:
        dc.w    bplcon0,$0200           ; no bitplanes, background only
        dc.w    color+$00,$0000
        dc.w    $8001,$fffe
        dc.w    color+$00,$000f
        dc.w    $8101,$fffe
        dc.w    color+$00,$0000
        dc.w    $ffff,$fffe

        section vars,bss
gfxbase:    ds.l    1
intbase:    ds.l    1
oldview:    ds.l    1
oldcopinit: ds.l    1
vbr:        ds.l    1
oldlevel3:  ds.l    1
framecount: ds.l    1
oldintena:  ds.w    1
olddmacon:  ds.w    1
oldadkcon:  ds.w    1
```

Extend it the same way for other vectors: level 2 (`VBR+$68`, keyboard -- see
[cia-and-io.md](cia-and-io.md#keyboard)), level 4 (`VBR+$70`, audio), level 6 (`VBR+$78`, CIA-B).
Save and restore each vector you replace, and enable the matching INTENA bits.

The same sequence in C (Bartman's gcc, `proto/*.h` inlines), outline only:

```c
struct GfxBase *GfxBase = (struct GfxBase *)OpenLibrary("graphics.library", 0);
struct View *oldView = GfxBase->ActiView;
struct copinit *oldCopinit = GfxBase->copinit;
LoadView(NULL); WaitTOF(); WaitTOF();
OwnBlitter(); WaitBlit();
Forbid();
/* vbr via Supervisor() + movec in an asm helper when SysBase->AttnFlags & AFF_68010 */
UWORD oldIntena = custom.intenar, oldDmacon = custom.dmaconr, oldAdkcon = custom.adkconr;
custom.intena = 0x7fff; custom.intreq = 0x7fff; custom.dmacon = 0x7fff;
/* ... install vectors, custom.cop1lc = (ULONG)myCopper; custom.copjmp1 = 0x7fff; ... */
/* exit: */
custom.intena = 0x7fff; custom.intreq = 0x7fff; custom.dmacon = 0x7fff;
custom.cop1lc = (ULONG)oldCopinit; custom.copjmp1 = 0x7fff;
custom.adkcon = 0x7fff; custom.adkcon = 0x8000 | oldAdkcon;
custom.dmacon = 0x8000 | oldDmacon;
custom.intena = 0x8000 | oldIntena;
LoadView(oldView); WaitTOF(); WaitTOF();
WaitBlit(); DisownBlitter();
Permit();
CloseLibrary((struct Library *)GfxBase);
```

(`custom` is the `struct Custom` from `hardware/custom.h` located at `$DFF000`, e.g.
`#define custom (*(struct Custom *)0xdff000)`. Keep the vector handlers in assembler: compiled C
functions end in `RTS`, not `RTE`, and do not save all registers.)

## OS-friendly alternative: AddIntServer

When the program must coexist with the OS (a tool, a Workbench game in a window, a music
player), do not touch vectors, INTENA or DMACON globally:

- Per-frame code: add a server to the VERTB chain with `AddIntServer(INTB_VERTB, interrupt)`
  (exec LVO -168, D0 = bit number, A1 = `struct Interrupt`); remove it with `RemIntServer`
  (LVO -174) before exiting.
- Display: open a screen/View through intuition/graphics (user copper lists via the OS), not by
  writing COP1LC.
- Blitter: `OwnBlitter`/`WaitBlit` ... `DisownBlitter` around direct register use.
- Audio: allocate channels with audio.device. CIAs: `cia.resource`. Pot port: `potgo.resource`.

```asm
        include "exec/interrupts.i"
        include "exec/nodes.i"
        include "hardware/intbits.i"
        include "lvo/exec_lib.i"

        section code,code
AddVBServer:
        move.l  4.w,a6
        lea     vbserver,a1
        move.b  #NT_INTERRUPT,LN_TYPE(a1)
        move.b  #0,LN_PRI(a1)
        move.l  #vbname,LN_NAME(a1)
        move.l  #framecount,IS_DATA(a1)
        move.l  #VBCode,IS_CODE(a1)
        moveq   #INTB_VERTB,d0
        jsr     _LVOAddIntServer(a6)
        rts

RemVBServer:
        move.l  4.w,a6
        lea     vbserver,a1
        moveq   #INTB_VERTB,d0
        jsr     _LVORemIntServer(a6)
        rts

; Server: A1 = IS_DATA. May trash D0/D1/A0/A1/A5/A6, must preserve the rest.
VBCode:
        addq.l  #1,(a1)                 ; count frames
        lea     $dff000,a0              ; expected by later servers if priority >= 10
        moveq   #0,d0                   ; Z set: continue the chain (required for VERTB)
        rts

        section vars,bss
vbserver:   ds.b    IS_SIZE
framecount: ds.l    1

        section strings,data
vbname: dc.b    "myprog vblank",0
```

The chain dispatcher acknowledges the interrupt itself (unverified -- do not write INTREQ from a
server).

## Common mistakes

- Skipping `LoadView(NULL)` + `WaitTOF`: graphics.library keeps rewriting COP1LC and your list
  flickers or never shows.
- Restoring INTENA/DMACON with the saved value but without bit 15 (clears instead of sets),
  or without clearing everything first (bits you enabled stay on).
- Calling `WaitTOF` on exit before re-enabling INTENA: hangs forever.
- Hard-coding `$6C` instead of `VBR+$6C` (breaks on accelerated machines after SetPatch).
- Calling `Supervisor` with the routine address in A0 instead of A5, or ending it with `RTS`.
- Forgetting `DisownBlitter`/`Permit` on an error path: the Workbench freezes after exit.
- Turning DMA off mid-frame: the OS pointer sprite leaves a vertical bar.
- Leaving COPCON (copper danger) set, audio modulation bits, or the audio filter LED changed.
- Loading files (DOS) after INTENA was cleared.
- `OwnBlitter` twice in a row (does not nest -- deadlock).
