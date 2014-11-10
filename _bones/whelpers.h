#ifndef __WHELPERS_INCLUDED
#define __WHELPERS_INCLUDED

#include "winternals.h"

typedef int
(*ldr_callback_t)(HANDLE process, PVOID ldr_entry);

extern int
ldr_walk_NT513(HANDLE process, PVOID peb, ldr_callback_t callback);

#endif // __WHELPERS_INCLUDED
