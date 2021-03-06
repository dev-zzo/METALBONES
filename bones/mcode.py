import sys
import functools

class Error(Exception):
    """Base class for errors raised in this module."""
    pass

class InvalidOpcodeError(Error):
    """Opcode is marked invalid."""
    pass

class UnknownOpcodeError(Error):
    """Opcode is not marked invalid, but I don't know it."""
    pass

OPW_8BIT = 0
OPW_16BIT = 1
OPW_32BIT = 2
OPW_64BIT = 3
OPW_80BIT = 4
OPW_128BIT = 5
OPW_256BIT = 6
OPW_48BIT = 7
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
    def __init__(self, value, size, signed=False):
        self.size = size # Data width, bits
        self._bits = long(value)
        self.signed = signed
    def get_value(self):
        if self.signed:
            return self.as_signed()
        return self.as_unsigned()
    def as_signed(self):
        width = _opwidth_bits[self.size]
        sign_bit = 1 << (width - 1)
        mask = (1 << width) - 1
        if (self._bits & sign_bit) != 0:
            return -((~self._bits & mask) + 1)
        return self._bits
    def as_unsigned(self):
        return self._bits
    def __str__(self):
        fmt = '%%0%dx' % (_opwidth_bits[self.size] >> 2)
        value = self.get_value()
        if self.signed:
            if value < 0:
                value = -value
                fmt = '-' + fmt
            else:
                fmt = '+' + fmt
        return fmt % value
#
class MemoryRef:
    def __init__(self, size, base=None, index=None, scale=1, displ=None, seg=None):
        self.size = size # Data width, bits
        self.base = base
        self.index = index
        self.scale = scale
        self.displ = displ
        self.seg = seg
    def __str__(self):
        return 'Base: %s Index: %s Scale: %s Displacement: %s' % (self.base, self.index, self.scale, self.displ)
#
class Address:
    def __init__(self, seg, off):
        self.seg = seg
        self.off = off
    def __str__(self):
        return 'Segment: %s Offset: %s' % (self.seg, self.off)
#
class Register:
    def __init__(self, name, size):
        self.size = size # Data width, bits
        self.name = name
    def __str__(self):
        return self.name
#

_register_map = {
    "rax": Register("rax", OPW_64BIT),
    "rcx": Register("rcx", OPW_64BIT),
    "rdx": Register("rdx", OPW_64BIT),
    "rbx": Register("rbx", OPW_64BIT),
    "rsp": Register("rsp", OPW_64BIT),
    "rbp": Register("rbp", OPW_64BIT),
    "rsi": Register("rsi", OPW_64BIT),
    "rdi": Register("rdi", OPW_64BIT),
    "eax": Register("eax", OPW_32BIT),
    "ecx": Register("ecx", OPW_32BIT),
    "edx": Register("edx", OPW_32BIT),
    "ebx": Register("ebx", OPW_32BIT),
    "esp": Register("esp", OPW_32BIT),
    "ebp": Register("ebp", OPW_32BIT),
    "esi": Register("esi", OPW_32BIT),
    "edi": Register("edi", OPW_32BIT),
    "ax": Register("ax", OPW_16BIT),
    "cx": Register("cx", OPW_16BIT),
    "dx": Register("dx", OPW_16BIT),
    "bx": Register("bx", OPW_16BIT),
    "sp": Register("sp", OPW_16BIT),
    "bp": Register("bp", OPW_16BIT),
    "si": Register("si", OPW_16BIT),
    "di": Register("di", OPW_16BIT),
    "al": Register("al", OPW_8BIT),
    "cl": Register("cl", OPW_8BIT),
    "dl": Register("dl", OPW_8BIT),
    "bl": Register("bl", OPW_8BIT),
    "ah": Register("ah", OPW_8BIT),
    "ch": Register("ch", OPW_8BIT),
    "dh": Register("dh", OPW_8BIT),
    "bh": Register("bh", OPW_8BIT),
    "es": Register("es", OPW_16BIT),
    "cs": Register("cs", OPW_16BIT),
    "ss": Register("ss", OPW_16BIT),
    "ds": Register("ds", OPW_16BIT),
    "fs": Register("fs", OPW_16BIT),
    "gs": Register("gs", OPW_16BIT),
    "dr0": Register("dr0", OPW_32BIT),
    "dr1": Register("dr1", OPW_32BIT),
    "dr2": Register("dr2", OPW_32BIT),
    "dr3": Register("dr3", OPW_32BIT),
    "dr6": Register("dr6", OPW_32BIT),
    "dr7": Register("dr7", OPW_32BIT),
    "cr0": Register("cr0", OPW_32BIT),
    "cr2": Register("cr2", OPW_32BIT),
    "cr3": Register("cr3", OPW_32BIT),
    "cr4": Register("cr4", OPW_32BIT),
    "flags": Register("flags", OPW_16BIT),
    "eflags": Register("eflags", OPW_32BIT),
    "rflags": Register("rflags", OPW_64BIT),
    "st(0)": Register("st(0)", OPW_80BIT),
    "st(1)": Register("st(1)", OPW_80BIT),
    "st(2)": Register("st(2)", OPW_80BIT),
    "st(3)": Register("st(3)", OPW_80BIT),
    "st(4)": Register("st(4)", OPW_80BIT),
    "st(5)": Register("st(5)", OPW_80BIT),
    "st(6)": Register("st(6)", OPW_80BIT),
    "st(7)": Register("st(7)", OPW_80BIT),
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
_rfpu_decode = (
    _register_map["st(0)"], _register_map["st(1)"], _register_map["st(2)"], _register_map["st(3)"], 
    _register_map["st(4)"], _register_map["st(5)"], _register_map["st(6)"], _register_map["st(7)"],
    )
class State:
    def __init__(self, reader):
        self.reader = reader
        # Opcode bytes so far
        self.opcode = ''
        self.opcode_hex = ''
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
        self.prefix_F0 = False # LOCK
        self.prefix_F2 = False # REPNE
        self.prefix_F3 = False # REPE
        
    def fetch_opcode(self):
        b = self.reader.read()
        self.opcode += chr(b)
        self.opcode_hex += '%02x' % b
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
        self.opcode_hex += ' '
        d = 0L
        d |= self.fetch_opcode()
        if size >= 1:
            d |= self.fetch_opcode()<< 8
        if size >= 2:
            d |= self.fetch_opcode() << 16
            d |= self.fetch_opcode() << 24
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
        state.seg_override = _register_map[self.regname]
        return state.handler(state)
class OperandSizePrefix:
    def __call__(self, state):
        state.prefix_66 = True
        return state.handler(state)
class AddressSizePrefix:
    def __call__(self, state):
        state.prefix_67 = True
        return state.handler(state)
class LockPrefix:
    def __call__(self, state):
        state.prefix_F0 = True
        return state.handler(state)
class RepnePrefix:
    def __call__(self, state):
        state.prefix_F2 = True
        return state.handler(state)
class RepePrefix:
    def __call__(self, state):
        state.prefix_F3 = True
        return state.handler(state)

class SwitchOpcode:
    """Table switch based on insn opcode byte"""
    def __init__(self, entries):
        self.entries = entries
        
    def __call__(self, state):
        # Keep self for prefix handlers...
        state.handler = self
        b = state.fetch_opcode()
        e = self.entries[b]
        return e(state)
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
class SwitchModRMMod:
    """Choose either Mod{012} or Mod3, and then switch by Reg"""
    def __init__(self, mod_012, mod_3):
        self.lower_tab = mod_012
        self.upper_tab = mod_3
    def __call__(self, state):
        state.fetch_modrm()
        if state.modrm_mod != 3:
            e = self.lower_tab[state.modrm_reg]
        else:
            e = self.upper_tab[state.modrm_reg]
        return e(state)
class SwitchModRMReg:
    """Switch by Reg"""
    def __init__(self, entries):
        self.entries = entries
    def __call__(self, state):
        state.fetch_modrm()
        e = self.entries[state.modrm_reg]
        return e(state)
class SwitchModRMRM:
    """Switch by R/M"""
    def __init__(self, entries):
        self.entries = entries
    def __call__(self, state):
        state.fetch_modrm()
        e = self.entries[state.modrm_rm]
        return e(state)

_modrm_lookup_16 = (
    # base, index, displacement size
    (_register_map['bx'], _register_map['si'], _register_map['ds'], None),
    (_register_map['bx'], _register_map['di'], _register_map['ds'], None),
    (_register_map['bp'], _register_map['si'], _register_map['ss'], None),
    (_register_map['bp'], _register_map['di'], _register_map['ss'], None),
    (               None, _register_map['si'], _register_map['ds'], None),
    (               None, _register_map['si'], _register_map['ds'], None),
    (               None,                None, _register_map['ds'], 1),
    (_register_map['bx'],                None, _register_map['ds'], None),
    
    (_register_map['bx'], _register_map['si'], _register_map['ds'], 0),
    (_register_map['bx'], _register_map['di'], _register_map['ds'], 0),
    (_register_map['bp'], _register_map['si'], _register_map['ss'], 0),
    (_register_map['bp'], _register_map['di'], _register_map['ss'], 0),
    (               None, _register_map['si'], _register_map['ds'], 0),
    (               None, _register_map['si'], _register_map['ds'], 0),
    (_register_map['bp'],                None, _register_map['ss'], 0),
    (_register_map['bx'],                None, _register_map['ds'], 0),
    
    (_register_map['bx'], _register_map['si'], _register_map['ds'], 1),
    (_register_map['bx'], _register_map['di'], _register_map['ds'], 1),
    (_register_map['bp'], _register_map['si'], _register_map['ss'], 1),
    (_register_map['bp'], _register_map['di'], _register_map['ss'], 1),
    (               None, _register_map['si'], _register_map['ds'], 1),
    (               None, _register_map['si'], _register_map['ds'], 1),
    (_register_map['bp'],                None, _register_map['ss'], 1),
    (_register_map['bx'],                None, _register_map['ds'], 1))
_modrm_lookup_32 = (
    # base, displacement size
    (_register_map['eax'], _register_map['ds'], None),
    (_register_map['ecx'], _register_map['ds'], None),
    (_register_map['edx'], _register_map['ds'], None),
    (_register_map['ebx'], _register_map['ds'], None),
    (                None, None, None), # SIB
    (                None, _register_map['ds'], 2),
    (_register_map['esi'], _register_map['ds'], None),
    (_register_map['edi'], _register_map['ds'], None),

    (_register_map['eax'], _register_map['ds'], 0),
    (_register_map['ecx'], _register_map['ds'], 0),
    (_register_map['edx'], _register_map['ds'], 0),
    (_register_map['ebx'], _register_map['ds'], 0),
    (                None, None, 0), # SIB
    (_register_map['ebp'], _register_map['ss'], 0),
    (_register_map['esi'], _register_map['ds'], 0),
    (_register_map['edi'], _register_map['ds'], 0),

    (_register_map['eax'], _register_map['ds'], 2),
    (_register_map['ecx'], _register_map['ds'], 2),
    (_register_map['edx'], _register_map['ds'], 2),
    (_register_map['ebx'], _register_map['ds'], 2),
    (                None, None, 2), # SIB
    (_register_map['ebp'], _register_map['ss'], 2),
    (_register_map['esi'], _register_map['ds'], 2),
    (_register_map['edi'], _register_map['ds'], 2))
_sib_index_lookup = (
    _register_map['eax'],
    _register_map['ecx'],
    _register_map['edx'],
    _register_map['ebx'],
                    None,
    _register_map['ebp'],
    _register_map['esi'],
    _register_map['edi'])
_sib_seg_lookup = (
    _register_map["ds"],
    _register_map["ds"],
    _register_map["ds"],
    _register_map["ds"],
    _register_map["ss"],
    _register_map["ss"],
    _register_map["ds"],
    _register_map["ds"])
_gpr_decode = (
    _r8_decode,
    _r16_decode,
    _r32_decode,
    _r64_decode)

def _decode_opsize_p(state):
    if state.operand_width == OPW_16BIT:
        return OPW_32BIT
    if state.operand_width == OPW_32BIT:
        return OPW_48BIT
    if state.operand_width == OPW_64BIT:
        return OPW_80BIT
    raise InvalidOpcodeError()

def _decode_E_mem(state, size):
    s = 1
    i = None
    b = None
    d = None
    seg = state.seg_override
    mod_rm = (state.modrm_mod << 3) + state.modrm_rm
    if state.address_width == OPW_16BIT:
        l = _modrm_lookup_16[mod_rm]
        d_size = l[3]
        b = l[0]
        i = l[1]
        if seg is None:
            seg = l[2]
    else:
        l = _modrm_lookup_32[mod_rm]
        d_size = l[2]
        if state.modrm_rm == 4:
            # SIB
            scale = 1 << state.sib_scale
            i = _sib_index_lookup[state.sib_index]
            if not (state.modrm_mod == 0 and state.sib_base == 5):
                b = _r32_decode[state.sib_base]
                if seg is None:
                    seg = _sib_seg_lookup[state.sib_base]
            else:
                if seg is None:
                    seg = _sib_seg_lookup[0]
                d_size = 2
        else:
            b = l[0]
            if seg is None:
                seg = l[1]
    if d_size is not None:
        # Vol 2A, Tables 2.1 and 2.2: 8-bit displacement is sign-extended.
        d_signed = (d_size == OPW_8BIT) or (b is not None or i is not None)
        d = Immediate(state.fetch_mp(d_size), d_size, signed=d_signed)
    return MemoryRef(size, base=b, index=i, scale=s, displ=d, seg=seg)
def _decode_E_(state, size):
    if state.modrm_mod == 3:
        return _gpr_decode[size][state.modrm_rm]
    return _decode_E_mem(state, size)
def _decode_Eb(state):
    return _decode_E_(state, OPW_8BIT)
def _decode_Ew(state):
    return _decode_E_(state, OPW_16BIT)
def _decode_Ev(state):
    return _decode_E_(state, state.operand_width)
def _decode_Ey(state):
    # FIXME: 64-bit
    return _decode_E_(state, OPW_32BIT)
def _decode_Ep(state):
    opsize = _decode_opsize_p(state)
    return _decode_E_(state, opsize)

def _decode_Gb(state):
    return _r8_decode[state.modrm_reg]
def _decode_Gw(state):
    return _r16_decode[state.modrm_reg]
def _decode_Gv(state):
    return _gpr_decode[state.operand_width][state.modrm_reg]
def _decode_Gy(state):
    # FIXME: 64-bit
    return _r32_decode[state.modrm_reg]
def _decode_Gz(state):
    if state.operand_width == OPW_16BIT:
        return _r16_decode[state.modrm_reg]
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
    return Immediate(state.fetch_mp(OPW_8BIT), OPW_8BIT, signed=True)
def _decode_Jz(state):
    if state.operand_width == OPW_16BIT:
        return Immediate(state.fetch_mp(OPW_16BIT), OPW_16BIT, signed=True)
    return Immediate(state.fetch_mp(OPW_32BIT), OPW_32BIT, signed=True)

def _decode_Ib(state):
    return Immediate(state.fetch_mp(OPW_8BIT), OPW_8BIT)
def _decode_Isb(state):
    return Immediate(state.fetch_mp(OPW_8BIT), OPW_8BIT, signed=True)
def _decode_Iw(state):
    return Immediate(state.fetch_mp(OPW_16BIT), OPW_16BIT)
def _decode_Iv(state):
    return Immediate(state.fetch_mp(state.operand_width), state.operand_width)
def _decode_Iz(state):
    if state.operand_width == OPW_16BIT:
        return Immediate(state.fetch_mp(OPW_16BIT), OPW_16BIT)
    return Immediate(state.fetch_mp(OPW_32BIT), OPW_32BIT)

def _decode_Ap(state):
    off = Immediate(state.fetch_mp(state.operand_width), state.operand_width)
    seg = Immediate(state.fetch_mp(OPW_16BIT), OPW_16BIT)
    return Address(seg, off)

def _decode_Ma(state):
    if state.modrm_mod == 3:
        raise InvalidOpcodeError()
    return _decode_E_mem(state, OPW_64BIT)
def _decode_Mp(state):
    if state.modrm_mod == 3:
        raise InvalidOpcodeError()
    opsize = _decode_opsize_p(state)
    return _decode_E_mem(state, opsize)
def _decode_Mb(state):
    return _decode_E_mem(state, OPW_8BIT)
def _decode_Mw(state):
    return _decode_E_mem(state, OPW_16BIT)
def _decode_Md(state):
    return _decode_E_mem(state, OPW_32BIT)
def _decode_Mv(state):
    if state.modrm_mod == 3:
        raise InvalidOpcodeError()
    return _decode_E_mem(state, state.operand_width)
def _decode_Mq(state):
    return _decode_E_mem(state, OPW_64BIT)
def _decode_Mt(state):
    return _decode_E_mem(state, OPW_80BIT)

_flags_lookup = (
    None,
    _register_map['flags'],
    _register_map['eflags'],
    _register_map['rflags'],
    )
def _decode_Fv(state):
    return _flags_lookup[state.operand_width]

def _decode_X_(state, size):
    seg = state.seg_override
    if seg is None:
        seg = _register_map['ds']
    base = _gpr_decode[state.address_width][6]
    return MemoryRef(size, base=base, seg=seg)
def _decode_Xb(state):
    return _decode_X_(state, OPW_8BIT)
def _decode_Xv(state):
    return _decode_X_(state, state.operand_width)
def _decode_Xz(state):
    if state.operand_width == OPW_16BIT:
        return _decode_X_(state, OPW_16BIT)
    return _decode_X_(state, OPW_32BIT)
def _decode_Y_(state, size):
    seg = state.seg_override
    if seg is None:
        seg = _register_map['es']
    base = _gpr_decode[state.address_width][7]
    return MemoryRef(size, base=base, seg=seg)
def _decode_Yb(state):
    return _decode_Y_(state, OPW_8BIT)
def _decode_Yv(state):
    return _decode_Y_(state, state.operand_width)
def _decode_Yz(state):
    if state.operand_width == OPW_16BIT:
        return _decode_Y_(state, OPW_16BIT)
    return _decode_Y_(state, OPW_32BIT)

def _decode_Sw(state):
    return _rseg_decode[state.modrm_reg]

def _decode_O_(state, size):
    d = Immediate(state.fetch_mp(state.address_width), state.address_width)
    seg = state.seg_override
    if seg is None:
        seg = _register_map['ds']
    return MemoryRef(size, displ=d, seg=seg)
def _decode_Ob(state):
    return _decode_O_(state, OPW_8BIT)
def _decode_Ov(state):
    return _decode_O_(state, state.operand_width)

def _decode_Kt(state):
    return _rfpu_decode[state.modrm_rm]
    
def _decode_reg(which, state):
    if which[0] == '?':
        # Can choose based on current operand size
        which = ('', 'e', 'r')[state.operand_width - 1] + which[1:]
    return _register_map[which]

class DecodeBase:
    # Map reg decoders to partials to conserve memory
    _reg_decoders = {}
    
    def __init__(self, mnemonic, op_spec, flags):
        self.mnemonic = mnemonic
        self.flags = flags
        self.op_list = self._prepare_operands(op_spec)
        
    def __call__(self, state):
        self._apply_prefices(state)
        if self.modrm_needed:
            state.fetch_modrm()
            self._check_fetch_sib(state)
        return self._decode(state)

    def _prepare_operands(self, operands):
        op_list = []
        for op in operands:
            op_list.append(self._prepare_operand(op))
        return op_list
    def _prepare_operand(self, op):
        if op[0].isupper():
            return sys.modules[Decode.__module__].__dict__['_decode_' + op]
        else:
            try:
                return Decode._reg_decoders[op]
            except KeyError:
                p = functools.partial(_decode_reg, op)
                Decode._reg_decoders[op] = p
                return p
    def _apply_prefices(self, state):
        if state.prefix_66:
            state.operand_width = OPW_16BIT if state.operand_width != OPW_16BIT else OPW_32BIT
        if state.prefix_67:
            state.address_width = OPW_16BIT if state.address_width != OPW_16BIT else OPW_32BIT
    def _check_fetch_sib(self, state):
        if state.address_width == OPW_32BIT and state.modrm_mod != 3 and state.modrm_rm == 4:
            state.fetch_sib()
    def _decode(self, state):
        decoded_ops = []
        for handler in self.op_list:
            decoded_ops.append(handler(state))
        insn = Insn(self.mnemonic, decoded_ops, state.opcode, state.opcode_hex)
        insn.prefix_F0 = state.prefix_F0
        insn.prefix_F2 = state.prefix_F2
        insn.prefix_F3 = state.prefix_F3
        return insn
class Decode(DecodeBase):
    """Decoder for generic instructions"""
    def __init__(self, mnemonic, operands, flags):
        self.modrm_needed = False
        DecodeBase.__init__(self, mnemonic, operands, flags)
    def __call__(self, state):
        self._apply_prefices(state)
        if self.modrm_needed:
            state.fetch_modrm()
            self._check_fetch_sib(state)
        return self._decode(state)
    def _prepare_operand(self, op):
        if op[0] in "CDEGMNPQRSUVW":
            self.modrm_needed = True
        return DecodeBase._prepare_operand(self, op)
class DecodeFPU(DecodeBase):
    """Decoder for FPU instructions"""
    def __call__(self, state):
        self._apply_prefices(state)
        self._check_fetch_sib(state)
        return self._decode(state)

class Insn:
    def __init__(self, mnemonic, operands, opcode, opcode_hex):
        self.mnemonic = mnemonic
        self.operands = operands
        self.opcode = opcode
        self.opcode_hex = opcode_hex
        self.prefix_F0 = False
        self.prefix_F2 = False
        self.prefix_F3 = False
    def __str__(self):
        return '%s %s' % (self.mnemonic, str(self.operands))
#

# Group 1
decode_80_32 = SwitchModRMReg((
    Decode('add',       ('Eb', 'Ib'), ()),
    Decode('or',        ('Eb', 'Ib'), ()),
    Decode('adc',       ('Eb', 'Ib'), ()),
    Decode('sbb',       ('Eb', 'Ib'), ()),
    Decode('and',       ('Eb', 'Ib'), ()),
    Decode('sub',       ('Eb', 'Ib'), ()),
    Decode('xor',       ('Eb', 'Ib'), ()),
    Decode('cmp',       ('Eb', 'Ib'), ())
    ))
decode_81_32 = SwitchModRMReg((
    Decode('add',       ('Ev', 'Iz'), ()),
    Decode('or',        ('Ev', 'Iz'), ()),
    Decode('adc',       ('Ev', 'Iz'), ()),
    Decode('sbb',       ('Ev', 'Iz'), ()),
    Decode('and',       ('Ev', 'Iz'), ()),
    Decode('sub',       ('Ev', 'Iz'), ()),
    Decode('xor',       ('Ev', 'Iz'), ()),
    Decode('cmp',       ('Ev', 'Iz'), ())
    ))
decode_82_32 = SwitchModRMReg((
    Decode('add',       ('Eb', 'Ib'), ()),
    Decode('or',        ('Eb', 'Ib'), ()),
    Decode('adc',       ('Eb', 'Ib'), ()),
    Decode('sbb',       ('Eb', 'Ib'), ()),
    Decode('and',       ('Eb', 'Ib'), ()),
    Decode('sub',       ('Eb', 'Ib'), ()),
    Decode('xor',       ('Eb', 'Ib'), ()),
    Decode('cmp',       ('Eb', 'Ib'), ())
    ))
decode_83_32 = SwitchModRMReg(( # Sign-extend the Ib
    Decode('add',       ('Ev', 'Isb'), ()),
    Decode('or',        ('Ev', 'Isb'), ()),
    Decode('adc',       ('Ev', 'Isb'), ()),
    Decode('sbb',       ('Ev', 'Isb'), ()),
    Decode('and',       ('Ev', 'Isb'), ()),
    Decode('sub',       ('Ev', 'Isb'), ()),
    Decode('xor',       ('Ev', 'Isb'), ()),
    Decode('cmp',       ('Ev', 'Isb'), ())
    ))
# Group 1A
decode_8F_32 = SwitchModRMReg((
    Decode('pop',       ('Ev',), ()),
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, 
    _invalidOpcode, _invalidOpcode
    ))
# Group 2
decode_C0_32 = SwitchModRMReg((
    Decode('rol',       ('Eb', 'Ib'), ()),
    Decode('ror',       ('Eb', 'Ib'), ()),
    Decode('rcl',       ('Eb', 'Ib'), ()),
    Decode('rcr',       ('Eb', 'Ib'), ()),
    Decode('shl',       ('Eb', 'Ib'), ()),
    Decode('shr',       ('Eb', 'Ib'), ()),
    _invalidOpcode,
    Decode('sar',       ('Eb', 'Ib'), ())
    ))
decode_C1_32 = SwitchModRMReg((
    Decode('rol',       ('Ev', 'Ib'), ()),
    Decode('ror',       ('Ev', 'Ib'), ()),
    Decode('rcl',       ('Ev', 'Ib'), ()),
    Decode('rcr',       ('Ev', 'Ib'), ()),
    Decode('shl',       ('Ev', 'Ib'), ()),
    Decode('shr',       ('Ev', 'Ib'), ()),
    _invalidOpcode,
    Decode('sar',       ('Ev', 'Ib'), ())
    ))
decode_D0_32 = SwitchModRMReg((
    Decode('rol',       ('Eb',), ()),
    Decode('ror',       ('Eb',), ()),
    Decode('rcl',       ('Eb',), ()),
    Decode('rcr',       ('Eb',), ()),
    Decode('shl',       ('Eb',), ()),
    Decode('shr',       ('Eb',), ()),
    _invalidOpcode,
    Decode('sar',       ('Eb',), ())
    ))
decode_D1_32 = SwitchModRMReg((
    Decode('rol',       ('Ev',), ()),
    Decode('ror',       ('Ev',), ()),
    Decode('rcl',       ('Ev',), ()),
    Decode('rcr',       ('Ev',), ()),
    Decode('shl',       ('Ev',), ()),
    Decode('shr',       ('Ev',), ()),
    _invalidOpcode,
    Decode('sar',       ('Ev',), ())
    ))
decode_D2_32 = SwitchModRMReg((
    Decode('rol',       ('Eb', 'cl'), ()),
    Decode('ror',       ('Eb', 'cl'), ()),
    Decode('rcl',       ('Eb', 'cl'), ()),
    Decode('rcr',       ('Eb', 'cl'), ()),
    Decode('shl',       ('Eb', 'cl'), ()),
    Decode('shr',       ('Eb', 'cl'), ()),
    _invalidOpcode,
    Decode('sar',       ('Eb', 'cl'), ())
    ))
decode_D3_32 = SwitchModRMReg((
    Decode('rol',       ('Ev', 'cl'), ()),
    Decode('ror',       ('Ev', 'cl'), ()),
    Decode('rcl',       ('Ev', 'cl'), ()),
    Decode('rcr',       ('Ev', 'cl'), ()),
    Decode('shl',       ('Ev', 'cl'), ()),
    Decode('shr',       ('Ev', 'cl'), ()),
    _invalidOpcode,
    Decode('sar',       ('Ev', 'cl'), ())
    ))
# Group 3
decode_F6_32 = SwitchModRMReg((
    Decode('test',      ('Eb', 'Ib'), ()),
    _invalidOpcode,
    Decode('not',       ('Eb',), ()),
    Decode('neg',       ('Eb',), ()),
    Decode('mul',       ('Eb',), ()),
    Decode('imul',      ('Eb',), ()),
    Decode('div',       ('Eb',), ()),
    Decode('idiv',      ('Eb',), ()),
    ))
decode_F7_32 = SwitchModRMReg((
    Decode('test',      ('Ev', 'Iz'), ()),
    _invalidOpcode,
    Decode('not',       ('Ev',), ()),
    Decode('neg',       ('Ev',), ()),
    Decode('mul',       ('Ev',), ()),
    Decode('imul',      ('Ev',), ()),
    Decode('div',       ('Ev',), ()),
    Decode('idiv',      ('Ev',), ()),
    ))
# Group 4
decode_FE_32 = SwitchModRMReg((
    Decode('inc',       ('Eb',), ()),
    Decode('dec',       ('Eb',), ()),
    _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, 
    _invalidOpcode, _invalidOpcode
    ))
# Group 5
decode_FF_32 = SwitchModRMReg((
    Decode('inc',       ('Ev',), ('allow66')),
    Decode('dec',       ('Ev',), ('allow66')),
    Decode('call',      ('Ev',), ()),
    Decode('call',      ('Ep',), ()),
    Decode('jmp',       ('Ev',), ()),
    Decode('jmp',       ('Mp',), ()),
    Decode('push',      ('Ev',), ('allow66')),
    _invalidOpcode
    ))
# Group 8
decode_0F_BA = SwitchModRMReg((
    _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, 
    Decode('bt',        ('Ev', 'Ib'), ()),
    Decode('bts',       ('Ev', 'Ib'), ()),
    Decode('btr',       ('Ev', 'Ib'), ()),
    Decode('btc',       ('Ev', 'Ib'), ()),
    ))
# Group 11
decode_C6_32 = SwitchModRMReg((
    Decode('mov',       ('Eb', 'Ib'), ()),
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, 
    _invalidOpcode, _invalidOpcode
    ))
decode_C7_32 = SwitchModRMReg((
    Decode('mov',       ('Ev', 'Iz'), ()),
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, 
    _invalidOpcode, _invalidOpcode
    ))
# Group 15
decode_0F_AE = SwitchModRMMod((
    Decode('fxsave',    ('Md',), ()),
    Decode('fxrstor',   ('Md',), ()),
    Decode('ldmxcsr',   ('Md',), ()),
    Decode('stmxcsr',   ('Md',), ()),
    _invalidOpcode, _invalidOpcode, 
    _invalidOpcode, _invalidOpcode
    ),
    _invalidOpcode # Not implemented yet
    )

decode_D8 = SwitchModRMMod((
    DecodeFPU('fadd',       ('Md',), ()),
    DecodeFPU('fmul',       ('Md',), ()),
    DecodeFPU('fcom',       ('Md',), ()),
    DecodeFPU('fcomp',      ('Md',), ()),
    DecodeFPU('fsub',       ('Md',), ()),
    DecodeFPU('fsubr',      ('Md',), ()),
    DecodeFPU('fdiv',       ('Md',), ()),
    DecodeFPU('fdivr',      ('Md',), ()),
    ), (
    DecodeFPU('fadd',       ('st(0)', 'Kt'), ()),
    DecodeFPU('fmul',       ('st(0)', 'Kt'), ()),
    DecodeFPU('fcom',       ('st(0)', 'Kt'), ()),
    DecodeFPU('fcomp',      ('st(0)', 'Kt'), ()),
    DecodeFPU('fsub',       ('st(0)', 'Kt'), ()),
    DecodeFPU('fsubr',      ('st(0)', 'Kt'), ()),
    DecodeFPU('fdiv',       ('st(0)', 'Kt'), ()),
    DecodeFPU('fdivr',      ('st(0)', 'Kt'), ()),
    ))
decode_D9 = SwitchModRMMod((
    DecodeFPU('fld',        ('Md',), ()),
    _invalidOpcode,
    DecodeFPU('fst',        ('Md',), ()),
    DecodeFPU('fstp',       ('Md',), ()),
    DecodeFPU('fldenv',     ('Md',), ()), # 14/28 bytes
    DecodeFPU('fldcw',      ('Mw',), ()),
    DecodeFPU('fstenv',     ('Md',), ()), # 14/28 bytes
    DecodeFPU('fstcw',      ('Mw',), ()),
    ), (
    DecodeFPU('fld',        ('st(0)', 'Kt'), ()),
    DecodeFPU('fxch',       ('st(0)', 'Kt'), ()),
    SwitchModRMRM((
        DecodeFPU('fnop',   (), ()),
        _invalidOpcode,
        _invalidOpcode, _invalidOpcode,
        _invalidOpcode, _invalidOpcode,
        _invalidOpcode, _invalidOpcode,
        )),
    _invalidOpcode,
    SwitchModRMRM((
        DecodeFPU('fchs',   (), ()),
        DecodeFPU('fabs',   (), ()),
        _invalidOpcode, _invalidOpcode,
        DecodeFPU('ftst',   (), ()),
        DecodeFPU('fxam',   (), ()),
        _invalidOpcode, _invalidOpcode,
        )),
    SwitchModRMRM((
        DecodeFPU('fld1',   (), ()),
        DecodeFPU('fldl2t', (), ()),
        DecodeFPU('fldl2e', (), ()),
        DecodeFPU('fldpi',  (), ()),
        DecodeFPU('fldlg2', (), ()),
        DecodeFPU('fldln2', (), ()),
        DecodeFPU('fldz',   (), ()),
        _invalidOpcode,
        )),
    SwitchModRMRM((
        DecodeFPU('f2xm1',  (), ()),
        DecodeFPU('fyl2x',  (), ()),
        DecodeFPU('fptan',  (), ()),
        DecodeFPU('fpatan', (), ()),
        DecodeFPU('fxtract',(), ()),
        DecodeFPU('fprem1', (), ()),
        DecodeFPU('fdecstp',(), ()),
        DecodeFPU('fincstp',(), ()),
        )),
    SwitchModRMRM((
        DecodeFPU('fprem',  (), ()),
        DecodeFPU('fyl2xp1',(), ()),
        DecodeFPU('fsqrt',  (), ()),
        DecodeFPU('fsincos',(), ()),
        DecodeFPU('frndint',(), ()),
        DecodeFPU('fscale', (), ()),
        DecodeFPU('fsin',   (), ()),
        DecodeFPU('fcos',   (), ()),
        )),
    ))
decode_DA = SwitchModRMMod((
    DecodeFPU('fiadd',      ('Md',), ()),
    DecodeFPU('fimul',      ('Md',), ()),
    DecodeFPU('ficom',      ('Md',), ()),
    DecodeFPU('ficomp',     ('Md',), ()),
    DecodeFPU('fisub',      ('Md',), ()),
    DecodeFPU('fisubr',     ('Md',), ()),
    DecodeFPU('fidiv',      ('Md',), ()),
    DecodeFPU('fidivr',     ('Md',), ()),
    ), (
    DecodeFPU('fcmovb',     ('st(0)', 'Kt'), ()),
    DecodeFPU('fcmove',     ('st(0)', 'Kt'), ()),
    DecodeFPU('fcmovbe',    ('st(0)', 'Kt'), ()),
    DecodeFPU('fcmovu',     ('st(0)', 'Kt'), ()),
    _invalidOpcode,
    SwitchModRMRM((
        _invalidOpcode,
        DecodeFPU('fucompp',(), ()),
        _invalidOpcode, _invalidOpcode,
        _invalidOpcode, _invalidOpcode,
        _invalidOpcode, _invalidOpcode,
        )),
    _invalidOpcode,
    _invalidOpcode,
    ))
decode_DB = SwitchModRMMod((
    DecodeFPU('fild',       ('Md',), ()),
    DecodeFPU('fisttp',     ('Md',), ()),
    DecodeFPU('fist',       ('Md',), ()),
    DecodeFPU('fistp',      ('Md',), ()),
    _invalidOpcode,
    DecodeFPU('fld',        ('Mt',), ()),
    _invalidOpcode,
    DecodeFPU('fst',        ('Mt',), ()),
    ), (
    DecodeFPU('fcmovnb',    ('st(0)', 'Kt'), ()),
    DecodeFPU('fcmovne',    ('st(0)', 'Kt'), ()),
    DecodeFPU('fcmovnbe',   ('st(0)', 'Kt'), ()),
    DecodeFPU('fcmovnu',    ('st(0)', 'Kt'), ()),
    SwitchModRMRM((
        _invalidOpcode, _invalidOpcode,
        DecodeFPU('fclex',  (), ()),
        DecodeFPU('finit',  (), ()),
        _invalidOpcode, _invalidOpcode,
        _invalidOpcode, _invalidOpcode,
        )),
    DecodeFPU('fucomi',     ('st(0)', 'Kt'), ()),
    DecodeFPU('fcomi',      ('st(0)', 'Kt'), ()),
    _invalidOpcode,
    ))
decode_DC = SwitchModRMMod((
    DecodeFPU('fadd',       ('Mq',), ()),
    DecodeFPU('fmul',       ('Mq',), ()),
    DecodeFPU('fcom',       ('Mq',), ()),
    DecodeFPU('fcomp',      ('Mq',), ()),
    DecodeFPU('fsub',       ('Mq',), ()),
    DecodeFPU('fsubr',      ('Mq',), ()),
    DecodeFPU('fdiv',       ('Mq',), ()),
    DecodeFPU('fdivr',      ('Mq',), ()),
    ), (
    DecodeFPU('fadd',       ('Kt', 'st(0)'), ()),
    DecodeFPU('fmul',       ('Kt', 'st(0)'), ()),
    _invalidOpcode, _invalidOpcode,
    DecodeFPU('fsubr',      ('Kt', 'st(0)'), ()),
    DecodeFPU('fsub',       ('Kt', 'st(0)'), ()),
    DecodeFPU('fdivr',      ('Kt', 'st(0)'), ()),
    DecodeFPU('fdiv',       ('Kt', 'st(0)'), ()),
    ))
decode_DD = SwitchModRMMod((
    DecodeFPU('fld',        ('Mq',), ()),
    DecodeFPU('fisttp',     ('Mq',), ()),
    DecodeFPU('fst',        ('Mq',), ()),
    DecodeFPU('fstp',       ('Mq',), ()),
    DecodeFPU('frstor',     ('Md',), ()), # 98/108 bytes
    _invalidOpcode,
    DecodeFPU('fsave',      ('Md',), ()), # 98/108 bytes
    DecodeFPU('fstsw',      ('Mw',), ()),
    ), (
    DecodeFPU('ffree',      ('Kt',), ()),
    _invalidOpcode,
    DecodeFPU('fst',        ('Kt',), ()),
    DecodeFPU('fstp',       ('Kt',), ()),
    DecodeFPU('fucom',      ('Kt', 'st(0)'), ()),
    DecodeFPU('fucomp',     ('Kt',), ()),
    _invalidOpcode, _invalidOpcode,
    ))
decode_DE = SwitchModRMMod((
    DecodeFPU('fiadd',      ('Mw',), ()),
    DecodeFPU('fimul',      ('Mw',), ()),
    DecodeFPU('ficom',      ('Mw',), ()),
    DecodeFPU('ficomp',     ('Mw',), ()),
    DecodeFPU('fisub',      ('Mw',), ()),
    DecodeFPU('fisubr',     ('Mw',), ()),
    DecodeFPU('fidiv',      ('Mw',), ()),
    DecodeFPU('fidivr',     ('Mw',), ()),
    ), (
    DecodeFPU('faddp',      ('Kt', 'st(0)'), ()),
    DecodeFPU('fmulp',      ('Kt', 'st(0)'), ()),
    _invalidOpcode,
    SwitchModRMRM((
        _invalidOpcode,
        DecodeFPU('fcompp',(), ()),
        _invalidOpcode, _invalidOpcode,
        _invalidOpcode, _invalidOpcode,
        _invalidOpcode, _invalidOpcode,
        )),
    DecodeFPU('fsubrp',     ('Kt', 'st(0)'), ()),
    DecodeFPU('fsubp',      ('Kt', 'st(0)'), ()),
    DecodeFPU('fdivrp',     ('Kt', 'st(0)'), ()),
    DecodeFPU('fdivp',      ('Kt', 'st(0)'), ()),
    ))
decode_DF = SwitchModRMMod((
    DecodeFPU('fild',       ('Mw',), ()),
    DecodeFPU('fisttp',     ('Mw',), ()),
    DecodeFPU('fist',       ('Mw',), ()),
    DecodeFPU('fistp',      ('Mw',), ()),
    DecodeFPU('fbld',       ('Mb',), ()),
    DecodeFPU('fild',       ('Mq',), ()),
    DecodeFPU('fbstp',      ('Mb',), ()),
    DecodeFPU('fistp',      ('Mq',), ()),
    ), (
    _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode,
    SwitchModRMRM((
        DecodeFPU('fstsw',  ('ax',), ()),
        _invalidOpcode,
        _invalidOpcode, _invalidOpcode,
        _invalidOpcode, _invalidOpcode,
        _invalidOpcode, _invalidOpcode,
        )),
    DecodeFPU('fucomip',    ('st(0)', 'Kt'), ()),
    DecodeFPU('fcomip',     ('st(0)', 'Kt'), ()),
    _invalidOpcode,
    ))

decode_0F_32 = SwitchOpcode((
    # 00
    None, # ModRM opcode group 6
    None, # ModRM opcode group 7
    Decode('lar',       ('Gv', 'Ew'), ()),
    Decode('lsl',       ('Gv', 'Ew'), ()),
    _invalidOpcode,
    _invalidOpcode, # SYSCALL -- only 64-bit
    Decode('clts',      (), ()),
    _invalidOpcode, # SYSRET -- only 64-bit
    # 08
    Decode('invd',      (), ()),
    Decode('wbinvd',    (), ()),
    _invalidOpcode,
    Decode('ud2',       (), ()),
    _invalidOpcode,
    Decode('prefetchw', ('Ev',), ()),
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
    Decode('nop',       ('Ev',), ()),
    # 20
    Decode('mov',       ('Rd', 'Cd'), ()),
    Decode('mov',       ('Rd', 'Dd'), ()),
    Decode('mov',       ('Cd', 'Rd'), ()),
    Decode('mov',       ('Dd', 'Rd'), ()),
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 28
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 30
    Decode('wrmsr',     (), ()),
    Decode('rdtsc',     (), ()),
    Decode('rdmsr',     (), ()),
    Decode('rdpmc',     (), ()),
    Decode('sysenter',  (), ()),
    Decode('sysexit',   (), ()),
    _invalidOpcode,
    Decode('getsec',    (), ()),
    # 38
    None, # Escape 0F38
    _invalidOpcode,
    None, # Escape 0F3A
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 40
    Decode('cmovo',     ('Gv', 'Ev'), ()),
    Decode('cmovno',    ('Gv', 'Ev'), ()),
    Decode('cmovb',     ('Gv', 'Ev'), ()),
    Decode('cmovae',    ('Gv', 'Ev'), ()),
    Decode('cmove',     ('Gv', 'Ev'), ()),
    Decode('cmovne',    ('Gv', 'Ev'), ()),
    Decode('cmovbe',    ('Gv', 'Ev'), ()),
    Decode('cmova',     ('Gv', 'Ev'), ()),
    # 48
    Decode('cmovs',     ('Gv', 'Ev'), ()),
    Decode('cmovns',    ('Gv', 'Ev'), ()),
    Decode('cmovp',     ('Gv', 'Ev'), ()),
    Decode('cmovnp',    ('Gv', 'Ev'), ()),
    Decode('cmovl',     ('Gv', 'Ev'), ()),
    Decode('cmovge',    ('Gv', 'Ev'), ()),
    Decode('cmovle',    ('Gv', 'Ev'), ()),
    Decode('cmovg',     ('Gv', 'Ev'), ()),
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
    Decode('vmread',    ('Ey', 'Gy'), ()),
    Decode('vmwrite',   ('Gy', 'Ey'), ()),
    _invalidOpcode,
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # 80
    Decode('jo',        ('Jz',), ()),
    Decode('jno',       ('Jz',), ()),
    Decode('jb',        ('Jz',), ()),
    Decode('jae',       ('Jz',), ()),
    Decode('je',        ('Jz',), ()),
    Decode('jne',       ('Jz',), ()),
    Decode('jbe',       ('Jz',), ()),
    Decode('ja',        ('Jz',), ()),
    # 88
    Decode('js',        ('Jz',), ()),
    Decode('jns',       ('Jz',), ()),
    Decode('jp',        ('Jz',), ()),
    Decode('jnp',       ('Jz',), ()),
    Decode('jl',        ('Jz',), ()),
    Decode('jge',       ('Jz',), ()),
    Decode('jle',       ('Jz',), ()),
    Decode('jg',        ('Jz',), ()),
    # 90
    Decode('seto',      ('Eb',), ()),
    Decode('setno',     ('Eb',), ()),
    Decode('setb',      ('Eb',), ()),
    Decode('setae',     ('Eb',), ()),
    Decode('sete',      ('Eb',), ()),
    Decode('setne',     ('Eb',), ()),
    Decode('setbe',     ('Eb',), ()),
    Decode('seta',      ('Eb',), ()),
    # 98
    Decode('sets',      ('Eb',), ()),
    Decode('setns',     ('Eb',), ()),
    Decode('setp',      ('Eb',), ()),
    Decode('setnp',     ('Eb',), ()),
    Decode('setl',      ('Eb',), ()),
    Decode('setge',     ('Eb',), ()),
    Decode('setle',     ('Eb',), ()),
    Decode('setg',      ('Eb',), ()),
    # A0
    Decode('push',      ('fs',), ()),
    Decode('pop',       ('fs',), ()),
    Decode('cpuid',     (), ()),
    Decode('bt',        ('Ev', 'Gv'), ()),
    Decode('shld',      ('Ev', 'Gv', 'Ib'), ()),
    Decode('shld',      ('Ev', 'Gv', 'cl'), ()),
    _invalidOpcode,
    _invalidOpcode,
    # A8
    Decode('push',      ('gs',), ()),
    Decode('pop',       ('gs',), ()),
    Decode('rsm',       (), ()),
    Decode('bts',       ('Ev', 'Gv'), ()),
    Decode('shrd',      ('Ev', 'Gv', 'Ib'), ()),
    Decode('shrd',      ('Ev', 'Gv', 'cl'), ()),
    decode_0F_AE, # Group 15
    Decode('imul',      ('Gv', 'Ev'), ()),
    # B0
    Decode('cmpxchg',   ('Eb', 'Gb'), ()),
    Decode('cmpxchg',   ('Ev', 'Gv'), ()),
    Decode('lss',       ('Gv', 'Mp'), ()),
    Decode('btr',       ('Ev', 'Gv'), ()),
    Decode('lfs',       ('Gv', 'Mp'), ()),
    Decode('lgs',       ('Gv', 'Mp'), ()),
    Decode('movzx',     ('Gv', 'Eb'), ()),
    Decode('movzx',     ('Gv', 'Ew'), ()),
    # B8
    _invalidOpcode,
    None, # ModRM opcode group 10 ?
    decode_0F_BA, # ModRM opcode group 8
    Decode('btc',       ('Ev', 'Gv'), ()),
    Decode('bsf',       ('Gv', 'Ev'), ()),
    Decode('bsr',       ('Gv', 'Ev'), ()),
    Decode('movsx',     ('Gv', 'Eb'), ()),
    Decode('movsx',     ('Gv', 'Ew'), ()),
    # C0
    Decode('xadd',      ('Eb', 'Gb'), ()),
    Decode('xadd',      ('Ev', 'Gv'), ()),
    _invalidOpcode,
    _invalidOpcode,
    _invalidOpcode, _invalidOpcode, _invalidOpcode, _invalidOpcode,
    # C8
    Decode('bswap',     ('eax',), ('no66')),
    Decode('bswap',     ('ecx',), ('no66')),
    Decode('bswap',     ('edx',), ('no66')),
    Decode('bswap',     ('ebx',), ('no66')),
    Decode('bswap',     ('esp',), ('no66')),
    Decode('bswap',     ('ebp',), ('no66')),
    Decode('bswap',     ('esi',), ('no66')),
    Decode('bswap',     ('edi',), ('no66')),
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
    Decode('add',       ('Eb', 'Gb'), ()),
    Decode('add',       ('Ev', 'Gv'), ('allow66')),
    Decode('add',       ('Gb', 'Eb'), ()),
    Decode('add',       ('Gv', 'Ev'), ('allow66')),
    Decode('add',       ('al', 'Ib'), ()),
    Decode('add',       ('?ax', 'Iz'), ('allow66')),
    Decode('push',      ('es',), ()), # invalid in x64
    Decode('pop',       ('es',), ()), # invalid in x64
    # 08
    Decode('or',        ('Eb', 'Gb'), ()),
    Decode('or',        ('Ev', 'Gv'), ('allow66')),
    Decode('or',        ('Gb', 'Eb'), ()),
    Decode('or',        ('Gv', 'Ev'), ('allow66')),
    Decode('or',        ('al', 'Ib'), ()),
    Decode('or',        ('?ax', 'Iz'), ('allow66')),
    Decode('push',      ('cs',), ()), # invalid in x64
    decode_0F_32, # Escape 0F
    # 10
    Decode('adc',       ('Eb', 'Gb'), ()),
    Decode('adc',       ('Ev', 'Gv'), ('allow66')),
    Decode('adc',       ('Gb', 'Eb'), ()),
    Decode('adc',       ('Gv', 'Ev'), ('allow66')),
    Decode('adc',       ('al', 'Ib'), ()),
    Decode('adc',       ('?ax', 'Iz'), ('allow66')),
    Decode('push',      ('ss',), ()), # invalid in x64
    Decode('pop',       ('ss',), ()), # invalid in x64
    # 18
    Decode('sbb',       ('Eb', 'Gb'), ()),
    Decode('sbb',       ('Ev', 'Gv'), ('allow66')),
    Decode('sbb',       ('Gb', 'Eb'), ()),
    Decode('sbb',       ('Gv', 'Ev'), ('allow66')),
    Decode('sbb',       ('al', 'Ib'), ()),
    Decode('sbb',       ('?ax', 'Iz'), ('allow66')),
    Decode('push',      ('ds',), ()), # invalid in x64
    Decode('pop',       ('ds',), ()), # invalid in x64
    # 20
    Decode('and',       ('Eb', 'Gb'), ()),
    Decode('and',       ('Ev', 'Gv'), ('allow66')),
    Decode('and',       ('Gb', 'Eb'), ()),
    Decode('and',       ('Gv', 'Ev'), ('allow66')),
    Decode('and',       ('al', 'Ib'), ()),
    Decode('and',       ('?ax', 'Iz'), ('allow66')),
    SegmentOverridePrefix('es',),
    Decode('daa',       (), ()),
    # 28
    Decode('sub',       ('Eb', 'Gb',), ()),
    Decode('sub',       ('Ev', 'Gv'), ('allow66')),
    Decode('sub',       ('Gb', 'Eb'), ()),
    Decode('sub',       ('Gv', 'Ev'), ('allow66')),
    Decode('sub',       ('al', 'Ib'), ()),
    Decode('sub',       ('?ax', 'Iz'), ('allow66')),
    SegmentOverridePrefix('cs',),
    Decode('das',       (), ()),
    # 30
    Decode('xor',       ('Eb', 'Gb'), ()),
    Decode('xor',       ('Ev', 'Gv'), ('allow66')),
    Decode('xor',       ('Gb', 'Eb'), ()),
    Decode('xor',       ('Gv', 'Ev'), ('allow66')),
    Decode('xor',       ('al', 'Ib'), ()),
    Decode('xor',       ('?ax', 'Iz'), ('allow66')),
    SegmentOverridePrefix('ss',),
    Decode('aaa',       (), ()),
    # 38
    Decode('cmp',       ('Eb', 'Gb'), ()),
    Decode('cmp',       ('Ev', 'Gv'), ('allow66')),
    Decode('cmp',       ('Gb', 'Eb'), ()),
    Decode('cmp',       ('Gv', 'Ev'), ('allow66')),
    Decode('cmp',       ('al', 'Ib'), ()),
    Decode('cmp',       ('?ax', 'Iz'), ('allow66')),
    SegmentOverridePrefix('ds',),
    Decode('aas',       (), ()),
    # 40
    Decode('inc',       ('?ax',), ('allow66')),
    Decode('inc',       ('?cx',), ('allow66')),
    Decode('inc',       ('?dx',), ('allow66')),
    Decode('inc',       ('?bx',), ('allow66')),
    Decode('inc',       ('?sp',), ('allow66')),
    Decode('inc',       ('?bp',), ('allow66')),
    Decode('inc',       ('?si',), ('allow66')),
    Decode('inc',       ('?di',), ('allow66')),
    # 48
    Decode('dec',       ('?ax',), ('allow66')),
    Decode('dec',       ('?cx',), ('allow66')),
    Decode('dec',       ('?dx',), ('allow66')),
    Decode('dec',       ('?bx',), ('allow66')),
    Decode('dec',       ('?sp',), ('allow66')),
    Decode('dec',       ('?bp',), ('allow66')),
    Decode('dec',       ('?si',), ('allow66')),
    Decode('dec',       ('?di',), ('allow66')),
    # 50
    Decode('push',      ('?ax',), ('allow66')),
    Decode('push',      ('?cx',), ('allow66')),
    Decode('push',      ('?dx',), ('allow66')),
    Decode('push',      ('?bx',), ('allow66')),
    Decode('push',      ('?sp',), ('allow66')),
    Decode('push',      ('?bp',), ('allow66')),
    Decode('push',      ('?si',), ('allow66')),
    Decode('push',      ('?di',), ('allow66')),
    # 58
    Decode('pop',       ('?ax',), ('allow66')),
    Decode('pop',       ('?cx',), ('allow66')),
    Decode('pop',       ('?dx',), ('allow66')),
    Decode('pop',       ('?bx',), ('allow66')),
    Decode('pop',       ('?sp',), ('allow66')),
    Decode('pop',       ('?bp',), ('allow66')),
    Decode('pop',       ('?si',), ('allow66')),
    Decode('pop',       ('?di',), ('allow66')),
    # 60
    Decode('pusha',     (), ()), # invalid in x64
    Decode('popa',      (), ()), # invalid in x64
    Decode('bound',     ('Gv', 'Ma'), ()), # invalid in x64
    Decode('arpl',      ('Ew', 'Gw'), ()),
    SegmentOverridePrefix('fs',),
    SegmentOverridePrefix('gs',),
    OperandSizePrefix(),
    AddressSizePrefix(),
    # 68
    Decode('push',      ('Iz',), ('allow66')),
    Decode('imul',      ('Gv', 'Ev', 'Iz'), ('allow66')),
    Decode('push',      ('Ib',), ()),
    Decode('imul',      ('Gv', 'Ev', 'Ib'), ('allow66')),
    Decode('ins',       ('Yb', 'dx'), ()),
    Decode('ins',       ('Yz', 'dx'), ('allow66')),
    Decode('outs',      ('dx', 'Xb'), ()),
    Decode('outs',      ('dx', 'Xz'), ('allow66')),
    # 70
    Decode('jo',        ('Jb',), ()),
    Decode('jno',       ('Jb',), ()),
    Decode('jb',        ('Jb',), ()),
    Decode('jae',       ('Jb',), ()),
    Decode('je',        ('Jb',), ()),
    Decode('jne',       ('Jb',), ()),
    Decode('jbe',       ('Jb',), ()),
    Decode('ja',        ('Jb',), ()),
    # 78
    Decode('js',        ('Jb',), ()),
    Decode('jns',       ('Jb',), ()),
    Decode('jp',        ('Jb',), ()),
    Decode('jnp',       ('Jb',), ()),
    Decode('jl',        ('Jb',), ()),
    Decode('jge',       ('Jb',), ()),
    Decode('jle',       ('Jb',), ()),
    Decode('jg',        ('Jb',), ()),
    # 80
    decode_80_32, # ModRM opcode group 1
    decode_81_32, # ModRM opcode group 1
    decode_82_32, # ModRM opcode group 1
    decode_83_32, # ModRM opcode group 1
    Decode('test',      ('Eb', 'Gb'), ()),
    Decode('test',      ('Ev', 'Gv'), ('allow66')),
    Decode('xchg',      ('Eb', 'Gb'), ()),
    Decode('xchg',      ('Ev', 'Gv'), ('allow66')),
    # 88
    Decode('mov',       ('Eb', 'Gb'), ()),
    Decode('mov',       ('Ev', 'Gv'), ('allow66')),
    Decode('mov',       ('Gb', 'Eb'), ()),
    Decode('mov',       ('Gv', 'Ev'), ('allow66')),
    Decode('mov',       ('Ev', 'Sw'), ('allow66')),
    Decode('lea',       ('Gv', 'Mv'), ('allow66')), # TBD, docs not clear
    Decode('mov',       ('Sw', 'Ew'), ('allow66')),
    decode_8F_32, # ModRM opcode group 1A
    # 90
    Decode('nop',       (), ()),
    Decode('xchg',      ('?cx', '?ax'), ('allow66')),
    Decode('xchg',      ('?dx', '?ax'), ('allow66')),
    Decode('xchg',      ('?bx', '?ax'), ('allow66')),
    Decode('xchg',      ('?sp', '?ax'), ('allow66')),
    Decode('xchg',      ('?bp', '?ax'), ('allow66')),
    Decode('xchg',      ('?si', '?ax'), ('allow66')),
    Decode('xchg',      ('?di', '?ax'), ('allow66')),
    # 98
    Decode('cwde',      (), ()),
    Decode('cdq',       (), ()),
    Decode('callf',     ('Ap',), ()),
    Decode('wait',      (), ()),
    Decode('pushf',     ('Fv',), ()),
    Decode('popf',      ('Fv',), ()),
    Decode('sahf',      (), ()),
    Decode('lahf',      (), ()),
    # A0
    Decode('mov',       ('al', 'Ob'), ()),
    Decode('mov',       ('?ax', 'Ov'), ('allow66')),
    Decode('mov',       ('Ob', 'al'), ()),
    Decode('mov',       ('Ov', '?ax'), ('allow66')),
    Decode('movs',      ('Yb', 'Xb'), ()),
    Decode('movs',      ('Yv', 'Xv'), ('allow66')),
    Decode('cmps',      ('Xb', 'Yb'), ()),
    Decode('cmps',      ('Xv', 'Yv'), ('allow66')),
    # A8
    Decode('test',      ('al', 'Ib'), ()),
    Decode('test',      ('?ax', 'Iz'), ('allow66')),
    Decode('stos',      ('Yb', 'al'), ()),
    Decode('stos',      ('Yv', '?ax'), ('allow66')),
    Decode('lods',      ('al', 'Xb'), ()),
    Decode('lods',      ('?ax', 'Xv'), ('allow66')),
    Decode('scas',      ('al', 'Xb'), ()),
    Decode('scas',      ('?ax', 'Xv'), ('allow66')),
    # B0(
    Decode('mov',       ('al', 'Ib'), ()),
    Decode('mov',       ('cl', 'Ib'), ()),
    Decode('mov',       ('dl', 'Ib'), ()),
    Decode('mov',       ('bl', 'Ib'), ()),
    Decode('mov',       ('ah', 'Ib'), ()),
    Decode('mov',       ('ch', 'Ib'), ()),
    Decode('mov',       ('dh', 'Ib'), ()),
    Decode('mov',       ('bh', 'Ib'), ()),
    # B8
    Decode('mov',       ('?ax', 'Iv'), ('allow66')),
    Decode('mov',       ('?cx', 'Iv'), ('allow66')),
    Decode('mov',       ('?dx', 'Iv'), ('allow66')),
    Decode('mov',       ('?bx', 'Iv'), ('allow66')),
    Decode('mov',       ('?sp', 'Iv'), ('allow66')),
    Decode('mov',       ('?bp', 'Iv'), ('allow66')),
    Decode('mov',       ('?si', 'Iv'), ('allow66')),
    Decode('mov',       ('?di', 'Iv'), ('allow66')),
    # C0
    decode_C0_32, # ModRM opcode group 2
    decode_C1_32, # ModRM opcode group 2
    Decode('retn',      ('Iw',), ()),
    Decode('retn',      (), ()),
    Decode('les',       ('Gz', 'Mp'), ('allow66')),
    Decode('lds',       ('Gz', 'Mp'), ('allow66')),
    decode_C6_32, # ModRM opcode group 11
    decode_C7_32, # ModRM opcode group 11
    # C8
    Decode('enter',     ('Iw', 'Ib'), ()),
    Decode('leave',     (), ()),
    Decode('retf',      ('Iw',), ()),
    Decode('retf',      (), ()),
    Decode('int3',      (), ()),
    Decode('int',       ('Ib',), ()),
    Decode('into',      (), ()),
    Decode('iret',      (), ()),
    # D0
    decode_D0_32, # ModRM opcode group 2
    decode_D1_32, # ModRM opcode group 2
    decode_D2_32, # ModRM opcode group 2
    decode_D3_32, # ModRM opcode group 2
    Decode('aam',       ('Ib',), ()),
    Decode('aad',       ('Ib',), ()),
    _invalidOpcode,
    Decode('xlat',      (), ()),
    # D8
    decode_D8, # FPU escape
    decode_D9, # FPU escape
    decode_DA, # FPU escape
    decode_DB, # FPU escape
    decode_DC, # FPU escape
    decode_DD, # FPU escape
    decode_DE, # FPU escape
    decode_DF, # FPU escape
    # E0
    Decode('loopnz',    ('Jb',), ()),
    Decode('loopz',     ('Jb',), ()),
    Decode('loop',      ('Jb',), ()),
    Decode('jcxz',      ('Jb',), ()),
    Decode('in',        ('al', 'Ib'), ()),
    Decode('in',        ('?ax', 'Ib'), ('allow66')),
    Decode('out',       ('Ib', 'al'), ()),
    Decode('out',       ('Ib', '?ax'), ('allow66')),
    # E8
    Decode('call',      ('Jz',), ()),
    Decode('jmp',       ('Jz',), ()),
    Decode('jmp',       ('Ap',), ()),
    Decode('jmp',       ('Jb',), ()),
    Decode('in',        ('al', 'dx'), ()),
    Decode('in',        ('?ax', 'dx'), ('allow66')),
    Decode('out',       ('dx', 'al'), ()),
    Decode('out',       ('dx', '?ax'), ('allow66')),
    # F0
    LockPrefix(),
    _invalidOpcode,
    RepnePrefix(),
    RepePrefix(),
    Decode('hlt',       (), ()),
    Decode('cmc',       (), ()),
    decode_F6_32, # ModRM opcode group 3
    decode_F7_32, # ModRM opcode group 3
    # F8
    Decode('clc',       (), ()),
    Decode('stc',       (), ()),
    Decode('cli',       (), ()),
    Decode('sti',       (), ()),
    Decode('cld',       (), ()),
    Decode('std',       (), ()),
    decode_FE_32, # ModRM opcode group 4
    decode_FF_32)) # ModRM opcode group 5
#

def decode(state):
    state.handler = decode_main_32
    return state.handler(state)

class Printer:
    """Pretty print the insn"""
    def print_insn(self, insn, insn_width=10):
        ops = []
        for op in insn.operands:
            ops.append(self._print_op(op))
        fmt = '%%-%ds %%s' % insn_width
        mnem_list = []
        if insn.prefix_F0:
            mnem_list.append('lock')
        if insn.prefix_F2:
            mnem_list.append('repne')
        if insn.prefix_F3:
            mnem_list.append('repe')
        mnem_list.append(insn.mnemonic)
        mnemonic = ' '.join(mnem_list)
        return fmt % (mnemonic, ', '.join(ops))
    def _print_op(self, op):
        if isinstance(op, Immediate):
            return self._print_imm(op)
        if isinstance(op, MemoryRef):
            return self._print_memref(op)
        if isinstance(op, Address):
            return self._print_addr(op)
        if isinstance(op, Register):
            return self._print_reg(op)
        raise Exception("I don't know how to print this.")
    def _print_imm(self, op):
        return str(op)
    def _print_memref(self, op):
        addr = None
        if op.base is not None:
            addr = self._print_reg(op.base)
        if op.index is not None:
            index = '%s*%d' % (self._print_reg(op.index), op.scale)
            if addr is None:
                addr = index
            else:
                addr += '+' + index
        if op.displ is not None:
            displ = self._print_imm(op.displ)
            if addr is None:
                addr = displ
            else:
                if not op.displ.signed:
                    addr += '+' + displ
                else:
                    addr += displ
        return '%s %s:[%s]' % (_opwidth_names[op.size], self._print_reg(op.seg), addr)
    def _print_addr(self, op):
        return '%s:%s' % (op.seg, op.off)
    def _print_reg(self, op):
        return str(op)
#
