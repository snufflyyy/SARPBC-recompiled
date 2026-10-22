"""Tagged properties of a UE3 object body (package version 539), read and written.

parse_body(u, off, size, names)   -> Body(prefix, tags, tail)
Body.build()                      -> bytes (tags re-encoded, 'None' terminator, tail)
parse_tags(b, p, names)           -> (tags, end)   a struct's property list
encode_tags(tags, none_idx)       -> bytes

A tag is a dict: name (i, n), type (i, n), size, index, extra (bytes: the struct /
enum name of Struct and Byte properties, the u32 value of Bool properties) and
value (bytes). The name table indices are kept as they are, so an edit that only
changes values never needs the name table. Array values are `u32 count` plus the
elements; an array of structs holds one tag list (ending with 'None') per element.

A default object body starts with one 4-byte word before the first tag.
"""
import struct


def _name(names, i, n):
    return names[i] + ('_%d' % (n - 1) if n else '')


class Tag(dict):
    @property
    def pname(self):
        return self['pname']


def parse_tags(b, p, names):
    tags = []
    none = names.index('None')
    while True:
        ni, nn = struct.unpack_from('>II', b, p)
        p += 8
        if ni == none and nn == 0:
            return tags, p
        ti, tn = struct.unpack_from('>II', b, p)
        p += 8
        size, aidx = struct.unpack_from('>ii', b, p)
        p += 8
        typ = names[ti]
        extra = b''
        if typ in ('StructProperty', 'ByteProperty'):
            extra = b[p:p + 8]
            p += 8
        elif typ == 'BoolProperty':
            extra = b[p:p + 4]
            p += 4
        tags.append(Tag(name=(ni, nn), type=(ti, tn), size=size, index=aidx, extra=extra,
                        value=bytes(b[p:p + size]), pname=_name(names, ni, nn), ptype=typ))
        p += size


def encode_tags(tags, none_idx):
    out = bytearray()
    for t in tags:
        out += struct.pack('>II', *t['name']) + struct.pack('>II', *t['type'])
        out += struct.pack('>ii', len(t['value']), t['index']) + t['extra'] + t['value']
    out += struct.pack('>II', none_idx, 0)
    return bytes(out)


class Body:
    def __init__(self, prefix, tags, tail, none_idx):
        self.prefix, self.tags, self.tail, self.none_idx = prefix, tags, tail, none_idx

    def get(self, pname):
        return [t for t in self.tags if t['pname'] == pname][0]

    def build(self):
        return self.prefix + encode_tags(self.tags, self.none_idx) + self.tail


def parse_body(u, off, size, names, skip=4):
    b = bytes(u[off:off + size])
    tags, end = parse_tags(b, skip, names)
    return Body(b[:skip], tags, b[end:], names.index('None'))


# ---- arrays of structs ------------------------------------------------------

def parse_struct_array(value, names):
    """value of an ArrayProperty of structs -> list of tag lists."""
    n = struct.unpack_from('>I', value, 0)[0]
    p = 4
    out = []
    for _ in range(n):
        tags, p = parse_tags(value, p, names)
        out.append(tags)
    if p != len(value):
        raise ValueError('array of structs: %d bytes left over' % (len(value) - p))
    return out


def encode_struct_array(elements, none_idx):
    return struct.pack('>I', len(elements)) + b''.join(encode_tags(e, none_idx) for e in elements)


def fstring_value(text):
    """An FString property value: i32 length including the NUL, then ASCII."""
    raw = text.encode('latin-1') + b'\0'
    return struct.pack('>i', len(raw)) + raw


def read_fstring(value):
    n = struct.unpack_from('>i', value, 0)[0]
    return value[4:4 + n].rstrip(b'\0').decode('latin-1')
