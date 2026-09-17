# AHI low-level playback

How to drive AHI's library API correctly: open, allocate, load, play, time from a
PlayerFunc, and shut down in the right order. Entries: [functions.md](../functions.md);
tags: [tags.md](../tags.md).

## The flow

The fixed order of calls for a low-level AHI program.

1. `CreateMsgPort()` + `CreateIORequest(port, sizeof(struct AHIRequest))`, set
   `ahir_Version`, `OpenDevice(AHINAME, AHI_NO_UNIT, req, 0)`.
2. `AHIBase = req->ahir_Std.io_Device`.
3. `AHI_AllocAudioA`: mode ID, mix rate, channels, sounds, hooks. Query the real rate
   with `AHIC_MixFreq_Query`.
4. `AHI_LoadSound` each sample (`AHIST_SAMPLE`) or stream buffer (`AHIST_DYNAMICSAMPLE`).
5. `AHI_ControlAudioA(AHIC_Play, TRUE)`: PlayerFunc starts, output is silence.
6. Per note: `AHI_SetFreq` + `AHI_SetVol` + `AHI_SetSound` (or `AHI_PlayA`).
7. Stop: `AHI_ControlAudioA(AHIC_Play, FALSE)`, cancel effects.
8. `AHI_FreeAudio` (unloads all sounds), free sample memory.
9. `CloseDevice`, `DeleteIORequest`, `DeleteMsgPort`.

Steps 3-8 must all be done by the same task. Keep multitasking enabled throughout.

## Opening the device for library use

Get `AHIBase` by opening unit `AHI_NO_UNIT` and reading `io_Device`.

```c
struct Library    *AHIBase;
struct MsgPort    *ahiPort;
struct AHIRequest *ahiReq;
BOOL               ahiOpen;

BOOL openAHI(UWORD version)
{
    if (!(ahiPort = CreateMsgPort()))
        return FALSE;
    if (!(ahiReq = (struct AHIRequest *)CreateIORequest(ahiPort, sizeof(struct AHIRequest))))
        return FALSE;
    ahiReq->ahir_Version = version;                       /* 4, or 6 for V6 features */
    if (OpenDevice(AHINAME, AHI_NO_UNIT, (struct IORequest *)ahiReq, 0) != 0)
        return FALSE;
    ahiOpen = TRUE;
    AHIBase = (struct Library *)ahiReq->ahir_Std.io_Device;
    return TRUE;
}

void closeAHI(void)                                       /* safe after partial open */
{
    if (ahiOpen) CloseDevice((struct IORequest *)ahiReq);
    if (ahiReq)  DeleteIORequest((struct IORequest *)ahiReq);
    if (ahiPort) DeleteMsgPort(ahiPort);
    ahiOpen = FALSE; ahiReq = NULL; ahiPort = NULL; AHIBase = NULL;
}
```

`devices/ahi.i` provides `OPENAHI <version>` (returns the base in D0 or 0) and
`CLOSEAHI` macros. Caveats from reading their source: they embed their variables
and the name string in the code where they are expanded (use each once per source
file); if CreateMsgPort/CreateIORequest fails, the state they leave makes CLOSEAHI
call CloseDevice on a NULL request; if OpenDevice fails, CLOSEAHI never deletes the
IORequest. Writing the open/close by hand (see the complete asm example) avoids both.

## Allocating the hardware

Choose a mode, channel count and timing hooks with AHI_AllocAudioA.

- Mode: `AHI_DEFAULT_ID` + `AHI_DEFAULT_FREQ` for zero configuration, or a saved
  ID/rate from AHI_AudioRequestA ([audio-modes topic](audio-modes.md)).
- `AHIA_Channels`: CPU cost rises with channels; in V4-style mixing each channel also
  gets quieter.
- `AHIA_Sounds`: number of sample slots you will AHI_LoadSound.
- Music timing: `AHIA_PlayerFunc`, `AHIA_PlayerFreq`, `AHIA_MinPlayerFreq`,
  `AHIA_MaxPlayerFreq` together. Use this instead of VBlank/CIA timers: it is the
  only way to be sure no mixing happens between your Set* calls, and the only timing
  that works in non-realtime (render-to-disk) modes.
- After success, read the real rate: `AHI_ControlAudio(actrl, AHIC_MixFreq_Query, (ULONG)&mixfreq, TAG_DONE)`.

## Loading sounds

Register sample memory with AHI_LoadSound before playing it.

- `struct AHISampleInfo { ahisi_Type; ahisi_Address; ahisi_Length /* frames */ }`.
- Memory: `MEMF_PUBLIC`, never swapped; chip RAM is not required.
- `AHIST_SAMPLE`: don't modify the data until unloaded (a driver may have uploaded it).
- `AHIST_DYNAMICSAMPLE`: data you keep rewriting (software mixer output, disk
  streaming). Keep at least `AHIDB_MaxPlaySamples * Fs / Fm` frames ready ahead of
  the play position (`AHIDB_MaxPlaySamples` from AHI_GetAudioAttrsA with
  `AHI_INVALID_ID` + handle; Fs = highest playback rate; Fm = real mix rate).
- Unroll short loops (a 32-frame waveform repeated to ~1000 frames): every sound end
  costs CPU (restart, SoundFunc).
- Load important sounds first; DSP cards may have little sample RAM.

## Playing notes

Start, change and stop sounds on channels with the Set* calls.

- A channel starts only after BOTH AHI_SetSound and AHI_SetFreq; without AHI_SetVol
  it plays silently. Channels are 0 .. `AHIA_Channels`-1.
- A started sound loops forever (Offset/Length part). Stop with
  `AHI_SetSound(ch, AHI_NOSOUND, 0, 0, actrl, AHISF_IMM)`.
- Pause: `AHI_SetFreq(ch, 0, ...)`; set a rate again to resume at the same frame.
- Backwards: negative Length (needs `AHIDB_PingPong`).
- Volume/pan are Fixed: `0x10000` = 1.0; pan `0x8000` = centre.

`AHISF_IMM` rules:

| Called from | Flags |
|---|---|
| SoundFunc hook | MUST be 0: changes apply to the sound that follows |
| PlayerFunc hook | `AHISF_IMM` (now) or 0 (when the current sound ends) |
| Anywhere else (your task) | MUST be `AHISF_IMM` |

With V6 anti-click, IMM changes may wait up to `AHIA_AntiClickSamples` frames for a
zero crossing; add `AHISF_NODELAY` to start at once.

One-shots and single loops:

- In a PlayerFunc: IMM Set* calls to start, then
  `AHI_SetSound(ch, AHI_NOSOUND, 0, 0, actrl, 0)` (or a loop part) without IMM.
- From your task: `AHI_PlayA` with `AHIP_LoopSound, AHI_NOSOUND` (or `AHIP_Loop*`
  values). Several channels in one AHI_PlayA start in sync.
- Multi-segment or ping-pong loops need a SoundFunc.

## Hooks

Calling convention and toolchain setup for SoundFunc, PlayerFunc and RecordFunc.

| Register | SoundFunc | PlayerFunc | RecordFunc |
|---|---|---|---|
| A0 | `struct Hook *` | `struct Hook *` | `struct Hook *` |
| A2 | `struct AHIAudioCtrl *` | `struct AHIAudioCtrl *` | `struct AHIAudioCtrl *` |
| A1 | `struct AHISoundMessage *` (`ahism_Channel`) | undefined | `struct AHIRecordMessage *` |
| D0 on return | ignored (return 0) | ignored (return 0) | MUST be 0 |

Rules:

- Preserve D2-D7 and A2-A6. The hook may run in an interrupt, in AHI's or the
  driver's task, or in yours; the system is not single-threaded.
- Only AHI_SetVol, AHI_SetFreq, AHI_SetSound and AHI_ControlAudioA (without
  `AHIC_Play`/`AHIC_Record`) may be called. Plus interrupt-safe exec calls such as
  `Signal()`. No DOS, no allocation, no AHI_SetEffect/AHI_LoadSound.
- Be quick; small stack use.
- `ahiac_UserData` (or `h_Data`) carries your context.

Asm hook: the entry point is called directly.

```asm
playerhook:
        dc.l    0,0                     ; h_MinNode
        dc.l    playerfunc              ; h_Entry  <- AHI jumps here
        dc.l    0                       ; h_SubEntry
        dc.l    0                       ; h_Data
```

C with m68k-amiga-elf-gcc: a C function cannot take register arguments, so
`h_Entry` points to a stub that pushes A1, A2, A0 and calls `h_SubEntry` with the
normal stack convention (the stub `utility/hooks.h` describes). GCC's calling
convention already preserves D2-D7/A2-A6.

```c
#include <utility/hooks.h>

__asm__(
    "    .text\n"
    "    .balign 2\n"
    "    .globl ahiHookEntry\n"
    "ahiHookEntry:\n"
    "    move.l %a1,-(%sp)\n"                   /* message */
    "    move.l %a2,-(%sp)\n"                   /* object = AHIAudioCtrl */
    "    move.l %a0,-(%sp)\n"                   /* hook */
    "    move.l 12(%a0),%a0\n"                  /* hook->h_SubEntry */
    "    jsr (%a0)\n"
    "    lea 12(%sp),%sp\n"
    "    rts\n");
extern ULONG ahiHookEntry(void);

static ULONG myPlayer(struct Hook *h, struct AHIAudioCtrl *actrl, APTR unused);

static struct Hook playerHook = {
    { NULL, NULL }, (HOOKFUNC)ahiHookEntry, (HOOKFUNC)myPlayer, NULL
};
```

The stub text is GAS syntax as used by top-level `__asm__` in Bartman's template;
not build-tested here (unverified). Alternatively assemble the same six
instructions with vasm and `xdef ahiHookEntry`.

## Module-player style PlayerFunc

Run a tracker-like replay routine from PlayerFunc at a fixed or tempo-driven rate.

The SDK's `PT-AHIPlay` (ProTracker replay) shows the mapping from Paula terms:

| Paula / ProTracker | AHI |
|---|---|
| 4 hardware channels | `AHIA_Channels, 4` (channels 0-3) |
| CIA/VBlank tick | PlayerFunc, `AHIA_PlayerFreq, 50<<16` |
| Tempo BPM | PlayerFreq = BPM * 2 / 5 Hz (125 BPM = 50 Hz); set via `AHI_ControlAudioA(AHIA_PlayerFreq)` inside PlayerFunc |
| Tempo range 32-255 | `AHIA_MinPlayerFreq (32*2/5)<<16`, `AHIA_MaxPlayerFreq (255*2/5)<<16` |
| Period | `AHI_SetFreq(ch, 3546895 / period, ...)` (PAL clock constant) |
| Volume 0-64 | `AHI_SetVol(ch, vol << 10, pan, ...)` |
| Hard-panned channels | PT-AHIPlay uses pan `0`, `0x10000`, `0`, `0x10000` for channels 0-3; which Paula channel is left/right is described inconsistently (see the amiga-hardware skill) |
| Sample start (AUDxLC/AUDxLEN) | `AHI_SetSound(ch, 0, offset, length, actrl, AHISF_IMM)` with all samples loaded as one sound |
| Repeat part | `AHI_SetSound(ch, 0, loopOffset, loopLength, actrl, 0)` right after (queued) |
| Length 2 (no loop) | `AHI_NOSOUND` as the queued sound |

Pattern per tick: advance the song, then for each changed channel issue
SetSound (IMM) + queued loop SetSound (flags 0) + SetFreq (IMM) + SetVol (IMM). All
calls in one PlayerFunc take effect together.

## Stopping and cleanup

Shut down in reverse order without leaks or crashes.

```c
AHI_ControlAudio(actrl, AHIC_Play, FALSE, TAG_DONE);   /* task context only */
echo.ahie_Effect = AHIET_DSPECHO | AHIET_CANCEL;       /* every effect you set */
AHI_SetEffect(&echo, actrl);
AHI_FreeAudio(actrl);                                  /* unloads all sounds */
FreeVec(sampleMem);                                    /* after the sounds are gone */
closeAHI();
```

## Complete C example

Four channels, a 50 Hz PlayerFunc plays 32 decaying notes, then signals the main task.

```c
/* ahi_notes.c - m68k-amiga-elf-gcc, AHI SDK Include/C on the include path.
   Startup code must have set SysBase. */
#include <exec/types.h>
#include <exec/memory.h>
#include <utility/hooks.h>
#include <dos/dos.h>                                  /* SIGBREAKF_* */
#include <devices/ahi.h>
#include <proto/exec.h>
#include <proto/ahi.h>

struct Library *AHIBase;

__asm__(
    "    .text\n"
    "    .balign 2\n"
    "    .globl ahiHookEntry\n"
    "ahiHookEntry:\n"
    "    move.l %a1,-(%sp)\n"
    "    move.l %a2,-(%sp)\n"
    "    move.l %a0,-(%sp)\n"
    "    move.l 12(%a0),%a0\n"
    "    jsr (%a0)\n"
    "    lea 12(%sp),%sp\n"
    "    rts\n");
extern ULONG ahiHookEntry(void);

#define CHANNELS    4
#define PLAYER_HZ   50
#define WAVE_LEN    32                                /* one cycle */
#define SND_FRAMES  (WAVE_LEN * 32)                   /* unrolled */
#define NOTE_TICKS  10
#define NUM_NOTES   32

static const UWORD     periods[8]     = { 428, 381, 339, 320, 285, 254, 226, 214 };
static const sposition pans[CHANNELS] = { 0x2000, 0xE000, 0xE000, 0x2000 };

static struct Task *mainTask;
static ULONG        tick;
static Fixed        vol[CHANNELS];

static ULONG playerFunc(struct Hook *hook, struct AHIAudioCtrl *actrl, APTR unused)
{
    ULONG t = tick++;
    UWORD ch;

    if (t % NOTE_TICKS == 0 && t / NOTE_TICKS < NUM_NOTES) {
        ULONG n = t / NOTE_TICKS;
        ch = n % CHANNELS;
        vol[ch] = 0x10000;
        AHI_SetFreq(ch, 3546895 / periods[n % 8], actrl, AHISF_IMM);
        AHI_SetVol(ch, vol[ch], pans[ch], actrl, AHISF_IMM);
        AHI_SetSound(ch, 0, 0, 0, actrl, AHISF_IMM);
    }
    for (ch = 0; ch < CHANNELS; ch++) {               /* decay envelope */
        if (vol[ch] == 0)
            continue;
        vol[ch] -= vol[ch] >> 4;
        if (vol[ch] < 0x400) {
            vol[ch] = 0;
            AHI_SetSound(ch, AHI_NOSOUND, 0, 0, actrl, AHISF_IMM);
        } else {
            AHI_SetVol(ch, vol[ch], pans[ch], actrl, AHISF_IMM);
        }
    }
    if (t == NUM_NOTES * NOTE_TICKS + PLAYER_HZ)      /* 1 s after the last note */
        Signal(mainTask, SIGBREAKF_CTRL_F);
    return 0;
}

static struct Hook playerHook = {
    { NULL, NULL }, (HOOKFUNC)ahiHookEntry, (HOOKFUNC)playerFunc, NULL
};

int main(void)
{
    struct MsgPort      *port   = NULL;
    struct AHIRequest   *req    = NULL;
    struct AHIAudioCtrl *actrl  = NULL;
    BYTE                *wave   = NULL;
    BOOL                 opened = FALSE;
    int                  rc     = 20;

    mainTask = FindTask(NULL);
    if (!(port = CreateMsgPort()))
        goto out;
    if (!(req = (struct AHIRequest *)CreateIORequest(port, sizeof(struct AHIRequest))))
        goto out;
    req->ahir_Version = 4;
    if (OpenDevice(AHINAME, AHI_NO_UNIT, (struct IORequest *)req, 0) != 0)
        goto out;
    opened  = TRUE;
    AHIBase = (struct Library *)req->ahir_Std.io_Device;

    actrl = AHI_AllocAudio(AHIA_AudioID,       AHI_DEFAULT_ID,
                           AHIA_MixFreq,       AHI_DEFAULT_FREQ,
                           AHIA_Channels,      CHANNELS,
                           AHIA_Sounds,        1,
                           AHIA_PlayerFunc,    (ULONG)&playerHook,
                           AHIA_PlayerFreq,    PLAYER_HZ << 16,
                           AHIA_MinPlayerFreq, PLAYER_HZ << 16,
                           AHIA_MaxPlayerFreq, PLAYER_HZ << 16,
                           TAG_DONE);
    if (!actrl)
        goto out;

    if (!(wave = AllocVec(SND_FRAMES, MEMF_PUBLIC)))
        goto out;
    for (ULONG i = 0; i < SND_FRAMES; i++)            /* 8-bit signed square wave */
        wave[i] = (i % WAVE_LEN) < WAVE_LEN / 2 ? 50 : -50;
    {
        struct AHISampleInfo si = { AHIST_M8S, wave, SND_FRAMES };
        if (AHI_LoadSound(0, AHIST_SAMPLE, &si, actrl) != AHIE_OK)
            goto out;
    }

    if (AHI_ControlAudio(actrl, AHIC_Play, TRUE, TAG_DONE) != AHIE_OK)
        goto out;
    Wait(SIGBREAKF_CTRL_C | SIGBREAKF_CTRL_F);        /* PlayerFunc signals the end */
    AHI_ControlAudio(actrl, AHIC_Play, FALSE, TAG_DONE);
    rc = 0;

out:
    if (actrl)  AHI_FreeAudio(actrl);                 /* also unloads sound 0 */
    if (wave)   FreeVec(wave);
    if (opened) CloseDevice((struct IORequest *)req);
    if (req)    DeleteIORequest((struct IORequest *)req);
    if (port)   DeleteMsgPort(port);
    return rc;
}
```

## Complete asm example

vasm: a PlayerFunc retriggers a one-shot 8-bit sample twice per second until Ctrl-C.

```asm
        include "exec/types.i"
        include "exec/io.i"
        include "dos/dos.i"                     ; SIGBREAKF_CTRL_C
        include "devices/ahi.i"                 ; AHI SDK Include/Asm
        include "lvo/exec_lib.i"
        include "lvo/ahi_lib.i"                 ; AHI SDK Include/Asm

        section code,code
start:  movem.l d2-d7/a2-a6,-(sp)
        move.l  4.w,a6
        jsr     _LVOCreateMsgPort(a6)
        move.l  d0,ahiport
        beq     .exit
        move.l  d0,a0
        moveq   #AHIRequest_SIZEOF,d0
        jsr     _LVOCreateIORequest(a6)
        move.l  d0,ahireq
        beq     .exit
        move.l  d0,a1
        move.w  #4,ahir_Version(a1)             ; set BEFORE OpenDevice
        lea     ahiname,a0
        move.l  #AHI_NO_UNIT,d0
        moveq   #0,d1
        jsr     _LVOOpenDevice(a6)
        tst.b   d0
        bne     .exit
        st      devopen
        move.l  ahireq,a1
        move.l  IO_DEVICE(a1),ahibase           ; AHIBase = io_Device

        move.l  ahibase,a6
        lea     alloctags,a1
        jsr     _LVOAHI_AllocAudioA(a6)
        move.l  d0,actrl
        beq     .exit
        move.l  d0,a2                           ; a2 = AHIAudioCtrl from here on
        moveq   #0,d0                           ; sound 0
        moveq   #AHIST_SAMPLE,d1
        lea     sampleinfo,a0
        jsr     _LVOAHI_LoadSound(a6)
        tst.l   d0
        bne     .exit
        lea     playtags,a1
        jsr     _LVOAHI_ControlAudioA(a6)       ; AHIC_Play TRUE
        tst.l   d0
        bne     .exit

        move.l  4.w,a6
        move.l  #SIGBREAKF_CTRL_C,d0
        jsr     _LVOWait(a6)                    ; play until Ctrl-C

        move.l  ahibase,a6
        move.l  actrl,a2
        lea     stoptags,a1
        jsr     _LVOAHI_ControlAudioA(a6)       ; AHIC_Play FALSE
.exit:  move.l  actrl,d0
        beq.s   .nofree
        move.l  ahibase,a6
        move.l  d0,a2
        jsr     _LVOAHI_FreeAudio(a6)           ; unloads the sound too
.nofree:
        move.l  4.w,a6
        tst.b   devopen
        beq.s   .noclose
        move.l  ahireq,a1
        jsr     _LVOCloseDevice(a6)
.noclose:
        move.l  ahireq,d0
        beq.s   .noreq
        move.l  d0,a0
        jsr     _LVODeleteIORequest(a6)
.noreq: move.l  ahiport,d0
        beq.s   .noport
        move.l  d0,a0
        jsr     _LVODeleteMsgPort(a6)
.noport:
        movem.l (sp)+,d2-d7/a2-a6
        moveq   #0,d0
        rts

; PlayerFunc: A0 = hook, A2 = AHIAudioCtrl, A1 undefined. Keep d2-d7/a2-a6.
playerfunc:
        movem.l d2-d4/a6,-(sp)
        move.l  ahibase,a6
        subq.w  #1,countdown
        bne.s   .done
        move.w  #25,countdown                   ; 25 ticks at 50 Hz = 0.5 s
        moveq   #0,d0                           ; channel 0
        move.l  #16574,d1                       ; Hz (3546895/214)
        moveq   #AHISF_IMM,d2
        jsr     _LVOAHI_SetFreq(a6)
        moveq   #0,d0
        move.l  #$10000,d1                      ; volume 1.0
        move.l  #$8000,d2                       ; centre
        moveq   #AHISF_IMM,d3
        jsr     _LVOAHI_SetVol(a6)
        moveq   #0,d0                           ; channel
        moveq   #0,d1                           ; sound 0
        moveq   #0,d2                           ; offset
        moveq   #0,d3                           ; length 0 = whole sound
        moveq   #AHISF_IMM,d4
        jsr     _LVOAHI_SetSound(a6)
        moveq   #0,d0
        moveq   #AHI_NOSOUND,d1                 ; queued: silence after the sample
        moveq   #0,d4                           ; no IMM (legal inside PlayerFunc)
        jsr     _LVOAHI_SetSound(a6)
.done:  movem.l (sp)+,d2-d4/a6
        moveq   #0,d0
        rts

        section data,data
ahiport:    dc.l    0
ahireq:     dc.l    0
ahibase:    dc.l    0
actrl:      dc.l    0
countdown:  dc.w    1
devopen:    dc.b    0
            even
ahiname:    AHINAME
            even
playerhook: dc.l    0,0,playerfunc,0,0          ; MinNode, h_Entry, h_SubEntry, h_Data
alloctags:  dc.l    AHIA_AudioID,AHI_DEFAULT_ID
            dc.l    AHIA_MixFreq,AHI_DEFAULT_FREQ
            dc.l    AHIA_Channels,1
            dc.l    AHIA_Sounds,1
            dc.l    AHIA_PlayerFunc,playerhook
            dc.l    AHIA_PlayerFreq,50<<16
            dc.l    AHIA_MinPlayerFreq,50<<16
            dc.l    AHIA_MaxPlayerFreq,50<<16
            dc.l    TAG_DONE
playtags:   dc.l    AHIC_Play,1,TAG_DONE
stoptags:   dc.l    AHIC_Play,0,TAG_DONE
sampleinfo: dc.l    AHIST_M8S,sample,SAMPLE_END-sample   ; type, address, frames
sample:     incbin  "hit.raw"                   ; 8-bit signed mono
SAMPLE_END:
            even
```

## Common mistakes

Errors that break low-level AHI programs.

- Calling AHI_ControlAudioA with `AHIC_Play`, AHI_SetEffect, AHI_LoadSound or
  AHI_FreeAudio from a hook.
- `AHISF_IMM` set inside a SoundFunc, or flags 0 from task code (the change never
  applies when you expect).
- Forgetting AHI_SetVol (silence) or AHI_SetFreq (sound never starts).
- Integer PlayerFreq (`50`) instead of Fixed (`50<<16`), or no Min/Max player freq.
- Channel numbers >= `AHIA_Channels`, sound IDs >= `AHIA_Sounds`.
- Offset/Length beyond the sample (the caller must keep them in range).
- Freeing sample memory before AHI_FreeAudio/AHI_UnloadSound.
- Timing music from VBlank or CIA instead of PlayerFunc, then the user selects a
  non-realtime or high-latency mode.
- Using the handle from a second task, or calling a C hook without the register stub.
- Unsigned 8-bit or little-endian 16-bit data loaded as `AHIST_M8S`/`AHIST_M16S`.
