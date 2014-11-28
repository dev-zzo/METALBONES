"""Microsoft Compound File Binary format"""

import struct
import string
import sys
import os

SIGNATURE = "\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"

DIFAT_SECTOR = 0xFFFFFFFCL
FAT_SECTOR = 0xFFFFFFFDL
END_OF_CHAIN = 0xFFFFFFFEL
FREE_SECTOR = 0xFFFFFFFFL

NO_STREAM = 0xFFFFFFFFL

OBJTYPE_UNKNOWN = 0
OBJTYPE_STORAGE = 1
OBJTYPE_STREAM = 2
OBJTYPE_ROOT_STORAGE = 5

class CFBStorage:
    def __init__(self, name):
        self.name = name
        self.subobjects = []

class CFBRootEntry(CFBStorage):
    def __init__(self):
        CFBStorage.__init__(self, 'Root Entry')

class CFBStream:
    def __init__(self, name):
        self.name = name
    @classmethod
    def create(name):   
        return CFBStream._registry[name]()
    @classmethod
    def register(name, type):
        CFBStream._registry[name] = type
    _registry = {}

class _FileBackend:
    """Support sector r/w on a physical file"""
    def __init__(self, fp, sector_size, offset=512):
        self.fp = fp
        self.sector_size = sector_size
        self.offset = offset

    def read_sector(self, sector_id):
        self.fp.seek(self.offset + sector_id * self.sector_size)
        return self.fp.read(self.sector_size)

    def write_sector(self, sector_id, data):
        self.fp.seek(self.offset + sector_id * self.sector_size)
        self.fp.write(data)

class _StringBackend:
    """Support sector r/w on a string"""
    def __init__(self, data, sector_size):
        self.data = data
        self.sector_size = sector_size

    def read_sector(self, sector_id):
        return self.data[self.sector_size * sector_id : self.sector_size * (sector_id + 1)]

    def write_sector(self, sector_id, data):
        self.data[self.sector_size * sector_id : self.sector_size * (sector_id + 1)] = data

class _StringStream:
    def __init__(self, data):
        self.data = data
        self.ptr = 0
    def read(self, size):
        result = self.data[self.ptr:self.ptr+size]
        self.ptr += size
        return result
    def write(self, data):
        self.data[self.ptr:self.ptr+len(data)] = data
        self.ptr += len(data)
    def seek(self, offset):
        self.ptr = offset

class _FatTable:
    def __init__(self, chains=None):
        self.chains = chains if chains is not None else []

    def get_next(self, sector_id):
        return self.chains[sector_id]
    def set_next(self, sector_id, next_sector_id):
        self.chains[sector_id] = next_sector_id
    
    def allocate_one(self):
        """Allocate a chain of 1 sector."""
        sector_id = 0
        try:
            while self.get_next(sector_id) != FREE_SECTOR:
                sector_id += 1
        except IndexError:
            self.chains.append(FREE_SECTOR)
        self.set_next(sector_id, END_OF_CHAIN)
        
    def truncate_chain(self, sector_id):
        next_sector_id = self.get_next(sector_id)
        self.set_next(sector_id, END_OF_CHAIN)
        while next_sector_id != END_OF_CHAIN:
            next_sector_id = self.get_next(sector_id)
            self.set_next(sector_id, FREE_SECTOR)
            sector_id = next_sector_id
        
    def allocate_chain(self, size):
        """Allocate a chain of size bytes, and return sector id of 1st sector."""
        start_sector_id = self.allocate_one()
        sector_id = start_sector_id
        size -= 1
        
        while size > 0:
            next_sector_id = self.allocate_one()
            self.set_next(sector_id, next_sector_id)
            sector_id = next_sector_id
            size -= 1
#

def stream_read(sector_id, fat, be):
    sectors = []
    while sector_id != END_OF_CHAIN:
        sectors.append(be.read_sector(sector_id))
        sector_id = fat.get_next(sector_id)
    return ''.join(sectors)

def parse_entry(directory, entry, parent=None):
    if entry['object_type'] == OBJTYPE_STREAM:
        try:
            n = CFBStream.create(entry['name'])
        except KeyError:
            n = CFBStream()
    elif entry['object_type'] == OBJTYPE_STORAGE:
        n = CFBStorage(entry['name'])
    elif entry['object_type'] == OBJTYPE_ROOT_STORAGE:
        n = CFBRootEntry()
    else:
        raise ValueError('Unknown object type')
    if parent is not None:
        parent.subobjects.append(n)
    if entry['child_id'] != NO_STREAM:
        parse_entry(directory, directory[entry['child_id']], n)
    if entry['left_sibling_id'] != NO_STREAM:
        parse_entry(directory, directory[entry['left_sibling_id']], parent)
    if entry['right_sibling_id'] != NO_STREAM:
        parse_entry(directory, directory[entry['right_sibling_id']], parent)
    return n
    
def load(path):
    fp = open(path, 'rb')
    fields = struct.unpack('<8s16xHHHHH6x9I109I', fp.read(512))
    if fields[0] != SIGNATURE:
        raise TypeError('Invalid signature')
    minor_version = fields[1]
    major_version = fields[2]
    bom = fields[3]
    sector_size = 1 << fields[4]
    minifat_sector_size = 1 << fields[5]
    #directory_sectors_count = fields[6]
    fat_sectors_count = fields[7]
    directory_start_sector = fields[8]
    #transaction_number = fields[9]
    minifat_stream_cutoff = fields[10]
    minifat_start_sector = fields[11]
    minifat_sectors_count = fields[12]
    difat_start_sector = fields[13]
    difat_sectors_count = fields[14]
    difat_data = list(fields[15:])
    
    be = _FileBackend(fp, sector_size)
    
    # Read in DIFAT
    difat_next_sector = difat_start_sector
    while difat_next_sector != END_OF_CHAIN:
        chains = struct.unpack('128I', be.read_sector(difat_next_sector))
        difat_data.extend(chains[:-1])
        difat_next_sector = chains[-1]
    print '%d entries in DIFAT' % len(difat_data)
    
    # Read in FAT
    unpack_format = '<' + str(sector_size // 4) + 'I'
    fat_sector = 0
    fat_data = []
    while fat_sector < fat_sectors_count:
        print 'FAT sector: %d' % difat_data[fat_sector]
        fat_data.extend(struct.unpack(unpack_format, be.read_sector(difat_data[fat_sector])))
        fat_sector += 1
    fat = _FatTable(chains=fat_data)
    
    # Read in MiniFAT
    print 'MiniFAT start: %d' % minifat_start_sector
    minifat_raw = stream_read(minifat_start_sector, fat, be)
    unpack_format = '<' + str(len(minifat_raw) // 4) + 'I'
    minifat_data = list(struct.unpack(unpack_format, minifat_raw))
    minifat = _FatTable(chains=minifat_data)
    mini_stream_start_sector = None
    
    # Read in Directory
    directory_raw = stream_read(directory_start_sector, fat, be)
    stream = _StringStream(directory_raw)
    directory = []
    root_entry = None
    try:
        while True:
            fields = struct.unpack('<64sHBBIII16sIQQIQ', stream.read(128))
            name_length = fields[1]
            entry_name = fields[0][:name_length - 2].decode('utf-16', 'ignore') if name_length > 0 else ''
            entry_object_type = fields[2]
            if entry_object_type == OBJTYPE_UNKNOWN:
                continue
            print 'Entry: "%s"' % entry_name
            entry = {
                'name': entry_name,
                'object_type': entry_object_type,
                'color': fields[3],
                'left_sibling_id': fields[4],
                'right_sibling_id': fields[5],
                'child_id': fields[6],
                #entry_clsid = fields[7]
                #entry_state_bits = fields[8]
                #entry_created_time = fields[9]
                #entry_modified_time = fields[10]
                'stream_start_sector': fields[11],
                'stream_size': fields[12],
                }
            print 'Type: %d' % entry['object_type']
            print 'Left: %d Right: %d Child: %d' % (entry['left_sibling_id'], entry['right_sibling_id'], entry['child_id'])
            directory.append(entry)
            if entry['object_type'] == OBJTYPE_ROOT_STORAGE:
                root_entry = entry
                mini_stream_start_sector = entry['stream_start_sector']
            print
    except:
        pass

def save(path, root):
    pass

if __name__ == '__main__':
    print "Testing"
    load('apc.doc')

