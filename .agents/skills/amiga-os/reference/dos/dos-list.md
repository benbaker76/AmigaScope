# dos.library: devices, volumes and assigns

The DOS list holds every device (`DF0:`), volume (`Workbench:`) and assign (`LIBS:`) as a
`struct DosList` (dos/dosextens.h). To walk it: `LockDosList()` with a type mask plus
`LDF_READ` or `LDF_WRITE`, step with `NextDosEntry()`/`FindDosEntry()`, then `UnLockDosList()`
with the SAME flags; no DosList pointer is valid after the unlock. `dol_Name` is a
[BSTR](concepts.md#bptr-and-bstr) (BPTR to length byte + chars, no colon). The Assign* calls
create and edit assigns by name; `GetDeviceProc()` resolves a path to the handler port.

| `dol_Type` | Value | Node |
|---|---|---|
| `DLT_DEVICE` | 0 | device (handler/filesystem), `dol_misc.dol_handler` valid |
| `DLT_DIRECTORY` | 1 | assign made by AssignLock (`dol_Lock`, `dol_List` for extra dirs) |
| `DLT_VOLUME` | 2 | volume, `dol_misc.dol_volume` valid (date, lock list, disk type) |
| `DLT_LATE` | 3 | late-binding assign (AssignLate, `dol_AssignName`) |
| `DLT_NONBINDING` | 4 | non-binding assign (AssignPath, `dol_AssignName`) |
| `DLT_PRIVATE` | -1 | internal use only |

| Flag | Value | Meaning |
|---|---|---|
| `LDF_READ` | `$01` | read access -- one of READ/WRITE is REQUIRED when locking |
| `LDF_WRITE` | `$02` | write access (adding/removing entries) |
| `LDF_DEVICES` | `$04` | device nodes |
| `LDF_VOLUMES` | `$08` | volume nodes |
| `LDF_ASSIGNS` | `$10` | assign nodes (all three assign types) |
| `LDF_ENTRY` | `$20` | internal locking (excluded from `LDF_ALL`) |
| `LDF_DELETE` | `$40` | defined in dosextens.h, no public description |
| `LDF_ALL` | `$1C` | devices + volumes + assigns |

Colon rules differ per call: FindDosEntry, MakeDosEntry, AssignLock/Late/Path/Add and
RemAssignList take the bare name (`"LIBS"`); IsFileSystem, Inhibit, Format (device), Relabel
(old name) and AddBuffers take it WITH the colon (`"DF0:"`); GetDeviceProc/DeviceProc take a
full path.

## LockDosList
`struct DosList * LockDosList(ULONG flags)` — LVO -654 (-$28E)
Registers: flags=D1; result in D0

Lock the DOS list for walking or modification, blocking until it is free.

- **flags** — `LDF_READ` or `LDF_WRITE`, ORed with the node types you will touch
  (`LDF_DEVICES`, `LDF_VOLUMES`, `LDF_ASSIGNS`, `LDF_ALL`).
- **Result** — a list-head cookie to pass to NextDosEntry/FindDosEntry. It is NOT a valid
  DosList node -- never read fields from it.

Since V36.

### Example
```c
#include <proto/dos.h>
#include <dos/dosextens.h>
#include <string.h>

#define MAXVOL 32
char names[MAXVOL][32];
int n = 0, i;
ULONG flags = LDF_VOLUMES | LDF_READ;
struct DosList *dl = LockDosList(flags);

while (n < MAXVOL && (dl = NextDosEntry(dl, LDF_VOLUMES)) != NULL) {
    UBYTE *b = (UBYTE *)BADDR(dl->dol_Name);   /* BSTR: b[0] = length */
    int len = b[0] < 31 ? b[0] : 31;
    memcpy(names[n], b + 1, len);
    names[n][len] = '\0';
    n++;
}
UnLockDosList(flags);                  /* same flags; dl is now invalid */

for (i = 0; i < n; i++)                /* do the I/O after unlocking */
    Printf("%s:\n", (LONG)names[i]);
```

### Gotchas
- Calls nest: every LockDosList needs its own UnLockDosList with identical flags.
- It also does a `Forbid()` for 1.3 compatibility (may be removed later). Copy what you need
  and unlock quickly; don't do file or console I/O while holding it.
- Handlers/filesystems must never lock with `LDF_WRITE` (deadlock if a reader is waiting on
  a packet to you): use AttemptLockDosList in a retry loop, or spawn a process.
- Pre-V36 there is no call: walk the `di_DevInfo` BPTR chain (dosextens.h `DosInfo`) under
  `Forbid()`.

**See also:** [AttemptLockDosList](#attemptlockdoslist), [UnLockDosList](#unlockdoslist),
[NextDosEntry](#nextdosentry), [FindDosEntry](#finddosentry), exec.library Forbid

## AttemptLockDosList
`struct DosList * AttemptLockDosList(ULONG flags)` — LVO -666 (-$29A)
Registers: flags=D1; result in D0

Try to lock the DOS list without waiting; fails if another process holds it.

- **flags** — as for [LockDosList](#lockdoslist) (must include `LDF_READ` or `LDF_WRITE`).
- **Result** — list-head cookie (not a valid node) or failure.

Since V36.

### Gotchas
- V36 up to dos V39.23 returned either NULL **or 1** on failure (fixed V39.24). Test both:
  `if (dl != NULL && dl != (struct DosList *)1)`.
- Intended for handlers: on failure, service packets waiting at your port (don't Wait), then
  retry.

**See also:** [LockDosList](#lockdoslist), [UnLockDosList](#unlockdoslist), [AddDosEntry](#adddosentry)

## UnLockDosList
`VOID UnLockDosList(ULONG flags)` — LVO -660 (-$294)
Registers: flags=D1; no result

Release a DOS list lock taken by LockDosList or AttemptLockDosList.

- **flags** — MUST be exactly the flags used for the matching lock call.

Since V36.

### Gotchas
- Every DosList pointer obtained under the lock is dead afterwards.

**See also:** [LockDosList](#lockdoslist), [AttemptLockDosList](#attemptlockdoslist), exec.library Permit

## NextDosEntry
`struct DosList * NextDosEntry(CONST struct DosList *dlist, ULONG flags)` — LVO -690 (-$2B2)
Registers: dlist=D1, flags=D2; result in D0

Step to the next DOS list entry whose type matches the flags.

- **dlist** — the LockDosList/AttemptLockDosList result, or the entry returned last time.
- **flags** — node types wanted (`LDF_DEVICES`/`LDF_VOLUMES`/`LDF_ASSIGNS`); those types must
  be locked.
- **Result** — next matching entry, or NULL at the end.

Since V36.

**See also:** [LockDosList](#lockdoslist), [FindDosEntry](#finddosentry), [AddDosEntry](#adddosentry),
[RemDosEntry](#remdosentry)

## FindDosEntry
`struct DosList * FindDosEntry(CONST struct DosList *dlist, CONST_STRPTR name, ULONG flags)` — LVO -684 (-$2AC)
Registers: dlist=D1, name=D2, flags=D3; result in D0

Find a DOS list entry by name among the locked node types.

- **dlist** — start point: the LockDosList result, or a previously found entry to continue
  (the autodoc loops `while (dl = FindDosEntry(dl, name, LDF_VOLUMES))`).
- **name** — entry name WITHOUT the colon (`"Work"`, not `"Work:"`).
- **flags** — types to match; the same flags as the lock, or a subset. `LDF_READ`/`LDF_WRITE`
  are not needed here.
- **Result** — matching entry or NULL.

Since V36.

### Example
```c
/* Is there a volume node called "Work"? (name without ':') */
BOOL HaveVolume(CONST_STRPTR name)
{
    struct DosList *dl = LockDosList(LDF_VOLUMES | LDF_READ);
    BOOL found = FindDosEntry(dl, name, LDF_VOLUMES) != NULL;
    UnLockDosList(LDF_VOLUMES | LDF_READ);
    return found;
}
```

### Gotchas
- The list must be locked for the whole search and for any use of the result.
- Several volume nodes may share a name (different dates); loop to see all of them.

**See also:** [LockDosList](#lockdoslist), [NextDosEntry](#nextdosentry), [GetDeviceProc](#getdeviceproc)

## MakeDosEntry
`struct DosList * MakeDosEntry(CONST_STRPTR name, LONG type)` — LVO -696 (-$2B8)
Registers: name=D1, type=D2; result in D0

Allocate a zeroed DosList node with its name and type filled in.

- **name** — node name without colon; copied into a newly allocated, null-terminated BSTR.
- **type** — `DLT_DEVICE`, `DLT_DIRECTORY`, `DLT_VOLUME`, `DLT_LATE` or `DLT_NONBINDING`.
- **Result** — new node (all other fields 0) or NULL.

Since V36.

### Example
```c
/* Publish an already-running handler port as device "MYH:" */
struct DosList *dl = MakeDosEntry("MYH", DLT_DEVICE);
if (dl) {
    dl->dol_Task = myHandlerPort;      /* non-NULL: DOS won't try to start a handler */
    if (!AddDosEntry(dl))
        FreeDosEntry(dl);              /* name clash etc. -- IoErr() has why */
}
```

**See also:** [FreeDosEntry](#freedosentry), [AddDosEntry](#adddosentry), [RemDosEntry](#remdosentry)

## FreeDosEntry
`VOID FreeDosEntry(struct DosList *dlist)` — LVO -702 (-$2BE)
Registers: dlist=D1; no result

Free a DosList node that came from MakeDosEntry.

- **dlist** — node from MakeDosEntry, already removed from (or never added to) the list.

Since V36.

### Gotchas
- Only for MakeDosEntry nodes; never for entries DOS or other programs created.

**See also:** [MakeDosEntry](#makedosentry), [RemDosEntry](#remdosentry)

## AddDosEntry
`LONG AddDosEntry(struct DosList *dlist)` — LVO -678 (-$2A6)
Registers: dlist=D1; result in D0

Link a device, volume or assign node into the DOS list.

- **dlist** — node to add (normally from MakeDosEntry).
- **Result** — non-zero on success; 0 if it conflicts with an existing entry (another
  assign or device of the same name). Volumes may share names with each other (different
  dates), with devices and with assigns.

Since V36.

### Gotchas
- The list need NOT be locked for this call, but after a successful add you may only touch
  the node while holding the list lock.
- From inside a handler: `if (AttemptLockDosList(LDF_xxx|LDF_WRITE)) { AddDosEntry(...);
  UnLockDosList(LDF_xxx|LDF_WRITE); }`, and on failure process your pending packets (don't
  wait) and retry -- otherwise you can deadlock.

**See also:** [RemDosEntry](#remdosentry), [MakeDosEntry](#makedosentry), [AttemptLockDosList](#attemptlockdoslist)

## RemDosEntry
`BOOL RemDosEntry(struct DosList *dlist)` — LVO -672 (-$2A0)
Registers: dlist=D1; result in D0

Unlink an entry from the DOS list without freeing it.

- **dlist** — entry to remove.
- **Result** — non-zero on success.

Since V36.

### Gotchas
- Lock the list first with `LDF_WRITE` plus the entry's type flag; handlers use the
  AttemptLockDosList retry pattern from [AddDosEntry](#adddosentry).
- Memory is not freed: call FreeDosEntry afterwards if it came from MakeDosEntry.

**See also:** [AddDosEntry](#adddosentry), [FreeDosEntry](#freedosentry), [LockDosList](#lockdoslist)

## AssignLock
`LONG AssignLock(CONST_STRPTR name, BPTR lock)` — LVO -612 (-$264)
Registers: name=D1, lock=D2; result in D0

Create or replace an assign that points at a directory lock you hand over.

- **name** — assign name WITHOUT trailing colon (`"GAMEDATA"`).
- **lock** — lock on the target directory; ownership passes to the assign on success.
  0 removes any existing assign of that name.
- **Result** — non-zero on success. Replaces an existing assign of the same name; fails if a
  conflicting entry (e.g. a device) has the name.

Since V36.

### Example
```c
BPTR lock = Lock("Work:MyGame/data", ACCESS_READ);
if (lock) {
    if (!AssignLock("GAMEDATA", lock)) {
        PrintFault(IoErr(), "assign");
        UnLock(lock);                  /* failure: lock is still ours */
    }
    /* success: lock belongs to the assign -- don't use or UnLock it */
}
/* ... later: */
AssignLock("GAMEDATA", 0);             /* remove the assign */
```

### Gotchas
- After success never use the lock again; the system unlocks it when the assign goes. To
  keep your own copy pass `DupLock(lock)` (check it for 0) instead.
- On failure the lock is NOT unlocked -- free it yourself.

**See also:** [AssignAdd](#assignadd), [AssignPath](#assignpath), [AssignLate](#assignlate),
[RemAssignList](#remassignlist), [Lock](locks-and-directories.md#lock), [DupLock](locks-and-directories.md#duplock)

## AssignLate
`BOOL AssignLate(CONST_STRPTR name, CONST_STRPTR path)` — LVO -618 (-$26A)
Registers: name=D1, path=D2; result in D0

Create an assign stored as a path that is locked on first use.

- **name** — assign name without trailing colon.
- **path** — target path string. On the first reference (e.g. `Open("NAME:x",...)`) DOS locks
  it; if that works the assign behaves like an AssignLock assign from then on.
- **Result** — non-zero on success.

Since V36.

### Example
```c
/* Neither volume needs to be mounted yet; access will ask for it */
if (!AssignLate("MYFONTS", "Extras:Fonts"))
    PrintFault(IoErr(), "AssignLate");
if (!AssignPath("C2", "DF2:C"))        /* re-resolved on every use */
    PrintFault(IoErr(), "AssignPath");
```

### Gotchas
- Main use: assigns to volumes that aren't inserted (startup scripts) without an immediate
  "insert volume" requester.
- AssignAdd works on it only after it has been resolved.

**See also:** [AssignPath](#assignpath), [AssignLock](#assignlock), [AssignAdd](#assignadd)

## AssignPath
`BOOL AssignPath(CONST_STRPTR name, CONST_STRPTR path)` — LVO -624 (-$270)
Registers: name=D1, path=D2; result in D0

Create a non-binding assign whose path is re-resolved on every reference.

- **name** — assign name without trailing colon.
- **path** — target path; no permanent lock is held (`DLT_NONBINDING`). `C2` -> `DF2:C`
  follows whatever disk is in DF2: at each access.
- **Result** — non-zero on success.

Since V36. Example: see [AssignLate](#assignlate).

### Gotchas
- V36 [DeviceProc](#deviceproc) fails for names relative to an AssignPath assign; use
  GetDeviceProc.

**See also:** [AssignLate](#assignlate), [AssignLock](#assignlock), [AssignAdd](#assignadd), [Open](files.md#open)

## AssignAdd
`BOOL AssignAdd(CONST_STRPTR name, BPTR lock)` — LVO -630 (-$276)
Registers: name=D1, lock=D2; result in D0

Add another directory lock to an existing assign, making a multi-directory assign.

- **name** — assign name without trailing colon.
- **lock** — directory lock to append; owned by the assign on success.
- **Result** — non-zero on success; on failure the lock is not unlocked.

Since V36.

### Example
```c
BPTR l = Lock("Work:MyLibs", ACCESS_READ);
if (l && !AssignAdd("LIBS", l)) {     /* LIBS: now also searches Work:MyLibs */
    PrintFault(IoErr(), "AssignAdd");
    UnLock(l);
}
```

### Gotchas
- Only works on an AssignLock assign, or an AssignLate one that has already been resolved;
  not on AssignPath assigns.
- Lock ownership as for [AssignLock](#assignlock): pass a DupLock if you need to keep it.

**See also:** [AssignLock](#assignlock), [RemAssignList](#remassignlist), [GetDeviceProc](#getdeviceproc)

## RemAssignList
`LONG RemAssignList(CONST_STRPTR name, BPTR lock)` — LVO -636 (-$27C)
Registers: name=D1, lock=D2; result in D0

Remove one directory from a multi-directory assign.

- **name** — assign name without trailing colon.
- **lock** — any lock on the directory to drop; the first entry for which SameLock reports
  the same object is removed and the ASSIGN's own lock is unlocked (yours is untouched).
- **Result** — non-zero on success.

Since V36.

### Gotchas
- V36 through dos V39.23 could not remove the FIRST lock of the assign (fixed V39.24).

**See also:** [AssignAdd](#assignadd), [AssignLock](#assignlock), [SameLock](locks-and-directories.md#samelock)

## GetDeviceProc
`struct DevProc * GetDeviceProc(CONST_STRPTR name, struct DevProc *dp)` — LVO -642 (-$282)
Registers: name=D1, dp=D2; result in D0

Resolve a path to the handler port and directory lock to send packets to.

- **name** — object path: relative (`"foo/bar"`), relative to the current volume
  (`":foo/bar"`) or to a device/volume/assign (`"foo:bar"`).
- **dp** — NULL on the first call; the previous result to move to the next directory of a
  multi-directory assign.
- **Result** — `struct DevProc *` or NULL. Fields: `dvp_Port` (handler MsgPort), `dvp_Lock`
  (lock the name is relative to), `dvp_Flags` (`DVPF_ASSIGN` = 2: came from an assign),
  `dvp_DevNode` (don't touch). After the last directory it returns NULL with
  `ERROR_NO_MORE_ENTRIES` in IoErr().

Since V36.

### Example
```c
/* Try an operation in every directory of a (multi-)assign until it works.
   try_one() is your packet I/O against port + dirlock; it sets IoErr(). */
LONG TryAllDirs(CONST_STRPTR path)
{
    struct DevProc *dvp = NULL;
    LONG err;

    for (;;) {
        dvp = GetDeviceProc(path, dvp);
        if (dvp == NULL) {
            err = IoErr();             /* ERROR_NO_MORE_ENTRIES after the last dir */
            break;
        }
        if (try_one(dvp->dvp_Port, dvp->dvp_Lock)) {
            err = 0;
            break;
        }
        err = IoErr();
        if (err != ERROR_OBJECT_NOT_FOUND || !(dvp->dvp_Flags & DVPF_ASSIGN))
            break;                     /* real error, or nothing more to try */
    }
    FreeDeviceProc(dvp);               /* NULL is fine */
    return err;
}
```

### Gotchas
- Retry with the old DevProc only when the operation failed with `ERROR_OBJECT_NOT_FOUND`
  AND `dvp_Flags & DVPF_ASSIGN`; 2.0/2.01 required that check before calling again.
- Never UnLock `dvp_Lock` or use port/lock after FreeDeviceProc. The handler-in-memory
  usage counter it bumps was not active in 2.0.

**See also:** [FreeDeviceProc](#freedeviceproc), [DeviceProc](#deviceproc), [DoPkt](packets.md#dopkt),
[AssignAdd](#assignadd)

## FreeDeviceProc
`VOID FreeDeviceProc(struct DevProc *dp)` — LVO -648 (-$288)
Registers: dp=D1; no result

Release a DevProc from GetDeviceProc along with any temporary locks it holds.

- **dp** — GetDeviceProc result; NULL is allowed.

Since V36.

### Gotchas
- The port and lock from the DevProc must not be used afterwards.

**See also:** [GetDeviceProc](#getdeviceproc), [DeviceProc](#deviceproc)

## DeviceProc
`struct MsgPort * DeviceProc(CONST_STRPTR name)` — LVO -174 (-$AE)
Registers: name=D1; result in D0

Old-style lookup of the handler MsgPort for a name; use GetDeviceProc on V36+.

- **name** — device, volume, assign or path name.
- **Result** — the handler process's `pr_MsgPort`, or 0 if none. For an assign, IoErr()
  returns the assign's directory lock -- borrowed: don't UnLock or Examine it (DupLock first).

### Gotchas
- dosextens.h: the Process is `(struct Process *)(port - sizeof(struct Task))`.
- Cannot handle multi-directory assigns; in V36 it fails for names relative to an
  AssignPath assign.

**See also:** [GetDeviceProc](#getdeviceproc), [FreeDeviceProc](#freedeviceproc), [DupLock](locks-and-directories.md#duplock)

## IsFileSystem
`BOOL IsFileSystem(CONST_STRPTR name)` — LVO -708 (-$2C4)
Registers: name=D1; result in D0

Ask whether a DOS device is a filesystem (stores separate files) or a stream handler.

- **name** — device name WITH trailing colon (`"PIPE:"`, `"DH0:"`).
- **Result** — non-zero for a filesystem. Handlers that don't know the 2.0 packet are tested
  with `Lock(":")` instead.

Since V36.

### Gotchas
- A filesystem need not support directories.

**See also:** [Lock](locks-and-directories.md#lock), [Info](locks-and-directories.md#info)

## Inhibit
`LONG Inhibit(CONST_STRPTR name, LONG onoff)` — LVO -726 (-$2D6)
Registers: name=D1, onoff=D2; result in D0

Stop (or restart) all activity of a filesystem, e.g. around raw disk access or formatting.

- **name** — device name WITH colon (`"DF0:"`).
- **onoff** — `DOSTRUE` (-1) inhibits, `FALSE` (0) releases.
- **Result** — non-zero on success. Sends `ACTION_INHIBIT` to the handler.

Since V36.

### Example
```asm
        include "dos/dos.i"
        include "lvo/dos_lib.i"

        move.l  DOSBase,a6
        move.l  #df0,d1
        moveq   #DOSTRUE,d2             ; stop the filesystem
        jsr     _LVOInhibit(a6)
        tst.l   d0
        beq     .fail
        ; ... trackdisk.device raw I/O on unit 0 ...
        move.l  #df0,d1
        moveq   #DOSFALSE,d2            ; always release again
        jsr     _LVOInhibit(a6)
.fail:
        rts

df0:    dc.b    "DF0:",0
        even
```

### Gotchas
- Always pair with `Inhibit(name, FALSE)`. When released, the disk may have changed or been
  removed; the filesystem has to re-read it.

**See also:** [Format](#format), [Relabel](#relabel), [action codes](packets.md#action-codes)

## Format
`BOOL Format(CONST_STRPTR filesystem, CONST_STRPTR volumename, ULONG dostype)` — LVO -714 (-$2CA)
Registers: filesystem=D1, volumename=D2, dostype=D3; result in D0

Make a filesystem write an empty volume structure onto already low-level formatted media.

- **filesystem** — device name WITH colon (`"DF0:"`).
- **volumename** — new volume name, no colon (if the filesystem supports names).
- **dostype** — format type for multi-type filesystems, e.g. `ID_DOS_DISK` (`'DOS\0'`),
  `ID_FFS_DISK` (`'DOS\1'`), `ID_INTER_FFS_DISK` (`'DOS\3'`), `ID_FASTDIR_FFS_DISK`
  (`'DOS\5'`) from dos/dos.h.
- **Result** — non-zero on success.

Since V36.

### Example
```c
if (Inhibit("DF0:", DOSTRUE)) {
    if (!Format("DF0:", "Empty", ID_FFS_DISK))
        PrintFault(IoErr(), "Format");
    Inhibit("DF0:", FALSE);
}
```

### Gotchas
- Inhibit the device first, otherwise expect `ERROR_OBJECT_IN_USE`.
- Does not low-level format or verify tracks; do that via the device driver first.
- Broken in V36 (volume name not converted to a BSTR): require V37.
- Several printed packet docs give wrong arguments for `ACTION_FORMAT`; call Format()
  rather than sending the packet.

**See also:** [Inhibit](#inhibit), [Relabel](#relabel), [Info](locks-and-directories.md#info)

## Relabel
`LONG Relabel(CONST_STRPTR drive, CONST_STRPTR newname)` — LVO -720 (-$2D0)
Registers: drive=D1, newname=D2; result in D0

Rename a volume, if the filesystem supports it.

- **drive** — full device name WITH colon (`"DF0:"`).
- **newname** — new volume name WITHOUT colon.
- **Result** — non-zero on success.

Since V36.

**See also:** [Format](#format), [Rename](files.md#rename)

## AddBuffers
`LONG AddBuffers(CONST_STRPTR name, LONG number)` — LVO -732 (-$2DC)
Registers: name=D1, number=D2; result in D0

Grow or shrink a filesystem's block buffer cache.

- **name** — device name WITH colon (`"DH0:"`).
- **number** — buffers to add; may be negative. Memory per buffer and limits depend on the
  filesystem.
- **Result** — success; IoErr() then holds the number of buffers now in use. See gotchas for
  old ROM filesystems.

Since V36.

### Example
```c
LONG r = AddBuffers("DH0:", 50);
LONG total;
if (r == 0)
    PrintFault(IoErr(), "AddBuffers");
else {
    total = (r == DOSTRUE) ? IoErr() : r;  /* V37-and-older FS return the count itself */
    Printf("%ld buffers\n", total);
}
```

### Gotchas
- V37 and older ROM filesystems return the buffer count instead of a boolean: treat 0 as
  failure, -1 (`DOSTRUE`) as "count is in IoErr()", any other positive value as the count.
- The V36 ROM filesystem reports a wrong count unless preceded by `AddBuffers(fs, -1)`
  (fixed V37).

**See also:** [IoErr](errors.md#ioerr), [Info](locks-and-directories.md#info)
