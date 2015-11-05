"""
Layer 3 of the METALBONES core -- high-level code.

This governs the whole process of running a fuzzer.
"""

import dbg
import monitor
import logging

class ProcessMonitorAdapter(monitor.ProcessMonitor):
    "Route events to another handler object"
    def __init__(self, handler, delta_threshold=50, max_inactive=3):
        self.handler = handler
        monitor.ProcessMonitor.__init__(self, delta_threshold, max_inactive)
    def on_process_idle(self, process_id):
        self.handler.on_process_idle(process_id)
#
class DebuggerAdapter(dbg.Debugger):
    "Route events to another handler object"
    def __init__(self, handler):
        self.handler = handler
        dbg.Debugger.__init__(self)
    def on_process_create_begin(self, process):
        self.handler.on_process_create_begin(process)
    def on_process_create_end(self, process):
        self.handler.on_process_create_end(process)
        process.initial_thread.resume()
    def on_process_exit(self, process):
        self.handler.on_process_exit(process)
    def on_thread_create(self, thread):
        self.handler.on_thread_create(thread)
    def on_thread_exit(self, thread):
        self.handler.on_thread_exit(thread)
    def on_module_load(self, module):
        self.handler.on_module_load(module)
    def on_module_unload(self, module):
        self.handler.on_module_unload(module)
    def on_breakpoint(self, thread, context, bp):
        self.handler.on_breakpoint(thread, context, bp)
    def on_single_step(self, thread):
        self.handler.on_single_step(thread)
    def on_exception(self, thread, info, first_chance):
        self.handler.on_exception(thread, info, first_chance)
        # Hmm, so far we won't be returning anything else?
        return DebuggerAdapter.DBG_EXCEPTION_NOT_HANDLED
#
class ExceptionEvidence(object):
    def __init__(self, xinfo):
        self.info = xinfo
#
class TargetRunner(object):
    "The main test runner, doing a single test run"
    def __init__(self, ignore_exceptions=None):
        self._logger = logging.getLogger()
        self.__dbg = DebuggerAdapter(self)
        self.__pm = ProcessMonitorAdapter(self)
        self.__initial_bp_hit = False
        self.ignore_exceptions = ignore_exceptions
        self.evidence = None
        self.done = False
    def start(self, cmdline):
        self._logger.debug('Running `%s`', cmdline)
        self.__dbg.spawn(cmdline)
    def update(self):
        while self.__dbg.wait_event(50):
            pass
        self.__pm.update()
    def on_process_create_begin(self, process):
        pass
    def on_process_create_end(self, process):
        self._logger.info('%s: created', process)
        self.__pm.track_process(process.id)
        process.initial_thread.resume()
    def on_process_exit(self, process):
        self._logger.info('%s: exited', process)
        # Process gets untracked automatically
        # self.__pm.untrack_process(process.id)
        if not self.__dbg.processes:
            self.done = True
            self._logger.debug('Execution completed')
    def on_thread_create(self, thread):
        self._logger.debug('%s: created', thread)
    def on_thread_exit(self, thread):
        self._logger.debug('%s: exited', thread)
    def on_module_load(self, module):
        self._logger.debug('Loaded %s', module)
    def on_module_unload(self, module):
        self._logger.debug('Unloaded %s', module)
    def on_breakpoint(self, thread, context, bp):
        if not self.__initial_bp_hit:
            self.__initial_bp_hit = True
            return
        # Didn't expect the breakpoint.
        pass
    def on_single_step(self, thread):
        # Single stepping is not expected.
        pass
    def on_exception(self, thread, info, first_chance):
        self._logger.info('%s: %s (%s)', thread, info, "1st chance" if first_chance else "2nd chance")
        if first_chance:
            # Log and be done; might be expected/handled
            return
        if info.code not in self.ignore_exceptions:
            self.evidence = ExceptionEvidence(info)
        self._terminate_target()
    def on_process_idle(self, process_id):
        process = self.__dbg.processes[process_id]
        self._logger.info('%s: idle', process)
        self._terminate_target()
    def _terminate_target(self):
        for pid, process in self.__dbg.processes.iteritems():
            process.terminate()
#
