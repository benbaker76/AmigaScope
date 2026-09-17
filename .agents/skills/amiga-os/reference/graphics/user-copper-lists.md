# graphics.library: user copper lists

A user copper list adds your own copper MOVEs and WAITs (colour gradients, split-screen register
changes) to a ViewPort while the OS keeps building the rest of the display. Workflow: allocate a
zeroed `struct UCopList` yourself, [UCopperListInit](#ucopperlistinit) it for n instructions,
append instructions with [CWait](#cwait) / [CMove](#cmove), each followed by [CBump](#cbump)
(the [CWAIT/CMOVE/CEND macros](copper-macros.md) do both), terminate with CEND, then under
exec Forbid store it in `vp->UCopIns`, Permit, and rebuild the display (screens: intuition
RethinkDisplay; private View: MakeVPort + MrgCop + LoadView). The system frees the list with the
ViewPort's other lists ([FreeVPortCopLists](views-and-viewports.md#freevportcoplists)).
WAIT positions are relative to the top of the ViewPort; instructions must be in Y,X order.

## UCopperListInit
`struct CopList * UCopperListInit(struct UCopList *uCopList, LONG n)` — LVO -594 (-$252)
Registers: uCopList=A0, n=D0; result in D0

Allocate the instruction buffer inside a caller-allocated UCopList for n instructions.

- **uCopList** — a zeroed `struct UCopList` you allocated (exec AllocMem, `MEMF_PUBLIC |
  MEMF_CLEAR`, `sizeof(struct UCopList)` = 12 / asm `ucl_SIZEOF`). NULL does NOT allocate one.
- **n** — number of instructions the first buffer block holds (every CWait, CMove and the final
  CEND count one each).
- **Result** — pointer to the first `struct CopList` block (`uCopList->FirstCopList`), NOT the
  UCopList; 0 if the buffer could not be allocated.

The C macro form is [CINIT](copper-macros.md#cinit).

### Example
```c
/* blue gradient behind the first 16*8 lines of our own screen */
#define HW ((struct Custom *)0xdff000)   /* hardware/custom.h declares no `custom` object */

BOOL add_gradient(struct Screen *scr)
{
    struct UCopList *ucl;
    int i;

    ucl = AllocMem(sizeof(struct UCopList), MEMF_PUBLIC | MEMF_CLEAR);
    if (!ucl)
        return FALSE;
    if (!UCopperListInit(ucl, 16 * 2 + 1)) {     /* 16 waits + 16 moves + end */
        FreeMem(ucl, sizeof(struct UCopList));
        return FALSE;
    }
    for (i = 0; i < 16; i++) {
        CWait(ucl, i * 8, 0);                    /* line relative to ViewPort top */
        CBump(ucl);
        CMove(ucl, (APTR)&HW->color[0], i);      /* register ADDRESS, value */
        CBump(ucl);
    }
    CWait(ucl, 10000, 255);                      /* = CEND(ucl) */
    CBump(ucl);

    Forbid();
    scr->ViewPort.UCopIns = ucl;
    Permit();
    RethinkDisplay();                            /* intuition rebuilds the copper lists */
    return TRUE;
}
```

```asm
        include "lvo/intuition_lib.i"

; in: a0 = ViewPort (e.g. screen + sc_ViewPort); out: d0 = 0 on failure
AddGradient:
        movem.l d2/a2-a3/a6,-(sp)
        move.l  a0,a2
        move.l  4.w,a6
        moveq   #ucl_SIZEOF,d0
        move.l  #MEMF_PUBLIC!MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        move.l  d0,a3                   ; a3 = UCopList
        tst.l   d0
        beq     .out
        move.l  _GfxBase,a6
        move.l  a3,a0
        moveq   #16*2+1,d0              ; instructions incl. end
        jsr     _LVOUCopperListInit(a6)
        tst.l   d0
        beq.s   .nobuf
        moveq   #0,d2                   ; i
.loop:  move.l  a3,a1
        move.l  d2,d0
        lsl.l   #3,d0                   ; v = i*8
        moveq   #0,d1                   ; h
        jsr     _LVOCWait(a6)
        move.l  a3,a1
        jsr     _LVOCBump(a6)
        move.l  a3,a1
        move.l  #$dff000+color,d0       ; address of COLOR00 ($dff180)
        move.l  d2,d1                   ; $00i = blue ramp
        jsr     _LVOCMove(a6)
        move.l  a3,a1
        jsr     _LVOCBump(a6)
        addq.l  #1,d2
        cmp.l   #16,d2
        bne.s   .loop
        move.l  a3,a1                   ; CEND = CWait(10000,255) + CBump
        move.l  #10000,d0
        move.l  #255,d1
        jsr     _LVOCWait(a6)
        move.l  a3,a1
        jsr     _LVOCBump(a6)
        move.l  4.w,a6
        jsr     _LVOForbid(a6)
        move.l  a3,vp_UCopIns(a2)
        jsr     _LVOPermit(a6)
        move.l  _IntuitionBase,a6
        jsr     _LVORethinkDisplay(a6)
        moveq   #1,d0
        bra.s   .out
.nobuf: move.l  4.w,a6
        move.l  a3,a1
        moveq   #ucl_SIZEOF,d0
        jsr     _LVOFreeMem(a6)
        moveq   #0,d0
.out:   movem.l (sp)+,d2/a2-a3/a6
        rts
```

### Gotchas
- Never free the UCopList yourself once attached: FreeVPortCopLists (called when the screen or
  View is torn down) frees it. Intuition CloseScreen doing this is (unverified); to drop the list
  from a screen that stays open, FreeVPortCopLists(&scr->ViewPort) then intuition RemakeDisplay
  (unverified).
- Attach under Forbid/Permit and only after CEND: the display rebuild can happen at any time.
- By default the list is not clipped at the ViewPort's bottom edge; enable with VideoControl
  `VTAG_USERCLIP_SET`.
- If n is too small, [CBump](#cbump) moves on to a further instruction block.

**See also:** [CWait](#cwait), [CMove](#cmove), [CBump](#cbump), [CINIT](copper-macros.md#cinit),
[FreeVPortCopLists](views-and-viewports.md#freevportcoplists),
[VideoControl](views-and-viewports.md#videocontrol)

## CMove
`VOID CMove(struct UCopList *copList, APTR destination, LONG data)` — LVO -372 (-$174)
Registers: copList=A1, destination=D0, data=D1; no result

Write a copper MOVE (register = value) at the current position of a user copper list.

- **copList** — the UCopList.
- **destination** — ADDRESS of the custom-chip register, e.g. `$DFF180` for COLOR00
  (C `&custom->color[0]`, asm `$dff000+color`).
- **data** — 16-bit value to write.

Follow every CMove with [CBump](#cbump), or use the [CMOVE](copper-macros.md#cmove) macro.

### Gotchas
- hardware/custom.h does NOT declare a `custom` object (only a comment
  `extern struct Custom custom;`). Bartman's amiga-debug template defines
  `volatile struct Custom *custom` = `$DFF000` as a POINTER, so there write
  `CMove(ucl, (APTR)&custom->color[0], v); CBump(ucl);` -- the macro form
  `CMOVE(ucl, custom.color[0], v)` does not compile with a pointer.
- Bartman's hardware/custom.h declares the register fields `volatile` (the NDK 3.9 one does
  not): without the `(APTR)` cast gcc warns about discarding the qualifier.
- Only the low word is written; register must be copper-writable (COLOR, BPLCON, BPLxPT...).
- A COLORxx MOVE is 12-bit; full 24-bit AGA colours need the extra BPLCON3 LOCT writes
  described in the amiga-aga skill.

**See also:** [CWait](#cwait), [CBump](#cbump), [CMOVE](copper-macros.md#cmove)

## CWait
`VOID CWait(struct UCopList *copList, LONG v, LONG h)` — LVO -378 (-$17A)
Registers: copList=A1, v=D0, h=D1; no result

Write a copper WAIT for beam position (v,h) into a user copper list.

- **copList** — the UCopList.
- **v** — line relative to the top of the ViewPort.
- **h** — horizontal beam position; values above 222 are illegal.

Follow every CWait with [CBump](#cbump), or use the [CWAIT](copper-macros.md#cwait) macro.

### Gotchas
- Waits must be in increasing Y,X order; MrgCop merges sorted lists.
- The list end marker is `CWait(ucl, 10000, 255)` + CBump ([CEND](copper-macros.md#cend)).

**See also:** [CMove](#cmove), [CBump](#cbump), [CWAIT](copper-macros.md#cwait)

## CBump
`VOID CBump(struct UCopList *copList)` — LVO -366 (-$16E)
Registers: copList=A1; no result

Advance a user copper list's write pointer to the next instruction slot.

- **copList** — the UCopList. When the current block is full the pointer moves to a further
  instruction block.

Needed after every [CMove](#cmove) and [CWait](#cwait); the CMOVE/CWAIT/CEND macros call it for
you.

### Gotchas
- Forgetting it makes the next CMove/CWait overwrite the previous instruction.

**See also:** [CMove](#cmove), [CWait](#cwait), [UCopperListInit](#ucopperlistinit)
