# dos.library: date and time

DOS time is a `struct DateStamp` (`dos/dos.h`): `ds_Days` since 1 January 1978, `ds_Minute`
past midnight, `ds_Tick` past the minute at `TICKS_PER_SECOND` (50) ticks per second, on PAL
and NTSC alike. `DateToStr()`/`StrToDate()` convert through a `struct DateTime`
(`dos/datetime.h`). `Delay()` sleeps in the same 1/50 s ticks. None of this is a frame or
high-resolution timer: use graphics WaitTOF() for vertical-blank sync and timer.device for
sub-second measurement.

`struct DateTime`: `dat_Stamp` (DateStamp), `dat_Format` (UBYTE), `dat_Flags` (UBYTE),
`dat_StrDay`, `dat_StrDate`, `dat_StrTime` (UBYTE * buffers, `LEN_DATSTRING` = 16 bytes each).

| Format | Value | Layout (datetime.h comment) |
|---|---|---|
| `FORMAT_DOS` | 0 | dd-mmm-yy |
| `FORMAT_INT` | 1 | yy-mm-dd (autodoc says yy-mmm-dd) |
| `FORMAT_USA` | 2 | mm-dd-yy |
| `FORMAT_CDN` | 3 | dd-mm-yy |
| `FORMAT_DEF` | 4 | locale default, FORMAT_DOS if no locale (C header only; not in datetime.i) |

Flags: `DTF_SUBST` (1) use "Today", "Monday" etc. where possible (DateToStr only);
`DTF_FUTURE` (2) weekday names mean the next such day, not the last (StrToDate only).
Unknown format values fall back to `FORMAT_DOS`.

## DateStamp
`struct DateStamp * DateStamp(struct DateStamp *date)` — LVO -192 (-$C0)
Registers: date=D1; result in D0

Fill a DateStamp with the current date and time.

- **date** — `struct DateStamp` to fill (3 LONGs).
- **Result** — `date` (returned for 1.x compatibility).

### Example
```c
struct DateStamp ds;
DateStamp(&ds);
ULONG secs = ds.ds_Days * 86400UL + ds.ds_Minute * 60UL + ds.ds_Tick / TICKS_PER_SECOND;
/* seconds since 1-Jan-1978; enough for timestamps and random seeds */
```

```asm
        move.l  DOSBase,a6
        move.l  #stamp,d1
        jsr     _LVODateStamp(a6)
        move.l  stamp+ds_Days,d0        ; days since 1-Jan-1978
        ...

        section bss,bss
stamp   ds.b    ds_SIZEOF               ; struct DateStamp (dos/dos.i)
```

### Gotchas
- `ds_Tick` currently only advances in whole seconds (multiples of 50 ticks): DateStamp cannot
  time anything shorter than a second.
- All three fields are 0 if the clock was never set.
- Day and minute are guaranteed consistent (no midnight roll-over race inside one call).

**See also:** [CompareDates](#comparedates), [DateToStr](#datetostr), [StrToDate](#strtodate),
[SetFileDate](files.md#setfiledate)

## Delay
`VOID Delay(LONG timeout)` — LVO -198 (-$C6)
Registers: timeout=D1; no result

Sleep the calling process for a number of ticks (50 per second).

- **timeout** — ticks to wait (the autodoc calls it `ticks`, unsigned).
- **Result** — none.

### Example
```asm
        move.l  DOSBase,a6
        moveq   #TICKS_PER_SECOND,d1    ; one second
        jsr     _LVODelay(a6)
```

### Gotchas
- A real wait (the process sleeps), not a busy loop -- but not synchronised to the display:
  use graphics WaitTOF() or a vertical-blank interrupt for per-frame timing.
- Process only; do not call from an exec Task, an interrupt, or with the OS switched off.
- Kickstart 1.2/1.3: `Delay(0)` could disturb the timer and floppy operation (fixed V36); avoid
  zero if you still support 1.x.

**See also:** [DateStamp](#datestamp), [WaitForChar](files.md#waitforchar),
[CheckSignal](processes.md#checksignal)

## CompareDates
`LONG CompareDates(CONST struct DateStamp *date1, CONST struct DateStamp *date2)` — LVO -738 (-$2E2)
Registers: date1=D1, date2=D2; result in D0

Compare two DateStamps.

- **date1**, **date2** — stamps to compare.
- **Result** — negative if `date1` is LATER than `date2`, 0 if equal, positive if `date2` is
  later.

Since V36.

### Example
```c
if (CompareDates(&srcfib->fib_Date, &dstfib->fib_Date) < 0) {
    /* source is newer than destination: copy it */
}
```

### Gotchas
- The sign is the reverse of `strcmp(date1, date2)` intuition: `< 0` means date1 is newer.

**See also:** [DateStamp](#datestamp), [DateToStr](#datetostr), [StrToDate](#strtodate)

## DateToStr
`LONG DateToStr(struct DateTime *datetime)` — LVO -744 (-$2E8)
Registers: datetime=D1; result in D0

Format a DateStamp as day, date and time strings.

- **datetime** — a `struct DateTime` with `dat_Stamp` set, `dat_Format`, `dat_Flags`
  (`DTF_SUBST` honoured) and up to three buffers (`dat_StrDay`, `dat_StrDate`, `dat_StrTime`,
  each `LEN_DATSTRING` bytes); a NULL buffer pointer skips that string.
- **Result** — non-zero on success, 0 if the DateStamp was invalid.

Since V36.

### Example
```c
#include <dos/datetime.h>

struct DateTime dt = { 0 };
char day[LEN_DATSTRING], date[LEN_DATSTRING], clock[LEN_DATSTRING];

DateStamp(&dt.dat_Stamp);
dt.dat_Format  = FORMAT_DOS;
dt.dat_Flags   = DTF_SUBST;          /* allow "Today", "Yesterday"... */
dt.dat_StrDay  = (UBYTE *)day;
dt.dat_StrDate = (UBYTE *)date;
dt.dat_StrTime = (UBYTE *)clock;
if (DateToStr(&dt))
    Printf("%s %s %s\n", (LONG)day, (LONG)date, (LONG)clock);
```

### Gotchas
- The NDK prototype returns LONG, the autodoc BOOL: test for non-zero.
- With `DTF_SUBST` the date string may be a word, not digits -- clear it when you need a
  parseable or fixed-width date.

**See also:** [StrToDate](#strtodate), [DateStamp](#datestamp), [CompareDates](#comparedates)

## StrToDate
`LONG StrToDate(struct DateTime *datetime)` — LVO -750 (-$2EE)
Registers: datetime=D1; result in D0

Parse date and/or time strings into the DateStamp inside a DateTime.

- **datetime** — `struct DateTime` with `dat_Format`, `dat_Flags` (`DTF_FUTURE` honoured),
  `dat_StrDate` (date in the chosen format, or "Today", "Tomorrow", "Monday"...; NULL leaves
  `ds_Days` unchanged) and `dat_StrTime` (`hh:mm:ss`; NULL leaves `ds_Minute`/`ds_Tick`
  unchanged). `dat_StrDay` is ignored.
- **Result** — non-zero on success with `dat_Stamp` filled, 0 if the strings could not be
  converted.

Since V36.

### Example
```c
struct DateTime dt = { 0 };
DateStamp(&dt.dat_Stamp);                    /* keep today's date */
dt.dat_Format  = FORMAT_DOS;
dt.dat_StrTime = (UBYTE *)"23:59:00";
if (!StrToDate(&dt))
    PutStr("bad time\n");
```

### Gotchas
- The autodoc says `dat_Stamp` is ignored on input, yet a NULL string pointer leaves the
  matching fields untouched -- initialise `dat_Stamp` when you pass only one of the strings.

**See also:** [DateToStr](#datetostr), [DateStamp](#datestamp)
