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
    reader = StringReader(opcode)
    state = mcode.State(reader)
    insn = state.decode()
    return insn

# add byte ds:[si*1-0001], al
print decode("\x67\x00\x44\x7f")
# add byte ds:[si*1-0001], al
print decode("\x67\x00\x84\xff\xff")

