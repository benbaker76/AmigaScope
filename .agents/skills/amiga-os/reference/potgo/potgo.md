# potgo.resource: allocating and writing POTGO bits

Allocate the pot-port bits you need with [AllocPotBits](#allocpotbits), change the pins with
[WritePotgo](#writepotgo) (only inside the bits you were granted), read pin levels from POTINP
(`$DFF016`) yourself, and release the bits with [FreePotBits](#freepotbits). Call with A6 =
`PotgoBase` from `OpenResource("potgo.resource")`. Bit names (START, DATxx, OUTxx) are described in
[the POTGO bit table](index.md#potgo-bits-as-the-resource-names-them).

## AllocPotBits
`UWORD AllocPotBits(ULONG bits)` — LVO -6 (-$6)
Registers: bits=D0; result in D0

Reserve bits of the shared POTGO register for your program.

- **bits** — request mask: START (bit 0) to control pot counting on your input pins; DATLX (8),
  DATLY (10), DATRX (12), DATRY (14) for each pin you use; OUTLX (9), OUTLY (11), OUTRX (13), OUTRY
  (15) additionally when you promise to use that pin only as an output (then other users' START
  pulses don't matter to you). START must be requested in the same call as the DATxx bits it applies
  to, with their OUTxx bits clear.
- **Result** — UWORD: the START and DATxx bits actually granted (OUTxx bits in it are meaningless).
  Pass it unchanged to FreePotBits.

### Example
```asm
; Read the 2nd (pin 9) and 3rd (pin 5) fire buttons of the joystick port.
        include "exec/types.i"
        include "hardware/custom.i"
        include "lvo/exec_lib.i"
        include "lvo/potgo_lib.i"

POT_RY  equ     $c000                   ; OUTRY+DATRY: port 1 pin 9 output-high
POT_RX  equ     $3000                   ; OUTRX+DATRX: port 1 pin 5 output-high

InitButtons:                            ; out: D0 = 0 ok
        move.l  a6,-(sp)
        move.l  4.w,a6
        lea     potgoname(pc),a1
        jsr     _LVOOpenResource(a6)
        move.l  d0,_PotgoBase
        beq.s   .fail
        move.l  d0,a6
        move.l  #POT_RY!POT_RX,d0
        jsr     _LVOAllocPotBits(a6)
        move.w  d0,potbits
        and.w   #$5000,d0               ; DATRY+DATRX granted?
        cmp.w   #$5000,d0
        bne.s   .free
        move.l  #POT_RY!POT_RX,d0       ; word: drive both pins high
        move.l  d0,d1                   ; mask: only our bits
        jsr     _LVOWritePotgo(a6)
        moveq   #0,d0
        bra.s   .out
.free:
        moveq   #0,d0
        move.w  potbits,d0
        jsr     _LVOFreePotBits(a6)
        clr.w   potbits
.fail:
        moveq   #-1,d0
.out:
        move.l  (sp)+,a6
        rts

; each frame: D0 bit 0 = 2nd fire, bit 1 = 3rd fire (1 = pressed)
ReadButtons:
        moveq   #0,d0
        move.w  $dff000+potinp,d1
        btst    #14,d1
        bne.s   .n2
        moveq   #1,d0
.n2:    btst    #12,d1
        bne.s   .n3
        addq.w  #2,d0
.n3:    rts

potgoname:
        dc.b    "potgo.resource",0
        even

        section bss,bss
_PotgoBase:     ds.l    1
potbits:        ds.w    1
```

### Gotchas
- A partial grant is possible: test the DATxx bits you need, and free the result if it is not enough.
- The allocation is not tied to your task: free it on every exit path, or the bits stay taken until
  reboot.
- After WritePotgo changes a pin, give the line a few hundred microseconds before reading it.
- A request for START fails while anyone holds input bits, and any request fails while someone
  holds START.

**See also:** [WritePotgo](#writepotgo), [FreePotBits](#freepotbits), exec [OpenResource](../exec/libraries-devices-resources.md#openresource)

## WritePotgo
`VOID WritePotgo(ULONG word, ULONG mask)` — LVO -18 (-$12)
Registers: word=D0, mask=D1; no result

Set or clear your allocated POTGO bits, keeping every other user's settings.

- **word** — new values for the bits selected by `mask`.
- **mask** — bits of `word` to apply. Only include bits you were granted by
  [AllocPotBits](#allocpotbits) (and their OUTxx partners you allocated).

The resource saves the high byte (the OUTxx/DATxx settings) and writes the merged value to POTGO,
so later writes by others keep your pin settings. START is not saved: it reaches the hardware only
on a call with START set in `word` and `mask`, and others never repeat it.

### Gotchas
- Setting mask bits you do not own is improper and breaks other users' pins.
- POTGO cannot be read back; POTINP (`$DFF016`) shows pin levels, not the saved output settings.

**See also:** [AllocPotBits](#allocpotbits), [FreePotBits](#freepotbits)

## FreePotBits
`VOID FreePotBits(ULONG bits)` — LVO -12 (-$C)
Registers: bits=D0; no result

Give back POTGO bits obtained with AllocPotBits.

- **bits** — the value AllocPotBits returned (not your original request).

### Gotchas
- Free exactly what was granted, once: freeing bits you do not hold can release another program's allocation.

**See also:** [AllocPotBits](#allocpotbits)
