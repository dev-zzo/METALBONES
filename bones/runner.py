"""Entities related to performing an actual test run."""

from __future__ import print_function
import sys
import bones
import mcode

def info(text):
    print(text, file=sys.stderr)

class MemReader:
    def __init__(self, process, address):
        # No insns should be longer than 16 bytes, so try read them all
        self.data = process.read_memory(address, 16)
        self.offset = 0
    def read(self):
        b = ord(self.data[self.offset])
        self.offset += 1
        return b

def format_insn_at(self, process, address):
    try:
        reader = MemReader(process, address)
    except:
        return '%08x %-22s' % (address, '???')
    insn = mcode.decode(mcode.State(reader))
    return '%08x %-22s %s' % (address, insn.opcode_hex, mcode.Printer().print_insn(insn))

class Debugger(bones.Debugger):
    def __init__(self):
        bones.Debugger.__init__(self)
        self.initial_process = None
        self.ldr_breakpoint_hit = False
        self.initial_process_exited = False
        self.killing = False

    def on_process_create(self, p):
        info('[%05d] Process created.' % (p.id))
        if self.initial_process is None:
            self.initial_process = p

    def on_thread_create(self, t):
        info('[%05d/%05d] Thread created.' % (t.process.id, t.id))

    def on_thread_exit(self, t):
        info('[%05d/%05d] Thread exited, status %08x.' % (t.process.id, t.id, t.exit_status))

    def on_process_exit(self, p):
        info("[%05d] Process exited, status %08x." % (p.id, p.exit_status))
        if p.id == self.initial_process.id:
            self.initial_process = None
            self.initial_process_exited = True

    def on_module_load(self, m):
        info('[%05d] Module loaded at %08x~%08x: %s.' % (
            m.process.id,
            m.base_address,
            m.base_address + m.mapped_size - 1,
            m.name))

    def on_module_unload(self, m):
        info('[%05d] Module unloaded at %08x: %s.' % (m.process.id, m.base_address, m.name))

    def on_exception(self, t, exc_info, first_chance):
        info('[%05d/%05d] Exception caught:' % (t.process.id, t.id))
        info(str(exc_info))
        
        # TODO: handle 1st-chance right away?
        if first_chance:
            info('First-chance, passing to the application.')
            return Debugger.DBG_EXCEPTION_NOT_HANDLED
        else:
            info('Second-chance, handling.')
            # TODO: handle me.
            return Debugger.DBG_EXCEPTION_NOT_HANDLED

    def on_breakpoint(self, t):
        ctx = t.context
        loc = t.process.get_location_from_va(ctx.eip)
        info('[%05d/%05d] Breakpoint hit at %s.' % (t.process.id, t.id, loc))
        # Check for the initial BP, else handle as exception.
        if not self.ldr_breakpoint_hit and loc.module is not None and loc.module.name.lower() == 'ntdll.dll':
            info('[%05d/%05d] Initial breakpoint in LdrpInitializeProcess, ignoring.')
            self.ldr_breakpoint_hit = True
            return
        # TODO: handle me.
        pass
    
    def on_single_step(self, t):
        info('[%05d/%05d] Single step hit -- should not happen.')
#

d = Debugger()

d.spawn('victim.exe 2')

idle_count = 0
while not d.initial_process_exited:
    if not d.wait_event(1000):
        idle_count += 1
        if idle_count >= 5 and not d.killing:
            d.p.terminate(0xDEADBEEF)
