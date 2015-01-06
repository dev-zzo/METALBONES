"""
Layer 2 of the METALBONES core -- Python wrappers.

This wraps CPython objects and adds more functionality that
can be more easily implemented in Python than in C.
"""

import _bones
import os.path

class BonesError(_bones.BonesException):
    pass

class InvalidOperationError(BonesError):
    pass

class Location:
    def __init__(self, rva, module=None):
        self.module = module
        self.rva = rva
    def __str__(self):
        if self.module is not None:
            return '%s+%08x' % (self.module.name, self.rva - self.module.base_address)
        return '%08x' % self.rva

class Breakpoint:
    """Software breakpoint class.
    
    This is used to implement "software breakpoints" via the int3 instruction.
    """
    def __init__(self, process, address):
        self.process = process
        self.address = address
        self.old_byte = None
        self.auto_rearm = False

    def __str__(self):
        return 'Breakpoint at %08x (%s)' % (self.address, 'armed' if self.is_armed() else 'disarmed')

    def is_armed(self):
        return self.old_byte is not None

    def arm(self):
        if self.old_byte is not None:
            raise InvalidOperationError('The breakpoint is already armed.')
        self.old_byte = self.process.read_memory(self.address, 1)
        self._write_byte(self.address, "\xCC")
        byte = self.process.read_memory(self.address, 1)
        if byte != "\xCC":
            raise BonesError('Failed to arm the breakpoint (read back: %02x)' % ord(byte))

    def disarm(self):
        if self.old_byte is None:
            raise InvalidOperationError('The breakpoint is not armed.')
        self._disarm()
        self.old_byte = None

    def _arm(self):
        self.old_byte = self.process.read_memory(self.address, 1)
        self._write_byte(self.address, "\xCC")

    def _disarm(self):
        self._write_byte(self.address, self.old_byte)

    def _write_byte(self, address, value):
        oldprotect = self.process.protect_memory(address, 1, Process.PAGE_READWRITE)
        # No need to flush -- x86 doesn't need it.
        self.process.write_memory(address, 1, value)
        self.process.protect_memory(address, 1, oldprotect)

class HwBreakpoint:
    """Hardware breakpoint class.
    
    This is used to abstract CPU debug registers and provide the interface 
    similar to how software breakpoints operate.
    
    These trigger the single stepping event.
    """

    EVENT_X = 0
    EVENT_W = 1
    EVENT_IO = 2 # Not actually implemented
    EVENT_RW = 3
    
    def __init__(self, process, address, event):
        self.process = process
        self.address = address
        self.event = event
    
class Process(_bones.Process):
    """An abstraction representing a debugged process."""
    def __init__(self, pid, process_handle, base_address):
        _bones.Process.__init__(self, pid, process_handle, base_address)
        self.image = None
        self.initial_thread = None
        self.breakpoints = {}

    def get_module_from_va(self, address):
        for m in self.modules.values():
            base = m.base_address
            if base <= address < (base + m.mapped_size):
                return m
        return None

    def get_location_from_va(self, address):
        return Location(address, self.get_module_from_va(address))

    def get_breakpoint(self, address):
        address = long(address)
        try:
            return self.breakpoints[address]
        except KeyError:
            bp = Breakpoint(self, address)
            self.breakpoints[address] = bp
            return bp
#

class Thread(_bones.Thread):
    """An abstraction representing a thread within a debugged process."""
    def __init__(self, tid, handle, process, start_address):
        _bones.Thread.__init__(self, tid, handle, process, start_address)
        self.is_initial = False
#

class Module(_bones.Module):
    """An abstraction representing a module within a debugged process."""
    
    def get_mapped_size(self):
        try:
            return self._mapped_size
        except:
            size = 0
            address = self.base_address
            while True:
                try:
                    pages = self.process.query_memory(address)
                    size += pages[1]
                    address += pages[1]
                    # Hit another module?
                    if self.process.query_section_file_name(address) != self.path:
                        break
                except _bones.NtStatusError:
                    # Hit unallocated space?
                    break
            self._mapped_size = size
            return self._mapped_size

    def get_name(self):
        return os.path.basename(self.path)

    def get_path(self):
        try:
            return self._path
        except:
            self._path = self.process.query_section_file_name(self.base_address)
            return self._path
    
    name = property(get_name, None, None, "Module file name")
    path = property(get_path, None, None, "Module file path")
    mapped_size = property(get_mapped_size, None, None, "Module's size in virtual memory")
#

class Debugger(_bones.Debugger):
    """The debugger object itself."""
    
    def __init__(self):
        _bones.Debugger.__init__(self)

    def _on_process_create(self, pid, process_handle, tid, thread_handle, base_address, start_address):
        """The DbgCreateProcessStateChange handler."""
        
        process = Process(pid, process_handle, base_address)
        self.processes[pid] = process
        try:
            self.on_process_create(process)
        except AttributeError, e:
            if 'on_process_create' not in e.message:
                raise

        self._on_module_load(pid, base_address)
        process.image = process.modules[base_address]

        self._on_thread_create(pid, tid, thread_handle, start_address)
        initial_thread = process.threads[tid]
        initial_thread.is_initial = True
        process.initial_thread = initial_thread

        try:
            self.on_process_created(process)
        except AttributeError, e:
            if 'on_process_created' not in e.message:
                raise
        return Debugger.DBG_CONTINUE

    def _on_module_load(self, pid, base_address):
        """The DbgLoadDllStateChange handler."""
        
        process = self.processes[pid]
        module = Module(base_address, process)
        process.modules[base_address] = module
        try:
            self.on_module_load(module)
        except AttributeError, e:
            if 'on_module_load' not in e.message:
                raise
        return Debugger.DBG_CONTINUE

    def _on_thread_create(self, pid, tid, handle, start_address):
        """The DbgCreateThreadStateChange handler."""
        
        process = self.processes[pid]
        thread = Thread(tid, handle, process, start_address)
        process.threads[tid] = thread
        try:
            self.on_thread_create(thread)
        except AttributeError, e:
            if 'on_thread_create' not in e.message:
                raise
        return Debugger.DBG_CONTINUE

    def _on_thread_exit(self, pid, tid, exit_status):
        """The DbgExitThreadStateChange handler."""
        
        process = self.processes[pid]
        thread = process.threads[tid]
        thread.exit_status = exit_status
        try:
            self.on_thread_exit(thread)
        except AttributeError, e:
            if 'on_thread_exit' not in e.message:
                raise
        del process.threads[tid]
        return Debugger.DBG_CONTINUE

    def _on_module_unload(self, pid, base_address):
        """The DbgUnloadDllStateChange handler."""
        
        process = self.processes[pid]
        try:
            self.on_module_unload(process.modules[base_address])
        except AttributeError, e:
            if 'on_module_unload' not in e.message:
                raise
        del process.modules[base_address]
        return Debugger.DBG_CONTINUE

    def _on_process_exit(self, pid, exit_status):
        """The DbgExitProcessStateChange handler."""
        
        process = self.processes[pid]
        process.exit_status = exit_status
        try:
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
        result = Debugger.DBG_EXCEPTION_NOT_HANDLED
        try:
            result = self.on_exception(thread, info, first_chance)
        except AttributeError, e:
            if 'on_exception' not in e.message:
                raise
        return result

    def _on_breakpoint(self, pid, tid):
        """The DbgBreakpointStateChange handler."""
        
        process = self.processes[pid]
        thread = process.threads[tid]
        context = thread.context
        context.eip -= 1
        bp = None
        try:
            bp = process.breakpoints[context.eip]
            bp.disarm()
            thread.context = context
        except KeyError:
            pass

        try:
            self.on_breakpoint(thread, context, bp)
        except AttributeError, e:
            if 'on_breakpoint' not in e.message:
                raise
        
        if bp is not None and bp.auto_rearm:
            pass

        return Debugger.DBG_CONTINUE

    def _on_single_step(self, pid, tid):
        """The DbgSingleStepStateChange handler."""
        
        process = self.processes[pid]
        thread = process.threads[tid]
        try:
            self.on_single_step(thread)
        except AttributeError, e:
            if 'on_single_step' not in e.message:
                raise
        return Debugger.DBG_CONTINUE
#
