# utility.library: dates

Amiga time stamps count seconds from 01-Jan-1978 00:00:00. These three calls convert between that
count and a broken-down `struct ClockData`. dos.library's `struct DateStamp` uses the same epoch
(days / minutes / ticks): seconds = `ds_Days * 86400 + ds_Minute * 60 + ds_Tick / TICKS_PER_SECOND`
(`TICKS_PER_SECOND` = 50, dos/dos.h). For formatted date strings use dos.library DateToStr instead.

`struct ClockData` (utility/date.h; asm utility/date.i, offsets checked with gcc and vasm):

| Offset | Field (C and asm) | Type | Meaning |
|---|---|---|---|
| $00 | `sec` | UWORD | seconds 0-59 |
| $02 | `min` | UWORD | minutes 0-59 |
| $04 | `hour` | UWORD | hours 0-23 |
| $06 | `mday` | UWORD | day of month 1-31 |
| $08 | `month` | UWORD | month 1-12 |
| $0A | `year` | UWORD | full year, e.g. 1994 |
| $0C | `wday` | UWORD | day of week 0-6, 0 = Sunday |
| $0E | `CD_SIZE` | | size 14 |

The value ranges are the usual convention, not stated in the NDK headers or autodocs (unverified).
asm gotcha: date.i defines the bare labels `sec`, `min`, `hour`, `mday`, `month`, `year`, `wday`,
which clash with your own symbols of the same name.

## Amiga2Date
`VOID Amiga2Date(ULONG seconds, struct ClockData *result)` — LVO -120 (-$78)
Registers: seconds=D0, result=A0; no result

Fill a ClockData with the calendar date and time of a seconds-since-1978 value.

- **seconds** — seconds since 01-Jan-1978 00:00:00.
- **result** — your ClockData; every field including `wday` is written.

Since V36.

### Example
```c
#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/utility.h>
#include <dos/dos.h>
#include <utility/date.h>

extern struct DosLibrary *DOSBase;
extern struct UtilityBase *UtilityBase;

/* today's date from the system clock (needs a Process for DateStamp) */
void Today(struct ClockData *cd)
{
    struct DateStamp ds;
    ULONG secs;

    DateStamp(&ds);
    secs = ds.ds_Days * 86400UL + ds.ds_Minute * 60UL + ds.ds_Tick / TICKS_PER_SECOND;
    Amiga2Date(secs, cd);       /* cd->year, cd->month, cd->mday, cd->hour ... */
}
```

**See also:** [Date2Amiga](#date2amiga), [CheckDate](#checkdate), [DateStamp](../dos/time.md#datestamp)

## Date2Amiga
`ULONG Date2Amiga(CONST struct ClockData *date)` — LVO -126 (-$7E)
Registers: date=A0; result in D0

Convert a ClockData into seconds since 01-Jan-1978, without validating it.

- **date** — filled-in ClockData (`wday` is not needed).
- **Result** — seconds since 01-Jan-1978 00:00:00.

Since V36.

### Gotchas
- No sanity checking (autodoc warning): garbage in, garbage out. Validate user input with
  [CheckDate](#checkdate), which returns the same value for a legal date.

**See also:** [CheckDate](#checkdate), [Amiga2Date](#amiga2date)

## CheckDate
`ULONG CheckDate(CONST struct ClockData *date)` — LVO -132 (-$84)
Registers: date=A0; result in D0

Validate a ClockData and return its seconds since 1978, or 0 if it is illegal.

- **date** — filled-in ClockData.
- **Result** — 0 for an illegal date, otherwise the seconds since 01-Jan-1978.

Since V36.

### Example
```asm
; a2 = ClockData typed in by the user
        include "utility/date.i"
        include "lvo/utility_lib.i"

        move.l  _UtilityBase,a6
        move.l  a2,a0
        jsr     _LVOCheckDate(a6)
        tst.l   d0
        beq     .baddate                ; (or exactly 01-Jan-1978 00:00:00)
        move.l  d0,newtime
```

### Gotchas
- `wday` is not checked (autodoc BUGS).
- 0 is also the correct answer for 01-Jan-1978 00:00:00, so that one moment reads as "illegal".

**See also:** [Date2Amiga](#date2amiga), [Amiga2Date](#amiga2date)
