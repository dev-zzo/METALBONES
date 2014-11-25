"""Entities related to controlling the whole flow"""

from __future__ import print_function
import sys
import os
import time
import hashlib
import argparse
import runner

#

rj = runner.RunnerJob('victim.exe 1', options={'timeout': 10})
rj.run()
while not rj.poll():
    time.sleep(0.5)
