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

pool = runner.RunnerPool(4)

def process_retired(job):
    pass

try:
    while True:
        retired = pool.poll()
        for job in retired:
            process_retired(job)
        time.sleep(0.25)
        
except KeyboardInterrupt:
    pass
