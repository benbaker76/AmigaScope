# AHI effects

AHI_SetEffect switches mixer-level effects on an allocated AHIAudioCtrl: master
volume, a read-only tap of the mixed output, a DSP echo with a per-channel wet/dry
mask, and per-channel play positions. Structures and offsets:
[tags.md](../tags.md#ahiet-effect-types).

## Rules for every effect

How to enable, update and cancel effects safely.

- Call from your task only; never from a hook or interrupt.
- Enable: fill the structure, `ahie_Effect = AHIET_xxx`, `AHI_SetEffect(&s, actrl)`.
  Check the result (`AHIE_OK`; before V4 it was always OK).
- Update: change fields and call AHI_SetEffect again with the same type.
- Disable: `ahie_Effect = AHIET_xxx | AHIET_CANCEL` and call again. Cancelling an
  effect that was never enabled is safe.
- Cancel every enabled effect BEFORE AHI_FreeAudio, or AHI leaks memory.
- Keep hook-based effect structures (`AHIET_OUTPUTBUFFER`, `AHIET_CHANNELINFO`) alive
  and unchanged while enabled: AHI writes its results into YOUR structure before each
  hook call (autodoc BUGS).
- Any effect may be unsupported by a driver (an output tap is impossible on some DSP
  cards), and the user can disable echo in the prefs. Never depend on one.

## AHIET_MASTERVOLUME

Scale the whole mix, including boosting it above 1.0.

`struct AHIEffMasterVolume { ULONG ahie_Effect; Fixed ahiemv_Volume; }`

- Range: 0 .. channels / (channels per hardware output). 4 channels in a mono mode,
  or a stereo mode with panning: 0.0-4.0. 4 channels in stereo WITHOUT panning (2
  channels per side): 0.0-2.0. Outside the range the result is unpredictable.
- Turn it off with `AHIET_CANCEL`, not by writing 1.0.
- Boosting can clip/distort. The prefs "Master volume" clipping option reduces this
  (user guide: 128 kB extra memory in the current implementation); HiFi modes turn
  clipping on automatically.
- In V4 each extra channel makes the mix quieter; V6 adjusts volume dynamically and
  plays sounds at full volume by default (user guide).

### Example
```c
struct AHIEffMasterVolume mv;
mv.ahie_Effect   = AHIET_MASTERVOLUME;
mv.ahiemv_Volume = 0x20000;                     /* 2.0 with 4 channels, mono mode */
if (AHI_SetEffect(&mv, actrl) != AHIE_OK) { /* not available */ }
/* ... */
mv.ahie_Effect = AHIET_MASTERVOLUME | AHIET_CANCEL;
AHI_SetEffect(&mv, actrl);
```

## AHIET_OUTPUTBUFFER

Get read-only access to each mixed output buffer, for scopes and VU meters.

`struct AHIEffOutputBuffer { ULONG ahie_Effect; struct Hook *ahieob_Func; ULONG ahieob_Type; APTR ahieob_Buffer; ULONG ahieob_Length; }`

- Hook: A0 hook, A2 AHIAudioCtrl, A1 the structure. AHI fills `ahieob_Type`
  (`AHIST_` format; always check it), `ahieob_Buffer`, `ahieob_Length` (FRAMES).
- Read only; runs in mixer context: copy a few frames or compute peaks and return.

### Example
```c
static struct Hook scopeHook;                   /* h_Entry = register stub, h_SubEntry = scopeFunc */
static struct AHIEffOutputBuffer tap;
static WORD peakL;

static ULONG scopeFunc(struct Hook *h, struct AHIAudioCtrl *actrl,
                       struct AHIEffOutputBuffer *ob)
{
    if (ob->ahieob_Type == AHIST_S16S || ob->ahieob_Type == AHIST_M16S) {
        WORD *s = ob->ahieob_Buffer, m = 0;
        ULONG step = (ob->ahieob_Type == AHIST_S16S) ? 2 : 1;
        for (ULONG i = 0; i < ob->ahieob_Length; i++, s += step) {
            WORD v = *s < 0 ? -*s : *s;
            if (v > m) m = v;
        }
        peakL = m;
    }
    return 0;
}

/* enable */
tap.ahie_Effect = AHIET_OUTPUTBUFFER;
tap.ahieob_Func = &scopeHook;
AHI_SetEffect(&tap, actrl);
```

Other buffer types are possible (the mixer produces 32-bit data in HiFi modes, so
`AHIST_M32S`/`AHIST_S32S` taps are plausible; unverified): ignore types you don't handle.

## AHIET_DSPMASK

Choose which channels pass through the DSP effects (echo) (V4).

`struct AHIEffDSPMask { ULONG ahie_Effect; UWORD ahiedm_Channels; UBYTE ahiedm_Mask[]; }`

- One UBYTE per channel: `AHIEDM_WET` (0) = processed, `AHIEDM_DRY` (1) = bypass.
  Default: all wet.
- `ahiedm_Channels` MUST equal the channel count of the AHIAudioCtrl; anything else
  is undefined (crash).
- The C struct ends in a zero-length array: embed it in a bigger struct or allocate
  `sizeof(struct AHIEffDSPMask) + channels` (header = 6 bytes).

### Example
```c
struct {
    struct AHIEffDSPMask hdr;
    UBYTE                mask[4];               /* 4 = AHIA_Channels */
} dm;
dm.hdr.ahie_Effect     = AHIET_DSPMASK;
dm.hdr.ahiedm_Channels = 4;
dm.mask[0] = AHIEDM_DRY;                        /* music channels dry */
dm.mask[1] = AHIEDM_DRY;
dm.mask[2] = AHIEDM_WET;                        /* sfx channels get the echo */
dm.mask[3] = AHIEDM_WET;
AHI_SetEffect(&dm, actrl);
```

## AHIET_DSPECHO

Add echo or delay to the wet channels (V4).

`struct AHIEffDSPEcho { ULONG ahie_Effect; ULONG ahiede_Delay; Fixed ahiede_Feedback; Fixed ahiede_Mix; Fixed ahiede_Cross; }`

| Field | Meaning |
|---|---|
| `ahiede_Delay` | Delay in sample frames of the MIX rate: `mixfreq * ms / 1000` (query `AHIC_MixFreq_Query`) |
| `ahiede_Feedback` | 0..`0x10000`: 0 = single delay, higher = repeating echo |
| `ahiede_Mix` | 0 = effect off .. `0x10000` = only the delayed signal is heard |
| `ahiede_Cross` | 0..`0x10000`: how much of the delayed signal crosses to the other side (stereo modes only) |

CPU cost (from the autodoc and user guide):

- Echo is expensive on most hardware; below a 68040 it can be unusable, which is
  why the prefs can disable echo entirely.
- `ahiede_Mix = 0x10000` with `ahiede_Cross = 0` selects much faster routines.
- With the user's "Fast Echo" option AHI may round parameters (to powers of two or
  to extremes): the sound can differ from what you asked.

### Example
```c
ULONG mixfreq = 0;
struct AHIEffDSPEcho echo;
AHI_ControlAudio(actrl, AHIC_MixFreq_Query, (ULONG)&mixfreq, TAG_DONE);
echo.ahie_Effect     = AHIET_DSPECHO;
echo.ahiede_Delay    = mixfreq / 4;             /* 250 ms */
echo.ahiede_Feedback = 0x8000;                  /* 0.5 */
echo.ahiede_Mix      = 0x10000;                 /* with Cross 0: fast path */
echo.ahiede_Cross    = 0;
if (AHI_SetEffect(&echo, actrl) != AHIE_OK) { /* no echo, carry on */ }
/* before AHI_FreeAudio: */
echo.ahie_Effect = AHIET_DSPECHO | AHIET_CANCEL;
AHI_SetEffect(&echo, actrl);
```

## AHIET_CHANNELINFO

Have a hook receive every channel's current play offset (V4).

`struct AHIEffChannelInfo { ULONG ahie_Effect; struct Hook *ahieci_Func; UWORD ahieci_Channels; UWORD ahieci_Pad; ULONG ahieci_Offset[]; }`

- `ahieci_Channels` MUST equal the allocated channel count; the structure must have
  room for that many ULONGs after the 12-byte header.
- Before each hook call (A0 hook, A2 AHIAudioCtrl, A1 structure) AHI stores each
  channel's offset in FRAMES into `ahieci_Offset[]`.
- Only offsets are reported: track sound, rate, volume per channel yourself.
- Typical use: sync graphics to sample playback, or read the play position of an
  `AHIST_DYNAMICSAMPLE` ring buffer that a software mixer keeps filling.

### Example
```c
static struct {
    struct AHIEffChannelInfo ci;
    ULONG                    offs[1];           /* 1 = AHIA_Channels */
} chinfo;
static volatile ULONG playPos;
static struct Hook infoHook;                     /* register stub + infoFunc */

static ULONG infoFunc(struct Hook *h, struct AHIAudioCtrl *a, struct AHIEffChannelInfo *ci)
{
    playPos = ci->ahieci_Offset[0];
    return 0;
}

chinfo.ci.ahie_Effect     = AHIET_CHANNELINFO;
chinfo.ci.ahieci_Func     = &infoHook;
chinfo.ci.ahieci_Channels = 1;
AHI_SetEffect(&chinfo, actrl);
```

## Channel volume and pan tricks

Negative volume and pan in AHI_SetVol (V4) as cheap per-channel effects.

- Negative volume plays the channel phase-inverted; negative pan sends it to the
  surround channel; both negative = inverted on surround.
- They cost more CPU than positive values. Drivers that can't do it use the absolute
  value. In "Fast" modes surround sounds fall back to the slower mixer, and the user
  can disable surround for them in the prefs.

## Common mistakes

Errors specific to AHI effects.

- Calling AHI_SetEffect from PlayerFunc/SoundFunc.
- Forgetting to cancel effects before AHI_FreeAudio.
- `ahiedm_Channels`/`ahieci_Channels` not equal to the allocated channel count, or
  the trailing array not allocated.
- Echo delay given in milliseconds instead of frames, or computed from the requested
  instead of the real mix rate.
- Disabling master volume by setting 1.0 instead of `AHIET_CANCEL`.
- Using a stack-local `AHIEffOutputBuffer`/`AHIEffChannelInfo` that goes out of scope
  while the effect is on.
