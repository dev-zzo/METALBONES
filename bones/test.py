import bones
import mcode

class MemReader:
    def __init__(self, process, address):
        self.process = process
        self.address = address
    def read(self):
        b = ord(self.process.read_memory(self.address, 1))
        self.address += 1
        return b

class TestDebugger(bones.Debugger):
    def __init__(self):
        bones.Debugger.__init__(self)
        self.done = False
        self.idle_count = 0
        self.killing = False
        self.p = None

    def on_process_create(self, p):
        print "[%05d] Process created." % (p.id)
        self.p = p

    def on_thread_create(self, t):
        print "[%05d/%05d] Thread created." % (t.process.id, t.id)

    def on_thread_exit(self, t):
        print "[%05d/%05d] Thread exited, status %08x." % (t.process.id, t.id, t.exit_status)

    def on_process_exit(self, p):
        print "[%05d] Process exited, status %08x." % (p.id, p.exit_status)
        self.p = None
        self.done = True

    def on_module_load(self, m):
        print "[%05d] Module loaded at %08x+%08x:\n%s." % (m.process.id, m.base_address, m.mapped_size, m.path)

    def on_module_unload(self, m):
        print "[%05d] Module unloaded at %08x." % (m.process.id, m.base_address)

    def on_exception(self, t, info, first_chance):
        print "[%05d/%05d] Exception caught (%s-chance)." % (t.process.id, t.id, "first" if first_chance else "second")
        print str(info)
        try:
            reader = MemReader(t.process, info.address)
            decoder_state = mcode.State(reader)
            insn = decoder_state.decode()
            print '%08x %s %s' % (info.address, decoder_state.opcode_hex, insn)
        except Exception, e:
            print e
            print '%08x %s ???'% (info.address, decoder_state.opcode_hex)

    def on_breakpoint(self, t):
        print "[%05d/%05d] Breakpoint hit." % (t.process.id, t.id)
        ctx = t.context
        print str(ctx)
        print "Location: %s" % (t.process.get_location_from_va(ctx.eip))
#

d = TestDebugger()

d.spawn('victim.exe 2')

while not d.done:
    if not d.wait_event(1000):
        print "timed out"
        d.idle_count += 1
        if d.idle_count >= 5 and not d.killing:
            d.p.terminate(0xDEADBEEF)
