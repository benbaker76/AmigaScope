# audio.device: playing samples

How to play sounds the OS-friendly way: allocate channels, queue writes, change pitch and volume
while playing, then stop and free. The complete program at the end was built with Bartman's
m68k-amiga-elf-gcc and the amiga-debug template flags. Command details are in
[commands.md](commands.md); the allocation rules are in [index.md](index.md#channel-allocation-model).

## Sample data and period

- **Format:** signed 8-bit bytes (-128..127), one byte per sample, mono per channel.
- **Memory:** chip RAM, word-aligned, even length, at most 131072 bytes per write. Use
  `AllocMem(len, MEMF_CHIP)` (blocks are always aligned) or an asm `section name,data_c` hunk.
  Fast RAM plays noise or silence.
- **Period** = clock constant / sample rate, with 3546895 (PAL) or 3579545 (NTSC). The two
  constants differ by 0.9%, so the wrong one makes every sound slightly off-pitch.
  graphics.library's `DisplayFlags` has `PAL`; from V39 `REALLY_PAL` reports the actual crystal
  rather than the display mode the boot menu picked (gfxbase.h). Paula's clock follows the crystal
  (HRM), so prefer `REALLY_PAL` when available.
- **Limits:** period 124..65535, volume 0..64. Periods above roughly 300-500 (sample rates below
  about 7-12 kHz) alias audibly, because the fixed output filter only suppresses aliasing below that.
- **Pitch of a looped waveform:** rate = note frequency x bytes per cycle. A 32-byte square wave
  at 440 Hz is 14080 bytes/s: period 251 PAL.

| Sample rate | PAL period | NTSC period |
|---|---|---|
| 8000 Hz | 443 | 447 |
| 11025 Hz | 321 | 324 |
| 16000 Hz | 221 | 223 |
| 22050 Hz | 160 | 162 |

## Allocating a stereo pair

Pass a combination array to OpenDevice so the device is opened and channels are allocated in
one call, without waiting:

- `{ 3, 5, 10, 12 }` asks for one channel from each stereo side (0 or 3, plus 1 or 2), in order
  of preference. For a single effect channel use `{ 1, 2, 4, 8 }`; for all four, `{ 15 }`.
- `ln_Pri` is the precedence: a background sound should be low so other programs can steal it,
  and a sound you cannot lose should be high. Stealing only takes strictly lower channels.
- On success `io_Unit` is the mask you got. `chans & 0x9` is the channel on the 0/3 side and
  `chans & 0x6` the channel on the 1/2 side. Which physical side is left is disputed between
  sources (see the amiga-hardware skill).
- Keep that opened request untouched and close it last: CloseDevice frees the channels named in
  its `io_Unit`. Send commands through copies of it (CopyMem into a request from CreateIORequest,
  then set `io_Unit`), one copy per concurrent write plus one for control commands.

## One-shot playback

CMD_WRITE with `ioa_Cycles` = 1 plays the sample once and replies when it is done:

- `io_Flags` = `ADIOF_PERVOL`, so period and volume are loaded (always set it: see the CMD_WRITE
  bug note).
- Send it with **BeginIO** (`<inline/alib.h>`). SendIO and DoIO would wipe the flag.
- WaitIO blocks until the sound has played. To keep the program responsive, Wait on the port
  signal together with your other signals and use CheckIO to see which request came back.
- Retriggering the same effect: AbortIO + WaitIO the previous write first, or queue the new write
  on the same channel using a second request.

## Looping playback in sync

`ioa_Cycles` = 0 repeats the sample until the write is aborted, flushed or finished. To start two
channels together, stop them first, queue the writes, then start both in one command:

1. `CMD_STOP` on both channels (DoIO on the control request).
2. BeginIO a CMD_WRITE on each channel. The writes queue on the stopped channels.
3. `CMD_START` on both channels. Playback begins on both at the same moment.

A sample with an intro and a loop part: queue a write of the intro with `ioa_Cycles` = 1, then a
second write (second request) of the loop part with `ioa_Cycles` = 0 on the same channel. Writes
on a channel play in order.

## Changing period and volume live

[ADCMD_PERVOL](commands.md#adcmd_pervol) sets new `ioa_Period`/`ioa_Volume` for the writes playing
on every channel in `io_Unit`:

- Immediate change: DoIO on the control request (DoIO clears `ADIOF_SYNCCYCLE`).
- Change at the end of the current waveform cycle (smoother for looped waveforms): BeginIO with
  `ADIOF_SYNCCYCLE | IOF_QUICK`, then WaitIO only if `IOF_QUICK` was cleared.
- It affects only writes in progress. A queued write loads its own values.

## Stopping and freeing

- **Now:** AbortIO each playing write, then WaitIO each one (`io_Error` = `IOERR_ABORTED`). Or
  send [CMD_FLUSH](commands.md#cmd_flush) on the channels and WaitIO every write that was
  playing or queued.
- **At the end of the waveform:** [ADCMD_FINISH](commands.md#adcmd_finish) with
  `ADIOF_SYNCCYCLE`, then WaitIO the write.
- **Free:** CloseDevice on the opened request frees its channels. [ADCMD_FREE](commands.md#adcmd_free)
  frees them explicitly if you want to keep the device open.
- **Memory last:** FreeMem the samples only after every write that used them has been collected.

## Complete example

Allocates a stereo pair, plays a decaying one-shot "blip" on one channel, then starts a 440 Hz
square wave on both channels in sync, slides its pitch up while fading it out, and cleans up.

```c
/* playsample.c -- audio.device: allocate a stereo pair, play a one-shot and a looping
   sample, bend period/volume live, then stop and free everything */
#include <proto/exec.h>
#include <proto/dos.h>
#include <exec/execbase.h>
#include <exec/memory.h>
#include <graphics/gfxbase.h>
#include <devices/audio.h>
#include <dos/dos.h>
#include <inline/alib.h>                        /* BeginIO() without amiga.lib */

#define CLOCK_PAL   3546895UL                   /* Paula clock constants (ticks/s) */
#define CLOCK_NTSC  3579545UL
#define WAVE_LEN    32                          /* one cycle of a square wave (even) */
#define SHOT_LEN    4000                        /* one-shot length in bytes (even) */

struct ExecBase   *SysBase;
struct DosLibrary *DOSBase;
struct GfxBase    *GfxBase;

static UBYTE stereoPairs[] = { 3, 5, 10, 12 };  /* ch0+1, ch0+2, ch3+1, ch3+2 */
static ULONG clockConst;

/* sample rate (bytes per second) -> period, clamped to the legal range */
static UWORD PeriodFor(ULONG rate)
{
    ULONG p = clockConst / rate;
    return (UWORD)(p < 124 ? 124 : p > 65535 ? 65535 : p);
}

/* extra request sharing the device, allocation key and reply port of the opened one */
static struct IOAudio *CloneAudio(struct MsgPort *port, struct IOAudio *opened, ULONG mask)
{
    struct IOAudio *io = (struct IOAudio *)CreateIORequest(port, sizeof(struct IOAudio));
    if (io) {
        CopyMem(opened, io, sizeof(struct IOAudio));
        io->ioa_Request.io_Unit = (struct Unit *)mask;
    }
    return io;
}

/* queue a write; flags other than 0 need BeginIO (SendIO/DoIO overwrite io_Flags) */
static void StartWrite(struct IOAudio *io, BYTE *data, ULONG len, UWORD period,
                       UWORD volume, UWORD cycles)
{
    io->ioa_Request.io_Command = CMD_WRITE;
    io->ioa_Request.io_Flags   = ADIOF_PERVOL;  /* always: see the CMD_WRITE bug note */
    io->ioa_Data   = (UBYTE *)data;
    io->ioa_Length = len;
    io->ioa_Period = period;
    io->ioa_Volume = volume;
    io->ioa_Cycles = cycles;                    /* 0 = loop until stopped */
    BeginIO((struct IORequest *)io);
}

/* synchronous multi-channel command on the control request */
static BYTE ChanCmd(struct IOAudio *ctl, ULONG mask, UWORD cmd)
{
    ctl->ioa_Request.io_Unit    = (struct Unit *)mask;  /* commands overwrite io_Unit */
    ctl->ioa_Request.io_Command = cmd;
    return DoIO((struct IORequest *)ctl);
}

int main(void)
{
    struct MsgPort *port = NULL;
    struct IOAudio *opened = NULL, *ctl = NULL, *side03 = NULL, *side12 = NULL;
    BYTE *wave = NULL, *shot = NULL;
    BOOL  deviceOpen = FALSE;
    ULONG chans, i;
    int   rc = RETURN_FAIL;

    SysBase = *((struct ExecBase **)4UL);
    DOSBase = (struct DosLibrary *)OpenLibrary((CONST_STRPTR)"dos.library", 37);
    GfxBase = (struct GfxBase *)OpenLibrary((CONST_STRPTR)"graphics.library", 37);
    if (!DOSBase || !GfxBase)
        goto cleanup;
    /* Paula's clock follows the crystal: V39+ REALLY_PAL reports the crystal even when the
       boot menu switched the display mode; older systems only have PAL */
    if (GfxBase->LibNode.lib_Version >= 39)
        clockConst = (GfxBase->DisplayFlags & REALLY_PAL) ? CLOCK_PAL : CLOCK_NTSC;
    else
        clockConst = (GfxBase->DisplayFlags & PAL) ? CLOCK_PAL : CLOCK_NTSC;

    /* 1. samples in chip RAM (AllocMem blocks are word-aligned) */
    wave = (BYTE *)AllocMem(WAVE_LEN, MEMF_CHIP);
    shot = (BYTE *)AllocMem(SHOT_LEN, MEMF_CHIP);
    if (!wave || !shot)
        goto cleanup;
    for (i = 0; i < WAVE_LEN; i++)
        wave[i] = (i < WAVE_LEN / 2) ? 90 : -90;
    for (i = 0; i < SHOT_LEN; i++) {            /* decaying square "blip" */
        LONG amp = 127 - (LONG)(i * 127 / SHOT_LEN);
        shot[i] = (BYTE)(((i / 10) & 1) ? amp : -amp);
    }

    /* 2. open the device and allocate a stereo pair in one go (never waits) */
    port = CreateMsgPort();
    if (port)
        opened = (struct IOAudio *)CreateIORequest(port, sizeof(struct IOAudio));
    if (!opened)
        goto cleanup;
    opened->ioa_Request.io_Message.mn_Node.ln_Pri = 0;  /* allocation precedence */
    opened->ioa_AllocKey = 0;                           /* 0 = give me a new key */
    opened->ioa_Data     = stereoPairs;
    opened->ioa_Length   = sizeof(stereoPairs);
    if (OpenDevice((CONST_STRPTR)AUDIONAME, 0, (struct IORequest *)opened, 0) != 0) {
        PutStr((CONST_STRPTR)"No free stereo pair\n");  /* IOERR_OPENFAIL or ADIOERR_ALLOCFAILED */
        goto cleanup;
    }
    deviceOpen = TRUE;
    chans = (ULONG)opened->ioa_Request.io_Unit;         /* e.g. 3 = channels 0 and 1 */

    ctl    = CloneAudio(port, opened, chans);           /* control commands */
    side03 = CloneAudio(port, opened, chans & 0x9);     /* our channel 0 or 3 */
    side12 = CloneAudio(port, opened, chans & 0x6);     /* our channel 1 or 2 */
    if (!ctl || !side03 || !side12)
        goto cleanup;

    /* 3. one-shot: 8 kHz, full volume, once; WaitIO returns when it has played */
    StartWrite(side03, shot, SHOT_LEN, PeriodFor(8000), 64, 1);
    if (WaitIO((struct IORequest *)side03) != 0)
        PutStr((CONST_STRPTR)"one-shot failed\n");

    /* 4. looping tone on both channels, started in sync: stop, queue, start */
    ChanCmd(ctl, chans, CMD_STOP);
    StartWrite(side03, wave, WAVE_LEN, PeriodFor(440 * WAVE_LEN), 40, 0);
    StartWrite(side12, wave, WAVE_LEN, PeriodFor(440 * WAVE_LEN), 40, 0);
    ChanCmd(ctl, chans, CMD_START);

    /* 5. slide pitch up and fade out while it plays */
    for (i = 0; i < 40 && !(SetSignal(0, SIGBREAKF_CTRL_C) & SIGBREAKF_CTRL_C); i++) {
        ctl->ioa_Period = PeriodFor((440 + i * 11) * WAVE_LEN);
        ctl->ioa_Volume = (UWORD)(40 - i);
        ChanCmd(ctl, chans, ADCMD_PERVOL);              /* immediate: io_Flags cleared by DoIO */
        Delay(2);
    }

    /* 6. stop the loops: abort and ALWAYS collect */
    AbortIO((struct IORequest *)side03);
    AbortIO((struct IORequest *)side12);
    WaitIO((struct IORequest *)side03);                 /* io_Error = IOERR_ABORTED */
    WaitIO((struct IORequest *)side12);
    rc = RETURN_OK;

cleanup:
    if (deviceOpen)
        CloseDevice((struct IORequest *)opened);        /* frees the channels of this key */
    DeleteIORequest(side12);
    DeleteIORequest(side03);
    DeleteIORequest(ctl);
    DeleteIORequest(opened);
    DeleteMsgPort(port);
    if (shot) FreeMem(shot, SHOT_LEN);                  /* only after nothing plays them */
    if (wave) FreeMem(wave, WAVE_LEN);
    CloseLibrary((struct Library *)GfxBase);
    CloseLibrary((struct Library *)DOSBase);
    return rc;
}
```

## Common mistakes

- **SendIO or DoIO for CMD_WRITE:** `ADIOF_PERVOL` is wiped, so the period and volume never load
  (silence or a wrong pitch). Use BeginIO.
- **Sample in fast RAM**, odd length, or `ioa_Length` given in words (it counts bytes).
- **Writing without an allocation** (key 0, or a key from another open): `ADIOERR_NOALLOCATION`.
- **Sending commands through the opened request** and then closing it with a changed `io_Unit`:
  some channels are never freed. Use copies.
- **Reusing a playing write request** for a second write. One pending write per request.
- **Aborting without WaitIO**, or freeing the sample or deleting the request while the write is
  still out.
- **Stopping channels with CMD_STOP and never starting, resetting or flushing them:** the queued
  writes never return.
- **Using the wrong clock constant** (PAL vs NTSC) for the period.
- **Poking `AUDx`/`DMACON`/`ADKCON` audio bits or the audio interrupt vectors** while
  audio.device owns the channels. Allocate and lock them first
  ([direct Paula access](index.md#audiodevice-and-direct-paula-access)).
- **Unsuitable precedence:** 127 for a background loop starves every other program, while -128 for
  a sound that must be heard gets stolen by anything.

**See also:** [CMD_WRITE](commands.md#cmd_write), [ADCMD_ALLOCATE](commands.md#adcmd_allocate), [ADCMD_PERVOL](commands.md#adcmd_pervol), [CMD_STOP](commands.md#cmd_stop), [ADCMD_LOCK](commands.md#adcmd_lock), [exec I/O](../exec/io.md)
