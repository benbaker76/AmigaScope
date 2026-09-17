# ahi.device: device (I/O request) interface

The high-level API: a normal Exec device. Send `struct AHIRequest`s with
`CMD_WRITE` to play and `CMD_READ` to record; AHI mixes all writers, converts
format and rate on the fly, and lets many programs share the card (up to the
channel count the user set for the unit). Lengths here are in **bytes** (the
library API counts frames). Needs ahi.device V4+ (V2 had only the library API;
V1 and V3 are obsolete). For games/music with tight timing use the library API
instead ([functions.md](functions.md)).

C: `#include <devices/ahi.h>` (AHI SDK `Include/C`) plus `<proto/exec.h>`. Asm:
`include "devices/ahi.i"` (SDK `Include/Asm`), `include "exec/io.i"`, `lvo/exec_lib.i`.

## OpenDevice
`BYTE OpenDevice(AHINAME, ULONG unit, struct AHIRequest *req, ULONG flags)` — exec LVO -444
Registers: name=A0, unit=D0, ioRequest=A1, flags=D1; error in D0 (also `io_Error`)

Open ahi.device on a unit for I/O, or on `AHI_NO_UNIT` to reach the library API.

- **AHINAME** — `"ahi.device"`.
- **unit** — `AHI_DEFAULT_UNIT` (0), another unit 1-3 the user asked for (e.g. a
  `UNIT` tooltype), or `AHI_NO_UNIT` (255) for low-level use. Units 0-3 are configured
  (mode, rate, channels) in the AHI prefs; `AHI_NO_UNIT` is the prefs "Music unit".
- **req** — from `CreateIORequest(port, sizeof(struct AHIRequest))`.
  **`ahir_Version` must be set before the call** to the minimum version you need
  (4 for the device API, 6 for 32-bit/7.1 types).
- **flags** — 0. `AHIDF_NOMODESCAN` only for mode-database tools (skips building
  the database from `DEVS:AudioModes`).
- **Result** — 0 = success, `io_Device` is the device base (= `AHIBase` for the
  library calls). Otherwise `IOERR_OPENFAIL` (-1), also when the installed device is
  older than `ahir_Version`.

Each open re-reads `ENV:Sys/ahi.prefs`; the first open also loads the mode database.

### Example
```c
struct MsgPort    *port = CreateMsgPort();
struct AHIRequest *req  = port ? (struct AHIRequest *)
                          CreateIORequest(port, sizeof(struct AHIRequest)) : NULL;
BOOL opened = FALSE;
if (req) {
    req->ahir_Version = 4;
    opened = (OpenDevice(AHINAME, AHI_DEFAULT_UNIT, (struct IORequest *)req, 0) == 0);
}
```

```asm
        move.l  4.w,a6
        jsr     _LVOCreateMsgPort(a6)
        move.l  d0,ahiport
        beq     .fail
        move.l  d0,a0
        moveq   #AHIRequest_SIZEOF,d0   ; 80
        jsr     _LVOCreateIORequest(a6)
        move.l  d0,ahireq
        beq     .fail
        move.l  d0,a1
        move.w  #4,ahir_Version(a1)     ; BEFORE OpenDevice
        lea     ahiname,a0
        moveq   #AHI_DEFAULT_UNIT,d0    ; AHI_NO_UNIT (255) needs move.l
        moveq   #0,d1
        jsr     _LVOOpenDevice(a6)
        tst.b   d0
        bne     .fail
        ...
ahiname:
        AHINAME                         ; macro from devices/ahi.i: dc.b "ahi.device",0
        even
```

### Gotchas
- Forgetting `ahir_Version` (left 0 by CreateIORequest) silently accepts any old device.
- Don't CloseDevice after a failed open; `io_Device` is -1 then.
- `AHI_NO_UNIT` opens no unit (`io_Unit` = NULL): never send CMD_WRITE/CMD_READ on it.
- `devices/ahi.i` has `OPENAHI <ver>` / `CLOSEAHI` macros for the `AHI_NO_UNIT` case;
  see [low-level-playback topic](topics/low-level-playback.md) for their caveats.

**See also:** CloseDevice, AHIRequest, [overview topic](topics/overview.md)

## CloseDevice
`void CloseDevice(struct IORequest *req)` — exec LVO -450
Registers: ioRequest=A1; no result

Close the unit opened with this request; every successful OpenDevice needs one.

- **req** — the SAME request used for OpenDevice.

All requests you sent must have completed first: `AbortIO()` + `WaitIO()` each one
still pending. Then `DeleteIORequest()` the original, `FreeVec()` any copies you
made, `DeleteMsgPort()`.

**See also:** OpenDevice, Double buffering

## AHIRequest

Extended `IOStdReq` used for every ahi.device command.

| Off | C field | Asm label | Type | Use |
|---|---|---|---|---|
| 0 | `ahir_Std` | `ahir_Std` | struct IOStdReq | Standard part (48 bytes) |
| 9 | `ahir_Std.io_Message.mn_Node.ln_Pri` | `LN_PRI` | BYTE | CMD_WRITE precedence -128..127 |
| 20 | `ahir_Std.io_Device` | `IO_DEVICE` | struct Device * | Device base after OpenDevice |
| 28 | `ahir_Std.io_Command` | `IO_COMMAND` | UWORD | `CMD_WRITE`, `CMD_READ`... |
| 31 | `ahir_Std.io_Error` | `IO_ERROR` | BYTE | 0, `AHIE_` or `IOERR_` code |
| 32 | `ahir_Std.io_Actual` | `IO_ACTUAL` | ULONG | Bytes done |
| 36 | `ahir_Std.io_Length` | `IO_LENGTH` | ULONG | Bytes, a multiple of the frame size |
| 40 | `ahir_Std.io_Data` | `IO_DATA` | APTR | Sample buffer |
| 44 | `ahir_Std.io_Offset` | `IO_OFFSET` | ULONG | 0 for writes; read position for reads |
| 48 | `ahir_Version` | `ahir_Version` | UWORD | Minimum device version (set before OpenDevice) |
| 50 | `ahir_Pad1` | `ahir_Pad1` | UWORD | V4+ fields follow |
| 52 | `ahir_Private[2]` | `ahir_Private1/2` | ULONG[2] | Hands off |
| 60 | `ahir_Type` | `ahir_Type` | ULONG | Sample format `AHIST_M8S`... |
| 64 | `ahir_Frequency` | `ahir_Frequency` | ULONG | Sample rate in Hz |
| 68 | `ahir_Volume` | `ahir_Volume` | Fixed | 0 (mute) .. `0x10000` (full) |
| 72 | `ahir_Position` | `ahir_Position` | Fixed | 0 left, `0x8000` centre, `0x10000` right |
| 76 | `ahir_Link` | `ahir_Link` | struct AHIRequest * | Play after this earlier request; else NULL |
| 80 | sizeof | `AHIRequest_SIZEOF` | | |

After completion every field except `io_Device`, `io_Unit`, `io_Command` is trashed:
set all of them again before re-sending.

Formats: [AHIST sample formats](tags.md#ahist-sample-formats). Errors:
[AHIE error codes](tags.md#ahie-error-codes).

**See also:** CMD_WRITE, CMD_READ

## CMD_WRITE

Play `io_Length` bytes of samples on the unit, mixed with other programs (V4).

| Input | Value |
|---|---|
| `io_Command` | `CMD_WRITE` (3) |
| `io_Data` | Sample buffer (MEMF_PUBLIC; chip RAM not needed) |
| `io_Length` | Bytes, multiple of the frame size |
| `io_Offset` | 0 |
| `ln_Pri` | Precedence (see below) |
| `ahir_Type` | `AHIST_M8S`, `AHIST_M16S`, `AHIST_S8S`, `AHIST_S16S`; V6: `AHIST_M32S`, `AHIST_S32S` |
| `ahir_Frequency` | Hz of the data (converted to the unit's rate) |
| `ahir_Volume` | Fixed 0..`0x10000` |
| `ahir_Position` | Fixed 0..`0x10000` (`0x8000` centre) |
| `ahir_Link` | Previous request to follow, or NULL |

Result: `io_Error` 0 or error; `io_Actual` = bytes played (V6: valid even when
aborted/failed).

Precedence: if more writes are active than the unit has channels, the lowest
precedence ones play muted (and keep advancing) until a channel frees up. It
cannot be changed while playing. audio.device's scale applies: 127 unstoppable,
90..100 emergency, 80..90 annunciator, 75 speech, 50..70 sonic cue, -50..50
music, -70..-50 sound effects, -100..-80 background, -128 silence.

### Example
```asm
; A1 = AHIRequest opened on a unit; plays synchronously
        move.l  ahireq,a1
        move.b  #-60,LN_PRI(a1)         ; sound-effect precedence
        move.w  #CMD_WRITE,IO_COMMAND(a1)
        move.l  #sample,IO_DATA(a1)
        move.l  #SAMPLE_BYTES,IO_LENGTH(a1)
        clr.l   IO_OFFSET(a1)
        move.l  #AHIST_M8S,ahir_Type(a1)
        move.l  #11025,ahir_Frequency(a1)
        move.l  #$10000,ahir_Volume(a1)
        move.l  #$8000,ahir_Position(a1)
        clr.l   ahir_Link(a1)
        move.l  4.w,a6
        jsr     _LVODoIO(a6)            ; returns when done, D0 = io_Error
```

### Gotchas
- `io_Length` in BYTES; an odd byte count for 16-bit data is a bug.
- 16/32-bit data is big-endian signed. Unsigned 8-bit (WAV) data must be flipped (`^0x80`).
- One request can only be in flight once: copy it for a second simultaneous sound.
- The developer guide advises against the device API for music; latency is set by
  AHI/the driver, not by you (community reports ~20 ms, unverified).

**See also:** Double buffering, Several sounds at once, CMD_STOP, CMD_START

## CMD_READ

Record `io_Length` bytes from the preferred input in your format and rate (V4).

| Input | Value |
|---|---|
| `io_Command` | `CMD_READ` (2) |
| `io_Data` | Buffer |
| `io_Length` | Bytes, multiple of the frame size |
| `io_Offset` | 0 on the first read or after a pause; leave the returned value for continuous reads |
| `ahir_Type` | Signed mono or stereo only (`AHIST_M8S`, `AHIST_M16S`, `AHIST_S8S`, `AHIST_S16S`) |
| `ahir_Frequency` | Hz wanted |

Result: `io_Error`, `io_Actual` = bytes read (V6: valid even on error), `io_Offset`
updated for the next read.

### Gotchas
- Asking a rate different from the unit's rate resamples without proper filtering:
  lower quality (aliasing if the unit rate is higher). Use the unit's rate when you can.
- Half-duplex hardware: reads and writes conflict (`AHIE_HALFDUPLEX`).
- Continuous recording: see Double buffering; don't reset `io_Offset` between reads.

**See also:** [recording topic](topics/recording.md), Double buffering

## CMD_STOP, CMD_START

Pause all CMD_WRITE processing, then release the queued writes together (V4).

- `CMD_STOP` (6): new writes queue up instead of playing.
- `CMD_START` (7): everything queued since CMD_STOP starts synchronised.
- Only `io_Command` is needed; `io_Error` returns the result.

### Gotchas
- Affects EVERY program's writes on the device, not just yours: keep the
  STOP..START window tiny.
- Unlike other devices, STOP/START nest in ahi.device: match every STOP with a START.

**See also:** CMD_WRITE

## CMD_FLUSH, CMD_RESET

Abort every program's requests; RESET also reloads prefs and resets the hardware (V4).

- `CMD_FLUSH` (8): aborts all active and queued requests; `io_Actual` = count flushed.
- `CMD_RESET` (1): flush + reload the configuration + hardware back to its initial state.

Never use them in applications; they exist for AHI system utilities.

## NSCMD_DEVICEQUERY

Standard New-Style-Device query of device type and supported commands (V4).

- `io_Command` = `NSCMD_DEVICEQUERY` (`0x4000`), `io_Data` = cleared
  `struct NSDeviceQueryResult`, `io_Length` = its size (16).
- Layout: `DevQueryFormat` ULONG @0 (0), `SizeAvailable` ULONG @4 (clear it; AHI sets 16),
  `DeviceType` UWORD @8 (AHI: `NSDEVTYPE_UNKNOWN` 0), `DeviceSubType` UWORD @10,
  `SupportedCommands` UWORD * @12 (0-terminated list).
- AHI lists: `NSCMD_DEVICEQUERY`, `CMD_RESET`, `CMD_READ`, `CMD_WRITE`, `CMD_STOP`,
  `CMD_START`, `CMD_FLUSH`. Anything else returns `IOERR_NOCMD`.

`devices/newstyle.h` is not in the NDK 3.9 include tree used here; declare the
structure yourself with the layout above.

## Double buffering

Gap-free streaming: queue the next buffer while one plays, chained by `ahir_Link`.

Writing (two requests, two buffers):

1. After OpenDevice, `AllocVec(sizeof(struct AHIRequest), MEMF_PUBLIC)` a second
   request and `CopyMem()` the opened one into it.
2. Fill buffer A, `SendIO` request A with `ahir_Link = NULL`.
3. Fill buffer B, set request B `ahir_Link = &A`, `SendIO` B (it starts exactly when A ends).
4. `Wait` for A's reply, `WaitIO(A)`; refill A, set A's `ahir_Link = &B`, `SendIO(A)`. Repeat, swapping roles.
5. At the end: `WaitIO` the last one (let it finish) or `AbortIO`+`WaitIO` both.

Reading (one request): `DoIO` the first read with `io_Offset = 0`; then `SendIO` the
next read on the same request WITHOUT clearing `io_Offset`, process the previous
buffer while it fills, `WaitIO`, swap buffers, repeat.

### Gotchas
- `ahir_Link` must point to a request that is still in flight or just finished; NULL
  when not chaining.
- Free the copy with `FreeVec`, never `DeleteIORequest` (it was not created by
  CreateIORequest).
- A buffer must stay valid until its request is replied.

**See also:** Example: streaming with ahir_Link

## Several sounds at once

Play overlapping sounds by sending one copied request per sound.

Copy the opened request (as for double buffering) once per simultaneous sound and
`CMD_WRITE` each copy. AHI allocates channels dynamically: if the user configured
fewer channels than active writes, the lowest precedence writes are muted (still
advancing) until others end. To sync several starts, bracket the writes with
CMD_STOP / CMD_START. To mix many voices into one stream yourself, stream one
buffer instead (see Double buffering).

## Example: play a buffer

Complete C function: open unit 0 and play one second of 8-bit tone with DoIO.

```c
#include <exec/types.h>
#include <exec/memory.h>
#include <exec/io.h>
#include <devices/ahi.h>
#include <proto/exec.h>

#define RATE    22050
#define FRAMES  RATE                            /* one second, AHIST_M8S = 1 byte/frame */

/* returns 0 on success, else io_Error / -1 */
LONG ahiPlayTone(void)
{
    struct MsgPort    *port;
    struct AHIRequest *req;
    BYTE              *buf;
    LONG               rc = -1;

    if (!(buf = AllocVec(FRAMES, MEMF_PUBLIC)))
        return -1;
    for (ULONG i = 0; i < FRAMES; i++)          /* 441 Hz square wave */
        buf[i] = ((i / 25) & 1) ? 48 : -48;

    if ((port = CreateMsgPort())) {
        if ((req = (struct AHIRequest *)CreateIORequest(port, sizeof(struct AHIRequest)))) {
            req->ahir_Version = 4;
            if (OpenDevice(AHINAME, AHI_DEFAULT_UNIT, (struct IORequest *)req, 0) == 0) {
                req->ahir_Std.io_Message.mn_Node.ln_Pri = 0;
                req->ahir_Std.io_Command = CMD_WRITE;
                req->ahir_Std.io_Data    = buf;
                req->ahir_Std.io_Length  = FRAMES;  /* bytes */
                req->ahir_Std.io_Offset  = 0;
                req->ahir_Type      = AHIST_M8S;
                req->ahir_Frequency = RATE;
                req->ahir_Volume    = 0x10000;       /* 1.0 */
                req->ahir_Position  = 0x8000;        /* centre */
                req->ahir_Link      = NULL;
                rc = DoIO((struct IORequest *)req);  /* blocks until played */
                CloseDevice((struct IORequest *)req);
            }
            DeleteIORequest((struct IORequest *)req);
        }
        DeleteMsgPort(port);
    }
    FreeVec(buf);                                  /* after the request completed */
    return rc;
}
```

For non-blocking playback use `SendIO`, then `Wait` on `1UL << port->mp_SigBit`
and `WaitIO`; before closing, `AbortIO` + `WaitIO` if still pending.

## Example: streaming with ahir_Link

Complete C function: gap-free 16-bit stereo stream from a fill callback until Ctrl-C.

```c
#include <exec/types.h>
#include <exec/memory.h>
#include <exec/io.h>
#include <dos/dos.h>                               /* SIGBREAKF_CTRL_C */
#include <devices/ahi.h>
#include <proto/exec.h>

#define RATE   44100
#define CHUNK  (RATE / 10)                         /* frames per buffer (100 ms) */
#define BYTES  (CHUNK * 4)                         /* AHIST_S16S: 4 bytes/frame */

extern void fillAudio(WORD *lr, ULONG frames);     /* your mixer / decoder */

LONG ahiStream(void)
{
    struct MsgPort    *port = CreateMsgPort();
    struct AHIRequest *req[2] = { NULL, NULL };
    WORD              *buf[2] = { NULL, NULL };
    BOOL               busy[2] = { FALSE, FALSE }, opened = FALSE;
    struct AHIRequest *link = NULL;
    int                cur = 0;

    if (!port)
        return -1;
    req[0] = (struct AHIRequest *)CreateIORequest(port, sizeof(struct AHIRequest));
    buf[0] = AllocVec(BYTES, MEMF_PUBLIC);
    buf[1] = AllocVec(BYTES, MEMF_PUBLIC);
    if (!req[0] || !buf[0] || !buf[1])
        goto out;
    req[0]->ahir_Version = 4;
    if (OpenDevice(AHINAME, AHI_DEFAULT_UNIT, (struct IORequest *)req[0], 0) != 0)
        goto out;
    opened = TRUE;
    if (!(req[1] = AllocVec(sizeof(struct AHIRequest), MEMF_PUBLIC)))
        goto out;
    CopyMem(req[0], req[1], sizeof(struct AHIRequest));   /* copy AFTER OpenDevice */

    for (;;) {
        struct AHIRequest *r = req[cur];

        fillAudio(buf[cur], CHUNK);
        r->ahir_Std.io_Command = CMD_WRITE;
        r->ahir_Std.io_Data    = buf[cur];
        r->ahir_Std.io_Length  = BYTES;
        r->ahir_Std.io_Offset  = 0;
        r->ahir_Type      = AHIST_S16S;
        r->ahir_Frequency = RATE;
        r->ahir_Volume    = 0x10000;
        r->ahir_Position  = 0x8000;
        r->ahir_Link      = link;                  /* start right after the previous one */
        SendIO((struct IORequest *)r);
        busy[cur] = TRUE;

        if (link) {                                /* wait until the older buffer is done */
            ULONG sig = Wait((1UL << port->mp_SigBit) | SIGBREAKF_CTRL_C);
            if (sig & SIGBREAKF_CTRL_C)
                break;
            LONG err = WaitIO((struct IORequest *)link);
            busy[cur ^ 1] = FALSE;                 /* link == req[cur ^ 1] */
            if (err != 0)
                break;                             /* error or aborted */
        }
        link = r;
        cur ^= 1;
    }

out:
    for (int i = 0; i < 2; i++)
        if (busy[i]) {
            AbortIO((struct IORequest *)req[i]);
            WaitIO((struct IORequest *)req[i]);
        }
    if (opened)
        CloseDevice((struct IORequest *)req[0]);
    if (req[1]) FreeVec(req[1]);                   /* the copy: FreeVec, not DeleteIORequest */
    if (req[0]) DeleteIORequest((struct IORequest *)req[0]);
    if (buf[0]) FreeVec(buf[0]);
    if (buf[1]) FreeVec(buf[1]);
    DeleteMsgPort(port);
    return 0;
}
```

The fill callback runs in your task, so it may be slow-ish, but it must finish a
100 ms buffer in well under 100 ms or the stream underruns.
