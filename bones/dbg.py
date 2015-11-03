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
        self._arm()
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
        self.process.write_memory(address, 1, "\xCC")

    def _disarm(self):
        self.process.write_memory(address, 1, self.old_byte)
        self._write_byte(self.address, self.old_byte)

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

class Process(object):
    """An abstraction representing a debugged process."""

    PAGE_NOACCESS = 0x00000001
    PAGE_READONLY = 0x00000002
    PAGE_READWRITE = 0x00000004
    PAGE_WRITECOPY = 0x00000008
    PAGE_EXECUTE = 0x00000010
    PAGE_EXECUTE_READ = 0x00000020
    PAGE_EXECUTE_READWRITE = 0x00000040
    PAGE_EXECUTE_WRITECOPY = 0x00000080
    PAGE_GUARD = 0x00000100
    PAGE_NOCACHE = 0x00000200
    PAGE_WRITECOMBINE = 0x00000400

    def __init__(self, pid, handle, base_address):
        self.id = pid
        self.handle = handle
        self.base_address = base_address
        self.image = None
        self.initial_thread = None
        self.exit_status = None
        self.threads = {}
        self.modules = {}
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

    def terminate(self, exit_code=0xDEADBEEFL):
        _bones.process_terminate(self.handle, exit_code)
    def read_memory(self, address, size):
        return _bones.vmem_read(self.handle, address, size)
    def write_memory(self, address, buffer):
        return _bones.vmem_write(self.handle, address, buffer)
    def query_memory(self, address):
        return _bones.vmem_query(self.handle, address)
    def protect_memory(self, address, size, protect):
        return _bones.vmem_protect(self.handle, address, size, protect)
    def query_section_name(self, address):
        return _bones.vmem_query_section_name(self.handle, address)
#

class Thread(object):
    """An abstraction representing a thread within a debugged process."""
    def __init__(self, tid, handle, process, start_address):
        self.id = tid
        self.handle = handle
        self.process = process
        self.start_address = start_address
        self.is_initial = False
        self.exit_status = None

    def __get_context(self):
        return _bones.thread_get_context(self.handle)
    def __set_context(self, value):
        return _bones.thread_set_context(self.handle, value)
    context = property(__get_context, __set_context, None, "Thread context")

    def __get_teb(self):
        return _bones.thread_get_teb(self.handle)
    teb_address = property(__get_teb, None, None, "Thread's TEB address")

    def set_single_step(self):
        _bones.thread_set_single_step(self.handle)
    def suspend(self):
        return _bones.thread_suspend(self.handle)
    def resume(self):
        return _bones.thread_resume(self.handle)
#

class Module(object):
    """An abstraction representing a module within a debugged process."""

    def __init__(self, base_address, process):
        self.base_address = base_address
        self.process = process

    def get_entry_point(self):
        # TODO
        return None

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
                    if self.process.query_section_name(address) != self.path:
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
            self._path = self.process.query_section_name(self.base_address)
            return self._path

    name = property(get_name, None, None, "Module file name")
    path = property(get_path, None, None, "Module file path")
    mapped_size = property(get_mapped_size, None, None, "Module's size in virtual memory")
#

class ExceptionInfo(object):
    def __init__(self, info):
        self.code, self.address, self.flags, self.args, self.nested = info
    def __str__(self):
        return "Exception %08X at address %08X" % (self.code, self.address)
class AccessViolationInfo(ExceptionInfo):
    __kind_map = { 0: 'read', 1: 'write', 8: 'dep' }
    def __init__(self, info):
        ExceptionInfo.__init__(self, info)
        self.kind = AccessViolationInfo.__kind_map[self.args[0]]
        self.target = self.args[1]
    def __str__(self):
        return "Access violation at address %08X when accessing %08X (%s)" % (self.address, self.target, self.kind)
#

class Debugger(_bones.Debugger):
    """The debugger object.

    The object provides access to debugging capabilities on the system.
    """

    def __init__(self):
        _bones.Debugger.__init__(self)
        self.processes = {}

    # These event handlers are designed to be overridden as needed when subclassing

    def on_process_create_begin(self, process):
        "Called when the process is created (before thread/module creation)"
        pass
    def on_process_create_end(self, process):
        "Called when the process is created (after initial thread creation)"
        pass
    def on_process_exit(self, process):
        "Called when the process has exited"
        pass
    def on_thread_create(self, thread):
        "Called when the thread has been created"
        pass
    def on_thread_exit(self, thread):
        "Called when the thread has exited"
        pass
    def on_module_load(self, module):
        "Called when the module has been loaded"
        pass
    def on_module_unload(self, module):
        "Called when the module has been unloaded"
        pass
    def on_breakpoint(self, thread, context, bp):
        "Called when a breakpoint exception occurs"
        pass
    def on_single_step(self, thread):
        "Called when a single step exception occurs"
        pass
    def on_exception(self, thread, info, first_chance):
        "Called when an exception occurs (other than SS/BP)"
        return Debugger.DBG_EXCEPTION_NOT_HANDLED

    # These are internal handlers not designed to be user accessible

    def _on_process_create(self, pid, process_handle, tid, thread_handle, base_address, start_address):
        """The DbgCreateProcessStateChange handler."""
        process = Process(pid, process_handle, base_address)
        self.processes[pid] = process
        self.on_process_create_begin(process)
        # Fake the main module load
        self._on_module_load(pid, base_address)
        process.image = process.modules[base_address]
        # Fake the initial thread creation
        self._on_thread_create(pid, tid, thread_handle, start_address)
        initial_thread = process.threads[tid]
        initial_thread.is_initial = True
        process.initial_thread = initial_thread
        # Let the user know we're done with initial stuff
        self.on_process_create_end(process)
        return Debugger.DBG_CONTINUE

    def _on_process_exit(self, pid, exit_status):
        """The DbgExitProcessStateChange handler."""
        process = self.processes[pid]
        process.exit_status = exit_status
        self.on_process_exit(self.processes[pid])
        del self.processes[pid]
        return Debugger.DBG_CONTINUE

    def _on_thread_create(self, pid, tid, handle, start_address):
        """The DbgCreateThreadStateChange handler."""
        process = self.processes[pid]
        thread = Thread(tid, handle, process, start_address)
        process.threads[tid] = thread
        self.on_thread_create(thread)
        return Debugger.DBG_CONTINUE

    def _on_thread_exit(self, pid, tid, exit_status):
        """The DbgExitThreadStateChange handler."""
        process = self.processes[pid]
        thread = process.threads[tid]
        thread.exit_status = exit_status
        self.on_thread_exit(thread)
        del process.threads[tid]
        return Debugger.DBG_CONTINUE

    def _on_module_load(self, pid, base_address):
        """The DbgLoadDllStateChange handler."""
        process = self.processes[pid]
        module = Module(base_address, process)
        process.modules[base_address] = module
        self.on_module_load(module)
        return Debugger.DBG_CONTINUE

    def _on_module_unload(self, pid, base_address):
        """The DbgUnloadDllStateChange handler."""
        process = self.processes[pid]
        self.on_module_unload(process.modules[base_address])
        del process.modules[base_address]
        return Debugger.DBG_CONTINUE

    def _on_exception(self, pid, tid, info, first_chance):
        """The DbgExceptionStateChange handler."""
        process = self.processes[pid]
        thread = process.threads[tid]
        if info[0] == 0xC0000005L:
            xinfo = AccessViolationInfo(info)
        else:
            xinfo = ExceptionInfo(info)
        result = self.on_exception(thread, xinfo, first_chance)
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

        self.on_breakpoint(thread, context, bp)

        if bp is not None and bp.auto_rearm:
            pass

        return Debugger.DBG_CONTINUE

    def _on_single_step(self, pid, tid):
        """The DbgSingleStepStateChange handler."""
        process = self.processes[pid]
        thread = process.threads[tid]
        self.on_single_step(thread)
        return Debugger.DBG_CONTINUE
#
