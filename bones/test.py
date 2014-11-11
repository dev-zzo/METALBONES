import bones

class TestDebugger(bones.Debugger):
    def __init__(self):
        bones.Debugger.__init__(self)
        self.done = False
        self.idle_count = 0
        self.killing = False
        self.p = None

    def on_process_create(self, p):
        print "[%05d] Process created!!!" % (p.id)
        self.p = p
        print "PEB at %08x" % p.peb_address

    def on_thread_create(self, t):
        print "[%05d/%05d] Thread created." % (t.process.id, t.id)
        print "Thread context:"
        print str(t.context)
        print "TEB at %08x" % t.teb_address

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
        print "[%05d/%05d] Exception caught; first-chance: %s." % (t.process.id, t.id, first_chance)
        print str(info)
#

d = TestDebugger()

d.spawn('victim.exe 1')

while not d.done:
    if not d.wait_event(1000):
        print "timed out"
        d.idle_count += 1
        if d.idle_count >= 5 and not d.killing:
            d.p.terminate(0xDEADBEEF)
