"""Entities related to performing an actual test run."""

from __future__ import print_function
import sys
import os
import pickle
import hashlib
import argparse
import subprocess
import collections
import logging
import bones
import mcode

class MemReader:
    def __init__(self, process, address):
        # No insns should be longer than 16 bytes, so try read them all
        self.data = process.read_memory(address, 16)
        self.offset = 0
    def read(self):
        b = ord(self.data[self.offset])
        self.offset += 1
        return b

def format_insn_at(self, process, address):
    try:
        reader = MemReader(process, address)
    except:
        return '%08x %-22s' % (address, '???')
    insn = mcode.decode(mcode.State(reader))
    return '%08x %-22s %s' % (address, insn.opcode_hex, mcode.Printer().print_insn(insn))

class Runner(bones.Debugger):
    """Actual runner that runs and controls the target"""

    def __init__(self, args):
        bones.Debugger.__init__(self)
        self.args = args
        self.initial_process = None
        self.ldr_breakpoint_hit = False
        self.done = False
        self.initial_process_exited = False
        self.timed_out = False
        self.report = {}
    
    def on_timeout(self):
        self.report['status'] = 'timeout'
        self.timed_out = True
        self.done = True

    def on_process_create(self, p):
        logging.info('[%05d] Process creation in progress.', p.id)
        if self.initial_process is None:
            self.initial_process = p

    def on_process_created(self, p):
        logging.info('[%05d] Process created.', p.id)
        logging.info('[%05d] Entry point = %08x.', p.id, p.image.entry_point)

    def on_thread_create(self, t):
        logging.info('[%05d/%05d] Thread created.', t.process.id, t.id)

    def on_thread_exit(self, t):
        logging.info('[%05d/%05d] Thread exited, status %08x.', t.process.id, t.id, t.exit_status)

    def on_process_exit(self, p):
        logging.info("[%05d] Process exited, status %08x.", p.id, p.exit_status)
        if p.id == self.initial_process.id:
            self.initial_process = None
            self.initial_process_exited = True
            self.done = True

    def on_module_load(self, m):
        logging.info('[%05d] Module loaded at %08x~%08x: %s.',
            m.process.id,
            m.base_address,
            m.base_address + m.mapped_size - 1,
            m.name)

    def on_module_unload(self, m):
        logging.info('[%05d] Module unloaded at %08x: %s.', m.process.id, m.base_address, m.name)

    def on_exception(self, thread, exc_info, first_chance):
        logging.info('[%05d/%05d] %s (%s-chance).',
            thread.process.id, thread.id,
            str(exc_info),
            '1st' if first_chance else '2nd')
        
        # TODO: handle 1st-chance right away?
        if first_chance and not self.args.handle_1st_chance:
            logging.info('[%05d/%05d] First-chance, passing to the application.', thread.process.id, thread.id)
            return bones.Debugger.DBG_EXCEPTION_NOT_HANDLED

        logging.critical('[%05d/%05d] Not handled by the target; reporting.', thread.process.id, thread.id)
        self.prepare_exception_report(thread, exc_info)
        return bones.Debugger.DBG_EXCEPTION_NOT_HANDLED

    def on_breakpoint(self, thread):
        process = thread.process
        logging.info('[%05d/%05d] Breakpoint hit.', process.id, thread.id)

        if not self.ldr_breakpoint_hit:
            loc = process.get_location_from_va(thread.context.eip)
            if loc.module is not None and loc.module.name.lower() == 'ntdll.dll':
                logging.info('[%05d/%05d] Initial breakpoint in LdrpInitializeProcess, ignoring.', process.id, thread.id)
                self.ldr_breakpoint_hit = True
                return

        logging.critical('[%05d/%05d] Not handled by the target; reporting.', thread.process.id, thread.id)
        self.prepare_breakpoint_report(thread)
        self.done = True

    def run(self):
        if not self.args.enable_debug_heap:
            # http://msdn.microsoft.com/en-us/library/windows/hardware/ff545528%28v=vs.85%29.aspx
            os.environ['_NO_DEBUG_HEAP'] = '1'
        
        if self.args.working_dir is not None:
            os.chdir(self.args.working_dir)
        logging.critical('Running: %s', self.args.cmdline)
        self.spawn(self.args.cmdline)
        
        wait_quantum = 250
        timeout_count = (self.args.timeout * 1000) // wait_quantum
        while not self.done:
            if not self.wait_event(wait_quantum):
                # wait_event() timed out
                if not self.timed_out:
                    timeout_count -= 1
                    if timeout_count < 0:
                        self.on_timeout()
        logging.critical('Debugger loop exited cleanly.')
    
    def prepare_exception_report(self, thread, exc_info):
        self.report['status'] = 'exception'
        context = thread.context
        loc = thread.process.get_location_from_va(context.eip)
        self.report['at'] = str(loc)
        self.report['hash'] = hashlib.md5(self.report['status'] + self.report['at']).hexdigest()
        self.report['context'] = str(context)
        self.report['info'] = {
            'code': exc_info.code,
            'args': exc_info.args,
            }
    def prepare_breakpoint_report(self, thread):
        self.report['status'] = 'breakpoint'
        context = thread.context
        context.eip -= 1
        loc = thread.process.get_location_from_va(context.eip)
        self.report['at'] = str(loc)
        self.report['hash'] = hashlib.md5(self.report['status'] + self.report['at']).hexdigest()
        self.report['context'] = str(context)

class RunnerJob:
    """Contains a job item to be run via a runner process"""
    def __init__(self, cmdline, options={}):
        self.args = ['python', 'runner.py', cmdline]
        for opt in options.keys():
            self.args.append('--%s=%s' % (opt, options[opt]))
        self.proc = None
        self.report = None
    
    def run(self):
        self.proc = subprocess.Popen(self.args, stdout=subprocess.PIPE, bufsize=-1, universal_newlines=True)
        
    def poll(self):
        rc = self.proc.poll()
        if rc is None:
            return False
        self.report = pickle.load(self.proc.stdout)
        return True

class RunnerPool:
    """Handles queueing of RunnerJobs"""
    def __init__(self, size = 4):
        self.size = size
        self.pool = set()
        self.queue = collections.deque()
        
    def enqueue(self, job):
        self.queue.append(job)
    
    def poll(self):
        retired = []
        for j in self.pool:
            if j is None:
                continue
            if j.poll():
                retired.append(j)
        for j in retired:
            self.pool.remove(j)
        try:
            while len(self.pool) < self.size:
                j = self.queue.popleft()
                self.pool.add(j)
                j.run()
        except IndexError:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Runner: run the target and control the execution.')
    parser.add_argument('cmdline',
        help='the command to run')
    parser.add_argument('--timeout',
        help='hard timeout, seconds',
        type=int,
        default=15)
    parser.add_argument('--working-dir',
        help='working directory for the target')
    parser.add_argument('--log',
        help='where to output log text, default=stderr',
        type=argparse.FileType('w'),
        default=sys.stderr)
    parser.add_argument('--enable-debug-heap',
        help='allow RTL to use debug heap',
        action='store_true')
    parser.add_argument('--handle-1st-chance',
        help='terminate the target on 1st chance exception',
        action='store_true')
    args = parser.parse_args()
    
    logging.basicConfig(format='%(asctime)-15s %(levelname)8s %(message)s', stream=args.log, level='INFO')
    
    r = Runner(args)
    r.run()
    pickle.dump(r.report, sys.stdout)
    sys.stdout.flush()
