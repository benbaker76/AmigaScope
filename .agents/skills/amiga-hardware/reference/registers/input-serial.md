# Custom chips: controller ports and serial port

Controller ports: register "0" (JOY0DAT, POT0DAT, CIA-A `CIAB_GAMEPORT0`) is the left
connector, labelled PORT 1 / mouse port; register "1" (JOY1DAT, POT1DAT,
`CIAB_GAMEPORT1`) is the right connector, labelled PORT 2 / joystick port. Pin 6 (fire /
left mouse button) is read from CIA-A PRA; pins 9 and 5 (right / middle button, pot
inputs) from POTGOR. The serial port UART is in Paula; its handshake lines are on CIA-B.

## JOY0DAT
`$DFF00A` · read · Denise · OCS

Mouse counters or joystick switch bits of the left controller port (port 1, mouse).

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | Y7-Y0 | vertical mouse counter (down = increments) |
| 7-0 | X7-X0 | horizontal mouse counter (right = increments) |

Joystick decoding (same for JOY1DAT): right = bit 1, left = bit 9,
down (back) = bit 1 XOR bit 0, up (forward) = bit 9 XOR bit 8.

NDK: `joy0dat` (custom.i); C `custom->joy0dat`.

### Example
```asm
; d0 bits: 0 = right, 1 = left, 2 = down, 3 = up (port 2 joystick)
ReadJoy:
        move.w  joy1dat(a6),d1
        moveq   #0,d0
        btst    #1,d1
        beq.s   .nr
        bset    #0,d0
.nr     btst    #9,d1
        beq.s   .nl
        bset    #1,d0
.nl     move.w  d1,d2
        lsr.w   #1,d2
        eor.w   d1,d2                           ; bit 0 = b1^b0, bit 8 = b9^b8
        btst    #0,d2
        beq.s   .nd
        bset    #2,d0
.nd     btst    #8,d2
        beq.s   .nu
        bset    #3,d0
.nu     rts
```

### Gotchas
- Mouse: subtract the previous reading per axis as signed bytes. Moves of more than 127
  counts between reads are ambiguous, so read at least once per frame.
- The register bits are already decoded: do not invert them (the connector pins are
  active low, the bits are not).
- Fire / left mouse button is CIA-A PRA bit 6 (port 1) or 7 (port 2), right mouse button
  is POTGOR bit 10.

**See also:** JOY1DAT, JOYTEST, [CIAA PRA](cia.md#ciaa-pra), POTGOR

## JOY1DAT
`$DFF00C` · read · Denise · OCS

Mouse counters or joystick switch bits of the right controller port (port 2, joystick).

Bit layout and decoding as JOY0DAT.

NDK: `joy1dat` (custom.i); C `custom->joy1dat`.

**See also:** JOY0DAT, JOYTEST

## JOYTEST
`$DFF036` · write · Denise · OCS

Write the same value into all four mouse counters at once.

| Bit | Meaning |
|---|---|
| 15-10 | Y7-Y2 of both counters |
| 9-8 | not written |
| 7-2 | X7-X2 of both counters |
| 1-0 | not written |

NDK: `joytest` (custom.i); C `custom->joytest`.

### Example
```asm
        move.w  #0,joytest(a6)                  ; zero the mouse counters of both ports
```

### Gotchas
- Bits 9-8 and 1-0 are not written: they reflect the port input pins (joystick switches).

**See also:** JOY0DAT, JOY1DAT

## POT0DAT
`$DFF012` · read · Paula · OCS (ECS: counts depend on scan rate)

Pot (paddle / analogue) counters of the left port: Y on pin 9, X on pin 5.

| Bit | Name | Meaning |
|---|---|---|
| 15-8 | Y7-Y0 | pin 9 counter (POT0Y) |
| 7-0 | X7-X0 | pin 5 counter (POT0X) |

NDK: `pot0dat` (custom.i); C `custom->pot0dat`.

### Gotchas
- Counters are reset and restarted by writing POTGO with START (bit 0); read them one
  frame later. Higher resistance = higher count; about 500k reaches full scale ($FF)
  within one frame at normal scan rates.
- Values jitter: average several readings.
- ECS/AGA programmable scan rates count faster lines, so the values get smaller.

**See also:** POT1DAT, POTGO

## POT1DAT
`$DFF014` · read · Paula · OCS (ECS: counts depend on scan rate)

Pot counters of the right port: Y (pin 9) in bits 15-8, X (pin 5) in bits 7-0.

NDK: `pot1dat` (custom.i); C `custom->pot1dat`.

**See also:** POT0DAT, POTGO

## POTGO
`$DFF034` · write · Paula · OCS · read back via POTGOR `$DFF016`

Direction and output data of the four pot pins (pins 5 and 9 of both ports) and pot start.

| Bit | Name | Meaning |
|---|---|---|
| 15 | OUTRY | 1 = port 2 pin 9 is an output |
| 14 | DATRY | port 2 pin 9 data |
| 13 | OUTRX | 1 = port 2 pin 5 is an output |
| 12 | DATRX | port 2 pin 5 data |
| 11 | OUTLY | 1 = port 1 pin 9 is an output |
| 10 | DATLY | port 1 pin 9 data (right mouse button) |
| 9 | OUTLX | 1 = port 1 pin 5 is an output |
| 8 | DATLX | port 1 pin 5 data (middle mouse button) |
| 7-1 | -- | write 0 |
| 0 | START | discharge the pot capacitors and restart the counters |

NDK: `potgo` (custom.i); no bit constants; C `custom->potgo`.

### Example
```asm
        move.w  #$ff00,potgo(a6)                ; all 4 pins: output high = pull-ups on
        ; ... later
        btst    #10-8,potinp(a6)                ; POTGOR bit 10: 0 = right button down
        beq.s   RightButton
```

### Gotchas
- To read a button, configure the pin as output driven high (OUT and DAT = 1): the button
  shorts it to ground and POTGOR reads 0.
- The pins have large capacitors: allow up to 300 us after a change before reading.
- Pins configured as inputs are connected to the pot counters.
- OS-friendly code must allocate the bits it uses through `potgo.resource`
  (resources/potgo.h) instead of writing POTGO directly.

**See also:** POTGOR, POT0DAT, [JOY0DAT](#joy0dat)

## POTGOR
`$DFF016` · read · Paula · OCS · write via POTGO `$DFF034`; formerly called POTINP

Read the level of the four pot pins (right / middle mouse buttons, second fire buttons).

| Bit | Name | Meaning |
|---|---|---|
| 14 | DATRY | port 2 pin 9 (0 = button down) |
| 12 | DATRX | port 2 pin 5 |
| 10 | DATLY | port 1 pin 9: right mouse button (0 = down) |
| 8 | DATLX | port 1 pin 5: middle mouse button |
| 15, 13, 11, 9 | OUTRY, OUTRX, OUTLY, OUTLX | output enables: test only the DAT bits |
| 7-1 | -- | chip revision ID (reads 0) |
| 0 | START | -- |

NDK: `potinp` (custom.i: the old name; there is no `potgor` label); C `custom->potinp`.

### Example
```asm
        btst    #10-8,potinp(a6)                ; byte test of $DFF016
        beq.s   RightMouseDown
```

### Gotchas
- Use the NDK label `potinp`; `potgor` does not exist in custom.i / custom.h.
- `btst` on memory tests the high byte: bit 10 is `#2`.
- The address `$DFF09A` that some register tables list as "POTINP" is INTENA.

**See also:** POTGO, JOY0DAT

## SERDAT
`$DFF030` · write · Paula · OCS

Serial transmit buffer: data bits plus the stop bit(s) that define the word length.

| Bit | Name | Meaning |
|---|---|---|
| 15-10 | -- | write 0 |
| 9 | S | stop bit (1) for a 9-bit word |
| 8 | D8 / S | 9th data bit, or stop bit for 8 data bits |
| 7-0 | D7-D0 | data bits |

NDK: `serdat` (custom.i); C `custom->serdat`.

### Example
```asm
; send one 8N1 byte in d0 (after checking INTREQR TBE)
        and.w   #$00ff,d0
        or.w    #$0100,d0                       ; stop bit right after D7
        move.w  d0,serdat(a6)
        move.w  #INTF_TBE,intreq(a6)            ; clear TBE: set again when buffer empties
```

### Gotchas
- The word length is given by the position of the stop bit: `$100|byte` = 8 data bits.
- INTREQ TBE (level 1) is set when the buffer moves to the shift register; writing
  SERDAT does not clear it, clear it yourself before waiting for the next TBE.
- Set SERPER before sending.

**See also:** SERDATR, SERPER, [INTREQ](interrupts.md#intreq)

## SERDATR
`$DFF018` · read · Paula · OCS

Serial receive buffer and UART status.

| Bit | Name | Meaning |
|---|---|---|
| 15 | OVRUN | receiver overrun (reset by clearing INTREQ RBF) |
| 14 | RBF | receive buffer full (mirror of INTREQ bit 11) |
| 13 | TBE | transmit buffer empty (mirror of INTREQ bit 0) |
| 12 | TSRE | transmit shift register empty (reset by loading SERDAT) |
| 11 | RXD | live level of the RXD pin |
| 10 | -- | unused |
| 9 | STP | stop bit |
| 8 | STP / DB8 | stop bit, or data bit 8 if SERPER LONG is set |
| 7-0 | DB7-DB0 | received data |

NDK: `serdatr` (custom.i); no bit constants; C `custom->serdatr`.

### Example
```asm
.wait   btst    #14-8,serdatr(a6)               ; RBF
        beq.s   .wait
        move.w  serdatr(a6),d0                  ; d0.b = received byte
        move.w  #INTF_RBF,intreq(a6)            ; acknowledge, also clears OVRUN
```

### Gotchas
- RBF and TBE are only mirrors: acknowledge them in INTREQ.
- Read the data before clearing RBF, or the next byte can overrun it.

**See also:** SERDAT, SERPER, [INTREQR](interrupts.md#intreqr)

## SERPER
`$DFF032` · write · Paula · OCS

Serial baud rate divisor and 8/9-bit receive length.

| Bit | Name | Meaning |
|---|---|---|
| 15 | LONG | 1 = receive 9-bit words |
| 14-0 | RATE | N: one bit every N+1 colour clocks |

`SERPER = clock / baud - 1` with clock 3579545 (NTSC) or 3546895 (PAL).

NDK: `serper` (custom.i); C `custom->serper`.

### Example
```asm
        move.w  #3546895/9600-1,serper(a6)      ; 9600 baud on PAL (368); NTSC: 371
```

### Gotchas
- The divisor depends on PAL/NTSC crystal: compute it for the machine you run on.
- Very high rates (above roughly 150000 bps) cannot be serviced with interrupts.

**See also:** SERDAT, SERDATR, [CIAB PRA](cia.md#ciab-pra)
