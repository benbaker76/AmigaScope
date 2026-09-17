# intuition.library: time, preferences, memory and internals

The odds and ends. **CurrentTime** and **DoubleClick** give coarse timestamps and double-click tests;
IntuiMessages already carry `Seconds`/`Micros` for the latter. **GetPrefs**/**GetDefPrefs**/**SetPrefs**
read and write the old 1.x `struct Preferences`. Since V36 most settings come from IPrefs and ENV:
files, so treat that structure as read-mostly. **AllocRemember**/**FreeRemember** are a simple
allocation tracker. **SetEditHook** installs a global string-gadget edit hook. **OpenIntuition** and
**Intuition** are internal entry points you never call.

## CurrentTime
`VOID CurrentTime(ULONG *seconds, ULONG *micros)` — LVO -84 (-$54)
Registers: seconds=A0, micros=A1; no result

Read Intuition's current time as seconds plus microseconds.

- **seconds** — pointer to a ULONG that receives the seconds.
- **micros** — pointer to a ULONG that receives the microseconds.

### Gotchas
- Coarse. It is updated at most 60 times a second and often less. Use timer.device (`TR_GETSYSTIME`)
  for real timing.

**See also:** [DoubleClick](#doubleclick), [IntuiMessage fields](concepts.md#intuimessage-fields)

## DoubleClick
`BOOL DoubleClick(ULONG sSeconds, ULONG sMicros, ULONG cSeconds, ULONG cMicros)` — LVO -102 (-$66)
Registers: sSeconds=D0, sMicros=D1, cSeconds=D2, cMicros=D3; result in D0

Test whether two timestamps are close enough to count as a double-click.

- **sSeconds**, **sMicros** — time of the first click.
- **cSeconds**, **cMicros** — time of the second click.
- **Result** — TRUE if the gap is within the user's Preferences double-click interval.

### Example
```c
static ULONG lastSecs, lastMicros;

/* inside the IDCMP loop, after copying the message fields */
if (class == IDCMP_MOUSEBUTTONS && code == SELECTDOWN) {
    if (DoubleClick(lastSecs, lastMicros, secs, micros)) {
        /* double-click: also check the pointer is still on the same item */
    }
    lastSecs = secs;
    lastMicros = micros;
}
```

### Gotchas
- It only compares times. Checking that both clicks hit the same object is up to you.
- Take the times from `IntuiMessage->Seconds`/`Micros` (copied before ReplyMsg), not from
  CurrentTime() when you process the message.

**See also:** [CurrentTime](#currenttime), [The IDCMP loop](concepts.md#the-idcmp-loop)

## GetPrefs
`struct Preferences * GetPrefs(struct Preferences *preferences, LONG size)` — LVO -132 (-$84)
Registers: preferences=A0, size=D0; result in D0

Copy the current Intuition Preferences structure (or its first part) into your buffer.

- **preferences** — buffer that receives the copy.
- **size** — bytes to copy. Partial copies are legal; the most used fields (`FontHeight`,
  `PrinterPort`, `BaudRate`, `KeyRptSpeed`, `KeyRptDelay`, `DoubleClick`, ...) come first. Use
  `sizeof(struct Preferences)` for all of it.
- **Result** — `preferences` (your buffer).

### Gotchas
- V36+: preferences come from IPrefs and many newer settings cannot be expressed in this structure,
  so the copy is only an approximation of the real state.
- Include `<intuition/preferences.h>` (pulled in by `intuition/intuition.h`).

**See also:** [GetDefPrefs](#getdefprefs), [SetPrefs](#setprefs)

## GetDefPrefs
`struct Preferences * GetDefPrefs(struct Preferences *preferences, LONG size)` — LVO -126 (-$7E)
Registers: preferences=A0, size=D0; result in D0

Copy Intuition's built-in default Preferences (used when no preferences file exists).

- **preferences** — buffer that receives the copy.
- **size** — bytes to copy. A partial copy is legal.
- **Result** — `preferences`.

**See also:** [GetPrefs](#getprefs), [SetPrefs](#setprefs)

## SetPrefs
`struct Preferences * SetPrefs(CONST struct Preferences *preferences, LONG size, LONG inform)` — LVO -324 (-$144)
Registers: preferences=A0, size=D0, inform=D1; result in D0

Install new Intuition Preferences, optionally notifying windows with IDCMP_NEWPREFS.

- **preferences** — buffer holding the new settings.
- **size** — number of leading bytes to install. A partial structure is legal.
- **inform** — TRUE: send `IDCMP_NEWPREFS` to every window that asked for it.
- **Result** — `preferences`.

### Gotchas
- For preference editors only. Applications must not override the user's settings.
- Many fields are ignored now. Pointer changes are honoured only until IPrefs sends a V36-style
  pointer (V39+: only the one from `devs:system-configuration`). V39+ palette changes are ignored after
  IPrefs sets new-style colours. `FontHeight` and `LaceWB` come only from `devs:system-configuration`.
  `ViewXOffset`/`ViewYOffset` and the size changes apply only to the default NTSC/PAL monitor.
- Always GetPrefs() first and change only the fields you mean. Writing back a stale full copy can
  truncate extended data.

**See also:** [GetPrefs](#getprefs), [GetDefPrefs](#getdefprefs)

## SetEditHook
`struct Hook * SetEditHook(struct Hook *hook)` — LVO -492 (-$1EC)
Registers: hook=A0; result in D0

Install a global edit hook that sees every keystroke typed into any string gadget.

- **hook** — `struct Hook` (utility/hooks.h). It is called before any per-gadget
  `StringExtend->EditHook` and receives `SGH_KEY` commands with a `struct SGWork` (intuition/sghooks.h).
- **Result** — the previous global hook. Call it for keys you do not handle yourself.

Since V36.

### Gotchas
- The autodoc calls it risky and says not to use it in commercial products. It affects every
  string gadget in the system.
- Only `SGH_KEY` reaches the global hook (per-gadget hooks also get `SGH_CLICK`). Most gadgets have no
  WorkBuffer, so once you call the old hook its effect cannot easily be undone.
- Set `SGA_REDISPLAY` in `SGWork->Actions` when the visuals change and put a meaningful `EO_` value in
  `SGWork->EditOp`. Nothing arbitrates keys between the global hook and a gadget's custom hook.

**See also:** utility.library CallHookPkt

## AllocRemember
`APTR AllocRemember(struct Remember **rememberKey, ULONG size, ULONG flags)` — LVO -396 (-$18C)
Registers: rememberKey=A0, size=D0, flags=D1; result in D0

AllocMem() that also records the block in a Remember list so it can be freed in one call.

- **rememberKey** — address of your `struct Remember *` anchor. Set the anchor to NULL before the first call.
- **size** — bytes wanted (as exec AllocMem).
- **flags** — `MEMF_` requirement flags (`MEMF_CHIP`, `MEMF_FAST`, `MEMF_CLEAR`, ...).
- **Result** — the block, or NULL. On failure the list is unchanged.

### Example
```c
struct Remember *rkey = NULL;

UBYTE *planes = AllocRemember(&rkey, 40 * 256, MEMF_CHIP | MEMF_CLEAR);
UBYTE *table  = AllocRemember(&rkey, 4096, MEMF_ANY);
if (planes && table) {
    /* ... use them ... */
}
FreeRemember(&rkey, TRUE);      /* frees every block and every node */
```

### Gotchas
- Each call makes two allocations (your block and a `struct Remember` node): slow and fragmenting.
  exec memory pools (CreatePool/AllocPooled, V39) do the same job better.
- Not for use from interrupts (it calls AllocMem).
- Bartman gcc 15 with `proto/intuition.h`: the inline macro copies the `struct Remember **` argument
  into a `volatile struct Remember **` register variable, which is an incompatible-pointer-types
  **error** (checked by compiling). Add `-Wno-error=incompatible-pointer-types` for that file, or use
  exec AllocVec/pools instead. FreeRemember has the same problem.

**See also:** [FreeRemember](#freeremember), exec.library AllocMem

## FreeRemember
`VOID FreeRemember(struct Remember **rememberKey, LONG reallyForget)` — LVO -408 (-$198)
Registers: rememberKey=A0, reallyForget=D0; no result

Free a Remember list: either the nodes and all the blocks, or only the nodes.

- **rememberKey** — address of the anchor (an empty/NULL list is fine).
- **reallyForget** — TRUE: free all blocks and all nodes. FALSE: free only the tracking nodes, and the
  blocks become yours to FreeMem().

### Gotchas
- After a FALSE call the links are gone. You must free each block yourself, with its size.
- Does not compile as-is with Bartman gcc 15 inline headers; see [AllocRemember](#allocremember).

**See also:** [AllocRemember](#allocremember), exec.library FreeMem

## OpenIntuition
`VOID OpenIntuition(VOID)` — LVO -30 (-$1E)
Registers: none; no result

Internal Intuition initialisation vector; never call it.

- The NDK clib header says it is intentionally undocumented. There is no autodoc. Just open
  `intuition.library` with exec OpenLibrary().

Source: NDK 3.9 includes (no autodoc in the source set).

**See also:** [index](index.md)

## Intuition
`VOID Intuition(struct InputEvent *iEvent)` — LVO -36 (-$24)
Registers: iEvent=A0; no result

Internal Intuition entry that takes an InputEvent pointer; never call it.

- **iEvent** — `struct InputEvent *` (devices/inputevent.h).
- Intentionally undocumented, like OpenIntuition. It is presumably Intuition's input-event entry
  (unverified). To inject input, send `IND_WRITEEVENT` to input.device (or use commodities.library)
  so the event goes through the normal handler chain.

Source: NDK 3.9 includes (no autodoc in the source set).

**See also:** [OpenIntuition](#openintuition)
