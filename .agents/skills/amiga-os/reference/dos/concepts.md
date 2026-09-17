# dos.library: concepts

AmigaDOS was originally written in BCPL and still shows it: BCPL pointers and strings, a
secondary error slot per process, and message "packets" to handler processes. Read this
page before writing any DOS code; the function entries assume it.

## BPTR and BSTR

A **BPTR** is a longword address divided by 4 (`typedef long BPTR`, `dos/dos.h`). File handles,
locks, seglists, `pr_CurrentDir`, `dol_Next` and most fields in DOS structures are BPTRs. 0
is the null BPTR. Anything a BPTR points to must be longword aligned, because the low two
bits are lost.

A **BSTR** is a BPTR to a BCPL string: a length byte followed by that many characters, at most
255, with no guaranteed NUL terminator (`s[0]=3, s[1]='S', s[2]='Y', s[3]='S'`). Device, volume
and assign names in the DosList (`dol_Name`) and the name fields of `struct CommandLineInterface`
are BSTRs.

`dos/dos.h` supplies the conversions:

```c
#define BADDR(x)   ((APTR)((ULONG)(x) << 2))    /* BPTR -> C pointer */
#define MKBADDR(x) (((LONG)(x)) >> 2)            /* C pointer -> BPTR */
```

```c
#include <proto/exec.h>
#include <dos/dos.h>
#include <exec/memory.h>

/* Read a BSTR into a C string (always NUL-terminated, truncated to fit). */
void BStrToC(BSTR bs, char *out, LONG outsize)
{
    UBYTE *s = BADDR(bs);
    LONG len = s ? s[0] : 0;
    if (len > outsize - 1)
        len = outsize - 1;
    if (len > 0)
        CopyMem(s + 1, out, len);
    out[len] = 0;
}

/* Build a BSTR (e.g. for a packet argument). Free with FreeVec(BADDR(bs)). */
BSTR CToBStr(CONST_STRPTR str)
{
    LONG len = 0;
    while (str[len] && len < 255)
        len++;
    UBYTE *mem = AllocVec(len + 2, MEMF_ANY);    /* exec memory is longword aligned */
    if (!mem)
        return 0;
    mem[0] = len;
    CopyMem((APTR)str, mem + 1, len);
    mem[len + 1] = 0;                             /* harmless extra NUL */
    return MKBADDR(mem);
}
```

```asm
; BPTR in d0 -> address in a0
        lsl.l   #2,d0
        move.l  d0,a0

; longword-aligned address in a0 -> BPTR in d0
        move.l  a0,d0
        lsr.l   #2,d0

; BSTR (a BPTR) in d0 -> length in d1, first character at (a0)
        lsl.l   #2,d0
        move.l  d0,a0
        moveq   #0,d1
        move.b  (a0)+,d1

; static data that DOS will address through a BPTR must be aligned
        cnop    0,4
fib:    ds.b    fib_SIZEOF
```

Gotchas:
- Never do arithmetic on a BPTR as if it were an address, and never pass a C pointer where a
  BPTR is expected (or vice versa) -- the prototypes are both `LONG`-sized, the compiler will
  not catch it.
- `MKBADDR` of an odd or 2-mod-4 address silently loses the low bits; allocate with
  `AllocVec`/`AllocDosObject` (exec rounds blocks to `MEM_BLOCKSIZE`, 8 bytes) or `cnop 0,4`.
- `BADDR(0)` is 0: check the BPTR before dereferencing.

## Calling convention and IoErr

Library base in A6 (`DOSBase`), arguments in **D1, D2, D3, D4...** in prototype order, result
in D0. D0/D1/A0/A1 are scratch; the other registers are preserved. Unlike exec and graphics,
dos passes almost nothing in address registers, and D0 is not an argument except in the
exceptions below.

| Exception | Registers |
|---|---|
| `DoPkt` (and DoPkt0-4) | port D1, action D2, arg1-arg5 D3-D7; secondary result also in D1 |
| `CliInitNewcli`, `CliInitRun` | packet in A0 |
| `InternalLoadSeg` | fh D0, table A0, funcarray A1, stack A2 |
| `InternalUnLoadSeg` | seglist D1, freefunc A1 |
| `LoadSeg` | result in D0 and also D1 (overlay compatibility) |

After a failure, `IoErr()` returns the reason (`pr_Result2`); see
[the error table](errors.md#error-codes). Know which failure value each call uses:

| Return convention | Calls (examples) |
|---|---|
| 0 / NULL = failure | Open, Lock, DupLock, CreateDir, LoadSeg, AllocDosObject, ReadArgs, Examine, ExNext, NameFromLock, Rename, DeleteFile, SetProtection, Info, most BOOL calls |
| -1 = failure | Read, Write, Seek, SetFileSize, GetVar, StrToLong, ParsePattern, RunCommand, SystemTagList (shell not started) |
| -1 = EOF or error | FGetC, FPutC, VFPrintf, VPrintf, WriteChars |
| 0 = success | PutStr, FPuts (else -1), SetVBuf, MatchFirst/MatchNext (else error code), SystemTagList (else command's return code) |
| no failure value | Input, Output, CurrentDir, IoErr, Cli, GetProgramDir (0 is a valid result) |

- DOS "true" is `DOSTRUE` (-1), not 1: test results for non-zero, never `== TRUE`.
- IoErr is undefined after a success unless the entry says otherwise; read it before making
  another DOS call.
- In C with Bartman's inlines, `Printf`/`FPrintf` pack every vararg as a 32-bit ULONG: cast
  pointers to `(LONG)` and use `%ld`/`%lx`/`%lu` (RawDoFmt reads `%d` as 16 bits).

## Locks vs file handles

| | Lock | File handle |
|---|---|---|
| What | reference to a named object (file or directory) | open byte stream with a position and buffer |
| Type | BPTR to `struct FileLock` | BPTR to `struct FileHandle` |
| Get | [Lock](locks-and-directories.md#lock), [DupLock](locks-and-directories.md#duplock), [CreateDir](locks-and-directories.md#createdir), [ParentDir](locks-and-directories.md#parentdir), [DupLockFromFH](files.md#duplockfromfh), [ParentOfFH](files.md#parentoffh) | [Open](files.md#open), [OpenFromLock](files.md#openfromlock) |
| Release | [UnLock](locks-and-directories.md#unlock) (0 is harmless) | [Close](files.md#close) |
| Modes | `ACCESS_READ`/`SHARED_LOCK` (-2), `ACCESS_WRITE`/`EXCLUSIVE_LOCK` (-1) | `MODE_OLDFILE` 1005, `MODE_NEWFILE` 1006 (exclusive), `MODE_READWRITE` 1004 (shared) |
| Used for | CurrentDir, Examine/ExNext/ExAll, Info, NameFromLock, assigns, SameLock | Read/Write/Seek, buffered I/O, ExamineFH, NameFromFH, record locks |

- Release every lock and handle you obtained exactly once; never release ones you were given
  (`Input()`, `Output()`, the lock returned by `CurrentDir()` at startup, `GetProgramDir()`).
- Copy a lock only with `DupLock` (shared locks only); copying the BPTR value is not a copy.
- An exclusive lock (including one held by a `MODE_NEWFILE` handle) blocks every other Lock or
  Open of that object until released.
- Lock 0 stands for the root of the boot filesystem (CurrentDir/ParentDir autodocs).
- `OpenFromLock` consumes the lock on success; `AssignLock`/`AssignAdd` consume it on success.

## Processes vs tasks

`struct Process` (`dos/dosextens.h`) is a `struct Task` followed by `pr_MsgPort` and the DOS
fields: `pr_Result2` (IoErr), `pr_CurrentDir`, `pr_CIS`/`pr_COS`/`pr_CES` (streams),
`pr_ConsoleTask`, `pr_FileSystemTask`, `pr_CLI`, `pr_WindowPtr`, `pr_HomeDir` (PROGDIR:),
`pr_LocalVars`. DOS calls send packets and wait for the reply on `pr_MsgPort` and store errors
in `pr_Result2`, so **only a Process may call dos.library** in general. A plain exec Task
(AddTask/CreateTask) has none of these fields.

- Test: `FindTask(NULL)->tc_Node.ln_Type == NT_PROCESS` (13); a Task is `NT_TASK` (1).
- The autodocs name a few task-callable exceptions: `AllocDosObject` (V37
  types/tags), `CreateNewProc` (DOS I/O parts such as copying the current dir are skipped),
  `DoPkt` (V37+), `SendPkt`. From a Task, the usual way to do file I/O is to start a Process
  with [CreateNewProc](processes.md#createnewproc).
- Ports returned by `CreateProc`/`DeviceProc` are `pr_MsgPort`s; the Process is at
  `port - sizeof(struct Task)` (dosextens.h comment).
- Never call DOS from interrupt code, input handlers or anything running inside `Disable()`.
  A DOS call waits for its reply, and a `Wait()` breaks `Forbid()` (exec Forbid autodoc), so
  DOS I/O inside Forbid silently lets other tasks run.
- Bare-metal games/demos: load every file BEFORE taking over the machine (killing the system
  copper list, interrupts and multitasking), or restore the OS around disk access. DOS needs
  multitasking, interrupts and the disk handlers running.
- Start-up from Workbench: the program is a Process but not a CLI (`Cli()` returns NULL) and
  normally has no input/output streams or console window (Execute autodoc; stream details
  unverified).

## Standard input and output

- `Input()`/`Output()` return the process's current streams (`pr_CIS`/`pr_COS`): the Shell
  window, or the files given with `<`/`>` redirection. Never `Close()` them.
- They can be 0 -- notably for Workbench-started programs, and for processes created with
  no streams -- so test before use or open your own `CON:` window.
- `SelectInput()`/`SelectOutput()` swap them and return the old value; restore it before exit.
- Buffered calls (`PutStr`, `Printf`, `FPuts`, `FGets`, ...) keep a buffer inside the handle.
  Do not mix them with `Read`/`Write` on the same handle without `Flush()`.
- `dos/stdio.h` macros wrap the buffered calls on the default streams: `ReadChar()`,
  `WriteChar(c)`, `UnReadChar(c)`, `ReadChars(buf,n)`, `ReadLn(buf,len)`, `WriteStr(s)`,
  `VWritef(fmt,argv)`; `ENDSTREAMCH` (-1) is EOF.
- `pr_CES` (error stream, V36 field) has no accessor function in this dos.library; when it is
  0, use `pr_COS`.
- CLI return code: return `RETURN_OK` (0), `RETURN_WARN` (5), `RETURN_ERROR` (10) or
  `RETURN_FAIL` (20) from `main()` (D0 in asm); set `SetIoErr()` for a meaningful `Why`.

## Console vs files

- Names you can `Open`: files and paths; `NIL:` (discards writes; reads give EOF); `CON:` and
  `RAW:` followed by window parameters (`CON:x/y/width/height/title`, unverified syntax
  details); `CONSOLE:` for the process's current console (`"*"` means the same but is obsolete
  since V36).
- `IsInteractive(fh)` is true for console-type handles; use it to decide whether to prompt or
  to show progress.
- A CON: handle is line-edited ("cooked"): Read returns after Return. `SetMode(fh, 1)`
  switches that CON: handle to RAW: behaviour (single keys), `SetMode(fh, 0)` back.
  `WaitForChar(fh, microseconds)` tests for pending input without blocking forever.
- Buffered output on an interactive handle flushes at newline, carriage return or NUL
  (FPutC autodoc); on a file it flushes when the buffer fills or at `Close`/`Flush`.
- Consoles do not support `Seek`, `SetFileSize`, record locks or `ExamineFH` like files do;
  check return values rather than assuming (unverified per handler).

## Safe file load

Load a whole file into memory with every failure path handled. `MEMF_CHIP` is needed for
anything the custom chips read (samples, bitplanes, copper lists); otherwise pass `MEMF_ANY`.

```c
#include <proto/exec.h>
#include <proto/dos.h>
#include <exec/memory.h>
#include <dos/dos.h>

/* Returns an AllocVec() buffer (FreeVec it) and sets *sizeOut, or returns NULL with the
   reason in IoErr(). Call from a Process with the OS running. */
APTR LoadFile(CONST_STRPTR name, ULONG memFlags, LONG *sizeOut)
{
    APTR buf = NULL;
    LONG err = 0, size = -1;
    BPTR fh = Open(name, MODE_OLDFILE);
    if (!fh)
        return NULL;                                  /* IoErr() already set */

    if (Seek(fh, 0, OFFSET_END) != -1)
        size = Seek(fh, 0, OFFSET_BEGINNING);         /* previous position = length */

    if (size == -1) {
        err = IoErr();
    } else if (!(buf = AllocVec(size > 0 ? size : 1, memFlags))) {
        err = ERROR_NO_FREE_STORE;
    } else {
        LONG done = 0;
        while (done < size) {
            LONG n = Read(fh, (UBYTE *)buf + done, size - done);
            if (n <= 0) {                             /* -1 = error, 0 = file shrank */
                err = (n < 0) ? IoErr() : ERROR_SEEK_ERROR;
                break;
            }
            done += n;
        }
        if (err) {
            FreeVec(buf);
            buf = NULL;
        }
    }

    Close(fh);                                        /* read-only: result not critical */
    if (err)
        SetIoErr(err);                                /* Close may have changed IoErr */
    else
        *sizeOut = size;
    return buf;
}

/* usage */
BOOL LoadTune(void)
{
    LONG len;
    APTR tune = LoadFile("PROGDIR:data/tune.mod", MEMF_CHIP, &len);
    if (!tune) {
        PrintFault(IoErr(), "tune.mod");
        return FALSE;
    }
    /* ... play it, then FreeVec(tune) ... */
    return TRUE;
}
```

Notes:
- Seek returns the position BEFORE the move, hence the two-call length idiom. The V36/V37
  ROM filesystem returns the current position instead of -1 on error (IoErr is 0 on
  success), so on 2.x a failure shows up as a wrong size; `ExamineFH()` (`fib_Size`) is an
  alternative.
- Test Seek against exactly -1: the V43+ FFS release notes allow files up to 4 GB - 2 bytes,
  so positions above 2 GB look negative as a LONG.
- `Read` may return fewer bytes than asked; always loop.
- `PROGDIR:` is the directory the program was started from (see
  [GetProgramDir](processes.md#getprogramdir)); prefer it to a fixed volume name.
- For big files, loading in chunks with a progress display is kinder than one Read.
- In asm the same sequence is Open (D1 name, D2 mode) -> Seek twice -> AllocVec (exec) -> Read
  (D1 fh, D2 buffer, D3 length) -> Close (D1 fh); keep the handle in a non-scratch register
  such as D4 across calls. See the [Open](files.md#open) asm example.
