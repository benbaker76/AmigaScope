# AHI audio modes

How to choose the mode ID and mixing rate an AHI program allocates: take the user's
default, ask with the requester, search with AHI_BestAudioIDA, or enumerate the
database. All of these work right after opening `AHI_NO_UNIT`; none needs
AHI_AllocAudioA. Tag values: [tags.md](../tags.md#ahidb-tags).

## Strategy

Recommended order for picking a mode.

1. First run: `AHIA_AudioID, AHI_DEFAULT_ID` + `AHIA_MixFreq, AHI_DEFAULT_FREQ`
   (the user's Music-unit settings). Zero configuration.
2. Settings screen: AHI_AudioRequestA (with `AHIR_DoMixFreq`, `AHIR_DoDefaultMode`,
   filters for what you need); save `ahiam_AudioID` and `ahiam_MixFreq`.
3. Next run: verify the saved ID still exists (AHI_GetAudioAttrsA returns FALSE for
   unknown IDs, per the V4 source) and still fits your needs; otherwise fall back to 1.
4. Headless/automatic choice: AHI_BestAudioIDA with hard requirements plus
   `AHIB_Dizzy` wishes.

Never ship a hardcoded ID other than `AHI_DEFAULT_ID`: IDs identify one machine's hardware.

## Mode ID layout

What the 32 bits of an audio ID mean (for recognising, not constructing, IDs).

| Bits | Meaning |
|---|---|
| 31-16 | Hardware ID, allocated to drivers by the AHI author |
| 15-12 | Card number (first card 0) |
| 11-8 | D/A converter on the card (first 0) |
| 4-0 | Mode within the driver |
| others | 0 |

Reserved: `AHI_DEFAULT_ID` = `0`, `AHI_LOOPBACK_ID` = `1`, `AHI_INVALID_ID` = `0xFFFFFFFF`.

## Enumerating with AHI_NextAudioID

Walk every mode in the database and read its attributes.

```c
ULONG id = AHI_INVALID_ID;
while ((id = AHI_NextAudioID(id)) != AHI_INVALID_ID) {
    char  name[64];
    ULONG bits = 0, stereo = 0, panning = 0, hifi = 0, realtime = 0,
          maxch = 0, minf = 0, maxf = 0, rec = 0;
    name[0] = 0;
    AHI_GetAudioAttrs(id, NULL,
        AHIDB_BufferLen,   sizeof(name),
        AHIDB_Name,        (ULONG)name,
        AHIDB_Bits,        (ULONG)&bits,
        AHIDB_Stereo,      (ULONG)&stereo,
        AHIDB_Panning,     (ULONG)&panning,
        AHIDB_HiFi,        (ULONG)&hifi,
        AHIDB_Realtime,    (ULONG)&realtime,
        AHIDB_MaxChannels, (ULONG)&maxch,
        AHIDB_MinMixFreq,  (ULONG)&minf,
        AHIDB_MaxMixFreq,  (ULONG)&maxf,
        AHIDB_Record,      (ULONG)&rec,
        TAG_DONE);
    /* list it ... */
}
```

```asm
        move.l  _AHIBase,a6
        moveq   #AHI_INVALID_ID,d0      ; ~0 fits moveq (-1)
.next:  jsr     _LVOAHI_NextAudioID(a6)
        cmp.l   #AHI_INVALID_ID,d0
        beq.s   .done
        move.l  d0,d7                   ; keep the ID (d7 survives calls)
        ; ... AHI_GetAudioAttrsA: d0 = ID, a2 = 0, a1 = taglist ...
        move.l  d7,d0
        bra.s   .next
.done:
```

## AHI_GetAudioAttrsA queries

Read what a mode (or an allocated handle) can do.

- By ID: `AHI_GetAudioAttrs(id, NULL, ...)`; `id` may be `AHI_DEFAULT_ID` (V4).
- For an allocated handle: `AHI_GetAudioAttrs(AHI_INVALID_ID, actrl, ...)`; some tags
  return wrong values if you ask by ID instead.
- Pointers for results (4-byte variables, pre-cleared: missing attributes are not
  written); plain values for `AHIDB_BufferLen`, `AHIDB_FrequencyArg`,
  `AHIDB_IndexArg`, `AHIDB_InputArg`, `AHIDB_OutputArg`; buffer address for strings.

Supported rates list:

```c
ULONG n = 0;
AHI_GetAudioAttrs(id, NULL, AHIDB_Frequencies, (ULONG)&n, TAG_DONE);
for (ULONG i = 0; i < n; i++) {
    ULONG hz = 0;
    AHI_GetAudioAttrs(id, NULL, AHIDB_FrequencyArg, i,
                                AHIDB_Frequency,    (ULONG)&hz, TAG_DONE);
}
/* nearest supported rate to 22050: */
ULONG idx = 0, hz = 0;
AHI_GetAudioAttrs(id, NULL, AHIDB_IndexArg, 22050, AHIDB_Index, (ULONG)&idx, TAG_DONE);
AHI_GetAudioAttrs(id, NULL, AHIDB_FrequencyArg, idx, AHIDB_Frequency, (ULONG)&hz, TAG_DONE);
```

Attributes that matter most for games and players:

| Attribute | Why |
|---|---|
| `AHIDB_Realtime` | FALSE = renders offline (file save). Only usable with PlayerFunc timing |
| `AHIDB_MaxChannels` | Must cover `AHIA_Channels` or AHI_AllocAudioA fails |
| `AHIDB_Panning` | Without it a stereo mode puts even channels left, odd right |
| `AHIDB_Volume` | FALSE = no per-channel volume |
| `AHIDB_HiFi` | TRUE = best quality, much more CPU |
| `AHIDB_Bits` | Output resolution |
| `AHIDB_MaxPlaySamples` | Buffer size for `AHIST_DYNAMICSAMPLE` |
| `AHIDB_Record`, `AHIDB_FullDuplex` | Recording ability |

## AHI_BestAudioIDA

Let AHI rank the database against hard requirements and soft preferences.

- Main taglist = filters. Only present tags count. Booleans are exact: TRUE = must
  have, FALSE = must NOT have. `AHIDB_Bits` and `AHIDB_MaxChannels` are minimums;
  `AHIDB_MinMixFreq, hz` keeps modes whose lowest rate is <= hz; `AHIDB_MaxMixFreq, hz`
  keeps modes whose highest rate is >= hz. `AHIDB_AudioID, id` = same hardware as `id`.
- `AHIB_Dizzy` (V4) = pointer to a second taglist of wishes: among the survivors the
  mode with the most wanted and fewest unwanted features wins. Without it the
  choice is barely "best".
- Result `AHI_INVALID_ID` when nothing passes; fall back to `AHI_DEFAULT_ID`.
- ahi.device <= 4.158: boolean tag values must be exactly 1 for TRUE.

```c
struct TagItem prefer[] = {
    { AHIDB_Panning, TRUE },
    { AHIDB_HiFi,    FALSE },               /* cheaper mixing preferred */
    { AHIDB_Bits,    16 },
    { TAG_DONE,      0 }
};
ULONG id = AHI_BestAudioID(AHIDB_Realtime,    TRUE,
                           AHIDB_MaxChannels, 8,
                           AHIB_Dizzy,        (ULONG)prefer,
                           TAG_DONE);
if (id == AHI_INVALID_ID)
    id = AHI_DEFAULT_ID;
```

## AHI_AudioRequestA

Let the user pick a mode and rate with the system-style requester.

```c
struct TagItem needs[] = { { AHIDB_Realtime, TRUE }, { TAG_DONE, 0 } };
struct AHIAudioModeRequester *req = AHI_AllocAudioRequest(
    AHIR_Window,         (ULONG)win,        /* or AHIR_PubScreenName */
    AHIR_SleepWindow,    TRUE,
    AHIR_TitleText,      (ULONG)"Sound output",
    AHIR_DoMixFreq,      TRUE,
    AHIR_DoDefaultMode,  TRUE,
    AHIR_FilterTags,     (ULONG)needs,
    TAG_DONE);
if (req) {
    if (AHI_AudioRequest(req,
            AHIR_InitialAudioID, cfg.audioID,
            AHIR_InitialMixFreq, cfg.mixFreq,
            TAG_DONE)) {
        cfg.audioID = req->ahiam_AudioID;    /* AHI_DEFAULT_ID if "default" chosen */
        cfg.mixFreq = req->ahiam_MixFreq;    /* AHI_DEFAULT_FREQ likewise */
    } else if (IoErr() != 0) {
        /* ERROR_NO_FREE_STORE or ERROR_NO_MORE_ENTRIES (filter removed all modes) */
    }
    AHI_FreeAudioRequest(req);
}
```

- Tags given to AHI_AudioRequestA stay in effect for later calls on the same requester.
- `AHIR_FilterFunc` hook: A0 hook, A1 = mode ID (ULONG, not a pointer), A2 requester;
  return TRUE to show the mode. Needs the register stub in C.
- `AHIR_TextAttr` fonts must already be loaded (AHI uses OpenFont).
- The requester structure is read-only.
- With `AHIR_DoDefaultMode` and filters, re-validate "default" with AHI_BestAudioIDA
  at use time; the user may change the default mode later.
- The requester needs Intuition and a screen.

## Choosing a mixing rate

Balance quality against CPU for the chosen mode.

- The rate you pass is rounded to one the driver supports; always read back
  `AHIC_MixFreq_Query` after AHI_AllocAudioA and base echo delays, dynamic buffer
  sizes and PlayerFreq limits on it.
- `MixFreq / PlayerFreq` must stay <= 65535 and should stay > 80, i.e. PlayerFreq
  between MixFreq/65535 and MixFreq/80 (at 8000 Hz mixing: at most 100 Hz). Check
  `AHIA_MaxPlayerFreq` against the real mix rate.
- Software mixing cost scales with rate x channels (x2 for stereo, much more for
  HiFi). On 68020/030 machines modest rates (for example 11-22 kHz) and non-HiFi modes
  keep the CPU free for the game.
- Paula's native driver on 15 kHz screens is limited to about 28 kHz (user guide); the
  user must allow higher rates via prefs/env variables.

## Common mistakes

Errors when selecting modes.

- `AHIDB_Stereo, FALSE` in BestAudioID meaning "don't care" (it excludes stereo modes).
- Forgetting `AHIDB_BufferLen`, so names come back empty.
- Passing `&index` for `AHIDB_FrequencyArg` or `AHIDB_IndexArg` (they take values).
- Treating the value from `AHIR_DoDefaultMode` (0) as an invalid ID.
- Picking a non-realtime mode for a VBlank-timed player.
