import bones

class TestDebugger(bones.Debugger):
    def __init__(self):
        bones.Debugger.__init__(self)
        self.done = False
        self.idle_count = 0
        self.killing = False
        self.p = None
    
    def on_process_create(self, p):
        print "Process created!"
        self.p = p
    def on_thread_create(self, t):
        print "Thread created!"
    def on_thread_exit(self, t):
        print "Thread exited!"
    def on_process_exit(self, p):
        print "Process exited!"
        self.p = None
        self.done = True

d = TestDebugger()

d.spawn('cmd')

while not d.done:
    if not d.wait_event(1000):
        print "timed out"
        d.idle_count += 1
        if d.idle_count >= 5 and not d.killing:
            d.p.terminate(1)
