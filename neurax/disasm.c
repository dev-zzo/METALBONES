#include "disasm.h"
#include <intrin.h>
#include <windows.h>

static const BYTE ModRMPresentTab[] = {
    0x0FU, 0x0FU,
    0x0FU, 0x0FU,
    0x0FU, 0x0FU,
    0x0FU, 0x0FU,

    0x00U, 0x00U,
    0x00U, 0x00U,
    0x0CU, 0x0AU,
    0x00U, 0x00U,

    0xFFU, 0xFFU,
    0x00U, 0x00U,
    0x00U, 0x00U,
    0x00U, 0x00U,

    0x3FU, 0x00U,
    0xF3U, 0xFFU,
    0x00U, 0x00U,
    0xC0U, 0xC0U,
};

static const BYTE ModRMPresent0FTab[] = {
    0x0FU, 0x20U,
    0xFFU, 0x81U,
    0x0FU, 0xFFU,
    0x00U, 0x00U,

    0xFFU, 0xFFU,
    0xFFU, 0xFFU,
    0xFFU, 0xFFU,
    0x7FU, 0xF3U,

    0x00U, 0x00U,
    0xFFU, 0xFFU,
    0x38U, 0xF8U,
    0xFFU, 0xFFU,

    0xFFU, 0xFFU,
    0xFFU, 0xFFU,
    0xFFU, 0xFFU,
    0xFFU, 0xFFU,
};

static const BYTE ImmPresentTab[] = {
    0x30U, 0x30U,
    0x30U, 0x30U,
    0x30U, 0x30U,
    0x30U, 0x30U,

    0x00U, 0x00U,
    0x00U, 0x00U,
    0x00U, 0x0FU,
    0xFFU, 0xFFU,

    0x0FU, 0x00U,
    0x00U, 0x04U,
    0x0FU, 0x03U,
    0xFFU, 0xFFU,

    0xC7U, 0x25U,
    0x30U, 0x00U,
    0xFFU, 0x0FU,
    0x00U, 0x00U,
};

static const BYTE ImmWidthTab[] = {
    0x20U, 0x20U,
    0x20U, 0x20U,
    0x20U, 0x20U,
    0x20U, 0x20U,

    0x00U, 0x00U,
    0x00U, 0x00U,
    0x00U, 0x02U,
    0x00U, 0x00U,

    0x02U, 0x00U,
    0x00U, 0x00U,
    0x0AU, 0x00U,
    0x00U, 0xFFU,

    0x80U, 0x00U,
    0x00U, 0x00U,
    0x00U, 0x03U,
    0x00U, 0x00U,
};

void DecodeInsn32(unsigned char *Ptr, PINSN_INFO Info)
{
    BOOL ModRMPresent = FALSE;
    int OperandSize = 4;
    int ImmSize = 0;
    BYTE Opcode;

    Info->Start = Ptr;

fetch_prefix:
    Opcode = *Ptr++;
    if ((Opcode & 0xE7) == 0x26)
        goto fetch_prefix;
    if ((Opcode & 0xFC) == 0xF0)
        goto fetch_prefix;
    if ((Opcode & 0xFC) == 0x64) {
        if (Opcode == 0x66) {
            OperandSize = 2;
        }
        goto fetch_prefix;
    }

    if (Opcode == 0x0F) {
        Opcode = *Ptr++;
        if (Opcode == 0x38) {
            Opcode = *Ptr;
            if (Opcode == 0x13) {
                ImmSize = 1;
            }
            Ptr++;
            ModRMPresent = TRUE;
        }
        else if (Opcode == 0x3A) {
            Opcode = *Ptr;
            if ((Opcode & 0xF8) != 0x48) {
                ImmSize = 1;
            }
            Ptr++;
            ModRMPresent = TRUE;
        }
        else if ((Opcode & 0xF0) == 0x80) {
            /* Jcc, long */
            Info->IsCondJump = 1;
            Info->JumpCC = Opcode & 0x0F;
            Info->Offset = *(INT_PTR *)Ptr;
            Ptr += sizeof(INT_PTR); /* 16-bit WARN */
        }
        else {
            if ((Opcode & 0xFC) == 0x70 || (Opcode & 0xF7) == 0xA4 || Opcode == 0xBA || Opcode == 0xC2 || Opcode == 0xC4 || Opcode == 0xC5 || Opcode == 0xC6) {
                ImmSize = 1;
            }
            ModRMPresent = _bittest((long *)ModRMPresent0FTab, Opcode);
        }
    }
    else {
        if (Opcode == 0xC2 || Opcode == 0xCA) {
            ImmSize = 2;
        }
        else if (Opcode == 0xC8) {
            ImmSize = 3;
        }
        else if (Opcode == 0x9A || Opcode == 0xEA) {
            ImmSize = 2 + 4;
        }
        else if ((Opcode & 0xF0) == 0x70) {
            /* Jcc, short */
            Info->IsCondJump = 1;
            Info->JumpCC = Opcode & 0x0F;
            Info->Offset = *(signed char *)Ptr;
            Ptr++;
        }
        else if ((Opcode & 0xFC) == 0xE0 || Opcode == 0xEB) {
            /* LOOP/JCXZ */
            Info->IsRelJump = 1;
            Info->Offset = *(signed char *)Ptr;
            Ptr++;
        }
        else if (Opcode == 0xE8) {
            Info->IsRelCall = 1;
            Info->Offset = *(INT_PTR *)Ptr;
            Ptr += sizeof(INT_PTR); /* 16-bit WARN */
        }
        else {
            if (_bittest((long *)ImmPresentTab, Opcode)) {
                ImmSize = _bittest((long *)ImmWidthTab, Opcode) ? OperandSize : 1;
            }
            ModRMPresent = _bittest((long *)ModRMPresentTab, Opcode);
        }
    }

    if (ModRMPresent) {
        BYTE ModRM;
        BYTE Mod, RM;
        ModRM = *Ptr++;
        Mod = ModRM >> 6;
        RM = ModRM & 0x07;
        if (Mod == 0) {
            if (RM == 4) {
                BYTE SIB;
                SIB = *Ptr++;
                if ((SIB & 0x07) == 5) {
                    Ptr += 4;
                }
            }
            else if (RM == 5) {
                Ptr += 4;
            }
        }
        else if (Mod == 1) {
            if (RM == 4) {
                Ptr++;
            }
            Ptr += 1;
        }
        else if (Mod == 2) {
            if (RM == 4) {
                Ptr++;
            }
            Ptr += 4;
        }
    }

    Ptr += ImmSize;

    Info->Length = (UINT_PTR)Ptr - (UINT_PTR)Info->Start;
}
