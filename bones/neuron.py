"""Neuron orchestrates test execution among larva slaves.
"""

import sys
import argparse
import logging
import xmlrpclib
import SimpleXMLRPCServer
import hashlib
import random
import os

class Neuron:
    def __init__(self):
        host = 'localhost'
        port = 8300
        self.server = SimpleXMLRPCServer.SimpleXMLRPCServer((host, port), allow_none=True)
        self.server.register_instance(self)
        logging.info('Larva XMLRPC listening on http://%s:%d/', host, port)
    
    def run(self):
        logging.info('Entering server loop.')
        self.server.serve_forever()
    
    def signon(self, larva_id):
        logging.info('Larva ID %s signed on.', larva_id)
        return True

    def signoff(self, larva_id):
        logging.info('Larva ID %s signed off.', larva_id)
        return True
    
    def fetch_job(self, larva_id):
        logging.info('Larva ID %s asking for a job.', larva_id)
        job = self._get_next_job()
        logging.info('Larva ID %s gets job %s.', larva_id, job['id'])
        return job
    
    def complete_job(self, larva_id, job_id, report):
        logging.info('Larva ID %s completed job %s.', larva_id, job_id)
        self._process_completed_job(job_id, report)
        return True

    def _get_next_job(self):
        return {
            'cmdline': 'IDontExist',
            'id': 'BogusJobId',
            'blob': xmlrpclib.Binary('AAAAA'),
            }

    def _process_completed_job(self, job_id, report):
        pass
#

class RandomNeuron(Neuron):
    def _get_next_job(self):
        max_len = random.randint(1, 32768)
        s = ''
        while max_len > 0:
            s += chr(random.randint(0, 255))
            max_len -= 1
        
        hash = hashlib.sha1(s).hexdigest()
        with open(hash + '.job', 'wb') as fp:
            fp.write(s)
        return {
            'cmdline': '"c:\Projects\OITVictims\Release\CheckFileId.exe" "{BLOBPATH}"',
            'id': hash,
            'blob': xmlrpclib.Binary(s),
            }

    def _process_completed_job(self, job_id, report):
        logging.info('Job run result: %s', report['status'])
        if report['status'] == 'nothing':
            os.remove(job_id + '.job')
            logging.info('Job %s junked.', job_id)
            return
        pass

logging.basicConfig(format='%(asctime)-15s %(levelname)8s %(message)s', level='INFO')

n = RandomNeuron()
n.run()

