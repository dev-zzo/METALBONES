
class Error(Exception):
    """Base class for errors raised in this module."""
    pass

class InvalidOpcodeError(Error):
    """Opcode is marked invalid."""
    pass

class UnknownOpcodeError(Error):
    """Opcode is not marked invalid, but I don't know it."""
    pass

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
    def __init__(self, reader):
        self.reader = reader
        # Opcode bytes so far
        self.opcode = ""
        # ModRM byte fetched
        self.modrm = None
        # SIB byte fetched
        self.sib = None
        
        self.bitness = 32
        self.seg_override = None
        self.prefix_66 = False # Operand size
        self.prefix_67 = False # Address size
        self.prefix_F2 = False # REPNE
        self.prefix_F3 = False # REPE
        
    def fetch(self):
        b = self.reader.read()
        self.opcode += b
        return b
#

class SegmentOverridePrefix:
    def __init__(self, regname):
        self.regname = regname
    def __call__(self, state):
        state.seg_override = self.regname
class OperandSizePrefix:
    def __call__(self, state):
        state.prefix_66 = True
class AddressSizePrefix:
    def __call__(self, state):
        state.prefix_67 = True

class InvalidOpcode:
    def __call__(self, state):
        raise InvalidOpcodeError()
_invalidOpcode = InvalidOpcode()

class SwitchOpcode:
    """Table switch based on insn opcode byte"""
    def __init__(self, entries):
        self.entries = entries
        
    def __call__(self, state):
        b = state.fetch()
        e = self.entries[b]
        if e is None:
            raise UnknownOpcodeError()
        return e(state)
#

class SwitchPrefix:
    """Table switch based on insn prefix."""
    def __init__(self, nopfx=None, pfx66=None, pfxF2=None, pfxF3=None, pfx66F2=None):
        self.nopfx = nopfx
        self.pfx66 = pfx66
        self.pfxF2 = pfxF2
        self.pfxF3 = pfxF3
        self.pfx66F2 = pfx66F2

    def __call__(self, state):
        if state.prefix_66:
            # TODO: Not sure how to resolve prefix conflicts
            if state.prefix_F2 and self.pfx66F2 is not None:
                state.prefix_66 = False
                state.prefix_F2 = False
                return self.pfx66F2(state)
            if self.pfx66 is not None:
                state.prefix_66 = False
                return self.pfx66(state)
        if state.prefix_F2 and self.pfxF2 is not None:
            state.prefix_F2 = False
            return self.pfxF2(state)
        if state.prefix_F3:
            state.prefix_F3 = False
            return self.pfxF3(state)
#

def _check_modrm(code):
    return code[0] in "CDEGMNOPQRSUVW"

class Insn:
    def __init__(self, mnemonic, operands, flags):
        self.mnemonic = mnemonic
        self.operands = operands
        self.flags = flags
        
    def __call__(self, state):
        # General instruction structure is as follows
        # Legacy prefices
        # REX prefix
        # Opcode
        # ModR/M
        # SIB
        # Displacement
        # Immediate
        pass
#

decode_0F_32 = SwitchOpcode(
    # 00
    None, # ModRM opcode group 6
    None, # ModRM opcode group 7
    Insn("lar",     ("Gv", "Ew", None), ()),
    Insn("lsl",     ("Gv", "Ew", None), ()),
    _invalidOpcode,
    _invalidOpcode, # SYSCALL -- only 64-bit
    Insn("clts",    (None, None, None), ()),
    _invalidOpcode, # SYSRET -- only 64-bit
    # 08
    Insn("invd",    (None, None, None), ()),
    Insn("wbinvd",  (None, None, None), ()),
    _invalidOpcode,
    Insn("ud2",     (None, None, None), ()),
    _invalidOpcode,
    Insn("prefetchw", ("Ev", None, None), ()),
    _invalidOpcode,
    _invalidOpcode,
    # 10
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 18
    None, # ModRM opcode group 16
    _invalidOpcode,
    _invalidOpcode,
    _invalidOpcode,
    _invalidOpcode,
    _invalidOpcode,
    _invalidOpcode,
    Insn("nop",     ("Ev", None, None), ()),
    # 20
    Insn("mov",     ("Rd", "Cd", None), ()),
    Insn("mov",     ("Rd", "Dd", None), ()),
    Insn("mov",     ("Cd", "Rd", None), ()),
    Insn("mov",     ("Dd", "Rd", None), ()),
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 28
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 30
    Insn("wrmsr",   (None, None, None), ()),
    Insn("rdtsc",   (None, None, None), ()),
    Insn("rdmsr",   (None, None, None), ()),
    Insn("rdpmc",   (None, None, None), ()),
    Insn("sysenter", (None, None, None), ()),
    Insn("sysexit", (None, None, None), ()),
    _invalidOpcode,
    Insn("getsec",  (None, None, None), ()),
    # 38
    None, # Escape 0F38
    _invalidOpcode,
    None, # Escape 0F3A
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 40
    Insn("cmovo",   ("Gv", "Ev", None), ()),
    Insn("cmovno",  ("Gv", "Ev", None), ()),
    Insn("cmovb",   ("Gv", "Ev", None), ()),
    Insn("cmovae",  ("Gv", "Ev", None), ()),
    Insn("cmove",   ("Gv", "Ev", None), ()),
    Insn("cmovne",  ("Gv", "Ev", None), ()),
    Insn("cmovbe",  ("Gv", "Ev", None), ()),
    Insn("cmova",   ("Gv", "Ev", None), ()),
    # 48
    Insn("cmovs",   ("Gv", "Ev", None), ()),
    Insn("cmovns",  ("Gv", "Ev", None), ()),
    Insn("cmovp",   ("Gv", "Ev", None), ()),
    Insn("cmovnp",  ("Gv", "Ev", None), ()),
    Insn("cmovl",   ("Gv", "Ev", None), ()),
    Insn("cmovge",  ("Gv", "Ev", None), ()),
    Insn("cmovle",  ("Gv", "Ev", None), ()),
    Insn("cmovg",   ("Gv", "Ev", None), ()),
    # 50
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 58
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 60
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 68
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 70
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 78
    Insn("vmread",  ("Ey", "Gy", None), ()),
    Insn("vmwrite", ("Gy", "Ey", None), ()),
    _invalidOpcode,
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 80
    Insn("jo",      ("Jz", None, None), ()),
    Insn("jno",     ("Jz", None, None), ()),
    Insn("jb",      ("Jz", None, None), ()),
    Insn("jae",     ("Jz", None, None), ()),
    Insn("je",      ("Jz", None, None), ()),
    Insn("jne",     ("Jz", None, None), ()),
    Insn("jbe",     ("Jz", None, None), ()),
    Insn("ja",      ("Jz", None, None), ()),
    # 88
    Insn("js",      ("Jz", None, None), ()),
    Insn("jns",     ("Jz", None, None), ()),
    Insn("jp",      ("Jz", None, None), ()),
    Insn("jnp",     ("Jz", None, None), ()),
    Insn("jl",      ("Jz", None, None), ()),
    Insn("jge",     ("Jz", None, None), ()),
    Insn("jle",     ("Jz", None, None), ()),
    Insn("jg",      ("Jz", None, None), ()),
    # 90
    Insn("seto",    ("Eb", None, None), ()),
    Insn("setno",   ("Eb", None, None), ()),
    Insn("setb",    ("Eb", None, None), ()),
    Insn("setae",   ("Eb", None, None), ()),
    Insn("sete",    ("Eb", None, None), ()),
    Insn("setne",   ("Eb", None, None), ()),
    Insn("setbe",   ("Eb", None, None), ()),
    Insn("seta",    ("Eb", None, None), ()),
    # 98
    Insn("sets",    ("Eb", None, None), ()),
    Insn("setns",   ("Eb", None, None), ()),
    Insn("setp",    ("Eb", None, None), ()),
    Insn("setnp",   ("Eb", None, None), ()),
    Insn("setl",    ("Eb", None, None), ()),
    Insn("setge",   ("Eb", None, None), ()),
    Insn("setle",   ("Eb", None, None), ()),
    Insn("setg",    ("Eb", None, None), ()),
    # A0
    Insn("push",    ("fs", None, None), ()),
    Insn("pop",     ("fs", None, None), ()),
    Insn("cpuid",   None, None, None), ()),
    Insn("bt",      ("Ev", "Gv", None), ()),
    Insn("shld",    ("Ev", "Gv", "Ib", ()),
    Insn("shld",    ("Ev", "Gv", "cl", ()),
    _invalidOpcode,
    _invalidOpcode,
    # A8
    Insn("push",    ("gs", None, None), ()),
    Insn("pop",     ("gs", None, None), ()),
    Insn("rsm",     (None, None, None), ()),
    Insn("bts",     ("Ev", "Gv", None), ()),
    Insn("shrd",    ("Ev", "Gv", "Ib", ()),
    Insn("shrd",    ("Ev", "Gv", "cl", ()),
    None, # Group 15
    Insn("imul",    ("Gv", "Ev", None), ()),
    # B0
    Insn("cmpxchg", ("Eb", "Gb", None), ()),
    Insn("cmpxchg", ("Ev", "Gv", None), ()),
    Insn("lss",     ("Gv", "Mp", None), ()),
    Insn("btr",     ("Ev", "Gv", None), ()),
    Insn("lfs",     ("Gv", "Mp", None), ()),
    Insn("lgs",     ("Gv", "Mp", None), ()),
    Insn("movzx",   ("Gv", "Eb", None), ()),
    Insn("movzx",   ("Gv", "Ew", None), ()),
    # B8
    _invalidOpcode,
    None, # ModRM opcode group 10 ?
    None, # ModRM opcode group 8
    Insn("btc",     ("Ev", "Gv", None), ()),
    Insn("bsf",     ("Gv", "Ev", None), ()),
    Insn("bsr",     ("Gv", "Ev", None), ()),
    Insn("movsx",   ("Gv", "Eb", None), ()),
    Insn("movsx",   ("Gv", "Ew", None), ()),
    # C0
    Insn("xadd",    ("Eb", "Gb", None), ()),
    Insn("xadd",    ("Ev", "Gv", None), ()),
    _invalidOpcode,
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # C8
    Insn("bswap",   ("eax", None, None), ()),
    Insn("bswap",   ("ecx", None, None), ()),
    Insn("bswap",   ("edx", None, None), ()),
    Insn("bswap",   ("ebx", None, None), ()),
    Insn("bswap",   ("esp", None, None), ()),
    Insn("bswap",   ("ebp", None, None), ()),
    Insn("bswap",   ("esi", None, None), ()),
    Insn("bswap",   ("edi", None, None), ()),
    # D0
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # D8
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # E0
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # E8
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # F0
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # F8
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode)

decode_main_32 = SwitchOpcode(
    # 00
    Insn("add",     ("Eb", "Gb", None), ()),
    Insn("add",     ("Ev", "Gv", None), ()),
    Insn("add",     ("Gb", "Eb", None), ()),
    Insn("add",     ("Gv", "Ev", None), ()),
    Insn("add",     ("al", "Ib", None), ()),
    Insn("add",     ("eax", "Iz", None), ()),
    Insn("push",    ("es", None, None), ()), # invalid in x64
    Insn("pop",     ("es", None, None), ()), # invalid in x64
    # 08
    Insn("or",      ("Eb", "Gb", None), ()),
    Insn("or",      ("Ev", "Gv", None), ()),
    Insn("or",      ("Gb", "Eb", None), ()),
    Insn("or",      ("Gv", "Ev", None), ()),
    Insn("or",      ("al", "Ib", None), ()),
    Insn("or",      ("eax", "Iz", None), ()),
    Insn("push",    ("cs", None, None), ()), # invalid in x64
    None, # Escape 0F
    # 10
    Insn("adc",     ("Eb", "Gb", None), ()),
    Insn("adc",     ("Ev", "Gv", None), ()),
    Insn("adc",     ("Gb", "Eb", None), ()),
    Insn("adc",     ("Gv", "Ev", None), ()),
    Insn("adc",     ("al", "Ib", None), ()),
    Insn("adc",     ("eax", "Iz", None), ()),
    Insn("push",    ("ss", None, None), ()), # invalid in x64
    Insn("pop",     ("ss", None, None), ()), # invalid in x64
    # 18
    Insn("sbb",     ("Eb", "Gb", None), ()),
    Insn("sbb",     ("Ev", "Gv", None), ()),
    Insn("sbb",     ("Gb", "Eb", None), ()),
    Insn("sbb",     ("Gv", "Ev", None), ()),
    Insn("sbb",     ("al", "Ib", None), ()),
    Insn("sbb",     ("eax", "Iz", None), ()),
    Insn("push",    ("ds", None, None), ()), # invalid in x64
    Insn("pop",     ("ds", None, None), ()), # invalid in x64
    # 20
    Insn("and",     ("Eb", "Gb", None), ()),
    Insn("and",     ("Ev", "Gv", None), ()),
    Insn("and",     ("Gb", "Eb", None), ()),
    Insn("and",     ("Gv", "Ev", None), ()),
    Insn("and",     ("al", "Ib", None), ()),
    Insn("and",     ("eax", "Iz", None), ()),
    SegmentOverridePrefix("es"),
    Insn("daa",     (None, None, None), ()),
    # 28
    Insn("sub",     ("Eb", "Gb", None), ()),
    Insn("sub",     ("Ev", "Gv", None), ()),
    Insn("sub",     ("Gb", "Eb", None), ()),
    Insn("sub",     ("Gv", "Ev", None), ()),
    Insn("sub",     ("al", "Ib", None), ()),
    Insn("sub",     ("eax", "Iz", None), ()),
    SegmentOverridePrefix("cs"),
    Insn("das",     (None, None, None), ()),
    # 30
    Insn("xor",     ("Eb", "Gb", None), ()),
    Insn("xor",     ("Ev", "Gv", None), ()),
    Insn("xor",     ("Gb", "Eb", None), ()),
    Insn("xor",     ("Gv", "Ev", None), ()),
    Insn("xor",     ("al", "Ib", None), ()),
    Insn("xor",     ("eax", "Iz", None), ()),
    SegmentOverridePrefix("ss"),
    Insn("aaa",     (None, None, None), ()),
    # 38
    Insn("cmp",     ("Eb", "Gb", None), ()),
    Insn("cmp",     ("Ev", "Gv", None), ()),
    Insn("cmp",     ("Gb", "Eb", None), ()),
    Insn("cmp",     ("Gv", "Ev", None), ()),
    Insn("cmp",     ("al", "Ib", None), ()),
    Insn("cmp",     ("eax", "Iz", None), ()),
    SegmentOverridePrefix("ds"),
    Insn("aas",     (None, None, None), ()),
    # 40
    Insn("inc",     ("eax", None, None), ()),
    Insn("inc",     ("ecx", None, None), ()),
    Insn("inc",     ("edx", None, None), ()),
    Insn("inc",     ("ebx", None, None), ()),
    Insn("inc",     ("esp", None, None), ()),
    Insn("inc",     ("ebp", None, None), ()),
    Insn("inc",     ("esi", None, None), ()),
    Insn("inc",     ("edi", None, None), ()),
    # 48
    Insn("dec",     ("eax", None, None), ()),
    Insn("dec",     ("ecx", None, None), ()),
    Insn("dec",     ("edx", None, None), ()),
    Insn("dec",     ("ebx", None, None), ()),
    Insn("dec",     ("esp", None, None), ()),
    Insn("dec",     ("ebp", None, None), ()),
    Insn("dec",     ("esi", None, None), ()),
    Insn("dec",     ("edi", None, None), ()),
    # 50
    Insn("push",    ("eax", None, None), ()),
    Insn("push",    ("ecx", None, None), ()),
    Insn("push",    ("edx", None, None), ()),
    Insn("push",    ("ebx", None, None), ()),
    Insn("push",    ("esp", None, None), ()),
    Insn("push",    ("ebp", None, None), ()),
    Insn("push",    ("esi", None, None), ()),
    Insn("push",    ("edi", None, None), ()),
    # 58
    Insn("pop",     ("eax", None, None), ()),
    Insn("pop",     ("ecx", None, None), ()),
    Insn("pop",     ("edx", None, None), ()),
    Insn("pop",     ("ebx", None, None), ()),
    Insn("pop",     ("esp", None, None), ()),
    Insn("pop",     ("ebp", None, None), ()),
    Insn("pop",     ("esi", None, None), ()),
    Insn("pop",     ("edi", None, None), ()),
    # 60
    Insn("pusha",   (None, None, None), ()), # invalid in x64
    Insn("popa",    (None, None, None), ()), # invalid in x64
    Insn("bound",   ("Gv", "Ma", None), ()), # invalid in x64
    Insn("arpl",    ("Ew", "Gw", None), ()),
    SegmentOverridePrefix("fs"),
    SegmentOverridePrefix("gs"),
    OperandSizePrefix(),
    AddressSizePrefix(),
    # 68
    Insn("push",    ("Iz", None, None), ()),
    Insn("imul",    ("Gv", "Ev", "Iz", ()),
    Insn("push",    ("Ib", None, None), ()),
    Insn("imul",    ("Gv", "Ev", "Ib", ()),
    Insn("ins",     ("Yb", "dx", None), ()),
    Insn("ins",     ("Yz", "dx", None), ()),
    Insn("outs",    ("dx", "Xb", None), ()),
    Insn("outs",    ("dx", "Xz", None), ()),
    # 70
    Insn("jo",      ("Jb", None, None), ()),
    Insn("jno",     ("Jb", None, None), ()),
    Insn("jb",      ("Jb", None, None), ()),
    Insn("jae",     ("Jb", None, None), ()),
    Insn("je",      ("Jb", None, None), ()),
    Insn("jne",     ("Jb", None, None), ()),
    Insn("jbe",     ("Jb", None, None), ()),
    Insn("ja",      ("Jb", None, None), ()),
    # 78
    Insn("js",      ("Jb", None, None), ()),
    Insn("jns",     ("Jb", None, None), ()),
    Insn("jp",      ("Jb", None, None), ()),
    Insn("jnp",     ("Jb", None, None), ()),
    Insn("jl",      ("Jb", None, None), ()),
    Insn("jge",     ("Jb", None, None), ()),
    Insn("jle",     ("Jb", None, None), ()),
    Insn("jg",      ("Jb", None, None), ()),
    # 80
    None, # ModRM opcode group 1
    None, # ModRM opcode group 1
    None, # ModRM opcode group 1
    None, # ModRM opcode group 1
    Insn("test",    ("Eb", "Gb", None), ()),
    Insn("test",    ("Ev", "Gv", None), ()),
    Insn("xchg",    ("Eb", "Gb", None), ()),
    Insn("xchg",    ("Ev", "Gv", None), ()),
    # 88
    Insn("mov",     ("Eb", "Gb", None), ()),
    Insn("mov",     ("Ev", "Gv", None), ()),
    Insn("mov",     ("Gb", "Eb", None), ()),
    Insn("mov",     ("Gv", "Ev", None), ()),
    Insn("mov",     ("Ev", "Sw", None), ()),
    Insn("lea",     ("Ev", "M", None), ()),
    Insn("mov",     ("Sw", "Ew", None), ()),
    None, # ModRM opcode group 1A
    # 90
    Insn("nop",     (None, None, None), ()),
    Insn("xchg",    ("ecx", "eax", None), ()),
    Insn("xchg",    ("edx", "eax", None), ()),
    Insn("xchg",    ("ebx", "eax", None), ()),
    Insn("xchg",    ("esp", "eax", None), ()),
    Insn("xchg",    ("ebp", "eax", None), ()),
    Insn("xchg",    ("esi", "eax", None), ()),
    Insn("xchg",    ("edi", "eax", None), ()),
    # 98
    Insn("cwde",    (None, None, None), ()),
    Insn("cdq",     (None, None, None), ()),
    Insn("callf",   ("Ap", None, None), ()),
    Insn("wait",    (None, None, None), ()),
    Insn("pushf",   ("Fv", None, None), ()),
    Insn("popf",    ("Fv", None, None), ()),
    Insn("sahf",    (None, None, None), ()),
    Insn("lahf",    (None, None, None), ()),
    # A0
    Insn("mov",     ("al", "Ob", None), ()),
    Insn("mov",     ("eax", "Ov", None), ()),
    Insn("mov",     ("Ob", "al", None), ()),
    Insn("mov",     ("Ov", "eax", None), ()),
    Insn("movs",    ("Yb", "Xb", None), ()),
    Insn("movs",    ("Yv", "Xv", None), ()),
    Insn("cmps",    ("Xb", "Yb", None), ()),
    Insn("cmps",    ("Xv", "Yv", None), ()),
    # A8
    Insn("test",    ("al", "Ib", None), ()),
    Insn("test",    ("eax", "Iz", None), ()),
    Insn("stos",    ("Yb", "al", None), ()),
    Insn("stos",    ("Yv", "eax", None), ()),
    Insn("lods",    ("al", "Xb", None), ()),
    Insn("lods",    ("eax", "Xv", None), ()),
    Insn("scas",    ("al", "Xb", None), ()),
    Insn("scas",    ("eax", "Xv", None), ()),
    # B0(
    Insn("mov",     ("al", "Ib", None), ()),
    Insn("mov",     ("cl", "Ib", None), ()),
    Insn("mov",     ("dl", "Ib", None), ()),
    Insn("mov",     ("bl", "Ib", None), ()),
    Insn("mov",     ("ah", "Ib", None), ()),
    Insn("mov",     ("ch", "Ib", None), ()),
    Insn("mov",     ("dh", "Ib", None), ()),
    Insn("mov",     ("bh", "Ib", None), ()),
    # B8
    Insn("mov",     ("eax", "Iv", None), ()),
    Insn("mov",     ("ecx", "Iv", None), ()),
    Insn("mov",     ("edx", "Iv", None), ()),
    Insn("mov",     ("ebx", "Iv", None), ()),
    Insn("mov",     ("esp", "Iv", None), ()),
    Insn("mov",     ("ebp", "Iv", None), ()),
    Insn("mov",     ("esi", "Iv", None), ()),
    Insn("mov",     ("edi", "Iv", None), ()),
    # C0
    None, # ModRM opcode group 2
    None, # ModRM opcode group 2
    Insn("retn",    ("Iw", None, None), ()),
    Insn("retn",    (None, None, None), ()),
    Insn("les",     ("Gz", "Mp", None), ()),
    Insn("lds",     ("Gz", "Mp", None), ()),
    None, # ModRM opcode group 11
    None, # ModRM opcode group 11
    # C8
    Insn("enter",   ("Iw", "Ib", None), ()),
    Insn("leave",   (None, None, None), ()),
    Insn("retf",    ("Iw", None, None), ()),
    Insn("retf",    (None, None, None), ()),
    Insn("int3",    (None, None, None), ()),
    Insn("int",     ("Ib", None, None, None), ()),
    Insn("into",    (None, None, None), ()),
    Insn("iret",    (None, None, None), ()),
    # D0
    None, # ModRM opcode group 2
    None, # ModRM opcode group 2
    None, # ModRM opcode group 2
    None, # ModRM opcode group 2
    Insn("aam",     ("Ib", None, None), ()),
    Insn("aad",     ("Ib", None, None), ()),
    _invalidOpcode,
    Insn("xlat",    (None, None, None), ()),
    # D8
    None, # FPU escape
    None, # FPU escape
    None, # FPU escape
    None, # FPU escape
    None, # FPU escape
    None, # FPU escape
    None, # FPU escape
    None, # FPU escape
    # E0
    Insn("loopnz",  ("Jb", None, None), ()),
    Insn("loopz",   ("Jb", None, None), ()),
    Insn("loop",    ("Jb", None, None), ()),
    Insn("jcxz",    ("Jb", None, None), ()),
    Insn("in",      ("al", "Ib", None), ()),
    Insn("in",      ("eax", "Ib", None), ()),
    Insn("out",     ("Ib", "al", None), ()),
    Insn("out",     ("Ib", "eax", None), ()),
    # E8
    Insn("call",    ("Jz", None, None), ()),
    Insn("jmp",     ("Jz", None, None), ()),
    Insn("jmp",     ("Ap", None, None), ()),
    Insn("jmp",     ("Jb", None, None), ()),
    Insn("in",      ("al", "dx", None), ()),
    Insn("in",      ("eax", "dx", None), ()),
    Insn("out",     ("dx", "al", None), ()),
    Insn("out",     ("dx", "eax", None), ()),
    # F0
    None, # LOCK prefix
    _invalidOpcode,
    None, # REPNE prefix
    None, # REPE prefix
    Insn("hlt",     (None, None, None), ()),
    Insn("cmc",     (None, None, None), ()),
    None, # ModRM opcode group 3
    None, # ModRM opcode group 3
    # F8
    Insn("clc",     (None, None, None), ()),
    Insn("stc",     (None, None, None), ()),
    Insn("cli",     (None, None, None), ()),
    Insn("sti",     (None, None, None), ()),
    Insn("cld",     (None, None, None), ()),
    Insn("std",     (None, None, None), ()),
    None, # ModRM opcode group 4
    None) # ModRM opcode group 5
#
