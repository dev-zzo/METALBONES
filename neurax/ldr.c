#if 0

#include <Windows.h>

#define _PEDANTIC

#define IMAGE_PE_SIGNATURE 0x00004550U

LPVOID _ImageBase;

/* http://msdn.microsoft.com/en-us/magazine/cc301808.aspx */

static void WINAPI _LdrBreakPoint()
{
    __asm int 3;
}

/* Imports handling */

static void WINAPI _LdrHandleImports(LPVOID ImageBase, PIMAGE_NT_HEADERS NtHeaders)
{
}

/* Relocations handling */

typedef struct _IMAGE_BASE_RELOCATION_TYPEOFFSET {
    WORD Offset : 12;
    WORD Type : 4;
} IMAGE_BASE_RELOCATION_TYPEOFFSET, *PIMAGE_BASE_RELOCATION_TYPEOFFSET;

static void WINAPI _LdrHandleFixups(LPVOID ImageBase, PIMAGE_NT_HEADERS NtHeaders)
{
    PIMAGE_DATA_DIRECTORY FixupDirectoryEntry = &NtHeaders->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC];
    PIMAGE_BASE_RELOCATION Relocation;
    DWORD RelocsSize = FixupDirectoryEntry->Size;
    UINT_PTR Delta = (UINT_PTR)ImageBase - (UINT_PTR)NtHeaders->OptionalHeader.ImageBase;

    Relocation = (PIMAGE_BASE_RELOCATION)((UINT_PTR)ImageBase + FixupDirectoryEntry->VirtualAddress);
    while (RelocsSize && RelocsSize < FixupDirectoryEntry->Size) {
        DWORD TypeOffsetCount = (Relocation->SizeOfBlock - sizeof(IMAGE_BASE_RELOCATION)) / sizeof(WORD);
        PIMAGE_BASE_RELOCATION_TYPEOFFSET TypeOffset = (PIMAGE_BASE_RELOCATION_TYPEOFFSET)(Relocation + 1);
        UINT_PTR RelocationBase = (UINT_PTR)ImageBase + (UINT_PTR)Relocation->VirtualAddress;

        while (TypeOffsetCount > 0) {
            LPVOID Addr = (LPVOID)(RelocationBase + TypeOffset->Offset);
            switch (TypeOffset->Type) {
            case IMAGE_REL_BASED_ABSOLUTE:
                /* Nothing. */
                break;
            case IMAGE_REL_BASED_HIGH:
            case IMAGE_REL_BASED_LOW:
                _LdrBreakPoint();
                break;
            case IMAGE_REL_BASED_HIGHLOW:
                *(DWORD *)Addr += Delta;
                break;
            default:
                /* Something I don't know about. */
                break;
            }
            ++TypeOffset;
            --TypeOffsetCount;
        }

        Relocation = (PIMAGE_BASE_RELOCATION)((UINT_PTR)Relocation + Relocation->SizeOfBlock);
        RelocsSize -= Relocation->SizeOfBlock;
    }
}

/* The entry point */

BOOL WINAPI _EntryPoint(LPVOID ImageBase)
{
    PIMAGE_DOS_HEADER DosHeader = (PIMAGE_DOS_HEADER)ImageBase;
    PIMAGE_NT_HEADERS NtHeaders = (PIMAGE_NT_HEADERS)((ULONG_PTR)DosHeader + DosHeader->e_lfanew);

    _ImageBase = ImageBase;

#ifdef _PEDANTIC
    if (DosHeader->e_magic != IMAGE_DOS_SIGNATURE) {
        return FALSE;
    }
    if (NtHeaders->Signature != IMAGE_PE_SIGNATURE) {
        return FALSE;
    }
#endif

    _LdrHandleImports(ImageBase, NtHeaders);
    _LdrHandleFixups(ImageBase, NtHeaders);

    return TRUE;
}
#endif
