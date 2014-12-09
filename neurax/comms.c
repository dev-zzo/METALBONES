#include <Windows.h>
#include <intrin.h>
#include "ntdll.h"

static void InitializeContext(PCONTEXT Context, UINT_PTR InitialEsp, PVOID InitialEip)
{
    Context->SegCs = 0x0018;
    Context->SegDs = 0x0020;
    Context->SegSs = 0x0020;
    Context->SegEs = 0x0020;
    Context->SegFs = 0x0038;
    Context->SegGs = 0x0000;
    Context->Esp = InitialEsp - sizeof(UINT_PTR);
    Context->Eip = (UINT_PTR)InitialEip;
    Context->ContextFlags = CONTEXT_ALL;
}

static void WINAPI CommsThread(void)
{
    __debugbreak();
    NtTerminateThread(0, 0);
}

NTSTATUS SpawnCommsThread(void)
{
    NTSTATUS Status;
    USER_STACK Stack;
    SIZE_T StackSize = 0x2000;
    PVOID StackBottom = NULL;
    CONTEXT Context;
    OBJECT_ATTRIBUTES ThreadAttributes;
    HANDLE ThreadHandle;
    CLIENT_ID ThreadClientId;

    Status = NtAllocateVirtualMemory(
        (HANDLE)0xFFFFFFFFU,
        &StackBottom,
        0,
        &StackSize,
        MEM_COMMIT,
        PAGE_READWRITE);
    if (!NT_SUCCESS(Status)) {
        return Status;
    }

    Stack.FixedStackBase = NULL;
    Stack.FixedStackLimit = NULL;
    Stack.ExpandableStackBase = (PVOID)((UINT_PTR)StackBottom + StackSize);
    Stack.ExpandableStackLimit = StackBottom;
    Stack.ExpandableStackBottom = StackBottom;

    InitializeContext(&Context, (UINT_PTR)Stack.ExpandableStackBase, &CommsThread);
    InitializeObjectAttributes(&ThreadAttributes, NULL, 0, NULL, NULL);

    Status = NtCreateThread(
        &ThreadHandle,
        0x1F03FF,
        &ThreadAttributes,
        (HANDLE)0xFFFFFFFFU,
        &ThreadClientId, 
        &Context,
        &Stack,
        FALSE);

    return Status;
}

