
class Error(Exception):
    """Base class for errors raised in this module."""
    pass

class InvalidOpcodeError(Error):
    """Opcode is marked invalid."""
    pass

class UnknownOpcodeError(Error):
    """Opcode is not marked invalid, but I don't know it."""
    pass

class Immediate:
    def __init__(self, value, size):
        self.size = size # Data width, bits
        self.value = long(value)
#
class MemoryRef:
    def __init__(self, size, base=None, index=None, scale=1, displ=None):
        self.size = size # Data width, bits
        self.base = base
        self.index = index
        self.scale = scale
        self.displ = displ
#
class Register:
    def __init__(self, name, size):
        self.size = size # Data width, bits
        self.name = name
#

_register_map = {
    "rax": Register("rax", 3),
    "rcx": Register("rcx", 3),
    "rdx": Register("rdx", 3),
    "rbx": Register("rbx", 3),
    "rsp": Register("rsp", 3),
    "rbp": Register("rbp", 3),
    "rsi": Register("rsi", 3),
    "rdi": Register("rdi", 3),
    "eax": Register("eax", 2),
    "ecx": Register("ecx", 2),
    "edx": Register("edx", 2),
    "ebx": Register("ebx", 2),
    "esp": Register("esp", 2),
    "ebp": Register("ebp", 2),
    "esi": Register("esi", 2),
    "edi": Register("edi", 2),
    "ax": Register("ax", 1),
    "cx": Register("cx", 1),
    "dx": Register("dx", 1),
    "bx": Register("bx", 1),
    "sp": Register("sp", 1),
    "bp": Register("bp", 1),
    "si": Register("si", 1),
    "di": Register("di", 1),
    "al": Register("al", 0),
    "cl": Register("cl", 0),
    "dl": Register("dl", 0),
    "bl": Register("bl", 0),
    "ah": Register("ah", 0),
    "ch": Register("ch", 0),
    "dh": Register("dh", 0),
    "bh": Register("bh", 0),
    "es": Register("es", 1),
    "cs": Register("cs", 1),
    "ss": Register("ss", 1),
    "ds": Register("ds", 1),
    "fs": Register("fs", 1),
    "gs": Register("gs", 1),
    "dr0": Register("dr0", 2),
    "dr1": Register("dr1", 2),
    "dr2": Register("dr2", 2),
    "dr3": Register("dr3", 2),
    "dr6": Register("dr6", 2),
    "dr7": Register("dr7", 2),
    "cr0": Register("cr0", 2),
    "cr2": Register("cr2", 2),
    "cr3": Register("cr3", 2),
    "cr4": Register("cr4", 2),
    }
_r8_decode = (
    _register_map["al"], _register_map["cl"], _register_map["dl"], _register_map["bl"],
    _register_map["ah"], _register_map["ch"], _register_map["dh"], _register_map["bh"])
_r16_decode = (
    _register_map["ax"], _register_map["cx"], _register_map["dx"], _register_map["bx"],
    _register_map["sp"], _register_map["bp"], _register_map["si"], _register_map["di"])
_r32_decode = (
    _register_map["eax"], _register_map["ecx"], _register_map["edx"], _register_map["ebx"],
    _register_map["esp"], _register_map["ebp"], _register_map["esi"], _register_map["edi"])
_r64_decode = (
    _register_map["rax"], _register_map["rcx"], _register_map["rdx"], _register_map["rbx"],
    _register_map["rsp"], _register_map["rbp"], _register_map["rsi"], _register_map["rdi"])
_rseg_decode = (
    _register_map["es"], _register_map["cs"], _register_map["ss"], _register_map["ds"],
    _register_map["fs"], _register_map["gs"], None, None)
_rdebug_decode = (
    _register_map["dr0"], _register_map["dr1"], _register_map["dr2"], _register_map["dr3"],
    None, None, _register_map["dr6"], _register_map["dr7"])
_rcontrol_decode = (
    _register_map["cr0"], None, _register_map["cr2"], _register_map["cr3"],
    _register_map["cr4"], None, None, None)

class State:
    def __init__(self, reader):
        self.reader = reader
        # Opcode bytes so far
        self.opcode = ""
        # ModRM byte fetched
        self.modrm = None
        # SIB byte fetched
        self.sib = None
        self.disp = None
        self.imm = None
        
        # 0 = 8; 1 = 16; 2 = 32; 3 = 64
        self.bitness = 2
        self.operand_width = self.bitness
        self.address_width = self.bitness
        
        self.seg_override = None
        self.prefix_66 = False # Operand size
        self.prefix_67 = False # Address size
        self.prefix_F2 = False # REPNE
        self.prefix_F3 = False # REPE
        
    def fetch_opcode(self):
        b = self.reader.read()
        self.opcode += b
        return b
    def fetch_modrm(self):
        if self.modrm is None:
            modrm = self.fetch_opcode()
            self.modrm = modrm
            self.modrm_mod = modrm >> 6
            self.modrm_reg = (modrm >> 3) & 0x07
            self.modrm_rm = modrm & 0x07
        return self.modrm
    def fetch_sib(self):
        if self.sib is None:
            sib = self.fetch_opcode()
            self.sib = sib
            self.sib_scale = sib >> 6
            self.sib_index = (sib >> 3) & 0x07
            self.sib_base = sib & 0x07
        return self.sib
    def fetch_mp(self, size):
        d = 0L
        d |= self.reader.read()
        if size >= 1:
            d |= self.reader.read() << 8
        if size >= 2:
            d |= (self.reader.read() << 16)
            d |= (self.reader.read() << 24)
        return d
#

class InvalidOpcode:
    def __call__(self, state):
        raise InvalidOpcodeError()
_invalidOpcode = InvalidOpcode()

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

class SwitchOpcode:
    """Table switch based on insn opcode byte"""
    def __init__(self, entries):
        self.entries = entries
        
    def __call__(self, state):
        b = state.fetch_opcode()
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
def _check_imm(code):
    return code[0] == "I"

_modrm_lookup_16 = (
    # base, index, displacement size
    (_register_map['bx'], _register_map['si'], 0),
    (_register_map['bx'], _register_map['di'], 0),
    (_register_map['bp'], _register_map['si'], 0),
    (_register_map['bp'], _register_map['di'], 0),
    (               None, _register_map['si'], 0),
    (               None, _register_map['si'], 0),
    (               None,                None, 16),
    (_register_map['bx'],                None, 0),
    
    (_register_map['bx'], _register_map['si'], 8),
    (_register_map['bx'], _register_map['di'], 8),
    (_register_map['bp'], _register_map['si'], 8),
    (_register_map['bp'], _register_map['di'], 8),
    (               None, _register_map['si'], 8),
    (               None, _register_map['si'], 8),
    (_register_map['bp'],                None, 8),
    (_register_map['bx'],                None, 8),
    
    (_register_map['bx'], _register_map['si'], 16),
    (_register_map['bx'], _register_map['di'], 16),
    (_register_map['bp'], _register_map['si'], 16),
    (_register_map['bp'], _register_map['di'], 16),
    (               None, _register_map['si'], 16),
    (               None, _register_map['si'], 16),
    (_register_map['bp'],                None, 16),
    (_register_map['bx'],                None, 16))
_modrm_lookup_32 = (
    # base, displacement size
    (_register_map['eax'],  0),
    (_register_map['ecx'],  0),
    (_register_map['edx'],  0),
    (_register_map['ebx'],  0),
    (                None,  0),
    (                None, 32),
    (_register_map['esi'],  0),
    (_register_map['edi'],  0),

    (_register_map['eax'],  8),
    (_register_map['ecx'],  8),
    (_register_map['edx'],  8),
    (_register_map['ebx'],  8),
    (                None,  8),
    (_register_map['ebp'],  8),
    (_register_map['esi'],  8),
    (_register_map['edi'],  8),

    (_register_map['eax'], 32),
    (_register_map['ecx'], 32),
    (_register_map['edx'], 32),
    (_register_map['ebx'], 32),
    (                None, 32),
    (_register_map['ebp'], 32),
    (_register_map['esi'], 32),
    (_register_map['edi'], 32))
_sib_index_lookup = (
    _register_map['eax'],
    _register_map['ecx'],
    _register_map['edx'],
    _register_map['ebx'],
                    None,
    _register_map['ebp'],
    _register_map['esi'],
    _register_map['edi'])
_sib_base_lookup_mod0 = (
    _register_map['eax'],
    _register_map['ecx'],
    _register_map['edx'],
    _register_map['ebx'],
    _register_map['esp'],
                    None,
    _register_map['esi'],
    _register_map['edi'])
_sib_base_lookup_mod12 = (
    _register_map['eax'],
    _register_map['ecx'],
    _register_map['edx'],
    _register_map['ebx'],
    _register_map['esp'],
    _register_map['ebp'],
    _register_map['esi'],
    _register_map['edi'])
_gpr_decode = (
    _r8_decode,
    _r16_decode,
    _r32_decode,
    _r64_decode)
    
def _decode_reg(size, num):
    return _gpr_decode[size][num]
def _decode_E(state, size):
    if state.modrm_mod == 3:
        return _decode_reg(size, state.modrm_reg)
    else:
        b = None
        i = None
        s = 1
        d = None
        mod_rm = (state.modrm_mod << 3) + state.modrm_rm
        if state.address_width = 1:
            l = _modrm_lookup_16[mod_rm]
            d_size = l[2]
            b = l[0]
            i = l[1]
        else:
            l = _modrm_lookup_32[mod_rm]
            d_size = l[1]
            if state.modrm_rm == 4:
                # SIB
                scale = 1 << state.sib_scale
                index = _sib_index_lookup[state.sib_index]
                if state.modrm_mod == 0:
                    base = _sib_base_lookup_mod0[state.sib_base]
                else:
                    base = _sib_base_lookup_mod12[state.sib_base]
            else:
                b = l[0]
        if d_size > 0:
            d = Immediate(state.fetch_mp(d_size), d_size)
        return MemoryRef(size, base=b, index=i, scale=s, displ=d)
def _decode_Eb(state):
    return _decode_E(state, 0)
def _decode_Ew(state):
    return _decode_E(state, 1)
def _decode_Ev(state):
    return _decode_E(state, state.operand_width)
def _decode_Ew(state):
    # FIXME: 64-bit
    return _decode_E(state, 2)
    
def _decode_Gb(state):
    return _r8_decode[state.modrm_reg]
def _decode_Gv(state):
    return _decode_reg(state.operand_width, state.modrm_reg)
def _decode_Gy(state):
    # FIXME: 64-bit
    return _r32_decode[state.modrm_reg]

def _decode_Rd(state):
    # The R/M field of the ModR/M byte may refer only to a general register.
    if state.modrm_mod != 3:
        raise InvalidOpcodeError()
    return _r32_decode[state.modrm_rm]

def _decode_Cd(state):
    r = _rcontrol_decode[state.modrm_reg]
    if r is None:
        raise InvalidOpcodeError()
    return r

def _decode_Dd(state):
    r = _rdebug_decode[state.modrm_reg]
    if r is None:
        raise InvalidOpcodeError()
    return r

def _decode_Jb(state):
    raise UnknownOpcodeError()
def _decode_Jz(state):
    raise UnknownOpcodeError()
def _decode_Ib(state):
    raise UnknownOpcodeError()
def _decode_Iw(state):
    raise UnknownOpcodeError()
def _decode_Iz(state):
    raise UnknownOpcodeError()

class OpDecoder:
    def __init__(self, operands):
        self.op_spec = operands

    def __call__(self, state):
        # Apply operand/address size modifiers
        if state.prefix_66:
            state.operand_width = 1 if state.operand_width != 1 else 2
        if state.prefix_67:
            state.address_width = 1 if state.address_width != 1 else 2
        
        # Check and parse ModR/M
        modrm_needed = (_check_modrm(self.op_spec[0])
            or _check_modrm(self.op_spec[1])
            or _check_modrm(self.op_spec[2]))
        if modrm_needed:
            state.fetch_modrm()
        
        # Check and parse SIB
        sib_needed = state.address_width == 2 and state.mod != 3 and state.regmem == 4
        if sib_needed:
            state.fetch_sib()
            

    def _decode_op(self, state, op, flags):
        amode = op[0]
        if amode.isupper():
            if op == 'Gv':
                return _decode_Gv(state)
            if op == 'Gb':
                return _decode_Gb(state)
            raise UnknownOpcodeError()
        else:
            # Must be a register reference
            if op[0] == '?':
                # Can choose based on current operand size
                op = ('', 'e', 'r')[state.operand_width] + op[1:]
            return _register_map[op]
    
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
        # ModR/M (if present)
        # SIB (if present)
        # Displacement (if required by ModR/M or SIB)
        # Immediate
        pass
#

decode_0F_32 = SwitchOpcode(
    # 00
    None, # ModRM opcode group 6
    None, # ModRM opcode group 7
    Insn("lar",     ("Gv", "Ew"), ()),
    Insn("lsl",     ("Gv", "Ew"), ()),
    _invalidOpcode,
    _invalidOpcode, # SYSCALL -- only 64-bit
    Insn("clts",    (), ()),
    _invalidOpcode, # SYSRET -- only 64-bit
    # 08
    Insn("invd",    (), ()),
    Insn("wbinvd",  (), ()),
    _invalidOpcode,
    Insn("ud2",     (), ()),
    _invalidOpcode,
    Insn("prefetchw", ("Ev"), ()),
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
    Insn("nop",     ("Ev"), ()),
    # 20
    Insn("mov",     ("Rd", "Cd"), ()),
    Insn("mov",     ("Rd", "Dd"), ()),
    Insn("mov",     ("Cd", "Rd"), ()),
    Insn("mov",     ("Dd", "Rd"), ()),
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 28
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 30
    Insn("wrmsr",   (), ()),
    Insn("rdtsc",   (), ()),
    Insn("rdmsr",   (), ()),
    Insn("rdpmc",   (), ()),
    Insn("sysenter", (), ()),
    Insn("sysexit", (), ()),
    _invalidOpcode,
    Insn("getsec",  (), ()),
    # 38
    None, # Escape 0F38
    _invalidOpcode,
    None, # Escape 0F3A
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 40
    Insn("cmovo",   ("Gv", "Ev"), ()),
    Insn("cmovno",  ("Gv", "Ev"), ()),
    Insn("cmovb",   ("Gv", "Ev"), ()),
    Insn("cmovae",  ("Gv", "Ev"), ()),
    Insn("cmove",   ("Gv", "Ev"), ()),
    Insn("cmovne",  ("Gv", "Ev"), ()),
    Insn("cmovbe",  ("Gv", "Ev"), ()),
    Insn("cmova",   ("Gv", "Ev"), ()),
    # 48
    Insn("cmovs",   ("Gv", "Ev"), ()),
    Insn("cmovns",  ("Gv", "Ev"), ()),
    Insn("cmovp",   ("Gv", "Ev"), ()),
    Insn("cmovnp",  ("Gv", "Ev"), ()),
    Insn("cmovl",   ("Gv", "Ev"), ()),
    Insn("cmovge",  ("Gv", "Ev"), ()),
    Insn("cmovle",  ("Gv", "Ev"), ()),
    Insn("cmovg",   ("Gv", "Ev"), ()),
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
    Insn("vmread",  ("Ey", "Gy"), ()),
    Insn("vmwrite", ("Gy", "Ey"), ()),
    _invalidOpcode,
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 80
    Insn("jo",      ("Jz"), ()),
    Insn("jno",     ("Jz"), ()),
    Insn("jb",      ("Jz"), ()),
    Insn("jae",     ("Jz"), ()),
    Insn("je",      ("Jz"), ()),
    Insn("jne",     ("Jz"), ()),
    Insn("jbe",     ("Jz"), ()),
    Insn("ja",      ("Jz"), ()),
    # 88
    Insn("js",      ("Jz"), ()),
    Insn("jns",     ("Jz"), ()),
    Insn("jp",      ("Jz"), ()),
    Insn("jnp",     ("Jz"), ()),
    Insn("jl",      ("Jz"), ()),
    Insn("jge",     ("Jz"), ()),
    Insn("jle",     ("Jz"), ()),
    Insn("jg",      ("Jz"), ()),
    # 90
    Insn("seto",    ("Eb"), ()),
    Insn("setno",   ("Eb"), ()),
    Insn("setb",    ("Eb"), ()),
    Insn("setae",   ("Eb"), ()),
    Insn("sete",    ("Eb"), ()),
    Insn("setne",   ("Eb"), ()),
    Insn("setbe",   ("Eb"), ()),
    Insn("seta",    ("Eb"), ()),
    # 98
    Insn("sets",    ("Eb"), ()),
    Insn("setns",   ("Eb"), ()),
    Insn("setp",    ("Eb"), ()),
    Insn("setnp",   ("Eb"), ()),
    Insn("setl",    ("Eb"), ()),
    Insn("setge",   ("Eb"), ()),
    Insn("setle",   ("Eb"), ()),
    Insn("setg",    ("Eb"), ()),
    # A0
    Insn("push",    ("fs"), ()),
    Insn("pop",     ("fs"), ()),
    Insn("cpuid",   (), ()),
    Insn("bt",      ("Ev", "Gv"), ()),
    Insn("shld",    ("Ev", "Gv", "Ib", ()),
    Insn("shld",    ("Ev", "Gv", "cl", ()),
    _invalidOpcode,
    _invalidOpcode,
    # A8
    Insn("push",    ("gs"), ()),
    Insn("pop",     ("gs"), ()),
    Insn("rsm",     (), ()),
    Insn("bts",     ("Ev", "Gv"), ()),
    Insn("shrd",    ("Ev", "Gv", "Ib", ()),
    Insn("shrd",    ("Ev", "Gv", "cl", ()),
    None, # Group 15
    Insn("imul",    ("Gv", "Ev"), ()),
    # B0
    Insn("cmpxchg", ("Eb", "Gb"), ()),
    Insn("cmpxchg", ("Ev", "Gv"), ()),
    Insn("lss",     ("Gv", "Mp"), ()),
    Insn("btr",     ("Ev", "Gv"), ()),
    Insn("lfs",     ("Gv", "Mp"), ()),
    Insn("lgs",     ("Gv", "Mp"), ()),
    Insn("movzx",   ("Gv", "Eb"), ()),
    Insn("movzx",   ("Gv", "Ew"), ()),
    # B8
    _invalidOpcode,
    None, # ModRM opcode group 10 ?
    None, # ModRM opcode group 8
    Insn("btc",     ("Ev", "Gv"), ()),
    Insn("bsf",     ("Gv", "Ev"), ()),
    Insn("bsr",     ("Gv", "Ev"), ()),
    Insn("movsx",   ("Gv", "Eb"), ()),
    Insn("movsx",   ("Gv", "Ew"), ()),
    # C0
    Insn("xadd",    ("Eb", "Gb"), ()),
    Insn("xadd",    ("Ev", "Gv"), ()),
    _invalidOpcode,
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # C8
    Insn("bswap",   ("eax"), ("no66")),
    Insn("bswap",   ("ecx"), ("no66")),
    Insn("bswap",   ("edx"), ("no66")),
    Insn("bswap",   ("ebx"), ("no66")),
    Insn("bswap",   ("esp"), ("no66")),
    Insn("bswap",   ("ebp"), ("no66")),
    Insn("bswap",   ("esi"), ("no66")),
    Insn("bswap",   ("edi"), ("no66")),
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
    Insn("add",     ("Eb", "Gb"), ()),
    Insn("add",     ("Ev", "Gv"), ("allow66")),
    Insn("add",     ("Gb", "Eb"), ()),
    Insn("add",     ("Gv", "Ev"), ("allow66")),
    Insn("add",     ("al", "Ib"), ()),
    Insn("add",     ("?ax", "Iz"), ("allow66")),
    Insn("push",    ("es"), ()), # invalid in x64
    Insn("pop",     ("es"), ()), # invalid in x64
    # 08
    Insn("or",      ("Eb", "Gb"), ()),
    Insn("or",      ("Ev", "Gv"), ("allow66")),
    Insn("or",      ("Gb", "Eb"), ()),
    Insn("or",      ("Gv", "Ev"), ("allow66")),
    Insn("or",      ("al", "Ib"), ()),
    Insn("or",      ("?ax", "Iz"), ("allow66")),
    Insn("push",    ("cs"), ()), # invalid in x64
    decode_0F_32, # Escape 0F
    # 10
    Insn("adc",     ("Eb", "Gb"), ()),
    Insn("adc",     ("Ev", "Gv"), ("allow66")),
    Insn("adc",     ("Gb", "Eb"), ()),
    Insn("adc",     ("Gv", "Ev"), ("allow66")),
    Insn("adc",     ("al", "Ib"), ()),
    Insn("adc",     ("?ax", "Iz"), ("allow66")),
    Insn("push",    ("ss"), ()), # invalid in x64
    Insn("pop",     ("ss"), ()), # invalid in x64
    # 18
    Insn("sbb",     ("Eb", "Gb"), ()),
    Insn("sbb",     ("Ev", "Gv"), ("allow66")),
    Insn("sbb",     ("Gb", "Eb"), ()),
    Insn("sbb",     ("Gv", "Ev"), ("allow66")),
    Insn("sbb",     ("al", "Ib"), ()),
    Insn("sbb",     ("?ax", "Iz"), ("allow66")),
    Insn("push",    ("ds"), ()), # invalid in x64
    Insn("pop",     ("ds"), ()), # invalid in x64
    # 20
    Insn("and",     ("Eb", "Gb"), ()),
    Insn("and",     ("Ev", "Gv"), ("allow66")),
    Insn("and",     ("Gb", "Eb"), ()),
    Insn("and",     ("Gv", "Ev"), ("allow66")),
    Insn("and",     ("al", "Ib"), ()),
    Insn("and",     ("?ax", "Iz"), ("allow66")),
    SegmentOverridePrefix("es"),
    Insn("daa",     (), ()),
    # 28
    Insn("sub",     ("Eb", "Gb",), ()),
    Insn("sub",     ("Ev", "Gv"), ("allow66")),
    Insn("sub",     ("Gb", "Eb"), ()),
    Insn("sub",     ("Gv", "Ev"), ("allow66")),
    Insn("sub",     ("al", "Ib"), ()),
    Insn("sub",     ("?ax", "Iz"), ("allow66")),
    SegmentOverridePrefix("cs"),
    Insn("das",     (), ()),
    # 30
    Insn("xor",     ("Eb", "Gb"), ()),
    Insn("xor",     ("Ev", "Gv"), ("allow66")),
    Insn("xor",     ("Gb", "Eb"), ()),
    Insn("xor",     ("Gv", "Ev"), ("allow66")),
    Insn("xor",     ("al", "Ib"), ()),
    Insn("xor",     ("?ax", "Iz"), ("allow66")),
    SegmentOverridePrefix("ss"),
    Insn("aaa",     (), ()),
    # 38
    Insn("cmp",     ("Eb", "Gb"), ()),
    Insn("cmp",     ("Ev", "Gv"), ("allow66")),
    Insn("cmp",     ("Gb", "Eb"), ()),
    Insn("cmp",     ("Gv", "Ev"), ("allow66")),
    Insn("cmp",     ("al", "Ib"), ()),
    Insn("cmp",     ("?ax", "Iz"), ("allow66")),
    SegmentOverridePrefix("ds"),
    Insn("aas",     (), ()),
    # 40
    Insn("inc",     ("?ax"), ("allow66")),
    Insn("inc",     ("?cx"), ("allow66")),
    Insn("inc",     ("?dx"), ("allow66")),
    Insn("inc",     ("?bx"), ("allow66")),
    Insn("inc",     ("?sp"), ("allow66")),
    Insn("inc",     ("?bp"), ("allow66")),
    Insn("inc",     ("?si"), ("allow66")),
    Insn("inc",     ("?di"), ("allow66")),
    # 48
    Insn("dec",     ("?ax"), ("allow66")),
    Insn("dec",     ("?cx"), ("allow66")),
    Insn("dec",     ("?dx"), ("allow66")),
    Insn("dec",     ("?bx"), ("allow66")),
    Insn("dec",     ("?sp"), ("allow66")),
    Insn("dec",     ("?bp"), ("allow66")),
    Insn("dec",     ("?si"), ("allow66")),
    Insn("dec",     ("?di"), ("allow66")),
    # 50
    Insn("push",    ("?ax"), ("allow66")),
    Insn("push",    ("?cx"), ("allow66")),
    Insn("push",    ("?dx"), ("allow66")),
    Insn("push",    ("?bx"), ("allow66")),
    Insn("push",    ("?sp"), ("allow66")),
    Insn("push",    ("?bp"), ("allow66")),
    Insn("push",    ("?si"), ("allow66")),
    Insn("push",    ("?di"), ("allow66")),
    # 58
    Insn("pop",     ("?ax"), ("allow66")),
    Insn("pop",     ("?cx"), ("allow66")),
    Insn("pop",     ("?dx"), ("allow66")),
    Insn("pop",     ("?bx"), ("allow66")),
    Insn("pop",     ("?sp"), ("allow66")),
    Insn("pop",     ("?bp"), ("allow66")),
    Insn("pop",     ("?si"), ("allow66")),
    Insn("pop",     ("?di"), ("allow66")),
    # 60
    Insn("pusha",   (), ()), # invalid in x64
    Insn("popa",    (), ()), # invalid in x64
    Insn("bound",   ("Gv", "Ma"), ()), # invalid in x64
    Insn("arpl",    ("Ew", "Gw"), ()),
    SegmentOverridePrefix("fs"),
    SegmentOverridePrefix("gs"),
    OperandSizePrefix(),
    AddressSizePrefix(),
    # 68
    Insn("push",    ("Iz"), ("allow66")),
    Insn("imul",    ("Gv", "Ev", "Iz", ("allow66")),
    Insn("push",    ("Ib"), ()),
    Insn("imul",    ("Gv", "Ev", "Ib", ("allow66")),
    Insn("ins",     ("Yb", "dx"), ()),
    Insn("ins",     ("Yz", "dx"), ("allow66")),
    Insn("outs",    ("dx", "Xb"), ()),
    Insn("outs",    ("dx", "Xz"), ("allow66")),
    # 70
    Insn("jo",      ("Jb"), ()),
    Insn("jno",     ("Jb"), ()),
    Insn("jb",      ("Jb"), ()),
    Insn("jae",     ("Jb"), ()),
    Insn("je",      ("Jb"), ()),
    Insn("jne",     ("Jb"), ()),
    Insn("jbe",     ("Jb"), ()),
    Insn("ja",      ("Jb"), ()),
    # 78
    Insn("js",      ("Jb"), ()),
    Insn("jns",     ("Jb"), ()),
    Insn("jp",      ("Jb"), ()),
    Insn("jnp",     ("Jb"), ()),
    Insn("jl",      ("Jb"), ()),
    Insn("jge",     ("Jb"), ()),
    Insn("jle",     ("Jb"), ()),
    Insn("jg",      ("Jb"), ()),
    # 80
    None, # ModRM opcode group 1
    None, # ModRM opcode group 1
    None, # ModRM opcode group 1
    None, # ModRM opcode group 1
    Insn("test",    ("Eb", "Gb"), ()),
    Insn("test",    ("Ev", "Gv"), ("allow66")),
    Insn("xchg",    ("Eb", "Gb"), ()),
    Insn("xchg",    ("Ev", "Gv"), ("allow66")),
    # 88
    Insn("mov",     ("Eb", "Gb"), ()),
    Insn("mov",     ("Ev", "Gv"), ("allow66")),
    Insn("mov",     ("Gb", "Eb"), ()),
    Insn("mov",     ("Gv", "Ev"), ("allow66")),
    Insn("mov",     ("Ev", "Sw"), ("allow66")),
    Insn("lea",     ("Ev", "M"), ("allow66")),
    Insn("mov",     ("Sw", "Ew"), ("allow66")),
    None, # ModRM opcode group 1A
    # 90
    Insn("nop",     (), ()),
    Insn("xchg",    ("?cx", "?ax"), ("allow66")),
    Insn("xchg",    ("?dx", "?ax"), ("allow66")),
    Insn("xchg",    ("?bx", "?ax"), ("allow66")),
    Insn("xchg",    ("?sp", "?ax"), ("allow66")),
    Insn("xchg",    ("?bp", "?ax"), ("allow66")),
    Insn("xchg",    ("?si", "?ax"), ("allow66")),
    Insn("xchg",    ("?di", "?ax"), ("allow66")),
    # 98
    Insn("cwde",    (), ()),
    Insn("cdq",     (), ()),
    Insn("callf",   ("Ap"), ()),
    Insn("wait",    (), ()),
    Insn("pushf",   ("Fv"), ()),
    Insn("popf",    ("Fv"), ()),
    Insn("sahf",    (), ()),
    Insn("lahf",    (), ()),
    # A0
    Insn("mov",     ("al", "Ob"), ()),
    Insn("mov",     ("?ax", "Ov"), ("allow66")),
    Insn("mov",     ("Ob", "al"), ()),
    Insn("mov",     ("Ov", "?ax"), ("allow66")),
    Insn("movs",    ("Yb", "Xb"), ()),
    Insn("movs",    ("Yv", "Xv"), ("allow66")),
    Insn("cmps",    ("Xb", "Yb"), ()),
    Insn("cmps",    ("Xv", "Yv"), ("allow66")),
    # A8
    Insn("test",    ("al", "Ib"), ()),
    Insn("test",    ("?ax", "Iz"), ("allow66")),
    Insn("stos",    ("Yb", "al"), ()),
    Insn("stos",    ("Yv", "?ax"), ("allow66")),
    Insn("lods",    ("al", "Xb"), ()),
    Insn("lods",    ("?ax", "Xv"), ("allow66")),
    Insn("scas",    ("al", "Xb"), ()),
    Insn("scas",    ("?ax", "Xv"), ("allow66")),
    # B0(
    Insn("mov",     ("al", "Ib"), ()),
    Insn("mov",     ("cl", "Ib"), ()),
    Insn("mov",     ("dl", "Ib"), ()),
    Insn("mov",     ("bl", "Ib"), ()),
    Insn("mov",     ("ah", "Ib"), ()),
    Insn("mov",     ("ch", "Ib"), ()),
    Insn("mov",     ("dh", "Ib"), ()),
    Insn("mov",     ("bh", "Ib"), ()),
    # B8
    Insn("mov",     ("?ax", "Iv"), ("allow66")),
    Insn("mov",     ("?cx", "Iv"), ("allow66")),
    Insn("mov",     ("?dx", "Iv"), ("allow66")),
    Insn("mov",     ("?bx", "Iv"), ("allow66")),
    Insn("mov",     ("?sp", "Iv"), ("allow66")),
    Insn("mov",     ("?bp", "Iv"), ("allow66")),
    Insn("mov",     ("?si", "Iv"), ("allow66")),
    Insn("mov",     ("?di", "Iv"), ("allow66")),
    # C0
    None, # ModRM opcode group 2
    None, # ModRM opcode group 2
    Insn("retn",    ("Iw"), ()),
    Insn("retn",    (), ()),
    Insn("les",     ("Gz", "Mp"), ("allow66")),
    Insn("lds",     ("Gz", "Mp"), ("allow66")),
    None, # ModRM opcode group 11
    None, # ModRM opcode group 11
    # C8
    Insn("enter",   ("Iw", "Ib"), ()),
    Insn("leave",   (), ()),
    Insn("retf",    ("Iw"), ()),
    Insn("retf",    (), ()),
    Insn("int3",    (), ()),
    Insn("int",     ("Ib"), ()),
    Insn("into",    (), ()),
    Insn("iret",    (), ()),
    # D0
    None, # ModRM opcode group 2
    None, # ModRM opcode group 2
    None, # ModRM opcode group 2
    None, # ModRM opcode group 2
    Insn("aam",     ("Ib"), ()),
    Insn("aad",     ("Ib"), ()),
    _invalidOpcode,
    Insn("xlat",    (), ()),
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
    Insn("loopnz",  ("Jb"), ()),
    Insn("loopz",   ("Jb"), ()),
    Insn("loop",    ("Jb"), ()),
    Insn("jcxz",    ("Jb"), ()),
    Insn("in",      ("al", "Ib"), ()),
    Insn("in",      ("?ax", "Ib"), ("allow66")),
    Insn("out",     ("Ib", "al"), ()),
    Insn("out",     ("Ib", "?ax"), ("allow66")),
    # E8
    Insn("call",    ("Jz"), ()),
    Insn("jmp",     ("Jz"), ()),
    Insn("jmp",     ("Ap"), ()),
    Insn("jmp",     ("Jb"), ()),
    Insn("in",      ("al", "dx"), ()),
    Insn("in",      ("?ax", "dx"), ("allow66")),
    Insn("out",     ("dx", "al"), ()),
    Insn("out",     ("dx", "?ax"), ("allow66")),
    # F0
    None, # LOCK prefix
    _invalidOpcode,
    None, # REPNE prefix
    None, # REPE prefix
    Insn("hlt",     (), ()),
    Insn("cmc",     (), ()),
    None, # ModRM opcode group 3
    None, # ModRM opcode group 3
    # F8
    Insn("clc",     (), ()),
    Insn("stc",     (), ()),
    Insn("cli",     (), ()),
    Insn("sti",     (), ()),
    Insn("cld",     (), ()),
    Insn("std",     (), ()),
    None, # ModRM opcode group 4
    None) # ModRM opcode group 5
#
