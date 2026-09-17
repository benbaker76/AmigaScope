# Custom chips: floppy disk registers

Paula reads and writes raw MFM (or GCR) bit streams by DMA. Drive selection, motor,
stepping and side come from CIA-B port B; drive status (ready, track 0, write protect,
disk change) from CIA-A port A; the index pulse arrives on CIA-B FLAG. Disk mode bits
(sync, bit rate, precompensation) are in ADKCON. Standard Amiga MFM read setup: ADKCON
`MFMPREC|WORDSYNC|FAST`, DSKSYNC `$4489`, then read a whole track into a buffer.

## DSKPTH, DSKPTL
`$DFF020` / `$DFF022` · write · Agnus · OCS (high word: 3 address bits OCS, 5 ECS) · pointer pair: one `move.l`

Chip-RAM buffer address for the next disk DMA read or write.

NDK: `dskpt` (custom.i, longword label; no separate H/L labels); C `custom->dskpt`.

### Gotchas
- Must be set before disk DMA is started, as one longword, to an even chip-RAM address.
- The pointer advances as words are transferred: reload it before every read or write.

**See also:** DSKLEN, [CIAB PRB](cia.md#ciab-prb)

## DSKLEN
`$DFF024` · write · Paula · OCS

Disk DMA enable, direction and length; DMA starts only on the second enabling write.

| Bit | Name | Meaning |
|---|---|---|
| 15 | DMAEN | disk DMA enable (must be written as 1 twice in a row) |
| 14 | WRITE | 1 = write (RAM to disk), 0 = read |
| 13-0 | LENGTH | number of words to transfer |

NDK: `dsklen` (custom.i); no bit constants; C `custom->dsklen`.

### Example
```asm
; read TRKWORDS raw words from the selected drive into TrackBuf (chip RAM)
        include "hardware/custom.i"
        include "hardware/dmabits.i"
        include "hardware/intbits.i"
        include "hardware/adkbits.i"
        lea     $dff000,a6
        move.w  #DMAF_SETCLR!DMAF_MASTER!DMAF_DISK,dmacon(a6)
        move.w  #$4000,dsklen(a6)               ; DMA off (safe state)
        move.w  #$7f00,adkcon(a6)
        move.w  #ADKF_SETCLR!ADKF_MFMPREC!ADKF_WORDSYNC!ADKF_FAST,adkcon(a6)
        move.w  #$4489,dsksync(a6)
        move.l  #TrackBuf,dskpt(a6)
        move.w  #INTF_DSKBLK,intreq(a6)         ; clear old "block done"
        move.w  #$8000!TRKWORDS,dsklen(a6)
        move.w  #$8000!TRKWORDS,dsklen(a6)      ; second write starts the DMA
.wait   btst    #INTB_DSKBLK,intreqr+1(a6)
        beq.s   .wait
        move.w  #$4000,dsklen(a6)               ; back to the safe state
```

### Gotchas
- The double write is a hardware safety feature: a single write never starts DMA.
- Write `$4000` before setting up and after finishing, so a stray write cannot start an
  accidental disk write.
- LENGTH counts down to 0; completion raises INTREQ DSKBLK (level 1).
- Hardware bugs: the last 3 bits of a write are lost and a read may deliver one word less
  than requested, so pad buffers.
- Select the drive, turn the motor on and wait for /RDY (CIA-A PRA bit 5) or 500 ms first.
- OS-friendly code must own the drive through the disk resource / trackdisk.device
  instead of poking these registers.

**See also:** DSKPTH, DSKPTL, DSKSYNC, DSKBYTR, [ADKCON](audio.md#adkcon), [INTREQ](interrupts.md#intreq), [CIAA PRA](cia.md#ciaa-pra)

## DSKDAT
`$DFF026` · write · Paula · OCS · DMA-only

Disk DMA data buffer for writes: two bytes on their way from RAM to the disk.

NDK: `dskdat` (custom.i); C `custom->dskdat`.

### Gotchas
- Filled by disk DMA; the CPU has no reason to write it.

**See also:** DSKDATR, DSKLEN

## DSKDATR
`$DFF008` · DMA-only (early read) · Paula · OCS · never read by the CPU

Disk DMA data buffer for reads (early-read dummy address used by the DMA).

NDK: `dskdatr` (custom.i); C `custom->dskdatr`.

### Gotchas
- Use DSKBYTR to look at incoming bytes from the CPU.

**See also:** DSKBYTR, DSKDAT

## DSKBYTR
`$DFF01A` · read · Paula · OCS

Disk byte buffer and status: one byte of the input stream at a time, plus DMA state.

| Bit | Name | Meaning |
|---|---|---|
| 15 | DSKBYT | 1 = bits 7-0 hold a new byte (cleared by reading this register) |
| 14 | DMAON | disk DMA really running (DSKLEN DMAEN and DMACON DMAEN/DSKEN) |
| 13 | DISKWRITE | mirror of DSKLEN WRITE |
| 12 | WORDEQUAL | input currently equals DSKSYNC (true for only about 2 us) |
| 11-8 | -- | unused |
| 7-0 | DATA | disk byte |

NDK: `dskbytr` (custom.i); no bit constants; C `custom->dskbytr`.

### Gotchas
- Reading clears DSKBYT: read once and test the copy.
- Useful to synchronise to the disk stream without DMA; normal reading uses DMA plus
  DSKSYNC.

**See also:** DSKSYNC, DSKLEN

## DSKSYNC
`$DFF07E` · write · Paula · OCS · copper danger

Sync word compared with the disk input stream (`$4489` for Amiga MFM).

NDK: `dsksync` (custom.i); C `custom->dsksync`.

### Gotchas
- With ADKCON WORDSYNC set, read DMA waits for this word and starts with the following
  word; the controller resyncs on every match during the read.
- INTREQ DSKSYNC (level 5) is set on every match, whether or not WORDSYNC is on.

**See also:** DSKLEN, DSKBYTR, [ADKCON](audio.md#adkcon), [INTREQ](interrupts.md#intreq)
