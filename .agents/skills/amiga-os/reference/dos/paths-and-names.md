# dos.library: paths, names and patterns

AmigaDOS paths are `volume:dir/dir/name`; a leading `:` means the root of the current volume
and each leading `/` means "parent". FilePart, PathPart, AddPart and SplitName edit path
strings in place without touching the disk. Wildcards are tokenized by ParsePattern(NoCase)
and tested with MatchPattern(NoCase); MatchFirst/MatchNext/MatchEnd walk the disk for every
object matching a pattern. Filenames are case-insensitive, so use the NoCase variants for
names. All of these are V36+ (the NoCase pair V37+).

## Pattern syntax

| Token | Meaning | Example |
|---|---|---|
| `?` | any one character | `a?c` matches `abc`, `a1c` |
| `#` | zero or more repeats of the next expression | `#?` = anything; `#[0-9]` = digits only |
| `(a\|b)` | any one of the `\|`-separated alternatives | `#?.(mod\|med)` |
| `~` | NOT the next expression (whole string must not match it) | `~(#?.info)` = all but `.info` files |
| `[abc]` | character class: any listed character | `[abc]#?` |
| `[~bc]` | negated class: any character not listed | `[~0-9]#?` |
| `a-z` | range, only inside a class | `[a-zA-Z]` |
| `%` | matches the empty string | `foo(bar\|%)` = `foo` or `foobar` |
| `*` | same as `#?`, but only when the system option is on (off by default in 2.0) | do not rely on it |

"Expression" (after `#` or `~`) is one character, one `( | )` group or one `[ ]` class.
Tokenized output needs at least `2 * strlen(pattern) + 2` bytes. MatchFirst tokenizes for
you; ExAll's `eac_MatchString`, MatchPattern and MatchPatternNoCase need pre-tokenized input.

## FilePart
`STRPTR FilePart(CONST_STRPTR path)` — LVO -870 (-$366)
Registers: path=D1; result in D0

Return a pointer to the last component (normally the file name) of a path string.

- **path** — path string (absolute or relative). It is not modified.
- **Result** — pointer INTO `path` at the last component; the start of the string if there
  is only one component. `"Work:Games/Foo/foo.cfg"` -> `"foo.cfg"`, `"Work:foo"` -> `"foo"`.

Since V36.

### Example
```c
UBYTE full[256] = "Work:Games/Foo/foo.cfg";
STRPTR name = FilePart(full);        /* "foo.cfg" */

*PathPart(full) = '\0';              /* full is now "Work:Games/Foo" */
Printf("dir=%s name=%s\n", (LONG)full, (LONG)name);   /* name is past the new NUL: still valid */
```

### Gotchas
- No copy is made: the result dies with (and changes with) the original string.

**See also:** [PathPart](#pathpart), [AddPart](#addpart)

## PathPart
`STRPTR PathPart(CONST_STRPTR path)` — LVO -876 (-$36C)
Registers: path=D1; result in D0

Return a pointer just past the directory portion of a path, where the file part begins.

- **path** — path string.
- **Result** — pointer INTO `path`: at the last `/` for `"Work:Games/Foo/foo.cfg"`, at the
  first character after `:` for `"Work:foo.cfg"`, at the start for a single component.
  Writing a NUL there truncates the string to its directory.

Since V36.

Example: see [FilePart](#filepart).

### Gotchas
- Differs from FilePart only in how `/` is handled: FilePart skips past the slash,
  PathPart points at it (so truncating does not leave a trailing `/`).

**See also:** [FilePart](#filepart), [AddPart](#addpart)

## AddPart
`BOOL AddPart(STRPTR dirname, CONST_STRPTR filename, ULONG size)` — LVO -882 (-$372)
Registers: dirname=D1, filename=D2, size=D3; result in D0

Append a file or subpath to a directory path in a buffer, inserting `/` as needed.

- **dirname** — buffer holding the directory path; modified in place.
- **filename** — name or relative path to add. A leading `/` goes up one level per slash; a
  name containing `:` (absolute) replaces `dirname` entirely.
- **size** — total size of the `dirname` buffer in bytes; must not be 0.
- **Result** — non-zero on success; 0 if the result would overflow (then `dirname` is left
  unchanged).

Since V36.

### Example
```c
UBYTE path[256] = "PROGDIR:";

if (!AddPart(path, "data/level1.dat", sizeof(path)))
    PutStr("path too long\n");
/* path = "PROGDIR:data/level1.dat" */
```

### Gotchas
- V36 (2.0-2.02) does not handle leading `/` and does not check for `:`; V37 accepts any
  path, including absolute ones.
- `size` is the buffer capacity, not the current string length.

**See also:** [FilePart](#filepart), [PathPart](#pathpart)

## SplitName
`WORD SplitName(CONST_STRPTR name, ULONG separator, STRPTR buf, LONG oldpos, LONG size)` — LVO -414 (-$19E)
Registers: name=D1, separator=D2, buf=D3, oldpos=D4, size=D5; result in D0

Copy the next separator-delimited component of a path into a buffer (handler helper).

- **name** — path being parsed.
- **separator** — character to split on (e.g. `'/'`).
- **buf** — receives the component, NUL-terminated, truncated to `size-1` characters.
- **oldpos** — position in `name` to start from (the value returned by the previous call).
- **size** — size of `buf` including the NUL.
- **Result** — position to pass as `oldpos` next time, or -1 when no further separator was
  found (the remaining text is still copied into `buf`). Result is a 16-bit WORD.

Since V36.

### Gotchas
- V36/V37: a component of `size` characters or more loses its last character when a
  separator follows (fixed V39). Workaround: pass a buffer one byte larger than you need as
  `size`, then force `buf[size-2] = '\0'`.
- The return type is WORD: in asm test/extend the low word (`ext.l d0`) before comparing
  with -1.

**See also:** [FilePart](#filepart), [PathPart](#pathpart), [AddPart](#addpart)

## MatchFirst
`LONG MatchFirst(CONST_STRPTR pat, struct AnchorPath *anchor)` — LVO -822 (-$336)
Registers: pat=D1, anchor=D2; result in D0

Start a wildcard search on disk and return the first matching file or directory.

- **pat** — raw (untokenized) pattern, e.g. `"DH0:Mods/#?.mod"`; see
  [pattern syntax](#pattern-syntax).
- **anchor** — longword-aligned `struct AnchorPath` (dos/dosasl.h), normally zeroed, set up
  before the call:
  - `ap_BreakBits` — break signals to honour (e.g. `SIGBREAKF_CTRL_C`) or 0;
    `ap_FoundBreak` — clear it; receives the signals that stopped the search.
  - `ap_Flags` — `APF_` flags or 0 (see below).
  - `ap_Strlen` — size of a buffer allocated directly after the structure (`ap_Buf`) to
    receive the full path of each match; 0 if you do not want full paths.
- **Result** — 0 on success (match described in `anchor`), otherwise a dos error code:
  `ERROR_NO_MORE_ENTRIES` (232) = nothing (more) found, `ERROR_BREAK` (304) = break signal,
  `ERROR_BUFFER_OVERFLOW` (303), or another dos error code.

On success: `ap_Info` holds an Examine() of the match (`fib_FileName`, `fib_DirEntryType`...),
`ap_Current->an_Lock` is a lock on the directory containing it, `ap_Buf` holds the full path
when `ap_Strlen` was set.

`APF_` flags (bits of the BYTE `ap_Flags`): `APF_DOWILD` 1 (user option ALL), `APF_ITSWILD` 2
(set by MatchFirst if the pattern has wildcards), `APF_DODIR` 4 (set it to enter the directory
just returned; clear it to skip), `APF_DIDDIR` 8 (set when a directory is revisited on the way
out), `APF_NOMEMERR` 16 (out of memory), `APF_DODOT` 32 (allow `.` as current directory),
`APF_DirChanged` 64 (`ap_Current->an_Lock` changed since the last call), `APF_FollowHLinks` 128
(follow hard links on DODIR; default off).

Since V36.

### Example
```c
#include <exec/memory.h>
#include <dos/dosasl.h>

#define PATHLEN 256

/* Print full paths of all files matching 'pattern'. Returns 0 or a dos error code. */
LONG ListMatches(CONST_STRPTR pattern)
{
    LONG err;
    struct AnchorPath *ap = AllocVec(sizeof(struct AnchorPath) + PATHLEN, MEMF_CLEAR);

    if (!ap)
        return ERROR_NO_FREE_STORE;
    ap->ap_BreakBits = SIGBREAKF_CTRL_C;       /* user can abort with Ctrl-C */
    ap->ap_Strlen    = PATHLEN;                /* we want ap_Buf filled */

    for (err = MatchFirst(pattern, ap); err == 0; err = MatchNext(ap)) {
        if (ap->ap_Info.fib_DirEntryType < 0)
            Printf("%s\n", (LONG)ap->ap_Buf);
    }
    MatchEnd(ap);                              /* always, success or not */
    FreeVec(ap);

    if (err == ERROR_NO_MORE_ENTRIES)
        err = 0;                               /* normal end of search */
    return err;                                /* ERROR_BREAK if Ctrl-C */
}
```

Recursive ("ALL") scan inside the loop body:
```c
if (ap->ap_Info.fib_DirEntryType > 0) {
    if (ap->ap_Flags & APF_DIDDIR)
        ap->ap_Flags &= ~APF_DIDDIR;           /* leaving a directory: just clear */
    else
        ap->ap_Flags |= APF_DODIR;             /* enter it on the next MatchNext */
}
```

### Gotchas
- Unlike most dos calls the error is the RETURN value, not IoErr().
- AnchorPath must be longword aligned and `ap_Buf` space must follow it in the SAME
  allocation (AllocVec gives both). Clear/reset the fields when reusing it.
- To operate on a match, `CurrentDir(ap->ap_Current->an_Lock)`, use `fib_FileName`, then
  CurrentDir back: this hits the right object even with two volumes of the same name.
  Use `ap_Buf` only for display.
- Patterns ending in `/` may return the directory lock with an empty `fib_FileName`.
- V36 has several lock/path bugs (fixed V37). Still in V37: a pattern that is a single
  directory name (e.g. `l`) entered with DODIR is re-locked relative to the current directory,
  so do not change the current directory between calls in that case.

**See also:** [MatchNext](#matchnext), [MatchEnd](#matchend), [ParsePattern](#parsepattern), [Examine](locks-and-directories.md#examine), [CurrentDir](locks-and-directories.md#currentdir), [ExNext](locks-and-directories.md#exnext)

## MatchNext
`LONG MatchNext(struct AnchorPath *anchor)` — LVO -828 (-$33C)
Registers: anchor=D1; result in D0

Continue a MatchFirst search and return the next matching object.

- **anchor** — the AnchorPath used with MatchFirst; `ap_Flags` may be changed between calls
  (`APF_DODIR` to enter a directory, clear `APF_DIDDIR`).
- **Result** — 0 on success, `ERROR_NO_MORE_ENTRIES` when finished, `ERROR_BREAK` on a break
  signal, or another dos error code.

Since V36.

Example and gotchas: see [MatchFirst](#matchfirst).

**See also:** [MatchFirst](#matchfirst), [MatchEnd](#matchend), [ParsePattern](#parsepattern), [CurrentDir](locks-and-directories.md#currentdir)

## MatchEnd
`VOID MatchEnd(struct AnchorPath *anchor)` — LVO -834 (-$342)
Registers: anchor=D1; no result

Free all locks and memory attached to an AnchorPath by MatchFirst/MatchNext.

- **anchor** — the (longword-aligned) AnchorPath of the search. The structure itself is
  yours to free afterwards.

Since V36.

### Gotchas
- Call it whenever the search is over: normal end, error, break, or you quit early.
  Skipping it leaks directory locks.

**See also:** [MatchFirst](#matchfirst), [MatchNext](#matchnext)

## ParsePattern
`LONG ParsePattern(CONST_STRPTR pat, STRPTR buf, LONG buflen)` — LVO -840 (-$348)
Registers: pat=D1, buf=D2, buflen=D3; result in D0

Tokenize a wildcard pattern for the case-sensitive MatchPattern.

- **pat** — source pattern; see [pattern syntax](#pattern-syntax).
- **buf** — output buffer for the tokenized pattern.
- **buflen** — size of `buf`; use at least `2 * strlen(pat) + 2`.
- **Result** — 1 = pattern contains wildcards, 0 = plain string (no wildcards), -1 = buffer
  overflow or other error.

Since V36.

### Gotchas
- Always handle -1 even with a large buffer: the token format may change.
- A 0 result means the "pattern" is a literal name: you can Lock/Open it directly instead of
  scanning.
- V37: IoErr() is not always meaningful after an error (fixed V39).
- For filenames use ParsePatternNoCase; this variant is case-sensitive.

**See also:** [ParsePatternNoCase](#parsepatternnocase), [MatchPattern](#matchpattern), [MatchFirst](#matchfirst), [MatchNext](#matchnext)

## ParsePatternNoCase
`LONG ParsePatternNoCase(CONST_STRPTR pat, UBYTE *buf, LONG buflen)` — LVO -966 (-$3C6)
Registers: pat=D1, buf=D2, buflen=D3; result in D0

Tokenize a wildcard pattern for the case-insensitive MatchPatternNoCase.

- **pat** — source pattern.
- **buf** — output buffer; at least `2 * strlen(pat) + 2` bytes.
- **buflen** — size of `buf`.
- **Result** — 1 wildcards present, 0 none, -1 overflow/error.

Since V37.

### Example
```c
UBYTE tok[2 * 32 + 2];                  /* pattern up to 32 chars */
LONG wild = ParsePatternNoCase("#?.(mod|med)", tok, sizeof(tok));

if (wild < 0)
    PutStr("bad pattern\n");
else if (MatchPatternNoCase(tok, (STRPTR)fib->fib_FileName))
    Printf("module: %s\n", (LONG)fib->fib_FileName);
```

### Gotchas
- V37: character classes (`[a-z]`) are not upper-cased, so they match case-sensitively.
  Workaround: upper-case the pattern first (utility.library ToUpper). Fixed in V39.
- V37: IoErr() not always set on error (fixed V39).
- The output is only valid for MatchPatternNoCase and ExAll's `eac_MatchString`.

**See also:** [ParsePattern](#parsepattern), [MatchPatternNoCase](#matchpatternnocase), [MatchFirst](#matchfirst), [ExAll](locks-and-directories.md#exall), utility.library ToUpper

## MatchPattern
`BOOL MatchPattern(CONST_STRPTR pat, STRPTR str)` — LVO -846 (-$34E)
Registers: pat=D1, str=D2; result in D0

Test a string against a pattern tokenized by ParsePattern (case-sensitive).

- **pat** — tokenized pattern from ParsePattern (not the raw pattern).
- **str** — string to test.
- **Result** — non-zero on a match, 0 otherwise. On 0, IoErr() is 0 (plain mismatch) or
  `ERROR_TOO_MANY_LEVELS` (217, recursion limit; V37+).

Since V36.

### Gotchas
- Highly recursive: needs at least 1500 bytes of free stack (about 100 nesting levels of
  `#`, `(`, `~`). V36 had no stack check.
- Passing a raw pattern gives wrong results silently.

**See also:** [ParsePattern](#parsepattern), [MatchPatternNoCase](#matchpatternnocase), [MatchFirst](#matchfirst), [MatchNext](#matchnext)

## MatchPatternNoCase
`BOOL MatchPatternNoCase(CONST_STRPTR pat, STRPTR str)` — LVO -972 (-$3CC)
Registers: pat=D1, str=D2; result in D0

Test a string against a pattern tokenized by ParsePatternNoCase (case-insensitive).

- **pat** — tokenized pattern from ParsePatternNoCase.
- **str** — string to test (e.g. `fib_FileName`).
- **Result** — non-zero on a match, 0 otherwise; IoErr() 0 or `ERROR_TOO_MANY_LEVELS` on 0.

Since V37.

Example: see [ParsePatternNoCase](#parsepatternnocase).

### Gotchas
- Same 1500-byte stack requirement as MatchPattern.
- Inherits the V37 character-class bug of ParsePatternNoCase.

**See also:** [ParsePatternNoCase](#parsepatternnocase), [MatchPattern](#matchpattern), [MatchFirst](#matchfirst), [MatchNext](#matchnext)
