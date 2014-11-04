import bones

class TestDebugger(bones.Debugger):
    def __init__(self):
        bones.Debugger.__init__(self)
        self.done = False
    
    def on_process_create(self, p):
        print "Process created!"
    def on_thread_create(self, t):
        print "Thread created!"
    def on_thread_exit(self, t):
        print "Thread exited!"
    def on_process_exit(self, p):
        print "Process exited!"
        self.done = True

d = TestDebugger()

d.spawn('cmd')

while not d.done:
    d.wait_event()
