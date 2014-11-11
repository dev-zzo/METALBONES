import _bones

class Process(_bones.Process):
    """An abstarction representing a debugged process."""
    # Nothing yet.
    pass
#

class Thread(_bones.Thread):
    """An abstarction representing a thread within a debugged process."""
    
    def enable_single_step(self):
        ctx = self.context
        ctx.eflags.tf = True
        self.context = ctx
#
    
class Module(_bones.Module):
    """An abstarction representing a module within a debugged process."""
    
    def get_mapped_size(self):
        try:
            return self._mapped_size
        except:
            size = 0
            addr = self.base_address
            while True:
                try:
                    pages = self.process.query_memory(addr)
                    size += pages[1]
                    addr += pages[1]
                    print repr(pages)
                    # Hit another module?
                    if self.process.query_section_file_name(addr) != self.path:
                        break
                except _bones.NtStatusError:
                    # Hit unallocated space?
                    break
            self._mapped_size = size
            return self._mapped_size

    def get_path(self):
        try:
            return self._path
        except:
            self._path = self.process.query_section_file_name(self.base_address)
            return self._path
    
    path = property(get_path, None, None, "Module file path")
    mapped_size = property(get_mapped_size, None, None, "Module's size in virtual memory")
#

class Debugger(_bones.Debugger):
    """The debugger object itself."""
    
    def __init__(self):
        _bones.Debugger.__init__(self)

    def _on_process_create(self, pid, process_handle, tid, thread_handle, base_address, start_address):
        """The DbgCreateProcessStateChange handler."""
        
        # print "[%05d] Process created." % (pid)
        process = Process(pid, process_handle, base_address)
        self.processes[pid] = process
        try:
            # Return result ignored; always DBG_CONTINUE
            self.on_process_create(process)
        except AttributeError, e:
            if 'on_process_create' not in e.message:
                raise
        self._on_module_load(pid, base_address)
        self._on_thread_create(pid, tid, thread_handle, start_address)
        return Debugger.DBG_CONTINUE

    def _on_module_load(self, pid, base_address):
        """The DbgLoadDllStateChange handler."""
        
        # print "[%05d] Module loaded: %08x." % (pid, base_address)
        process = self.processes[pid]
        module = Module(base_address, process)
        process.modules[base_address] = module
        try:
            # Return result ignored; always DBG_CONTINUE
            self.on_module_load(module)
        except AttributeError, e:
            if 'on_module_load' not in e.message:
                raise
        return Debugger.DBG_CONTINUE

    def _on_thread_create(self, pid, tid, handle, start_address):
        """The DbgCreateThreadStateChange handler."""
        
        # print "[%05d/%05d] Thread created: handle = %08x, start addr = %08x." % (pid, tid, handle, start_address)
        process = self.processes[pid]
        thread = Thread(tid, handle, process, start_address)
        process.threads[tid] = thread
        try:
            # Return result ignored; always DBG_CONTINUE
            self.on_thread_create(thread)
        except AttributeError, e:
            if 'on_thread_create' not in e.message:
                raise
        return Debugger.DBG_CONTINUE

    def _on_thread_exit(self, pid, tid, exit_status):
        """The DbgExitThreadStateChange handler."""
        
        # print "[%05d/%05d] Thread exited, status %08x." % (pid, tid, exit_status)
        process = self.processes[pid]
        thread = process.threads[tid]
        thread.exit_status = exit_status
        try:
            # Return result ignored; always DBG_CONTINUE
            self.on_thread_exit(thread)
        except AttributeError, e:
            if 'on_thread_exit' not in e.message:
                raise
        del process.threads[tid]
        return Debugger.DBG_CONTINUE

    def _on_module_unload(self, pid, base_address):
        """The DbgUnloadDllStateChange handler."""
        
        # print "[%05d] Module unloaded: %08x." % (pid, base_address)
        process = self.processes[pid]
        try:
            # Return result ignored; always DBG_CONTINUE
            self.on_module_unload(process.modules[base_address])
        except AttributeError, e:
            if 'on_module_unload' not in e.message:
                raise
        del process.modules[base_address]
        return Debugger.DBG_CONTINUE

    def _on_process_exit(self, pid, exit_status):
        """The DbgExitProcessStateChange handler."""
        
        # print "[%05d] Process exited, status %08x." % (pid, exit_status)
        process = self.processes[pid]
        process.exit_status = exit_status
        try:
            # Return result ignored; always DBG_CONTINUE
            self.on_process_exit(self.processes[pid])
        except AttributeError, e:
            if 'on_process_exit' not in e.message:
                raise
        del self.processes[pid]
        return Debugger.DBG_CONTINUE

    def _on_exception(self, pid, tid, info, first_chance):
        """The DbgExceptionStateChange handler."""
        
        process = self.processes[pid]
        thread = process.threads[tid]
        try:
            self.on_exception(thread, info, first_chance)
        except AttributeError, e:
            if 'on_exception' not in e.message:
                raise
        return Debugger.DBG_EXCEPTION_NOT_HANDLED

    def _on_breakpoint(self, pid, tid):
        """The DbgBreakpointStateChange handler."""
        
        process = self.processes[pid]
        thread = process.threads[tid]
        try:
            self.on_breakpoint(thread, info, first_chance)
        except AttributeError, e:
            if 'on_breakpoint' not in e.message:
                raise
        return Debugger.DBG_EXCEPTION_HANDLED

    def _on_single_step(self, pid, tid):
        """The DbgSingleStepStateChange handler."""
        
        process = self.processes[pid]
        thread = process.threads[tid]
        try:
            self.on_single_step(thread, info, first_chance)
        except AttributeError, e:
            if 'on_single_step' not in e.message:
                raise
        return Debugger.DBG_EXCEPTION_HANDLED
#
