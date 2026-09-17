# utility.library: strings

Case-insensitive comparison and case conversion that handle international characters, not only
ASCII A-Z. All four are V37. When locale.library is running it
replaces them with code for the user's language, so results may differ between systems: never use
them to build sort orders or hashes that must be stable on disk, and don't use them in tight
game loops where a plain ASCII compare will do.

## Stricmp
`LONG Stricmp(CONST_STRPTR string1, CONST_STRPTR string2)` — LVO -162 (-$A2)
Registers: string1=A0, string2=A1; result in D0

Compare two NUL-terminated strings ignoring case.

- **string1, string2** — strings to compare. A shorter string compares as if padded with zeros.
- **Result** — < 0 if string1 sorts before string2, 0 if equal, > 0 if after.

Since V37.

### Example
```c
#include <proto/utility.h>

extern struct UtilityBase *UtilityBase;

BOOL IsIconFile(CONST_STRPTR name, ULONG len)
{
    /* compare the last 5 characters with ".info", any case */
    return len >= 5 && Stricmp(name + len - 5, (CONST_STRPTR)".info") == 0;
}
```

### Gotchas
- Language-dependent once locale.library is installed (autodoc NOTE): identical pairs of strings may
  compare differently under different language settings.
- Test the sign of the full LONG, not just "-1/0/1".

**See also:** [Strnicmp](#strnicmp), [ToUpper](#toupper), locale.library StrnCmp

## Strnicmp
`LONG Strnicmp(CONST_STRPTR string1, CONST_STRPTR string2, LONG length)` — LVO -168 (-$A8)
Registers: string1=A0, string2=A1, length=D0; result in D0

Compare at most length characters of two strings ignoring case.

- **string1, string2** — strings to compare. A shorter string compares as if padded with zeros.
- **length** — maximum number of characters to examine.
- **Result** — < 0, 0 or > 0 as for [Stricmp](#stricmp).

Since V37.

### Example
```asm
; a2 = command line: does it start with "QUIT" (any case)?
        include "lvo/utility_lib.i"

        move.l  _UtilityBase,a6
        move.l  a2,a0
        lea     quitword(pc),a1
        moveq   #4,d0
        jsr     _LVOStrnicmp(a6)
        tst.l   d0
        beq     .quit

quitword:
        dc.b    "quit",0
        even
```

### Gotchas
- Language-dependent once locale.library is installed (autodoc NOTE).

**See also:** [Stricmp](#stricmp), locale.library StrnCmp

## ToUpper
`UBYTE ToUpper(ULONG character)` — LVO -174 (-$AE)
Registers: character=D0; result in D0

Convert one character to upper case, including international characters.

- **character** — character code; only the low byte is meaningful (the SFD types it UBYTE).
- **Result** — upper-case character (UBYTE): use the low byte of D0 only.

Since V37.

### Gotchas
- Language-dependent once locale.library is installed (autodoc NOTE).
- asm: follow with `and.l #$ff,d0` (or use `move.b d0,...`) before using D0 as a long.

**See also:** [ToLower](#tolower), [Stricmp](#stricmp), locale.library ConvToUpper

## ToLower
`UBYTE ToLower(ULONG character)` — LVO -180 (-$B4)
Registers: character=D0; result in D0

Convert one character to lower case, including international characters.

- **character** — character code; only the low byte is meaningful (the SFD types it UBYTE).
- **Result** — lower-case character (UBYTE): use the low byte of D0 only.

Since V37.

### Gotchas
- Language-dependent once locale.library is installed (autodoc NOTE).

**See also:** [ToUpper](#toupper), locale.library ConvToLower
