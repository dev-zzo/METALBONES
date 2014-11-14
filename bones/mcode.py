
class Error(Exception):
    """Base class for errors raised in this module."""
    pass

class InvalidOpcodeError(Error):
    """Opcode is marked invalid."""
    pass

class UnknownOpcodeError(Error):
    """Opcode is not marked invalid, but I don't know it."""
    pass

_opwidth_names = (
    "byte",
    "word",
    "dword",
    "qword",
    "tword",
    "xmmword",
    "ymmword",
    "fword")
_opwidth_bits = (
    8,
    16,
    32,
    64,
    80,
    128,
    256,
    48)

class Immediate:
    def __init__(self, value, size):
        self.size = size # Data width, bits
        self.value = long(value)
    def as_signed(self):
        bits = 8 << self.size
        if (self.value & (1 << (bits - 1))) != 0 :
            return -((~self.value + 1) & ((1 << bits) - 1))
        return self.value
    def as_unsigned(self):
        return self.value
#
class MemoryRef:
    def __init__(self, size, base=None, index=None, scale=1, displ=None):
        self.size = size # Data width, bits
        self.base = base
        self.index = index
        self.scale = scale
        self.displ = displ
    def __str__(self):
        return '[%s+%08x+%s*%d]' % (self.base, self.displ.as_signed(), self.index, self.scale)
#
class Register:
    def __init__(self, name, size):
        self.size = size # Data width, bits
        self.name = name
    def __str__(self):
        return self.name
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

class StringReader:
    def __init__(self, data):
        self.data = data
        self.offset = 0
    def read(self):
        b = self.data[self.offset]
        self.offset += 1
        return b

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
        
    def decode(self):
        self.handler = decode_main_32
        return self.handler(self)
    def fetch_opcode(self):
        b = self.reader.read()
        self.opcode += b
        return ord(b)
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
        d |= ord(self.reader.read())
        if size >= 1:
            d |= ord(self.reader.read()) << 8
        if size >= 2:
            d |= ord(self.reader.read()) << 16
            d |= ord(self.reader.read()) << 24
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
        return state.handler(state)
class OperandSizePrefix:
    def __call__(self, state):
        state.prefix_66 = True
        return state.handler(state)
class AddressSizePrefix:
    def __call__(self, state):
        state.prefix_67 = True
        return state.handler(state)

class SwitchOpcode:
    """Table switch based on insn opcode byte"""
    def __init__(self, entries):
        self.entries = entries
        
    def __call__(self, state):
        state.handler = self
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
    (_register_map['bx'], _register_map['si'], None),
    (_register_map['bx'], _register_map['di'], None),
    (_register_map['bp'], _register_map['si'], None),
    (_register_map['bp'], _register_map['di'], None),
    (               None, _register_map['si'], None),
    (               None, _register_map['si'], None),
    (               None,                None, 1),
    (_register_map['bx'],                None, None),
    
    (_register_map['bx'], _register_map['si'], 0),
    (_register_map['bx'], _register_map['di'], 0),
    (_register_map['bp'], _register_map['si'], 0),
    (_register_map['bp'], _register_map['di'], 0),
    (               None, _register_map['si'], 0),
    (               None, _register_map['si'], 0),
    (_register_map['bp'],                None, 0),
    (_register_map['bx'],                None, 0),
    
    (_register_map['bx'], _register_map['si'], 1),
    (_register_map['bx'], _register_map['di'], 1),
    (_register_map['bp'], _register_map['si'], 1),
    (_register_map['bp'], _register_map['di'], 1),
    (               None, _register_map['si'], 1),
    (               None, _register_map['si'], 1),
    (_register_map['bp'],                None, 1),
    (_register_map['bx'],                None, 1))
_modrm_lookup_32 = (
    # base, displacement size
    (_register_map['eax'], None),
    (_register_map['ecx'], None),
    (_register_map['edx'], None),
    (_register_map['ebx'], None),
    (                None, None),
    (                None, 2),
    (_register_map['esi'], None),
    (_register_map['edi'], None),

    (_register_map['eax'], 0),
    (_register_map['ecx'], 0),
    (_register_map['edx'], 0),
    (_register_map['ebx'], 0),
    (                None, 0),
    (_register_map['ebp'], 0),
    (_register_map['esi'], 0),
    (_register_map['edi'], 0),

    (_register_map['eax'], 2),
    (_register_map['ecx'], 2),
    (_register_map['edx'], 2),
    (_register_map['ebx'], 2),
    (                None, 2),
    (_register_map['ebp'], 2),
    (_register_map['esi'], 2),
    (_register_map['edi'], 2))
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
    
def _decode_E(state, size):
    if state.modrm_mod == 3:
        return _gpr_decode[size][state.modrm_reg]
    else:
        b = None
        i = None
        s = 1
        d = None
        mod_rm = (state.modrm_mod << 3) + state.modrm_rm
        if state.address_width == 1:
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
        if d_size is not None:
            d = Immediate(state.fetch_mp(d_size), d_size)
        return MemoryRef(size, base=b, index=i, scale=s, displ=d)
def _decode_Eb(state):
    return _decode_E(state, 0)
def _decode_Ew(state):
    return _decode_E(state, 1)
def _decode_Ev(state):
    return _decode_E(state, state.operand_width)
def _decode_Ey(state):
    # FIXME: 64-bit
    return _decode_E(state, 2)
    
def _decode_Gb(state):
    return _r8_decode[state.modrm_reg]
def _decode_Gv(state):
    return _gpr_decode[state.operand_width][state.modrm_reg]
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
    return Immediate(state.fetch_mp(0), 0)
def _decode_Jz(state):
    if state.operand_width == 1:
        return Immediate(state.fetch_mp(1), 1)
    return Immediate(state.fetch_mp(2), 2)

def _decode_Ib(state):
    return Immediate(state.fetch_mp(0), 0)
def _decode_Iw(state):
    return Immediate(state.fetch_mp(1), 1)
def _decode_Iz(state):
    if state.operand_width == 1:
        return Immediate(state.fetch_mp(1), 1)
    return Immediate(state.fetch_mp(2), 2)

def _decode_Mp(state):
    raise InvalidOpcodeError()

class Decode:
    def __init__(self, mnemonic, operands, flags):
        self.mnemonic = mnemonic
        self.op_spec = operands
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

        # Apply operand/address size modifiers
        if state.prefix_66:
            state.operand_width = 1 if state.operand_width != 1 else 2
        if state.prefix_67:
            state.address_width = 1 if state.address_width != 1 else 2
        
        # Check and fetch ModR/M
        modrm_needed = (_check_modrm(self.op_spec[0])
            or _check_modrm(self.op_spec[1])
            or _check_modrm(self.op_spec[2]))
        if modrm_needed:
            state.fetch_modrm()
        
        # Check and fetch SIB
        sib_needed = state.address_width == 2 and state.modrm_mod != 3 and state.modrm_rm == 4
        if sib_needed:
            state.fetch_sib()
            
        # NOTE: Displacement comes before any immediate operands
        # I am not sure how to work around that
        decoded_ops = []
        for spec in self.op_spec:
            decoded_ops.append(self._decode_op(state, spec, self.flags))
            
        return Insn(self.mnemonic, decoded_ops)

    def _decode_op(self, state, op, flags):
        amode = op[0]
        if amode.isupper():
            if op == 'Ev': return _decode_Ev(state)
            if op == 'Eb': return _decode_Eb(state)
            if op == 'Gv': return _decode_Gv(state)
            if op == 'Gb': return _decode_Gb(state)
            raise UnknownOpcodeError(op)
        else:
            # Must be a register reference
            if op[0] == '?':
                # Can choose based on current operand size
                op = ('', 'e', 'r')[state.operand_width] + op[1:]
            return _register_map[op]
    
class Insn:
    def __init__(self, mnemonic, operands):
        self.mnemonic = mnemonic
        self.operands = operands
    def __str__(self):
        ops_str = ', '.join(map(str, self.operands))
        return '%s %s' % (self.mnemonic, ops_str)
#

decode_0F_32 = SwitchOpcode((
    # 00
    None, # ModRM opcode group 6
    None, # ModRM opcode group 7
    Decode("lar",       ("Gv", "Ew"), ()),
    Decode("lsl",       ("Gv", "Ew"), ()),
    _invalidOpcode,
    _invalidOpcode, # SYSCALL -- only 64-bit
    Decode("clts",      (), ()),
    _invalidOpcode, # SYSRET -- only 64-bit
    # 08
    Decode("invd",      (), ()),
    Decode("wbinvd",    (), ()),
    _invalidOpcode,
    Decode("ud2",       (), ()),
    _invalidOpcode,
    Decode("prefetchw", ("Ev"), ()),
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
    Decode("nop",       ("Ev"), ()),
    # 20
    Decode("mov",       ("Rd", "Cd"), ()),
    Decode("mov",       ("Rd", "Dd"), ()),
    Decode("mov",       ("Cd", "Rd"), ()),
    Decode("mov",       ("Dd", "Rd"), ()),
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 28
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 30
    Decode("wrmsr",     (), ()),
    Decode("rdtsc",     (), ()),
    Decode("rdmsr",     (), ()),
    Decode("rdpmc",     (), ()),
    Decode("sysenter",  (), ()),
    Decode("sysexit",   (), ()),
    _invalidOpcode,
    Decode("getsec",    (), ()),
    # 38
    None, # Escape 0F38
    _invalidOpcode,
    None, # Escape 0F3A
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 40
    Decode("cmovo",     ("Gv", "Ev"), ()),
    Decode("cmovno",    ("Gv", "Ev"), ()),
    Decode("cmovb",     ("Gv", "Ev"), ()),
    Decode("cmovae",    ("Gv", "Ev"), ()),
    Decode("cmove",     ("Gv", "Ev"), ()),
    Decode("cmovne",    ("Gv", "Ev"), ()),
    Decode("cmovbe",    ("Gv", "Ev"), ()),
    Decode("cmova",     ("Gv", "Ev"), ()),
    # 48
    Decode("cmovs",     ("Gv", "Ev"), ()),
    Decode("cmovns",    ("Gv", "Ev"), ()),
    Decode("cmovp",     ("Gv", "Ev"), ()),
    Decode("cmovnp",    ("Gv", "Ev"), ()),
    Decode("cmovl",     ("Gv", "Ev"), ()),
    Decode("cmovge",    ("Gv", "Ev"), ()),
    Decode("cmovle",    ("Gv", "Ev"), ()),
    Decode("cmovg",     ("Gv", "Ev"), ()),
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
    Decode("vmread",    ("Ey", "Gy"), ()),
    Decode("vmwrite",   ("Gy", "Ey"), ()),
    _invalidOpcode,
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 80
    Decode("jo",        ("Jz"), ()),
    Decode("jno",       ("Jz"), ()),
    Decode("jb",        ("Jz"), ()),
    Decode("jae",       ("Jz"), ()),
    Decode("je",        ("Jz"), ()),
    Decode("jne",       ("Jz"), ()),
    Decode("jbe",       ("Jz"), ()),
    Decode("ja",        ("Jz"), ()),
    # 88
    Decode("js",        ("Jz"), ()),
    Decode("jns",       ("Jz"), ()),
    Decode("jp",        ("Jz"), ()),
    Decode("jnp",       ("Jz"), ()),
    Decode("jl",        ("Jz"), ()),
    Decode("jge",       ("Jz"), ()),
    Decode("jle",       ("Jz"), ()),
    Decode("jg",        ("Jz"), ()),
    # 90
    Decode("seto",      ("Eb"), ()),
    Decode("setno",     ("Eb"), ()),
    Decode("setb",      ("Eb"), ()),
    Decode("setae",     ("Eb"), ()),
    Decode("sete",      ("Eb"), ()),
    Decode("setne",     ("Eb"), ()),
    Decode("setbe",     ("Eb"), ()),
    Decode("seta",      ("Eb"), ()),
    # 98
    Decode("sets",      ("Eb"), ()),
    Decode("setns",     ("Eb"), ()),
    Decode("setp",      ("Eb"), ()),
    Decode("setnp",     ("Eb"), ()),
    Decode("setl",      ("Eb"), ()),
    Decode("setge",     ("Eb"), ()),
    Decode("setle",     ("Eb"), ()),
    Decode("setg",      ("Eb"), ()),
    # A0
    Decode("push",      ("fs"), ()),
    Decode("pop",       ("fs"), ()),
    Decode("cpuid",     (), ()),
    Decode("bt",        ("Ev", "Gv"), ()),
    Decode("shld",      ("Ev", "Gv", "Ib"), ()),
    Decode("shld",      ("Ev", "Gv", "cl"), ()),
    _invalidOpcode,
    _invalidOpcode,
    # A8
    Decode("push",      ("gs"), ()),
    Decode("pop",       ("gs"), ()),
    Decode("rsm",       (), ()),
    Decode("bts",       ("Ev", "Gv"), ()),
    Decode("shrd",      ("Ev", "Gv", "Ib"), ()),
    Decode("shrd",      ("Ev", "Gv", "cl"), ()),
    None, # Group 15
    Decode("imul",      ("Gv", "Ev"), ()),
    # B0
    Decode("cmpxchg",   ("Eb", "Gb"), ()),
    Decode("cmpxchg",   ("Ev", "Gv"), ()),
    Decode("lss",       ("Gv", "Mp"), ()),
    Decode("btr",       ("Ev", "Gv"), ()),
    Decode("lfs",       ("Gv", "Mp"), ()),
    Decode("lgs",       ("Gv", "Mp"), ()),
    Decode("movzx",     ("Gv", "Eb"), ()),
    Decode("movzx",     ("Gv", "Ew"), ()),
    # B8
    _invalidOpcode,
    None, # ModRM opcode group 10 ?
    None, # ModRM opcode group 8
    Decode("btc",       ("Ev", "Gv"), ()),
    Decode("bsf",       ("Gv", "Ev"), ()),
    Decode("bsr",       ("Gv", "Ev"), ()),
    Decode("movsx",     ("Gv", "Eb"), ()),
    Decode("movsx",     ("Gv", "Ew"), ()),
    # C0
    Decode("xadd",      ("Eb", "Gb"), ()),
    Decode("xadd",      ("Ev", "Gv"), ()),
    _invalidOpcode,
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # C8
    Decode("bswap",     ("eax"), ("no66")),
    Decode("bswap",     ("ecx"), ("no66")),
    Decode("bswap",     ("edx"), ("no66")),
    Decode("bswap",     ("ebx"), ("no66")),
    Decode("bswap",     ("esp"), ("no66")),
    Decode("bswap",     ("ebp"), ("no66")),
    Decode("bswap",     ("esi"), ("no66")),
    Decode("bswap",     ("edi"), ("no66")),
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
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode
))

decode_main_32 = SwitchOpcode((
    # 00
    Decode("add",       ("Eb", "Gb"), ()),
    Decode("add",       ("Ev", "Gv"), ("allow66")),
    Decode("add",       ("Gb", "Eb"), ()),
    Decode("add",       ("Gv", "Ev"), ("allow66")),
    Decode("add",       ("al", "Ib"), ()),
    Decode("add",       ("?ax", "Iz"), ("allow66")),
    Decode("push",      ("es"), ()), # invalid in x64
    Decode("pop",       ("es"), ()), # invalid in x64
    # 08
    Decode("or",        ("Eb", "Gb"), ()),
    Decode("or",        ("Ev", "Gv"), ("allow66")),
    Decode("or",        ("Gb", "Eb"), ()),
    Decode("or",        ("Gv", "Ev"), ("allow66")),
    Decode("or",        ("al", "Ib"), ()),
    Decode("or",        ("?ax", "Iz"), ("allow66")),
    Decode("push",      ("cs"), ()), # invalid in x64
    decode_0F_32, # Escape 0F
    # 10
    Decode("adc",       ("Eb", "Gb"), ()),
    Decode("adc",       ("Ev", "Gv"), ("allow66")),
    Decode("adc",       ("Gb", "Eb"), ()),
    Decode("adc",       ("Gv", "Ev"), ("allow66")),
    Decode("adc",       ("al", "Ib"), ()),
    Decode("adc",       ("?ax", "Iz"), ("allow66")),
    Decode("push",      ("ss"), ()), # invalid in x64
    Decode("pop",       ("ss"), ()), # invalid in x64
    # 18
    Decode("sbb",       ("Eb", "Gb"), ()),
    Decode("sbb",       ("Ev", "Gv"), ("allow66")),
    Decode("sbb",       ("Gb", "Eb"), ()),
    Decode("sbb",       ("Gv", "Ev"), ("allow66")),
    Decode("sbb",       ("al", "Ib"), ()),
    Decode("sbb",       ("?ax", "Iz"), ("allow66")),
    Decode("push",      ("ds"), ()), # invalid in x64
    Decode("pop",       ("ds"), ()), # invalid in x64
    # 20
    Decode("and",       ("Eb", "Gb"), ()),
    Decode("and",       ("Ev", "Gv"), ("allow66")),
    Decode("and",       ("Gb", "Eb"), ()),
    Decode("and",       ("Gv", "Ev"), ("allow66")),
    Decode("and",       ("al", "Ib"), ()),
    Decode("and",       ("?ax", "Iz"), ("allow66")),
    SegmentOverridePrefix("es"),
    Decode("daa",       (), ()),
    # 28
    Decode("sub",       ("Eb", "Gb",), ()),
    Decode("sub",       ("Ev", "Gv"), ("allow66")),
    Decode("sub",       ("Gb", "Eb"), ()),
    Decode("sub",       ("Gv", "Ev"), ("allow66")),
    Decode("sub",       ("al", "Ib"), ()),
    Decode("sub",       ("?ax", "Iz"), ("allow66")),
    SegmentOverridePrefix("cs"),
    Decode("das",       (), ()),
    # 30
    Decode("xor",       ("Eb", "Gb"), ()),
    Decode("xor",       ("Ev", "Gv"), ("allow66")),
    Decode("xor",       ("Gb", "Eb"), ()),
    Decode("xor",       ("Gv", "Ev"), ("allow66")),
    Decode("xor",       ("al", "Ib"), ()),
    Decode("xor",       ("?ax", "Iz"), ("allow66")),
    SegmentOverridePrefix("ss"),
    Decode("aaa",       (), ()),
    # 38
    Decode("cmp",       ("Eb", "Gb"), ()),
    Decode("cmp",       ("Ev", "Gv"), ("allow66")),
    Decode("cmp",       ("Gb", "Eb"), ()),
    Decode("cmp",       ("Gv", "Ev"), ("allow66")),
    Decode("cmp",       ("al", "Ib"), ()),
    Decode("cmp",       ("?ax", "Iz"), ("allow66")),
    SegmentOverridePrefix("ds"),
    Decode("aas",       (), ()),
    # 40
    Decode("inc",       ("?ax"), ("allow66")),
    Decode("inc",       ("?cx"), ("allow66")),
    Decode("inc",       ("?dx"), ("allow66")),
    Decode("inc",       ("?bx"), ("allow66")),
    Decode("inc",       ("?sp"), ("allow66")),
    Decode("inc",       ("?bp"), ("allow66")),
    Decode("inc",       ("?si"), ("allow66")),
    Decode("inc",       ("?di"), ("allow66")),
    # 48
    Decode("dec",       ("?ax"), ("allow66")),
    Decode("dec",       ("?cx"), ("allow66")),
    Decode("dec",       ("?dx"), ("allow66")),
    Decode("dec",       ("?bx"), ("allow66")),
    Decode("dec",       ("?sp"), ("allow66")),
    Decode("dec",       ("?bp"), ("allow66")),
    Decode("dec",       ("?si"), ("allow66")),
    Decode("dec",       ("?di"), ("allow66")),
    # 50
    Decode("push",      ("?ax"), ("allow66")),
    Decode("push",      ("?cx"), ("allow66")),
    Decode("push",      ("?dx"), ("allow66")),
    Decode("push",      ("?bx"), ("allow66")),
    Decode("push",      ("?sp"), ("allow66")),
    Decode("push",      ("?bp"), ("allow66")),
    Decode("push",      ("?si"), ("allow66")),
    Decode("push",      ("?di"), ("allow66")),
    # 58
    Decode("pop",       ("?ax"), ("allow66")),
    Decode("pop",       ("?cx"), ("allow66")),
    Decode("pop",       ("?dx"), ("allow66")),
    Decode("pop",       ("?bx"), ("allow66")),
    Decode("pop",       ("?sp"), ("allow66")),
    Decode("pop",       ("?bp"), ("allow66")),
    Decode("pop",       ("?si"), ("allow66")),
    Decode("pop",       ("?di"), ("allow66")),
    # 60
    Decode("pusha",     (), ()), # invalid in x64
    Decode("popa",      (), ()), # invalid in x64
    Decode("bound",     ("Gv", "Ma"), ()), # invalid in x64
    Decode("arpl",      ("Ew", "Gw"), ()),
    SegmentOverridePrefix("fs"),
    SegmentOverridePrefix("gs"),
    OperandSizePrefix(),
    AddressSizePrefix(),
    # 68
    Decode("push",      ("Iz"), ("allow66")),
    Decode("imul",      ("Gv", "Ev", "Iz"), ("allow66")),
    Decode("push",      ("Ib"), ()),
    Decode("imul",      ("Gv", "Ev", "Ib"), ("allow66")),
    Decode("ins",       ("Yb", "dx"), ()),
    Decode("ins",       ("Yz", "dx"), ("allow66")),
    Decode("outs",      ("dx", "Xb"), ()),
    Decode("outs",      ("dx", "Xz"), ("allow66")),
    # 70
    Decode("jo",        ("Jb"), ()),
    Decode("jno",       ("Jb"), ()),
    Decode("jb",        ("Jb"), ()),
    Decode("jae",       ("Jb"), ()),
    Decode("je",        ("Jb"), ()),
    Decode("jne",       ("Jb"), ()),
    Decode("jbe",       ("Jb"), ()),
    Decode("ja",        ("Jb"), ()),
    # 78
    Decode("js",        ("Jb"), ()),
    Decode("jns",       ("Jb"), ()),
    Decode("jp",        ("Jb"), ()),
    Decode("jnp",       ("Jb"), ()),
    Decode("jl",        ("Jb"), ()),
    Decode("jge",       ("Jb"), ()),
    Decode("jle",       ("Jb"), ()),
    Decode("jg",        ("Jb"), ()),
    # 80
    None, # ModRM opcode group 1
    None, # ModRM opcode group 1
    None, # ModRM opcode group 1
    None, # ModRM opcode group 1
    Decode("test",      ("Eb", "Gb"), ()),
    Decode("test",      ("Ev", "Gv"), ("allow66")),
    Decode("xchg",      ("Eb", "Gb"), ()),
    Decode("xchg",      ("Ev", "Gv"), ("allow66")),
    # 88
    Decode("mov",       ("Eb", "Gb"), ()),
    Decode("mov",       ("Ev", "Gv"), ("allow66")),
    Decode("mov",       ("Gb", "Eb"), ()),
    Decode("mov",       ("Gv", "Ev"), ("allow66")),
    Decode("mov",       ("Ev", "Sw"), ("allow66")),
    Decode("lea",       ("Ev", "M"), ("allow66")),
    Decode("mov",       ("Sw", "Ew"), ("allow66")),
    None, # ModRM opcode group 1A
    # 90
    Decode("nop",       (), ()),
    Decode("xchg",      ("?cx", "?ax"), ("allow66")),
    Decode("xchg",      ("?dx", "?ax"), ("allow66")),
    Decode("xchg",      ("?bx", "?ax"), ("allow66")),
    Decode("xchg",      ("?sp", "?ax"), ("allow66")),
    Decode("xchg",      ("?bp", "?ax"), ("allow66")),
    Decode("xchg",      ("?si", "?ax"), ("allow66")),
    Decode("xchg",      ("?di", "?ax"), ("allow66")),
    # 98
    Decode("cwde",      (), ()),
    Decode("cdq",       (), ()),
    Decode("callf",     ("Ap"), ()),
    Decode("wait",      (), ()),
    Decode("pushf",     ("Fv"), ()),
    Decode("popf",      ("Fv"), ()),
    Decode("sahf",      (), ()),
    Decode("lahf",      (), ()),
    # A0
    Decode("mov",       ("al", "Ob"), ()),
    Decode("mov",       ("?ax", "Ov"), ("allow66")),
    Decode("mov",       ("Ob", "al"), ()),
    Decode("mov",       ("Ov", "?ax"), ("allow66")),
    Decode("movs",      ("Yb", "Xb"), ()),
    Decode("movs",      ("Yv", "Xv"), ("allow66")),
    Decode("cmps",      ("Xb", "Yb"), ()),
    Decode("cmps",      ("Xv", "Yv"), ("allow66")),
    # A8
    Decode("test",      ("al", "Ib"), ()),
    Decode("test",      ("?ax", "Iz"), ("allow66")),
    Decode("stos",      ("Yb", "al"), ()),
    Decode("stos",      ("Yv", "?ax"), ("allow66")),
    Decode("lods",      ("al", "Xb"), ()),
    Decode("lods",      ("?ax", "Xv"), ("allow66")),
    Decode("scas",      ("al", "Xb"), ()),
    Decode("scas",      ("?ax", "Xv"), ("allow66")),
    # B0(
    Decode("mov",       ("al", "Ib"), ()),
    Decode("mov",       ("cl", "Ib"), ()),
    Decode("mov",       ("dl", "Ib"), ()),
    Decode("mov",       ("bl", "Ib"), ()),
    Decode("mov",       ("ah", "Ib"), ()),
    Decode("mov",       ("ch", "Ib"), ()),
    Decode("mov",       ("dh", "Ib"), ()),
    Decode("mov",       ("bh", "Ib"), ()),
    # B8
    Decode("mov",       ("?ax", "Iv"), ("allow66")),
    Decode("mov",       ("?cx", "Iv"), ("allow66")),
    Decode("mov",       ("?dx", "Iv"), ("allow66")),
    Decode("mov",       ("?bx", "Iv"), ("allow66")),
    Decode("mov",       ("?sp", "Iv"), ("allow66")),
    Decode("mov",       ("?bp", "Iv"), ("allow66")),
    Decode("mov",       ("?si", "Iv"), ("allow66")),
    Decode("mov",       ("?di", "Iv"), ("allow66")),
    # C0
    None, # ModRM opcode group 2
    None, # ModRM opcode group 2
    Decode("retn",      ("Iw"), ()),
    Decode("retn",      (), ()),
    Decode("les",       ("Gz", "Mp"), ("allow66")),
    Decode("lds",       ("Gz", "Mp"), ("allow66")),
    None, # ModRM opcode group 11
    None, # ModRM opcode group 11
    # C8
    Decode("enter",     ("Iw", "Ib"), ()),
    Decode("leave",     (), ()),
    Decode("retf",      ("Iw"), ()),
    Decode("retf",      (), ()),
    Decode("int3",      (), ()),
    Decode("int",       ("Ib"), ()),
    Decode("into",      (), ()),
    Decode("iret",      (), ()),
    # D0
    None, # ModRM opcode group 2
    None, # ModRM opcode group 2
    None, # ModRM opcode group 2
    None, # ModRM opcode group 2
    Decode("aam",       ("Ib"), ()),
    Decode("aad",       ("Ib"), ()),
    _invalidOpcode,
    Decode("xlat",      (), ()),
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
    Decode("loopnz",    ("Jb"), ()),
    Decode("loopz",     ("Jb"), ()),
    Decode("loop",      ("Jb"), ()),
    Decode("jcxz",      ("Jb"), ()),
    Decode("in",        ("al", "Ib"), ()),
    Decode("in",        ("?ax", "Ib"), ("allow66")),
    Decode("out",       ("Ib", "al"), ()),
    Decode("out",       ("Ib", "?ax"), ("allow66")),
    # E8
    Decode("call",      ("Jz"), ()),
    Decode("jmp",       ("Jz"), ()),
    Decode("jmp",       ("Ap"), ()),
    Decode("jmp",       ("Jb"), ()),
    Decode("in",        ("al", "dx"), ()),
    Decode("in",        ("?ax", "dx"), ("allow66")),
    Decode("out",       ("dx", "al"), ()),
    Decode("out",       ("dx", "?ax"), ("allow66")),
    # F0
    None, # LOCK prefix
    _invalidOpcode,
    None, # REPNE prefix
    None, # REPE prefix
    Decode("hlt",       (), ()),
    Decode("cmc",       (), ()),
    None, # ModRM opcode group 3
    None, # ModRM opcode group 3
    # F8
    Decode("clc",       (), ()),
    Decode("stc",       (), ()),
    Decode("cli",       (), ()),
    Decode("sti",       (), ()),
    Decode("cld",       (), ()),
    Decode("std",       (), ()),
    None, # ModRM opcode group 4
    None)) # ModRM opcode group 5
#

r = StringReader("\x8b\x4c\x24\x08")
s = State(r)
i = s.decode()
print i