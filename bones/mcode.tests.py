import mcode

class StringReader:
    def __init__(self, data):
        self.data = data
        self.offset = 0
    def read(self):
        b = ord(self.data[self.offset])
        self.offset += 1
        return b

def decode(opcode):
    return mcode.decode(mcode.State(StringReader(opcode)))

p = mcode.Printer()
# add byte es:[si*1+7f], al
print p.print_insn(decode("\x26\x67\x00\x44\x7f"))
# add byte ds:[si*1-0001], al
print p.print_insn(decode("\x67\x00\x84\xff\xff"))
# lea eax, ss:[esp+10]
print p.print_insn(decode("\x8d\x44\x24\x10\x89\x89\x89"))
