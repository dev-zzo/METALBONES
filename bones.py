import _bones

class Process(_bones.Process):
    pass
class Thread(_bones.Thread):
    pass
class Module(_bones.Module):
    pass

class Debugger(_bones.Debugger):
    def __init__(self):
        _bones.Debugger.__init__(self)

    def _on_process_create(self, pid, process_handle, tid, thread_handle, base_address, start_address):
        print "[%05d] Process created." % (pid)
        process = Process(pid, process_handle, base_address)
        self.processes[pid] = process
        try:
            self.on_process_create(process)
        except AttributeError:
            pass
        self._on_module_load(pid, base_address)
        self._on_thread_create(pid, tid, thread_handle, start_address)

    def _on_module_load(self, pid, base_address):
        print "[%05d] Module loaded: %08x." % (pid, base_address)
        process = self.processes[pid]
        module = Module(base_address, process)
        process.modules[base_address] = module
        try:
            self.on_module_load(module)
        except AttributeError:
            pass
        
    def _on_thread_create(self, pid, tid, handle, start_address):
        print "[%05d/%05d] Thread created: handle = %08x, start addr = %08x." % (pid, tid, handle, start_address)
        process = self.processes[pid]
        thread = Thread(tid, handle, process, start_address)
        process.threads[tid] = thread
        try:
            self.on_thread_create(thread)
        except AttributeError:
            pass
        
    def _on_thread_exit(self, pid, tid, exit_status):
        print "[%05d/%05d] Thread exited, status %08x." % (pid, tid, exit_status)
        process = self.processes[pid]
        thread = process.threads[tid]
        thread.exit_status = exit_status
        try:
            self.on_thread_exit(thread)
        except AttributeError:
            pass
        del process.threads[tid]
        
    def _on_module_unload(self, pid, base_address):
        print "[%05d] Module unloaded: %08x." % (pid, base_address)
        process = self.processes[pid]
        try:
            self.on_module_unload(process.modules[base_address])
        except AttributeError:
            pass
        del process.modules[base_address]
        
    def _on_process_exit(self, pid, exit_status):
        print "[%05d] Process exited, status %08x." % (pid, exit_status)
        process = self.processes[pid]
        process.exit_status = exit_status
        try:
            self.on_process_exit(self.processes[pid])
        except AttributeError:
            pass
        del self.processes[pid]
