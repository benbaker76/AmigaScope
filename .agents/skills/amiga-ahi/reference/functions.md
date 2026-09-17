# ahi.device: library functions

The low-level API. `ahi.device` is not opened with OpenLibrary: open the device
on unit `AHI_NO_UNIT`, then use the request's `io_Device` as the library base
(`AHIBase`). Asm: `jsr _LVOAHI_xxx(a6)` with `include "lvo/ahi_lib.i"` and
`include "devices/ahi.i"` from the AHI SDK `Include/Asm`; C: `#include <proto/ahi.h>`
(AHI SDK `Include/C` on the include path) and a global `struct Library *AHIBase`.
Tag lists: [tags.md](tags.md). Walkthrough: [low-level-playback topic](topics/low-level-playback.md).

Callable from interrupts and from the SoundFunc/PlayerFunc/RecordFunc hooks (the
only documented ones): AHI_SetVol, AHI_SetFreq, AHI_SetSound, and AHI_ControlAudioA
with tags other than `AHIC_Play`/`AHIC_Record`. Everything else only from the task
that called AHI_AllocAudioA.

In C tag lists (`AHI_AllocAudio(tag, data, ...)` etc.) every ti_Data is a ULONG:
cast pointers, `(ULONG)&hook`. GCC 14+ rejects the implicit pointer-to-integer
conversion.

## AHI_AllocAudioA
`struct AHIAudioCtrl * AHI_AllocAudioA(struct TagItem * tagList)` — LVO -42 (-$2A) (varargs form: AHI_AllocAudio)
Registers: tagList=A1; result in D0

Allocate the audio hardware in one mode and return the control handle.

- **tagList** — [AHIA tags](tags.md#ahia-tags):
  - `AHIA_AudioID` — mode; default `AHI_DEFAULT_ID` (user's prefs "Music unit"). Never
    hardcode other IDs: ask with AHI_AudioRequestA or AHI_BestAudioIDA and save it.
  - `AHIA_MixFreq` — Hz; default `AHI_DEFAULT_FREQ`. Rounded to a supported rate:
    read the real one with `AHIC_MixFreq_Query`.
  - `AHIA_Channels` — **required**. Too many for the mode = failure; you may get more.
  - `AHIA_Sounds` — **required**. Sound IDs 0..n-1 for AHI_LoadSound.
  - `AHIA_SoundFunc` — hook run whenever a sound starts/restarts on a channel.
  - `AHIA_PlayerFunc` + `AHIA_PlayerFreq` (Fixed Hz) + `AHIA_MinPlayerFreq` +
    `AHIA_MaxPlayerFreq` — the music "interrupt". All four together.
  - `AHIA_RecordFunc` — hook receiving sampled data (see AHI_ControlAudioA `AHIC_Record`).
  - `AHIA_UserData` — initial `ahiac_UserData`.
  - `AHIA_AntiClickSamples` (V6) — max frames a new sound may be delayed to a zero
    crossing; 0 = off; default from prefs.
- **Result** — `struct AHIAudioCtrl *`, or NULL. Handle failure gracefully.

Hooks are called with A0 = `struct Hook *`, A2 = `struct AHIAudioCtrl *`,
A1 = message (`struct AHISoundMessage *` / undefined / `struct AHIRecordMessage *`).

### Example
```c
struct AHIAudioCtrl *actrl = AHI_AllocAudio(
    AHIA_AudioID,       AHI_DEFAULT_ID,
    AHIA_MixFreq,       AHI_DEFAULT_FREQ,
    AHIA_Channels,      4,
    AHIA_Sounds,        16,
    AHIA_PlayerFunc,    (ULONG)&playerHook,
    AHIA_PlayerFreq,    50 << 16,
    AHIA_MinPlayerFreq, 50 << 16,
    AHIA_MaxPlayerFreq, 50 << 16,
    TAG_DONE);
if (actrl == NULL)
    goto no_audio;
```

```asm
        move.l  _AHIBase,a6
        lea     alloctags,a1
        jsr     _LVOAHI_AllocAudioA(a6)
        move.l  d0,_actrl
        beq     .no_audio
        ...
alloctags:
        dc.l    AHIA_AudioID,AHI_DEFAULT_ID
        dc.l    AHIA_MixFreq,AHI_DEFAULT_FREQ
        dc.l    AHIA_Channels,4
        dc.l    AHIA_Sounds,16
        dc.l    AHIA_PlayerFunc,playerhook
        dc.l    AHIA_PlayerFreq,50<<16
        dc.l    AHIA_MinPlayerFreq,50<<16
        dc.l    AHIA_MaxPlayerFreq,50<<16
        dc.l    TAG_DONE
```

### Gotchas
- Nothing is heard until AHI_ControlAudioA(`AHIC_Play`, TRUE).
- Hooks may run in an interrupt, in AHI's task or in yours: preserve D2-D7/A2-A6,
  no DOS/Intuition/allocation, return fast, `Signal()` a task for real work.
- `AHIA_PlayerFreq` is Fixed. Before V6 values below `0x10000` are treated as plain
  integers (compat kludge): always shift, `hz<<16`. Keep `MixFreq/PlayerFreq`
  <= 65535 (and > 80); 50 Hz is a sane lower limit.
- A mode with `AHIDB_Realtime` FALSE (e.g. file-save) only works if all timing comes
  from PlayerFunc; VBlank/CIA-timed players must pick realtime modes.
- Allocating takes the card exclusively (other low-level AHI programs fail) unless
  the user routed the Music unit through `device.audio` (V6).
- The handle belongs to the allocating task; don't share it.

**See also:** AHI_FreeAudio, AHI_ControlAudioA, AHI_LoadSound, AHI_BestAudioIDA

## AHI_FreeAudio
`void AHI_FreeAudio(struct AHIAudioCtrl * AudioCtrl)` — LVO -48 (-$30)
Registers: AudioCtrl=A2; no result

Release the hardware, all loaded sounds and the control handle.

- **AudioCtrl** — handle from AHI_AllocAudioA; NULL does nothing.
- Calls AHI_UnloadSound for every loaded sound. The handle is dead afterwards.

### Example
```c
AHI_ControlAudio(actrl, AHIC_Play, FALSE, TAG_DONE);
AHI_FreeAudio(actrl);           /* unloads sounds */
actrl = NULL;
FreeVec(sampleData);            /* only now may the sample memory go */
```

### Gotchas
- Cancel every effect you set (`AHIET_CANCEL`) BEFORE AHI_FreeAudio, or its memory leaks.
- Not from a hook or interrupt.

**See also:** AHI_AllocAudioA, AHI_UnloadSound, AHI_SetEffect

## AHI_ControlAudioA
`ULONG AHI_ControlAudioA(struct AHIAudioCtrl * AudioCtrl, struct TagItem * tagList)` — LVO -60 (-$3C) (varargs form: AHI_ControlAudio)
Registers: AudioCtrl=A2, tagList=A1; result in D0

Start/stop playback or recording, swap hooks, and set or query sound-card controls.

- **AudioCtrl** — handle.
- **tagList** — [AHIC tags](tags.md#ahic-tags): `AHIC_Play`, `AHIC_Record` (BOOL);
  `AHIC_MixFreq_Query` (ULONG *); `AHIC_MonitorVolume` (Fixed) / `_Query`;
  V2: `AHIC_InputGain`, `AHIC_OutputVolume` (Fixed), `AHIC_Input`, `AHIC_Output`
  (index), each with a `_Query` (pointer). Also `AHIA_SoundFunc`, `AHIA_PlayerFunc`,
  `AHIA_PlayerFreq`, `AHIA_RecordFunc`, `AHIA_UserData`.
- **Result** — `AHIE_OK` (0) or an [AHIE error](tags.md#ahie-error-codes).

When `AHIC_Play` TRUE returns, PlayerFunc is running and the driver is outputting
silence until you start sounds.

### Example
```c
ULONG mixfreq = 0;
AHI_ControlAudio(actrl, AHIC_MixFreq_Query, (ULONG)&mixfreq, TAG_DONE);
if (AHI_ControlAudio(actrl, AHIC_Play, TRUE, TAG_DONE) != AHIE_OK)
    goto fail;
/* ... */
AHI_ControlAudio(actrl, AHIC_Play, FALSE, TAG_DONE);
```

```asm
        move.l  _AHIBase,a6
        move.l  _actrl,a2
        lea     playtags,a1
        jsr     _LVOAHI_ControlAudioA(a6)
        tst.l   d0                      ; AHIE_OK?
        bne     .error
        ...
playtags:
        dc.l    AHIC_Play,1             ; asm includes have no TRUE
        dc.l    TAG_DONE
```

### Gotchas
- `AHIC_Play` / `AHIC_Record` must never be used from a hook or interrupt. The
  other tags may (e.g. change `AHIA_PlayerFreq` from PlayerFunc for tempo changes).
- New `AHIA_PlayerFreq` must stay within `AHIA_MinPlayerFreq`..`AHIA_MaxPlayerFreq`
  and change gently (50 Hz -> 5 Hz is asking for trouble).
- Half-duplex hardware: starting playback stops recording and vice versa.
- Get valid ranges for monitor/gain/volume and input/output indexes from
  AHI_GetAudioAttrsA first; equal min and max means "not adjustable".

**See also:** AHI_AllocAudioA, AHI_GetAudioAttrsA, [recording topic](topics/recording.md)

## AHI_SetVol
`void AHI_SetVol(UWORD Channel, Fixed Volume, sposition Pan, struct AHIAudioCtrl * AudioCtrl, ULONG Flags)` — LVO -66 (-$42)
Registers: Channel=D0, Volume=D1, Pan=D2, AudioCtrl=A2, Flags=D3; no result

Set a channel's volume and stereo position.

- **Channel** — 0 .. channels-1 (never out of range).
- **Volume** — Fixed, `0x10000` = 1.0 = full, `0` = silent (the sound keeps playing;
  stop it with AHI_SetSound). Negative (V4) = phase-inverted, if the driver can.
- **Pan** — sposition, `0` left, `0x8000` centre, `0x10000` right. Negative (V4) =
  surround speaker. Set a sensible value (0x8000) even in mono modes.
- **AudioCtrl** — handle.
- **Flags** — `AHISF_IMM`: take effect now; clear: at the end of the current sound.
  See the IMM rules below.

### Example
```c
AHI_SetVol(ch, vol64 << 10, 0x8000, actrl, AHISF_IMM);   /* 0..64 -> 0..1.0, centre */
```

```asm
        move.l  _AHIBase,a6
        move.l  _actrl,a2
        moveq   #0,d0                   ; channel
        move.l  #$10000,d1              ; volume 1.0
        move.l  #$8000,d2               ; pan centre
        moveq   #AHISF_IMM,d3
        jsr     _LVOAHI_SetVol(a6)
```

### Gotchas
- Safe from interrupts and hooks.
- `AHISF_IMM`: MUST be clear inside a SoundFunc, may be either inside a PlayerFunc,
  MUST be set anywhere else.
- A sound without any AHI_SetVol call plays at volume 0 (silent).
- Negative volume/pan cost more CPU; not every driver supports them (absolute value used).
- Calls made outside PlayerFunc can be split across mixing passes; only
  PlayerFunc guarantees several Set* calls land together.

**See also:** AHI_SetFreq, AHI_SetSound, AHI_PlayA, [Fixed](tags.md#fixed-sposition)

## AHI_SetFreq
`void AHI_SetFreq(UWORD Channel, ULONG Freq, struct AHIAudioCtrl * AudioCtrl, ULONG Flags)` — LVO -72 (-$48)
Registers: Channel=D0, Freq=D1, AudioCtrl=A2, Flags=D2; no result

Set a channel's playback rate in Hz.

- **Channel** — 0 .. channels-1.
- **Freq** — sample rate in Hz for this sound; `0` pauses it (it resumes from the
  same spot when set non-zero again); `AHI_MIXFREQ` = the mixing rate (V4 docs: meant
  for `AHIST_INPUT` sounds).
- **AudioCtrl** — handle.
- **Flags** — `AHISF_IMM` or 0, same rules as AHI_SetVol.

### Example
```c
/* ProTracker period -> Hz (PAL Paula clock constant, as in the SDK's PT-AHIPlay) */
AHI_SetFreq(ch, 3546895 / period, actrl, AHISF_IMM);
```

```asm
        moveq   #0,d0                   ; channel
        move.l  #22050,d1               ; Hz
        move.l  _actrl,a2
        moveq   #AHISF_IMM,d2
        jsr     _LVOAHI_SetFreq(a6)     ; a6 = AHIBase
```

### Gotchas
- Safe from interrupts and hooks; IMM rules as AHI_SetVol.
- A sound does not start until BOTH AHI_SetSound and AHI_SetFreq were called for the channel.
- The rate is per-sound playback speed, not the mixing rate: 8363 Hz sample stays 8363.

**See also:** AHI_SetSound, AHI_SetVol, AHI_PlayA

## AHI_SetSound
`void AHI_SetSound(UWORD Channel, UWORD Sound, ULONG Offset, LONG Length, struct AHIAudioCtrl * AudioCtrl, ULONG Flags)` — LVO -78 (-$4E)
Registers: Channel=D0, Sound=D1, Offset=D2, Length=D3, AudioCtrl=A2, Flags=D4; no result

Select the sound (or a part of it) a channel plays; `AHI_NOSOUND` turns the channel off.

- **Channel** — 0 .. channels-1.
- **Sound** — ID from AHI_LoadSound, or `AHI_NOSOUND` (`0xFFFF`) = channel off.
- **Offset** — first frame to play (also the first frame when playing backwards).
  Must be 0 for types other than `AHIST_SAMPLE`/`AHIST_DYNAMICSAMPLE`.
- **Length** — frames to play; 0 (with Offset 0) = whole sound; negative = backwards
  (Offset 3, Length -4 plays frames 3,2,1,0). Length 0 with Offset != 0 is illegal.
- **AudioCtrl** — handle.
- **Flags** — `AHISF_IMM` or 0 (IMM rules as AHI_SetVol); `AHISF_NODELAY` with IMM
  skips the V6 anti-click wait.

A started sound loops forever. One-shot inside a PlayerFunc: start it with IMM, then
queue `AHI_NOSOUND` with flags 0 (takes effect when the sound ends). From ordinary task
code use AHI_PlayA with `AHIP_LoopSound, AHI_NOSOUND` instead (flags 0 is only legal
in hooks).

### Example
```c
/* inside PlayerFunc: one-shot = start now, queue "off" for when it ends */
AHI_SetFreq (ch, 22050, actrl, AHISF_IMM);
AHI_SetVol  (ch, 0x10000, 0x8000, actrl, AHISF_IMM);
AHI_SetSound(ch, sndBang, 0, 0, actrl, AHISF_IMM);
AHI_SetSound(ch, AHI_NOSOUND, 0, 0, actrl, AHISF_NONE);
```

```asm
; inside PlayerFunc (A2 = AHIAudioCtrl already), A6 = AHIBase
        moveq   #0,d0                   ; channel
        moveq   #0,d1                   ; sound 0
        moveq   #0,d2                   ; offset
        moveq   #0,d3                   ; length 0 = all
        moveq   #AHISF_IMM,d4
        jsr     _LVOAHI_SetSound(a6)
        moveq   #0,d0
        moveq   #AHI_NOSOUND,d1         ; queued: stop at the end
        moveq   #0,d4
        jsr     _LVOAHI_SetSound(a6)    ; d2/d3/a2/a6 survive the call
```

### Gotchas
- Safe from interrupts and hooks. In a SoundFunc use flags 0: the new sound
  follows the one that just started (Paula-style repeat part).
- Offset + Length must stay inside the sample; checking it is the caller's job.
- Very short sounds are CPU-expensive (end-of-sound work every few frames): unroll
  short loops to ~1000 frames unless you need SoundFunc per cycle.
- `AHISF_NONE` is a V6 name; use 0 for older includes.
- Special `AHIST_DYNAMICSAMPLE` trick (Address 0, Length `0xFFFFFFFF`): Offset may be
  an absolute address of 8-bit data. Not for 16-bit.

**See also:** AHI_SetFreq, AHI_SetVol, AHI_PlayA, AHI_LoadSound

## AHI_SetEffect
`ULONG AHI_SetEffect(APTR Effect, struct AHIAudioCtrl * AudioCtrl)` — LVO -84 (-$54)
Registers: Effect=A0, AudioCtrl=A2; result in D0

Switch a mixer effect on or off by passing its effect structure.

- **Effect** — pointer to an effect structure whose first ULONG is the type:
  [AHIET_MASTERVOLUME](tags.md#ahieffmastervolume), [AHIET_OUTPUTBUFFER](tags.md#ahieffoutputbuffer),
  V4: [AHIET_DSPMASK](tags.md#ahieffdspmask), [AHIET_DSPECHO](tags.md#ahieffdspecho),
  [AHIET_CHANNELINFO](tags.md#ahieffchannelinfo). OR the type with `AHIET_CANCEL` to turn it off.
- **AudioCtrl** — handle.
- **Result** — `AHIE_OK` or an [AHIE error](tags.md#ahie-error-codes) (before V4 always `AHIE_OK`).

Details, ranges and CPU cost: [effects topic](topics/effects.md).

### Gotchas
- NOT callable from interrupts or hooks (unlike the other `AHI_Set` calls).
- Disable master volume with `AHIET_CANCEL`, not by setting 1.0.
- Cancel every effect before AHI_FreeAudio (leaks otherwise). Cancelling one that
  was never set is harmless.
- `ahiedm_Channels` / `ahieci_Channels` must equal the allocated channel count
  (crash otherwise).
- Any effect can be unavailable on some hardware: check the result.

**See also:** [effects topic](topics/effects.md), AHI_FreeAudio

## AHI_LoadSound
`ULONG AHI_LoadSound(UWORD Sound, ULONG Type, APTR Info, struct AHIAudioCtrl * AudioCtrl)` — LVO -90 (-$5A)
Registers: Sound=D0, Type=D1, Info=A0, AudioCtrl=A2; result in D0

Register sample data under a sound ID so channels can play it.

- **Sound** — ID, 0 .. `AHIA_Sounds`-1.
- **Type** — `AHIST_SAMPLE` (static; memory must not change until unloaded) or
  `AHIST_DYNAMICSAMPLE` (you rewrite it while playing). [Types](tags.md#ahist-sound-types).
- **Info** — `struct AHISampleInfo *`: `ahisi_Type` = format (`AHIST_M8S`, `AHIST_M16S`;
  V4 `AHIST_S8S`, `AHIST_S16S`; V6 `AHIST_M32S`, `AHIST_S32S`, `AHIST_L7_1`),
  `ahisi_Address`, `ahisi_Length` in FRAMES.
- **AudioCtrl** — handle.
- **Result** — `AHIE_OK` (0) or an [AHIE error](tags.md#ahie-error-codes).

### Example
```c
struct AHISampleInfo si;
si.ahisi_Type    = AHIST_M16S;
si.ahisi_Address = data;                          /* MEMF_PUBLIC, not chip */
si.ahisi_Length  = bytes / AHI_SampleFrameSize(AHIST_M16S);
if (AHI_LoadSound(0, AHIST_SAMPLE, &si, actrl) != AHIE_OK)
    goto fail;
```

```asm
        move.l  _AHIBase,a6
        moveq   #0,d0                   ; sound ID
        moveq   #AHIST_SAMPLE,d1
        lea     sampleinfo,a0
        move.l  _actrl,a2
        jsr     _LVOAHI_LoadSound(a6)
        tst.l   d0
        bne     .error
        ...
sampleinfo:
        dc.l    AHIST_M8S               ; ahisi_Type
        dc.l    sampledata              ; ahisi_Address
        dc.l    SAMPLE_FRAMES           ; ahisi_Length (frames)
```

### Gotchas
- Sample memory does NOT need chip RAM but must never be paged out: MEMF_PUBLIC
  (for virtual memory, double-buffer from a task).
- Load the most important sounds first: DSP cards with little RAM may run out.
- `AHIST_DYNAMICSAMPLE` is mixed in chunks: keep at least
  `AHIDB_MaxPlaySamples * Fs / Fm` frames valid ahead of the play position
  (Fs = highest playback rate, Fm = real mix rate). It costs extra CPU on DSP cards.
- Don't write into an `AHIST_SAMPLE` after loading (reading is fine).
- `AHIST_L7_1` only plays in 7.1 modes.
- Not from interrupts or hooks.

**See also:** AHI_UnloadSound, AHI_SetSound, AHI_SampleFrameSize, [AHISampleInfo](tags.md#ahisampleinfo)

## AHI_UnloadSound
`void AHI_UnloadSound(UWORD Sound, struct AHIAudioCtrl * Audioctrl)` — LVO -96 (-$60)
Registers: Sound=D0, Audioctrl=A2; no result

Tell AHI a sound ID is no longer used.

- **Sound** — ID previously loaded.
- **Audioctrl** — handle.

AHI_FreeAudio unloads everything automatically. Free your sample memory only after
the sound is unloaded.

### Gotchas
- Does not break a Forbid().
- Stop every channel playing the sound first.

**See also:** AHI_LoadSound, AHI_FreeAudio

## AHI_NextAudioID
`ULONG AHI_NextAudioID(ULONG Last_ID)` — LVO -102 (-$66)
Registers: Last_ID=D0; result in D0

Iterate over all mode IDs in the audio mode database.

- **Last_ID** — previous ID, or `AHI_INVALID_ID` to start.
- **Result** — next ID, or `AHI_INVALID_ID` when done.

Loop: `id = AHI_INVALID_ID; while ((id = AHI_NextAudioID(id)) != AHI_INVALID_ID) ...`.
Full example in the [audio-modes topic](topics/audio-modes.md).

**See also:** AHI_GetAudioAttrsA, AHI_BestAudioIDA

## AHI_GetAudioAttrsA
`BOOL AHI_GetAudioAttrsA(ULONG ID, struct AHIAudioCtrl * Audioctrl, struct TagItem * tagList)` — LVO -108 (-$6C) (varargs form: AHI_GetAudioAttrs)
Registers: ID=D0, Audioctrl=A2, tagList=A1; result in D0

Read attributes of a mode, or of the mode an allocated handle is using.

- **ID** — mode ID, `AHI_DEFAULT_ID` (V4), or `AHI_INVALID_ID` to query `Audioctrl`.
- **Audioctrl** — handle, used only when ID is `AHI_INVALID_ID`; otherwise NULL.
- **tagList** — [AHIDB tags](tags.md#ahidb-tags). ti_Data is a pointer to a 4-byte
  result, except: `*Arg` tags and `AHIDB_BufferLen` take plain values; string tags
  (`AHIDB_Name`, `AHIDB_Driver`, `AHIDB_Author`, `AHIDB_Copyright`, `AHIDB_Version`,
  `AHIDB_Annotation`, `AHIDB_Input`, `AHIDB_Output`) take the buffer address.
- **Result** — TRUE on success.

### Example
```c
char  name[64];
ULONG bits = 0, stereo = 0, maxch = 0, realtime = 0;
if (AHI_GetAudioAttrs(id, NULL,
        AHIDB_BufferLen,   sizeof(name),
        AHIDB_Name,        (ULONG)name,
        AHIDB_Bits,        (ULONG)&bits,
        AHIDB_Stereo,      (ULONG)&stereo,
        AHIDB_MaxChannels, (ULONG)&maxch,
        AHIDB_Realtime,    (ULONG)&realtime,
        TAG_DONE)) { /* ... */ }
```

### Gotchas
- With an allocated handle pass `AHI_INVALID_ID` + handle; asking by ID can return
  wrong values for some tags.
- Missing attributes leave your variable untouched: initialise them.
- Without `AHIDB_BufferLen` (default 0) no string is copied.
- Opens the driver library: task context only.

**See also:** AHI_BestAudioIDA, AHI_NextAudioID, [audio-modes topic](topics/audio-modes.md)

## AHI_BestAudioIDA
`ULONG AHI_BestAudioIDA(struct TagItem * tagList)` — LVO -114 (-$72) (varargs form: AHI_BestAudioID)
Registers: tagList=A1; result in D0

Pick the mode ID that best satisfies a set of required and preferred attributes.

- **tagList** — only present tags count ([AHIDB tags](tags.md#ahidb-tags)):
  `AHIDB_AudioID` (same hardware as this ID), booleans `AHIDB_Volume`, `AHIDB_Stereo`,
  `AHIDB_MultiChannel` (V6), `AHIDB_Panning`, `AHIDB_HiFi`, `AHIDB_PingPong`,
  `AHIDB_Record`, `AHIDB_Realtime`, `AHIDB_FullDuplex` (TRUE = must have, FALSE = must
  not have), `AHIDB_Bits` (>=), `AHIDB_MaxChannels` (>=), `AHIDB_MinMixFreq` (mode's
  lowest rate <= value), `AHIDB_MaxMixFreq` (mode's highest rate >= value), and `AHIB_Dizzy` (V4) = pointer to a second list of
  wishes used to rank the survivors.
- **Result** — best ID, or `AHI_INVALID_ID` if nothing qualifies.

### Example
```c
struct TagItem wish[] = {
    { AHIDB_HiFi,    TRUE },
    { AHIDB_Panning, TRUE },
    { AHIDB_Bits,    16   },
    { TAG_DONE,      0    }
};
ULONG id = AHI_BestAudioID(AHIDB_Realtime,    TRUE,
                           AHIDB_MaxChannels, 4,
                           AHIB_Dizzy,        (ULONG)wish,
                           TAG_DONE);
if (id == AHI_INVALID_ID)
    id = AHI_DEFAULT_ID;
```

### Gotchas
- Boolean tags are strict: `AHIDB_Stereo, FALSE` EXCLUDES stereo modes. Omit a tag you
  don't care about; put soft wishes in `AHIB_Dizzy`.
- ahi.device <= 4.158: TRUE must be exactly 1.
- Prefer letting the user choose (AHI_AudioRequestA) and storing the ID.

**See also:** AHI_GetAudioAttrsA, AHI_AudioRequestA, [audio-modes topic](topics/audio-modes.md)

## AHI_AllocAudioRequestA
`struct AHIAudioModeRequester * AHI_AllocAudioRequestA(struct TagItem * tagList)` — LVO -120 (-$78) (varargs form: AHI_AllocAudioRequest)
Registers: tagList=A0; result in D0

Allocate an audio mode requester structure.

- **tagList** — optional [AHIR tags](tags.md#ahir-tags) used as defaults for AHI_AudioRequestA.
- **Result** — `struct AHIAudioModeRequester *` or NULL.

The structure is read-only; change settings only through tags.

**See also:** AHI_AudioRequestA, AHI_FreeAudioRequest

## AHI_AudioRequestA
`BOOL AHI_AudioRequestA(struct AHIAudioModeRequester * Requester, struct TagItem * tagList)` — LVO -126 (-$7E) (varargs form: AHI_AudioRequest)
Registers: Requester=A0, tagList=A1; result in D0

Show the mode requester and let the user pick a mode and frequency.

- **Requester** — from AHI_AllocAudioRequestA. NULL: returns FALSE, IoErr() =
  `ERROR_NO_FREE_STORE`.
- **tagList** — [AHIR tags](tags.md#ahir-tags); they persist for later calls until changed.
- **Result** — TRUE: read `ahiam_AudioID` / `ahiam_MixFreq`. FALSE: IoErr() 0 =
  user cancelled; `ERROR_NO_FREE_STORE` = no memory; `ERROR_NO_MORE_ENTRIES` = no
  modes (e.g. your filter rejected them all).

### Example
```c
struct AHIAudioModeRequester *req = AHI_AllocAudioRequest(
    AHIR_TitleText,      (ULONG)"Select audio mode",
    AHIR_DoMixFreq,      TRUE,
    AHIR_DoDefaultMode,  TRUE,
    AHIR_InitialAudioID, savedID,
    TAG_DONE);
if (req) {
    if (AHI_AudioRequest(req, TAG_DONE)) {
        savedID   = req->ahiam_AudioID;      /* may be AHI_DEFAULT_ID */
        savedFreq = req->ahiam_MixFreq;      /* may be AHI_DEFAULT_FREQ */
    }
    AHI_FreeAudioRequest(req);
}
```

### Gotchas
- Needs Intuition (a screen): not for a program that has taken over the display.
- With `AHIR_DoDefaultMode` plus a filter, re-check the result with AHI_BestAudioIDA:
  the user can change what "default" means at any time.
- Listed frequencies may be a subset of what the driver accepts.

**See also:** AHI_AllocAudioRequestA, AHI_FreeAudioRequest, AHI_BestAudioIDA

## AHI_FreeAudioRequest
`void AHI_FreeAudioRequest(struct AHIAudioModeRequester * Requester)` — LVO -132 (-$84)
Registers: Requester=A0; no result

Free a requester from AHI_AllocAudioRequestA.

- **Requester** — requester or NULL (no-op). Unusable afterwards.

**See also:** AHI_AllocAudioRequestA, AHI_AudioRequestA

## AHI_PlayA
`void AHI_PlayA(struct AHIAudioCtrl * Audioctrl, struct TagItem * tagList)` — LVO -138 (-$8A) (varargs form: AHI_Play)
Registers: Audioctrl=A2, tagList=A1; no result

Set sound, rate, volume and one loop for several channels in one call (V4).

- **Audioctrl** — handle.
- **tagList** — [AHIP tags](tags.md#ahip-tags), read in order like a program: per
  channel `AHIP_BeginChannel, n` ... `AHIP_EndChannel, 0`; inside: `AHIP_Freq`,
  `AHIP_Vol`, `AHIP_Pan`, `AHIP_Sound`, optional `AHIP_Offset`+`AHIP_Length`, then loop
  tags `AHIP_Loop*` (default to the non-loop values; `AHIP_LoopSound, AHI_NOSOUND` = one-shot).

Channels in one call start in sync even outside a PlayerFunc; one-shots and simple
loops need no SoundFunc.

Since V4.

### Example
```c
AHI_Play(actrl,
    AHIP_BeginChannel, 0,
    AHIP_Freq,         22050,
    AHIP_Vol,          0x10000,
    AHIP_Pan,          0x8000,
    AHIP_Sound,        sndExplosion,
    AHIP_LoopSound,    AHI_NOSOUND,     /* play once */
    AHIP_EndChannel,   0,
    TAG_DONE);
```

### Gotchas
- More overhead than the three Set* calls: use those inside SoundFunc/PlayerFunc.
- Omitting Begin/EndChannel gives undefined results; `AHIP_EndChannel` data must be 0.
- `AHIP_Offset` requires `AHIP_Length`.

**See also:** AHI_SetSound, AHI_SetFreq, AHI_SetVol

## AHI_SampleFrameSize
`ULONG AHI_SampleFrameSize(ULONG SampleType)` — LVO -144 (-$90)
Registers: SampleType=D0; result in D0

Return the size in bytes of one frame of a sample format.

- **SampleType** — `AHIST_M8S` ... `AHIST_L7_1`.
- **Result** — bytes per frame (1, 2, 4, 8 or 32), 0 for an unknown type (V6;
  earlier versions returned garbage).

Since V4.

### Example
```c
ULONG frames = byteCount / AHI_SampleFrameSize(AHIST_S16S);   /* 4 bytes/frame */
```

```asm
        moveq   #AHIST_S16S,d0
        jsr     _LVOAHI_SampleFrameSize(a6)     ; a6 = AHIBase, d0 = 4
```

**See also:** AHI_LoadSound, [AHIST sample formats](tags.md#ahist-sample-formats)

## AHI_AddAudioMode
`ULONG AHI_AddAudioMode(struct TagItem * AHIPrivate)` — LVO -150 (-$96)
Registers: AHIPrivate=A0; result in D0

Add one mode (described by a database taglist) to the audio mode database (V4).

For mode-database tools such as AddAudioModes; applications never call it. The
argument is a private taglist; result FALSE on failure. An existing mode with the
same `AHIDB_AudioID` is replaced.

**See also:** AHI_RemoveAudioMode, AHI_LoadModeFile

## AHI_RemoveAudioMode
`ULONG AHI_RemoveAudioMode(ULONG AHIPrivate)` — LVO -156 (-$9C)
Registers: AHIPrivate=D0; result in D0

Remove a mode from the audio mode database (V4).

For mode-database tools only. Argument: mode ID (the V4 source doc also allows
`AHI_INVALID_ID`); result FALSE on failure.

**See also:** AHI_AddAudioMode, AHI_LoadModeFile

## AHI_LoadModeFile
`ULONG AHI_LoadModeFile(STRPTR AHIPrivate)` — LVO -162 (-$A2)
Registers: AHIPrivate=A0; result in D0

Add all modes from an IFF-AHIM mode file, or from every file in a directory (V4).

For mode-database tools only; ahi.device itself loads `DEVS:AudioModes` on first
OpenDevice (unless `AHIDF_NOMODESCAN`). Argument: file or directory name
(not recursive); result FALSE on error, details in IoErr().

**See also:** AHI_AddAudioMode, AHI_RemoveAudioMode, [drivers topic](topics/drivers.md)
