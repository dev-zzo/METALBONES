"""Larva controls test run execution on a single machine.

"""

import os
import sys
import time
import subprocess
import pickle
import argparse
import runner
import logging
import xmlrpclib

class RunnerJob:
    """Contains a job item to be run via a runner process"""
    def __init__(self, id, cmdline, options={}):
        self.id = id
        self.args = ['python', 'runner.py']
        for opt in options.keys():
            self.args.append('--%s=%s' % (opt, options[opt]))
        self.args.append(cmdline)
        self.proc = None
    
    def __hash__(self):
        return hash(self.id)

    def run(self):
        self.proc = subprocess.Popen(self.args, 
            # stdout=subprocess.PIPE, 
            # bufsize=-1, 
            # universal_newlines=True, 
            creationflags=subprocess.CREATE_NEW_CONSOLE)
        
    def poll(self):
        rc = self.proc.poll()
        if rc is None:
            return False
        return True

class Larva:
    def __init__(self, args):
        self.next_refill_time = 0
        self.instance_id = args.instance_id
        self._pool_size = args.pool_size
        self._pool = set()
        self._proxy = xmlrpclib.ServerProxy(args.neuron_url, allow_none=True)

    def run(self):
        logging.info('Larva signing on...')
        result = self._proxy.signon(self.instance_id)

        logging.info('Running...')

        try:
            while True:
                self._poll_jobs()
                if len(self._pool) < self._pool_size:
                    self._refill_queue()
                time.sleep(0.25)
        except KeyboardInterrupt:
            logging.error('Control-C pressed, exiting the loop.')
            pass

        logging.info('Larva signing off...')
        result = self._proxy.signoff(self.instance_id)

    def _process_retired_job(self, job):
        logging.info('Job %s completed.', job.id)
        
        blob_path = os.path.join(os.environ['TEMP'], job.id)
        os.remove(blob_path)
        
        log_path = blob_path + '.log'
        with open(log_path, 'r') as fp:
            log_text = fp.read()
        os.remove(log_path)
        
        report_path = blob_path + '.rpt'
        with open(report_path, 'r') as fp:
            report = pickle.load(fp)
        os.remove(report_path)

        logging.info('Reporting to the server...')
        call_result = self._proxy.complete_job(self.instance_id, job.id, report)
        
    def _poll_jobs(self):
        retired = []
        for j in self._pool:
            if j is None:
                continue
            if j.poll():
                retired.append(j)
        for j in retired:
            self._pool.remove(j)
            self._process_retired_job(j)
        return len(retired) > 0

    def _refill_queue(self):
        if self.next_refill_time > time.time():
            return

        logging.info('Refilling jobs...')
        while len(self._pool) < self._pool_size:
            try:
                job_data = self._proxy.fetch_job(self.instance_id)
            except xmlrpclib.Fault as err:
                logging.info('Fault occurred when fetching jobs: %s', err.faultString)
                self.next_refill_time = time.time() + 20
                break
            
            job_id = job_data['id']
            
            # This only works for blobs supplied via disk files...
            blob_path = os.path.join(os.environ['TEMP'], job_id)
            with open(blob_path, 'wb') as blob_file:
                blob_file.write(job_data['blob'].data)
            
            cmdline = job_data['cmdline']
            cmdline = cmdline.replace('{BLOBPATH}', blob_path)
            options = {
                'log': blob_path + '.log',
                'report': blob_path + '.rpt',
                }
            job = RunnerJob(job_id, cmdline, options=options)
            self._pool.add(job)
            job.run()
#

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Larva: local test execution controller.')
    parser.add_argument('--instance-id',
        help='my instance, identifies me within the swarm',
        required=True)
    parser.add_argument('--neuron-url',
        help='swarm controller XMLRPC URL',
        default='http://localhost:8300/')
    parser.add_argument('--pool-size',
        help='how many runners to spawn',
        type=int,
        default=4)
    parser.add_argument('--log',
        help='where to output log text, default=stderr',
        type=argparse.FileType('w'),
        default=sys.stderr)
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)-15s %(levelname)8s %(message)s', stream=args.log, level='INFO')

    logging.info('Larva ID %s starting up.', args.instance_id)

    larva = Larva(args)
    larva.run()

    logging.info('Goodbye.')
