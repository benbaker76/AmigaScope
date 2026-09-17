# dos.library: buffered I/O

Since V36 every file handle carries its own buffer; these calls read and write through it and
only talk to the handler when it is empty/full (or at a newline on consoles). They are much
faster than `Read`/`Write` for small pieces. Never mix them with unbuffered
[Read](files.md#read)/[Write](files.md#write)/[Seek](files.md#seek) on the same handle without
calling [Flush](#flush) in between. Watch the return conventions: `FPuts`, `PutStr` and
`SetVBuf` return 0 on SUCCESS; `FGetC`/`FPutC` use -1 (`ENDSTREAMCH`) for EOF/error; the
formatted-print calls return a count or -1.

dos/stdio.h wraps some of them for the default streams: `ReadChar()` = `FGetC(Input())`,
`WriteChar(c)` = `FPutC(Output(),c)`, `UnReadChar(c)`, `ReadChars(buf,n)`, `ReadLn(buf,len)` =
`FGets(Input(),buf,len)`, `WriteStr(s)` = `FPuts(Output(),s)`, `VWritef(fmt,argv)`.

## FGetC
`LONG FGetC(BPTR fh)` — LVO -306 (-$132)
Registers: fh=D1; result in D0

Read one character from a file handle through its buffer.

- **fh** — file handle.
- **Result** — the character as 0-255, or -1 (`ENDSTREAMCH`) at end of file or on error. To
  tell them apart, `SetIoErr(0)` before reading and check `IoErr()` afterwards (0 = plain EOF;
  the autodoc does not state this for FGetC, unverified).

Since V36.

### Example
```c
/* count lines of a text file */
LONG c, lines = 0;
SetIoErr(0);
while ((c = FGetC(fh)) != -1)
    if (c == '\n')
        lines++;
if (IoErr())
    PrintFault(IoErr(), "read");
```

### Gotchas
- Store the result in a LONG, not a UBYTE/char, or you cannot see the -1.
- V36: once EOF was hit, every later FGetC returned EOF. From V37 it asks the handler again
  (useful on consoles), unless `UnGetC(fh,-1)` pushed the EOF back.
- `Flush()` before switching to `Read`/`Seek` on the same handle.

**See also:** [UnGetC](#ungetc), [FPutC](#fputc), [Flush](#flush), [FGets](#fgets)

## UnGetC
`LONG UnGetC(BPTR fh, LONG character)` — LVO -318 (-$13E)
Registers: fh=D1, character=D2; result in D0

Push a character back so the next buffered read returns it again.

- **fh** — file handle used for buffered input.
- **character** — character to push back, or -1 to push back the last character read (if that
  was EOF, the next read returns EOF again).
- **Result** — the character pushed back, or 0 (FALSE) if it could not be pushed back.

Since V36.

### Gotchas
- Only one push-back after each buffered read is guaranteed.
- V36: `UnGetC(fh,-1)` after an EOF did not make the next read return EOF; fixed in V37.

**See also:** [FGetC](#fgetc), [FPutC](#fputc), [Flush](#flush)

## FGets
`STRPTR FGets(BPTR fh, STRPTR buf, ULONG buflen)` — LVO -336 (-$150)
Registers: fh=D1, buf=D2, buflen=D3; result in D0

Read one line (up to a newline or EOF) from a file handle into a buffer.

- **fh** — file handle.
- **buf** — destination buffer; the result is always null-terminated and keeps the `'\n'` if the
  line ended with one.
- **buflen** — size of `buf`, > 0. At most `buflen-1` characters are stored; longer lines are
  split across calls.
- **Result** — `buf`, or NULL if EOF came before any character or on error (`IoErr()` is 0 for a
  plain EOF).

Since V36.

### Example
```c
UBYTE line[128];
/* pass size-1: V36/V37 write one byte too many (see Gotchas) */
while (FGets(fh, line, sizeof(line) - 1)) {
    UBYTE *p = line;
    while (*p && *p != '\n')
        p++;
    *p = 0;                                  /* strip the newline */
    parse_line(line);
}
if (IoErr())
    PrintFault(IoErr(), "config");
```

### Gotchas
- V36/V37 bug: when a line does not fit, it copies `buflen` characters and writes the null at
  `buf[buflen]` (one past the end). Fixed in V39. Pass `sizeof(buf)-1` for 2.x-safe code.
- A line longer than the buffer comes back without `'\n'`; the rest arrives on the next call.

**See also:** [FRead](#fread), [FPuts](#fputs), [FGetC](#fgetc)

## FRead
`LONG FRead(BPTR fh, APTR block, ULONG blocklen, ULONG number)` — LVO -324 (-$144)
Registers: fh=D1, block=D2, blocklen=D3, number=D4; result in D0

Read a number of fixed-size blocks through the handle's buffer.

- **fh** — file handle.
- **block** — destination buffer, at least `blocklen * number` bytes.
- **blocklen** — bytes per block, > 0.
- **number** — blocks wanted, > 0.
- **Result** — number of complete BLOCKS read (not bytes); 0 at EOF; fewer than requested on EOF
  or error.

Since V36.

### Gotchas
- It does not clear IoErr() first: call `SetIoErr(0)` before FRead if you want to tell a short
  read at EOF from an error.
- For large blocks plain `Read()` avoids a copy through the buffer.

**See also:** [FGetC](#fgetc), [FWrite](#fwrite), [FGets](#fgets), [Read](files.md#read)

## FPutC
`LONG FPutC(BPTR fh, LONG ch)` — LVO -312 (-$138)
Registers: fh=D1, ch=D2; result in D0

Write one character to a file handle through its buffer.

- **fh** — file handle.
- **ch** — character, passed as a LONG in the range 0-255.
- **Result** — the character written, or -1 (`ENDSTREAMCH`) on error.

Since V36.

### Gotchas
- Interactive (console) handles are flushed automatically on `'\n'`, `'\r'` or `'\0'`; files are
  flushed only when the buffer fills, on `Flush()` or on `Close()`.
- Old autodocs said UBYTE; pass a full LONG (0-255).

**See also:** [FGetC](#fgetc), [UnGetC](#ungetc), [Flush](#flush)

## FPuts
`LONG FPuts(BPTR fh, CONST_STRPTR str)` — LVO -342 (-$156)
Registers: fh=D1, str=D2; result in D0

Write a null-terminated string to a file handle through its buffer (no newline added).

- **fh** — file handle.
- **str** — string to write.
- **Result** — 0 on success, -1 on error. Inverted compared with most dos calls.

Since V36.

### Example
```c
if (FPuts(fh, "[settings]\n") != 0)          /* non-zero = FAILED */
    PrintFault(IoErr(), "prefs");
```

### Gotchas
- `if (FPuts(...))` is true on FAILURE.

**See also:** [FGets](#fgets), [FPutC](#fputc), [FWrite](#fwrite), [PutStr](#putstr)

## FWrite
`LONG FWrite(BPTR fh, CONST APTR block, ULONG blocklen, ULONG number)` — LVO -330 (-$14A)
Registers: fh=D1, block=D2, blocklen=D3, number=D4; result in D0

Write a number of fixed-size blocks through the handle's buffer.

- **fh** — file handle.
- **block** — source data, `blocklen * number` bytes.
- **blocklen** — bytes per block, > 0.
- **number** — blocks to write, > 0.
- **Result** — number of complete BLOCKS written; fewer than requested on error (disk full...).

Since V36.

### Gotchas
- It does not clear IoErr() first: `SetIoErr(0)` before calling if you check it afterwards.
- Buffered data is written later; also check `Flush()`/`Close()` results.

**See also:** [FPutC](#fputc), [FRead](#fread), [FPuts](#fputs), [Write](files.md#write)

## PutStr
`LONG PutStr(CONST_STRPTR str)` — LVO -948 (-$3B4)
Registers: str=D1; result in D0

Write a null-terminated string to the default output, buffered (no newline added).

- **str** — string to write to `Output()`.
- **Result** — 0 on success, -1 on error. Inverted compared with most dos calls.

Since V36.

### Example
```c
PutStr("Usage: mygame [LEVEL <n>] [NOSOUND]\n");
```

```asm
        move.l  DOSBase,a6
        lea     usage(pc),a0
        move.l  a0,d1
        jsr     _LVOPutStr(a6)          ; d0 = 0 ok / -1 error
        ...
usage:  dc.b    "Usage: mygame [LEVEL <n>]",10,0
```

### Gotchas
- Does nothing useful when `Output()` is 0 (e.g. started from Workbench).
- Cheapest way to print a constant string: no format parsing, unlike `Printf`.

**See also:** [FPuts](#fputs), [FPutC](#fputc), [FWrite](#fwrite), [WriteChars](#writechars),
[Output](files.md#output)

## WriteChars
`LONG WriteChars(CONST_STRPTR buf, ULONG buflen)` — LVO -942 (-$3AE)
Registers: buf=D1, buflen=D2; result in D0

Write a counted run of bytes to the default output, buffered.

- **buf** — bytes to write (need not be null-terminated).
- **buflen** — number of bytes.
- **Result** — number of bytes written, or -1 on error.

Since V36.

**See also:** [FPuts](#fputs), [FPutC](#fputc), [FWrite](#fwrite), [PutStr](#putstr)

## VFPrintf
`LONG VFPrintf(BPTR fh, CONST_STRPTR format, CONST APTR argarray)` — LVO -354 (-$162)
Registers: fh=D1, format=D2, argarray=D3; result in D0

Format values with RawDoFmt codes and write the text to a file handle, buffered.

- **fh** — file handle.
- **format** — exec RawDoFmt format string (`%ld`, `%lu`, `%lx`, `%s`, `%lc`, `%b` for a BSTR...).
- **argarray** — pointer to the packed argument values (32-bit each when every code has `l`).
- **Result** — number of bytes written, or -1 on error (reason in `IoErr()`).

The varargs form `FPrintf(fh, format, ...)` builds the array for you (amiga.lib stub, or the
inline macro in Bartman's `proto/dos.h`).

Since V36.

### Example
```c
LONG args[2];
args[0] = (LONG)"level1";
args[1] = 1500;
VFPrintf(fh, "%s=%ld\n", args);

FPrintf(fh, "%s=%ld\n", (LONG)"level2", 2300L);     /* same with varargs */
```

### Gotchas
- RawDoFmt reads `%d`, `%x` and `%c` as 16-bit WORDs unless `l` is given; the varargs macros pack
  every argument as 32 bits, so ALWAYS write `%ld`, `%lx`, `%lc` (and `%lu`, V37+ exec). Plain
  `%d` prints the upper word and shifts every later argument.
- With GCC 15 (Bartman) a pointer argument without a cast is a compile error
  (`-Wint-conversion`): write `(LONG)str`.
- No floating point formats.

**See also:** [VPrintf](#vprintf), [VFWritef](#vfwritef), [FPutC](#fputc), exec.library RawDoFmt

## VPrintf
`LONG VPrintf(CONST_STRPTR format, CONST APTR argarray)` — LVO -954 (-$3BA)
Registers: format=D1, argarray=D2; result in D0

Format values with RawDoFmt codes and write the text to the default output, buffered.

- **format** — exec RawDoFmt format string.
- **argarray** — pointer to the packed argument values.
- **Result** — number of bytes written, or -1 on error (reason in `IoErr()`).

The varargs form is `Printf(format, ...)`.

Since V36.

### Example
```c
LONG frames = 50, secs = 3;
Printf("Rendered %ld frames in %ld s (%s)\n", frames, secs, (LONG)"PAL");
```

```asm
        move.l  DOSBase,a6
        lea     fmt(pc),a0
        move.l  a0,d1
        lea     args(pc),a0             ; array of LONGs
        move.l  a0,d2
        jsr     _LVOVPrintf(a6)
        ...
fmt:    dc.b    "Score: %ld",10,0
        even
args:   dc.l    12345
```

### Gotchas
- Always use `%ld`/`%lx`/`%lu`: without `l` RawDoFmt reads a 16-bit WORD and every following
  argument is misaligned.
- Cast pointers to `(LONG)` in `Printf` arguments (GCC 15 rejects the implicit conversion).
- Output goes to `Output()`; nothing appears if the process has none (Workbench start).
- The text sits in the buffer until a newline (console) or Flush/Close; flush before a `Write()`
  to the same handle.

**See also:** [VFPrintf](#vfprintf), [VFWritef](#vfwritef), [PutStr](#putstr), [FPutC](#fputc),
exec.library RawDoFmt

## VFWritef
`VOID VFWritef(BPTR fh, CONST_STRPTR format, CONST LONG *argarray)` — LVO -348 (-$15C)
Registers: fh=D1, format=D2, argarray=D3; no result

Write BCPL-style formatted text to a file handle, buffered (legacy; prefer VFPrintf).

- **fh** — file handle.
- **format** — BCPL format string. Codes: `%S` string (C string), `%Tx` left-justified string in a
  field at least x wide, `%C` character, `%Ox` octal, `%Xx` hex, `%Ix` decimal, each at most x
  characters wide, `%N` decimal of any length, `%Ux` unsigned, `%$` skip an argument. The width x
  is a single character (the autodoc calls it base 36 but also "character value - '0'"; digits
  `0`-`9` are unambiguous).
- **argarray** — pointer to an array of LONG arguments, one per code.
- **Result** — none usable (prototype is VOID).

The varargs form is `FWritef(fh, format, ...)`; dos/stdio.h defines `VWritef(format, argv)` for
`Output()`.

Since V36.

### Gotchas
- The V36 autodoc promised a byte count; as of V37 no valid value is returned, which is why the
  prototype is VOID.

**See also:** [VFPrintf](#vfprintf), [FPutC](#fputc)

## Flush
`LONG Flush(BPTR fh)` — LVO -360 (-$168)
Registers: fh=D1; result in D0

Write out pending buffered output, or discard read-ahead and resync the file position.

- **fh** — file handle.
- **Result** — non-zero for success. Before V37 the value was random; V37 always returns success.

Since V36.

### Example
```c
Printf("Progress: ");
Flush(Output());                      /* no newline yet: force it onto the console */

FPuts(fh, "header\n");
Flush(fh);                            /* switch from buffered to unbuffered */
Write(fh, bigblock, blocksize);
```

### Gotchas
- Call it between buffered calls and `Read`/`Write`/`Seek` on the same handle, in either
  direction. For an input handle it drops the buffer and seeks back to the logical position.
- V36/V37 did not flush handles that never had buffered I/O (e.g. redirected input, input of a
  process started with `NP_Arguments`, or a fresh handle given to `SelectInput()` before
  `RunCommand()`). Workaround: `FGetC(fh)`, `UnGetC(fh,-1)`, then `Flush(fh)`. Fixed in V39.
- `Close()` flushes for you.

**See also:** [FPutC](#fputc), [FGetC](#fgetc), [UnGetC](#ungetc), [Seek](files.md#seek),
[Close](files.md#close), [CreateNewProc](processes.md#createnewproc),
[SelectInput](files.md#selectinput), [RunCommand](processes.md#runcommand)

## SetVBuf
`LONG SetVBuf(BPTR fh, STRPTR buff, LONG type, LONG size)` — LVO -366 (-$16E)
Registers: fh=D1, buff=D2, type=D3, size=D4; result in D0

Change the buffering mode and/or buffer size of a file handle.

- **fh** — file handle.
- **buff** — your own buffer (longword aligned, at least max(size,208) bytes), or NULL to let dos
  allocate one of about `size` bytes.
- **type** — `BUF_LINE` (0, flush at newline), `BUF_FULL` (1, flush only when full), `BUF_NONE`
  (2, unbuffered). From dos/stdio.h.
- **size** — buffer size in bytes (below 208 is rounded up to 208), or -1 to change only the mode.
- **Result** — 0 on SUCCESS, non-zero on failure (inverted).

Since V39.

### Gotchas
- Only functional after V39: in V36-V39 it did nothing and returned 0. Do not assume it worked on
  those versions.
- A buffer you supply is never freed by dos, not when replaced and not on Close -- free it
  yourself after Close, and only if SetVBuf returned 0.
- Fails if something replaced the buffer without SetVBuf (RunCommand does this).
- Has no effect on the size of handles not created by AllocDosObject().

**See also:** [FPutC](#fputc), [FGetC](#fgetc), [UnGetC](#ungetc), [Flush](#flush), [FRead](#fread),
[FWrite](#fwrite), [FGets](#fgets), [FPuts](#fputs), [AllocDosObject](objects.md#allocdosobject)
