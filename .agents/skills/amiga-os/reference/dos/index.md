# dos.library

AmigaDOS: files, directories, locks, processes, command-line parsing, environment variables,
the device/volume/assign list and handler packets. Library name `"dos.library"` (`DOSNAME`),
base variable `DOSBase` (`struct DosLibrary *`, `dos/dosextens.h`). Read
[concepts](concepts.md) first: BPTRs, IoErr, locks vs file handles, processes vs tasks.

## Opening

dos.library is in ROM and always present, but open it like any other library and check the
version you need. Require **V37 (Kickstart 2.04)** for anything beyond the original 1.x calls:
many V36 functions were broken (see each entry's Gotchas).

```c
#include <proto/exec.h>
#include <proto/dos.h>

struct DosLibrary *DOSBase;

int main(void)
{
    DOSBase = (struct DosLibrary *)OpenLibrary("dos.library", 37);
    if (!DOSBase)
        return 20;                       /* RETURN_FAIL: needs Kickstart 2.04+ */
    PutStr("Hello\n");
    CloseLibrary((struct Library *)DOSBase);
    return 0;
}
```

```asm
        include "exec/types.i"
        include "dos/dos.i"
        include "lvo/exec_lib.i"
        include "lvo/dos_lib.i"

        move.l  4.w,a6                  ; ExecBase
        lea     dosname(pc),a1
        moveq   #37,d0
        jsr     _LVOOpenLibrary(a6)
        move.l  d0,DOSBase
        beq     .nodos
        ...
        move.l  4.w,a6
        move.l  DOSBase,a1
        jsr     _LVOCloseLibrary(a6)

dosname:
        DOSNAME                         ; dc.b 'dos.library',0 (macro in dos/dos.i)
```

## Calling convention

- A6 = `DOSBase`. Arguments in **D1, D2, D3, D4, ...** (not D0/A0 as in exec); result in D0.
  D0/D1/A0/A1 are scratch after every call; all other registers are preserved.
- Exceptions: `DoPkt` uses D1-D7 (secondary result also in D1); `CliInitNewcli`/`CliInitRun`
  take A0; `InternalLoadSeg` takes D0/A0/A1/A2; `InternalUnLoadSeg` takes D1/A1.
- On failure most calls return 0 (some -1, a few return 0 for SUCCESS) and leave the reason in
  `IoErr()`; see [calling convention and IoErr](concepts.md#calling-convention-and-ioerr) and
  [error codes](errors.md#error-codes).
- Only a **Process** may call dos.library (not a plain exec Task, interrupt or input handler),
  and only while the OS is running normally.

## Version landmarks

| Version | Kickstart | What arrived |
|---|---|---|
| V33 and earlier | 1.x | the original BCPL-era calls (LVO -30 Open ... -222 Execute): Open, Close, Read, Write, Seek, Input, Output, Lock, UnLock, DupLock, Examine, ExNext, Info, CreateDir, CurrentDir, ParentDir, DeleteFile, Rename, SetComment, SetProtection, LoadSeg, UnLoadSeg, CreateProc, Execute, Exit, DeviceProc, DateStamp, Delay, WaitForChar, IsInteractive, IoErr. Their autodocs carry no version tag. |
| V36 | 2.0 | almost everything else: buffered I/O, Printf, ReadArgs, AllocDosObject, ExAll, pattern matching, notification, record locks, DosList and assign calls, variables, SystemTagList, CreateNewProc, RunCommand, packet calls, NameFromLock, SetFileDate... |
| V37 | 2.04 | MatchPatternNoCase, ParsePatternNoCase, working SameDevice; fixes for NP_Arguments, ChangeMode, ExAll, LockRecord, soft links, ROM filesystem notification. SetOwner entry exists but returns FALSE. |
| V39 | 3.0 | ExAllEnd, SetOwner, ED_OWNER, GVF_SAVE_VAR, GVF_DONT_NULL_TERM for globals; fixes to FGets, StrToLong, SplitName, DOS_CLI freeing, AttemptLockDosList, RemAssignList, Seek error return in the ROM filesystem. |
| V40 | 3.1 | SetVBuf actually implemented (the autodoc says "not implemented until after V39"). |
| V44/V45 | 3.5/3.9 | no dos.library function in the NDK 3.9 autodocs is newer than V39. The V43+ FFS (release notes) supports files up to 4 GB - 2 bytes: compare Seek results with exactly -1. |

## Files in this directory

- [concepts.md](concepts.md) -- BPTR/BSTR, register convention and IoErr, locks vs file handles,
  processes vs tasks, stdin/stdout, consoles, a safe whole-file load.
- [files.md](files.md) -- Open/Close/Read/Write/Seek, default streams, handle-to-lock
  conversions, delete/rename/protection/comment/date/owner, console handle calls.
- [buffered-io.md](buffered-io.md) -- FGetC/FGets/FRead, FPutC/FPuts/FWrite, PutStr, Printf
  family, Flush, SetVBuf.
- [locks-and-directories.md](locks-and-directories.md) -- Lock/UnLock/DupLock, CurrentDir,
  ParentDir, CreateDir, Examine/ExNext/ExAll, Info, SameLock, links.
- [paths-and-names.md](paths-and-names.md) -- pattern syntax, FilePart/PathPart/AddPart/SplitName,
  MatchFirst/MatchNext/MatchEnd, ParsePattern/MatchPattern (+NoCase).
- [processes.md](processes.md) -- CreateNewProc, SystemTagList, Execute, RunCommand, Ctrl-C
  checks, CLI structure and program name/dir/prompt accessors, shell start-up calls.
- [loading.md](loading.md) -- LoadSeg/UnLoadSeg, NewLoadSeg, InternalLoadSeg, resident segments.
- [arguments.md](arguments.md) -- ReadArgs template syntax, FreeArgs, FindArg, ReadItem,
  StrToLong.
- [errors.md](errors.md) -- IoErr/SetIoErr, Fault/PrintFault, ErrorReport, all ERROR_ codes.
- [variables.md](variables.md) -- GetVar/SetVar/DeleteVar/FindVar, GVF_/LV_ flags.
- [dos-list.md](dos-list.md) -- DosList locking and walking, assigns, GetDeviceProc,
  Inhibit/Format/Relabel/AddBuffers/IsFileSystem.
- [packets.md](packets.md) -- ACTION_ codes, DoPkt/SendPkt/WaitPkt/ReplyPkt/AbortPkt.
- [time.md](time.md) -- DateStamp, Delay, CompareDates, DateToStr/StrToDate.
- [notification-and-locking.md](notification-and-locking.md) -- StartNotify/EndNotify, record
  locks.
- [objects.md](objects.md) -- AllocDosObject/FreeDosObject and the DOS_ object types.

<!-- FUNCTION TABLE -->
<!-- Generated by tools/skills/build_indexes.py - do not edit by hand. -->

## Functions

| Function | LVO | Registers | Summary |
|---|---|---|---|
| [AbortPkt](packets.md#abortpkt) | -264 | port=D1, pkt=D2 | Ask a handler to abort a packet sent with SendPkt; currently does nothing. |
| [AddBuffers](dos-list.md#addbuffers) | -732 | name=D1, number=D2 | Grow or shrink a filesystem's block buffer cache. |
| [AddDosEntry](dos-list.md#adddosentry) | -678 | dlist=D1 | Link a device, volume or assign node into the DOS list. |
| [AddPart](paths-and-names.md#addpart) | -882 | dirname=D1, filename=D2, size=D3 | Append a file or subpath to a directory path in a buffer, inserting `/` as needed. |
| [AddSegment](loading.md#addsegment) | -774 | name=D1, seg=D2, system=D3 | Add a seglist to the DOS resident list under a name. |
| [AllocDosObject](objects.md#allocdosobject) (alias: AllocDosObjectTagList, AllocDosObjectTags) | -228 | type=D1, tags=D2 | Allocate and initialise a DOS structure of the given type. |
| [AssignAdd](dos-list.md#assignadd) | -630 | name=D1, lock=D2 | Add another directory lock to an existing assign, making a multi-directory assign. |
| [AssignLate](dos-list.md#assignlate) | -618 | name=D1, path=D2 | Create an assign stored as a path that is locked on first use. |
| [AssignLock](dos-list.md#assignlock) | -612 | name=D1, lock=D2 | Create or replace an assign that points at a directory lock you hand over. |
| [AssignPath](dos-list.md#assignpath) | -624 | name=D1, path=D2 | Create a non-binding assign whose path is re-resolved on every reference. |
| [AttemptLockDosList](dos-list.md#attemptlockdoslist) | -666 | flags=D1 | Try to lock the DOS list without waiting; fails if another process holds it. |
| [ChangeMode](files.md#changemode) | -450 | type=D1, fh=D2, newmode=D3 | Ask the handler to change the access mode of an open lock or file handle. |
| [CheckSignal](processes.md#checksignal) | -792 | mask=D1 | Test and clear signals in a mask; the standard way to poll for Ctrl-C/D/E/F breaks. |
| [Cli](processes.md#cli) | -492 | none | Return the calling process's CommandLineInterface structure, or NULL if it has none. |
| [CliInitNewcli](processes.md#cliinitnewcli) | -930 | dp=A0 | Shell writers only: set up a new shell process from its NewShell/NewCLI startup packet. |
| [CliInitRun](processes.md#cliinitrun) | -936 | dp=A0 | Shell writers only: set up a shell process from a Run/System()/Execute() startup packet. |
| [Close](files.md#close) | -36 | file=D1 | Close a file handle, flushing buffered output, and free it. |
| [CompareDates](time.md#comparedates) | -738 | date1=D1, date2=D2 | Compare two DateStamps. |
| [CreateDir](locks-and-directories.md#createdir) | -120 | name=D1 | Create a new directory and return an exclusive lock on it. |
| [CreateNewProc](processes.md#createnewproc) (alias: CreateNewProcTagList, CreateNewProcTags) | -498 | tags=D1 | Create a new DOS process from a seglist or an entry point, configured by tags. |
| [CreateProc](processes.md#createproc) | -138 | name=D1, pri=D2, segList=D3, stackSize=D4 | Create a process from a seglist (1.x call); returns the new process's message port. |
| [CurrentDir](locks-and-directories.md#currentdir) | -126 | lock=D1 | Make a lock the process's current directory and return the previous one. |
| [DateStamp](time.md#datestamp) | -192 | date=D1 | Fill a DateStamp with the current date and time. |
| [DateToStr](time.md#datetostr) | -744 | datetime=D1 | Format a DateStamp as day, date and time strings. |
| [Delay](time.md#delay) | -198 | timeout=D1 | Sleep the calling process for a number of ticks (50 per second). |
| [DeleteFile](files.md#deletefile) | -72 | name=D1 | Delete a file or an empty directory. |
| [DeleteVar](variables.md#deletevar) | -912 | name=D1, flags=D2 | Delete a local or global variable. |
| [DeviceProc](dos-list.md#deviceproc) | -174 | name=D1 | Old-style lookup of the handler MsgPort for a name; use GetDeviceProc on V36+. |
| [DoPkt](packets.md#dopkt) (alias: DoPkt0, DoPkt1, DoPkt2, DoPkt3, DoPkt4) | -240 | port=D1, action=D2, arg1=D3, arg2=D4, arg3=D5, arg4=D6, arg5=D7 | Send a packet to a handler and wait for the reply (synchronous). |
| [DupLock](locks-and-directories.md#duplock) | -96 | lock=D1 | Create a second, independent shared lock on the same object. |
| [DupLockFromFH](files.md#duplockfromfh) | -372 | fh=D1 | Get a new lock on the object behind an open file handle. |
| [EndNotify](notification-and-locking.md#endnotify) | -894 | notify=D1 | Cancel a notification request. |
| [ErrorReport](errors.md#errorreport) | -480 | code=D1, type=D2, arg1=D3, device=D4 | Put up the system Retry/Cancel requester for a disk-type error. |
| [ExAll](locks-and-directories.md#exall) | -432 | lock=D1, buffer=D2, size=D3, data=D4, control=D5 | Read many directory entries per call into a buffer of linked ExAllData records. |
| [ExAllEnd](locks-and-directories.md#exallend) | -990 | lock=D1, buffer=D2, size=D3, data=D4, control=D5 | Abort an ExAll scan early, before it reaches `ERROR_NO_MORE_ENTRIES`. |
| [Examine](locks-and-directories.md#examine) | -102 | lock=D1, fileInfoBlock=D2 | Fill a FileInfoBlock with the name, type, size, protection and date of a locked object. |
| [ExamineFH](files.md#examinefh) | -390 | fh=D1, fib=D2 | Fill a FileInfoBlock with information about an open file. |
| [Execute](processes.md#execute) | -222 | string=D1, file=D2, file2=D3 | Run a shell command line (optionally followed by commands read from a handle) and wait. |
| [Exit](processes.md#exit) | -144 | returnCode=D1 | BCPL-style program exit; do NOT call it from C or assembler programs. |
| [ExNext](locks-and-directories.md#exnext) | -108 | lock=D1, fileInfoBlock=D2 | Step to the next entry of a directory previously passed to Examine. |
| [Fault](errors.md#fault) | -468 | code=D1, header=D2, buffer=D3, len=D4 | Build the text for a DOS error code, prefixed by a header, into a buffer. |
| [FGetC](buffered-io.md#fgetc) | -306 | fh=D1 | Read one character from a file handle through its buffer. |
| [FGets](buffered-io.md#fgets) | -336 | fh=D1, buf=D2, buflen=D3 | Read one line (up to a newline or EOF) from a file handle into a buffer. |
| [FilePart](paths-and-names.md#filepart) | -870 | path=D1 | Return a pointer to the last component (normally the file name) of a path string. |
| [FindArg](arguments.md#findarg) | -804 | keyword=D1, arg_template=D2 | Return the index of a keyword within a ReadArgs template, or -1. |
| [FindCliProc](processes.md#findcliproc) | -546 | num=D1 | Return the Process for a CLI number, or NULL if that number is not an active CLI. |
| [FindDosEntry](dos-list.md#finddosentry) | -684 | dlist=D1, name=D2, flags=D3 | Find a DOS list entry by name among the locked node types. |
| [FindSegment](loading.md#findsegment) | -780 | name=D1, seg=D2, system=D3 | Search the DOS resident list for a named segment; call it under Forbid(). |
| [FindVar](variables.md#findvar) | -918 | name=D1, type=D2 | Find a local variable's LocalVar node in the current process's list. |
| [Flush](buffered-io.md#flush) | -360 | fh=D1 | Write out pending buffered output, or discard read-ahead and resync the file position. |
| [Format](dos-list.md#format) | -714 | filesystem=D1, volumename=D2, dostype=D3 | Make a filesystem write an empty volume structure onto already low-level formatted media. |
| [FPutC](buffered-io.md#fputc) | -312 | fh=D1, ch=D2 | Write one character to a file handle through its buffer. |
| [FPuts](buffered-io.md#fputs) | -342 | fh=D1, str=D2 | Write a null-terminated string to a file handle through its buffer (no newline added). |
| [FRead](buffered-io.md#fread) | -324 | fh=D1, block=D2, blocklen=D3, number=D4 | Read a number of fixed-size blocks through the handle's buffer. |
| [FreeArgs](arguments.md#freeargs) | -858 | args=D1 | Free everything a successful ReadArgs() allocated. |
| [FreeDeviceProc](dos-list.md#freedeviceproc) | -648 | dp=D1 | Release a DevProc from GetDeviceProc along with any temporary locks it holds. |
| [FreeDosEntry](dos-list.md#freedosentry) | -702 | dlist=D1 | Free a DosList node that came from MakeDosEntry. |
| [FreeDosObject](objects.md#freedosobject) | -234 | type=D1, ptr=D2 | Free an object obtained from AllocDosObject(). |
| [FWrite](buffered-io.md#fwrite) | -330 | fh=D1, block=D2, blocklen=D3, number=D4 | Write a number of fixed-size blocks through the handle's buffer. |
| [GetArgStr](processes.md#getargstr) | -534 | none | Return the argument string the current program was started with. |
| [GetConsoleTask](processes.md#getconsoletask) | -510 | none | Return the process's default console handler port (`pr_ConsoleTask`). |
| [GetCurrentDirName](processes.md#getcurrentdirname) | -564 | buf=D1, len=D2 | Copy the current directory name kept in the CLI structure into a buffer. |
| [GetDeviceProc](dos-list.md#getdeviceproc) | -642 | name=D1, dp=D2 | Resolve a path to the handler port and directory lock to send packets to. |
| [GetFileSysTask](processes.md#getfilesystask) | -522 | none | Return the process's default filesystem handler port (`pr_FileSystemTask`). |
| [GetProgramDir](processes.md#getprogramdir) | -600 | none | Return a shared lock on the directory the running program was loaded from (PROGDIR:). |
| [GetProgramName](processes.md#getprogramname) | -576 | buf=D1, len=D2 | Copy the current command name from the CLI structure into a buffer. |
| [GetPrompt](processes.md#getprompt) | -588 | buf=D1, len=D2 | Copy the shell prompt string from the CLI structure into a buffer. |
| [GetVar](variables.md#getvar) | -906 | name=D1, buffer=D2, size=D3, flags=D4 | Copy the value of a local or global variable into a buffer. |
| [Info](locks-and-directories.md#info) | -114 | lock=D1, parameterBlock=D2 | Fill an InfoData block with size, usage and state of the volume holding a lock. |
| [Inhibit](dos-list.md#inhibit) | -726 | name=D1, onoff=D2 | Stop (or restart) all activity of a filesystem, e.g. |
| [Input](files.md#input) | -54 | none | Return the process's current default input file handle. |
| [InternalLoadSeg](loading.md#internalloadseg) | -756 | fh=D0, table=A0, funcarray=A1, stack=A2 | Load a hunk file from an open handle using caller-supplied read, alloc and free functions. |
| [InternalUnLoadSeg](loading.md#internalunloadseg) | -762 | seglist=D1, freefunc=A1 | Free a seglist from InternalLoadSeg() using a caller-supplied free function. |
| [IoErr](errors.md#ioerr) | -132 | none | Return the secondary result (usually the error code) of the last DOS call. |
| [IsFileSystem](dos-list.md#isfilesystem) | -708 | name=D1 | Ask whether a DOS device is a filesystem (stores separate files) or a stream handler. |
| [IsInteractive](files.md#isinteractive) | -216 | file=D1 | Tell whether a file handle is connected to a console (virtual terminal). |
| [LoadSeg](loading.md#loadseg) | -150 | name=D1 | Load and relocate an executable (hunk) file into memory and return its seglist. |
| [Lock](locks-and-directories.md#lock) | -84 | name=D1, type=D2 | Obtain a shared or exclusive filing-system lock on a named file or directory. |
| [LockDosList](dos-list.md#lockdoslist) | -654 | flags=D1 | Lock the DOS list for walking or modification, blocking until it is free. |
| [LockRecord](notification-and-locking.md#lockrecord) | -270 | fh=D1, offset=D2, length=D3, mode=D4, timeout=D5 | Lock a byte range of an open file, shared or exclusive, waiting up to a timeout. |
| [LockRecords](notification-and-locking.md#lockrecords) | -276 | recArray=D1, timeout=D2 | Lock several records described by a RecordLock array. |
| [MakeDosEntry](dos-list.md#makedosentry) | -696 | name=D1, type=D2 | Allocate a zeroed DosList node with its name and type filled in. |
| [MakeLink](locks-and-directories.md#makelink) | -444 | name=D1, dest=D2, soft=D3 | Create a hard link (to a locked object) or a soft link (to a path string). |
| [MatchEnd](paths-and-names.md#matchend) | -834 | anchor=D1 | Free all locks and memory attached to an AnchorPath by MatchFirst/MatchNext. |
| [MatchFirst](paths-and-names.md#matchfirst) | -822 | pat=D1, anchor=D2 | Start a wildcard search on disk and return the first matching file or directory. |
| [MatchNext](paths-and-names.md#matchnext) | -828 | anchor=D1 | Continue a MatchFirst search and return the next matching object. |
| [MatchPattern](paths-and-names.md#matchpattern) | -846 | pat=D1, str=D2 | Test a string against a pattern tokenized by ParsePattern (case-sensitive). |
| [MatchPatternNoCase](paths-and-names.md#matchpatternnocase) | -972 | pat=D1, str=D2 | Test a string against a pattern tokenized by ParsePatternNoCase (case-insensitive). |
| [MaxCli](processes.md#maxcli) | -552 | none | Return the highest CLI number that may currently be in use. |
| [NameFromFH](files.md#namefromfh) | -408 | fh=D1, buffer=D2, len=D3 | Copy the full path name of an open file into a buffer. |
| [NameFromLock](locks-and-directories.md#namefromlock) | -402 | lock=D1, buffer=D2, len=D3 | Build the full path (`Volume:dir/name`) of a locked object into a buffer. |
| [NewLoadSeg](loading.md#newloadseg) (alias: NewLoadSegTagList, NewLoadSegTags) | -768 | file=D1, tags=D2 | LoadSeg() with a tag list for extra options (no tags are defined). |
| [NextDosEntry](dos-list.md#nextdosentry) | -690 | dlist=D1, flags=D2 | Step to the next DOS list entry whose type matches the flags. |
| [Open](files.md#open) | -30 | name=D1, accessMode=D2 | Open a file, device or console window and return a file handle. |
| [OpenFromLock](files.md#openfromlock) | -378 | lock=D1 | Turn a lock into an open file handle on the same object. |
| [Output](files.md#output) | -60 | none | Return the process's current default output file handle. |
| [ParentDir](locks-and-directories.md#parentdir) | -210 | lock=D1 | Get a new lock on the directory containing a file or directory. |
| [ParentOfFH](files.md#parentoffh) | -384 | fh=D1 | Get a shared lock on the directory that contains an open file. |
| [ParsePattern](paths-and-names.md#parsepattern) | -840 | pat=D1, buf=D2, buflen=D3 | Tokenize a wildcard pattern for the case-sensitive MatchPattern. |
| [ParsePatternNoCase](paths-and-names.md#parsepatternnocase) | -966 | pat=D1, buf=D2, buflen=D3 | Tokenize a wildcard pattern for the case-insensitive MatchPatternNoCase. |
| [PathPart](paths-and-names.md#pathpart) | -876 | path=D1 | Return a pointer just past the directory portion of a path, where the file part begins. |
| [PrintFault](errors.md#printfault) | -474 | code=D1, header=D2 | Print "header: message" for an error code to Output() using buffered I/O. |
| [PutStr](buffered-io.md#putstr) | -948 | str=D1 | Write a null-terminated string to the default output, buffered (no newline added). |
| [Read](files.md#read) | -42 | file=D1, buffer=D2, length=D3 | Read up to length bytes from a file into a buffer, unbuffered. |
| [ReadArgs](arguments.md#readargs) | -798 | arg_template=D1, array=D2, args=D3 | Parse the command line (or a string) against a template into an array of LONGs. |
| [ReadItem](arguments.md#readitem) | -810 | name=D1, maxchars=D2, cSource=D3 | Read one whitespace/quote/`=`-delimited word from Input() or a CSource. |
| [ReadLink](locks-and-directories.md#readlink) | -438 | port=D1, lock=D2, path=D3, buffer=D4, size=D5 | Ask a filesystem to expand a soft link met while resolving a path. |
| [Relabel](dos-list.md#relabel) | -720 | drive=D1, newname=D2 | Rename a volume, if the filesystem supports it. |
| [RemAssignList](dos-list.md#remassignlist) | -636 | name=D1, lock=D2 | Remove one directory from a multi-directory assign. |
| [RemDosEntry](dos-list.md#remdosentry) | -672 | dlist=D1 | Unlink an entry from the DOS list without freeing it. |
| [RemSegment](loading.md#remsegment) | -786 | seg=D1 | Remove a resident segment from the DOS resident list and unload it. |
| [Rename](files.md#rename) | -78 | oldName=D1, newName=D2 | Rename a file or directory, optionally moving it to another directory on the same volume. |
| [ReplyPkt](packets.md#replypkt) | -258 | dp=D1, res1=D2, res2=D3 | Return a packet to its sender with both result fields set (handler side). |
| [RunCommand](processes.md#runcommand) | -504 | seg=D1, stack=D2, paramptr=D3, paramlen=D4 | Run a loaded seglist as a command on the calling process, with a newly allocated stack. |
| [SameDevice](locks-and-directories.md#samedevice) | -984 | lock1=D1, lock2=D2 | Tell whether two locks live on partitions of the same physical device. |
| [SameLock](locks-and-directories.md#samelock) | -420 | lock1=D1, lock2=D2 | Compare two locks: same object, same volume, or different volumes. |
| [Seek](files.md#seek) | -66 | file=D1, position=D2, offset=D3 | Move the read/write position of a file and return the previous position. |
| [SelectInput](files.md#selectinput) | -294 | fh=D1 | Make a file handle the process's default input and return the previous one. |
| [SelectOutput](files.md#selectoutput) | -300 | fh=D1 | Make a file handle the process's default output and return the previous one. |
| [SendPkt](packets.md#sendpkt) | -246 | dp=D1, port=D2, replyport=D3 | Send an initialised packet to a handler and return immediately (asynchronous). |
| [SetArgStr](processes.md#setargstr) | -540 | string=D1 | Replace the argument string returned by GetArgStr(); restore the old one before exit. |
| [SetComment](files.md#setcomment) | -180 | name=D1, comment=D2 | Attach a comment string (file note) to a file or directory. |
| [SetConsoleTask](processes.md#setconsoletask) | -516 | task=D1 | Set the process's default console handler port (`pr_ConsoleTask`). |
| [SetCurrentDirName](processes.md#setcurrentdirname) | -558 | name=D1 | Set the directory name kept in the CLI structure (does not change the current directory). |
| [SetFileDate](files.md#setfiledate) | -396 | name=D1, date=D2 | Set the modification date stamp of a file or directory. |
| [SetFileSize](files.md#setfilesize) | -456 | fh=D1, pos=D2, mode=D3 | Truncate or extend an open file to a new size. |
| [SetFileSysTask](processes.md#setfilesystask) | -528 | task=D1 | Set the process's default filesystem handler port (`pr_FileSystemTask`). |
| [SetIoErr](errors.md#setioerr) | -462 | result=D1 | Set the value that the next IoErr() will return. |
| [SetMode](files.md#setmode) | -426 | fh=D1, mode=D2 | Switch a console handler between cooked (CON:) and raw (RAW:) mode. |
| [SetOwner](files.md#setowner) | -996 | name=D1, owner_info=D2 | Store owner user and group IDs on a file or directory (for network filesystems). |
| [SetProgramDir](processes.md#setprogramdir) | -594 | lock=D1 | Set the lock returned by GetProgramDir() and used to resolve PROGDIR:. |
| [SetProgramName](processes.md#setprogramname) | -570 | name=D1 | Set the command name stored in the CLI structure. |
| [SetPrompt](processes.md#setprompt) | -582 | name=D1 | Set the shell prompt string in the CLI structure. |
| [SetProtection](files.md#setprotection) | -186 | name=D1, protect=D2 | Set the protection bits of a file or directory. |
| [SetVar](variables.md#setvar) | -900 | name=D1, buffer=D2, size=D3, flags=D4 | Create or replace a local or global variable. |
| [SetVBuf](buffered-io.md#setvbuf) | -366 | fh=D1, buff=D2, type=D3, size=D4 | Change the buffering mode and/or buffer size of a file handle. |
| [SplitName](paths-and-names.md#splitname) | -414 | name=D1, separator=D2, buf=D3, oldpos=D4, size=D5 | Copy the next separator-delimited component of a path into a buffer (handler helper). |
| [StartNotify](notification-and-locking.md#startnotify) | -888 | notify=D1 | Ask the filesystem to report changes to a file or directory. |
| [StrToDate](time.md#strtodate) | -750 | datetime=D1 | Parse date and/or time strings into the DateStamp inside a DateTime. |
| [StrToLong](arguments.md#strtolong) | -816 | string=D1, value=D2 | Convert leading decimal text to a LONG. |
| [SystemTagList](processes.md#systemtaglist) (alias: System, SystemTags) | -606 | command=D1, tags=D2 | Run a command line through a new shell process and return the command's return code. |
| [UnGetC](buffered-io.md#ungetc) | -318 | fh=D1, character=D2 | Push a character back so the next buffered read returns it again. |
| [UnLoadSeg](loading.md#unloadseg) | -156 | seglist=D1 | Free a seglist loaded by LoadSeg(), closing overlay files if needed. |
| [UnLock](locks-and-directories.md#unlock) | -90 | lock=D1 | Release a lock obtained from Lock, DupLock, CreateDir or ParentDir. |
| [UnLockDosList](dos-list.md#unlockdoslist) | -660 | flags=D1 | Release a DOS list lock taken by LockDosList or AttemptLockDosList. |
| [UnLockRecord](notification-and-locking.md#unlockrecord) | -282 | fh=D1, offset=D2, length=D3 | Release a record lock taken with LockRecord(). |
| [UnLockRecords](notification-and-locking.md#unlockrecords) | -288 | recArray=D1 | Release all record locks taken with LockRecords(). |
| [VFPrintf](buffered-io.md#vfprintf) (alias: FPrintf) | -354 | fh=D1, format=D2, argarray=D3 | Format values with RawDoFmt codes and write the text to a file handle, buffered. |
| [VFWritef](buffered-io.md#vfwritef) (alias: FWritef) | -348 | fh=D1, format=D2, argarray=D3 | Write BCPL-style formatted text to a file handle, buffered (legacy; prefer VFPrintf). |
| [VPrintf](buffered-io.md#vprintf) (alias: Printf) | -954 | format=D1, argarray=D2 | Format values with RawDoFmt codes and write the text to the default output, buffered. |
| [WaitForChar](files.md#waitforchar) | -204 | file=D1, timeout=D2 | Wait up to a timeout for a character to become available on a console handle. |
| [WaitPkt](packets.md#waitpkt) | -252 | none | Wait for a packet to arrive at the process's pr_MsgPort and return it, already removed. |
| [Write](files.md#write) | -48 | file=D1, buffer=D2, length=D3 | Write length bytes from a buffer to a file, unbuffered. |
| [WriteChars](buffered-io.md#writechars) | -942 | buf=D1, buflen=D2 | Write a counted run of bytes to the default output, buffered. |

Machine-readable: [../data/dos.tsv](../data/dos.tsv)
