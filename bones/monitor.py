"""
Layer 2 of the METALBONES core -- Python wrappers.

This wraps CPython objects and adds more functionality that
can be more easily implemented in Python than in C.
"""

import _bones

class ProcessMonitor(_bones.ProcessMonitor):
    """
    Track processes in the system via NtQuerySystemInformation()
    """
    def __init__(self, delta_threshold=50, max_inactive=3):
        _bones.ProcessMonitor.__init__(self)
        self.delta_threshold = delta_threshold
        self.max_inactive = max_inactive

    def track_process(self, process_id):
        context = {
            'kernel_time' : 0,
            'user_time' : 0,
            'inactive_count' : 0,
        }
        self._track_process(process_id, context)
    def untrack_process(self, process_id):
        self._untrack_process(process_id)

    def on_process_idle(self, process_id):
        pass

    def _on_update(self, process_id, context, kernel_time, user_time):
        kernel_delta = kernel_time - context['kernel_time']
        user_delta = user_time - context['user_time']
        context['kernel_time'] = kernel_time
        context['user_time'] = user_time
        if kernel_delta + user_delta < self.delta_threshold:
            inactive_count = context['inactive_count'] + 1
            context['inactive_count'] = inactive_count
            if inactive_count > self.max_inactive:
                self.on_process_idle(process_id)
                self.untrack_process(process_id)
# EOF