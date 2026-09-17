# dos.library: environment variables

DOS has two kinds of variables. **Local** variables (and shell aliases) live in the calling
process's `pr_LocalVars` list and die with it; **global** variables are files in `ENV:`, and
with `GVF_SAVE_VAR` (V39+) also in `ENVARC:`. Only type `LV_VAR` can be global. Names follow
filesystem syntax (a `/` in a global name is a subdirectory of ENV:). All four calls are V36+.

Type and flag values (`dos/var.h`), OR the flags into the type:

| Name | Value | Meaning |
|---|---|---|
| `LV_VAR` | 0 | ordinary variable |
| `LV_ALIAS` | 1 | shell alias (local only) |
| `LVF_IGNORE` | 0x80 | in `lv_Node.ln_Type`: entry ignored by GetVar etc. |
| `GVF_GLOBAL_ONLY` | 0x100 | only look at / act on ENV: |
| `GVF_LOCAL_ONLY` | 0x200 | only look at / act on the process list |
| `GVF_BINARY_VAR` | 0x400 | GetVar: do not stop at `'\n'` |
| `GVF_DONT_NULL_TERM` | 0x800 | GetVar: no NUL terminator (only with GVF_BINARY_VAR) |
| `GVF_SAVE_VAR` | 0x1000 | SetVar: also write ENVARC: (V39+, with GVF_GLOBAL_ONLY) |

## GetVar
`LONG GetVar(CONST_STRPTR name, STRPTR buffer, LONG size, LONG flags)` — LVO -906 (-$38A)
Registers: name=D1, buffer=D2, size=D3, flags=D4; result in D0

Copy the value of a local or global variable into a buffer.

- **name** — variable name.
- **buffer** — receives the value; NUL-terminated unless `GVF_DONT_NULL_TERM`.
- **size** — buffer size in bytes; must not be 0.
- **flags** — type (`LV_VAR`/`LV_ALIAS`) OR `GVF_GLOBAL_ONLY` / `GVF_LOCAL_ONLY` /
  `GVF_BINARY_VAR` / `GVF_DONT_NULL_TERM`. Default search: local first, then global.
- **Result** — characters stored (not counting the NUL), with `IoErr()` = full length of the
  variable; or -1 if not defined (`IoErr()` = `ERROR_OBJECT_NOT_FOUND`; `ERROR_BAD_NUMBER` for
  size 0). Too-small buffers are truncated, not an error.

Since V36.

### Example
```c
char value[64];
STRPTR level = (STRPTR)"normal";            /* default */
LONG len = GetVar("MyGame/Difficulty", value, sizeof(value), GVF_GLOBAL_ONLY);
if (len >= 0) {
    level = (STRPTR)value;
    if (IoErr() > len) {
        /* value was truncated to sizeof(value)-1 characters */
    }
}
```

### Gotchas
- Without `GVF_BINARY_VAR` the copy stops at the first `'\n'` (the newline is not stored).
- V36 returned the variable's size instead of the characters copied; V37+ behaves as above.
- `GVF_DONT_NULL_TERM` works only for local variables under V37; V39 extends it to globals.
- Only `LV_VAR` can be global.

**See also:** [SetVar](#setvar), [DeleteVar](#deletevar), [FindVar](#findvar)

## SetVar
`BOOL SetVar(CONST_STRPTR name, CONST_STRPTR buffer, LONG size, LONG flags)` — LVO -900 (-$384)
Registers: name=D1, buffer=D2, size=D3, flags=D4; result in D0

Create or replace a local or global variable.

- **name** — variable name.
- **buffer** — value bytes.
- **size** — length of `buffer`, or -1 when `buffer` is a NUL-terminated string.
- **flags** — type OR `GVF_LOCAL_ONLY` / `GVF_GLOBAL_ONLY` (OR `GVF_SAVE_VAR` on V39+ to
  also write ENVARC:). The autodoc gives a local variable as the default.
- **Result** — non-zero on success, 0 on failure (IoErr set).

Since V36.

### Example
```c
/* persistent global: ENV:MyGameHiScore and, on V39+, ENVARC:MyGameHiScore */
if (!SetVar("MyGameHiScore", "12500", -1, GVF_GLOBAL_ONLY | GVF_SAVE_VAR))
    PrintFault(IoErr(), "SetVar");
```

### Gotchas
- Pass `GVF_GLOBAL_ONLY` explicitly for ENV: variables; the flag-less default is local.
- V37 ignores `GVF_SAVE_VAR`; only ENV: is written there.
- Only `LV_VAR` can be global.

**See also:** [GetVar](#getvar), [DeleteVar](#deletevar), [FindVar](#findvar)

## DeleteVar
`LONG DeleteVar(CONST_STRPTR name, ULONG flags)` — LVO -912 (-$390)
Registers: name=D1, flags=D2; result in D0

Delete a local or global variable.

- **name** — variable name.
- **flags** — type OR `GVF_LOCAL_ONLY` / `GVF_GLOBAL_ONLY`. Default: delete a local variable if
  one exists, otherwise a global one (`LV_VAR` only).
- **Result** — non-zero on success, 0 on failure.

Since V36.

**See also:** [GetVar](#getvar), [SetVar](#setvar), [FindVar](#findvar),
[DeleteFile](files.md#deletefile)

## FindVar
`struct LocalVar * FindVar(CONST_STRPTR name, ULONG type)` — LVO -918 (-$396)
Registers: name=D1, type=D2; result in D0

Find a local variable's LocalVar node in the current process's list.

- **name** — variable name.
- **type** — `LV_VAR` or `LV_ALIAS`.
- **Result** — `struct LocalVar *` or NULL. Fields: `lv_Node` (name in `ln_Name`, type in
  `ln_Type`), `lv_Flags` (free for application use), `lv_Value`, `lv_Len`.

Since V36.

### Gotchas
- Local variables only; globals are ENV: files, use GetVar.
- Never allocate or link a LocalVar yourself (the structure may grow); create entries with
  SetVar. Read the value with `lv_Len` rather than assuming a terminator.

**See also:** [GetVar](#getvar), [SetVar](#setvar), [DeleteVar](#deletevar)
