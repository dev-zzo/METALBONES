
class Register:
    def __init__(self, name, bits):
        self.name = name
        self.bits = bits
#

# 64-bit regs
reg_rax = Register("rax", 64)
reg_rcx = Register("rcx", 64)
reg_rdx = Register("rdx", 64)
reg_rbx = Register("rbx", 64)
reg_rsp = Register("rsp", 64)
reg_rbp = Register("rbp", 64)
reg_rsi = Register("rsi", 64)
reg_rdi = Register("rdi", 64)

# 32-bit regs
reg_eax = Register("eax", 32)
reg_ecx = Register("ecx", 32)
reg_edx = Register("edx", 32)
reg_ebx = Register("ebx", 32)
reg_esp = Register("esp", 32)
reg_ebp = Register("ebp", 32)
reg_esi = Register("esi", 32)
reg_edi = Register("edi", 32)

# 16-bit regs
reg_ax = Register("ax", 16)
reg_cx = Register("cx", 16)
reg_dx = Register("dx", 16)
reg_bx = Register("bx", 16)
reg_sp = Register("sp", 16)
reg_bp = Register("bp", 16)
reg_si = Register("si", 16)
reg_di = Register("di", 16)

# 8-bit regs
reg_al = Register("al", 8)
reg_cl = Register("cl", 8)
reg_dl = Register("dl", 8)
reg_bl = Register("bl", 8)
reg_ah = Register("ah", 8)
reg_ch = Register("ch", 8)
reg_dh = Register("dh", 8)
reg_bh = Register("bh", 8)

r64_decode = (
    reg_rax, reg_rcx, reg_rdx, reg_rbx,
    reg_rsp, reg_rbp, reg_rsi, reg_rdi)
r32_decode = (
    reg_eax, reg_ecx, reg_edx, reg_ebx,
    reg_esp, reg_ebp, reg_esi, reg_edi)
r16_decode = (
    reg_ax, reg_cx, reg_dx, reg_bx,
    reg_sp, reg_bp, reg_si, reg_di)
#

reg_es = Register("es", 16)
reg_cs = Register("cs", 16)
reg_ss = Register("ss", 16)
reg_ds = Register("ds", 16)
reg_fs = Register("fs", 16)
reg_gs = Register("gs", 16)

rseg_decode = (
    reg_es, reg_cs, reg_ss, reg_ds,
    reg_fs, reg_gs, None, None)
#

reg_dr0 = Register("dr0", 32)
reg_dr1 = Register("dr1", 32)
reg_dr2 = Register("dr2", 32)
reg_dr3 = Register("dr3", 32)
reg_dr6 = Register("dr6", 32)
reg_dr7 = Register("dr7", 32)

rdebug_decode = (
    reg_dr0, reg_dr1, reg_dr2, reg_dr3,
    None, None, reg_dr6, reg_dr7)
#

reg_cr0 = Register("cr0", 32)
reg_cr2 = Register("cr2", 32)
reg_cr3 = Register("cr3", 32)
reg_cr4 = Register("cr4", 32)

rcontrol_decode = (
    reg_cr0, None, reg_cr2, reg_cr3,
    reg_cr4, None, None, None)
#

class State:
    def __init__(self):
        pass

class Table:
    def __init__(self, entries):
        self.entries = entries

decode_main = (
    # 0
    
    )
#
