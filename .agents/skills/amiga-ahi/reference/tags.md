# ahi.device: tags, constants and structures

Names and values are from `devices/ahi.h` / `devices/ahi.i` 6.0 (AHI SDK
`Include/C`, `Include/Asm`). `AHI_TagBase` = `TAG_USER` = `0x80000000`;
`AHI_TagBaseR` = `AHI_TagBase|0x8000` = `0x80008000`. "Ver" = first ahi.device
version that honours the tag (blank = original V1/V2 set). Tags a version does
not know are ignored, not rejected.

## AHIA tags

Tags for AHI_AllocAudioA; hooks, PlayerFreq and UserData also work in AHI_ControlAudioA.

| Tag | Value | ti_Data | Meaning | Ver |
|---|---|---|---|---|
| `AHIA_AudioID` | `0x80000001` | ULONG | Mode ID. Default `AHI_DEFAULT_ID` | |
| `AHIA_MixFreq` | `0x80000002` | ULONG | Wanted mix rate in Hz. Default `AHI_DEFAULT_FREQ` | |
| `AHIA_Channels` | `0x80000003` | UWORD | Channels wanted. **Required** | |
| `AHIA_Sounds` | `0x80000004` | UWORD | Sound slots (IDs 0..n-1). **Required** | |
| `AHIA_SoundFunc` | `0x80000005` | struct Hook * | Called when a sound starts on a channel (like a Paula audio IRQ) | |
| `AHIA_PlayerFunc` | `0x80000006` | struct Hook * | Called `AHIA_PlayerFreq` times per second | |
| `AHIA_PlayerFreq` | `0x80000007` | Fixed | PlayerFunc rate, `50<<16` = 50 Hz. Required with PlayerFunc | |
| `AHIA_MinPlayerFreq` | `0x80000008` | Fixed | Lowest PlayerFreq you will ever set. Give it with PlayerFunc | |
| `AHIA_MaxPlayerFreq` | `0x80000009` | Fixed | Highest PlayerFreq you will ever set. Give it with PlayerFunc | |
| `AHIA_RecordFunc` | `0x8000000A` | struct Hook * | Called with sampled data while `AHIC_Record` is on | |
| `AHIA_UserData` | `0x8000000B` | APTR | Initial `ahiac_UserData` | |
| `AHIA_AntiClickSamples` | `0x8000000D` | ULONG | Max frames a new sound may wait for a zero crossing; 0 = off | V6 |

Hook register contract: A0 = `struct Hook *`, A2 = `struct AHIAudioCtrl *`,
A1 = message (`struct AHISoundMessage *` for SoundFunc, undefined for PlayerFunc,
`struct AHIRecordMessage *` for RecordFunc). Preserve D2-D7/A2-A6. RecordFunc
must return 0 in D0.

- `MixFreq / PlayerFreq` must be <= 65535 and should stay > 80.
- Before V6 a PlayerFreq/Min/Max value below `0x10000` is read as a plain integer
  (compatibility kludge). Always pass Fixed.

**See also:** [AHI_AllocAudioA](functions.md#ahi_allocaudioa), [AHI_ControlAudioA](functions.md#ahi_controlaudioa)

## AHIC tags

Control tags for AHI_ControlAudioA: start/stop and sound-card hardware settings.

| Tag | Value | ti_Data | Meaning | Ver |
|---|---|---|---|---|
| `AHIC_Play` | `0x80000050` | BOOL | Start (TRUE) / stop (FALSE) playback and PlayerFunc | |
| `AHIC_Record` | `0x80000051` | BOOL | Start / stop sampling and RecordFunc | |
| `AHIC_MonitorVolume` | `0x80000052` | Fixed | Input monitor level (input mixed to output) | |
| `AHIC_MonitorVolume_Query` | `0x80000053` | Fixed * | Read monitor level | |
| `AHIC_MixFreq_Query` | `0x80000054` | ULONG * | Read the real mixing frequency | |
| `AHIC_InputGain` | `0x80000055` | Fixed | Input gain | V2 |
| `AHIC_InputGain_Query` | `0x80000056` | Fixed * | Read input gain | V2 |
| `AHIC_OutputVolume` | `0x80000057` | Fixed | Card output volume | V2 |
| `AHIC_OutputVolume_Query` | `0x80000058` | Fixed * | Read output volume | V2 |
| `AHIC_Input` | `0x80000059` | ULONG | Select input 0..`AHIDB_Inputs`-1 | V2 |
| `AHIC_Input_Query` | `0x8000005A` | ULONG * | Read selected input | V2 |
| `AHIC_Output` | `0x8000005B` | ULONG | Select output 0..`AHIDB_Outputs`-1 | V2 |
| `AHIC_Output_Query` | `0x8000005C` | ULONG * | Read selected output | V2 |

- `AHIC_Play` and `AHIC_Record` must NOT be used from interrupts or hooks.
- Valid ranges come from `AHIDB_Min/Max...` (see [AHIDB tags](#ahidb-tags)).
- On half-duplex hardware starting one of Play/Record stops the other.

**See also:** [AHI_ControlAudioA](functions.md#ahi_controlaudioa), [recording topic](topics/recording.md)

## AHIP tags

Program tags for AHI_PlayA (V4); order matters, each channel is bracketed.

| Tag | Value | ti_Data | Meaning |
|---|---|---|---|
| `AHIP_BeginChannel` | `0x80000028` | UWORD | Start a channel block (mandatory) |
| `AHIP_EndChannel` | `0x80000029` | NULL | End the block. ti_Data MUST be 0 |
| `AHIP_Freq` | `0x80000032` | ULONG | Hz, or `AHI_MIXFREQ` |
| `AHIP_Vol` | `0x80000033` | Fixed | Volume; defaults to 0 if only `AHIP_Pan` given |
| `AHIP_Pan` | `0x80000034` | sposition | Pan; defaults to 0 (far left) if only `AHIP_Vol` given |
| `AHIP_Sound` | `0x80000035` | UWORD | Sound ID or `AHI_NOSOUND` |
| `AHIP_Offset` | `0x80000036` | ULONG | Start frame; requires `AHIP_Length` |
| `AHIP_Length` | `0x80000037` | LONG | Frames to play; negative = backwards |
| `AHIP_LoopFreq` | `0x8000003C` | ULONG | Loop part values; each defaults to its non-loop sister |
| `AHIP_LoopVol` | `0x8000003D` | Fixed | " |
| `AHIP_LoopPan` | `0x8000003E` | sposition | " |
| `AHIP_LoopSound` | `0x8000003F` | UWORD | `AHI_NOSOUND` = one-shot (stop after first pass) |
| `AHIP_LoopOffset` | `0x80000040` | ULONG | " |
| `AHIP_LoopLength` | `0x80000041` | LONG | " |

Loop tags must come after the other tags of the block.

**See also:** [AHI_PlayA](functions.md#ahi_playa)

## AHIDB tags

Mode database attributes read by AHI_GetAudioAttrsA and matched by AHI_BestAudioIDA.

For AHI_GetAudioAttrsA ti_Data is normally a pointer to a 4-byte variable; for
AHI_BestAudioIDA / `AHIR_FilterTags` it is the required value.

| Tag | Value | GetAudioAttrs ti_Data | Meaning | Ver |
|---|---|---|---|---|
| `AHIDB_AudioID` | `0x80000064` | ULONG * | Mode ID (Best: "same hardware as this ID") | V4 |
| `AHIDB_Driver` | `0x80008065` | char buffer | Driver name, no path/extension | |
| `AHIDB_Flags` | `0x80000066` | - | Private | |
| `AHIDB_Volume` | `0x80000067` | ULONG * | TRUE if volume can change | |
| `AHIDB_Panning` | `0x80000068` | ULONG * | TRUE if free stereo panning | |
| `AHIDB_Stereo` | `0x80000069` | ULONG * | TRUE if stereo output | |
| `AHIDB_HiFi` | `0x8000006A` | ULONG * | TRUE if no mixing shortcuts | |
| `AHIDB_PingPong` | `0x8000006B` | ULONG * | TRUE if samples can play backwards | |
| `AHIDB_MultTable` | `0x8000006C` | - | Private | |
| `AHIDB_Name` | `0x8000806D` | char buffer | Human-readable mode name | |
| `AHIDB_Bits` | `0x8000006E` | ULONG * | Output bits (Best: >=) | |
| `AHIDB_MaxChannels` | `0x8000006F` | ULONG * | Max channels (Best: >=) | |
| `AHIDB_MinMixFreq` | `0x80000070` | ULONG * | Lowest mix rate (Best: mode's lowest <= value) | |
| `AHIDB_MaxMixFreq` | `0x80000071` | ULONG * | Highest mix rate (Best: mode's highest >= value) | |
| `AHIDB_Record` | `0x80000072` | ULONG * | TRUE if it can record | |
| `AHIDB_Frequencies` | `0x80000073` | ULONG * | Number of selectable rates | |
| `AHIDB_FrequencyArg` | `0x80000074` | ULONG value | Index for `AHIDB_Frequency` (NOT a pointer) | |
| `AHIDB_Frequency` | `0x80000075` | ULONG * | Rate at that index | |
| `AHIDB_Author` | `0x80000076` | char buffer | Driver author | |
| `AHIDB_Copyright` | `0x80000077` | char buffer | Driver copyright | |
| `AHIDB_Version` | `0x80000078` | char buffer | Driver version string | |
| `AHIDB_Annotation` | `0x80000079` | char buffer | Driver notes | |
| `AHIDB_BufferLen` | `0x8000007A` | ULONG value | Size of every string buffer; default 0 = strings not copied | |
| `AHIDB_IndexArg` | `0x8000007B` | ULONG value | A frequency in Hz (NOT a pointer) | |
| `AHIDB_Index` | `0x8000007C` | ULONG * | Index of the rate closest to `AHIDB_IndexArg` | |
| `AHIDB_Realtime` | `0x8000007D` | ULONG * | TRUE if realtime (see below) | |
| `AHIDB_MaxPlaySamples` | `0x8000007E` | ULONG * | Frames that must be in memory for `AHIST_DYNAMICSAMPLE` | |
| `AHIDB_MaxRecordSamples` | `0x8000007F` | ULONG * | Frames per RecordFunc call | |
| `AHIDB_FullDuplex` | `0x80000081` | ULONG * | TRUE if play + record together | |
| `AHIDB_MinMonitorVolume` | `0x80000082` | Fixed * | Monitor range; both 0 = no monitor | V2 |
| `AHIDB_MaxMonitorVolume` | `0x80000083` | Fixed * | " | V2 |
| `AHIDB_MinInputGain` | `0x80000084` | Fixed * | Equal min/max = no gain control | V2 |
| `AHIDB_MaxInputGain` | `0x80000085` | Fixed * | " | V2 |
| `AHIDB_MinOutputVolume` | `0x80000086` | Fixed * | Equal min/max = no volume control | V2 |
| `AHIDB_MaxOutputVolume` | `0x80000087` | Fixed * | " | V2 |
| `AHIDB_Inputs` | `0x80000088` | ULONG * | Number of inputs | V2 |
| `AHIDB_InputArg` | `0x80000089` | ULONG value | Input index for `AHIDB_Input` | V2 |
| `AHIDB_Input` | `0x8000008A` | char buffer | Input name ("Line", "Mic"...) | V2 |
| `AHIDB_Outputs` | `0x8000008B` | ULONG * | Number of outputs | V2 |
| `AHIDB_OutputArg` | `0x8000008C` | ULONG value | Output index for `AHIDB_Output` | V2 |
| `AHIDB_Output` | `0x8000008D` | char buffer | Output name | V2 |
| `AHIDB_Data` | `0x8000808E` | - | Private | V4 |
| `AHIDB_DriverBaseName` | `0x8000808F` | - | Private | V4 |
| `AHIDB_MultiChannel` | `0x80000090` | ULONG * | TRUE if 7.1 output | V6 |

- `AHIDB_Realtime` TRUE means: Set* calls from a PlayerFunc take effect within
  about 10 ms, and PlayerFunc really runs at the asked rate. Modes that render to
  disk are not realtime; never use them unless your timing comes from PlayerFunc.
- Stereo without `AHIDB_Panning`: even channels go left, odd channels right.
- Attributes the mode cannot supply leave your variable untouched: pre-clear them.
- Strings: ti_Data is the buffer address itself; `AHIDB_BufferLen` limits the copy.
  Before V3 an overflowing string was not NUL-terminated.
- `devices/ahi.i` also defines `AHIDB_MixFreq EQU AHI_TagBase+128`, which is not
  in `ahi.h` or the autodoc. Don't use it.
- Also in `libraries/ahi_sub.h`: `AHIDB_UserBase` = `AHI_TagBase+500` (driver-private tags).

**See also:** [AHI_GetAudioAttrsA](functions.md#ahi_getaudioattrsa), [AHI_BestAudioIDA](functions.md#ahi_bestaudioida), [audio-modes topic](topics/audio-modes.md)

## AHIB_Dizzy

`AHIB_Dizzy` = `0x800000BE` (V4): AHI_BestAudioIDA "preference" sub-taglist pointer.

After the hard filters in the main list are applied, the mode that best matches
the AHIDB_ tags in this second list (most wanted features, fewest unwanted) wins.
Without it AHI_BestAudioIDA barely ranks anything.

**See also:** [AHI_BestAudioIDA](functions.md#ahi_bestaudioida)

## AHIR tags

Tags for AHI_AllocAudioRequestA and AHI_AudioRequestA (like the ASL screenmode requester).

| Tag | Value | ti_Data | Meaning | Ver |
|---|---|---|---|---|
| `AHIR_Window` | `0x800000C8` | struct Window * | Parent window (also picks the screen) | |
| `AHIR_Screen` | `0x800000C9` | struct Screen * | Screen to open on (overrides the others) | |
| `AHIR_PubScreenName` | `0x800000CA` | STRPTR | Public screen name (overrides `AHIR_Window`) | |
| `AHIR_PrivateIDCMP` | `0x800000CB` | BOOL | TRUE = own IDCMP port, not the parent's | |
| `AHIR_IntuiMsgFunc` | `0x800000CC` | struct Hook * | Gets foreign IntuiMessages: A0 hook, A1 IntuiMessage, A2 requester | |
| `AHIR_SleepWindow` | `0x800000CD` | BOOL | Busy-block `AHIR_Window` while open | |
| `AHIR_ObsoleteUserData` | `0x800000CE` | - | V4 user data, obsolete | |
| `AHIR_UserData` | `0x800000CF` | APTR | Copied to `ahiam_UserData` | V6 |
| `AHIR_TextAttr` | `0x800000DC` | struct TextAttr * | Font (must be in memory: OpenFont, not OpenDiskFont) | |
| `AHIR_Locale` | `0x800000DD` | struct Locale * | Language for gadgets | |
| `AHIR_TitleText` | `0x800000DE` | STRPTR | Window title | |
| `AHIR_PositiveText` | `0x800000DF` | STRPTR | OK gadget label | |
| `AHIR_NegativeText` | `0x800000E0` | STRPTR | Cancel gadget label | |
| `AHIR_InitialLeftEdge` | `0x800000F0` | WORD | Window position | |
| `AHIR_InitialTopEdge` | `0x800000F1` | WORD | " | |
| `AHIR_InitialWidth` | `0x800000F2` | WORD | Window size | |
| `AHIR_InitialHeight` | `0x800000F3` | WORD | " | |
| `AHIR_InitialAudioID` | `0x800000F4` | ULONG | Preselected mode; default `AHI_INVALID_ID` (none) | |
| `AHIR_InitialMixFreq` | `0x800000F5` | ULONG | Frequency slider start; default lowest rate | |
| `AHIR_InitialInfoOpened` | `0x800000F6` | BOOL | Open the info window too | |
| `AHIR_InitialInfoLeftEdge` | `0x800000F7` | WORD | Info window position | |
| `AHIR_InitialInfoTopEdge` | `0x800000F8` | WORD | " | |
| `AHIR_InitialInfoWidth` | `0x800000F9` | - | Not used | |
| `AHIR_InitialInfoHeight` | `0x800000FA` | - | Not used | |
| `AHIR_DoMixFreq` | `0x80000104` | BOOL | Show the frequency slider | |
| `AHIR_DoDefaultMode` | `0x80000105` | BOOL | Offer the prefs default mode (returns `AHI_DEFAULT_ID`/`AHI_DEFAULT_FREQ`) | V4 |
| `AHIR_FilterTags` | `0x8000010E` | struct TagItem * | Only list modes matching these AHIDB_ tags | |
| `AHIR_FilterFunc` | `0x8000010F` | struct Hook * | A0 hook, A1 = (ULONG) mode ID, A2 requester; return TRUE to list it | |

**See also:** [AHI_AudioRequestA](functions.md#ahi_audiorequesta), [AHIAudioModeRequester](#ahiaudiomoderequester)

## Special IDs and values

Reserved mode IDs, frequencies and sound numbers.

| Name | Value | Use |
|---|---|---|
| `AHINAME` | `"ahi.device"` | Device name (asm: `AHINAME` macro emits the string) |
| `AHI_INVALID_ID` | `~0` = `0xFFFFFFFF` | "No mode"; start/end of AHI_NextAudioID; "use audioctrl" for AHI_GetAudioAttrsA |
| `AHI_DEFAULT_ID` | `0x00000000` | User's default mode. Only for AHI_AllocAudioA (and AHI_GetAudioAttrsA from V4) |
| `AHI_LOOPBACK_ID` | `0x00000001` | Special sample-render ID |
| `AHI_DEFAULT_FREQ` | `0` | User's default mix rate. Only for AHI_AllocAudioA |
| `AHI_MIXFREQ` | `~0` | AHI_SetFreq / `AHIP_Freq`: play at the mixing rate |
| `AHI_NOSOUND` | `0xFFFF` (asm `~0`) | AHI_SetSound / `AHIP_Sound`: turn the channel off |
| `AHI_DEFAULT_UNIT` | `0` | Device unit 0 |
| `AHI_NO_UNIT` | `255` | Open for the low-level library API |
| `AHIDF_NOMODESCAN` | `1<<0` (`AHIDB_NOMODESCAN` = 0) | OpenDevice flag: don't build the mode DB (for AddAudioModes-type tools) |

Mode ID layout (driver doc): upper word = hardware ID assigned by the AHI author;
lower word bits 0-4 = mode, 8-11 = converter on the card, 12-15 = card number.

**See also:** [device-interface.md](device-interface.md#opendevice), [audio-modes topic](topics/audio-modes.md)

## AHISF flags

Flags for the `Flags` argument of AHI_SetVol, AHI_SetFreq and AHI_SetSound.

| Name | Value | Meaning |
|---|---|---|
| `AHISF_NONE` | `0` | No flags: change applies when the current sound ends (V6 name; 0 works everywhere) |
| `AHISF_IMM` / `AHISB_IMM` | `1<<0` / 0 | Apply immediately |
| `AHISF_NODELAY` / `AHISB_NODELAY` | `1<<1` / 1 | Add to IMM: start now, skip the anti-click zero-crossing wait (`AHIA_AntiClickSamples`, V6) |

Rules for `AHISF_IMM`: inside a SoundFunc it must be CLEAR; inside a PlayerFunc
either; anywhere else it must be SET.

`libraries/ahi_sub.h` reuses the `AHISF_`/`AHISB_` prefix for driver return flags
(`AHISF_ERROR`, `AHISF_MIXING`, `AHISF_PLAY`...). Different meaning, same bit values;
see [drivers topic](topics/drivers.md).

## AHIST sound types

`type` argument of AHI_LoadSound: how AHI may treat the sample memory.

| Name | Value | Meaning |
|---|---|---|
| `AHIST_SAMPLE` | `0` | Static sample. Memory must not change until unloaded (driver may copy it to card RAM) |
| `AHIST_DYNAMICSAMPLE` | `1` | Sample you rewrite while it plays (streams, software synth). Always played from main RAM; costs more CPU on DSP cards |
| `AHIST_INPUT` | `1<<29` | Live sampler input (V4 source: "not fully functional"); dropped from the V6 autodoc |
| `AHIST_NOTYPE` | `~0` | Private |
| `AHIST_BW` | `1<<30` | Private |

**See also:** [AHI_LoadSound](functions.md#ahi_loadsound), [AHISampleInfo](#ahisampleinfo)

## AHIST sample formats

Sample formats for `ahisi_Type`, `ahir_Type`, `ahirm_Type` and `ahieob_Type`.

| Name | Value | Frame | Bytes/frame | Ver |
|---|---|---|---|---|
| `AHIST_M8S` | `0` | mono, signed BYTE | 1 | |
| `AHIST_M16S` | `1` | mono, signed WORD big-endian | 2 | |
| `AHIST_S8S` | `2` | L,R signed BYTEs | 2 | V4 |
| `AHIST_S16S` | `3` | L,R signed WORDs | 4 | V4 |
| `AHIST_M8U` | `4` | OBSOLETE (unsigned 8 bit) | - | |
| `AHIST_M32S` | `8` | mono, signed LONG | 4 | V6 |
| `AHIST_S32S` | `10` | L,R signed LONGs | 8 | V6 |
| `AHIST_L7_1` | `0x00C3000A` | 8 LONGs: FL, FR, BL, BR, SL, SR, C, LFE | 32 | V6 |

- Lengths in the library API are in **frames**; the device API (`io_Length`) is in **bytes**.
- 32-bit types: only the top 24 bits are guaranteed to matter.
- `AHIST_L7_1` plays only in 7.1 modes (no downmix) and never backwards.
- All data is signed. Convert unsigned 8-bit (WAV) with `x ^ 0x80`.
- Get the frame size with AHI_SampleFrameSize (V4) instead of hardcoding.

## AHIE error codes

Results of AHI_ControlAudioA, AHI_LoadSound, AHI_SetEffect and device `io_Error`.

| Name | Value | Meaning |
|---|---|---|
| `AHIE_OK` | `0` | No error |
| `AHIE_NOMEM` | `1` | Out of memory |
| `AHIE_BADSOUNDTYPE` | `2` | Unknown sound type |
| `AHIE_BADSAMPLETYPE` | `3` | Unknown/unsupported sample format |
| `AHIE_ABORTED` | `4` | Aborted by the user |
| `AHIE_UNKNOWN` | `5` | Unspecified error |
| `AHIE_HALFDUPLEX` | `6` | CMD_WRITE/CMD_READ clash on half-duplex hardware |

Device requests can also return negative `IOERR_` codes from `exec/errors.h`
(`IOERR_OPENFAIL` -1, `IOERR_ABORTED` -2, `IOERR_NOCMD` -3).

## AHIET effect types

Values for `ahie_Effect`, the first ULONG of every AHI_SetEffect structure.

In asm each structure names its first field `ahiemv_Effect`, `ahieob_Effect`...;
`devices/ahi.i` also defines the common `ahie_Effect EQU 0`.

| Name | Value | Structure | Ver |
|---|---|---|---|
| `AHIET_CANCEL` | `1<<31` | OR into `ahie_Effect` to switch the effect off | |
| `AHIET_MASTERVOLUME` | `1` | [AHIEffMasterVolume](#ahieffmastervolume) | |
| `AHIET_OUTPUTBUFFER` | `2` | [AHIEffOutputBuffer](#ahieffoutputbuffer) | |
| `AHIET_DSPMASK` | `3` | [AHIEffDSPMask](#ahieffdspmask) | V4 |
| `AHIET_DSPECHO` | `4` | [AHIEffDSPEcho](#ahieffdspecho) | V4 |
| `AHIET_CHANNELINFO` | `5` | [AHIEffChannelInfo](#ahieffchannelinfo) | V4 |

**See also:** [AHI_SetEffect](functions.md#ahi_seteffect), [effects topic](topics/effects.md)

## AHIEffMasterVolume

Effect structure scaling the whole mix (`AHIET_MASTERVOLUME`).

| Off | C field | Asm label | Type | Meaning |
|---|---|---|---|---|
| 0 | `ahie_Effect` | `ahiemv_Effect` | ULONG | `AHIET_MASTERVOLUME` |
| 4 | `ahiemv_Volume` | `ahiemv_Volume` | Fixed | 0 .. channels/hardware-channel (see effects topic) |
| 8 | sizeof | `AHIEffMasterVolume_SIZEOF` | | |

## AHIEffOutputBuffer

Effect structure giving a hook read-only access to mixed output (`AHIET_OUTPUTBUFFER`).

| Off | C field | Asm label | Type | Meaning |
|---|---|---|---|---|
| 0 | `ahie_Effect` | `ahieob_Effect` | ULONG | `AHIET_OUTPUTBUFFER` |
| 4 | `ahieob_Func` | `ahieob_Func` | struct Hook * | A0 hook, A2 AHIAudioCtrl, A1 this structure |
| 8 | `ahieob_Type` | `ahieob_Type` | ULONG | Filled by AHI: `AHIST_` format. Always check it |
| 12 | `ahieob_Buffer` | `ahieob_Buffer` | APTR | Filled by AHI: sample data |
| 16 | `ahieob_Length` | `ahieob_Length` | ULONG | Filled by AHI: length in FRAMES |
| 20 | sizeof | `AHIEffOutputBuffer_SIZEOF` | | |

## AHIEffDSPMask

Effect structure choosing which channels the DSP effects process (`AHIET_DSPMASK`, V4).

| Off | C field | Asm label | Type | Meaning |
|---|---|---|---|---|
| 0 | `ahie_Effect` | `ahiedm_Effect` | ULONG | `AHIET_DSPMASK` |
| 4 | `ahiedm_Channels` | `ahiedm_Channels` | UWORD | MUST equal the allocated channel count |
| 6 | `ahiedm_Mask[]` | `ahiedm_Mask` | UBYTE[channels] | `AHIEDM_WET` (0) = processed, `AHIEDM_DRY` (1) = bypass |

`sizeof` / `AHIEffDSPMask_SIZEOF` = 6 (header only): allocate `6 + channels` bytes.
Default is all channels wet.

## AHIEffDSPEcho

Effect structure for the echo/delay DSP (`AHIET_DSPECHO`, V4).

| Off | C field | Asm label | Type | Meaning |
|---|---|---|---|---|
| 0 | `ahie_Effect` | `ahiede_Effect` | ULONG | `AHIET_DSPECHO` |
| 4 | `ahiede_Delay` | `ahiede_Delay` | ULONG | Delay in sample frames (depends on mix rate) |
| 8 | `ahiede_Feedback` | `ahiede_Feedback` | Fixed | 0..1.0; 0 = plain delay, >0 = echo |
| 12 | `ahiede_Mix` | `ahiede_Mix` | Fixed | 0 = off .. 1.0 = only the delayed signal |
| 16 | `ahiede_Cross` | `ahiede_Cross` | Fixed | Stereo cross-feed 0..1.0 |
| 20 | sizeof | `AHIEffDSPEcho_SIZEOF` | | |

`AHIDSPEcho` is `#define`d to `AHIEffDSPEcho` (fix for the V4 include name).

## AHIEffChannelInfo

Effect structure whose hook gets each channel's play position (`AHIET_CHANNELINFO`, V4).

| Off | C field | Asm label | Type | Meaning |
|---|---|---|---|---|
| 0 | `ahie_Effect` | `ahieci_Effect` | ULONG | `AHIET_CHANNELINFO` |
| 4 | `ahieci_Func` | `ahieci_Func` | struct Hook * | A0 hook, A2 AHIAudioCtrl, A1 this structure |
| 8 | `ahieci_Channels` | `ahieci_Channels` | UWORD | MUST equal the allocated channel count |
| 10 | `ahieci_Pad` | `ahieci_Pad` | UWORD | |
| 12 | `ahieci_Offset[]` | `ahieci_Offset` | ULONG[channels] | Filled by AHI before each call: offset in frames |

`sizeof` / `AHIEffChannelInfo_SIZEOF` = 12: allocate `12 + 4*channels` bytes.

## AHIAudioCtrl

Handle returned by AHI_AllocAudioA; only its first field is public.

| Off | Field | Type | Meaning |
|---|---|---|---|
| 0 | `ahiac_UserData` | APTR | Free for you; set with `AHIA_UserData` or write it directly |

Everything after it is private. Never allocate or copy it; don't use
`AHIAudioCtrl_SIZEOF`. Do not share the handle with another task.

## AHISoundMessage

Message (A1) passed to the SoundFunc hook.

| Off | Field | Type | Meaning |
|---|---|---|---|
| 0 | `ahism_Channel` | UWORD | Channel whose sound just started/looped |

## AHIRecordMessage

Message (A1) passed to the RecordFunc hook.

| Off | Field | Type | Meaning |
|---|---|---|---|
| 0 | `ahirm_Type` | ULONG | Format; currently always `AHIST_S16S` but CHECK it |
| 4 | `ahirm_Buffer` | APTR | Samples; valid only until the next call |
| 8 | `ahirm_Length` | ULONG | Length in FRAMES (x4 for bytes with S16S) |
| 12 | sizeof | | |

## AHISampleInfo

Sample descriptor passed as `info` to AHI_LoadSound for sample-type sounds.

| Off | Field | Type | Meaning |
|---|---|---|---|
| 0 | `ahisi_Type` | ULONG | `AHIST_M8S`, `AHIST_S16S`... ([formats](#ahist-sample-formats)) |
| 4 | `ahisi_Address` | APTR | First frame |
| 8 | `ahisi_Length` | ULONG | Length in FRAMES |
| 12 | sizeof | | |

Special case (`AHIST_DYNAMICSAMPLE` only): `ahisi_Address` 0 and `ahisi_Length`
`0xFFFFFFFF` let AHI_SetSound take an absolute address as `Offset` (8-bit only).

## AHIAudioModeRequester

Read-only result structure of AHI_AllocAudioRequestA / AHI_AudioRequestA.

| Off | Field | Type | Meaning |
|---|---|---|---|
| 0 | `ahiam_AudioID` | ULONG | Selected mode (may be `AHI_DEFAULT_ID` with `AHIR_DoDefaultMode`) |
| 4 | `ahiam_MixFreq` | ULONG | Selected frequency (may be `AHI_DEFAULT_FREQ`) |
| 8 | `ahiam_LeftEdge` | WORD | Requester window on exit |
| 10 | `ahiam_TopEdge` | WORD | |
| 12 | `ahiam_Width` | WORD | |
| 14 | `ahiam_Height` | WORD | |
| 16 | `ahiam_InfoOpened` | BOOL | Info window was open |
| 18 | `ahiam_InfoLeftEdge` | WORD | Info window on exit |
| 20 | `ahiam_InfoTopEdge` | WORD | |
| 22 | `ahiam_InfoWidth` | WORD | |
| 24 | `ahiam_InfoHeight` | WORD | |
| 26 | `ahiam_ObsoleteUserData[2]` | UWORD[2] | Asm: `ahiam_ObsoleteUserData0/1` |
| 30 | `ahiam_Pad` | UWORD | |
| 32 | `ahiam_UserData` | APTR | From `AHIR_UserData` (V6) |

Private data follows. Change it only through tags.

## Fixed, sposition

AHI's 16.16 fixed-point types used for volume, pan, gains and PlayerFreq.

- `typedef LONG Fixed;` - 16 integer bits . 16 fraction bits. `1.0` = `0x10000`,
  `0.5` = `0x8000`, `-1.0` = `0xFFFF0000`. Range -32768 .. +32767.99998.
- `typedef Fixed sposition;` - stereo position: `0` far left, `0x8000` centre,
  `0x10000` far right. Negative (V4) = surround.
- Convert: `hz << 16`, `percent * 0x10000 / 100`, `vol64 << 10` (Paula 0-64 to 0..1.0).
- asm: `devices/ahi.i` defines a `Fixed` STRUCTURE macro (4 bytes), not a type.

## AHIUnitPrefs, AHIGlobalPrefs

Layouts of the `AHIU`/`AHIG` chunks of `ENV:Sys/ahi.prefs` (rarely read by programs).

`AHIUnitPrefs` (one per unit 0-3 and `AHI_NO_UNIT`, chunk `ID_AHIU`):

| Off | Field | Type |
|---|---|---|
| 0 | `ahiup_Unit` | UBYTE |
| 1 | `ahiup_Obsolete` | UBYTE (was ScaleMode) |
| 2 | `ahiup_Channels` | UWORD |
| 4 | `ahiup_AudioMode` | ULONG |
| 8 | `ahiup_Frequency` | ULONG |
| 12 | `ahiup_MonitorVolume` | Fixed |
| 16 | `ahiup_InputGain` | Fixed |
| 20 | `ahiup_OutputVolume` | Fixed |
| 24 | `ahiup_Input` | ULONG |
| 28 | `ahiup_Output` | ULONG |

`AHIGlobalPrefs` (chunk `ID_AHIG`): `ahigp_DebugLevel` UWORD @0 (`AHI_DEBUG_NONE` 0,
`_LOW` 1, `_HIGH` 2, `_ALL` 3), `ahigp_DisableSurround` BOOL @2, `ahigp_DisableEcho`
BOOL @4, `ahigp_FastEcho` BOOL @6, `ahigp_MaxCPU` Fixed @8, `ahigp_ClipMasterVolume`
BOOL @12, `ahigp_Pad` UWORD @14, `ahigp_AntiClickTime` Fixed seconds @16 (V6),
`ahigp_ScaleMode` UWORD @20 (V6): `AHI_SCALE_FIXED_SAFE` 0, `AHI_SCALE_DYNAMIC_SAFE` 1,
`AHI_SCALE_FIXED_0_DB` 2 (V6 default "full volume"), `AHI_SCALE_FIXED_3_DB` 3,
`AHI_SCALE_FIXED_6_DB` 4.

The prefs program's "Music unit" is the `AHI_NO_UNIT` record: it supplies the
mode and rate behind `AHI_DEFAULT_ID` and `AHI_DEFAULT_FREQ` for low-level programs.
