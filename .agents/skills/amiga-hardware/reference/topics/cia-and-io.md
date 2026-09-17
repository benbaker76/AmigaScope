# CIAs and I/O: timers, keyboard, joystick, mouse, serial, parallel, floppy lines

How to use the two 8520 CIAs and Paula's port/serial registers from bare-metal code.

Registers: [CIAA PRA](../registers/cia.md#ciaa-pra), [CIAA PRB](../registers/cia.md#ciaa-prb),
[CIAB PRA](../registers/cia.md#ciab-pra), [CIAB PRB](../registers/cia.md#ciab-prb),
[DDRA](../registers/cia.md#ddra), [DDRB](../registers/cia.md#ddrb),
[TALO, TAHI](../registers/cia.md#talo-tahi), [TBLO, TBHI](../registers/cia.md#tblo-tbhi),
[TODLOW, TODMID, TODHI](../registers/cia.md#todlow-todmid-todhi), [SDR](../registers/cia.md#sdr),
[ICR](../registers/cia.md#icr), [CRA](../registers/cia.md#cra), [CRB](../registers/cia.md#crb),
[JOY0DAT](../registers/input-serial.md#joy0dat), [JOY1DAT](../registers/input-serial.md#joy1dat),
[JOYTEST](../registers/input-serial.md#joytest), [POT0DAT](../registers/input-serial.md#pot0dat),
[POT1DAT](../registers/input-serial.md#pot1dat), [POTGO](../registers/input-serial.md#potgo),
[POTGOR](../registers/input-serial.md#potgor), [SERDAT](../registers/input-serial.md#serdat),
[SERDATR](../registers/input-serial.md#serdatr), [SERPER](../registers/input-serial.md#serper),
disk registers in [disk.md](../registers/disk.md). NDK: `hardware/cia.i`.

## The two 8520s

| | CIA-A | CIA-B |
|---|---|---|
| Base (`ciapra` = 0) | `$BFE001` (odd addresses) | `$BFD000` (even addresses) |
| Interrupt | INT2 -> INTREQ PORTS, level 2 | INT6 -> INTREQ EXTER, level 6 |
| Serial register SP/CNT | keyboard data / clock | unassigned |
| FLAG input | parallel ACK* | disk INDEX* |
| TOD counts | 50/60 Hz ticks (vertical sync or power-line tick, model dependent) | horizontal sync (one per line) |

- Every register is a **byte**; use byte access only. `lea $bfe001,a0` then `ciaicr(a0)` etc.
- Timers count the E clock: **709,379 Hz PAL, 715,909 Hz NTSC** (1.4097 / 1.3968 us per
  tick). `ticks = seconds * E`. ExecBase `ex_EClockFrequency` holds the value.
- The OS uses the CIAs (keyboard, timer.device, trackdisk, serial/parallel lines). With the OS
  alive, go through `cia.resource` (AddICRVector, RemICRVector, AbleICR, SetICR); never assume
  the register contents it left behind.

## Port bit assignments

**CIA-A PRA `$BFE001`** (DDRA normally `$03`: bits 0-1 outputs):

| Bit | NDK `CIAB_` | Signal |
|---|---|---|
| 7 | `GAMEPORT1` | port 1 (joystick port) fire button, 0 = pressed |
| 6 | `GAMEPORT0` | port 0 (mouse port) fire / left mouse button, 0 = pressed |
| 5 | `DSKRDY` | disk ready*, 0 = ready |
| 4 | `DSKTRACK0` | head on track 0*, 0 = yes |
| 3 | `DSKPROT` | write protected*, 0 = protected |
| 2 | `DSKCHANGE` | disk change*, 0 = removed (until a disk is in and a step pulse is sent) |
| 1 | `LED` | power LED / audio filter, 0 = bright/filter on (output) |
| 0 | `OVERLAY` | ROM overlay (output) -- do not change |

**CIA-A PRB `$BFE101`**: parallel port data D0-D7 (direction in DDRB).

**CIA-B PRA `$BFD000`**:

| Bit | NDK `CIAB_` | Signal |
|---|---|---|
| 7 | `COMDTR` | serial DTR* (output) |
| 6 | `COMRTS` | serial RTS* (output) |
| 5 | `COMCD` | serial carrier detect* |
| 4 | `COMCTS` | serial CTS* |
| 3 | `COMDSR` | serial DSR* |
| 2 | `PRTRSEL` | printer SELECT |
| 1 | `PRTRPOUT` | printer paper out |
| 0 | `PRTRBUSY` | printer busy |

**CIA-B PRB `$BFD100`** (all outputs, DDRB `$FF`) -- floppy control, all active low except DIR:

| Bit | NDK `CIAB_` | Signal |
|---|---|---|
| 7 | `DSKMOTOR` | MTR*: motor state, latched by a drive when its select goes low |
| 6-3 | `DSKSEL3`-`DSKSEL0` | select drive 3-0 (DF0 = bit 3) |
| 2 | `DSKSIDE` | SIDE*: 0 = upper head (side 1), 1 = lower head (side 0) |
| 1 | `DSKDIREC` | DIR: 0 = step inwards (towards higher tracks), 1 = outwards |
| 0 | `DSKSTEP` | STEP*: pulse low then high to step one track |

## Timers

Each CIA has two 16-bit down-counters. Writes go to a latch; reads return the live counter.

| CRA/CRB bit | NDK | Meaning |
|---|---|---|
| 0 | `START` | 1 = running (cleared automatically at underflow in one-shot mode) |
| 1 | `PBON` | 1 = output on PB6 (timer A) / PB7 (timer B) |
| 2 | `OUTMODE` | 1 = toggle, 0 = pulse |
| 3 | `RUNMODE` | 1 = one-shot, 0 = continuous |
| 4 | `LOAD` | write 1 = force latch into counter (strobe, reads 0) |
| 5 | CRA `INMODE` | 0 = count E clock, 1 = count CNT edges |
| 6 | CRA `SPMODE` | serial port: 0 = input, 1 = output |
| 6-5 | CRB `INMODE1/0` | 00 E clock, 01 CNT, 10 timer A underflows, 11 TA underflows while CNT high |
| 7 | CRB `ALARM` | 1 = TOD writes set the alarm |

- **Write order:** low byte, then high byte. Stopped timer: writing the high byte loads the
  latch into the counter; in one-shot mode it also **starts** the timer.
- Underflow sets ICR bit 0 (TA) / 1 (TB) whether or not the interrupt is enabled.
- Continuous mode reloads the latch automatically at each underflow.

```asm
        include "hardware/cia.i"
; Busy-wait d0.w E-clock ticks with CIA-B timer A (machine taken over).
; PAL: 20 ms = 14188 ticks, 3 ms = 2128 ticks.
CiaDelay:
        lea     $bfd000,a1
        move.b  ciacra(a1),d1
        and.b   #%11000000,d1                   ; keep bits 7-6, stop, continuous, E clock
        or.b    #CIACRAF_RUNMODE,d1             ; one-shot
        move.b  d1,ciacra(a1)
        move.b  #CIAICRF_TA,ciaicr(a1)          ; bit 7 = 0: disable TA interrupt
        tst.b   ciaicr(a1)                      ; clear pending flags
        move.b  d0,ciatalo(a1)
        lsr.w   #8,d0
        move.b  d0,ciatahi(a1)                  ; loads and starts (one-shot)
.wait   btst    #CIAICRB_TA,ciaicr(a1)          ; NOTE: this read clears other flags too
        beq.s   .wait
        rts
```

A periodic timer interrupt: set the latch, `CRA = START` (continuous), enable with
`move.b #CIAICRF_SETCLR!CIAICRF_TA,ciaicr(a1)` and handle it in the level-6 (CIA-B) or level-2
(CIA-A) handler, reading ICR once per interrupt.

## TOD counters

24-bit binary event counters: CIA-A counts a 50/60 Hz tick (ExecBase `PowerSupplyFrequency`
and `VBlankFrequency` tell you the rate), CIA-B counts horizontal sync pulses. Reading TODHI
latches all three bytes until TODLOW is read; writing stops the counter until TODLOW is
written. With CRB bit 7 set, writes go to the alarm (ICR bit 2).

```asm
        lea     $bfe001,a0
        moveq   #0,d0
        move.b  ciatodhi(a0),d0         ; latch
        lsl.l   #8,d0
        move.b  ciatodmid(a0),d0
        lsl.l   #8,d0
        move.b  ciatodlow(a0),d0        ; unlatch; d0 = frame counter
```

## Keyboard

The keyboard sends 8 bits on KDAT (CIA-A SP pin) clocked by KCLK (CNT); the CIA serial
register collects them and raises ICR bit 3 (SP) -> PORTS interrupt.

- **Bit order and polarity:** the keyboard rotates the byte left one bit (sends 6-5-4-3-2-1-0-7)
  and the line is active low. Decode: `not.b d0` then `ror.b #1,d0`. Bit 7 of the result
  is 1 for key up, bits 6-0 are the raw key code.
- **Handshake:** after reading SDR, pull KDAT low for **at least 85 us**, then release it. The
  usual way is to switch the CIA-A serial port to output (CRA bit 6 SPMODE = 1) and back. Without
  the handshake the keyboard sends nothing more (and eventually resynchronises, generating
  garbage key-ups).
- The keyboard buffers up to 10 codes. Caps Lock only sends on press; its up/down bit tells the
  LED state.

| Code | Key | Code | Key |
|---|---|---|---|
| `$00` | `` ` `` | `$40` | Space |
| `$01`-`$0A` | 1 .. 0 | `$41` | Backspace |
| `$0B` / `$0C` / `$0D` | - = \ | `$42` | Tab |
| `$10`-`$19` | Q W E R T Y U I O P | `$43` | keypad Enter |
| `$1A` / `$1B` | [ ] | `$44` | Return |
| `$20`-`$28` | A S D F G H J K L | `$45` | Esc |
| `$29` / `$2A` | ; ' | `$46` | Del |
| `$31`-`$37` | Z X C V B N M | `$4A` | keypad - |
| `$38` / `$39` / `$3A` | , . / | `$4C`/`$4D`/`$4E`/`$4F` | cursor up/down/right/left |
| `$0F`,`$1D`,`$1E`,`$1F` | keypad 0,1,2,3 | `$50`-`$59` | F1-F10 |
| `$2D`,`$2E`,`$2F` | keypad 4,5,6 | `$5A`-`$5E` | keypad ( ) / * + |
| `$3D`,`$3E`,`$3F` | keypad 7,8,9 | `$5F` | Help |
| `$3C` | keypad . | `$60`/`$61` | left/right Shift |
| `$2B`, `$30` | extra keys on international keyboards | `$62` / `$63` | Caps Lock / Ctrl |
| | | `$64`/`$65`, `$66`/`$67` | left/right Alt, left/right Amiga |

Raw codes are positions, not characters (layouts differ by country). Special codes (no up/down
bit): `$78` reset warning (Ctrl-Amiga-Amiga), `$F9` last code bad (next is a resend), `$FA`
keyboard buffer overflow, `$FC` self-test failed, `$FD` start / `$FE` end of the power-up key
stream. Filter them out.

```asm
        include "hardware/custom.i"
        include "hardware/intbits.i"
        include "hardware/cia.i"

; Level-2 handler (machine taken over). Stores the last raw code in 'lastkey'.
Level2:
        movem.l d0-d2/a0-a1,-(sp)
        lea     $dff000,a0
        move.w  intreqr(a0),d0
        btst    #INTB_PORTS,d0
        beq.s   .out
        lea     $bfe001,a1
        move.b  ciaicr(a1),d0           ; read once: clears all CIA-A flags
        btst    #CIAICRB_SP,d0
        beq.s   .ack
        move.b  ciasdr(a1),d1           ; raw byte
        or.b    #CIACRAF_SPMODE,ciacra(a1)      ; KDAT low: start handshake
        not.b   d1
        ror.b   #1,d1                   ; d1 = key code, bit 7 = released
        move.b  d1,lastkey
        moveq   #3-1,d2                 ; wait 3 line changes: >= 2 full lines (~128 us)
.hs     move.b  vhposr(a0),d1
.same   cmp.b   vhposr(a0),d1
        beq.s   .same
        dbf     d2,.hs
        and.b   #$bf,ciacra(a1)         ; clear SPMODE: release KDAT
        ; other CIA-A flags from this interrupt are still in d0 (TA, TB, ALRM, FLG)
.ack    move.w  #INTF_PORTS,intreq(a0)
        move.w  #INTF_PORTS,intreq(a0)
.out    movem.l (sp)+,d0-d2/a0-a1
        rte

        section vars,bss
lastkey: ds.b   1
        even
```

Enable it with `move.b #CIAICRF_SETCLR!CIAICRF_SP,$bfed01` and
`move.w #INTF_SETCLR!INTF_INTEN!INTF_PORTS,intena(a6)` after installing the vector at
`VBR+$68`. The ICR read clears every CIA-A flag; if you also use CIA-A timers, test their
bits in the same `d0`.

**Reset warning** (not on every keyboard, e.g. not the A500): two `$78` codes arrive.
Handshake the first normally. After the second, drive KDAT low within 250 ms to get up to 10 s
of clean-up time; the keyboard resets the machine when KDAT is released (or after 10 s).
Without that response it resets immediately. Games usually ignore it.

## Joystick

Digital joysticks use the mouse counter inputs. In JOYxDAT (port 0 = mouse port = `joy0dat`,
port 1 = joystick port = `joy1dat`):

| Direction | Test (1 = pressed) |
|---|---|
| right | bit 1 |
| left | bit 9 |
| down (back) | bit 1 XOR bit 0 |
| up (forward) | bit 9 XOR bit 8 |
| fire | CIA-A PRA bit 7 (port 1) / bit 6 (port 0) = **0** |

```asm
; out: d0 bit 0 right, 1 left, 2 down, 3 up, 4 fire (1 = active). a6 = $dff000
ReadJoy1:
        moveq   #0,d0
        move.w  joy1dat(a6),d1
        btst    #1,d1
        beq.s   .nr
        bset    #0,d0
.nr     btst    #9,d1
        beq.s   .nl
        bset    #1,d0
.nl     move.w  d1,d2
        lsr.w   #1,d2
        eor.w   d1,d2                   ; bit 0 = b1^b0, bit 8 = b9^b8
        btst    #0,d2
        beq.s   .nd
        bset    #2,d0
.nd     btst    #8,d2
        beq.s   .nu
        bset    #3,d0
.nu     btst    #CIAB_GAMEPORT1,$bfe001
        bne.s   .nf
        bset    #4,d0
.nf     rts
```

## Mouse

JOYxDAT bits 15-8 = vertical counter, 7-0 = horizontal counter. Counters increase to the right
and down, wrap at 8 bits, and are updated by the hardware (about 200 counts per inch). Read at
least once per frame and use 8-bit signed differences:

```asm
; out: d0.w = dx, d1.w = dy since the last call. Initialise 'lastmouse' with joy0dat first.
ReadMouse:
        move.w  joy0dat(a6),d2
        move.w  lastmouse,d3
        move.w  d2,lastmouse
        move.b  d2,d0
        sub.b   d3,d0
        ext.w   d0                      ; dx
        move.w  d2,d1
        lsr.w   #8,d1
        lsr.w   #8,d3
        sub.b   d3,d1
        ext.w   d1                      ; dy
        rts

        section vars,bss
lastmouse: ds.w 1
```

JOYTEST (write) presets all four counters (bits 1-0 of each byte are not written).
Left mouse button = CIA-A PRA bit 6 (port 0) / bit 7 (port 1), 0 = pressed.

## Second and third buttons (POTGO / POTGOR)

The pot pins double as a 4-bit I/O port. A button pulls its pin to ground; enable the pin as an
output driven high (both OUT and DAT = 1) so it is pulled up, then read POTGOR (`potinp`):
0 = pressed.

| Pin | Port 0 (mouse port) | Port 1 (joystick port) |
|---|---|---|
| 9: right mouse button / 2nd fire | DATLY bit 10, OUTLY bit 11 | DATRY bit 14, OUTRY bit 15 |
| 5: middle button / 3rd fire | DATLX bit 8, OUTLX bit 9 | DATRX bit 12, OUTRX bit 13 |

```asm
        move.w  #$0c00,potgo(a6)        ; once: port 0 pin 9 output-high (right button)
        ; ...                           ; the line needs up to ~300 us to settle
        btst    #10-8,potinp(a6)        ; byte read of the high byte: bit 2 = DATLY
        beq     .rmb_pressed
```

With the OS alive, POTGO belongs to `potgo.resource`.

## Proportional controllers (pots)

Write `POTGO = $0001` (START; all pins inputs) during vertical blank: the counters reset and
count lines until each capacitor charges. Read POT0DAT/POT1DAT during the next vertical blank
(bits 15-8 = pin 9 / Y, bits 7-0 = pin 5 / X), then start again. Average several readings;
470K pots are the design value.

## Serial port

Paula's UART, controlled without the OS:

- **Baud rate:** `SERPER = clock / baud - 1` (PAL clock 3546895, NTSC 3579545). 9600 baud:
  PAL 368, NTSC 371. SERPER bit 15 = 1 selects 9-bit receive.
- **Transmit:** write SERDAT with the data bits plus stop bit(s) above them: 8N1 = `$0100 ! byte`.
  Writing 0 sends nothing.
- **Receive:** SERDATR bit 14 (RBF) = byte ready (bits 7-0). Clear INTREQ RBF (bit 11)
  before the next byte arrives or bit 15 (OVRUN) sets.
- SERDATR bit 13 TBE = transmit buffer empty, bit 12 TSRE = shift register empty, bit 11 RXD =
  live input pin. ADKCON bit 11 (UARTBRK) forces a break. Modem lines are on CIA-B PRA.

```asm
; send d0.b at the current SERPER rate, polled. a6 = $dff000
SerPut:
.w      move.w  serdatr(a6),d1
        btst    #13,d1                  ; TBE
        beq.s   .w
        and.w   #$00ff,d0
        or.w    #$0100,d0               ; one stop bit
        move.w  d0,serdat(a6)
        rts
```

## Parallel port

Data on CIA-A PRB (set DDRB `$FF` to output). Each access to PRB pulses the CIA's PC line,
which is the port's data-ready/strobe output; the device's ACK* arrives on CIA-A FLAG (ICR bit
4). Status inputs are CIA-B PRA bits 0 (BUSY), 1 (POUT), 2 (SEL); for a Centronics printer
BUSY = 1 means busy (unverified polarity).

## Floppy control lines

- **Motor:** the drive latches MTR* when its select goes low. Sequence: deselect (SELx = 1),
  set MTR (0 = on), select (SELx = 0). Then wait for DSKRDY (CIA-A PRA bit 5 = 0) or 500 ms.
- **Step:** set DIR in a separate write first, then pulse STEP low -> high. At least 3 ms
  between steps, 18 ms after reversing direction, 15 ms settle before reading/writing. Never
  step outwards while TRACK0 reads 0.
- **Side:** SIDE must be stable 100 us before writing and 1.3 ms after.
- Data transfer is disk DMA (DSKPTH, DSKLEN written twice to start, DSKSYNC `$4489` for
  MFM, ADKCON precomp/sync bits); see [disk.md](../registers/disk.md).

```asm
        include "hardware/cia.i"
        lea     $bfd100,a1                      ; CIA-B PRB
        or.b    #CIAF_DSKSEL0!CIAF_DSKSEL1!CIAF_DSKSEL2!CIAF_DSKSEL3,(a1)   ; deselect all
        bclr    #CIAB_DSKMOTOR,(a1)             ; motor on (active low)
        bclr    #CIAB_DSKSEL0,(a1)              ; select DF0: latches "motor on"
        ; wait for btst #CIAB_DSKRDY,$bfe001 to read 0, or 500 ms
```

## Common mistakes

- Word access to CIA registers, or CIA-B at odd addresses.
- Writing CIA-A PRA as a full byte (clobbers OVL/LED); use `bset`/`bclr`.
- Reading ICR twice, or in a polling loop, and losing other flags (it clears on read).
- Timer bytes written high-then-low (the high write starts/loads with a stale low byte).
- Forgetting the keyboard handshake, or timing it with a CPU loop (too short on fast CPUs).
- Decoding raw keys with `rol` instead of `ror`, or skipping the `not`.
- Joystick up/down read directly from bits 8/0 instead of the XOR.
- Fire button tested for 1 instead of 0.
- Mouse deltas computed as 16-bit differences (wrap errors) or read less than once per frame.
- Reading POTGOR right after writing POTGO (no settle time), or leaving the pins as inputs.
- Using PAL SERPER values on NTSC.
