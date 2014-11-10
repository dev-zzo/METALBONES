#include <Python.h>
#include <Windows.h>

#include "whelpers.h"

int
ldr_walk_NT513(HANDLE process, PVOID peb, ldr_callback_t callback)
{
    NTSTATUS status;
    PPEB_NT513 peb_ptr = (PPEB_NT513)peb;
    PPEB_LDR_DATA_NT513 ldr_data_ptr;
    PEB_LDR_DATA_NT513 ldr_data;
    PLIST_ENTRY ldr_entry_ptr, hdr_entry_ptr;

    status = NtReadVirtualMemory(
        process,
        &peb_ptr->Ldr,
        &ldr_data_ptr,
        sizeof(ldr_data_ptr),
        NULL);
    if (!NT_SUCCESS(status))
        return -1;

    status = NtReadVirtualMemory(
        process,
        ldr_data_ptr,
        &ldr_data,
        sizeof(ldr_data),
        NULL);
    if (!NT_SUCCESS(status))
        return -1;

    hdr_entry_ptr = &ldr_data_ptr->InLoadOrderModuleList;
    ldr_entry_ptr = ldr_data.InLoadOrderModuleList.Flink;
    while (ldr_entry_ptr != hdr_entry_ptr) {
        LDR_DATA_TABLE_ENTRY_NT513 entry;

        status = NtReadVirtualMemory(
            process,
            ldr_entry_ptr,
            &entry,
            sizeof(entry),
            NULL);
        if (!NT_SUCCESS(status))
            return -1;

        if (callback(process, &entry) != 0)
            break;

        ldr_entry_ptr = entry.InLoadOrderLinks.Flink;
    }

    return 0;
}

