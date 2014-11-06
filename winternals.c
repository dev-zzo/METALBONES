#include <Python.h>
#include <Windows.h>
#include "winternals.h"
#include "internal.h"

PNTQUERYINFORMATIONTHREAD NtQueryInformationThread;

PNTQUERYINFORMATIONPROCESS NtQueryInformationProcess;
PNTREADVIRTUALMEMORY NtReadVirtualMemory;
PNTWRITEVIRTUALMEMORY NtWriteVirtualMemory;
PNTQUERYVIRTUALMEMORY NtQueryVirtualMemory;

PNTQUERYINFORMATIONFILE NtQueryInformationFile;

PNTCREATEDEBUGOBJECT NtCreateDebugObject;
PNTDEBUGACTIVEPROCESS NtDebugActiveProcess;
PNTWAITFORDEBUGEVENT NtWaitForDebugEvent;
PNTDEBUGCONTINUE NtDebugContinue;
PNTREMOVEPROCESSDEBUG NtRemoveProcessDebug;

#define GETPROC(t, p) \
    do { \
        p = (t)GetProcAddress(ntdll, #p); \
        if (!p) { \
            DEBUG_PRINT("BONES: Failed to get " #p "\n"); \
            return -1; \
        } \
    } while(0)

int
init_ntdll_pointers(void)
{
    HMODULE ntdll = GetModuleHandleA("ntdll.dll");
    if (!ntdll) {
        /* Print something? */
        DEBUG_PRINT("BONES: Failed to get a handle for ntdll!\n");
        return -1;
    }

    GETPROC(PNTQUERYINFORMATIONTHREAD, NtQueryInformationThread);

    GETPROC(PNTQUERYINFORMATIONPROCESS, NtQueryInformationProcess);
    GETPROC(PNTREADVIRTUALMEMORY, NtReadVirtualMemory);
    GETPROC(PNTWRITEVIRTUALMEMORY, NtWriteVirtualMemory);
    GETPROC(PNTQUERYVIRTUALMEMORY, NtQueryVirtualMemory);

    GETPROC(PNTQUERYINFORMATIONFILE, NtQueryInformationFile);

    GETPROC(PNTCREATEDEBUGOBJECT, NtCreateDebugObject);
    GETPROC(PNTDEBUGACTIVEPROCESS, NtDebugActiveProcess);
    GETPROC(PNTWAITFORDEBUGEVENT, NtWaitForDebugEvent);
    GETPROC(PNTDEBUGCONTINUE, NtDebugContinue);
    GETPROC(PNTREMOVEPROCESSDEBUG, NtRemoveProcessDebug);

    return 0;
}

