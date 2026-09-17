# dos.library: errors

Most DOS calls signal failure through their return value (0/DOSFALSE, -1 or NULL -- check each
entry) and leave a reason code in the process field `pr_Result2`, which `IoErr()` returns.
Read `IoErr()` immediately after the failing call: the next DOS call may overwrite it, and its
value after a *successful* call is undefined unless the entry says otherwise. Turn codes into
text with `Fault()` (into a buffer) or `PrintFault()` (to `Output()`). CLI commands return a
`RETURN_*` code from `main()`/D0.

## Error codes

From `dos/dos.h` (C) / `dos/dos.i` (asm), plus 303-305 from `dos/dosasl.h` and the two
`ErrorReport()`-only codes from `dos/dosextens.h`. "Seen from" lists callers the autodocs name.

| Value | Name | Meaning / seen from |
|---|---|---|
| 103 | `ERROR_NO_FREE_STORE` | out of memory |
| 105 | `ERROR_TASK_TABLE_FULL` | no free CLI task slot |
| 114 | `ERROR_BAD_TEMPLATE` | malformed ReadArgs template |
| 115 | `ERROR_BAD_NUMBER` | bad /N number; GetVar size 0; ExAll type not supported |
| 116 | `ERROR_REQUIRED_ARG_MISSING` | a /A argument was not given |
| 117 | `ERROR_KEY_NEEDS_ARG` | keyword given without its value |
| 118 | `ERROR_TOO_MANY_ARGS` | more arguments than the template takes |
| 119 | `ERROR_UNMATCHED_QUOTES` | unbalanced `"` on the command line |
| 120 | `ERROR_LINE_TOO_LONG` | buffer too small (NameFromLock); too many /M items |
| 121 | `ERROR_FILE_NOT_OBJECT` | file is not an executable load file |
| 122 | `ERROR_INVALID_RESIDENT_LIBRARY` | bad resident library |
| 201 | `ERROR_NO_DEFAULT_DIR` | no current directory |
| 202 | `ERROR_OBJECT_IN_USE` | object locked by someone else (e.g. Format without Inhibit) |
| 203 | `ERROR_OBJECT_EXISTS` | an object of that name already exists |
| 204 | `ERROR_DIR_NOT_FOUND` | directory not found |
| 205 | `ERROR_OBJECT_NOT_FOUND` | object not found; GetVar undefined; GetDeviceProc multi-assign retry |
| 206 | `ERROR_BAD_STREAM_NAME` | invalid stream/window name |
| 207 | `ERROR_OBJECT_TOO_LARGE` | object too large |
| 209 | `ERROR_ACTION_NOT_KNOWN` | handler does not implement the packet |
| 210 | `ERROR_INVALID_COMPONENT_NAME` | illegal character or name part |
| 211 | `ERROR_INVALID_LOCK` | lock not valid |
| 212 | `ERROR_OBJECT_WRONG_TYPE` | file where dir expected or vice versa; Get*Name without a CLI |
| 213 | `ERROR_DISK_NOT_VALIDATED` | volume still validating |
| 214 | `ERROR_DISK_WRITE_PROTECTED` | disk write-protected |
| 215 | `ERROR_RENAME_ACROSS_DEVICES` | Rename to another volume |
| 216 | `ERROR_DIRECTORY_NOT_EMPTY` | DeleteFile on a non-empty directory |
| 217 | `ERROR_TOO_MANY_LEVELS` | nesting too deep (MatchPattern recursion limit) |
| 218 | `ERROR_DEVICE_NOT_MOUNTED` | device/volume not mounted |
| 219 | `ERROR_SEEK_ERROR` | invalid seek |
| 220 | `ERROR_COMMENT_TOO_BIG` | comment too long |
| 221 | `ERROR_DISK_FULL` | disk full |
| 222 | `ERROR_DELETE_PROTECTED` | `d` protection bit set |
| 223 | `ERROR_WRITE_PROTECTED` | `w` protection bit set |
| 224 | `ERROR_READ_PROTECTED` | `r` protection bit set |
| 225 | `ERROR_NOT_A_DOS_DISK` | not a DOS disk |
| 226 | `ERROR_NO_DISK` | no disk in drive |
| 232 | `ERROR_NO_MORE_ENTRIES` | normal end of ExNext/ExAll/MatchNext/GetDeviceProc |
| 233 | `ERROR_IS_SOFT_LINK` | filesystem hit a soft link (resolve with ReadLink) |
| 234 | `ERROR_OBJECT_LINKED` | object has hard links |
| 235 | `ERROR_BAD_HUNK` | bad hunk in load file |
| 236 | `ERROR_NOT_IMPLEMENTED` | function not implemented |
| 240 | `ERROR_RECORD_NOT_LOCKED` | record not locked |
| 241 | `ERROR_LOCK_COLLISION` | record lock collision |
| 242 | `ERROR_LOCK_TIMEOUT` | record lock timed out |
| 243 | `ERROR_UNLOCK_ERROR` | record unlock failed |
| 288 | `ABORT_BUSY` | ErrorReport only ("you MUST replace...") |
| 296 | `ABORT_DISK_ERROR` | ErrorReport only (read/write error) |
| 303 | `ERROR_BUFFER_OVERFLOW` | user or internal buffer overflow (pattern matching) |
| 304 | `ERROR_BREAK` | break signal received (MatchFirst/MatchNext `ap_BreakBits`) |
| 305 | `ERROR_NOT_EXECUTABLE` | file has the `e` bit cleared |

Meanings are paraphrased from the constant names and header comments; the exact wording the
system prints comes from `Fault()`.

Command return codes (`dos/dos.h`): `RETURN_OK` 0, `RETURN_WARN` 5, `RETURN_ERROR` 10,
`RETURN_FAIL` 20. Other constants: `DOSTRUE` -1, `DOSFALSE` 0, `FAULT_MAX` 82 (standard
maximum Fault() string length).

## IoErr
`LONG IoErr(VOID)` — LVO -132 (-$84)
Registers: none; result in D0

Return the secondary result (usually the error code) of the last DOS call.

- **Result** — `pr_Result2` of the calling process: an error code from the table above after a
  failure, or a documented secondary result (see Gotchas).

### Example
```c
BPTR fh = Open("DATA:level1.map", MODE_OLDFILE);
if (!fh) {
    LONG err = IoErr();              /* grab it before any other DOS call */
    PrintFault(err, "loader");       /* prints "loader: <message>" */
    return RETURN_FAIL;
}
```

```asm
        move.l  DOSBase,a6
        move.l  #fname,d1
        move.l  #MODE_OLDFILE,d2
        jsr     _LVOOpen(a6)
        move.l  d0,d4                   ; BPTR file handle
        bne.s   .opened
        jsr     _LVOIoErr(a6)           ; d0 = error code
        move.l  d0,d1
        move.l  #progname,d2
        jsr     _LVOPrintFault(a6)
```

### Gotchas
- The value is only defined after a failure (or where an entry documents it). Never test
  `IoErr()` alone to decide whether a call worked.
- Some calls use it for a second result: `AddBuffers` (buffer count), `DeviceProc` (assign
  lock), `GetVar` (full variable length), `DoPkt` (dp_Res2, also in D1), V36/V37 `Seek`
  (0 on success). `Fault`, `PrintFault` and `ErrorReport` set it to the code passed in.
- It lives in the Process structure; a plain exec Task has no `pr_Result2`.
- `FRead`/`FWrite` do not clear it first: `SetIoErr(0)` before the call if you need to tell
  short counts from errors.

**See also:** [SetIoErr](#setioerr), [Fault](#fault), [PrintFault](#printfault),
[calling convention](concepts.md#calling-convention-and-ioerr)

## SetIoErr
`LONG SetIoErr(LONG result)` — LVO -462 (-$1CE)
Registers: result=D1; result in D0

Set the value that the next IoErr() will return.

- **result** — new code for `pr_Result2`.
- **Result** — the previous code.

Since V36.

### Gotchas
- Useful before `FRead`/`FWrite`/`MatchPattern` to distinguish "nothing happened" from a
  real error, and in a CLI command before returning a failure so the shell keeps a meaningful
  code (`cli_Result2` holds the IoErr of the last command, `dos/dosextens.h`).

**See also:** [IoErr](#ioerr), [Fault](#fault), [PrintFault](#printfault)

## Fault
`BOOL Fault(LONG code, STRPTR header, STRPTR buffer, LONG len)` — LVO -468 (-$1D4)
Registers: code=D1, header=D2, buffer=D3, len=D4; result in D0

Build the text for a DOS error code, prefixed by a header, into a buffer.

- **code** — error code (usually from `IoErr()`).
- **header** — text placed before the message and followed by a colon; NULL for none.
- **buffer** — receives a NUL-terminated string.
- **len** — size of `buffer`. Messages are meant to fit 80 characters (+1); `FAULT_MAX` (82)
  plus your header length is a safe size.
- **Result** — number of characters stored (0 if `code` was 0). Unknown codes give an
  "Error code <n>" message.

Since V36.

### Example
```c
char msg[FAULT_MAX + 32];
BPTR lock = Lock(name, ACCESS_READ);
if (lock) {
    UnLock(lock);
} else {
    Fault(IoErr(), (STRPTR)name, msg, sizeof(msg));
    /* show msg in your own requester or window */
}
```

### Gotchas
- The NDK prototype declares `BOOL`, but the call has always returned the length; treat D0 as
  a LONG character count.
- Sets `IoErr()` to `code`.

**See also:** [PrintFault](#printfault), [IoErr](#ioerr), [SetIoErr](#setioerr)

## PrintFault
`BOOL PrintFault(LONG code, CONST_STRPTR header)` — LVO -474 (-$1DA)
Registers: code=D1, header=D2; result in D0

Print "header: message" for an error code to Output() using buffered I/O.

- **code** — error code.
- **header** — prefix text, or NULL.
- **Result** — non-zero on success.

Since V36.

### Example
```c
if (!DeleteFile(name)) {
    PrintFault(IoErr(), (STRPTR)name);
    rc = RETURN_WARN;
}
```

### Gotchas
- Writes to `Output()`; a program without an output stream (typically a Workbench start,
  unverified) prints nothing -- use `Fault()` and your own display.
- Buffered: mixing with unbuffered `Write(Output(), ...)` can reorder text; `Flush(Output())`
  first.
- Sets `IoErr()` to `code`.

**See also:** [Fault](#fault), [IoErr](#ioerr), [Output](files.md#output), [FPuts](buffered-io.md#fputs)

## ErrorReport
`LONG ErrorReport(LONG code, LONG type, ULONG arg1, struct MsgPort *device)` — LVO -480 (-$1E0)
Registers: code=D1, type=D2, arg1=D3, device=D4; result in D0

Put up the system Retry/Cancel requester for a disk-type error.

- **code** — one of `ERROR_DISK_NOT_VALIDATED`, `ERROR_DISK_WRITE_PROTECTED`,
  `ERROR_DISK_FULL`, `ERROR_DEVICE_NOT_MOUNTED`, `ERROR_NOT_A_DOS_DISK`, `ERROR_NO_DISK`,
  `ABORT_DISK_ERROR` (296), `ABORT_BUSY` (288). Other codes return DOSTRUE at once.
- **type** — `REPORT_STREAM` (0, arg1 = file handle BPTR), `REPORT_LOCK` (2, arg1 = lock
  BPTR), `REPORT_VOLUME` (3, arg1 = volume DosList C pointer), `REPORT_INSERT` (4, arg1 = volume
  name string, split at `':'`; with `ERROR_DEVICE_NOT_MOUNTED` gives "Please insert...").
  `REPORT_TASK` (1) is unused.
- **arg1** — depends on `type` (see above).
- **device** — handler MsgPort; only needed for `REPORT_LOCK` when `arg1` is 0.
- **Result** — FALSE (0) = user chose Retry; DOSTRUE = Cancel, requester failed, or
  `pr_WindowPtr` is -1. Opposite sense to intuition AutoRequest.

Since V36.

### Gotchas
- Sets `IoErr()` to `code`. Retries automatically on disk insertion for the relevant codes.
- The autodoc calls the file-handle type `REPORT_FH`; the includes only define
  `REPORT_STREAM` (0) -- use that name.
- To stop DOS from opening *any* such requester for your process (e.g. while a game owns the
  display) set `pr_WindowPtr` to `(APTR)-1`; calls then fail with the error instead. Restore the
  old value before exiting.

```c
struct Process *me = (struct Process *)FindTask(NULL);
APTR oldwin = me->pr_WindowPtr;
me->pr_WindowPtr = (APTR)-1;        /* no "insert volume" requesters */
/* ... DOS calls ... */
me->pr_WindowPtr = oldwin;
```

**See also:** [Fault](#fault), [IoErr](#ioerr)
