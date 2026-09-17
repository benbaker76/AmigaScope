# audio.device

The OS arbiter for Paula's four sample channels: programs allocate channels by precedence, then
queue waveform writes to them. Device name `"audio.device"` (`AUDIONAME`), request `struct IOAudio`
(`devices/audio.h`, `devices/audio.i`). It has **no library functions** and no LVO table:
everything is a command sent with exec I/O ([DoIO](../exec/io.md#doio),
[SendIO](../exec/io.md#sendio), amiga.lib BeginIO). Command entries:
[commands.md](commands.md). Worked guide: [playing samples](playing-samples.md).

## Opening and closing

`OpenDevice(AUDIONAME, 0, (struct IORequest *)ioa, 0)`: the unit number and flags are not used.

- `ioa_Length` = 0: open only. `ioa_AllocKey` = 0 gets a fresh unique key on success.
- `ioa_Length` > 0: OpenDevice also tries an [ADCMD_ALLOCATE](commands.md#adcmd_allocate) with
  the combination array in `ioa_Data` at precedence `ln_Pri`. It never waits. On success
  `io_Unit` holds the allocated channel mask; on failure the device is closed again and the
  result is `ADIOERR_ALLOCFAILED`. Allocating needs `mn_ReplyPort` to be a port with an allocated
  signal bit (CreateMsgPort + CreateIORequest do that).
- Result (and `io_Error`): 0 = success, `IOERR_OPENFAIL` (-1), `ADIOERR_ALLOCFAILED` (-11). On
  failure `io_Device` is -1: do not send commands, and do not CloseDevice that request.
- **CloseDevice** frees every channel in the request's `io_Unit` that carries its `ioa_AllocKey`
  (an implicit ADCMD_FREE), then sets `io_Device` to -1 and `io_Unit` to 0. Keep `io_Unit` of the
  request you close intact: commands overwrite `io_Unit` with their success mask, so send them
  through copies.
- **BeginIO** is the device's dispatcher: immediate commands run at once, the rest are queued and
  handled one at a time. **AbortIO** may fail; when it works the request comes back with
  `IOERR_ABORTED` in `io_Error`. **Expunge** (after RemDevice) is deferred while the open count is
  non-zero.

```c
#include <proto/exec.h>
#include <devices/audio.h>

static UBYTE stereoPairs[] = { 3, 5, 10, 12 };

struct MsgPort *port = CreateMsgPort();
struct IOAudio *ioa  = NULL;
ULONG chans = 0;

if (port)
    ioa = (struct IOAudio *)CreateIORequest(port, sizeof(struct IOAudio));
if (ioa) {
    ioa->ioa_Request.io_Message.mn_Node.ln_Pri = 0;    /* allocation precedence */
    ioa->ioa_AllocKey = 0;                             /* new key */
    ioa->ioa_Data     = stereoPairs;
    ioa->ioa_Length   = sizeof(stereoPairs);
    if (OpenDevice((CONST_STRPTR)AUDIONAME, 0, (struct IORequest *)ioa, 0) == 0)
        chans = (ULONG)ioa->ioa_Request.io_Unit;      /* e.g. 5 = channels 0 and 2 */
}
```

```asm
        include "exec/io.i"
        include "devices/audio.i"
        include "lvo/exec_lib.i"

; audioreq = IOAudio from CreateIORequest(port, ioa_SIZEOF)
        move.l  4.w,a6
        move.l  audioreq,a1
        clr.b   LN_PRI(a1)              ; precedence 0
        clr.w   ioa_AllocKey(a1)        ; new key
        move.l  #pairs,ioa_Data(a1)
        move.l  #4,ioa_Length(a1)       ; 4 combinations
        lea     audioname(pc),a0
        moveq   #0,d0                   ; unit: not used
        moveq   #0,d1                   ; flags: not used
        jsr     _LVOOpenDevice(a6)
        tst.l   d0
        bne     .noaudio                ; IOERR_OPENFAIL / ADIOERR_ALLOCFAILED
        move.l  audioreq,a1
        move.l  IO_UNIT(a1),d0          ; allocated channel mask
.noaudio:
        rts

pairs:      dc.b    3,5,10,12
audioname:  AUDIONAME                   ; unlike TIMERNAME, this macro does not word-align
            even
```

## Channel allocation model

- **Channels and masks.** `ADHARD_CHANNELS` = 4. Bits 0-3 of a mask select channels 0-3 (1, 2, 4,
  8). Channels 0 and 3 feed one stereo side, 1 and 2 the other. The HRM puts 1/2 on the left, the
  common tracker convention puts 0/3 on the left: the amiga-hardware skill has the details.

  | Mask | Channels | Use |
  |---|---|---|
  | 1, 2, 4, 8 | one of 0..3 | mono sound effect |
  | 3, 5, 10, 12 | 0+1, 0+2, 1+3, 2+3 | stereo pair (one channel per side) |
  | 9, 6 | 0+3, 1+2 | two channels on the same side |
  | 15 | all four | music player, direct hardware use |

- **Combination array.** `ioa_Data` points to up to 16 (`ioa_Length`) UBYTE masks, tried in
  order. The first one that can be had without stealing wins. Otherwise the combination that
  steals the lowest-precedence channels is taken. An empty array (`ioa_Length` 0) always succeeds.
- **Precedence** is `ln_Pri` of the request: -128 (`ADALLOC_MINPREC`) .. 127 (`ADALLOC_MAXPREC`).
  An allocation can only steal channels of strictly **lower** precedence.
  [ADCMD_SETPREC](commands.md#adcmd_setprec) changes it later. RKM Devices guideline (not in the
  local sources, unverified): 127 unstealable, 90..100 emergencies, 80..90 annunciators (beep),
  75 speech, 50..70 sonic cues, -50..50 music, -70..-50 sound effects, -100..-80 background,
  -128 silence.
- **Allocation key.** The device stamps a WORD key (`ioa_AllocKey`) and the precedence into each
  channel it allocates. Every later command on those channels must carry the same key, otherwise
  it fails with `ADIOERR_NOALLOCATION`. Pass 0 to get a new key, or an existing key to add channels
  under it. Extra requests get the key (and `io_Device`) by copying the opened request.
- **Waiting.** A failed ADCMD_ALLOCATE waits for channels to become free unless `ADIOF_NOWAIT` is
  set (then `ADIOERR_ALLOCFAILED`). OpenDevice allocations never wait.
- **Stealing.** When your channels are stolen, your playing writes and waits return
  `IOERR_ABORTED` and later commands fail with `ADIOERR_NOALLOCATION`. There is no need to free
  stolen channels.
- **Locking.** [ADCMD_LOCK](commands.md#adcmd_lock) makes any would-be thief wait, even a no-wait
  allocation, until you free the channels. The pending lock request is replied with
  `ADIOERR_CHANNELSTOLEN` as a "please free now" notice. Allocating at `ADALLOC_MAXPREC` instead
  makes the channels unstealable: later allocations of them fail (or wait, without
  `ADIOF_NOWAIT`) instead of queuing behind your lock.
- **Freeing.** [ADCMD_FREE](commands.md#adcmd_free) or CloseDevice. Always free what you allocated
  (unless it was stolen): freeing resets the channel and hands it to waiting allocations.

## IOAudio

| Offset | asm label | C field | Type | Meaning |
|---|---|---|---|---|
| $00 | (IO_SIZE $20) | `ioa_Request` | `struct IORequest` | `LN_PRI` $09 = precedence; `MN_REPLYPORT` $0E; `IO_DEVICE` $14; `IO_UNIT` $18 = channel mask; `IO_COMMAND` $1C; `IO_FLAGS` $1E; `IO_ERROR` $1F |
| $20 | `ioa_AllocKey` | `ioa_AllocKey` | WORD | allocation key |
| $22 | `ioa_Data` | `ioa_Data` | `UBYTE *` | ALLOCATE: combination array; WRITE: sample; READ returns the playing request here |
| $26 | `ioa_Length` | `ioa_Length` | ULONG | ALLOCATE: 0..16 entries; WRITE: sample length in bytes, even, 2..131072 |
| $2A | `ioa_Period` | `ioa_Period` | UWORD | sample period, 124 and up (see CMD_WRITE) |
| $2C | `ioa_Volume` | `ioa_Volume` | UWORD | 0..64, linear |
| $2E | `ioa_Cycles` | `ioa_Cycles` | UWORD | times to play the sample, 0 = until stopped |
| $30 | `ioa_WriteMsg` | `ioa_WriteMsg` | `struct Message` | replied when a write starts (`ADIOF_WRITEMESSAGE`) |
| $44 | `ioa_SIZEOF` | `sizeof(struct IOAudio)` | | 68 bytes |

- In C `io_Unit` is declared `struct Unit *`: read with `(ULONG)ioa->ioa_Request.io_Unit`, write
  with `(struct Unit *)mask`.
- Flags (`io_Flags`): `IOF_QUICK` $01, `ADIOF_PERVOL` $10 (bit 4), `ADIOF_SYNCCYCLE` $20 (bit 5),
  `ADIOF_NOWAIT` $40 (bit 6), `ADIOF_WRITEMESSAGE` $80 (bit 7). Unused flags must be 0.
- Errors (`io_Error`): `IOERR_OPENFAIL` -1, `IOERR_ABORTED` -2 (exec/errors.h),
  `ADIOERR_NOALLOCATION` -10, `ADIOERR_ALLOCFAILED` -11, `ADIOERR_CHANNELSTOLEN` -12.
- Commands: `CMD_RESET` 1, `CMD_READ` 2, `CMD_WRITE` 3, `CMD_UPDATE` 4, `CMD_CLEAR` 5, `CMD_STOP`
  6, `CMD_START` 7, `CMD_FLUSH` 8, `ADCMD_FREE` 9, `ADCMD_SETPREC` 10, `ADCMD_FINISH` 11,
  `ADCMD_PERVOL` 12, `ADCMD_LOCK` 13, `ADCMD_WAITCYCLE` 14, `ADCMD_ALLOCATE` **32**.

## Sending commands

- **Flags need BeginIO.** DoIO forces `io_Flags` = `IOF_QUICK` and SendIO clears it, which wipes
  `ADIOF_PERVOL`, `ADIOF_SYNCCYCLE`, `ADIOF_NOWAIT` and `ADIOF_WRITEMESSAGE`. Send any command
  that uses those flags with BeginIO: `#include <inline/alib.h>` in Bartman C, or in asm
  `jsr DEV_BEGINIO(a6)` (-30) with A6 = `IO_DEVICE(a1)` (see [exec I/O](../exec/io.md)).
- **Replies.** With `IOF_QUICK` clear, every command replies to `mn_ReplyPort`, including
  synchronous ones and errors, so collect it with WaitIO. With `IOF_QUICK` set, a command that
  completes synchronously does not reply. Test `io_Flags & IOF_QUICK` after BeginIO: still set
  means done; cleared means wait for the reply.
- DoIO is fine for commands without flags (ADCMD_FREE, ADCMD_SETPREC, immediate ADCMD_PERVOL and
  ADCMD_FINISH, CMD_STOP, CMD_START, CMD_FLUSH, CMD_RESET, CMD_READ).
- **Channel selection.** Multi-channel commands act on every bit of `io_Unit` and return the mask
  of channels that succeeded there. CMD_WRITE, CMD_READ and ADCMD_WAITCYCLE use only the lowest
  set bit.
- **One request per pending operation.** A playing write occupies its request until it is
  replied. For stereo, or to queue several writes, create more IOAudio requests with
  CreateIORequest and copy the opened request into them (the autodocs allow `io_Device` and
  `ioa_AllocKey` to be copied), then set `io_Unit`.
- **Interrupts.** ADCMD_ALLOCATE, ADCMD_FREE, ADCMD_LOCK and ADCMD_SETPREC never from interrupt
  code. CMD_WRITE, ADCMD_PERVOL, ADCMD_FINISH, ADCMD_WAITCYCLE, CMD_STOP, CMD_START, CMD_FLUSH
  and CMD_RESET not at interrupt level 5 or higher.

## audio.device and direct Paula access

audio.device drives the AUDx registers, the audio DMA and interrupt bits, and the audio interrupt
vectors of the channels it manages. CMD_RESET, which runs on every allocation and free, clears
the channel's registers and attach bits and re-installs the device's audio interrupt vector.
Writing `AUDxLC/LEN/PER/VOL`, `DMACON` audio bits, `ADKCON` modulation bits or your own
`INTB_AUDx` vector on a channel the device thinks it owns is the classic conflict: the device, or
the next program that allocates the channel, silently undoes or corrupts your setup (clicks, stuck
channels, wrong interrupt handler).

- The OS-legal way: allocate the channels you will touch (mask 15 for all four), then either
  [ADCMD_LOCK](commands.md#adcmd_lock) them or allocate at `ADALLOC_MAXPREC` so they cannot be
  stolen (autodoc advice). Then program the registers as the amiga-hardware skill describes.
- When done: stop your DMA and interrupts, put back any vector you replaced, then
  ADCMD_FREE/CloseDevice (the reset restores the device's state).
- When a lock comes back with `ADIOERR_CHANNELSTOLEN`, stop using those channels and free them
  soon. Never make freeing depend on another allocation completing (deadlock).
- Programs that take the whole machine over (OS interrupts off) bypass audio.device completely.
  For retargetable sound cards use AHI (the amiga-ahi skill).

## Versions

The audio autodocs state no versions and the include is `audio.h` 36.3. All commands above are
the original 1.x set (unverified).

## Files

- [commands.md](commands.md) -- all 15 commands: ADCMD_ALLOCATE, ADCMD_FREE, ADCMD_SETPREC,
  ADCMD_LOCK, CMD_WRITE, ADCMD_PERVOL, ADCMD_FINISH, ADCMD_WAITCYCLE, CMD_STOP, CMD_START,
  CMD_FLUSH, CMD_RESET, CMD_READ, CMD_CLEAR, CMD_UPDATE.
- [playing-samples.md](playing-samples.md) -- guide: allocate a stereo pair, one-shot and looping
  playback, live period/volume changes, stopping and freeing, with a complete C program.
