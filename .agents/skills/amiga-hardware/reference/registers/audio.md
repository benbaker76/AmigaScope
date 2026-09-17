# Custom chips: audio registers

Paula has four 8-bit audio channels: 0 and 3 share one stereo output, 1 and 2 the other
(which side is which is disputed between sources, see
[stereo layout](../topics/audio.md#stereo-layout)). Each channel plays a signed 8-bit
sample from chip RAM by DMA at a rate set by AUDxPER, loops it until told otherwise, and raises its AUDx interrupt (level
4) every time it latches a new block. Channel registers are at `$DFF0A0 + x*$10`.

| x | LCH | LCL | LEN | PER | VOL | DAT |
|---|---|---|---|---|---|---|
| 0 | `$DFF0A0` | `$DFF0A2` | `$DFF0A4` | `$DFF0A6` | `$DFF0A8` | `$DFF0AA` |
| 1 | `$DFF0B0` | `$DFF0B2` | `$DFF0B4` | `$DFF0B6` | `$DFF0B8` | `$DFF0BA` |
| 2 | `$DFF0C0` | `$DFF0C2` | `$DFF0C4` | `$DFF0C6` | `$DFF0C8` | `$DFF0CA` |
| 3 | `$DFF0D0` | `$DFF0D2` | `$DFF0D4` | `$DFF0D6` | `$DFF0D8` | `$DFF0DA` |

NDK layout (custom.i): `aud0`..`aud3` (or `aud+x*ac_SIZEOF`) plus the offsets `ac_ptr`
(0), `ac_len` (4), `ac_per` (6), `ac_vol` (8), `ac_dat` ($A); `ac_SIZEOF` = $10.
C: `custom->aud[x].ac_ptr` etc.

## AUDxLCH, AUDxLCL
`$DFF0A0 + x*$10` / `+2` · write · Agnus (DMA pointer) · OCS (high word: 3 address bits OCS, 5 ECS) · location pair: one `move.l`, x = 0-3

Start address of channel x's sample; copied to the playback pointer at each block start.

NDK: `aud0+ac_ptr` ... `aud3+ac_ptr` (custom.i); C `custom->aud[x].ac_ptr`.

### Example
```asm
; play a looping sample on channel 0 (a6 = $DFF000)
        lea     aud0(a6),a0
        move.l  #Sample,ac_ptr(a0)              ; chip RAM
        move.w  #SampleLen/2,ac_len(a0)         ; length in WORDS
        move.w  #321,ac_per(a0)                 ; 3546895/11025 = PAL 11025 Hz
        move.w  #64,ac_vol(a0)                  ; full volume
        move.w  #DMAF_SETCLR!DMAF_AUD0,dmacon(a6)   ; DMAEN must also be on
```

### Gotchas
- Not a moving pointer: the hardware copies it into a backup register when a block
  starts, so you may leave it alone for looping or change it for the next block.
- The AUDx interrupt fires right after the channel has latched LC and LEN: write the next
  block's LC/LEN in that interrupt for gapless chaining. If you do nothing, the same
  block repeats.
- Sample data must be in chip RAM.

**See also:** AUDxLEN, AUDxPER, [DMACON](dma-beam.md#dmacon), [INTENA](interrupts.md#intena)

## AUDxLEN
`$DFF0A4 + x*$10` · write · Paula · OCS · x = 0-3

Length of channel x's sample block in words.

NDK: `aud0+ac_len` (custom.i); C `custom->aud[x].ac_len`.

### Gotchas
- Words, not bytes: a 20000-byte sample is length 10000.
- Latched at block start, like LC: a new value takes effect on the next block.
- To stop a one-shot sound cleanly, point LC/LEN at a short block of zeros in the AUDx
  interrupt, or clear the channel's DMACON bit.

**See also:** AUDxLCH, AUDxLCL, AUDxPER

## AUDxPER
`$DFF0A6 + x*$10` · write · Paula · OCS (ECS: limits depend on scan rate) · x = 0-3

Sample period in colour clocks per sample; a smaller value plays faster (higher pitch).

`period = clock / samples_per_second`, clock = 3579545 (NTSC) or 3546895 (PAL).
Tone frequency = `clock / (period * bytes_per_waveform_cycle)`.

NDK: `aud0+ac_per` (custom.i); C `custom->aud[x].ac_per`.

### Example
```asm
        move.w  #3546895/22050,aud1+ac_per(a6)  ; = 160: PAL 22050 Hz
```

### Gotchas
- Minimum period 124 (NTSC) / 123 (PAL), about 28.8 kHz; below it the DMA cannot fetch
  the next sample in time and samples repeat. Maximum 65535.
- The period constant differs between PAL and NTSC machines: pick it from the machine type
  (e.g. `GfxBase->DisplayFlags`), not a fixed value, if pitch matters.
- ECS/AGA programmable (e.g. 31 kHz) scan rates change the usable limits.
- AUDxPER can be modulated by the previous channel (ADKCON USExPy).

**See also:** AUDxVOL, ADKCON

## AUDxVOL
`$DFF0A8 + x*$10` · write · Paula · OCS · x = 0-3

Channel x volume, 0 (silent) to 64 (full), linear.

| Bit | Meaning |
|---|---|
| 15-7 | unused, write 0 |
| 6 | 1 = maximum volume (64) |
| 5-0 | volume 0-63 |

NDK: `aud0+ac_vol` (custom.i); C `custom->aud[x].ac_vol`.

### Gotchas
- 64 (`$40`) is full volume; do not write values above 64.
- Can be modulated by the previous channel (ADKCON USExVy).

**See also:** AUDxPER, ADKCON

## AUDxDAT
`$DFF0AA + x*$10` · write · Paula · OCS · normally DMA-only, x = 0-3

Output buffer of channel x: two signed 8-bit samples played one after the other.

NDK: `aud0+ac_dat` (custom.i); C `custom->aud[x].ac_dat`.

### Gotchas
- Filled automatically by audio DMA. The CPU may write it directly with the channel's DMA
  off (manual mode): the AUDx interrupt then signals that the register is ready for the
  next word.
- When a channel modulates another (ADKCON), its data words are volume/period values, not
  samples.

**See also:** AUDxLCH, AUDxLCL, ADKCON

## ADKCON
`$DFF09E` · write (set/clear) · Paula · OCS · read back via ADKCONR `$DFF010`

Audio modulation, disk read/write mode and UART break control (set/clear write).

| Bit | Name | Meaning |
|---|---|---|
| 15 | SET/CLR | 1 = set the 1-bits written, 0 = clear them |
| 14-13 | PRECOMP1-0 | disk write precompensation: 00 none, 01 140 ns, 10 280 ns, 11 560 ns |
| 12 | MFMPREC | 1 = MFM precompensation, 0 = GCR |
| 11 | UARTBRK | force serial TXD low (break) |
| 10 | WORDSYNC | start disk read DMA on a DSKSYNC match |
| 9 | MSBSYNC | GCR: sync on MSB of input |
| 8 | FAST | 1 = 2 us/bit (MFM), 0 = 4 us/bit (GCR) |
| 7 | USE3PN | channel 3 modulates nothing (silences channel 3) |
| 6 | USE2P3 | channel 2 modulates period of channel 3 |
| 5 | USE1P2 | channel 1 modulates period of channel 2 |
| 4 | USE0P1 | channel 0 modulates period of channel 1 |
| 3 | USE3VN | channel 3 modulates nothing (silences channel 3) |
| 2 | USE2V3 | channel 2 modulates volume of channel 3 |
| 1 | USE1V2 | channel 1 modulates volume of channel 2 |
| 0 | USE0V1 | channel 0 modulates volume of channel 1 |

NDK: `adkcon` (custom.i); `ADKF_SETCLR`, `ADKF_PRECOMP1`, `ADKF_PRECOMP0`,
`ADKF_MFMPREC`, `ADKF_UARTBRK`, `ADKF_WORDSYNC`, `ADKF_MSBSYNC`, `ADKF_FAST`,
`ADKF_USE3PN`...`ADKF_USE0V1`, `ADKF_PRE000NS`, `ADKF_PRE140NS`, `ADKF_PRE280NS`,
`ADKF_PRE560NS` and `ADKB_` bit numbers (adkbits.i); C `custom->adkcon`.

### Example
```asm
        move.w  #$00ff,adkcon(a6)               ; clear all audio modulation
        move.w  #$7f00,adkcon(a6)               ; clear disk bits
        move.w  #ADKF_SETCLR!ADKF_MFMPREC!ADKF_WORDSYNC!ADKF_FAST,adkcon(a6)  ; MFM read
```

### Gotchas
- A modulating channel stops producing sound; its data words become volume (V6-V0) or
  period values. If both period and volume are modulated, words alternate volume, period.
- Clear bits 7-0 when taking over audio: a leftover modulation bit silently mutes a channel.
- Save ADKCONR at start and restore it (value OR `ADKF_SETCLR` after clearing with `$7FFF`).

**See also:** ADKCONR, [DSKSYNC](disk.md#dsksync), [SERDAT](input-serial.md#serdat)

## ADKCONR
`$DFF010` · read · Paula · OCS · write via ADKCON `$DFF09E`

Read the current audio modulation, disk mode and UART break bits.

Bits 14-0 as in ADKCON; bit 15 has no meaning on read.

NDK: `adkconr` (custom.i); C `custom->adkconr`.

**See also:** ADKCON
