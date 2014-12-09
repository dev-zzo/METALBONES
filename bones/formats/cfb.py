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
    def __str__(self):
        return "Storage '%s' (%d children)" % (self.name, len(self.subobjects))

class CFBRootEntry(CFBStorage):
    def __init__(self):
        CFBStorage.__init__(self, 'Root Entry')

class CFBStream:
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return "Stream '%s'" % (self.name)
    def parse(self, data):
        self.raw_data = data
    @staticmethod
    def create(name):   
        return CFBStream._registry[name]()
    @staticmethod
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
    """Support sector r/w on a string -- MiniFAT"""
    def __init__(self, data, sector_size):
        self.data = data
        self.sector_size = sector_size

    def read_sector(self, sector_id):
        return self.data[self.sector_size * sector_id : self.sector_size * (sector_id + 1)]

    def write_sector(self, sector_id, data):
        self.data[self.sector_size * sector_id : self.sector_size * (sector_id + 1)] = data

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

class _DirEntry:
    def __init__(self):
        self.name = u''
        self.object_type = OBJTYPE_UNKNOWN
        self.color = 1
        self.left_sibling_id = NO_STREAM
        self.right_sibling_id = NO_STREAM
        self.child_id = NO_STREAM
        self.clsid = "\x00" * 16
        self.state_bits = 0
        self.created_time = 0
        self.modified_time = 0
        self.stream_start_sector = 0
        self.stream_size = 0
    def __str__(self):
        return 'Entry: "%s" (%d bytes), type %d' % (self.name, self.stream_size, self.object_type)
    def unpack(self, data):
        (name, name_length, self.object_type, self.color, 
            self.left_sibling_id, self.right_sibling_id, self.child_id,
            self.clsid, self.state_bits, self.created_time, self.modified_time,
            self.stream_start_sector, self.stream_size) = _DirEntry.__format.unpack(data)
        self.name = name[:name_length - 2].decode('utf-16', 'ignore') if name_length > 0 else u''
    def pack(self):
        name = (self.name + '\0').encode('utf-16', 'ignore')
        name_length = len(name)
        return _DirEntry.__format.pack(name, name_length, self.object_type, self.color,
            self.left_sibling_id, self.right_sibling_id, self.child_id,
            self.clsid, self.state_bits, self.created_time, self.modified_time,
            self.stream_start_sector, self.stream_size)
    __format = struct.Struct('<64sHBBIII16sIQQIQ')

def pieces(s, length):
    start = 0
    while start < len(s):
        yield s[start:start + length]
        start += length

def stream_read(sector_id, fat, be):
    sectors = []
    while sector_id != END_OF_CHAIN:
        sectors.append(be.read_sector(sector_id))
        sector_id = fat.get_next(sector_id)
    return ''.join(sectors)

def parse_entry(directory, entry, parent=None):
    if entry.object_type == OBJTYPE_STREAM:
        try:
            n = CFBStream.create(entry.name)
        except KeyError:
            n = CFBStream(entry.name)
        n.parse(entry.data)
    elif entry.object_type == OBJTYPE_STORAGE:
        n = CFBStorage(entry.name)
    elif entry.object_type == OBJTYPE_ROOT_STORAGE:
        n = CFBRootEntry()
    else:
        raise ValueError('Unknown object type')
    if parent is not None:
        parent.subobjects.append(n)
    if entry.child_id != NO_STREAM:
        parse_entry(directory, directory[entry.child_id], n)
    if entry.left_sibling_id != NO_STREAM:
        parse_entry(directory, directory[entry.left_sibling_id], parent)
    if entry.right_sibling_id != NO_STREAM:
        parse_entry(directory, directory[entry.right_sibling_id], parent)
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
    
    # Read in Directory
    directory_raw = stream_read(directory_start_sector, fat, be)
    directory = []
    root_entry = None
    for piece in pieces(directory_raw, 128):
        entry = _DirEntry()
        entry.unpack(piece)
        if entry.object_type == OBJTYPE_UNKNOWN:
            continue
        print str(entry)
        directory.append(entry)
        if entry.object_type == OBJTYPE_ROOT_STORAGE:
            root_entry = entry
            # Read in MiniFAT
            if root_entry.stream_start_sector != END_OF_CHAIN:
                minifat_raw = stream_read(minifat_start_sector, fat, be)
                unpack_format = '<' + str(len(minifat_raw) // 4) + 'I'
                minifat_data = list(struct.unpack(unpack_format, minifat_raw))
                minifat = _FatTable(chains=minifat_data)
                mbe = _StringBackend(stream_read(root_entry.stream_start_sector, fat, be), minifat_sector_size)

    # Read stream data
    for entry in directory:
        if entry.object_type != OBJTYPE_STREAM:
            continue
        if entry.stream_size < minifat_stream_cutoff:
            data = stream_read(entry.stream_start_sector, minifat, mbe)
        else:
            data = stream_read(entry.stream_start_sector, fat, be)
        entry.data = data
    return parse_entry(directory, root_entry)
    
def save(path, root):
    pass

if __name__ == '__main__':
    print "Testing"
    d = load('2014723154316.xls')
    print d

