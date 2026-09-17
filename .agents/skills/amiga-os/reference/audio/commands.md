# audio.device: commands

Every command goes in `io_Command` of a `struct IOAudio` whose `io_Device` and `ioa_AllocKey`
come from OpenDevice or ADCMD_ALLOCATE (directly, or copied into another request). `io_Unit` holds
the channel mask; a wrong key gives `ADIOERR_NOALLOCATION` (-10). Unused `io_Flags` bits must be 0.
Commands that use `ADIOF_` flags must be sent with BeginIO, because DoIO and SendIO overwrite
`io_Flags` (see [sending commands](index.md#sending-commands)). Entries follow a program's
workflow: allocate, play, control, reset.

## ADCMD_ALLOCATE
`io_Command` = `ADCMD_ALLOCATE` (32) · audio.device · request: `struct IOAudio`

Allocate one of several channel combinations, stealing lower-precedence ones if needed.

- **In:** `ln_Pri` = precedence -128..127; `ioa_AllocKey` = 0 for a new key or a key the device
  gave you; `ioa_Data` = UBYTE array of channel masks; `ioa_Length` = entries (0..16, 0 always
  succeeds); `io_Flags`: `ADIOF_NOWAIT` (fail instead of waiting), `IOF_QUICK` (no reply when it
  completes synchronously); `mn_ReplyPort`.
- **Out:** `io_Unit` = allocated mask (0 on failure); `ioa_AllocKey` = the key; `io_Error` = 0 or
  `ADIOERR_ALLOCFAILED` (-11); `IOF_QUICK` cleared in `io_Flags` if it went asynchronous.

It picks the first combination that needs no stealing, otherwise the one that steals the
lowest-precedence channels. It never takes a channel of equal or higher precedence. If a victim
channel is locked, that lock request is replied with `ADIOERR_CHANNELSTOLEN` and this allocation
waits until the channel is freed. On success the channels are reset (CMD_RESET) and stamped with
the key and precedence. It completes synchronously when it succeeds without locked victims, or
fails with `ADIOF_NOWAIT`. Otherwise it is asynchronous: a failed allocation without NOWAIT waits
until ADCMD_FREE or ADCMD_SETPREC makes room.

### Example
```c
/* ioa: opened with ioa_Length = 0, so it already holds a key */
static UBYTE anyChannel[] = { 1, 2, 4, 8 };
ULONG chan = 0;

ioa->ioa_Request.io_Command = ADCMD_ALLOCATE;
ioa->ioa_Request.io_Flags   = ADIOF_NOWAIT | IOF_QUICK;
ioa->ioa_Request.io_Message.mn_Node.ln_Pri = -60;     /* sound-effect level */
ioa->ioa_Data   = anyChannel;
ioa->ioa_Length = sizeof(anyChannel);
BeginIO((struct IORequest *)ioa);                     /* <inline/alib.h>: keeps io_Flags */
if (!(ioa->ioa_Request.io_Flags & IOF_QUICK))
    WaitIO((struct IORequest *)ioa);                  /* went asynchronous: wait for it */
if (ioa->ioa_Request.io_Error == 0)
    chan = (ULONG)ioa->ioa_Request.io_Unit;
```

### Gotchas
- Not from interrupt code.
- DoIO/SendIO would clear `ADIOF_NOWAIT`: a busy system then leaves you waiting indefinitely.
- Once you own channels you must free them ([ADCMD_FREE](#adcmd_free) or CloseDevice), unless
  they were stolen.
- Before writing Paula registers directly, [ADCMD_LOCK](#adcmd_lock) the channels or allocate
  at `ADALLOC_MAXPREC` so nobody can steal them mid-use.
- The autodoc text calls the error `IOERR_ALLOCFAILED` and the flag `ADIOF_QUICK`; neither name
  exists. Use `ADIOERR_ALLOCFAILED` and `IOF_QUICK`.

**See also:** [ADCMD_FREE](#adcmd_free), [ADCMD_SETPREC](#adcmd_setprec), [ADCMD_LOCK](#adcmd_lock), [allocation model](index.md#channel-allocation-model)

## ADCMD_FREE
`io_Command` = `ADCMD_FREE` (9) · audio.device · request: `struct IOAudio`

Release allocated channels: reset them and make them available to other allocations.

- **In:** `io_Unit` = channels to free; `ioa_AllocKey`; `io_Flags` 0 or `IOF_QUICK`.
- **Out:** `io_Unit` = channels actually freed; `io_Error` = 0 or `ADIOERR_NOALLOCATION`.

For each channel with a matching key it runs CMD_RESET, changes the channel's key and releases it.
A locked channel is unlocked, and the lock request is replied once none of its channels remain.
Allocations waiting for the channel are then retried. Synchronous.

### Example
```c
ctl->ioa_Request.io_Command = ADCMD_FREE;
ctl->ioa_Request.io_Unit    = (struct Unit *)chans;
DoIO((struct IORequest *)ctl);
```

### Gotchas
- Not from interrupt code.
- Stop using the hardware first: the reset silences the channel and clears its registers.
- If the channels were locked, collect the replied lock request (WaitIO) before deleting it.
- CloseDevice does the same for the channels in the closing request's `io_Unit`.
- On stolen channels it just returns `ADIOERR_NOALLOCATION`; that is harmless.

**See also:** [ADCMD_ALLOCATE](#adcmd_allocate), [ADCMD_LOCK](#adcmd_lock), [CMD_RESET](#cmd_reset)

## ADCMD_SETPREC
`io_Command` = `ADCMD_SETPREC` (10) · audio.device · request: `struct IOAudio`

Change the allocation precedence of channels you own.

- **In:** `ln_Pri` = new precedence (-128..127); `io_Unit`; `ioa_AllocKey`; `io_Flags` 0 or
  `IOF_QUICK`.
- **Out:** `io_Unit` = channels changed; `io_Error` = 0 or `ADIOERR_NOALLOCATION`.

After the change, waiting allocations that now outrank the channel are retried. Synchronous.

### Example
```c
/* drop a finished sound effect to background level so others may steal it */
ctl->ioa_Request.io_Command = ADCMD_SETPREC;
ctl->ioa_Request.io_Unit    = (struct Unit *)chan;
ctl->ioa_Request.io_Message.mn_Node.ln_Pri = -100;
DoIO((struct IORequest *)ctl);
```

### Gotchas
- Not from interrupt code.
- `ADALLOC_MAXPREC` (127) makes the channels unstealable, so later allocations of them fail. To
  make would-be thieves wait instead, use [ADCMD_LOCK](#adcmd_lock).

**See also:** [ADCMD_ALLOCATE](#adcmd_allocate), [ADCMD_LOCK](#adcmd_lock)

## ADCMD_LOCK
`io_Command` = `ADCMD_LOCK` (13) · audio.device · request: `struct IOAudio`

Keep allocated channels from being stolen until you free them.

- **In:** `io_Unit` = channels to lock; `ioa_AllocKey`; `io_Flags` = 0; `mn_ReplyPort`.
- **Out (when replied):** `io_Unit` = channels still locked and not freed; `io_Error` = 0 (all
  locked channels were freed), `ADIOERR_CHANNELSTOLEN` (-12, a higher-precedence allocation wants
  them) or `ADIOERR_NOALLOCATION` (wrong key; nothing locked, replied at once).

With a correct key the request stays pending. It is replied only when all its channels have been
freed, or when an allocation tries to steal one. Higher-precedence allocations, even
`ADIOF_NOWAIT` ones, wait while the lock holds.

### Example
```c
/* lock: a spare request copied from the opened one, io_Unit = chans */
lock->ioa_Request.io_Command = ADCMD_LOCK;
SendIO((struct IORequest *)lock);               /* SendIO clears io_Flags, as required */

/* main loop: include the port signal in Wait() */
if (CheckIO((struct IORequest *)lock) &&
    lock->ioa_Request.io_Error == ADIOERR_CHANNELSTOLEN) {
    StopMyPaulaCode();                          /* then free the channels right away */
}

/* exit: free, then collect the lock */
ChanCmd(ctl, chans, ADCMD_FREE);                /* DoIO on another request */
WaitIO((struct IORequest *)lock);
```

### Gotchas
- Never DoIO a lock: it does not complete until the channels are freed.
- On `ADIOERR_CHANNELSTOLEN` free the channels promptly: the thief is blocked until you do. Never
  make that free wait on another allocation (deadlock).
- A lock request is pending I/O. Free the channels and WaitIO it before CloseDevice and
  DeleteIORequest.
- Not from interrupt code.

**See also:** [ADCMD_FREE](#adcmd_free), [ADCMD_SETPREC](#adcmd_setprec), [direct Paula access](index.md#audiodevice-and-direct-paula-access)

## CMD_WRITE
`io_Command` = `CMD_WRITE` (3) · audio.device · request: `struct IOAudio`

Play a sample on one channel, repeating it a given number of times.

- **In:** `io_Unit` = channel (lowest set bit is used); `ioa_AllocKey`; `ioa_Data` = signed 8-bit
  sample in chip RAM, word-aligned; `ioa_Length` = bytes, even, 2..131072; `ioa_Cycles` = play
  count 1..65535, 0 = until stopped; `io_Flags`: `ADIOF_PERVOL` (load `ioa_Period` 124..65535 and
  `ioa_Volume` 0..64), `ADIOF_WRITEMESSAGE` (reply `ioa_WriteMsg` when playback starts).
- **Out:** `io_Error` = 0 (all cycles played), `IOERR_ABORTED` (-2: AbortIO, flush or channel
  stolen) or `ADIOERR_NOALLOCATION`; `io_Unit` = channel written; `IOF_QUICK` cleared on success.

Writes to a busy or stopped channel queue up and play in order. The request is replied after its
last cycle. Period = clock constant / samples per second, with clock 3546895 (PAL) or 3579545
(NTSC). The fixed anti-aliasing filter only works well for periods below roughly 300-500,
depending on the waveform.

### Example
```c
/* io: copy of the opened request with io_Unit = one channel */
io->ioa_Request.io_Command = CMD_WRITE;
io->ioa_Request.io_Flags   = ADIOF_PERVOL;
io->ioa_Data   = (UBYTE *)sample;               /* AllocMem(len, MEMF_CHIP) */
io->ioa_Length = len;                           /* bytes, even */
io->ioa_Period = (UWORD)(3546895 / 11025);      /* PAL, 11025 Hz */
io->ioa_Volume = 64;
io->ioa_Cycles = 1;                             /* one-shot */
BeginIO((struct IORequest *)io);
/* ... later, or right away to block: */
if (WaitIO((struct IORequest *)io) != 0)
    PutStr((CONST_STRPTR)"write failed or was aborted\n");
```

```asm
        move.l  audioreq,a1
        move.w  #CMD_WRITE,IO_COMMAND(a1)
        move.b  #ADIOF_PERVOL,IO_FLAGS(a1)
        move.l  #sample,ioa_Data(a1)            ; chip RAM (bss_c/data_c section)
        move.l  #SAMPLE_LEN,ioa_Length(a1)      ; bytes, even
        move.w  #3546895/11025,ioa_Period(a1)   ; PAL 11025 Hz
        move.w  #64,ioa_Volume(a1)
        move.w  #1,ioa_Cycles(a1)
        move.l  a6,-(sp)
        move.l  IO_DEVICE(a1),a6
        jsr     DEV_BEGINIO(a6)                 ; BeginIO: io_Flags kept
        move.l  (sp)+,a6
        move.l  4.w,a6
        move.l  audioreq,a1
        jsr     _LVOWaitIO(a6)                  ; D0 = io_Error
```

### Gotchas
- Use BeginIO: SendIO/DoIO clear `ADIOF_PERVOL`, and the period and volume are then not loaded.
- Autodoc BUG: when a write starts right after a previous write was stopped, the new data pointer
  and length may not be loaded unless `ADIOF_PERVOL` is set. Always set it.
- `ioa_Length` counts **bytes** (the AUDxLEN register counts words) and must be even. The sample
  must be in chip RAM and must not be freed until the write has been replied.
- One request plays on one channel: a stereo sound needs two requests. A request cannot be reused
  until its reply is collected.
- `ADIOF_WRITEMESSAGE`: `ioa_WriteMsg` is replied like any message, so give it a valid
  `mn_ReplyPort` and GetMsg it there.
- The autodoc allows periods up to 65536, which does not fit the UWORD `ioa_Period`: the real
  maximum is 65535.
- Not from interrupt code at level 5 or higher.

**See also:** [ADCMD_PERVOL](#adcmd_pervol), [ADCMD_FINISH](#adcmd_finish), [CMD_STOP](#cmd_stop), [CMD_FLUSH](#cmd_flush), [playing samples](playing-samples.md)

## ADCMD_PERVOL
`io_Command` = `ADCMD_PERVOL` (12) · audio.device · request: `struct IOAudio`

Change period and volume of the writes currently playing on the selected channels.

- **In:** `io_Unit`; `ioa_AllocKey`; `ioa_Period` (124..65535); `ioa_Volume` (0..64); `io_Flags`:
  `ADIOF_SYNCCYCLE` = apply at the end of the current cycle, clear = apply immediately.
- **Out:** `io_Unit` = channels changed; `io_Error` = 0 or `ADIOERR_NOALLOCATION`.

It changes only the write in progress; queued writes load their own values (`ADIOF_PERVOL`).
Synchronous.

### Example
```c
/* immediate pitch/volume change on both channels of a stereo pair */
ctl->ioa_Request.io_Command = ADCMD_PERVOL;
ctl->ioa_Request.io_Unit    = (struct Unit *)chans;
ctl->ioa_Period = newPeriod;
ctl->ioa_Volume = newVolume;
DoIO((struct IORequest *)ctl);                  /* DoIO clears SYNCCYCLE: immediate */

/* change at the end of the cycle instead */
ctl->ioa_Request.io_Unit  = (struct Unit *)chans;
ctl->ioa_Request.io_Flags = ADIOF_SYNCCYCLE | IOF_QUICK;
BeginIO((struct IORequest *)ctl);
if (!(ctl->ioa_Request.io_Flags & IOF_QUICK))
    WaitIO((struct IORequest *)ctl);
```

### Gotchas
- Nothing happens on a channel with no write in progress.
- Not from interrupt code at level 5 or higher.

**See also:** [CMD_WRITE](#cmd_write), [ADCMD_WAITCYCLE](#adcmd_waitcycle)

## ADCMD_FINISH
`io_Command` = `ADCMD_FINISH` (11) · audio.device · request: `struct IOAudio`

End the writes in progress, immediately or at the end of the current cycle.

- **In:** `io_Unit`; `ioa_AllocKey`; `io_Flags`: `ADIOF_SYNCCYCLE` = finish at the end of the
  cycle, clear = now.
- **Out:** `io_Unit` = channels finished; `io_Error` = 0 or `ADIOERR_NOALLOCATION`.

The ended write is replied to its sender. Synchronous for the FINISH request itself.

### Example
```c
/* let a looping sample reach its end, then stop (no mid-waveform click) */
ctl->ioa_Request.io_Command = ADCMD_FINISH;
ctl->ioa_Request.io_Unit    = (struct Unit *)chan;
ctl->ioa_Request.io_Flags   = ADIOF_SYNCCYCLE | IOF_QUICK;
BeginIO((struct IORequest *)ctl);
if (!(ctl->ioa_Request.io_Flags & IOF_QUICK))
    WaitIO((struct IORequest *)ctl);
WaitIO((struct IORequest *)loopWrite);          /* collect the finished write */
```

### Gotchas
- It ends only the current write. Queued writes on the channel presumably start next
  (unverified); use [CMD_FLUSH](#cmd_flush) to drop everything.
- The `io_Error` of the finished write request is not documented (unverified): do not treat a
  non-zero value there as a failure.
- Not from interrupt code at level 5 or higher.

**See also:** [CMD_WRITE](#cmd_write), [CMD_FLUSH](#cmd_flush)

## ADCMD_WAITCYCLE
`io_Command` = `ADCMD_WAITCYCLE` (14) · audio.device · request: `struct IOAudio`

Wait until the write playing on one channel completes its current cycle.

- **In:** `io_Unit` = channel (lowest set bit used); `ioa_AllocKey`; `io_Flags` 0 or `IOF_QUICK`.
- **Out:** `io_Error` = 0, `IOERR_ABORTED` (AbortIO or channel stolen) or
  `ADIOERR_NOALLOCATION`; `io_Unit`; `IOF_QUICK` cleared if it had to wait.

It replies immediately when the channel is not playing. Use it to change sounds or parameters in
step with the waveform loop.

### Example
```c
wait->ioa_Request.io_Command = ADCMD_WAITCYCLE;
wait->ioa_Request.io_Unit    = (struct Unit *)chan;
DoIO((struct IORequest *)wait);                 /* returns at the end of the cycle */
```

### Gotchas
- Use a request of its own: the write request is still busy playing.
- Not from interrupt code at level 5 or higher.
- The autodoc INPUTS call it `CMD_WAITCYCLE`; the include name is `ADCMD_WAITCYCLE` (14).

**See also:** [ADCMD_PERVOL](#adcmd_pervol), [ADCMD_FINISH](#adcmd_finish)

## CMD_STOP
`io_Command` = `CMD_STOP` (6) · audio.device · request: `struct IOAudio`

Pause the selected channels at once; new writes queue until CMD_START or CMD_RESET.

- **In:** `io_Unit`; `ioa_AllocKey`; `io_Flags` 0 or `IOF_QUICK`.
- **Out:** `io_Unit` = channels stopped; `io_Error` = 0 or `ADIOERR_NOALLOCATION`.

Synchronous. Together with CMD_START it lets several channels begin playing at the same moment.

### Example
```c
/* start a stereo pair in phase: stop, queue both writes, start */
ChanCmd(ctl, chans, CMD_STOP);
StartWrite(side03, wave, WAVE_LEN, period, 40, 0);
StartWrite(side12, wave, WAVE_LEN, period, 40, 0);
ChanCmd(ctl, chans, CMD_START);
```
(`ChanCmd` and `StartWrite` are defined in [playing samples](playing-samples.md#complete-example).)

### Gotchas
- A stopped channel holds its writes forever: always pair it with CMD_START, CMD_RESET or
  CMD_FLUSH.
- Not from interrupt code at level 5 or higher.

**See also:** [CMD_START](#cmd_start), [CMD_WRITE](#cmd_write)

## CMD_START
`io_Command` = `CMD_START` (7) · audio.device · request: `struct IOAudio`

Resume stopped channels, starting all selected channels at the same moment.

- **In:** `io_Unit`; `ioa_AllocKey`; `io_Flags` 0 or `IOF_QUICK`.
- **Out:** `io_Unit` = channels started; `io_Error` = 0 or `ADIOERR_NOALLOCATION`.

It only affects channels that were stopped with CMD_STOP. Starting them together keeps channels
that play the same waveform in step, which minimises distortion where their outputs mix.
Synchronous. See the example under [CMD_STOP](#cmd_stop).

### Gotchas
- Not from interrupt code at level 5 or higher.

**See also:** [CMD_STOP](#cmd_stop), [CMD_WRITE](#cmd_write)

## CMD_FLUSH
`io_Command` = `CMD_FLUSH` (8) · audio.device · request: `struct IOAudio`

Abort every playing and queued write, and every pending ADCMD_WAITCYCLE, on the channels.

- **In:** `io_Unit`; `ioa_AllocKey`; `io_Flags` 0 or `IOF_QUICK`.
- **Out:** `io_Unit` = channels flushed; `io_Error` = 0 or `ADIOERR_NOALLOCATION`.

The aborted requests are replied to their owners (their `io_Error` is presumably `IOERR_ABORTED`,
unverified). Synchronous.

### Example
```c
ChanCmd(ctl, chans, CMD_FLUSH);
WaitIO((struct IORequest *)side03);             /* collect every aborted write */
WaitIO((struct IORequest *)side12);
```

### Gotchas
- Each flushed request still has to be collected before reuse or DeleteIORequest.
- Not from interrupt code at level 5 or higher.

**See also:** [ADCMD_FINISH](#adcmd_finish), [CMD_RESET](#cmd_reset)

## CMD_RESET
`io_Command` = `CMD_RESET` (1) · audio.device · request: `struct IOAudio`

Return channels to a known state.

- **In:** `io_Unit`; `ioa_AllocKey`; `io_Flags` 0 or `IOF_QUICK`.
- **Out:** `io_Unit` = channels reset; `io_Error` = 0 or `ADIOERR_NOALLOCATION`.

For each channel it clears the audio hardware registers and attach (modulation) bits, sets the
audio interrupt vector, flushes all pending I/O as CMD_FLUSH does, and clears a CMD_STOP.
Synchronous. ADCMD_ALLOCATE and ADCMD_FREE run it on the channels they hand over.

### Example
```c
/* after poking Paula directly on channels you own */
ChanCmd(ctl, chans, CMD_RESET);
```

### Gotchas
- Aborted writes must still be collected (see CMD_FLUSH).
- Not from interrupt code at level 5 or higher.

**See also:** [CMD_FLUSH](#cmd_flush), [ADCMD_FREE](#adcmd_free), [direct Paula access](index.md#audiodevice-and-direct-paula-access)

## CMD_READ
`io_Command` = `CMD_READ` (2) · audio.device · request: `struct IOAudio`

Find which write request is currently playing on a channel.

- **In:** `io_Unit` = channel (lowest set bit used); `ioa_AllocKey`; `io_Flags` 0 or `IOF_QUICK`.
- **Out:** `ioa_Data` = pointer to the IOAudio being played, or 0 when idle; `io_Unit`;
  `io_Error` = 0 or `ADIOERR_NOALLOCATION`.

Synchronous.

### Example
```c
ctl->ioa_Request.io_Command = CMD_READ;
ctl->ioa_Request.io_Unit    = (struct Unit *)chan;
if (DoIO((struct IORequest *)ctl) == 0 && ctl->ioa_Data == NULL)
    PutStr((CONST_STRPTR)"channel idle\n");
```

### Gotchas
- The result is a request pointer typed `UBYTE *`: cast it to `struct IOAudio *`, and treat it as
  read-only.

**See also:** [CMD_WRITE](#cmd_write)

## CMD_CLEAR
`io_Command` = `CMD_CLEAR` (5) · audio.device · request: `struct IOAudio`

No operation for audio (there are no caches); it only checks the allocation key.

- **In:** `io_Unit`; `ioa_AllocKey`; `io_Flags` 0 or `IOF_QUICK`.
- **Out:** `io_Unit` = channels with a matching key; `io_Error` = 0 or `ADIOERR_NOALLOCATION`.

Synchronous. It can serve as a cheap "do I still own these channels?" test.

**See also:** [CMD_UPDATE](#cmd_update)

## CMD_UPDATE
`io_Command` = `CMD_UPDATE` (4) · audio.device · request: `struct IOAudio`

No operation for audio (there are no buffers to flush); it only checks the allocation key.

- **In:** `io_Unit`; `ioa_AllocKey`; `io_Flags` 0 or `IOF_QUICK`.
- **Out:** `io_Unit` = channels with a matching key; `io_Error` = 0 or `ADIOERR_NOALLOCATION`.

Synchronous.

**See also:** [CMD_CLEAR](#cmd_clear)
