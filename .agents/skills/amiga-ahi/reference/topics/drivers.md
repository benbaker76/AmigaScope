# AHI driver writing (orientation)

**Only for writing an AHI driver (`DEVS:AHI/<name>.audio`).** Programs that play
or record sound never call these functions; use [functions.md](../functions.md) and
[device-interface.md](../device-interface.md). Sources: `ahi_sub.doc`,
`libraries/ahi_sub.h`/`.i`, the SDK example drivers (`Developer/Drivers/Void`,
`Filesave`, `Device`). This is a map, not a full driver guide.

## What a driver is

The pieces a driver author ships and the rules AHI imposes on them.

- A shared library named `<name>.audio` in `DEVS:AHI`, opened by ahi.device with
  OpenLibrary. It must open successfully even when its hardware is absent.
- A mode descriptor file `DEVS:AudioModes/<NAME>`: IFF `FORM AHIM` containing
  `AUDN` (driver name, e.g. `"void"`), optional `AUDD` (driver data) and one `AUDM`
  chunk per mode = a taglist of `AHIDB_` tags (`AHIDB_AudioID`, `AHIDB_Volume`,
  `AHIDB_Panning`, `AHIDB_Stereo`, `AHIDB_HiFi`, `AHIDB_MultTable`,
  `AHIDB_MultiChannel`, `AHIDB_Name`...). IDs `ID_AHIM`, `ID_AUDN`, `ID_AUDD`, `ID_AUDM`
  are in `libraries/ahi_sub.h`. Driver-private tags start at `AHIDB_UserBase`
  (`AHI_TagBase+500`).
- Audio IDs: upper word = hardware ID assigned by the AHI author; lower word bits
  0-4 mode, 8-11 converter, 12-15 card number; other bits 0.
- Library version: at least 2; set it to the AHI version whose driver features you
  use (e.g. `ahiac_PreTimer` -> 4). AHI V4 refuses to open V6 drivers.
- Registers: all functions take the handle in A2 as `struct AHIAudioCtrlDrv *`.

## AHIAudioCtrlDrv

The driver's view of the AHIAudioCtrl handle (public part).

| Off | Field | Type | Meaning |
|---|---|---|---|
| 0 | `ahiac_AudioCtrl` | struct AHIAudioCtrl | App-visible part (`ahiac_UserData`) |
| 4 | `ahiac_Flags` | ULONG | `AHIACF_VOL` 1<<0, `_PAN` 1<<1, `_STEREO` 1<<2, `_HIFI` 1<<3, `_PINGPONG` 1<<4, `_RECORD` 1<<5, `_MULTTAB` 1<<6 (private), `_MULTICHANNEL` 1<<7 |
| 8 | `ahiac_SoundFunc` | struct Hook * | App's `AHIA_SoundFunc` |
| 12 | `ahiac_PlayerFunc` | struct Hook * | App's PlayerFunc (AHI supplies a default) |
| 16 | `ahiac_PlayerFreq` | Fixed | Calls per second wanted |
| 20 | `ahiac_MinPlayerFreq` | Fixed | |
| 24 | `ahiac_MaxPlayerFreq` | Fixed | |
| 28 | `ahiac_MixFreq` | ULONG | Mix rate; driver rounds it in AHIsub_AllocAudio |
| 32 | `ahiac_Channels` | UWORD | |
| 34 | `ahiac_Sounds` | UWORD | |
| 36 | `ahiac_DriverData` | APTR | Free for the driver |
| 40 | `ahiac_MixerFunc` | struct Hook * | AHI's software mixer |
| 44 | `ahiac_SamplerFunc` | struct Hook * | Call with recorded data |
| 48 | `ahiac_Obsolete` | ULONG | |
| 52 | `ahiac_BuffSamples` | ULONG | Frames to mix per pass (<= 65535) |
| 56 | `ahiac_MinBuffSamples` | ULONG | |
| 60 | `ahiac_MaxBuffSamples` | ULONG | Largest pass until Stop (size DMA buffers from it) |
| 64 | `ahiac_BuffSize` | ULONG | Bytes the mix buffer needs |
| 68 | `ahiac_BuffType` | ULONG | V2: `AHIST_M16S`, `AHIST_S16S`, `AHIST_M32S`, `AHIST_S32S` |
| 72 | `ahiac_PreTimer` | BOOL (*)(void) | V4: call before mixing; TRUE = skip this mix (CPU overload) |
| 76 | `ahiac_PostTimer` | void (*)(void) | V4: call after mixing |
| 80 | `ahiac_AntiClickSamples` | ULONG | V6 |
| 84 | `ahiac_PreTimerFunc` | struct Hook * | V6 hook form of PreTimer (check D0, don't rely on Z) |
| 88 | `ahiac_PostTimerFunc` | struct Hook * | V6 hook form of PostTimer |

Everything after offset 92 is private.

## Driver functions

The AHIsub_ library vectors a driver implements (LVOs relative to the driver base).

## AHIsub_AllocAudio
`ULONG AHIsub_AllocAudio(struct TagItem * tagList, struct AHIAudioCtrlDrv * AudioCtrl)` — LVO -30 (-$1E)
Registers: tagList=A1, AudioCtrl=A2; result in D0

Claim the hardware for a handle and tell AHI how playback will be produced.

- **tagList** — the MODE's database tags (`AHIDB_`), not the application's tags.
- **Result** — flags: `AHISF_ERROR` (1<<0), `AHISF_MIXING` (1<<1, use AHI's mixer),
  `AHISF_TIMING` (1<<2, driver can play any buffer length ~80-65535 frames, AHI
  derives timing), `AHISF_KNOWSTEREO` (1<<3), `AHISF_KNOWHIFI` (1<<4, accepts 32-bit
  mix buffers), `AHISF_CANRECORD` (1<<5), `AHISF_CANPOSTPROCESS` (1<<6, V4: wet and
  dry buffers for on-card DSP), `AHISF_KNOWMULTICHANNEL` (1<<7).
- Round `ahiac_MixFreq` to a supported rate. Without TIMING, also set `ahiac_BuffSamples`
  (a pass should play in < ~10-20 ms).
- No cleanup on failure needed: AHIsub_FreeAudio is always called.

## AHIsub_FreeAudio
`void AHIsub_FreeAudio(struct AHIAudioCtrlDrv * AudioCtrl)` — LVO -36 (-$24)
Registers: AudioCtrl=A2; no result

Release what AHIsub_AllocAudio took; must be safe if that failed or never ran.

AHIsub_Stop is always called before it.

## AHIsub_Disable
`void AHIsub_Disable(struct AHIAudioCtrlDrv * AudioCtrl)` — LVO -42 (-$2A)
Registers: AudioCtrl=A2; no result

Temporarily block the driver's own interrupt/task (lazy drivers call exec Disable).

Nests with AHIsub_Enable. V6 drivers need not preserve all registers (older: preserve all).

## AHIsub_Enable
`void AHIsub_Enable(struct AHIAudioCtrlDrv * AudioCtrl)` — LVO -48 (-$30)
Registers: AudioCtrl=A2; no result

Undo one AHIsub_Disable.

## AHIsub_Start
`ULONG AHIsub_Start(ULONG Flags, struct AHIAudioCtrlDrv * AudioCtrl)` — LVO -54 (-$36)
Registers: Flags=D0, AudioCtrl=A2; result in D0

Start playback (`AHISF_PLAY` 1<<0) and/or recording (`AHISF_RECORD` 1<<1).

- **Result** — `AHIE_OK` or an `AHIE_` error; AHIsub_Stop is called even on failure.
- Must tolerate repeated calls without AHIsub_Stop in between.
- See the mixing loop and recording model below.

## AHIsub_Update
`ULONG AHIsub_Update(ULONG Flags, struct AHIAudioCtrlDrv * AudioCtrl)` — LVO -60 (-$3C)
Registers: Flags=D0, AudioCtrl=A2; result in D0

Re-read hooks and buffer parameters after the application changed them.

Mixing+timing: `ahiac_PlayerFunc`, `ahiac_MixerFunc`, `ahiac_SamplerFunc`,
`ahiac_BuffSamples` (and `ahiac_PlayerFreq` if used). Mixing only: PlayerFunc,
MixerFunc, SamplerFunc, PlayerFreq. No mixing: PlayerFunc, SamplerFunc, PlayerFreq.
Must be interrupt-safe. No flags defined.

## AHIsub_Stop
`ULONG AHIsub_Stop(ULONG Flags, struct AHIAudioCtrlDrv * AudioCtrl)` — LVO -66 (-$42)
Registers: Flags=D0, AudioCtrl=A2; result in D0

Stop playback and/or recording and free what AHIsub_Start allocated.

Must be safe when Start never ran, failed, or Stop is called twice. The autodoc
synopsis shows `void`; the SFD declares ULONG.

## AHIsub_SetVol
`ULONG AHIsub_SetVol(UWORD Channel, Fixed Volume, sposition Pan, struct AHIAudioCtrlDrv * AudioCtrl, ULONG Flags)` — LVO -72 (-$48)
Registers: Channel=D0, Volume=D1, Pan=D2, AudioCtrl=A2, Flags=D3; result in D0

Driver hook for AHI_SetVol; return `AHIS_UNKNOWN` (`~0`) to let AHI's mixer handle it.

The Set*/Load/Unload vectors all follow this rule: without `AHISF_MIXING` every
call is routed only to the driver; with it the driver sees the call first and AHI
acts only when the driver returns `AHIS_UNKNOWN`. Semantics as the ahi.device calls.

## AHIsub_SetFreq
`ULONG AHIsub_SetFreq(UWORD Channel, ULONG Freq, struct AHIAudioCtrlDrv * AudioCtrl, ULONG Flags)` — LVO -78 (-$4E)
Registers: Channel=D0, Freq=D1, AudioCtrl=A2, Flags=D2; result in D0

Driver hook for AHI_SetFreq; `AHIS_UNKNOWN` = let AHI handle it.

## AHIsub_SetSound
`ULONG AHIsub_SetSound(UWORD Channel, UWORD Sound, ULONG Offset, LONG Length, struct AHIAudioCtrlDrv * AudioCtrl, ULONG Flags)` — LVO -84 (-$54)
Registers: Channel=D0, Sound=D1, Offset=D2, Length=D3, AudioCtrl=A2, Flags=D4; result in D0

Driver hook for AHI_SetSound; `AHIS_UNKNOWN` = let AHI handle it.

## AHIsub_SetEffect
`ULONG AHIsub_SetEffect(APTR Effect, struct AHIAudioCtrlDrv * AudioCtrl)` — LVO -90 (-$5A)
Registers: Effect=A0, AudioCtrl=A2; result in D0

Driver hook for AHI_SetEffect (lets cards do filters/echo on board); `AHIS_UNKNOWN` = AHI.

## AHIsub_LoadSound
`ULONG AHIsub_LoadSound(UWORD Sound, ULONG Type, APTR Info, struct AHIAudioCtrlDrv * AudioCtrl)` — LVO -96 (-$60)
Registers: Sound=D0, Type=D1, Info=A0, AudioCtrl=A2; result in D0

Driver hook for AHI_LoadSound (e.g. upload samples to card RAM); `AHIS_UNKNOWN` = AHI.

## AHIsub_UnloadSound
`ULONG AHIsub_UnloadSound(UWORD Sound, struct AHIAudioCtrlDrv * Audioctrl)` — LVO -102 (-$66)
Registers: Sound=D0, Audioctrl=A2; result in D0

Driver hook for AHI_UnloadSound; `AHIS_UNKNOWN` = AHI.

## AHIsub_GetAttr
`LONG AHIsub_GetAttr(ULONG Attribute, LONG Argument, LONG DefValue, struct TagItem * tagList, struct AHIAudioCtrlDrv * AudioCtrl)` — LVO -108 (-$6C)
Registers: Attribute=D0, Argument=D1, DefValue=D2, tagList=A1, AudioCtrl=A2; result in D0

Answer attribute queries for a mode; return `DefValue` for anything unknown.

`Attribute` is an `AHIDB_` tag: `AHIDB_Bits`, `AHIDB_MaxChannels`, `AHIDB_Frequencies`,
`AHIDB_Frequency` (Argument = index), `AHIDB_Index` (Argument = Hz), `AHIDB_Author`,
`AHIDB_Copyright`, `AHIDB_Version`, `AHIDB_Annotation` (return string pointers),
`AHIDB_Record`, `AHIDB_FullDuplex`, `AHIDB_Realtime`, `AHIDB_MaxPlaySamples`,
`AHIDB_MaxRecordSamples`; V2: `AHIDB_Min/MaxMonitorVolume`, `AHIDB_Min/MaxInputGain`,
`AHIDB_Min/MaxOutputVolume`, `AHIDB_Inputs`/`AHIDB_Input` (Argument = index),
`AHIDB_Outputs`/`AHIDB_Output`. `tagList` and `AudioCtrl` may be NULL.

## AHIsub_HardwareControl
`LONG AHIsub_HardwareControl(ULONG Attribute, LONG Argument, struct AHIAudioCtrlDrv * AudioCtrl)` — LVO -114 (-$72)
Registers: Attribute=D0, Argument=D1, AudioCtrl=A2; result in D0

Set or query sound-card controls such as input, gain and monitor volume.

`Attribute`: `AHIC_MonitorVolume`, V2 `AHIC_InputGain`, `AHIC_OutputVolume`,
`AHIC_Input`, `AHIC_Output`, each also as `_Query` (Argument ignored). Return the
queried value; TRUE after a successful set; FALSE for unknown or unsupported
attributes. Must be interrupt-safe.

## The mixing callback model

How a driver that returned `AHISF_MIXING|AHISF_TIMING` produces sound.

In AHIsub_Start (`AHISF_PLAY`): allocate a long-aligned mix buffer of
`ahiac_BuffSize` bytes, then run this loop in a task or software interrupt (not in
the hardware interrupt itself) until AHIsub_Stop:

1. Call `ahiac_PlayerFunc` hook: A0 hook, A2 AHIAudioCtrlDrv, A1 NULL.
2. Optional: `ahiac_PreTimer` (A2 = handle, all registers but D0 preserved; TRUE/Z
   clear = skip steps 3-4) or, V6, the `ahiac_PreTimerFunc` hook (test D0).
3. Call `ahiac_MixerFunc` hook: A0 hook, A2 handle, A1 = mix buffer. It preserves all
   registers, calls the application's SoundFunc itself, and writes
   `ahiac_BuffSamples` frames of `ahiac_BuffType` (16-bit, or 32-bit if `AHIACF_HIFI`;
   interleaved L/R if `AHIACF_STEREO`; stereo/HiFi only if you reported KNOWSTEREO/KNOWHIFI).
4. Convert and send to the hardware (clear CPU caches if DMA reads a cached buffer).
5. Optional: `ahiac_PostTimer` / V6 `ahiac_PostTimerFunc`.
6. Wait until the buffer has played; repeat. Double-buffer if possible.

With `AHISF_CANPOSTPROCESS` the buffer holds `ahiac_BuffSamples` wet frames followed
by the same number of dry frames: apply the DSP to the wet part, then add both.

The SDK's Void driver is the minimal model: a slave process that calls the player
hook, then the mixer hook into its buffer, discards the result and loops until signalled.

Variants:

- `AHISF_MIXING` without TIMING: same loop, but the driver calls PlayerFunc
  `ahiac_PlayerFreq` times per second itself, timed only by card timers,
  `timer.device` or `realtime.library` (no direct CIA use). Min/MaxBuffSamples are undefined.
- Neither flag: the hardware plays everything; the driver implements the Set*/Load
  vectors and still calls PlayerFunc at PlayerFreq with the same timing sources.

Recording (`AHISF_RECORD`): fill a long-aligned buffer (size divisible by 4) with
`AHIST_S16S` frames at the mix rate (duplicate mono), then call `ahiac_SamplerFunc`:
A0 hook, A2 handle, A1 `struct AHIRecordMessage` (`ahirm_Type` = `AHIST_S16S`,
`ahirm_Buffer`, `ahirm_Length` = frames). Keep the buffer valid until the next call;
aim for at least 4 calls per second at the lowest rate.

## Common mistakes

Driver pitfalls called out by the driver autodoc.

- Failing OpenLibrary when the card is missing.
- Doing the mixing inside the hardware interrupt.
- Buffers not long-aligned, or record buffers not divisible by 4.
- Reporting KNOWSTEREO/KNOWHIFI and then ignoring `ahiac_Flags`/`ahiac_BuffType`.
- Using CIA timers for PlayerFunc timing.
- Crashing in AHIsub_FreeAudio/AHIsub_Stop when called without a successful Alloc/Start.
