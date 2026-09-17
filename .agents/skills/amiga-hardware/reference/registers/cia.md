# 8520 CIA registers (CIA-A and CIA-B)

Two MOS 8520 Complex Interface Adapters. Each has two 8-bit I/O ports, two 16-bit
timers, a 24-bit event counter (TOD), an 8-bit serial shift register and an interrupt
control register. Registers are bytes spaced `$100` apart: register n is at base +
n*`$100`. Always use byte access.

| | CIA-A | CIA-B |
|---|---|---|
| Base | `$BFE001` (odd: CPU data bits 7-0) | `$BFD000` (even: CPU data bits 15-8) |
| Interrupt | INT2 -> INTREQ PORTS, level 2 | INT6 -> INTREQ EXTER, level 6 |
| Port A | fire buttons, disk status, LED, overlay | serial handshake, printer status |
| Port B | parallel port data | floppy control |
| SP / CNT | keyboard data / clock | printer BUSY / POUT |
| FLAG | parallel /ACK | disk /INDEX |
| TOD counts | 50/60 Hz ticks | horizontal sync pulses |

| n | Register | CIA-A | CIA-B | NDK offset (cia.i) |
|---|---|---|---|---|
| 0 | PRA | `$BFE001` | `$BFD000` | `ciapra` |
| 1 | PRB | `$BFE101` | `$BFD100` | `ciaprb` |
| 2 | DDRA | `$BFE201` | `$BFD200` | `ciaddra` |
| 3 | DDRB | `$BFE301` | `$BFD300` | `ciaddrb` |
| 4 | TALO | `$BFE401` | `$BFD400` | `ciatalo` |
| 5 | TAHI | `$BFE501` | `$BFD500` | `ciatahi` |
| 6 | TBLO | `$BFE601` | `$BFD600` | `ciatblo` |
| 7 | TBHI | `$BFE701` | `$BFD700` | `ciatbhi` |
| 8 | TODLOW | `$BFE801` | `$BFD800` | `ciatodlow` |
| 9 | TODMID | `$BFE901` | `$BFD900` | `ciatodmid` |
| A | TODHI | `$BFEA01` | `$BFDA00` | `ciatodhi` |
| B | -- | `$BFEB01` | `$BFDB00` | (unused) |
| C | SDR | `$BFEC01` | `$BFDC00` | `ciasdr` |
| D | ICR | `$BFED01` | `$BFDD00` | `ciaicr` |
| E | CRA | `$BFEE01` | `$BFDE00` | `ciacra` |
| F | CRB | `$BFEF01` | `$BFDF00` | `ciacrb` |

NDK asm: offsets above plus `XREF _ciaa` / `_ciab` (amiga.lib) or the absolute bases;
C: `struct CIA` fields `ciapra`...`ciacrb`, `extern struct CIA ciaa, ciab;`.
Timers count E-clock pulses: 709379 Hz PAL, 715909 Hz NTSC (1.41 / 1.40 us per count).

In cia.i the pin constants are `CIAB_xxx` (bit number) and `CIAF_xxx` (mask): the `B`
means "bit", not CIA-B. `CIAB_LED` is a CIA-A bit.

## CIAA PRA
`$BFE001` · read/write (direction per DDRA) · 8520 CIA-A · OCS · normal DDRA = `$03`

Fire buttons and floppy status inputs; power LED and ROM overlay outputs.

| Bit | Signal | NDK | Dir | Meaning |
|---|---|---|---|---|
| 7 | /FIR1 | `CIAB_GAMEPORT1` | in | port 2 (JOY1) fire, 0 = pressed |
| 6 | /FIR0 | `CIAB_GAMEPORT0` | in | port 1 (JOY0) fire / left mouse button, 0 = pressed |
| 5 | /RDY | `CIAB_DSKRDY` | in | selected drive ready (motor up to speed) |
| 4 | /TK0 | `CIAB_DSKTRACK0` | in | head on track 0 |
| 3 | /WPRO | `CIAB_DSKPROT` | in | disk write protected |
| 2 | /CHNG | `CIAB_DSKCHANGE` | in | 0 = disk removed; stays 0 until a disk is in AND a step pulse is sent |
| 1 | /LED | `CIAB_LED` | out | power LED, 0 = bright |
| 0 | OVL | `CIAB_OVERLAY` | out | ROM overlay at address 0 (cleared after boot) |

Masks: `CIAF_GAMEPORT1` ... `CIAF_OVERLAY`.

### Example
```asm
        include "hardware/cia.i"
        btst    #CIAB_GAMEPORT0,$bfe001         ; left mouse / port 1 fire
        beq.s   LeftPressed                     ; active low
        bchg    #CIAB_LED,$bfe001               ; toggle power LED
```

### Gotchas
- All inputs are active low.
- Never set OVL (bit 0): the ROM reappears over chip RAM at address 0 and the machine
  crashes.
- Change single bits with `bset` / `bclr` / `bchg` so the LED and OVL bits survive.
- /RDY is only meaningful while the drive motor is on.
- On most models the /LED line also switches the audio low-pass filter (unverified).

**See also:** DDRA, CIAB PRB, [JOY0DAT](input-serial.md#joy0dat), [DSKLEN](disk.md#dsklen)

## CIAA PRB
`$BFE101` · read/write (direction per DDRB) · 8520 CIA-A · OCS

Centronics parallel port data lines D7-D0.

| Bit | Signal | Meaning |
|---|---|---|
| 7-0 | D7-D0 | parallel data (direction set by CIA-A DDRB) |

The CIA-A PC output (pulses after each port B access) is the printer strobe (/DRDY);
the printer's /ACK arrives on CIA-A FLAG (ICR bit 4). Printer status lines are on
CIA-B PRA.

NDK: `ciaprb` (cia.i); no pin constants ("parallel port").

### Gotchas
- OS-friendly code uses parallel.device / printer.device, not this register.

**See also:** DDRB, CIAB PRA, ICR

## CIAB PRA
`$BFD000` · read/write (direction per DDRA) · 8520 CIA-B · OCS

Serial port handshake lines and printer status inputs.

| Bit | Signal | NDK | Dir | Meaning |
|---|---|---|---|---|
| 7 | /DTR | `CIAB_COMDTR` | out | serial Data Terminal Ready |
| 6 | /RTS | `CIAB_COMRTS` | out | serial Request To Send |
| 5 | /CD | `CIAB_COMCD` | in | serial Carrier Detect |
| 4 | /CTS | `CIAB_COMCTS` | in | serial Clear To Send |
| 3 | /DSR | `CIAB_COMDSR` | in | serial Data Set Ready |
| 2 | SEL | `CIAB_PRTRSEL` | in | printer SELECT |
| 1 | POUT | `CIAB_PRTRPOUT` | in | printer paper out |
| 0 | BUSY | `CIAB_PRTRBUSY` | in | printer busy |

Masks: `CIAF_COMDTR` ... `CIAF_PRTRBUSY`.

### Gotchas
- The serial handshake lines are active low; the UART data itself is in Paula (SERDAT).
- CIA-B SP and CNT pins are also wired to BUSY and POUT.

**See also:** DDRA, [SERPER](input-serial.md#serper), CIAA PRB

## CIAB PRB
`$BFD100` · read/write (all outputs, DDRB = `$FF`) · 8520 CIA-B · OCS

Floppy drive control: motor, drive selects, side, step direction and step pulse.

| Bit | Signal | NDK | Meaning |
|---|---|---|---|
| 7 | /MTR | `CIAB_DSKMOTOR` | motor on (0), latched by each drive when it is selected |
| 6 | /SEL3 | `CIAB_DSKSEL3` | select drive 3 (0 = selected) |
| 5 | /SEL2 | `CIAB_DSKSEL2` | select drive 2 |
| 4 | /SEL1 | `CIAB_DSKSEL1` | select drive 1 (first external) |
| 3 | /SEL0 | `CIAB_DSKSEL0` | select drive 0 (internal DF0:) |
| 2 | /SIDE | `CIAB_DSKSIDE` | head select: 0 = upper head |
| 1 | DIR | `CIAB_DSKDIREC` | step direction: 0 = inwards (towards the spindle, higher tracks) |
| 0 | /STEP | `CIAB_DSKSTEP` | step pulse: high, briefly low, high |

Masks: `CIAF_DSKMOTOR` ... `CIAF_DSKSTEP`.

### Example
```asm
CIABPRB equ     $bfd100
        ; DF0: motor on
        bset    #CIAB_DSKSEL0,CIABPRB           ; make sure DF0: is deselected
        bclr    #CIAB_DSKMOTOR,CIABPRB          ; motor line active...
        bclr    #CIAB_DSKSEL0,CIABPRB           ; ...latched when DF0: is selected
        ; wait for CIA-A /RDY or 500 ms
        ; step one track inwards
        bclr    #CIAB_DSKDIREC,CIABPRB          ; direction first, separate write
        bclr    #CIAB_DSKSTEP,CIABPRB
        bset    #CIAB_DSKSTEP,CIABPRB           ; pulse
        ; wait at least 3 ms before the next step
```

### Gotchas
- Set /MTR before selecting: each drive latches the motor bit when its select line goes
  low and keeps that state while deselected.
- After motor on, wait 500 ms or for CIA-A /RDY.
- DIR must be set in a separate write before the step pulse. Allow 3 ms per step, 18 ms
  after reversing direction and 15 ms settle before reading or writing.
- Never step outwards while CIA-A /TK0 is low (track 0): some drives damage alignment.
- /SIDE must be stable 100 us before writing, and wait 1.3 ms after writing before changing it.
- Busy loops are not acceptable delays: use a CIA timer or the beam counter.
- The OS (trackdisk.device) owns the drives: bare-metal only, or after taking over.

**See also:** CIAA PRA, TALO, TAHI, [DSKLEN](disk.md#dsklen)

## DDRA
CIA-A `$BFE201` · CIA-B `$BFD200` · read/write · 8520 · OCS

Data direction for port A: 1 = output, 0 = input, one bit per PRA bit.

| CIA | Normal value | Why |
|---|---|---|
| CIA-A | `$03` | LED and OVL outputs, fire buttons and disk status inputs |
| CIA-B | bits 7-6 out, 5-0 in | DTR/RTS outputs; CD, CTS, DSR, SEL, POUT, BUSY inputs |

NDK: `ciaddra` (cia.i); C `ciaa.ciaddra`, `ciab.ciaddra`.

### Gotchas
- Reading PR always returns the pin levels, whatever the direction.
- Fire buttons can be made outputs (CIA-A DDRA bits 7-6) but leave the other bits alone.
- The HRM CIA-B table says "set to $FF", which contradicts its own pin list; do not write
  `$FF` blindly (keep the OS value).

**See also:** CIAA PRA, CIAB PRA, DDRB

## DDRB
CIA-A `$BFE301` · CIA-B `$BFD300` · read/write · 8520 · OCS

Data direction for port B: 1 = output, 0 = input.

| CIA | Normal value |
|---|---|
| CIA-A | parallel data: in or out as the transfer requires |
| CIA-B | `$FF` (all floppy control lines are outputs) |

NDK: `ciaddrb` (cia.i); C `ciaa.ciaddrb`, `ciab.ciaddrb`.

### Gotchas
- CRA/CRB PBON overrides DDRB for PB6 (timer A) / PB7 (timer B).

**See also:** CIAA PRB, CIAB PRB, CRA

## TALO, TAHI
CIA-A `$BFE401` / `$BFE501` · CIA-B `$BFD400` / `$BFD500` · read = counter, write = latch · 8520 · OCS

Timer A: 16-bit down counter clocked by the E clock (or CNT); underflow sets ICR TA.

Writes go to the latch (prescaler); reads return the live counter.
Count for a delay: `ticks = microseconds * 709379 / 1000000` (PAL; NTSC 715909), e.g.
1/50 s PAL = 14188.

NDK: `ciatalo`, `ciatahi` (cia.i); C `ciaa.ciatalo` etc.

### Example
```asm
; busy-wait d0.w timer ticks on CIA-B timer A (bare metal: masks CIA-B interrupts)
        include "hardware/cia.i"
        lea     $bfd000,a0
        move.b  #$7f,ciaicr(a0)                 ; bit 7 = 0: disable all CIA-B sources
        move.b  ciacra(a0),d1
        and.b   #%11000000,d1                   ; keep bits 7-6, stop the timer
        or.b    #CIACRAF_RUNMODE,d1             ; one-shot
        move.b  d1,ciacra(a0)
        move.b  d0,ciatalo(a0)                  ; low byte first
        lsr.w   #8,d0
        move.b  d0,ciatahi(a0)                  ; high byte: load + start (one-shot)
.wait   btst    #CIAICRB_TA,ciaicr(a0)          ; flag is set even while masked
        beq.s   .wait                           ; (the read clears all ICR flags)
```

### Gotchas
- Write the low byte first, then the high byte.
- One-shot mode (RUNMODE = 1): writing TAHI loads the latch into the counter and starts
  it, whatever START says. Stopped timer: writing TAHI loads the counter. Running
  continuous timer: writing TAHI changes only the latch (used at the next underflow).
- Reading ICR to poll the timer also clears every other pending CIA flag.
- With the OS running, timers are shared resources: allocate one with `AddICRVector` on
  `ciaa.resource` / `ciab.resource` (LVOs in lvo/cia_lib.i) before touching it.
- CIA-A timer A is the baud generator when the CIA-A serial port (keyboard line) outputs.

**See also:** TBLO, TBHI, CRA, ICR

## TBLO, TBHI
CIA-A `$BFE601` / `$BFE701` · CIA-B `$BFD600` / `$BFD700` · read = counter, write = latch · 8520 · OCS

Timer B: 16-bit down counter; can also count timer A underflows for long delays.

Same load rules as TALO, TAHI; controlled by CRB. Underflow sets ICR TB; PB7 output with
CRB PBON.

NDK: `ciatblo`, `ciatbhi` (cia.i); C `ciaa.ciatblo` etc.

### Gotchas
- CRB INMODE `%10` (`CIACRBF_IN_TA`) chains timer B to timer A underflows: a 32-bit
  timer.

**See also:** TALO, TAHI, CRB

## TODLOW, TODMID, TODHI
CIA-A `$BFE801` / `$BFE901` / `$BFEA01` · CIA-B `$BFD800` / `$BFD900` / `$BFDA00` · read/write · 8520 · OCS

24-bit event counter (TOD) and alarm: CIA-A counts 50/60 Hz ticks, CIA-B counts HSYNC.

| Register | Bits |
|---|---|
| TODLOW | counter bits 7-0 |
| TODMID | counter bits 15-8 |
| TODHI | counter bits 23-16 |

With CRB ALARM = 1, writes set the alarm instead of the counter; reads always return the
counter. A match raises ICR ALRM.

NDK: `ciatodlow`, `ciatodmid`, `ciatodhi` (cia.i); C `ciaa.ciatodlow` etc.

### Example
```asm
; read the CIA-B line counter into d0
        lea     $bfd000,a0
        moveq   #0,d0
        move.b  ciatodhi(a0),d0                 ; MSB first: latches all three
        lsl.l   #8,d0
        move.b  ciatodmid(a0),d0
        lsl.l   #8,d0
        move.b  ciatodlow(a0),d0                ; LSB last: releases the latch
```

### Gotchas
- Read HI, MID, LOW in that order: reading TODHI freezes the outputs until TODLOW is read
  (the counter keeps counting). Reading only TODHI leaves it latched.
- Any write stops the counter; it restarts on the write to TODLOW. Write HI, MID, LOW.

**See also:** CRB, ICR

## SDR
CIA-A `$BFEC01` · CIA-B `$BFDC00` · read/write · 8520 · OCS

8-bit synchronous serial shift register: CIA-A receives the keyboard; CIA-B's is unused.

| Bit | Meaning |
|---|---|
| 7-0 | S7-S0, shifted MSB first |

Input mode (CRA SPMODE = 0): 8 bits clocked by CNT are copied here and raise ICR SP.
Output mode: timer A generates the clock; a write to SDR starts transmission.

NDK: `ciasdr` (cia.i); C `ciaa.ciasdr`.

### Example
```asm
; CIA-A SP interrupt: fetch a raw keycode
        move.b  $bfec01,d0                      ; CIA-A SDR
        not.b   d0                              ; KDAT is active low
        ror.b   #1,d0                           ; keyboard sends bit 7 last
        ; d0 = raw keycode, bit 7 set = key released
        ; handshake: pulse KDAT low for at least 85 us
        bset    #CIACRAB_SPMODE,$bfee01         ; SP as output (drives KDAT low; unverified)
        ; ... wait >= 85 us (e.g. 2 raster lines via VHPOSR, or a CIA timer)
        bclr    #CIACRAB_SPMODE,$bfee01         ; back to input
```

### Gotchas
- The keyboard sends bits 6-0 then 7, inverted: `not` then `ror #1` gives the keycode.
- The keyboard waits for the handshake before the next key (it buffers 10 keys). The
  pulse must be at least 85 us for all keyboard models: do not use a CPU busy loop,
  which is far too short on fast CPUs.
- Read ICR (SP bit) before clearing INTREQ PORTS in the level 2 handler.

**See also:** ICR, CRA, [INTREQ](interrupts.md#intreq)

## ICR
CIA-A `$BFED01` · CIA-B `$BFDD00` · read = flags (clears), write = mask (set/clear) · 8520 · OCS

Interrupt flags (read, cleared by the read) and interrupt enable mask (set/clear write).

| Bit | Read | Write | NDK |
|---|---|---|---|
| 7 | IR: an enabled source fired (IRQ active) | SET/CLR: 1 = enable, 0 = disable the 1-bits | `CIAICRB_IR` / `CIAICRB_SETCLR` |
| 6-5 | 0 | unused, 0 | |
| 4 | FLG: negative edge on FLAG | mask FLG | `CIAICRB_FLG` |
| 3 | SP: serial byte received / sent | mask SP | `CIAICRB_SP` |
| 2 | ALRM: TOD alarm match | mask ALRM | `CIAICRB_ALRM` |
| 1 | TB: timer B underflow | mask TB | `CIAICRB_TB` |
| 0 | TA: timer A underflow | mask TA | `CIAICRB_TA` |

Sources: CIA-A FLG = parallel /ACK, SP = keyboard, ALRM = 50/60 Hz TOD. CIA-B FLG =
disk /INDEX, ALRM = HSYNC TOD. Masks: `CIAICRF_TA` ... `CIAICRF_SETCLR`.

NDK: `ciaicr` (cia.i); C `ciaa.ciaicr`.

### Example
```asm
        move.b  #CIAICRF_SETCLR!CIAICRF_SP,$bfed01  ; enable CIA-A keyboard interrupt
        move.b  #$7f,$bfed01                        ; disable every CIA-A source

; level 2 handler core
        move.b  $bfed01,d0                      ; read ONCE: clears all flags
        btst    #CIAICRB_SP,d0
        beq.s   .notkey
        ; ... read SDR, handshake
.notkey move.w  #INTF_PORTS,$dff09c             ; then acknowledge in Paula
```

### Gotchas
- Reading clears every flag: read once, keep the byte, service every bit set in it.
- Masked sources still set their flag bit, but not IR and not the interrupt line.
- The CIA interrupt line stays active until ICR is read: acknowledge INTREQ PORTS
  (CIA-A) / EXTER (CIA-B) only after reading ICR.
- With the OS running, use `AddICRVector` / `AbleICR` / `SetICR` on
  `ciaa.resource` / `ciab.resource` instead of the hardware.

**See also:** CRA, CRB, [INTREQ](interrupts.md#intreq), [INTENA](interrupts.md#intena)

## CRA
CIA-A `$BFEE01` · CIA-B `$BFDE00` · read/write · 8520 · OCS

Control register A: timer A mode and the serial port direction.

| Bit | Name | Meaning | NDK |
|---|---|---|---|
| 7 | -- | unused on the 8520 (NDK name TODIN) | `CIACRAB_TODIN` |
| 6 | SPMODE | 1 = serial port output (timer A = shift clock), 0 = input (CNT clock) | `CIACRAB_SPMODE` |
| 5 | INMODE | 1 = timer A counts CNT rising edges, 0 = E-clock pulses | `CIACRAB_INMODE` |
| 4 | LOAD | strobe: 1 = copy latch into counter now (reads 0) | `CIACRAB_LOAD` |
| 3 | RUNMODE | 1 = one-shot, 0 = continuous | `CIACRAB_RUNMODE` |
| 2 | OUTMODE | 1 = toggle PB6 on underflow, 0 = one-cycle pulse | `CIACRAB_OUTMODE` |
| 1 | PBON | 1 = timer A output on PB6 | `CIACRAB_PBON` |
| 0 | START | 1 = run, 0 = stop; cleared automatically at one-shot underflow | `CIACRAB_START` |

Masks: `CIACRAF_START` ... `CIACRAF_TODIN`.

NDK: `ciacra` (cia.i); C `ciaa.ciacra`.

### Gotchas
- Read-modify-write: CIA-A bit 6 belongs to the keyboard. Unused bits read 0.
- LOAD never stays set; writing 0 to it does nothing.

**See also:** TALO, TAHI, SDR, CRB

## CRB
CIA-A `$BFEF01` · CIA-B `$BFDF00` · read/write · 8520 · OCS

Control register B: timer B mode, timer B input and TOD alarm write select.

| Bit | Name | Meaning | NDK |
|---|---|---|---|
| 7 | ALARM | 1 = TOD writes set the alarm, 0 = TOD writes set the clock | `CIACRBB_ALARM` |
| 6-5 | INMODE1-0 | 00 E clock, 01 CNT edges, 10 timer A underflows, 11 TA underflows while CNT high | `CIACRBB_INMODE1`, `CIACRBB_INMODE0` |
| 4 | LOAD | strobe: force latch into counter | `CIACRBB_LOAD` |
| 3 | RUNMODE | 1 = one-shot, 0 = continuous | `CIACRBB_RUNMODE` |
| 2 | OUTMODE | 1 = toggle PB7, 0 = pulse | `CIACRBB_OUTMODE` |
| 1 | PBON | 1 = timer B output on PB7 | `CIACRBB_PBON` |
| 0 | START | 1 = run; cleared at one-shot underflow | `CIACRBB_START` |

Input mode values: `CIACRBF_IN_PHI2` (0), `CIACRBF_IN_CNT`, `CIACRBF_IN_TA`,
`CIACRBF_IN_CNT_TA`; masks `CIACRBF_START` ... `CIACRBF_ALARM`.

NDK: `ciacrb` (cia.i); C `ciaa.ciacrb`.

### Gotchas
- Clear ALARM again after setting an alarm, or later TOD writes keep changing the alarm.

**See also:** TBLO, TBHI, TODLOW, TODMID, TODHI, CRA
