import monitor
import time

class TestMon(monitor.ProcessMonitor):
    def on_process_idle(self, process_id):
        print "Process %d detected as idle." % process_id

m = TestMon()
m.track_process(3400)
while True:
    m.update()
    time.sleep(0.5)
    print '.'
