#include <Windows.h>
#include <intrin.h>

#include "ntdll.h"

static const unsigned char _DllLoader[] =
    "\x53\x51\x56\x57\x64\xA1\x30\x00\x00\x00\x8B\x40\x0C\x8B\x40\x0C"
    "\x8B\x00\x8B\x40\x18\x8B\xD0\x03\x40\x3C\x8B\x58\x78\x8B\x74\x1A"
    "\x20\x03\xF2\x6A\xFF\x5F\x47\xAD\xB9\x4C\x64\x72\x4C\x39\x0C\x02"
    "\x75\xF4\xB9\x6F\x61\x64\x44\x39\x4C\x02\x04\x75\xE9\x66\xB9\x6C"
    "\x6C\x66\x39\x4C\x02\x08\x75\xDE\x8B\x74\x1A\x24\x03\xF2\x0F\xB7"
    "\x34\x7E\x8B\x44\x1A\x1C\x03\xC2\x8B\x04\xB0\x03\xC2\x33\xDB\x53"
    "\x54\x68\x70\x10\x40\x00\x53\x53\xFF\xD0\x58\x5F\x5E\x59\x5B\xC3";

NTSTATUS
ForceDllLoad(HANDLE Process, LPCWSTR DllPath)
{
    NTSTATUS Status;
    struct {
        unsigned char Code[sizeof(_DllLoader)];
        union {
            WCHAR Chars[260];
            UNICODE_STRING String;
        } Buffer;
    } Loader;
    LPBYTE Address = NULL;
    SIZE_T Size = 4096;

    Status = NtAllocateVirtualMemory(
        Process,
        &Address,
        12,
        &Size,
        MEM_COMMIT,
        PAGE_EXECUTE_READWRITE);
    if (!NT_SUCCESS(Status)) {
        return Status;
    }

    memcpy(Loader.Code, _DllLoader, sizeof(Loader.Code));
    Loader.Buffer.String.MaximumLength = sizeof(Loader.Buffer) - sizeof(UNICODE_STRING);
    Loader.Buffer.String.Length = wcslen(DllPath) * sizeof(WCHAR);
    wcscpy(&Loader.Buffer.Chars[sizeof(UNICODE_STRING) / sizeof(WCHAR)], DllPath);
    *(UINT_PTR *)Loader.Code[0x62] = (UINT_PTR)Address + 0x70;
    Loader.Buffer.String.Buffer = (PWSTR)(Address + 0x78);

    Status = NtWriteVirtualMemory(
        Process,
        Address,
        &Loader,
        sizeof(Loader),
        NULL);
    if (!NT_SUCCESS(Status)) {
        goto free_mem;
    }



free_mem:
    Size = 0;
    NtFreeVirtualMemory(
        Process,
        &Address,
        &Size,
        MEM_RELEASE);

    return 0;
}
