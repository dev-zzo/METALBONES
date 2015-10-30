import core
import mcode

class MemReader:
    def __init__(self, process, address):
        # No insns should be longer than 16 bytes, so try read them all
        self.data = process.read_memory(address, 16)
        self.offset = 0
    def read(self):
        b = ord(self.data[self.offset])
        self.offset += 1
        return b

class TestDebugger(core.Debugger):
    def __init__(self):
        core.Debugger.__init__(self)
        self.done = False
        self.idle_count = 0
        self.killing = False
        self.p = None

    def on_process_create_begin(self, p):
        print "[%05d] Process created." % (p.id)
        self.p = p

    def on_thread_create(self, t):
        print "[%05d/%05d] Thread created." % (t.process.id, t.id)
        print str(t.context)
        print self.format_insn_at(t.process, t.context.eip)
        # t.set_single_step()

    def on_thread_exit(self, t):
        print "[%05d/%05d] Thread exited, status %08x." % (t.process.id, t.id, t.exit_status)

    def on_process_exit(self, p):
        print "[%05d] Process exited, status %08x." % (p.id, p.exit_status)
        self.p = None
        self.done = True

    def on_module_load(self, m):
        print "[%05d] Module loaded at %08x~%08x:\n%s." % (m.process.id, m.base_address, m.mapped_size, m.path)

    def on_module_unload(self, m):
        print "[%05d] Module unloaded at %08x." % (m.process.id, m.base_address)

    def on_exception(self, t, info, first_chance):
        print "[%05d/%05d] Exception caught (%s-chance)." % (t.process.id, t.id, "first" if first_chance else "second")
        print str(info)
        if first_chance:
            return TestDebugger.DBG_EXCEPTION_NOT_HANDLED
        t.process.terminate(0)
        return TestDebugger.DBG_EXCEPTION_NOT_HANDLED

    def on_breakpoint(self, t, context, bp):
        print "[%05d/%05d] Breakpoint hit." % (t.process.id, t.id)
        print str(context)
        print "Location: %s" % (t.process.get_location_from_va(context.eip))
    
    def on_single_step(self, t):
        print "[%05d/%05d] Single stepping" % (t.process.id, t.id)
        #addr = 0
        #ctx = t.context
        addr = t.context.eip
        print self.format_insn_at(t.process, addr)
        # t.set_single_step()
    
    def format_insn_at(self, process, address):
        try:
            reader = MemReader(process, address)
        except:
            return '%08x %-22s' % (address, '???')
        printer = mcode.Printer()
        insn = mcode.decode(mcode.State(reader))
        return '%08x %-22s %s' % (address, insn.opcode_hex, printer.print_insn(insn))
#

d = TestDebugger()

d.spawn('victim.exe 2')

while not d.done:
    if not d.wait_event(1000):
        print "timed out"
        d.idle_count += 1
        if d.idle_count >= 5 and not d.killing:
            d.p.terminate(0xDEADBEEF)
