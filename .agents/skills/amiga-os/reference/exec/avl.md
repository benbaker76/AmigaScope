# exec.library: AVL trees

Balanced binary trees with O(log n) insert, remove and lookup, added in exec V45. Stock
Kickstart 3.1 ROMs carry exec V40, so test `SysBase->LibNode.lib_Version >= 45` before any
call. Embed a `struct AVLNode` (exec/avl.h: `ULONG reserved[4]`, 16 bytes, contents private)
anywhere inside your element and recover the element with `offsetof`. The tree is just a
`struct AVLNode *` root variable that starts as NULL; add/remove calls take the ADDRESS of that
variable, find calls take its value. Ordering comes entirely from your two callbacks:
AVLNODECOMP (A0 = node 1, A1 = node 2) and AVLKEYCOMP (A0 = node, A1 = key), both returning a
LONG <0 / 0 / >0 in D0 like strcmp. Keys must be unique, a key (`AVLKey`) is any 32-bit value,
the functions are not recursive, and nothing is arbitrated: guard shared trees with a
SignalSemaphore.

## AVL_AddNode
`struct AVLNode * AVL_AddNode(struct AVLNode **root, struct AVLNode *node, APTR func)` — LVO -852 (-$354)
Registers: root=A0, node=A1, func=A2; result in D0

Insert a node at the position chosen by the node comparison callback.

- **root** — address of the root pointer (`&root`). Set the root to NULL for an empty tree.
- **node** — the AVLNode embedded in the element to add.
- **func** — AVLNODECOMP callback: A0/A1 = the two nodes, return D0 <0/0/>0.
- **Result** — NULL when the node was added. If a node with an equal key is already in the
  tree, that node is returned and the new one is NOT added.

Since V45.

### Example
Element layout shared by the examples on this page (asm offsets match the C struct):

```c
#include <proto/exec.h>
#include <exec/avl.h>

/* Bartman inline/exec.h + GCC 14+: the struct AVLNode ** argument of AVL_AddNode,
   AVL_RemNodeByAddress and AVL_RemNodeByKey fails -Wincompatible-pointer-types */
#pragma GCC diagnostic ignored "-Wincompatible-pointer-types"

struct Element {
    ULONG          key;          /* offset 0 */
    struct AVLNode avl;          /* offset 4, 16 bytes */
    ULONG          data;         /* offset 20 */
};
/* offsetof: <stddef.h> or the Bartman template support header */
#define ELEMENT(n) ((struct Element *)((UBYTE *)(n) - offsetof(struct Element, avl)))

extern LONG NodeCmp(void);       /* asm callbacks below: args in A0/A1 */
extern LONG KeyCmp(void);

struct AVLNode *root = NULL;     /* empty tree */

BOOL AddElement(struct Element *el)
{
    if (SysBase->LibNode.lib_Version < 45)
        return FALSE;
    return AVL_AddNode(&root, &el->avl, (APTR)NodeCmp) == NULL;  /* FALSE = duplicate */
}
```

```asm
EL_KEY  equ     0
EL_AVL  equ     4
EL_DATA equ     20

        xdef    NodeCmp,KeyCmp          ; ELF C names have no leading underscore

; AVLNODECOMP: a0 = node1, a1 = node2 -> d0 = <0 / 0 / >0 (unsigned key order)
NodeCmp:
        move.l  EL_KEY-EL_AVL(a1),d1    ; key of node2
        bra.s   cmpkey

; AVLKEYCOMP: a0 = node, a1 = key value
KeyCmp:
        move.l  a1,d1
cmpkey:
        move.l  EL_KEY-EL_AVL(a0),d0    ; key of node (1)
        cmp.l   d1,d0
        bhi.s   .greater
        bcs.s   .less
        moveq   #0,d0
        rts
.greater:
        moveq   #1,d0
        rts
.less:
        moveq   #-1,d0
        rts
```

### Gotchas
- Passing `root` instead of `&root` corrupts memory.
- With Bartman's GCC (15.x) the inline macros for AVL_AddNode, AVL_RemNodeByAddress and
  AVL_RemNodeByKey add `volatile` to the `struct AVLNode **` type, which GCC 14+ rejects as an
  incompatible pointer. Silence it with the pragma shown (or
  `-Wno-error=incompatible-pointer-types`); the generated call is correct.
- Do not name your own functions after exec calls (`Insert`, `Remove`, `Wait`, ...): the
  inline headers define them as macros.
- Both callbacks must agree on the key; a flawed comparison breaks the tree silently.
- For duplicate keys, make them unique with a second-level key (for example compare the node
  addresses when the primary keys are equal); such entries can no longer be found by key alone.
- Do not compute the result as `key1 - key2` for full-range ULONG keys: the subtraction can
  overflow the sign. Compare and return -1/0/1 as above.
- Callbacks should preserve D2-D7/A2-A6 like any system callback (unverified).

**See also:** [AVL_FindNode](avl.md#avl_findnode),
[AVL_RemNodeByAddress](avl.md#avl_remnodebyaddress),
[AVL_RemNodeByKey](avl.md#avl_remnodebykey), [AVL_FindFirstNode](avl.md#avl_findfirstnode),
[AVL_FindNextNodeByAddress](avl.md#avl_findnextnodebyaddress)

## AVL_RemNodeByAddress
`struct AVLNode * AVL_RemNodeByAddress(struct AVLNode **root, struct AVLNode *node)` — LVO -858 (-$35A)
Registers: root=A0, node=A1; result in D0

Unlink a node that you already hold a pointer to.

- **root** — address of the root pointer.
- **node** — an AVLNode that is currently in this tree.
- **Result** — the removed node.

Since V45.

### Gotchas
- The node must really be in the tree; anything else corrupts memory.
- Freeing the element is up to you, after the call.

**See also:** [AVL_RemNodeByKey](avl.md#avl_remnodebykey), [AVL_AddNode](avl.md#avl_addnode),
[AVL_FindNextNodeByAddress](avl.md#avl_findnextnodebyaddress)

## AVL_RemNodeByKey
`struct AVLNode * AVL_RemNodeByKey(struct AVLNode **root, AVLKey key, APTR func)` — LVO -864 (-$360)
Registers: root=A0, key=A1, func=A2; result in D0

Find the node matching a key and unlink it.

- **root** — address of the root pointer.
- **key** — the key to look for (any 32-bit value your callback understands).
- **func** — AVLKEYCOMP callback: A0 = node, A1 = key, return D0 <0/0/>0.
- **Result** — the removed node, or NULL if no node matched.

Since V45.

### Example
```c
struct AVLNode *n = AVL_RemNodeByKey(&root, (AVLKey)1234, (APTR)KeyCmp);
if (n)
    FreeVec(ELEMENT(n));
```

**See also:** [AVL_RemNodeByAddress](avl.md#avl_remnodebyaddress),
[AVL_FindNode](avl.md#avl_findnode), [AVL_AddNode](avl.md#avl_addnode)

## AVL_FindNode
`struct AVLNode * AVL_FindNode(CONST struct AVLNode *root, AVLKey key, APTR func)` — LVO -870 (-$366)
Registers: root=A0, key=A1, func=A2; result in D0

Look up the node with exactly the given key.

- **root** — the root pointer itself (not its address).
- **key** — the key to look for.
- **func** — AVLKEYCOMP callback: A0 = node, A1 = key, return D0 <0/0/>0.
- **Result** — the matching node, or NULL.

Since V45.

### Example
```asm
        move.l  4.w,a6
        move.l  root,a0                 ; value of the root pointer
        move.l  #1234,a1                ; key
        lea     KeyCmp,a2
        jsr     _LVOAVL_FindNode(a6)
        tst.l   d0
        beq     .notfound
        move.l  d0,a0
        lea     -EL_AVL(a0),a0          ; back to the start of the element
        move.l  EL_DATA(a0),d2
```

### Gotchas
- NDK 3.9 has no `exec/avl.i`: asm code defines its own element offsets and uses
  `_LVOAVL_FindNode` etc. from `lvo/exec_lib.i`.

**See also:** [AVL_FindNextNodeByKey](avl.md#avl_findnextnodebykey),
[AVL_FindPrevNodeByKey](avl.md#avl_findprevnodebykey), [AVL_AddNode](avl.md#avl_addnode)

## AVL_FindFirstNode
`struct AVLNode * AVL_FindFirstNode(CONST struct AVLNode *root)` — LVO -900 (-$384)
Registers: root=A0; result in D0

Return the lowest-ordered node of a tree.

- **root** — the root pointer itself.
- **Result** — the smallest node, or NULL for an empty tree.

Since V45.

### Example
```c
struct AVLNode *n, *next;

for (n = AVL_FindFirstNode(root); n != NULL; n = next) {
    next = AVL_FindNextNodeByAddress(n);   /* fetch before n may be removed */
    if (ELEMENT(n)->data == 0) {
        AVL_RemNodeByAddress(&root, n);
        FreeVec(ELEMENT(n));
    }
}
```

**See also:** [AVL_FindLastNode](avl.md#avl_findlastnode),
[AVL_FindNextNodeByAddress](avl.md#avl_findnextnodebyaddress)

## AVL_FindLastNode
`struct AVLNode * AVL_FindLastNode(CONST struct AVLNode *root)` — LVO -906 (-$38A)
Registers: root=A0; result in D0

Return the highest-ordered node of a tree.

- **root** — the root pointer itself.
- **Result** — the biggest node, or NULL for an empty tree.

Since V45.

**See also:** [AVL_FindFirstNode](avl.md#avl_findfirstnode),
[AVL_FindPrevNodeByAddress](avl.md#avl_findprevnodebyaddress)

## AVL_FindNextNodeByAddress
`struct AVLNode * AVL_FindNextNodeByAddress(CONST struct AVLNode *node)` — LVO -888 (-$378)
Registers: node=A0; result in D0

Step from a node to its in-order successor.

- **node** — a node that is in the tree.
- **Result** — the next higher node, or NULL after the last one.

Start a forward walk with AVL_FindFirstNode (see its example). No comparison callback is
needed.

Since V45.

### Gotchas
- The node must be in the tree. To remove nodes during a walk, fetch the successor before
  removing the current node.

**See also:** [AVL_FindFirstNode](avl.md#avl_findfirstnode),
[AVL_FindPrevNodeByAddress](avl.md#avl_findprevnodebyaddress),
[AVL_RemNodeByAddress](avl.md#avl_remnodebyaddress)

## AVL_FindPrevNodeByAddress
`struct AVLNode * AVL_FindPrevNodeByAddress(CONST struct AVLNode *node)` — LVO -876 (-$36C)
Registers: node=A0; result in D0

Step from a node to its in-order predecessor.

- **node** — a node that is in the tree.
- **Result** — the next lower node, or NULL before the first one.

Start a backward walk with AVL_FindLastNode.

Since V45.

### Gotchas
- The node must be in the tree; fetch the predecessor before removing the current node.

**See also:** [AVL_FindLastNode](avl.md#avl_findlastnode),
[AVL_FindNextNodeByAddress](avl.md#avl_findnextnodebyaddress)

## AVL_FindNextNodeByKey
`struct AVLNode * AVL_FindNextNodeByKey(CONST struct AVLNode *root, AVLKey key, APTR func)` — LVO -894 (-$37E)
Registers: root=A0, key=A1, func=A2; result in D0

Find the node with a key, or the nearest node above it when there is no exact match.

- **root** — the root pointer itself.
- **key** — the key to search for.
- **func** — AVLKEYCOMP callback.
- **Result** — the exact match, else the next higher node. The autodoc does not spell out
  the result when every key is lower: treat NULL as "none".

Useful for range scans: find the first node >= a lower bound, then walk with
AVL_FindNextNodeByAddress.

Since V45.

**See also:** [AVL_FindPrevNodeByKey](avl.md#avl_findprevnodebykey),
[AVL_FindNode](avl.md#avl_findnode),
[AVL_FindNextNodeByAddress](avl.md#avl_findnextnodebyaddress)

## AVL_FindPrevNodeByKey
`struct AVLNode * AVL_FindPrevNodeByKey(CONST struct AVLNode *root, AVLKey key, APTR func)` — LVO -882 (-$372)
Registers: root=A0, key=A1, func=A2; result in D0

Find the node with a key, or the nearest node below it when there is no exact match.

- **root** — the root pointer itself.
- **key** — the key to search for.
- **func** — AVLKEYCOMP callback.
- **Result** — the exact match, else the next lower node; treat NULL as "none".

Since V45.

**See also:** [AVL_FindNextNodeByKey](avl.md#avl_findnextnodebykey),
[AVL_FindNode](avl.md#avl_findnode),
[AVL_FindPrevNodeByAddress](avl.md#avl_findprevnodebyaddress)
