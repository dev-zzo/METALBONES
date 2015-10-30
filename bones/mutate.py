import random

class FlipBit:
    def __init__(self, offset=None, bit=None):
        self.offset = offset
        self.bit = bit
    def __repr__(self):
        return 'FlipBit(offset=0x%08x, bit=%d)' % (self.offset, self.bit)
    def apply(self, target):
        self.offset = random.randint(0, len(target) - 1) if self.offset is None else self.offset
        self.bit = random.randint(0, 7) if self.bit is None else self.bit
        target.seek(offset)
        byte = chr(ord(target.read(1)) ^ (1 << self.bit))
        target.seek(offset)
        target.write(byte)
        
class WriteBytes:
    def __init__(self, offset=None, count=None, value=' '):
        self.offset = offset
        self.count = count
        self.value = value
    def __repr__(self):
        return 'WriteBytes(offset=0x%08x, count=%d, value=0x%02x)' % (self.offset, self.count, self.value)
    def apply(self, target):
        self.count = random.choice((1, 2, 4, 8)) if self.count is None else self.count
        self.offset = random.randint(0, len(target)) if self.offset is None else self.offset
        target.seek(offset)
        target.write(self.value * self.count)
class WriteFF(WriteBytes):
    def __init__(self, offset=None, count=None):
        WriteBytes.__init__(self, offset=offset, count=count, value="\xFF")
    def __repr__(self):
        return 'WriteFF(offset=0x%08x, count=%d)' % (self.offset, self.count)
class Write00(WriteBytes):
    def __init__(self, offset=None, count=None):
        WriteBytes.__init__(self, offset=offset, count=count, value="\x00")
    def __repr__(self):
        return 'Write00(offset=0x%08x, count=%d)' % (self.offset, self.count)
class Write20(WriteBytes):
    def __init__(self, offset=None, count=None):
        WriteBytes.__init__(self, offset=offset, count=count, value=" ")
    def __repr__(self):
        return 'Write00(offset=0x%08x, count=%d)' % (self.offset, self.count)
