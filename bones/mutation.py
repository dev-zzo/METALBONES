"""
Layer 3 of the METALBONES core -- high-level code.

Implements (simple) mutation algorithms.
"""

import random

class Mutator(object):
    def __init__(self, input_length):
        self.active = True
        self.offset = 0
        self.size = 0
    def apply(self, fp):
        if self.active:
            self._apply(fp)
    def _apply(self, fp):
        pass
#
class BitFlipper(Mutator):
    def __init__(self, input_length):
        Mutator.__init__(self, input_length)
        self.offset = random.randint(0, input_length - 1)
        self.size = 1
        self.bitmask = 1 << (random.randint(0, 7))
    def __str__(self):
        return '%08X BitFlip mask %02X' % (self.offset, self.bitmask)
    def _apply(self, fp):
        fp.seek(self.offset)
        x = fp.read(1)
        fp.seek(self.offset)
        fp.write(chr(ord(x) ^ self.bitmask))
#
class ByteSetter(Mutator):
    def __init__(self, input_length):
        Mutator.__init__(self, input_length)
        self.size = 1 << (random.randint(0, 3))
        self.offset = random.randint(0, input_length - self.size)
        self.value = "\xFF" if random.getrandbits(1) else "\x00"
    def __str__(self):
        return '%08X ByteSet %d bytes' % (self.offset, self.size)
    def _apply(self, fp):
        fp.seek(self.offset)
        fp.write(self.value * self.size)
#
def generate_mutations(mutators, input_length, max_mutations):
    mutations = []
    while max_mutations > 0:
        mutator = random.choice(mutators)
        mutations.append(mutator(input_length))
        max_mutations -= 1
    return mutations
def apply_mutations(mutations, fp):
    for mutation in mutations:
        mutation.apply(fp)
# EOF