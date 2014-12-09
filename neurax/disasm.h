#ifndef __disasm_included
#define __disasm_included

typedef struct _INSN_INFO {
    void *Start;
    int Length;
    unsigned char IsRelCall;
    unsigned char IsRelJump;
    unsigned char IsCondJump;
    unsigned char JumpCC;
    long Offset;
} INSN_INFO, *PINSN_INFO;

extern void DecodeInsn32(unsigned char *Ptr, PINSN_INFO Info);

#endif // __disasm_included
