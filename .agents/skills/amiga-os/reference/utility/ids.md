# utility.library: unique IDs

One system-wide counter that hands out 32-bit values no other caller gets. The OS uses it for
IDs that must not collide between programs, such as Intuition's gadget-help group IDs
(`WA_HelpGroup`, `HelpControl`).

## GetUniqueID
`ULONG GetUniqueID(VOID)` — LVO -270 (-$10E)
Registers: none; result in D0

Return a 32-bit number that no other GetUniqueID call in this session has returned.

- **Result** — the new ID; unique until the counter wraps after 4,294,967,295 calls.

Safe to call from interrupts (autodoc). Since V39.

### Example
```c
#include <proto/utility.h>
#include <proto/intuition.h>
#include <intuition/intuition.h>

extern struct UtilityBase *UtilityBase;

/* all windows of this program share one gadget-help group */
static ULONG helpGroup;

struct Window *OpenToolWindow(struct Screen *scr)
{
    if (helpGroup == 0)
        helpGroup = GetUniqueID();
    return OpenWindowTags(NULL,
        WA_PubScreen, (ULONG)scr,
        WA_Width,     200,
        WA_Height,    100,
        WA_HelpGroup, helpGroup,
        TAG_DONE);
}
```

### Gotchas
- V39+: check `UtilityBase->ub_LibNode.lib_Version >= 39` before calling.
- Never invent your own "unique" group IDs for OS features that expect this call.

**See also:** intuition.library HelpControl
