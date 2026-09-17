# dos.library: files

A file handle is a `BPTR` (BCPL pointer, see [BPTR and BSTR](concepts.md#bptr-and-bstr)) to a
`struct FileHandle`; test it for 0, never dereference it. `Read`/`Write`/`Seek` are unbuffered:
each call is a packet round-trip to the handler, so use big blocks or the
[buffered calls](buffered-io.md) for small pieces -- and `Flush` before mixing the two on one
handle. Close only what you opened: `Input()`/`Output()` handles belong to your parent. On any
failure the reason is in [IoErr](errors.md#ioerr).

## Open
`BPTR Open(CONST_STRPTR name, LONG accessMode)` — LVO -30 (-$1E)
Registers: name=D1, accessMode=D2; result in D0

Open a file, device or console window and return a file handle.

- **name** — path (`"work:data/level1.bin"`, relative to the current dir, `"PROGDIR:gfx.raw"`),
  a plain device (`"NIL:"` swallows output, returns EOF on read), a console window
  (`"CON:0/0/640/200/Title"`, `"RAW:..."` for unprocessed keys), or `"CONSOLE:"` for the process's
  current console window. `"*"` means the same but is obsolete since V36.
- **accessMode** — `MODE_OLDFILE` (1005): existing file, read/write, positioned at start, fails
  if missing. `MODE_NEWFILE` (1006): create or truncate, exclusive lock. `MODE_READWRITE` (1004):
  existing file with a shared lock, created if missing. Values from dos/dos.h.
- **Result** — file handle BPTR, or 0 on failure with the reason in `IoErr()` (e.g.
  `ERROR_OBJECT_NOT_FOUND` 205, `ERROR_OBJECT_IN_USE` 202, `ERROR_DISK_WRITE_PROTECTED` 214).

### Example
```c
BPTR fh = Open("ram:score.dat", MODE_NEWFILE);
if (!fh) {
    PrintFault(IoErr(), "score.dat");     /* "score.dat: <reason>" to Output() */
    return RETURN_FAIL;
}
if (Write(fh, &score, sizeof(score)) != sizeof(score))
    PrintFault(IoErr(), "write");
if (!Close(fh))
    PrintFault(IoErr(), "close");
```

```asm
        include "exec/types.i"
        include "dos/dos.i"
        include "lvo/dos_lib.i"

; out: d0 = bytes read (0 = empty file), or -1 on error
LoadBlock:
        movem.l d2-d5/a6,-(sp)
        move.l  DOSBase,a6
        move.l  #fname,d1
        move.l  #MODE_OLDFILE,d2
        jsr     _LVOOpen(a6)
        move.l  d0,d4                   ; d4 = file handle (BPTR)
        beq.s   .fail
        move.l  d4,d1
        move.l  #buffer,d2
        move.l  #BUFSIZE,d3
        jsr     _LVORead(a6)
        move.l  d0,d5                   ; -1 = error, else byte count
        move.l  d4,d1
        jsr     _LVOClose(a6)
        move.l  d5,d0
        bra.s   .out
.fail:  moveq   #-1,d0
.out:   movem.l (sp)+,d2-d5/a6
        rts

fname:  dc.b    "PROGDIR:level.bin",0
```

### Gotchas
- The result is a BPTR, not a C pointer: `BADDR(fh)` gives the `struct FileHandle *`. Never pass
  it to C library `fclose()` or similar.
- Only a Process may call Open (it needs `pr_MsgPort`, current dir and IoErr slot); a plain exec
  Task crashes or fails. See [Processes vs tasks](concepts.md#processes-vs-tasks).
- `MODE_NEWFILE` destroys the old contents immediately, before you write anything.
- A missing disk/volume puts up a "Please insert volume" requester unless `pr_WindowPtr` is -1.
- `CONSOLE:` and `"*"` only work if the process has a console (`pr_ConsoleTask`); a program started
  from Workbench normally has none.

**See also:** [Close](#close), [Read](#read), [Write](#write), [OpenFromLock](#openfromlock),
[ChangeMode](#changemode), [NameFromFH](#namefromfh), [ParentOfFH](#parentoffh),
[ExamineFH](#examinefh), [Lock](locks-and-directories.md#lock), [IoErr](errors.md#ioerr)

## Close
`LONG Close(BPTR file)` — LVO -36 (-$24)
Registers: file=D1; result in D0

Close a file handle, flushing buffered output, and free it.

- **file** — a handle you own (from `Open`, `OpenFromLock`, ...).
- **Result** — non-zero on success; 0 if the final flush/write failed (e.g. disk full). The handle
  is freed either way. The return value exists only since V36 (random before).

### Example
```c
if (!Close(fh))                 /* a failing Close means the data may not be on disk */
    PrintFault(IoErr(), "save");
fh = 0;                         /* handle is gone even on failure */
```

### Gotchas
- Close each handle exactly once. Never Close `Input()` or `Output()` or any handle you inherited.
- Check the result when writing: buffered data is written at Close time, so "disk full" can
  surface only here.
- Do not pass 0; unlike UnLock(0), Close(0) is not documented as harmless.

**See also:** [Open](#open), [OpenFromLock](#openfromlock), [Flush](buffered-io.md#flush)

## Read
`LONG Read(BPTR file, APTR buffer, LONG length)` — LVO -42 (-$2A)
Registers: file=D1, buffer=D2, length=D3; result in D0

Read up to length bytes from a file into a buffer, unbuffered.

- **file** — file handle.
- **buffer** — destination, at least `length` bytes. Any memory type.
- **length** — bytes wanted.
- **Result** — bytes actually read (> 0), 0 at end of file, -1 on error (`IoErr()` has the code).
  Normally fills the buffer if enough data remains; consoles return one line at a time.

### Example
```c
LONG n;
UBYTE buf[512];
while ((n = Read(fh, buf, sizeof(buf))) > 0)
    process(buf, n);
if (n < 0)
    PrintFault(IoErr(), "read");
```

### Gotchas
- A short count is not an error; loop until 0 (EOF) or -1.
- Do not interleave with `FGetC`/`FGets`/`FRead` on the same handle without `Flush()` -- the
  buffered layer may already hold bytes ahead of the handler's position.
- From a console (CON:), Read returns when the user presses Return, not when the buffer is full.

**See also:** [Write](#write), [Seek](#seek), [Open](#open), [FRead](buffered-io.md#fread),
[FGetC](buffered-io.md#fgetc)

## Write
`LONG Write(BPTR file, CONST APTR buffer, LONG length)` — LVO -48 (-$30)
Registers: file=D1, buffer=D2, length=D3; result in D0

Write length bytes from a buffer to a file, unbuffered.

- **file** — file handle.
- **buffer** — source data.
- **length** — bytes to write.
- **Result** — bytes written, or -1 on error (`IoErr()` has the code, e.g. `ERROR_DISK_FULL` 221).

### Example
```asm
        move.l  DOSBase,a6
        jsr     _LVOOutput(a6)          ; d0 = stdout handle (may be 0)
        move.l  d0,d1
        beq.s   .noout
        move.l  #msg,d2
        move.l  #msg_len,d3
        jsr     _LVOWrite(a6)           ; d0 = count or -1
.noout:
        ...
msg:    dc.b    "Loading...",10
msg_len equ     *-msg
```

### Gotchas
- Compare the result with `length`; anything else (including a short positive count) means the
  data did not all go out.
- Flush pending buffered output (`FPuts`, `Printf`, ...) before calling Write on the same handle,
  or the text appears out of order.

**See also:** [Read](#read), [Seek](#seek), [Open](#open), [Close](#close),
[FWrite](buffered-io.md#fwrite), [FPutC](buffered-io.md#fputc)

## Seek
`LONG Seek(BPTR file, LONG position, LONG offset)` — LVO -66 (-$42)
Registers: file=D1, position=D2, offset=D3; result in D0

Move the read/write position of a file and return the previous position.

- **file** — file handle.
- **position** — signed byte offset relative to `offset`.
- **offset** — mode: `OFFSET_BEGINNING` (-1), `OFFSET_CURRENT` (0) or `OFFSET_END` (1).
- **Result** — the position BEFORE this seek, or -1 on error (`IoErr()` has the code). Seeking 0
  from `OFFSET_CURRENT` therefore returns the current position.

### Example
```c
/* File length: go to the end, then back to the start; the second call returns the old
   position, i.e. the size. */
LONG FileSize(BPTR fh)
{
    if (Seek(fh, 0, OFFSET_END) == -1)
        return -1;
    return Seek(fh, 0, OFFSET_BEGINNING);
}
```

### Gotchas
- You cannot seek beyond the end of a file (use [SetFileSize](#setfilesize) to extend).
- V36/V37 ROM filesystem and V36/V37 `L:FastFileSystem` return the current position instead of -1
  on failure, but set `IoErr()` to 0 on success and to the error on failure. For 2.x-safe code
  also check `IoErr()` after `SetIoErr(0)`. Fixed in the V39 filesystem.
- Consoles and many handlers (NIL:, PIPE:, CON:) cannot seek.
- Compare with exactly -1, not `< 0`: the V43+ FFS release notes allow files up to 4 GB - 2
  bytes, so large positions look negative as a LONG.
- Flush the handle first if buffered calls were used on it.

**See also:** [Read](#read), [Write](#write), [SetFileSize](#setfilesize),
[ExamineFH](#examinefh), [Flush](buffered-io.md#flush)

## SetFileSize
`LONG SetFileSize(BPTR fh, LONG pos, LONG mode)` — LVO -456 (-$1C8)
Registers: fh=D1, pos=D2, mode=D3; result in D0

Truncate or extend an open file to a new size.

- **fh** — file handle (opened with write access).
- **pos** — offset of the new end of file, relative to `mode`.
- **mode** — `OFFSET_BEGINNING` (-1), `OFFSET_CURRENT` (0) or `OFFSET_END` (1).
- **Result** — the new end-of-file position, or -1 on error. It can differ from what you asked
  for if other handles on the file would otherwise point past the end.

Since V36.

### Gotchas
- Not all handlers support it; always check for -1.
- Contents of an extended area are undefined -- write them yourself.
- The seek position afterwards differs between handlers (RAM: moves to the new end; the ROM
  filesystem only moves it if it would lie past the new end). Seek explicitly after the call.

**See also:** [Seek](#seek)

## Input
`BPTR Input(VOID)` — LVO -54 (-$36)
Registers: none; result in D0

Return the process's current default input file handle.

- **Result** — file handle BPTR (`pr_CIS`), or 0 if the process has none.

### Example
```c
BPTR in  = Input();
BPTR out = Output();
if (out)
    Write(out, "Name? ", 6);
if (in)
    len = Read(in, name, sizeof(name) - 1);
```

### Gotchas
- NEVER Close the handle returned by Input().
- A program started from Workbench normally has no CLI streams: check for 0 before using it.
- The value changes if someone calls [SelectInput](#selectinput).

**See also:** [Output](#output), [SelectInput](#selectinput),
[Standard input and output](concepts.md#standard-input-and-output)

## Output
`BPTR Output(VOID)` — LVO -60 (-$3C)
Registers: none; result in D0

Return the process's current default output file handle.

- **Result** — file handle BPTR (`pr_COS`), or 0 if the process has none.

### Example
```c
static char msg[] = "Done.\n";
BPTR out = Output();
if (out)
    Write(out, msg, sizeof(msg) - 1);
```

### Gotchas
- NEVER Close the handle returned by Output().
- Workbench-started programs normally get 0; `PutStr`/`Printf` then have nowhere to write. Open a
  `CON:` window yourself if you need text output.
- `PutStr`, `VPrintf`, `WriteChars` and `PrintFault` write to this handle (buffered).

**See also:** [Input](#input), [SelectOutput](#selectoutput), [PutStr](buffered-io.md#putstr),
[VPrintf](buffered-io.md#vprintf)

## SelectInput
`BPTR SelectInput(BPTR fh)` — LVO -294 (-$126)
Registers: fh=D1; result in D0

Make a file handle the process's default input and return the previous one.

- **fh** — new default input handle.
- **Result** — the previous default input handle.

Since V36.

### Gotchas
- Restore the old handle before your program exits; close the one you selected yourself (not the
  old one you got back).

**See also:** [Input](#input), [SelectOutput](#selectoutput), [Output](#output)

## SelectOutput
`BPTR SelectOutput(BPTR fh)` — LVO -300 (-$12C)
Registers: fh=D1; result in D0

Make a file handle the process's default output and return the previous one.

- **fh** — new default output handle.
- **Result** — the previous default output handle.

Since V36.

### Example
```c
BPTR log = Open("ram:log.txt", MODE_NEWFILE);
if (log) {
    BPTR old = SelectOutput(log);
    Printf("value = %ld\n", value);    /* goes to ram:log.txt */
    SelectOutput(old);                 /* restore BEFORE closing */
    Close(log);                        /* Close flushes the Printf buffer */
}
```

### Gotchas
- Restore the previous handle before exit and before closing yours.

**See also:** [Output](#output), [SelectInput](#selectinput), [Input](#input)

## OpenFromLock
`BPTR OpenFromLock(BPTR lock)` — LVO -378 (-$17A)
Registers: lock=D1; result in D0

Turn a lock into an open file handle on the same object.

- **lock** — lock on the file to open.
- **Result** — file handle, or 0 on failure. On success the lock is consumed: do not UnLock or use
  it again. On failure the lock is still yours. A shared lock behaves like `MODE_OLDFILE`, an
  exclusive lock like `MODE_NEWFILE`.

Since V36.

### Gotchas
- Old V36 autodocs and prototypes showed a second "mode" argument; there is none.

**See also:** [Open](#open), [Close](#close), [Lock](locks-and-directories.md#lock),
[UnLock](locks-and-directories.md#unlock)

## DupLockFromFH
`BPTR DupLockFromFH(BPTR fh)` — LVO -372 (-$174)
Registers: fh=D1; result in D0

Get a new lock on the object behind an open file handle.

- **fh** — open file handle.
- **Result** — lock (UnLock it when done), or 0 on failure. Only works on files opened in a
  non-exclusive mode (not `MODE_NEWFILE`); the handler may refuse for other reasons.

Since V36.

**See also:** [DupLock](locks-and-directories.md#duplock), [Lock](locks-and-directories.md#lock),
[UnLock](locks-and-directories.md#unlock), [ParentOfFH](#parentoffh)

## ExamineFH
`BOOL ExamineFH(BPTR fh, struct FileInfoBlock *fib)` — LVO -390 (-$186)
Registers: fh=D1, fib=D2; result in D0

Fill a FileInfoBlock with information about an open file.

- **fh** — open file handle.
- **fib** — `struct FileInfoBlock`, longword aligned; allocate it with
  `AllocDosObject(DOS_FIB, NULL)`.
- **Result** — non-zero on success, 0 on failure (`IoErr()`).

Since V36.

### Example
```c
struct FileInfoBlock *fib = AllocDosObject(DOS_FIB, NULL);
if (fib) {
    if (ExamineFH(fh, fib))
        Printf("%s: %ld bytes, prot $%08lx\n",
               (LONG)fib->fib_FileName, fib->fib_Size, fib->fib_Protection);
    FreeDosObject(DOS_FIB, fib);
}
```

### Gotchas
- `fib_Size` may not reflect writes made through this handle since it was opened; filesystems
  only try to keep it current.
- A FileInfoBlock on the stack is not guaranteed longword aligned; use AllocDosObject.
- Old filesystems lack the packet (fails with `ERROR_ACTION_NOT_KNOWN` 209).

**See also:** [Examine](locks-and-directories.md#examine), [ExNext](locks-and-directories.md#exnext),
[ExAll](locks-and-directories.md#exall), [Open](#open), [AllocDosObject](objects.md#allocdosobject)

## ParentOfFH
`BPTR ParentOfFH(BPTR fh)` — LVO -384 (-$180)
Registers: fh=D1; result in D0

Get a shared lock on the directory that contains an open file.

- **fh** — open file handle.
- **Result** — shared lock on the parent directory (UnLock it), or 0 on failure.

Since V36.

**See also:** [ParentDir](locks-and-directories.md#parentdir), [Lock](locks-and-directories.md#lock),
[UnLock](locks-and-directories.md#unlock), [DupLockFromFH](#duplockfromfh)

## NameFromFH
`LONG NameFromFH(BPTR fh, STRPTR buffer, LONG len)` — LVO -408 (-$198)
Registers: fh=D1, buffer=D2, len=D3; result in D0

Copy the full path name of an open file into a buffer.

- **fh** — open file handle.
- **buffer** — receives the null-terminated path (e.g. `"Work:data/x.bin"`).
- **len** — size of `buffer`; never more than `len` bytes are written.
- **Result** — non-zero on success, 0 on failure (`IoErr()`; `ERROR_LINE_TOO_LONG` 120 if the
  buffer is too small).

Since V36.

### Gotchas
- Filesystems that cannot ExamineFH make this fail (the autodoc names the code
  `ERROR_ACTION_NOT_SUPPORTED`, which does not exist in dos/dos.h; expect `ERROR_ACTION_NOT_KNOWN`
  209).
- May bring up a "Please insert volume" requester if the volume was removed.

**See also:** [NameFromLock](locks-and-directories.md#namefromlock), [ExamineFH](#examinefh)

## ChangeMode
`LONG ChangeMode(LONG type, BPTR fh, LONG newmode)` — LVO -450 (-$1C2)
Registers: type=D1, fh=D2, newmode=D3; result in D0

Ask the handler to change the access mode of an open lock or file handle.

- **type** — `CHANGE_LOCK` (0) if `fh` is a lock, `CHANGE_FH` (1) if it is a file handle.
- **fh** — the lock or file handle (the prototype names it fh for both).
- **newmode** — the mode wanted, e.g. `EXCLUSIVE_LOCK` (-1) to upgrade a `SHARED_LOCK` (-2).
  Which value a handler expects for `CHANGE_FH` is not stated in the autodoc (unverified: the
  same lock access values).
- **Result** — non-zero on success; the handler may refuse (e.g. others hold the object).

Since V36.

### Gotchas
- Passing a lock with `CHANGE_FH` or a handle with `CHANGE_LOCK` can crash the system.
- Broken in V36 (2.02 and earlier) and may crash there; works from V37.

**See also:** [Lock](locks-and-directories.md#lock), [Open](#open)

## DeleteFile
`LONG DeleteFile(CONST_STRPTR name)` — LVO -72 (-$48)
Registers: name=D1; result in D0

Delete a file or an empty directory.

- **name** — path of the object.
- **Result** — non-zero on success, 0 on failure. Typical `IoErr()` codes:
  `ERROR_OBJECT_NOT_FOUND` (205), `ERROR_OBJECT_IN_USE` (202, still open or locked),
  `ERROR_DELETE_PROTECTED` (222), `ERROR_DIRECTORY_NOT_EMPTY` (216),
  `ERROR_DISK_WRITE_PROTECTED` (214).

### Example
```c
if (!DeleteFile("t:mygame.tmp") && IoErr() != ERROR_OBJECT_NOT_FOUND)
    PrintFault(IoErr(), "delete");
```

### Gotchas
- Directories must be emptied first; there is no recursive delete.
- Close/UnLock your own handles and locks on the object first.
- No pattern matching: to delete `#?.tmp` iterate with [MatchFirst](paths-and-names.md#matchfirst).

**See also:** [Rename](#rename), [SetProtection](#setprotection)

## Rename
`LONG Rename(CONST_STRPTR oldName, CONST_STRPTR newName)` — LVO -78 (-$4E)
Registers: oldName=D1, newName=D2; result in D0

Rename a file or directory, optionally moving it to another directory on the same volume.

- **oldName** — current path.
- **newName** — new path (may name a different directory).
- **Result** — non-zero on success, 0 on failure. Fails if `newName` already exists
  (`ERROR_OBJECT_EXISTS` 203) or lies on another volume (`ERROR_RENAME_ACROSS_DEVICES` 215).

### Example
```c
DeleteFile("s:mygame.prefs.bak");              /* Rename will not overwrite */
if (!Rename("s:mygame.prefs", "s:mygame.prefs.bak") && IoErr() != ERROR_OBJECT_NOT_FOUND)
    PrintFault(IoErr(), "backup");
```

### Gotchas
- Cannot cross volumes: copy then DeleteFile instead.
- To rename a volume use Relabel, not Rename.

**See also:** [DeleteFile](#deletefile), [Relabel](dos-list.md#relabel)

## SetProtection
`LONG SetProtection(CONST_STRPTR name, LONG protect)` — LVO -186 (-$BA)
Registers: name=D1, protect=D2; result in D0

Set the protection bits of a file or directory.

- **name** — path of the object.
- **protect** — new 32-bit protection mask (replaces the old one; read it first with `Examine`
  to change single bits).
- **Result** — non-zero on success, 0 on failure.

Protection bits (dos/dos.h). The low four RWED bits are inverted: **0 = allowed, 1 = denied**.
The group/other bits are the opposite: **1 = allowed**. The filesystem does not enforce
group/other bits.

| Bit | Name (`FIBB_`/`FIBF_`) | FIBF value | Meaning |
|---|---|---|---|
| 15 | OTR_READ | $8000 | other: readable (1 = yes) |
| 14 | OTR_WRITE | $4000 | other: writable |
| 13 | OTR_EXECUTE | $2000 | other: executable |
| 12 | OTR_DELETE | $1000 | other: deletable |
| 11 | GRP_READ | $0800 | group: readable (1 = yes) |
| 10 | GRP_WRITE | $0400 | group: writable |
| 9 | GRP_EXECUTE | $0200 | group: executable |
| 8 | GRP_DELETE | $0100 | group: deletable |
| 6 | SCRIPT | $0040 | "s": file is an Execute script (1 = set) |
| 5 | PURE | $0020 | "p": re-entrant, may be made resident (1 = set) |
| 4 | ARCHIVE | $0010 | "a": set by backup tools, cleared by the FS on change |
| 3 | READ | $0008 | "r": 1 = read denied |
| 2 | WRITE | $0004 | "w": 1 = write denied |
| 1 | EXECUTE | $0002 | "e": 1 = not executable (Shell checks it) |
| 0 | DELETE | $0001 | "d": 1 = delete denied |

### Example
```c
/* make a save file read-only: deny write and delete, keep r and e allowed */
if (!SetProtection("s:mygame.save", FIBF_WRITE | FIBF_DELETE))
    PrintFault(IoErr(), "protect");

/* back to normal "----rwed" */
SetProtection("s:mygame.save", 0);
```

### Gotchas
- `SetProtection(name, 0)` means everything ALLOWED (rwed), not "no rights".
- Before V36 the ROM filesystem ignored R and W (FFS respected them).
- The Shell refuses to run a file whose E bit (`FIBF_EXECUTE`) is set.

**See also:** [SetComment](#setcomment), [Examine](locks-and-directories.md#examine),
[ExNext](locks-and-directories.md#exnext), [SetOwner](#setowner)

## SetComment
`LONG SetComment(CONST_STRPTR name, CONST_STRPTR comment)` — LVO -180 (-$B4)
Registers: name=D1, comment=D2; result in D0

Attach a comment string (file note) to a file or directory.

- **name** — path of the object.
- **comment** — null-terminated text; up to 80 characters on the ROM filesystem and RAM:,
  other filesystems vary or have no comments.
- **Result** — non-zero on success, 0 on failure (`ERROR_COMMENT_TOO_BIG` 220 if too long).

**See also:** [Examine](locks-and-directories.md#examine), [ExNext](locks-and-directories.md#exnext),
[SetProtection](#setprotection)

## SetFileDate
`LONG SetFileDate(CONST_STRPTR name, CONST struct DateStamp *date)` — LVO -396 (-$18C)
Registers: name=D1, date=D2; result in D0

Set the modification date stamp of a file or directory.

- **name** — path of the object.
- **date** — `struct DateStamp` (days since 1-Jan-1978, minutes, ticks) to store.
- **Result** — non-zero on success, 0 on failure.

Since V36.

### Gotchas
- OFS/FFS cannot set the date of a volume's root directory; other filesystems may refuse for
  some objects.

**See also:** [DateStamp](time.md#datestamp), [Examine](locks-and-directories.md#examine),
[ExNext](locks-and-directories.md#exnext), [ExAll](locks-and-directories.md#exall)

## SetOwner
`BOOL SetOwner(CONST_STRPTR name, LONG owner_info)` — LVO -996 (-$3E4)
Registers: name=D1, owner_info=D2; result in D0

Store owner user and group IDs on a file or directory (for network filesystems).

- **name** — path of the object.
- **owner_info** — user ID in bits 31-16, group ID in bits 15-0: `(uid << 16) | gid`.
- **Result** — non-zero on success, 0 on failure.

Since V39.

### Gotchas
- The entry point does not exist in V36; V37/V38 dos.library has it but always returns FALSE.
  Open dos.library V39+ before relying on it.
- Filesystems only store the values (read back as `fib_OwnerUID`/`fib_OwnerGID`), they do not
  enforce them.

**See also:** [SetProtection](#setprotection), [Examine](locks-and-directories.md#examine),
[ExNext](locks-and-directories.md#exnext), [ExAll](locks-and-directories.md#exall)

## IsInteractive
`LONG IsInteractive(BPTR file)` — LVO -216 (-$D8)
Registers: file=D1; result in D0

Tell whether a file handle is connected to a console (virtual terminal).

- **file** — file handle.
- **Result** — non-zero (TRUE) for a console such as CON:/RAW:, 0 for files and NIL:.

### Example
```c
if (Output() && IsInteractive(Output()))
    PutStr("Press Return to continue\n");     /* no prompts when redirected to a file */
```

**See also:** [WaitForChar](#waitforchar), [Input](#input), [Output](#output)

## WaitForChar
`LONG WaitForChar(BPTR file, LONG timeout)` — LVO -204 (-$CC)
Registers: file=D1, timeout=D2; result in D0

Wait up to a timeout for a character to become available on a console handle.

- **file** — console file handle (e.g. `Input()` in a Shell).
- **timeout** — maximum wait in MICROSECONDS (not ticks).
- **Result** — -1 (DOSTRUE) if a character can be read now (then `Read` it), 0 on timeout.

### Example
```c
/* poll the console for a key once per frame without blocking (RAW mode, see SetMode) */
if (WaitForChar(Input(), 0)) {
    UBYTE c;
    Read(Input(), &c, 1);
}
```

### Gotchas
- Only valid on interactive handles (see [IsInteractive](#isinteractive)).
- On 1.2/1.3 a timeout of 0 could upset timer and floppy operation (timer.device bug, fixed V36).
- In normal CON: mode input only arrives after Return; switch to RAW with [SetMode](#setmode) to
  see single keys.

**See also:** [Read](#read), [FGetC](buffered-io.md#fgetc), [SetMode](#setmode)

## SetMode
`LONG SetMode(BPTR fh, LONG mode)` — LVO -426 (-$1AA)
Registers: fh=D1, mode=D2; result in D0

Switch a console handler between cooked (CON:) and raw (RAW:) mode.

- **fh** — console file handle.
- **mode** — for CON:, 1 = raw mode (keys delivered immediately, no echo or line editing),
  0 = normal CON: mode. Sent as `ACTION_SCREEN_MODE` (994).
- **Result** — non-zero on success.

Since V36.

### Gotchas
- Always switch back to 0 before exit, or the user's Shell window stays raw.
- Non-console handlers reject it.

**See also:** [WaitForChar](#waitforchar), [IsInteractive](#isinteractive),
[action codes](packets.md#action-codes)
