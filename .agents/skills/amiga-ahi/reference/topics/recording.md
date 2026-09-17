# AHI recording

Two ways to sample audio through AHI: the RecordFunc hook of the library API
(exclusive, full control of input, gain and monitoring) or `CMD_READ` on a device
unit (simple, shared, converted to the format you ask for).

## Is recording possible?

Check the mode's capabilities before trying to record.

- `AHIDB_Record` TRUE: the mode can sample. `AHIDB_FullDuplex` TRUE: it can play at
  the same time. Without full duplex, `AHIC_Record` TRUE stops playback and
  `AHIC_Play` TRUE stops recording; device reads/writes clash with `AHIE_HALFDUPLEX`.
- Find a mode: `AHI_BestAudioID(AHIDB_Record, TRUE, TAG_DONE)` (add
  `AHIDB_FullDuplex, TRUE` only if you must play while recording), or restrict the
  requester with `AHIR_FilterTags` pointing at `{ AHIDB_Record, TRUE }, { TAG_DONE }`.
- Paula driver: 8-bit modes record through parallel-port samplers; its 14-bit modes
  cannot record (user guide).

## Input selection and monitoring

Query card controls with AHI_GetAudioAttrsA and set them with AHI_ControlAudioA (V2).

| Control | Range / list query | Set | Read back |
|---|---|---|---|
| Input source | `AHIDB_Inputs` (count); name i: `AHIDB_InputArg, i` + `AHIDB_Input, buf` | `AHIC_Input, i` | `AHIC_Input_Query, &ul` |
| Input gain | `AHIDB_MinInputGain`, `AHIDB_MaxInputGain` (Fixed) | `AHIC_InputGain, fixed` | `AHIC_InputGain_Query, &fx` |
| Monitor (input to output) | `AHIDB_MinMonitorVolume`, `AHIDB_MaxMonitorVolume` | `AHIC_MonitorVolume, fixed` | `AHIC_MonitorVolume_Query, &fx` |
| Output | `AHIDB_Outputs`; `AHIDB_OutputArg, i` + `AHIDB_Output, buf` | `AHIC_Output, i` | `AHIC_Output_Query, &ul` |
| Output volume | `AHIDB_MinOutputVolume`, `AHIDB_MaxOutputVolume` | `AHIC_OutputVolume, fixed` | `AHIC_OutputVolume_Query, &fx` |

- Min == Max gain or volume: no adjustable control on that card.
- Monitor min and max both 0: no monitor feature. Equal but non-zero: the card always
  monitors at that level.
- Input 0 / output 0 are the defaults. Names need `AHIDB_BufferLen`.
- Hardware monitoring has the lowest latency; copying RecordFunc data to a playing
  `AHIST_DYNAMICSAMPLE` adds at least one buffer of delay.

### Example
```c
ULONG inputs = 0;
Fixed gmin = 0, gmax = 0;
char  name[32];

AHI_GetAudioAttrs(AHI_INVALID_ID, actrl,
                  AHIDB_Inputs,      (ULONG)&inputs,
                  AHIDB_MinInputGain,(ULONG)&gmin,
                  AHIDB_MaxInputGain,(ULONG)&gmax,
                  TAG_DONE);
for (ULONG i = 0; i < inputs; i++) {
    name[0] = 0;
    AHI_GetAudioAttrs(AHI_INVALID_ID, actrl,
                      AHIDB_BufferLen, sizeof(name),
                      AHIDB_InputArg,  i,
                      AHIDB_Input,     (ULONG)name,
                      TAG_DONE);
    /* show name ... */
}
Fixed gain = 0x10000;                              /* 1.0, clamped to the card's range */
if (gain > gmax) gain = gmax;
if (gain < gmin) gain = gmin;
AHI_ControlAudio(actrl,
                 AHIC_Input,         0,
                 AHIC_InputGain,     gain,
                 AHIC_MonitorVolume, 0,             /* check AHIDB_Min/MaxMonitorVolume first */
                 TAG_DONE);
```

## Library API: RecordFunc

Record with a hook that receives blocks of 16-bit stereo frames at the mixing rate.

1. Open `AHI_NO_UNIT`, AHI_AllocAudioA with the recording mode, the wanted rate as
   `AHIA_MixFreq`, `AHIA_RecordFunc`, and `AHIA_Channels, 1`, `AHIA_Sounds, 1` (both
   are always required).
2. Real sample rate: `AHIC_MixFreq_Query`. Block size:
   `AHI_GetAudioAttrs(AHI_INVALID_ID, actrl, AHIDB_MaxRecordSamples, (ULONG)&frames, TAG_DONE)`
   gives the frames per hook call; size your copy buffers from it.
3. Set input, gain, monitor (above).
4. `AHI_ControlAudio(actrl, AHIC_Record, TRUE, TAG_DONE)` (task context).
5. In the hook: check `ahirm_Type` (today always `AHIST_S16S`), copy `ahirm_Length`
   frames (x4 bytes) from `ahirm_Buffer` to your buffer, `Signal()` your task when a
   buffer is full, return 0.
6. The task writes full buffers to disk. Stop with `AHIC_Record, FALSE`, then AHI_FreeAudio.

Hook contract: A0 hook, A2 AHIAudioCtrl, A1 `struct AHIRecordMessage *`; preserve
D2-D7/A2-A6; `ahirm_Buffer` is valid only until the next call; it may run in an
interrupt, so never `Write()` from it; D0 MUST be 0 on return (undocumented before
the V6 autodoc).

### Example
```c
/* RecordFunc body; call it through the h_Entry register stub
   (low-level-playback topic, Hooks). */
struct RecState {
    struct Task *task;
    ULONG        sigMask;
    WORD        *buf;              /* frames * 2 WORDs */
    ULONG        size;             /* capacity in frames */
    ULONG        fill;             /* frames stored */
    BOOL         full;             /* set by hook, cleared by task after writing */
};

static ULONG recordFunc(struct Hook *h, struct AHIAudioCtrl *actrl,
                        struct AHIRecordMessage *rm)
{
    struct RecState *rs = h->h_Data;
    if (rm->ahirm_Type != AHIST_S16S || rs->full)
        return 0;                  /* unknown format or task too slow: drop */
    ULONG  n   = rm->ahirm_Length;
    WORD  *src = rm->ahirm_Buffer;
    WORD  *dst = rs->buf + rs->fill * 2;
    if (n > rs->size - rs->fill)
        n = rs->size - rs->fill;
    rs->fill += n;
    for (n *= 2; n; n--)           /* L and R words; no library calls needed */
        *dst++ = *src++;
    if (rs->fill == rs->size) {
        rs->full = TRUE;
        Signal(rs->task, rs->sigMask);
    }
    return 0;                      /* MUST be 0 */
}
```

The task loop: `Wait(sigMask)`, `Write()` `fill*4` bytes, set `fill = 0`, `full = FALSE`.
Frames arriving while `full` is set are dropped; size the buffer so the task keeps up.

```asm
; vasm RecordFunc: peak meter of the left channel into 'peak' (UWORD).
; A0 = hook, A2 = AHIAudioCtrl, A1 = AHIRecordMessage
recordfunc:
        move.l  d2,-(sp)
        cmp.l   #AHIST_S16S,ahirm_Type(a1)
        bne.s   .out                    ; unknown format: ignore
        move.l  ahirm_Length(a1),d1     ; frames
        beq.s   .out
        move.l  ahirm_Buffer(a1),a0
        moveq   #0,d2                   ; running max
.loop:  move.w  (a0),d0                 ; left sample, sets N
        addq.l  #4,a0                   ; skip L+R (addq to An leaves CCR alone)
        bpl.s   .pos
        neg.w   d0
.pos:   cmp.w   d2,d0
        bls.s   .next
        move.w  d0,d2
.next:  subq.l  #1,d1
        bne.s   .loop
        move.w  d2,peak
.out:   move.l  (sp)+,d2
        moveq   #0,d0                   ; RecordFunc must return 0
        rts
```

## Device API: CMD_READ

Record from a shared unit with I/O requests; AHI converts rate and format.

- Open unit `AHI_DEFAULT_UNIT` (or the user's unit) with `ahir_Version` 4.
- Request: `io_Command = CMD_READ`, `io_Data` buffer, `io_Length` bytes (multiple of
  the frame size), `ahir_Type` = `AHIST_M8S`/`AHIST_M16S`/`AHIST_S8S`/`AHIST_S16S`,
  `ahir_Frequency` Hz, `io_Offset = 0` for the first read.
- Continuous: `DoIO` the first read; then repeatedly `SendIO` the next read on the
  same request without touching `io_Offset`, save the previous buffer while it
  fills, `WaitIO`, swap buffers. `io_Actual` = bytes delivered.
- Quality: the unit samples at its prefs rate and AHI resamples without a proper
  filter. Asking for a lower rate than the unit's aliases; a higher rate is merely
  band-limited. Request the unit's rate when quality matters.
- Input, gain and monitor come from the unit's prefs, not from your program.

### Example
```c
/* req opened on AHI_DEFAULT_UNIT; bufA/bufB are BUFBYTES each */
req->ahir_Std.io_Command = CMD_READ;
req->ahir_Std.io_Data    = bufA;
req->ahir_Std.io_Length  = BUFBYTES;
req->ahir_Std.io_Offset  = 0;                   /* first read only */
req->ahir_Type      = AHIST_M16S;
req->ahir_Frequency = 22050;
if (DoIO((struct IORequest *)req) == 0) {
    for (;;) {
        ULONG got = req->ahir_Std.io_Actual;
        req->ahir_Std.io_Data   = bufB;         /* all but io_Device/io_Unit/io_Command */
        req->ahir_Std.io_Length = BUFBYTES;     /* are trashed: set them again,       */
        req->ahir_Type          = AHIST_M16S;   /* but keep io_Offset as returned     */
        req->ahir_Frequency     = 22050;
        SendIO((struct IORequest *)req);
        saveBuffer(bufA, got);                  /* while the next read fills */
        if (Wait((1UL << port->mp_SigBit) | SIGBREAKF_CTRL_C) & SIGBREAKF_CTRL_C)
            break;
        if (WaitIO((struct IORequest *)req) != 0)
            break;
        WORD *t = bufA; bufA = bufB; bufB = t;
    }
    if (!CheckIO((struct IORequest *)req))
        AbortIO((struct IORequest *)req);
    WaitIO((struct IORequest *)req);
}
```

## Common mistakes

Errors specific to recording.

- Not checking `ahirm_Type` / assuming the buffer is mono or 8-bit.
- Treating `ahirm_Length` as bytes (it is frames; bytes = frames * 4 for S16S).
- Doing file I/O or allocation inside RecordFunc; returning non-zero from it.
- Keeping `ahirm_Buffer` pointers past the next hook call.
- Clearing `io_Offset` between continuous CMD_READs (causes gaps/restarts).
- Setting gain/monitor values outside the `AHIDB_Min*`/`AHIDB_Max*` range.
- Starting `AHIC_Play` on a half-duplex mode and wondering why recording stopped.
