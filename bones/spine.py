"""Entities related to controlling the whole flow"""

from __future__ import print_function
import sys
import os
import time
import hashlib
import argparse
import runner
import logging

parser = argparse.ArgumentParser(description='Spine: main module.')
parser.add_argument('cmdline',
    help='the command to run')
parser.add_argument('--log',
    help='where to output log text, default=stderr',
    type=argparse.FileType('w'),
    default=sys.stderr)

logging.basicConfig(format='%(asctime)-15s %(levelname)8s %(message)s', stream=args.log, level='INFO')

pool = runner.RunnerPool(4)

def run_next():
    pass

def process_retired(job):
    """Handle the retired job and enqueue the next one."""
    pass

try:
    while True:
        retired = pool.poll()
        for job in retired:
            process_retired(job)
        time.sleep(0.25)
        
except KeyboardInterrupt:
    pass
