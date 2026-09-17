# Audio: Paula's four channels

Playing samples with audio DMA: format, period/volume maths, queuing, modulation, filter.

Each of the four channels has an 8-bit DAC fed by its own DMA channel: you give it a start
address, a length and a period, enable it in DMACON, and it plays -- looping -- with no CPU
help. Audio interrupts (level 4) tell you when a block has been latched or has finished.

Registers: [AUDxLCH, AUDxLCL](../registers/audio.md#audxlch-audxlcl),
[AUDxLEN](../registers/audio.md#audxlen), [AUDxPER](../registers/audio.md#audxper),
[AUDxVOL](../registers/audio.md#audxvol), [AUDxDAT](../registers/audio.md#audxdat),
[ADKCON](../registers/audio.md#adkcon), [ADKCONR](../registers/audio.md#adkconr),
[DMACON](../registers/dma-beam.md#dmacon), [INTENA](../registers/interrupts.md#intena),
[INTREQ](../registers/interrupts.md#intreq), [CIAA PRA](../registers/cia.md#ciaa-pra).

With the OS alive, allocate channels through audio.device; direct access as shown here needs
a taken-over machine ([system-takeover.md](system-takeover.md)).

## Sample format

- **Signed 8-bit** two's complement bytes, -128 .. +127. Unsigned (WAV-style) data must be
  converted (`eor.b #$80`).
- In **chip RAM**, starting on an even address.
- Played as words: **AUDxLEN is the length in words** (`bytes / 2`), 1-65535. An odd final byte
  is not played.
- Loops automatically: when the length counter runs out the channel reloads the location and
  length registers and starts again.

`hardware/custom.i` names: `aud0`..`aud3` (`$0A0`, `$0B0`, `$0C0`, `$0D0`) plus
`ac_ptr` (LCH/LCL, long), `ac_len`, `ac_per`, `ac_vol`, `ac_dat`.

## Period and sample rate

The period is the number of colour clocks between samples:

```text
period = clock / samples_per_second      clock: PAL 3546895, NTSC 3579545
rate   = clock / period
tone frequency = clock / (period * bytes in one waveform cycle)
```

| Rate | PAL period | NTSC period |
|---|---|---|
| 8363 Hz | 424 | 428 |
| 11025 Hz | 322 | 325 |
| 16000 Hz | 222 | 224 |
| 22050 Hz | 161 | 162 |
| 28604 / 28867 Hz | 124 | 124 |

- Minimum period: **124** (HRM: 124 NTSC, 123 PAL). Audio DMA gets one slot per scan line,
  about 28.9 kHz; below that the previous sample is repeated.
- Maximum 65535. Compute the period from the real video standard; a PAL period on NTSC plays
  about 1% sharp.
- Round: `period = (clock + rate/2) / rate`.

## Volume

AUDxVOL = 0-64 (bits 6-0; 64 = `$40` = full). The scale is linear in amplitude: 32 is -6 dB,
16 is -12 dB, 0 is silent. Keep samples at full scale and lower the volume for quiet sounds
(less quantisation noise).

## Stereo layout

The HRM (chapter 5) states channels 1 and 2 go to the left output and 0 and 3 to the right.
The common tracker convention treats 0 and 3 as left (unverified -- check on the target
setup). Either way, 0/3 share one side and 1/2 the other.

## Starting and stopping

1. Write AUDxLC (long), AUDxLEN, AUDxPER, AUDxVOL.
2. Enable: `DMACON = DMAF_SETCLR ! DMAF_MASTER ! DMAF_AUDx`.
3. Stop: `DMACON = DMAF_AUDx` (bit 15 clear). Re-enabling restarts from AUDxLC, not where
   it stopped (unless it was off for less than about two sample periods).

## Queuing the next block (audio interrupts)

When a channel starts, it copies AUDxLC/AUDxLEN into internal counters and raises its
interrupt (INTREQ bit 7-10 = AUD0-AUD3). From that moment the registers are free: whatever
you write now is used when the current block ends. The interrupt fires again as the last
word of each block starts playing.

- **One-shot:** after the start interrupt, point the channel at a short silent block; it
  plays the sample once, then loops silence.
- **Intro + loop** (tracker style): after the start interrupt, write the loop start/length.
- **Streaming:** in the level-4 handler write the next buffer each time.

The AUD bits raise a level-4 interrupt only if enabled in INTENA; you can also poll
INTREQR and acknowledge by writing the bit to INTREQ.

## Example: play a one-shot sample (polled)

```asm
        include "hardware/custom.i"
        include "hardware/dmabits.i"
        include "hardware/intbits.i"

CLOCK   equ     3546895                 ; PAL; NTSC = 3579545
RATE    equ     11025
PERIOD  equ     (CLOCK+RATE/2)/RATE     ; 322

        section code,code
; a6 = $dff000, machine taken over, AUD0 interrupt disabled in INTENA
PlayOnce:
        move.w  #DMAF_AUD0,dmacon(a6)           ; stop channel 0
        move.w  #INTF_AUD0,intreq(a6)           ; clear a stale request
        move.l  #sample,aud0+ac_ptr(a6)
        move.w  #(sample_end-sample)/2,aud0+ac_len(a6)
        move.w  #PERIOD,aud0+ac_per(a6)
        move.w  #64,aud0+ac_vol(a6)
        move.w  #DMAF_SETCLR!DMAF_MASTER!DMAF_AUD0,dmacon(a6)
.latch  move.w  intreqr(a6),d0                  ; wait until pointer/length are latched
        btst    #INTB_AUD0,d0
        beq.s   .latch
        move.l  #silence,aud0+ac_ptr(a6)        ; used when the sample ends
        move.w  #1,aud0+ac_len(a6)
        move.w  #INTF_AUD0,intreq(a6)
        rts

        section samples,data_c
sample: incbin  "boom.raw"                      ; signed 8-bit mono
sample_end:
        even
silence:
        dc.w    0
```

The latch interrupt arrives within a scan line or so. Later, `move.w #DMAF_AUD0,dmacon(a6)`
stops the (now silent) channel.

## Modulation (ADKCON)

A channel can modulate the **next higher** channel instead of producing sound. Its data words
are then used as volume (bits 6-0) or period (16 bits) values for the next channel, one word
per period of the modulator. With both bits set for a channel, words alternate volume,
period, volume, ...

| ADKCON bit | Name | Effect |
|---|---|---|
| 0 / 1 / 2 | `ADKF_USE0V1` / `USE1V2` / `USE2V3` | channel 0/1/2 modulates volume of 1/2/3 |
| 4 / 5 / 6 | `ADKF_USE0P1` / `USE1P2` / `USE2P3` | channel 0/1/2 modulates period of 1/2/3 |
| 3 / 7 | `ADKF_USE3VN` / `USE3PN` | channel 3 modulates nothing (just mutes it) |

ADKCON is a set/clear register shared with the disk controller (bits 8-14). Only touch the
audio bits:

```asm
        move.w  #$00ff,adkcon(a6)               ; clear all audio modulation (typical init)
        move.w  #ADKF_SETCLR!ADKF_USE0V1,adkcon(a6)  ; channel 0 -> volume of channel 1
```

## Direct (non-DMA) output

With the channel's DMA bit off, writing AUDxDAT outputs a word directly; the interrupt then
means "ready for the next word", and output freezes if you are more than two periods late.
CPU-heavy and not recommended.

## The low-pass filter (power LED bit)

On later A500s and 2-layer A2000s the audio low-pass filter (starts rolling off around 4-5
kHz) is switched with the power-LED output, CIA-A PRA bit 1 (`CIAB_LED`): 0 = LED bright /
filter on, 1 = LED dim / filter bypassed. Change only that bit -- bit 0 of the same register
is the ROM overlay control.

```asm
        include "hardware/cia.i"
        bset    #CIAB_LED,$bfe001               ; filter off
        bclr    #CIAB_LED,$bfe001               ; filter on
```

For clean sound keep the highest wanted frequency plus 7 kHz below the sample rate (e.g.
14 kHz rate for 7 kHz content; periods 124-256 give 14-28 kHz).

## Common mistakes

- Sample in fast RAM: silence or noise.
- AUDxLEN in bytes instead of words: the sample plays twice as long into random memory.
- Unsigned 8-bit data played as signed: loud distorted noise.
- Period below 124, or a PAL-computed period on NTSC.
- Volume above 64 (only 0-64 are defined).
- Expecting a sample to stop by itself: channels loop until DMA is switched off or a silent
  block is queued.
- Writing the next block's LC/LEN before the start interrupt: the channel may not have
  latched the first block yet, so the first block is skipped.
- Setting ADKCON with a bare value (`move.w #$0001,adkcon`) -- without bit 15 that clears bit 0;
  and writing whole-register values disturbs the disk bits.
- Writing CIA-A PRA as a byte to toggle the filter (clobbers `OVL`).
