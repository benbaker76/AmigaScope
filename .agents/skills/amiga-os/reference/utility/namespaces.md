# utility.library: named objects and namespaces

V39 namespaces are lists of `struct NamedObject`s that tasks can share and look up by name, with
use counts so an object cannot vanish while someone holds it. An object allocated with
`ANO_NameSpace` carries its own namespace, so trees can be built; passing NULL as the namespace
means the system's root namespace. Life cycle: [AllocNamedObjectA](#allocnamedobjecta) ->
[AddNamedObject](#addnamedobject) -> others [FindNamedObject](#findnamedobject) /
[ReleaseNamedObject](#releasenamedobject) -> [AttemptRemNamedObject](#attemptremnamedobject) or
[RemNamedObject](#remnamedobject) -> [FreeNamedObject](#freenamedobject).

`struct NamedObject` (utility/name.h, name.i) has one public field, `no_Object` (APTR, offset 0):
yours to use, or pointing at the user space requested with `ANO_UserSpace`. Name, use count
and list links are private.

Tags and flags (utility/name.h; note these tags are small numbers, not `TAG_USER` based):

| Name | Value | Meaning |
|---|---|---|
| `ANO_NameSpace` | 4000 | BOOL, default FALSE: attach a namespace to the object |
| `ANO_UserSpace` | 4001 | ULONG, default 0: bytes of long-aligned user memory; `no_Object` points to it (else NULL) |
| `ANO_Priority` | 4002 | BYTE, default 0: priority when enqueued in a namespace |
| `ANO_Flags` | 4003 | ULONG, default 0: flags of the attached namespace |
| `NSF_NODUPS` (bit `NSB_NODUPS` 0) | 1 | names in this namespace must be unique |
| `NSF_CASE` (bit `NSB_CASE` 1) | 2 | names in this namespace are case sensitive |

No other `ANO_Flags` bits may be set.

## AllocNamedObjectA
`struct NamedObject * AllocNamedObjectA(CONST_STRPTR name, CONST struct TagItem *tagList)` — LVO -228 (-$E4)
Registers: name=A0, tagList=A1; result in D0

Allocate a NamedObject with a name, optional user memory and optional child namespace.

- **name** — object name; must not be NULL.
- **tagList** — `ANO_` tags from the table above, or NULL.
- **Result** — the new object, or NULL on failure. It starts with ONE use, held by you.

Varargs form: `AllocNamedObject(name, tag1, ...)` (inline macro in Bartman's headers; asm calls
the A form). Since V39.

### Example
```c
#include <proto/exec.h>
#include <proto/utility.h>
#include <utility/name.h>
#include <utility/tagitem.h>

extern struct UtilityBase *UtilityBase;

struct HiScore { ULONG points; };

/* private namespace with unique names, holding one object with user data */
BOOL NameSpaceDemo(void)
{
    struct NamedObject *space, *obj, *found;
    BOOL ok = FALSE;

    space = AllocNamedObject((CONST_STRPTR)"MyGame.space",
                             ANO_NameSpace, TRUE,
                             ANO_Flags,     NSF_NODUPS,
                             TAG_DONE);
    if (space == NULL)
        return FALSE;

    obj = AllocNamedObject((CONST_STRPTR)"hiscore",
                           ANO_UserSpace, sizeof(struct HiScore),
                           TAG_DONE);
    if (obj != NULL) {
        ((struct HiScore *)obj->no_Object)->points = 0;
        if (AddNamedObject(space, obj)) {
            found = FindNamedObject(space, (CONST_STRPTR)"HISCORE", NULL);  /* caseless */
            if (found != NULL) {
                ((struct HiScore *)found->no_Object)->points += 100;
                ReleaseNamedObject(found);          /* one release per find */
                ok = TRUE;
            }
            if (AttemptRemNamedObject(obj))         /* uses the allocation's use count */
                FreeNamedObject(obj);
        } else {
            FreeNamedObject(obj);                   /* never added */
        }
    }
    FreeNamedObject(space);                         /* its namespace must be empty by now */
    return ok;
}
```

### Gotchas
- The autodoc does not say whether `name` is copied into the object: keep the string valid for the
  object's lifetime unless you know otherwise.
- To let OTHER tasks remove an object you added, give up your initial use with
  [ReleaseNamedObject](#releasenamedobject).

**See also:** [FreeNamedObject](#freenamedobject), [AddNamedObject](#addnamedobject)

## AddNamedObject
`BOOL AddNamedObject(struct NamedObject *nameSpace, struct NamedObject *object)` — LVO -222 (-$DE)
Registers: nameSpace=A0, object=A1; result in D0

Insert a NamedObject into a namespace, by priority.

- **nameSpace** — object that carries the namespace (allocated with `ANO_NameSpace`), or NULL for
  the root namespace.
- **object** — object to add; NULL makes the call fail.
- **Result** — TRUE on success; FALSE if `NSF_NODUPS` is set and the name already exists. ALWAYS
  check it (autodoc). BOOL: test the low word.

Since V39.

**See also:** [AttemptRemNamedObject](#attemptremnamedobject), [RemNamedObject](#remnamedobject), [FindNamedObject](#findnamedobject)

## FindNamedObject
`struct NamedObject * FindNamedObject(struct NamedObject *nameSpace, CONST_STRPTR name, struct NamedObject *lastObject)` — LVO -240 (-$F0)
Registers: nameSpace=A0, name=A1, lastObject=A2; result in D0

Find the next object with a name in a namespace and take a use count on it.

- **nameSpace** — object carrying the namespace, or NULL for the root namespace.
- **name** — name to match; NULL matches every object. Matching is caseless, using the locale
  string comparison (autodoc).
- **lastObject** — NULL to start at the beginning, or an object from a previous call on the same
  namespace to continue after it. This call does not release it.
- **Result** — first match, or NULL. The object cannot be freed until you call
  [ReleaseNamedObject](#releasenamedobject) on it.

Since V39.

### Gotchas
- Every non-NULL result needs exactly one ReleaseNamedObject, including the ones you only used as
  `lastObject` for the next search: release the previous object AFTER the next call returns.
- The autodoc says the comparison is always caseless, while `NSF_CASE` makes a namespace case
  sensitive; which wins is not documented (unverified).

**See also:** [ReleaseNamedObject](#releasenamedobject), [NamedObjectName](#namedobjectname)

## NamedObjectName
`STRPTR NamedObjectName(struct NamedObject *object)` — LVO -252 (-$FC)
Registers: object=A0; result in D0

Return a read-only pointer to a NamedObject's name.

- **object** — the object, or NULL.
- **Result** — the name, or NULL if `object` was NULL.

Since V39.

### Gotchas
- The string belongs to the object: do not modify it, and do not use it after the object is gone
  (copy it while you hold a use count).

**See also:** [FindNamedObject](#findnamedobject)

## ReleaseNamedObject
`VOID ReleaseNamedObject(struct NamedObject *object)` — LVO -258 (-$102)
Registers: object=A0; no result

Give back one use count taken by FindNamedObject or AllocNamedObjectA.

- **object** — the object, or NULL (no action).

Since V39.

If the object has been removed with [RemNamedObject](#remnamedobject) and this was the last use,
the remover's message is replied now.

**See also:** [FindNamedObject](#findnamedobject), [RemNamedObject](#remnamedobject)

## AttemptRemNamedObject
`LONG AttemptRemNamedObject(struct NamedObject *object)` — LVO -234 (-$EA)
Registers: object=A0; result in D0

Remove an object from its namespace now, unless someone else is using it.

- **object** — a valid object you hold a use count on (found, or still holding the allocation's use).
- **Result** — TRUE: removed, you may [FreeNamedObject](#freenamedobject) it. FALSE: still in use
  elsewhere or already being removed.

Since V39.

### Gotchas
- The autodoc does not say what happens to your use count when the result is FALSE (unverified);
  retry later or use [RemNamedObject](#remnamedobject), which waits for the other users.

**See also:** [RemNamedObject](#remnamedobject), [AddNamedObject](#addnamedobject), [ReleaseNamedObject](#releasenamedobject)

## RemNamedObject
`VOID RemNamedObject(struct NamedObject *object, struct Message *message)` — LVO -264 (-$108)
Registers: object=A0, message=A1; no result

Ask for an object to be removed and get a message replied once it is gone.

- **object** — a valid object you hold a use count on; the call releases that use for you.
- **message** — a `struct Message` with `mn_ReplyPort` set (required). When removal is complete it
  is ReplyMsg'd with `mn_Node.ln_Name` = the object pointer, or NULL if another task removed the
  object first.

Since V39.

After the reply with a non-NULL `ln_Name` the object is out of the namespace and can be freed with
[FreeNamedObject](#freenamedobject).

### Gotchas
- Wait for the reply (WaitPort/GetMsg on the reply port) before freeing the object or the message.
- Do not ReleaseNamedObject the object yourself afterwards: this call already did.

**See also:** [AttemptRemNamedObject](#attemptremnamedobject), [ReleaseNamedObject](#releasenamedobject)

## FreeNamedObject
`VOID FreeNamedObject(struct NamedObject *object)` — LVO -246 (-$F6)
Registers: object=A0; no result

Free a NamedObject, its user space and its (empty) namespace.

- **object** — object from [AllocNamedObjectA](#allocnamedobjecta). It must not be in any
  namespace, nobody but you may have it open, and a namespace it carries must be empty.

Since V39.

**See also:** [AllocNamedObjectA](#allocnamedobjecta), [AttemptRemNamedObject](#attemptremnamedobject)
