# dos.library: locks and directories

A lock (a `BPTR`) pins a file or directory without opening it. `ACCESS_READ` (shared) locks
can coexist; an `ACCESS_WRITE` (exclusive) lock keeps everyone else out. Every lock you get
from Lock, DupLock, CreateDir, ParentDir (and DupLockFromFH / ParentOfFH) must be UnLock()ed
exactly once; locks the system lends you (GetProgramDir, the startup current directory) must
not be. Lock value 0 stands for the root of the boot volume. Examine/ExNext fill a
FileInfoBlock that MUST be longword aligned -- allocate it with `AllocDosObject(DOS_FIB, NULL)`.
See [locks vs file handles](concepts.md#locks-vs-file-handles) and
[BPTR](concepts.md#bptr-and-bstr).

## Lock
`BPTR Lock(CONST_STRPTR name, LONG type)` — LVO -84 (-$54)
Registers: name=D1, type=D2; result in D0

Obtain a shared or exclusive filing-system lock on a named file or directory.

- **name** — path (absolute `Work:dir/file`, relative to the current directory, `PROGDIR:x`...).
- **type** — `ACCESS_READ` / `SHARED_LOCK` (-2) or `ACCESS_WRITE` / `EXCLUSIVE_LOCK` (-1).
  No other values.
- **Result** — lock BPTR, or 0 on failure; IoErr() then holds the reason
  (`ERROR_OBJECT_NOT_FOUND` 205, `ERROR_DIR_NOT_FOUND` 204, `ERROR_OBJECT_IN_USE` 202...).

### Example
```c
/* Does a file or directory exist? */
BOOL Exists(CONST_STRPTR name)
{
    BPTR lock = Lock(name, ACCESS_READ);
    if (!lock)
        return FALSE;           /* IoErr() says why */
    UnLock(lock);
    return TRUE;
}
```

```asm
        include "exec/types.i"
        include "dos/dos.i"
        include "lvo/dos_lib.i"

; size of S:Startup-Sequence -> d5 (-1 on failure)
        movem.l d2-d5/a6,-(sp)
        move.l  DOSBase,a6
        moveq   #-1,d5
        moveq   #DOS_FIB,d1
        moveq   #0,d2                   ; no tags
        jsr     _LVOAllocDosObject(a6)
        move.l  d0,d4                   ; d4 = FileInfoBlock (longword aligned)
        beq.s   .out
        move.l  #fname,d1
        moveq   #ACCESS_READ,d2
        jsr     _LVOLock(a6)
        move.l  d0,d3                   ; d3 = lock BPTR
        beq.s   .free
        move.l  d3,d1
        move.l  d4,d2
        jsr     _LVOExamine(a6)
        tst.l   d0
        beq.s   .unlock
        move.l  d4,a0
        move.l  fib_Size(a0),d5
.unlock move.l  d3,d1
        jsr     _LVOUnLock(a6)
.free   moveq   #DOS_FIB,d1
        move.l  d4,d2
        jsr     _LVOFreeDosObject(a6)
.out    movem.l (sp)+,d2-d5/a6
        rts
fname   dc.b    "S:Startup-Sequence",0
```

### Gotchas
- A 0 result is failure here, even though lock 0 means "boot volume root" to CurrentDir and
  ParentDir. Test the result before using it.
- Copying a BPTR does not copy the lock: use DupLock, and UnLock each copy once.
- An exclusive lock blocks every other Lock/Open on the object until released.
- Naming a volume that is not mounted opens a "please insert" requester; set the process
  `pr_WindowPtr` to -1 to fail silently instead.
- Do not read or rely on `struct FileLock` fields (`fl_Link`, `fl_Access`...).

**See also:** [UnLock](#unlock), [DupLock](#duplock), [ChangeMode](files.md#changemode), [NameFromLock](#namefromlock), [DupLockFromFH](files.md#duplockfromfh)

## UnLock
`VOID UnLock(BPTR lock)` — LVO -90 (-$5A)
Registers: lock=D1; no result

Release a lock obtained from Lock, DupLock, CreateDir or ParentDir.

- **lock** — lock BPTR to free; 0 is accepted and ignored.

### Gotchas
- Never UnLock a lock you do not own: GetProgramDir's lock, the startup current directory,
  the lock IoErr() returns after DeviceProc, a lock passed successfully to
  AssignLock/AssignAdd or OpenFromLock.
- The lock is invalid after the call; clear your variable.

**See also:** [Lock](#lock), [DupLock](#duplock), [ParentOfFH](files.md#parentoffh), [DupLockFromFH](files.md#duplockfromfh)

## DupLock
`BPTR DupLock(BPTR lock)` — LVO -96 (-$60)
Registers: lock=D1; result in D0

Create a second, independent shared lock on the same object.

- **lock** — a shared lock to duplicate.
- **Result** — new lock (UnLock it separately), or 0 on failure.

### Gotchas
- This is the only legal way to copy a lock. An exclusive lock cannot be duplicated.
- Typical use: hand a copy to a call that takes ownership (AssignLock, AssignAdd,
  `NP_CurrentDir`) while keeping your own.

**See also:** [Lock](#lock), [UnLock](#unlock), [DupLockFromFH](files.md#duplockfromfh), [ParentOfFH](files.md#parentoffh)

## SameLock
`LONG SameLock(BPTR lock1, BPTR lock2)` — LVO -420 (-$1A4)
Registers: lock1=D1, lock2=D2; result in D0

Compare two locks: same object, same volume, or different volumes.

- **lock1, lock2** — locks to compare.
- **Result** — `LOCK_SAME` (0), `LOCK_SAME_VOLUME` (1), `LOCK_DIFFERENT` (-1).
  `LOCK_SAME_HANDLER` is an obsolete alias of `LOCK_SAME_VOLUME`.

Since V36.

### Gotchas
- `LOCK_SAME` is 0: `if (SameLock(a, b))` means "NOT the same object". Compare with `==`
  against the named constants only (more values may be added).
- V36 returned `LOCK_SAME_VOLUME` for different volumes served by the same handler.

**See also:** [SameDevice](#samedevice), [Lock](#lock)

## SameDevice
`BOOL SameDevice(BPTR lock1, BPTR lock2)` — LVO -984 (-$3D8)
Registers: lock1=D1, lock2=D2; result in D0

Tell whether two locks live on partitions of the same physical device.

- **lock1, lock2** — locks to compare.
- **Result** — non-zero if dos can tell they share a device, 0 otherwise.

Since V37.

### Gotchas
- The entry exists in V36 but always returns 0. "Can't tell" also returns 0.

**See also:** [SameLock](#samelock)

## NameFromLock
`LONG NameFromLock(BPTR lock, STRPTR buffer, LONG len)` — LVO -402 (-$192)
Registers: lock=D1, buffer=D2, len=D3; result in D0

Build the full path (`Volume:dir/name`) of a locked object into a buffer.

- **lock** — lock on the object; 0 yields `"SYS:"`.
- **buffer** — receives a NUL-terminated path; never written past `len` bytes.
- **len** — buffer size in bytes.
- **Result** — non-zero on success; 0 on failure. A too-small buffer fails with IoErr()
  `ERROR_LINE_TOO_LONG` (120).

Since V36.

### Example
```c
UBYTE path[256];
BPTR dir = Lock("PROGDIR:", ACCESS_READ);

if (dir && NameFromLock(dir, path, sizeof(path)))
    Printf("Running from %s\n", (LONG)path);
else
    PrintFault(IoErr(), "NameFromLock");
UnLock(dir);                    /* UnLock(0) is harmless */
```

### Gotchas
- If the volume is not mounted a requester appears (unless `pr_WindowPtr` is -1); if it
  is still absent the call fails.
- A 0 lock gives `"SYS:"`, not the boot volume's real name.

**See also:** [NameFromFH](files.md#namefromfh), [Lock](#lock)

## CurrentDir
`BPTR CurrentDir(BPTR lock)` — LVO -126 (-$7E)
Registers: lock=D1; result in D0

Make a lock the process's current directory and return the previous one.

- **lock** — directory lock to become current (0 = root of the boot volume).
- **Result** — the old current-directory lock (0 is a valid value). You must keep it and
  restore it.

### Example
```c
BPTR dir = Lock("PROGDIR:data", ACCESS_READ);
if (dir) {
    BPTR old = CurrentDir(dir);           /* relative names now resolve in data/ */
    BPTR fh  = Open("level1.dat", MODE_OLDFILE);
    if (fh) {
        /* ... Read() ... */
        Close(fh);
    }
    CurrentDir(old);                       /* restore first ... */
    UnLock(dir);                           /* ... then free your lock */
}
```

### Gotchas
- CurrentDir does not copy or free anything: the lock you pass stays yours; UnLock it only
  after switching away from it.
- Restore the original directory before your program exits and never UnLock it -- it
  belongs to the Shell/Workbench that started you.
- Open/Lock with relative names need the current directory to be a valid lock or 0.

**See also:** [Lock](#lock), [UnLock](#unlock), [Open](files.md#open), [DupLock](#duplock), [SetCurrentDirName](processes.md#setcurrentdirname)

## ParentDir
`BPTR ParentDir(BPTR lock)` — LVO -210 (-$D2)
Registers: lock=D1; result in D0

Get a new lock on the directory containing a file or directory.

- **lock** — lock on a file or directory.
- **Result** — new shared lock on the parent (UnLock it), or 0. The root of a volume has
  no parent and also returns 0.

### Gotchas
- A 0 result from a volume root is not a usable "parent" -- it is the boot volume root.
  Stop walking upwards when you get 0.

**See also:** [Lock](#lock), [DupLock](#duplock), [UnLock](#unlock), [ParentOfFH](files.md#parentoffh), [DupLockFromFH](files.md#duplockfromfh)

## CreateDir
`BPTR CreateDir(CONST_STRPTR name)` — LVO -120 (-$78)
Registers: name=D1; result in D0

Create a new directory and return an exclusive lock on it.

- **name** — path of the directory to create; its parent must already exist.
- **Result** — exclusive lock on the new directory, or 0 (see IoErr(), e.g.
  `ERROR_OBJECT_EXISTS` 203, `ERROR_DISK_WRITE_PROTECTED` 214).

### Example
```c
BPTR lock = CreateDir("RAM:MyGame");
if (lock)
    UnLock(lock);                              /* release the exclusive lock at once */
else if (IoErr() != ERROR_OBJECT_EXISTS)
    PrintFault(IoErr(), "RAM:MyGame");
```

### Gotchas
- Forgetting to UnLock the returned exclusive lock keeps the directory unusable by
  others (and undeletable) until reboot.
- Only works on handlers that support directories.

**See also:** [Lock](#lock), [UnLock](#unlock), [DeleteFile](files.md#deletefile)

## Examine
`LONG Examine(BPTR lock, struct FileInfoBlock *fileInfoBlock)` — LVO -102 (-$66)
Registers: lock=D1, fileInfoBlock=D2; result in D0

Fill a FileInfoBlock with the name, type, size, protection and date of a locked object.

- **lock** — lock on the file or directory.
- **fileInfoBlock** — longword-aligned `struct FileInfoBlock`, from `AllocDosObject(DOS_FIB, NULL)`.
- **Result** — non-zero on success, 0 on failure (IoErr()).

FileInfoBlock fields (dos/dos.h; sizeof = `fib_SIZEOF` in dos.i):

| Field | Meaning |
|---|---|
| `fib_DiskKey` | handler-private |
| `fib_DirEntryType` | < 0 file, > 0 directory (see ST_ values below) |
| `fib_FileName[108]` | NUL-terminated name |
| `fib_Protection` | `FIBF_` bits; RWED bits 3-0 are 0 = allowed (see [SetProtection](files.md#setprotection)) |
| `fib_EntryType` | handler use; do not rely on it |
| `fib_Size` | size in bytes |
| `fib_NumBlocks` | blocks used |
| `fib_Date` | last-change `struct DateStamp` (asm label `fib_DateStamp`) |
| `fib_Comment[80]` | NUL-terminated file note |
| `fib_OwnerUID`, `fib_OwnerGID` | UWORD owner ids; zeroed by Examine, not every filesystem sets them |

`ST_` values (dos/dosextens.h): `ST_ROOT` 1, `ST_USERDIR` 2, `ST_SOFTLINK` 3, `ST_LINKDIR` 4,
`ST_FILE` -3, `ST_LINKFILE` -4, `ST_PIPEFILE` -5.

### Example
```c
#include <proto/exec.h>
#include <proto/dos.h>
#include <dos/dos.h>
#include <dos/dosextens.h>

/* Print every entry of a directory. Returns FALSE on a real error. */
BOOL ListDir(CONST_STRPTR path)
{
    BOOL ok = FALSE;
    struct FileInfoBlock *fib = AllocDosObject(DOS_FIB, NULL);
    BPTR lock = Lock(path, ACCESS_READ);

    if (fib && lock && Examine(lock, fib)) {
        if (fib->fib_DirEntryType > 0) {
            while (ExNext(lock, fib))
                Printf("%-32s %s %ld\n", (LONG)fib->fib_FileName,
                       (LONG)(fib->fib_DirEntryType > 0 ? "dir " : "file"),
                       fib->fib_Size);
            ok = (IoErr() == ERROR_NO_MORE_ENTRIES);   /* end of list, not an error */
        } else {
            SetIoErr(ERROR_OBJECT_WRONG_TYPE);
        }
    }
    if (!ok)
        PrintFault(IoErr(), path);
    UnLock(lock);
    if (fib)
        FreeDosObject(DOS_FIB, fib);
    return ok;
}
```

### Gotchas
- Longword alignment is mandatory. A FileInfoBlock declared as a local variable is not
  guaranteed to be; use AllocDosObject (or AllocVec).
- Test files with `fib_DirEntryType < 0`. `ST_SOFTLINK` looks like a directory but may point
  to a file.
- You may copy a FileInfoBlock, but never pass the copy to ExNext.

**See also:** [ExNext](#exnext), [ExAll](#exall), [ExamineFH](files.md#examinefh), [AllocDosObject](objects.md#allocdosobject), [Lock](#lock)

## ExNext
`LONG ExNext(BPTR lock, struct FileInfoBlock *fileInfoBlock)` — LVO -108 (-$6C)
Registers: lock=D1, fileInfoBlock=D2; result in D0

Step to the next entry of a directory previously passed to Examine.

- **lock** — the SAME directory lock given to Examine.
- **fileInfoBlock** — the SAME FileInfoBlock used by Examine or the previous ExNext; it is
  overwritten with the next entry.
- **Result** — non-zero with a new entry, 0 when done or on error. Done means IoErr() ==
  `ERROR_NO_MORE_ENTRIES` (232); anything else is a real error.

Example: see [Examine](#examine).

### Gotchas
- Examine a directory, never a file, before ExNext.
- To recurse, Lock the subdirectory and Examine it with a NEW FileInfoBlock; reusing the
  parent's FIB destroys the scan state.
- Keep the directory lock for the whole scan. Unlocking and relocking between calls is
  legal but makes every ExNext rebuild its state (slow).
- Always check IoErr() after the loop so a disk error is not mistaken for "end of directory".

**See also:** [Examine](#examine), [ExAll](#exall), [IoErr](errors.md#ioerr), [ExamineFH](files.md#examinefh), [AllocDosObject](objects.md#allocdosobject)

## ExAll
`LONG ExAll(BPTR lock, struct ExAllData *buffer, LONG size, LONG data, struct ExAllControl *control)` — LVO -432 (-$1B0)
Registers: lock=D1, buffer=D2, size=D3, data=D4, control=D5; result in D0

Read many directory entries per call into a buffer of linked ExAllData records.

- **lock** — lock on a directory.
- **buffer** — output buffer, at least word aligned (longword preferred); filled with
  `struct ExAllData` records chained by `ed_Next` (last one NULL).
- **size** — buffer size in bytes.
- **data** — how much to return per entry; each value includes everything below it:
  `ED_NAME` 1 (`ed_Name`), `ED_TYPE` 2 (`ed_Type`), `ED_SIZE` 3 (`ed_Size`),
  `ED_PROTECTION` 4 (`ed_Prot`), `ED_DATE` 5 (`ed_Days`, `ed_Mins`, `ed_Ticks`),
  `ED_COMMENT` 6 (`ed_Comment`, NULL if none), `ED_OWNER` 7 (`ed_OwnerUID`, `ed_OwnerGID`, V39).
  Fields past the requested level do not exist in the buffer.
- **control** — `struct ExAllControl` from `AllocDosObject(DOS_EXALLCONTROL, NULL)`:
  `eac_Entries` (records in buffer after the call), `eac_LastKey` (0 before the first call,
  then hands off), `eac_MatchString` (NULL, or a pattern already run through
  ParsePatternNoCase), `eac_MatchFunc` (NULL or a Hook: A0 = hook, A1 = filled ExAllData,
  A2 = pointer to the LONG data type; return TRUE to keep the entry).
- **Result** — non-zero: more entries remain, call again. 0: finished if IoErr() ==
  `ERROR_NO_MORE_ENTRIES`, otherwise an error. The final call can still return entries.

Since V36.

### Example
```c
#include <dos/exall.h>

#define EA_SIZE 2048

BOOL ScanDir(BPTR dir)
{
    BOOL ok = FALSE;
    struct ExAllData *buf = AllocVec(EA_SIZE, MEMF_ANY);       /* long aligned */
    struct ExAllControl *eac = AllocDosObject(DOS_EXALLCONTROL, NULL);

    if (buf && eac) {
        LONG more;
        eac->eac_LastKey = 0;
        do {
            more = ExAll(dir, buf, EA_SIZE, ED_SIZE, eac);
            if (!more && IoErr() != ERROR_NO_MORE_ENTRIES)
                break;                                     /* real error */
            if (eac->eac_Entries) {                        /* may be 0 even if more */
                struct ExAllData *ed;
                for (ed = buf; ed; ed = ed->ed_Next)
                    Printf("%s %s %lu\n", (LONG)ed->ed_Name,
                           (LONG)(ed->ed_Type < 0 ? "file" : "dir "), ed->ed_Size);
            }
            ok = !more;
        } while (more);
    }
    if (eac) FreeDosObject(DOS_EXALLCONTROL, eac);
    FreeVec(buf);
    return ok;
}
```

### Gotchas
- The control structure MUST come from AllocDosObject, and `eac_LastKey` MUST be 0 before
  the first call; never touch it between calls.
- Once ExAll returns non-zero you must keep calling until it returns 0, or stop with
  ExAllEnd (V39+).
- Handle `eac_Entries == 0` with a non-zero return.
- V37 ROM filesystem: `ED_OWNER` corrupts the returned data and comments come back as BSTRs;
  V37 dos emulation and RAM: reject `ED_OWNER` with `ERROR_BAD_NUMBER`. Fixed in V39. On
  pre-V39 systems ask for `ED_COMMENT` at most (or retry with it after `ERROR_BAD_NUMBER`).
- V36 ExAll is unreliable (MatchString, `ed_Next`, emulation); require V37.
- Handlers without the packet are emulated with Examine/ExNext, so behaviour is the same.

**See also:** [ExAllEnd](#exallend), [Examine](#examine), [ExNext](#exnext), [ExamineFH](files.md#examinefh), [MatchPatternNoCase](paths-and-names.md#matchpatternnocase), [ParsePatternNoCase](paths-and-names.md#parsepatternnocase), [AllocDosObject](objects.md#allocdosobject)

## ExAllEnd
`VOID ExAllEnd(BPTR lock, struct ExAllData *buffer, LONG size, LONG data, struct ExAllControl *control)` — LVO -990 (-$3DE)
Registers: lock=D1, buffer=D2, size=D3, data=D4, control=D5; no result

Abort an ExAll scan early, before it reaches `ERROR_NO_MORE_ENTRIES`.

- **lock, buffer, size, data, control** — exactly the arguments of the ExAll call being
  abandoned (needed for filesystems that cannot abort directly).

Since V39.

### Gotchas
- Not in V37/V38 dos: there, keep calling ExAll until it returns 0.

**See also:** [ExAll](#exall), [AllocDosObject](objects.md#allocdosobject)

## Info
`LONG Info(BPTR lock, struct InfoData *parameterBlock)` — LVO -114 (-$72)
Registers: lock=D1, parameterBlock=D2; result in D0

Fill an InfoData block with size, usage and state of the volume holding a lock.

- **lock** — lock on the volume or on any file/directory on it.
- **parameterBlock** — longword-aligned `struct InfoData` (allocate with AllocVec):
  `id_NumSoftErrors`, `id_UnitNumber`, `id_DiskState`, `id_NumBlocks`, `id_NumBlocksUsed`,
  `id_BytesPerBlock`, `id_DiskType`, `id_VolumeNode` (BPTR to the volume's DosList),
  `id_InUse` (0 if not in use).
- **Result** — non-zero on success, 0 on failure.

`id_DiskState`: `ID_WRITE_PROTECTED` 80, `ID_VALIDATING` 81, `ID_VALIDATED` 82.
`id_DiskType`: `ID_NO_DISK_PRESENT` -1, `ID_UNREADABLE_DISK` $42414400 ('BAD\0'),
`ID_DOS_DISK` $444F5300 ('DOS\0'), `ID_FFS_DISK` 'DOS\1', `ID_INTER_DOS_DISK` 'DOS\2',
`ID_INTER_FFS_DISK` 'DOS\3', `ID_FASTDIR_DOS_DISK` 'DOS\4', `ID_FASTDIR_FFS_DISK` 'DOS\5',
`ID_NOT_REALLY_DOS` $4E444F53 ('NDOS'), `ID_KICKSTART_DISK` $4B49434B ('KICK'),
`ID_MSDOS_DISK` $4D534400 ('MSD\0').

### Example
```c
/* Free space on the volume holding 'name', in KB; returns -1 on error. */
LONG FreeKB(CONST_STRPTR name)
{
    LONG kb = -1;
    struct InfoData *id = AllocVec(sizeof(struct InfoData), MEMF_ANY);
    BPTR lock = Lock(name, ACCESS_READ);

    if (id && lock && Info(lock, id)) {
        ULONG blocks = id->id_NumBlocks - id->id_NumBlocksUsed;
        ULONG bpb    = id->id_BytesPerBlock;
        kb = (LONG)((blocks >> 10) * bpb + (((blocks & 1023) * bpb) >> 10)); /* no 32-bit overflow */
    }
    UnLock(lock);
    FreeVec(id);
    return kb;
}
```

### Gotchas
- InfoData must be longword aligned; a local stack variable is not guaranteed to be.
- `blocks * id_BytesPerBlock` overflows 32 bits on volumes over 4 GB; scale first.
- Check `id_DiskState != ID_WRITE_PROTECTED` before planning writes.

**See also:** [Lock](#lock), [IsFileSystem](dos-list.md#isfilesystem), [AddBuffers](dos-list.md#addbuffers)

## MakeLink
`LONG MakeLink(CONST_STRPTR name, LONG dest, LONG soft)` — LVO -444 (-$1BC)
Registers: name=D1, dest=D2, soft=D3; result in D0

Create a hard link (to a locked object) or a soft link (to a path string).

- **name** — path of the link to create.
- **dest** — hard link: a lock (BPTR) on the target; soft link: a `CONST_STRPTR` path cast
  to LONG.
- **soft** — `LINK_HARD` (0) for a hard link, non-zero (`LINK_SOFT`, 1) for a soft link.
- **Result** — non-zero on success, 0 on failure.

Since V36.

### Gotchas
- Hard links are all equal to the original: the data survives until the last link is
  deleted. Soft links are resolved at access time (handler returns `ERROR_IS_SOFT_LINK`,
  dos calls ReadLink).
- V36 ROM filesystem soft links do not work (fixed V37); dos.h still comments soft links as
  "not fully supported".
- The lock passed for a hard link is still yours to UnLock (unverified).

**See also:** [ReadLink](#readlink), [Open](files.md#open), [Lock](#lock)

## ReadLink
`LONG ReadLink(struct MsgPort *port, BPTR lock, CONST_STRPTR path, STRPTR buffer, ULONG size)` — LVO -438 (-$1B6)
Registers: port=D1, lock=D2, path=D3, buffer=D4, size=D5; result in D0

Ask a filesystem to expand a soft link met while resolving a path.

- **port** — message port of the filesystem (e.g. `dvp_Port` from GetDeviceProc).
- **lock** — lock the path is relative to on that filesystem (e.g. `dvp_Lock`).
- **path** — the path that produced `ERROR_IS_SOFT_LINK` (233).
- **buffer** — receives the rewritten path.
- **size** — buffer size in bytes.
- **Result** — non-zero on success, 0 on failure.

Since V36.

### Gotchas
- Only needed by code that sends packets itself; ordinary dos calls resolve soft links
  internally. Restart resolution with GetDeviceProc on the new string.
- V36 ROM filesystem soft links do not work (fixed V37).

**See also:** [MakeLink](#makelink), [GetDeviceProc](dos-list.md#getdeviceproc), [Open](files.md#open), [Lock](#lock)
