# cia.resource: interrupt vectors and ICR control

[AddICRVector](#addicrvector) claims one ICR bit (and with it the timer, serial register or FLAG
input behind it) and installs your handler; [RemICRVector](#remicrvector) gives it back.
[AbleICR](#ableicr) masks or unmasks CIA interrupt sources and [SetICR](#seticr) clears, triggers or
samples pending flags. Every call takes the resource base in A6: the base from
`OpenResource("ciaa.resource")` acts on CIA-A, the one from `"ciab.resource"` on CIA-B. Mask arguments
use the ICR layout (`CIAICRF_TA` $01, `TB` $02, `ALRM` $04, `SP` $08, `FLG` $10; bit 7 `CIAICRF_SETCLR`).

## AddICRVector
`struct Interrupt * AddICRVector(struct Library *resource, LONG iCRBit, struct Interrupt *interrupt)` — LVO -6 (-$6)
Registers: resource=A6, iCRBit=D0, interrupt=A1; result in D0

Claim one CIA interrupt bit for a handler; fails with the owner if the bit is taken.

- **resource** — `ciaa.resource` or `ciab.resource` base (in A6).
- **iCRBit** — bit number 0-4: `CIAICRB_TA`, `CIAICRB_TB`, `CIAICRB_ALRM`, `CIAICRB_SP`, `CIAICRB_FLG`.
- **interrupt** — initialised `struct Interrupt`: `is_Code`, `is_Data` (A1 in the handler), `ln_Type`
  = `NT_INTERRUPT`, `ln_Name` identifying you.
- **Result** — 0 on success (you own the bit and its hardware). Otherwise a pointer to the
  `struct Interrupt` of the current owner.

On success the interrupt for that bit is enabled at once, so it may fire immediately.

### Example
```asm
; Claim a free CIA-B timer and call TimerCode 50 times a second.
        include "exec/types.i"
        include "exec/nodes.i"
        include "exec/interrupts.i"
        include "exec/execbase.i"
        include "hardware/cia.i"
        include "lvo/exec_lib.i"
        include "lvo/cia_lib.i"

StartCiaTimer:                          ; out: D0 = 0 ok, -1 no timer
        movem.l d2-d3/a2-a3/a6,-(sp)
        move.l  4.w,a6
        move.l  ex_EClockFrequency(a6),d3
        divu    #50,d3                  ; latch for 50 Hz (fits: < 65536)
        lea     ciabname(pc),a1
        jsr     _LVOOpenResource(a6)
        move.l  d0,ciabbase
        beq     .fail
        jsr     _LVODisable(a6)
        move.l  ciabbase,a6
        moveq   #CIAICRB_TA,d2
        move.l  d2,d0
        lea     timerint,a1
        jsr     _LVOAddICRVector(a6)
        tst.l   d0
        beq.s   .own
        moveq   #CIAICRB_TB,d2
        move.l  d2,d0
        lea     timerint,a1
        jsr     _LVOAddICRVector(a6)
        tst.l   d0
        bne.s   .busy
.own:
        move.b  d2,timerbit
        lea     $bfd000,a3              ; CIA-B
        lea     ciacra(a3),a2           ; timer A: CRA, TALO/TAHI
        lea     ciatalo(a3),a3
        moveq   #%11000000,d1           ; CRA bits we do not own (SPMODE, TODIN)
        tst.b   d2
        beq.s   .isA
        lea     ciacrb-ciacra(a2),a2    ; timer B: CRB, TBLO/TBHI
        lea     ciatblo-ciatalo(a3),a3
        moveq   #%10000000,d1           ; CRB: keep ALARM only (INMODE 00 = count E clock)
.isA:
        move.l  a2,timercr
        and.b   (a2),d1                 ; stopped, continuous, no PB output
        move.b  d1,(a2)
        move.b  d3,(a3)                 ; latch low byte first
        lsr.w   #8,d3
        move.b  d3,$100(a3)             ; then high byte (TAHI/TBHI)
        or.b    #CIACRAF_LOAD!CIACRAF_START,d1  ; same bits in CRB
        move.b  d1,(a2)
        move.l  4.w,a6
        jsr     _LVOEnable(a6)
        moveq   #0,d0
        bra.s   .out
.busy:
        move.l  4.w,a6
        jsr     _LVOEnable(a6)          ; could try ciaa.resource here
.fail:
        moveq   #-1,d0
.out:
        movem.l (sp)+,d2-d3/a2-a3/a6
        rts

StopCiaTimer:                           ; only after StartCiaTimer returned 0
        move.l  a6,-(sp)
        move.l  timercr,a0
        bclr    #CIACRAB_START,(a0)     ; stop the timer
        move.l  ciabbase,a6
        moveq   #0,d0
        move.b  timerbit,d0
        lea     timerint,a1
        jsr     _LVORemICRVector(a6)
        move.l  (sp)+,a6
        rts

TimerCode:                              ; A1 = is_Data
        addq.l  #1,(a1)
        moveq   #0,d0
        rts

ciabname:
        dc.b    "ciab.resource",0
intname:
        dc.b    "mygame timer",0
        even

        section data,data
timerint:
        dc.l    0,0                     ; ln_Succ, ln_Pred
        dc.b    NT_INTERRUPT,0          ; ln_Type, ln_Pri
        dc.l    intname                 ; ln_Name
        dc.l    ticks                   ; is_Data
        dc.l    TimerCode               ; is_Code
ciabbase:       dc.l    0
timercr:        dc.l    0
ticks:          dc.l    0
timerbit:       dc.b    0
        even
```

### Gotchas
- Never assume any CIA hardware is free: own it through AddICRVector first, and try the other
  timer / the other CIA when the result is non-zero. Exit cleanly if all four timers are taken.
- Do not change the timer (or other hardware) before AddICRVector succeeds. Calling it under Disable
  lets you set the hardware to a known state before the handler can run.
- To own a timer without taking interrupts, claim it and then mask the bit with [AbleICR](#ableicr).
- CIA-B interrupts at level 6 and holds off all lower levels while the handler runs: keep it short.
- The owner pointer returned on failure belongs to someone else: don't touch it.
- Always [RemICRVector](#remicrvector) before exiting.

**See also:** [RemICRVector](#remicrvector), [AbleICR](#ableicr), [SetICR](#seticr), exec [OpenResource](../exec/libraries-devices-resources.md#openresource), lowlevel [AddTimerInt](../lowlevel/interrupts-and-timing.md#addtimerint)

## RemICRVector
`VOID RemICRVector(struct Library *resource, LONG iCRBit, struct Interrupt *interrupt)` — LVO -12 (-$C)
Registers: resource=A6, iCRBit=D0, interrupt=A1; no result

Release a CIA interrupt bit claimed with AddICRVector and disable its interrupt.

- **resource** — the same resource base used for AddICRVector.
- **iCRBit** — the same bit number (0-4).
- **interrupt** — the same `struct Interrupt` pointer.

### Gotchas
- Stop the hardware (e.g. clear the timer's START bit) before removing the vector; a running timer
  keeps setting its flag, and the next owner gets an immediate interrupt when it enables the bit.
- Free the Interrupt structure and handler code only after this call.

**See also:** [AddICRVector](#addicrvector)

## AbleICR
`WORD AbleICR(struct Library *resource, LONG mask)` — LVO -18 (-$12)
Registers: resource=A6, mask=D0; result in D0

Enable or disable CIA interrupt sources and return the previous enable mask.

- **resource** — CIA resource base (A6).
- **mask** — ICR bit mask. Bit 7 (`CIAICRF_SETCLR`) set: enable the listed sources; bit 7 clear:
  disable them. 0 = change nothing.
- **Result** — enable mask before the change (low byte, ICR layout).

### Example
```c
#include <proto/exec.h>
#include <proto/cia.h>
#include <hardware/cia.h>

extern struct Library *CiabBase;        /* from OpenResource("ciab.resource") */

/* pause and resume the CIA-B timer B interrupt we own */
void PauseTimerB(void)
{
    AbleICR(CiabBase, CIAICRF_TB);                      /* disable */
}

void ResumeTimerB(void)
{
    SetICR(CiabBase, CIAICRF_TB);                       /* drop a stale pending flag */
    AbleICR(CiabBase, CIAICRF_SETCLR | CIAICRF_TB);     /* enable */
}

WORD CiabEnabled(void)
{
    return (WORD)(AbleICR(CiabBase, 0) & 0x1F);         /* read only */
}
```

### Gotchas
- Enabling a source whose flag is already pending causes an interrupt immediately: clear it first
  with [SetICR](#seticr).
- Only change bits you own.

**See also:** [SetICR](#seticr), [AddICRVector](#addicrvector)

## SetICR
`WORD SetICR(struct Library *resource, LONG mask)` — LVO -24 (-$18)
Registers: resource=A6, mask=D0; result in D0

Clear, cause or sample pending CIA interrupt flags without reading the ICR yourself.

- **resource** — CIA resource base (A6).
- **mask** — ICR bit mask. Bit 7 set: cause (set) the listed interrupts; bit 7 clear: clear them.
  0 = only sample.
- **Result** — the interrupt flag state before the change (low byte, ICR layout).

### Gotchas
- Never read `ciaicr` directly while the OS runs: the read clears all flags and other handlers
  (keyboard, timer.device, disk index) miss their interrupts. `SetICR(base, 0)` samples safely.
- Setting a flag for an enabled source generates the interrupt at once.
- Only clear or cause bits you own.

**See also:** [AbleICR](#ableicr), [AddICRVector](#addicrvector)
